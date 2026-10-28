"""Opt-in integration test: requires an EMPTY, dedicated POSTGRES_TEST_URL database."""
import os

import pytest

from medsupply.pipeline import Database, ingest, summary
from conftest import feed, record


@pytest.mark.skipif(not os.environ.get('POSTGRES_TEST_URL'), reason='Dedicated PostgreSQL service unavailable')
def test_postgres_transactional_ingestion(tmp_path, monkeypatch):
    url = os.environ['POSTGRES_TEST_URL']
    db = Database(url)
    assert not db.rows('SELECT * FROM snapshots'), 'Use an empty dedicated test database; no data is deleted'
    db.close()
    monkeypatch.setenv('DATABASE_URL',url)
    data=feed([record()])
    assert ingest(tmp_path,data,'2026-10-28T08:00:00Z')['status']=='success'
    assert ingest(tmp_path,data,'2026-10-28T08:00:00Z')['status']=='already_processed'
    ingest(tmp_path,feed([record(**{'Ende':'31.12.2026'})]),'2026-10-29T08:00:00Z')
    db=Database(url)
    assert summary(db)['snapshot_count']==2
    assert len(db.rows('SELECT * FROM changes'))==1
    db.close()
