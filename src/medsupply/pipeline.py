"""Snapshot pipeline. SQLite local baseline; PostgreSQL uses the same table contract."""
import csv
import hashlib
import io
import json
import os
import sqlite3
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

SOURCE_URL = "https://anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv"
FIELDS = {
    "PZN": "pzn", "ENR": "enr", "Bearbeitungsnummer": "report_id",
    "Referenzierte Erstmeldung": "referenced_report", "Meldungsart": "report_type",
    "Beginn": "start_date", "Ende": "expected_end_date",
    "Datum der letzten Meldung": "source_updated", "Art des Grundes": "reason_type",
    "Arzneimittlbezeichnung": "product", "Atc Code": "atc", "Wirkstoffe": "ingredient",
    "Krankenhausrelevant": "hospital_relevant", "Zulassungsinhaber": "manufacturer",
    "Grund": "reason", "Anm. zum Grund": "reason_note",
    "Datum der Erstmeldung": "first_reported", "Darreichungsform": "dosage_form",
    "klassifikation": "classification",
}
DATES = {"start_date", "expected_end_date", "source_updated", "first_reported"}
COLS = ["product_key", *FIELDS.values(), "critical_flag", "content_hash"]
SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
 run_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL, source_sha256 TEXT NOT NULL,
 status TEXT NOT NULL, source_rows INTEGER NOT NULL, accepted_rows INTEGER NOT NULL,
 rejected_rows INTEGER NOT NULL, error TEXT NOT NULL, source_url TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS snapshots (
 snapshot_id TEXT PRIMARY KEY, observed_at TEXT NOT NULL UNIQUE,
 source_sha256 TEXT NOT NULL, raw_path TEXT NOT NULL, source_url TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS observations (
 snapshot_id TEXT NOT NULL, product_key TEXT NOT NULL,
 pzn TEXT NOT NULL, enr TEXT NOT NULL, report_id TEXT NOT NULL,
 referenced_report TEXT NOT NULL, report_type TEXT NOT NULL,
 start_date TEXT NOT NULL, expected_end_date TEXT NOT NULL,
 source_updated TEXT NOT NULL, reason_type TEXT NOT NULL,
 product TEXT NOT NULL, atc TEXT NOT NULL, ingredient TEXT NOT NULL,
 hospital_relevant TEXT NOT NULL, manufacturer TEXT NOT NULL,
 reason TEXT NOT NULL, reason_note TEXT NOT NULL, first_reported TEXT NOT NULL,
 dosage_form TEXT NOT NULL, classification TEXT NOT NULL,
 critical_flag INTEGER NOT NULL, content_hash TEXT NOT NULL,
 PRIMARY KEY(snapshot_id, product_key),
 FOREIGN KEY(snapshot_id) REFERENCES snapshots(snapshot_id));
CREATE TABLE IF NOT EXISTS quarantine (
 run_id TEXT NOT NULL, row_number INTEGER NOT NULL, issue TEXT NOT NULL, row_json TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS changes (
 snapshot_id TEXT NOT NULL, product_key TEXT NOT NULL, change_type TEXT NOT NULL,
 field TEXT NOT NULL, old_value TEXT NOT NULL, new_value TEXT NOT NULL,
 PRIMARY KEY(snapshot_id, product_key, change_type, field));
CREATE INDEX IF NOT EXISTS obs_snapshot ON observations(snapshot_id);
CREATE VIEW IF NOT EXISTS current_observations AS
 SELECT o.*,s.observed_at FROM observations o JOIN snapshots s ON o.snapshot_id=s.snapshot_id
 WHERE s.observed_at=(SELECT MAX(observed_at) FROM snapshots);
"""


class Database:
    def __init__(self, path):
        self.postgres = str(path).startswith(("postgres://", "postgresql://"))
        if self.postgres:
            import psycopg
            from psycopg.rows import dict_row
            self.conn = psycopg.connect(str(path), row_factory=dict_row)
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(str(path), timeout=30)
            self.conn.row_factory = sqlite3.Row
            self.conn.execute("PRAGMA foreign_keys=ON")
            self.conn.execute("PRAGMA journal_mode=WAL")
        for sql in SCHEMA.split(";"):
            if sql.strip():
                self.execute(sql)
        self.conn.commit()

    def execute(self, sql, params=()):
        if self.postgres:
            sql = sql.replace("CREATE VIEW IF NOT EXISTS", "CREATE OR REPLACE VIEW")
            sql = sql.replace("?", "%s")
        return self.conn.execute(sql, params)

    def rows(self, sql, params=()):
        return [dict(r) for r in self.execute(sql, params).fetchall()]

    def close(self):
        self.conn.close()


def database_url(root):
    return os.environ.get("DATABASE_URL") or str(Path(root) / "data/medsupply.sqlite")


def fetch(url=SOURCE_URL):
    """Small bounded feed download; explicit retry for transient remote failures."""
    error = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "MedSupplyMonitor/1.0"})
            with urllib.request.urlopen(req, timeout=30) as response:
                data = response.read(10_000_001)
            if len(data) > 10_000_000:
                raise ValueError("Feed exceeds 10 MB safety limit")
            return data
        except (OSError, ValueError) as exc:
            error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"Feed download failed after 3 attempts: {error}")


def clean(value):
    value = (value or "").strip()
    return "" if value.casefold() in {"n/a", "na", "null"} else value


def parse(data):
    try:
        text = data.decode("utf-8-sig")
        encoding = "utf-8-sig"
    except UnicodeDecodeError:
        text = data.decode("cp1252")
        encoding = "cp1252"
    reader = csv.DictReader(io.StringIO(text, newline=""), delimiter=";")
    missing = set(FIELDS) - set(reader.fieldnames or [])
    if missing:
        raise ValueError(f"Source schema missing columns: {sorted(missing)}")
    accepted, rejected, seen = [], [], {}
    for number, raw in enumerate(reader, start=2):
        try:
            if None in raw or any(v is None for v in raw.values()):
                raise ValueError("Malformed column count")
            row = {dest: clean(raw[src]) for src, dest in FIELDS.items()}
            for key in ["enr", "pzn", "report_id", "product", "ingredient", "manufacturer"]:
                if not row[key]:
                    raise ValueError(f"Missing {key}")
            if not row["pzn"].isdigit() or len(row["pzn"]) != 8:
                raise ValueError("PZN must retain eight digits, including leading zeros")
            if row["hospital_relevant"] not in {"ja", "nein"}:
                raise ValueError("Unknown hospital relevance")
            if row["classification"] not in {"versrel", "verskri (auch versrel)", "weder versrel noch verskri"}:
                raise ValueError("Unknown classification")
            for key in DATES:
                if row[key]:
                    row[key] = datetime.strptime(row[key], "%d.%m.%Y").date().isoformat()
            if row["start_date"] and row["expected_end_date"] and row["start_date"] > row["expected_end_date"]:
                raise ValueError("Expected end precedes start")
            # Source has placeholder PZNs; include ENR and product label to avoid merging unrelated products.
            identity = [row[k] for k in ("enr", "pzn", "product")]
            row["product_key"] = hashlib.sha256(json.dumps(identity, ensure_ascii=False).encode()).hexdigest()[:24]
            if row["product_key"] in seen:
                prior_number, prior_raw, prior_row = seen[row["product_key"]]
                if prior_row in accepted:
                    accepted.remove(prior_row)
                    rejected.append({"row_number": prior_number,
                                     "issue": "Conflicting product identity: all matching rows quarantined",
                                     "row": prior_raw})
                raise ValueError("Conflicting product identity: all matching rows quarantined")
            seen[row["product_key"]] = (number, raw, row)
            row["critical_flag"] = int(row["classification"] == "verskri (auch versrel)")
            row["content_hash"] = hashlib.sha256(json.dumps(row, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
            accepted.append(row)
        except ValueError as exc:
            rejected.append({"row_number": number, "issue": str(exc), "row": raw})
    if not accepted:
        raise ValueError("No valid records; refusing to publish an empty snapshot")
    return accepted, rejected, encoding


def ingest(root, data, observed_at=None, source_url=SOURCE_URL):
    root = Path(root)
    stamp = datetime.fromisoformat(observed_at.replace("Z", "+00:00")) if observed_at else datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError("Observation timestamp must include a timezone")
    observed_at = stamp.astimezone(timezone.utc).isoformat(timespec="microseconds")
    sha = hashlib.sha256(data).hexdigest()
    snapshot_id = hashlib.sha256(f"{observed_at}|{sha}".encode()).hexdigest()[:24]
    raw_dir = root / "data/raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    raw_path = raw_dir / f"{sha}.csv"
    # Content addressed immutable raw store; never overwrite different bytes.
    if not raw_path.exists():
        with raw_path.open("xb") as f:
            f.write(data)
    elif hashlib.sha256(raw_path.read_bytes()).hexdigest() != sha:
        raise ValueError("Raw snapshot integrity failure")
    db = Database(database_url(root))
    try:
        if db.postgres:
            db.execute("SELECT pg_advisory_xact_lock(74531001)")
        else:
            db.execute("BEGIN IMMEDIATE")
        existing = db.rows("SELECT * FROM snapshots WHERE observed_at=?", (observed_at,))
        if existing:
            if existing[0]["source_sha256"] != sha:
                raise ValueError("Different source bytes already published at this observation timestamp")
            return {"snapshot_id": snapshot_id, "status": "already_processed"}
        accepted, rejected, encoding = parse(data)
        total = len(accepted) + len(rejected)
        for r in rejected:
            db.execute("INSERT INTO quarantine VALUES (?,?,?,?)", (
                snapshot_id, r["row_number"], r["issue"], json.dumps(r["row"], ensure_ascii=False)))
        status = "failed" if len(rejected) / total > .05 else "success"
        error = "More than 5% rejected; snapshot not published" if status == "failed" else ""
        db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", (
            snapshot_id, observed_at, sha, status, total, len(accepted), len(rejected), error, source_url))
        if status == "failed":
            db.conn.commit()
            raise ValueError(error)
        latest = db.rows("SELECT * FROM snapshots ORDER BY observed_at DESC LIMIT 1")
        if latest and observed_at <= latest[0]["observed_at"]:
            raise ValueError("Out-of-order observation; use a separate database for historical imports")
        previous = {r["product_key"]: r for r in db.rows("SELECT * FROM current_observations")}
        db.execute("INSERT INTO snapshots VALUES (?,?,?,?,?)", (
            snapshot_id, observed_at, sha, str(raw_path.relative_to(root)), source_url))
        marks = ",".join("?" for _ in range(len(COLS) + 1))
        for r in accepted:
            db.execute(f"INSERT INTO observations(snapshot_id,{','.join(COLS)}) VALUES ({marks})", (
                snapshot_id, *[r[k] for k in COLS]))
            if not latest:
                continue  # First observation is a baseline, not evidence of new shortages.
            old = previous.pop(r["product_key"], None)
            if old is None:
                db.execute("INSERT INTO changes VALUES (?,?,?,?,?,?)", (
                    snapshot_id, r["product_key"], "first_observed", "", "", ""))
            else:
                for field in FIELDS.values():
                    if old[field] != r[field]:
                        db.execute("INSERT INTO changes VALUES (?,?,?,?,?,?)", (
                            snapshot_id, r["product_key"], "field_changed", field, old[field], r[field]))
        for key in previous if latest else []:
            db.execute("INSERT INTO changes VALUES (?,?,?,?,?,?)", (
                snapshot_id, key, "not_in_latest_feed", "", "", ""))
        db.conn.commit()
        return {"snapshot_id": snapshot_id, "status": "success", "source_rows": total,
                "accepted_rows": len(accepted), "rejected_rows": len(rejected), "encoding": encoding,
                "observed_at": observed_at, "sha256": sha}
    except Exception as exc:
        db.conn.rollback()
        if not db.rows("SELECT run_id FROM runs WHERE run_id=?", (snapshot_id,)):
            db.execute("INSERT INTO runs VALUES (?,?,?,?,?,?,?,?,?)", (
                snapshot_id, observed_at, sha, "failed", 0, 0, 0, str(exc), source_url))
            db.conn.commit()
        raise
    finally:
        db.close()


def summary(db):
    latest = db.rows("SELECT * FROM snapshots ORDER BY observed_at DESC LIMIT 1")
    metrics = db.rows("""SELECT COUNT(*) AS package_observations,
      COUNT(DISTINCT report_id) AS source_reports, COUNT(DISTINCT ingredient) AS ingredient_labels,
      COUNT(DISTINCT manufacturer) AS manufacturers,
      COALESCE(SUM(critical_flag),0) AS critical_package_observations,
      COALESCE(SUM(CASE WHEN hospital_relevant='ja' THEN 1 ELSE 0 END),0) AS hospital_package_observations
      FROM current_observations""")[0]
    return {"latest_snapshot": latest[0] if latest else None, "metrics": metrics,
            "snapshot_count": db.rows("SELECT COUNT(*) AS n FROM snapshots")[0]["n"],
            "latest_run": (db.rows("SELECT * FROM runs ORDER BY observed_at DESC LIMIT 1") or [None])[0]}


def export(root):
    root = Path(root)
    db = Database(database_url(root))
    out = root / "data/exports"
    out.mkdir(parents=True, exist_ok=True)
    queries = {
        "FactObservation": "SELECT o.*,s.observed_at FROM observations o JOIN snapshots s ON s.snapshot_id=o.snapshot_id",
        "FactChange": "SELECT c.*,s.observed_at FROM changes c JOIN snapshots s ON s.snapshot_id=c.snapshot_id",
        "QualityAudit": "SELECT * FROM runs",
        "Snapshot": "SELECT * FROM snapshots ORDER BY observed_at",
    }
    headers = {
        "FactObservation": ["snapshot_id", *COLS, "observed_at"],
        "FactChange": ["snapshot_id", "product_key", "change_type", "field", "old_value", "new_value", "observed_at"],
        "QualityAudit": ["run_id", "observed_at", "source_sha256", "status", "source_rows", "accepted_rows", "rejected_rows", "error", "source_url"],
        "Snapshot": ["snapshot_id", "observed_at", "source_sha256", "raw_path", "source_url"],
    }
    for name, query in queries.items():
        rows = db.rows(query)
        tmp = out / f"{name}.csv.tmp"
        with tmp.open("w", encoding="utf-8", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=headers[name])
            writer.writeheader()
            writer.writerows(rows)
        tmp.replace(out / f"{name}.csv")
    result = summary(db)
    (out / "summary.json").write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    db.close()
    return result
