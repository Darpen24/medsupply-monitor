import json
import runpy
from datetime import datetime, timezone
from pathlib import Path

import pytest

from medsupply.pipeline import Database, summary
from conftest import feed, record

collect = runpy.run_path(str(Path(__file__).resolve().parents[1]/'scripts/collect_daily.py'))['collect']


def stamp(day, hour=8):
    return datetime(2026, 10, day, hour, tzinfo=timezone.utc)


def test_same_day_skips_download_and_next_day_records_changes(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    root, history = tmp_path/'app', tmp_path/'history'
    calls = []
    def download():
        calls.append(True)
        return feed([record(**{'Ende': '30.11.2026' if len(calls) == 1 else '31.12.2026'})])
    collect(root, history, stamp(28), download)
    assert collect(root, history, stamp(28, 20), download)['status'] == 'already_collected'
    collect(root, history, stamp(29), download)
    assert len(calls) == 2
    db = Database(root/'data/medsupply.sqlite')
    assert summary(db)['snapshot_count'] == 2
    assert len(db.rows('SELECT * FROM changes')) == 1
    db.close()
    # A fresh runner reconstructs history without another source call that day.
    restored = tmp_path/'restored'
    collect(restored, history, stamp(29, 20), download)
    db = Database(restored/'data/medsupply.sqlite')
    assert summary(db)['snapshot_count'] == 2
    assert len(db.rows('SELECT * FROM changes')) == 1
    assert len(calls) == 2
    db.close()


def test_failed_gate_can_retry_without_claiming_day(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    root, history = tmp_path/'app', tmp_path/'history'
    with pytest.raises(ValueError, match='5%'):
        collect(root, history, stamp(28), lambda: feed([record(), record(PZN='bad')]))
    assert not list(history.glob('*.json'))
    collect(root, history, stamp(28, 9), lambda: feed([record()]))
    assert len(list(history.glob('*.json'))) == 1


def test_tampered_history_is_not_silently_replaced(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    history = tmp_path/'history'
    collect(tmp_path/'app', history, stamp(28), lambda: feed([record()]))
    manifest = json.loads((history/'2026-10-28.json').read_text())
    (history/'raw'/f"{manifest['sha256']}.csv").write_bytes(b'corrupt')
    with pytest.raises(ValueError, match='integrity'):
        collect(tmp_path/'new', history, stamp(29), lambda: pytest.fail('Must not download'))


def test_unchanged_bytes_on_new_day_keep_one_raw_file(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    root, history = tmp_path/'app', tmp_path/'history'
    for day in (28, 29):
        collect(root, history, stamp(day), lambda: feed([record()]))
    assert len(list(history.glob('*.json'))) == 2
    assert len(list((history/'raw').glob('*.csv'))) == 1


def test_external_database_and_naive_time_are_refused(tmp_path, monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql://example')
    with pytest.raises(ValueError, match='unset'):
        collect(tmp_path/'app', tmp_path/'history')
    monkeypatch.delenv('DATABASE_URL')
    with pytest.raises(ValueError, match='timezone'):
        collect(tmp_path/'app', tmp_path/'history', datetime(2026, 10, 28))
