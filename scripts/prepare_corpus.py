"""Extract specifically delimited sections from downloaded official source pages.

Downloads are bounded. Original bytes and SHA-256 provenance stay separate from the index.
"""
import hashlib
import json
import sys
from datetime import datetime, timezone
from html.parser import HTMLParser
from pathlib import Path

from medsupply.pipeline import fetch


class Text(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)

    def handle_data(self, data):
        if not self.skip and data.strip():
            self.parts.append(data.strip())


SOURCES = [
    ("shortages.html", "https://gesund.bund.de/arzneimittel-mit-und-ohne-rezept", [
        ("supply-definition", "Lieferengpass: definition", "Was ist ein Lieferengpass?", "Ursachen für Lieferengpässe können sein:"),
        ("supply-causes", "Lieferengpass: published general causes", "Ursachen für Lieferengpässe können sein:", "Ein Lieferengpass muss allerdings"),
        ("supply-not-patient-impact", "Lieferengpass and Versorgungsengpass", "Ein Lieferengpass muss allerdings", "Informationen darüber,")]),
    ("registry.html", "https://www.verwaltungsdaten-informationsplattform.de/register/270", [
        ("registry-purpose", "Register: purpose and reported scope", "Zweck und Zielsetzung der Registerführung", "Kontext der Registerführung und -nutzung"),
        ("registry-reporting", "Register: reporting context", "Kontext der Registerführung und -nutzung", "Internetauftritt, Quellen"),
        ("registry-quality", "Register: data quality and update process", "Lieferengpässe werden über ein Meldeportal", "Informationsobjekte (Einheiten,")]),
]


def prepare(root):
    folder = Path(root) / "corpus"
    folder.mkdir(parents=True, exist_ok=True)
    docs, sources = [], []
    for filename, url, sections in SOURCES:
        path = folder / filename
        if not path.exists():
            path.write_bytes(fetch(url))
        raw = path.read_bytes()
        parser = Text()
        parser.feed(raw.decode("utf-8"))
        text = " ".join(parser.parts)
        observed_at = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat()
        digest = hashlib.sha256(raw).hexdigest()
        sources.append({"file": filename, "url": url, "sha256": digest, "retrieved_at": observed_at})
        for identifier, title, start, end in sections:
            left = text.find(start)
            right = text.find(end, left + len(start)) if left >= 0 else -1
            if left < 0 or right < 0:
                raise ValueError(f"Source section changed; review extraction boundaries for {identifier}")
            docs.append({"id": identifier, "title": title, "text": text[left:right].strip(),
                         "source_url": url, "source_locator": start, "observed_at": observed_at,
                         "source_sha256": digest, "language": "de"})
    (folder / "documents.json").write_text(json.dumps(docs, ensure_ascii=False, indent=2), encoding="utf-8")
    (folder / "manifest.json").write_text(json.dumps(sources, indent=2), encoding="utf-8")
    print(json.dumps({"documents": len(docs), "sources": len(sources)}))


if __name__ == "__main__":
    prepare(sys.argv[1] if len(sys.argv) > 1 else ".")
