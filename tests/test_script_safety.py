import json
import os
import runpy
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_corpus_checkout_mtime_does_not_change_acquisition_date(tmp_path):
    shutil.copytree(ROOT/'corpus', tmp_path/'corpus')
    before = json.loads((tmp_path/'corpus/manifest.json').read_text())
    for path in (tmp_path/'corpus').glob('*.html'):
        os.utime(path, (2000000000, 2000000000))
    prepare = runpy.run_path(str(ROOT/'scripts/prepare_corpus.py'))['prepare']
    prepare(tmp_path)
    after = json.loads((tmp_path/'corpus/manifest.json').read_text())
    assert [s['retrieved_at'] for s in after] == [s['retrieved_at'] for s in before]
    # Without matching saved provenance the date must remain unknown.
    (tmp_path/'corpus/manifest.json').write_text('[]')
    prepare(tmp_path)
    assert all(s['retrieved_at'] is None for s in json.loads((tmp_path/'corpus/manifest.json').read_text()))


def test_bootstrap_preserves_authored_powerbi_files(tmp_path, monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    shutil.copytree(ROOT/'data/sample', tmp_path/'data/sample')
    shutil.copytree(ROOT/'corpus', tmp_path/'corpus')
    authored = tmp_path/'powerbi/MedSupply.pbip'
    authored.parent.mkdir()
    authored.write_text('My saved Desktop edits')
    subprocess.run([sys.executable, str(ROOT/'scripts/bootstrap.py'), '--cached', '--root', str(tmp_path)],
                   check=True, capture_output=True, text=True)
    assert authored.read_text() == 'My saved Desktop edits'
    assert (tmp_path/'data/exports/FactObservation.csv').exists()
