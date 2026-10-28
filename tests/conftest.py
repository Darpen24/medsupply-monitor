import csv
import io

import pytest

from medsupply.pipeline import FIELDS


def record(**overrides):
    row = {key: "N/A" for key in FIELDS}
    row.update({"PZN": "00123456", "ENR": "12345", "Bearbeitungsnummer": "LE202600001",
                "Meldungsart": "Erstmeldung", "Beginn": "01.10.2026", "Ende": "30.11.2026",
                "Datum der letzten Meldung": "01.10.2026", "Datum der Erstmeldung": "01.10.2026",
                "Arzneimittlbezeichnung": "Testprodukt", "Wirkstoffe": "Testwirkstoff",
                "Zulassungsinhaber": "Testhersteller", "Krankenhausrelevant": "ja",
                "klassifikation": "verskri (auch versrel)", "Grund": "Erhöhte Nachfrage"})
    row.update(overrides)
    return row


def feed(rows, encoding="utf-8"):
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(FIELDS), delimiter=";")
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode(encoding)


@pytest.fixture
def sample():
    return feed([record()])
