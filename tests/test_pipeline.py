import json
from pathlib import Path

import pytest

from medsupply.pipeline import Database, export, ingest, parse, summary
from conftest import feed, record

D1, D2 = "2026-10-28T08:00:00Z", "2026-10-29T08:00:00Z"


def db(root):
    return Database(Path(root) / "data/medsupply.sqlite")


def test_encoding_and_leading_zero():
    rows, rejected, enc = parse(feed([record()], "cp1252"))
    assert enc == "cp1252" and not rejected
    assert rows[0]['pzn'] == '00123456' and rows[0]['reason'] == 'Erhöhte Nachfrage'


def test_embedded_newline_is_one_record():
    rows, rejected, _ = parse(feed([record(**{"Anm. zum Grund": "Line one\nLine two; quoted"})]))
    assert len(rows) == 1 and not rejected
    assert '\n' in rows[0]['reason_note']


def test_missing_schema_rejected():
    with pytest.raises(ValueError, match="schema"):
        parse(b"product;Ende\nx;30.11.2026")


def test_empty_feed_rejected():
    with pytest.raises(ValueError, match="No valid"):
        parse(feed([]))


def test_conflicting_identity_quarantines_both():
    rows = [record(), record(**{"Bearbeitungsnummer": "LE202600002"}), record(PZN="00123457")]
    accepted, rejected, _ = parse(feed(rows))
    assert len(accepted) == 1 and len(rejected) == 2
    assert accepted[0]['pzn'] == '00123457'


@pytest.mark.parametrize("field,value", [("Ende", "31.02.2026"), ("PZN", "123"),
    ("Krankenhausrelevant", "maybe"), ("klassifikation", "unknown"), ("Ende", "01.01.2020")])
def test_invalid_row_quarantined(field, value):
    _, rejected, _ = parse(feed([record(), record(**{"PZN": "00123457", field: value})]))
    assert rejected


def test_idempotency_and_raw_integrity(tmp_path, sample):
    first = ingest(tmp_path, sample, D1)
    assert ingest(tmp_path, sample, D1)['status'] == 'already_processed'
    conn = db(tmp_path)
    assert summary(conn)['snapshot_count'] == 1
    assert conn.rows('SELECT COUNT(*) AS n FROM observations')[0]['n'] == 1
    conn.close()
    path = next((tmp_path / 'data/raw').glob('*.csv'))
    assert path.read_bytes() == sample
    path.write_bytes(b'corruption')
    with pytest.raises(ValueError, match="integrity"):
        ingest(tmp_path, sample, D2)
    assert first['status'] == 'success'


def test_baseline_is_not_new_and_repeated_bytes_form_new_observation(tmp_path, sample):
    ingest(tmp_path, sample, D1)
    ingest(tmp_path, sample, D2)
    conn = db(tmp_path)
    assert summary(conn)['snapshot_count'] == 2
    assert not conn.rows('SELECT * FROM changes')
    conn.close()


def test_field_changes_and_membership(tmp_path):
    ingest(tmp_path, feed([record(), record(PZN="00123457")]), D1)
    ingest(tmp_path, feed([record(**{"Ende": "31.12.2026"}), record(PZN="00123458")]), D2)
    conn = db(tmp_path)
    changes = conn.rows('SELECT * FROM changes')
    assert {c['change_type'] for c in changes} == {'field_changed', 'first_observed', 'not_in_latest_feed'}
    assert not any('resolved' in c['change_type'] for c in changes)
    changed = next(c for c in changes if c['field'] == 'expected_end_date')
    assert changed['old_value'] == '2026-11-30' and changed['new_value'] == '2026-12-31'
    conn.close()


def test_quality_gate_does_not_publish(tmp_path, sample):
    ingest(tmp_path, sample, D1)
    with pytest.raises(ValueError, match="5%"):
        ingest(tmp_path, feed([record(), record(PZN='bad')]), D2)
    conn = db(tmp_path)
    state = summary(conn)
    assert state['snapshot_count'] == 1 and state['latest_run']['status'] == 'failed'
    assert len(conn.rows('SELECT * FROM quarantine')) == 1
    conn.close()


def test_schema_failure_is_audited(tmp_path, sample):
    ingest(tmp_path, sample, D1)
    with pytest.raises(ValueError):
        ingest(tmp_path, b'<html>Unavailable</html>', D2)
    conn = db(tmp_path)
    assert summary(conn)['latest_run']['status'] == 'failed'
    assert summary(conn)['metrics']['package_observations'] == 1
    conn.close()


def test_timestamp_collision_does_not_overwrite(tmp_path, sample):
    ingest(tmp_path, sample, D1)
    with pytest.raises(ValueError, match="Different source bytes"):
        ingest(tmp_path, feed([record(**{"Ende": "31.12.2026"})]), D1)


def test_out_of_order_import_refused(tmp_path, sample):
    ingest(tmp_path, sample, D2)
    with pytest.raises(ValueError, match="Out-of-order"):
        ingest(tmp_path, sample, D1)
    conn = db(tmp_path)
    assert summary(conn)['snapshot_count'] == 1
    conn.close()


def test_naive_timestamp_refused(tmp_path, sample):
    with pytest.raises(ValueError, match="timezone"):
        ingest(tmp_path, sample, "2026-10-28T08:00:00")


def test_export_reconciles(tmp_path, sample):
    ingest(tmp_path, sample, D1)
    result = export(tmp_path)
    stored = json.loads((tmp_path / 'data/exports/summary.json').read_text())
    assert stored == result
    assert stored['metrics']['package_observations'] == 1
    assert (tmp_path / 'data/exports/FactChange.csv').read_text().startswith('snapshot_id,product_key')
