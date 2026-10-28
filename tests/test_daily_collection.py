import json
import os
import runpy
import subprocess
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


@pytest.mark.parametrize('scenario,attempt,expected', [
    ('first', '1', 0), ('previous', '1', 0), ('own', '2', 0),
    ('missing', '2', 1), ('expired', '1', 1),
])
def test_workflow_restore_fails_closed(tmp_path, scenario, attempt, expected):
    workflow = (Path(__file__).resolve().parents[1]/'.github/workflows/daily-snapshot.yml').read_text()
    block = workflow.split('          set -euo pipefail\n', 1)[1].split('      - name:', 1)[0]
    shell = 'set -euo pipefail\n' + '\n'.join(line[10:] for line in block.splitlines())
    fake = tmp_path/'gh'
    fake.write_text("""#!/usr/bin/env python3
import json, os, pathlib, sys
args = sys.argv[1:]
scenario = os.environ['SCENARIO']
if args[0] == 'api':
    print(('true' if scenario == 'own' else 'false') if args[1].endswith('/artifacts') else '123')
elif args[:2] == ['run', 'list']:
    print('456' if scenario in {'previous', 'expired'} else '')
elif args[:2] == ['run', 'download']:
    if scenario == 'expired':
        sys.exit(1)
    folder = pathlib.Path('history')
    folder.mkdir()
    (folder/'state.json').write_text(json.dumps({'format_version': 1}))
    (folder/'2026-10-28.json').write_text('{}')
else:
    sys.exit(9)
""")
    fake.chmod(0o755)
    env = {**os.environ, 'PATH': str(tmp_path)+os.pathsep+os.environ['PATH'],
           'SCENARIO': scenario, 'GITHUB_RUN_ATTEMPT': attempt, 'GITHUB_RUN_ID': '789',
           'GITHUB_REPOSITORY': 'example/repo', 'GITHUB_REF_NAME': 'finish-project'}
    result = subprocess.run(['bash', '-c', shell], cwd=tmp_path, env=env,
                            capture_output=True, text=True)
    assert result.returncode == expected, result.stderr
    if scenario in {'previous', 'own'}:
        assert (tmp_path/'history/2026-10-28.json').exists()
    if scenario == 'missing':
        assert not (tmp_path/'history').exists()
