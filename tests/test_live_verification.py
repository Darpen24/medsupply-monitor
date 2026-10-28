import io
import json
import runpy
import sys
from pathlib import Path

import pytest

from medsupply.pipeline import Database, ingest
from medsupply.retrieval import build_index
from conftest import feed, record


SCRIPT = Path(__file__).resolve().parents[1]/'scripts/verify_live_llm.py'


def test_missing_credentials_refuses_before_calls(tmp_path, monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    verify = runpy.run_path(str(SCRIPT))['verify']
    with pytest.raises(ValueError, match='environment'):
        verify(tmp_path)
    assert not (tmp_path/'acceptance/live-llm-results.json').exists()


def test_cli_requires_explicit_live_opt_in(monkeypatch):
    monkeypatch.setattr(sys, 'argv', [str(SCRIPT)])
    with pytest.raises(SystemExit) as result:
        runpy.run_path(str(SCRIPT), run_name='__main__')
    assert result.value.code == 2


def test_verification_saves_passages_but_no_credentials(tmp_path, monkeypatch):
    ingest(tmp_path, feed([record(**{'Arzneimittlbezeichnung': 'NIPRUSS'})]), '2026-10-28T08:00:00Z')
    (tmp_path/'corpus').mkdir()
    (tmp_path/'corpus/documents.json').write_text(json.dumps([{
        'id': 'definitions', 'title': 'Lieferengpass Versorgungsengpass',
        'text': 'Lieferengpass und Versorgungsengpass sind nicht identisch.',
        'source_url': 'https://gesund.bund.de', 'source_locator': 'Definition',
        'observed_at': '2026-10-28T08:00:00Z'}]))
    db = Database(tmp_path/'data/medsupply.sqlite')
    build_index(tmp_path, db)
    db.close()
    monkeypatch.setenv('OPENAI_API_KEY', 'verification-test-placeholder')
    monkeypatch.setenv('OPENAI_MODEL', 'test-model')
    calls = []
    def response(request, timeout):
        payload = json.loads(request.data)
        assert payload['max_completion_tokens'] == 512
        calls.append(payload)
        return io.BytesIO(json.dumps({'choices': [{'message': {'content': 'Reported evidence [1]'}}]}).encode())
    monkeypatch.setattr('urllib.request.urlopen', response)
    report = runpy.run_path(str(SCRIPT))['verify'](tmp_path)
    assert len(calls) == 2
    assert report['human_groundedness_review'] == 'pending'
    stored = (tmp_path/'acceptance/live-llm-results.json').read_text()
    assert 'verification-test-placeholder' not in stored
    assert report['results'][0]['sources'][0]['passage']
