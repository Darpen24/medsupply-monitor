import json

import pytest
from fastapi.testclient import TestClient

from medsupply.api import create_app
from medsupply.pipeline import Database, ingest
from medsupply.retrieval import ask, build_index, generate, retrieve
from conftest import feed, record


@pytest.fixture
def indexed(tmp_path):
    ingest(tmp_path, feed([record(**{"Arzneimittlbezeichnung": "NIPRUSS", "Wirkstoffe": "Nitroprussid"}),
                           record(PZN='00123457', **{"Arzneimittlbezeichnung": "Aprepitant"})]),
           '2026-10-28T08:00:00Z')
    db = Database(tmp_path / 'data/medsupply.sqlite')
    build_index(tmp_path, db)
    yield tmp_path, db
    db.close()


def test_retrieves_named_product_with_source(indexed):
    root, db = indexed
    result = ask(root, db, 'Why is NIPRUSS reported in shortage?')
    assert result['mode'] == 'extractive_evidence'
    assert result['evidence'][0]['title'] == 'NIPRUSS'
    assert result['evidence'][0]['source_locator'].startswith('report LE')


def test_product_filter(indexed):
    root, db = indexed
    key = db.rows("SELECT product_key FROM current_observations WHERE product='Aprepitant'")[0]['product_key']
    evidence, _ = retrieve(root, 'Aprepitant', product_key=key)
    assert len(evidence) == 1 and evidence[0]['title'] == 'Aprepitant'


def test_no_evidence_refusal(indexed):
    root, db = indexed
    assert ask(root, db, 'quantum zebras on Mars')['mode'] == 'no_evidence'


@pytest.mark.parametrize('question', ['What dosage should I take?', 'Can you substitute NIPRUSS?',
                                     'Welche Dosierung soll ich einnehmen?'])
def test_clinical_scope_refusal(indexed, question):
    assert ask(*indexed, question)['mode'] == 'refused'


def test_counts_route_to_sql(indexed):
    assert ask(*indexed, 'How many shortages are reported?')['mode'] == 'sql_required'


def test_stale_index_blocked(indexed):
    root, db = indexed
    ingest(root, feed([record()]), '2026-10-29T08:00:00Z')
    assert ask(root, db, 'NIPRUSS')['mode'] == 'stale_index'


def test_live_configuration_required(monkeypatch):
    monkeypatch.delenv('OPENAI_API_KEY', raising=False)
    with pytest.raises(ValueError, match='requires'):
        generate('NIPRUSS', [])


def test_api_filter_and_injection(indexed):
    client = TestClient(create_app(indexed[0]))
    assert client.get('/health').json()['has_data']
    assert client.get('/api/summary').json()['metrics']['package_observations'] == 2
    assert client.get('/api/observations', params={'q': "' OR 1=1 --"}).json()['total'] == 0
    assert client.get('/api/observations', params={'q': '%'}).json()['total'] == 0
    assert client.get('/api/observations', params={'q': 'NIPRUSS'}).json()['total'] == 1
    assert client.get('/api/observations?limit=999999').status_code == 422
    assert client.get('/').status_code == 200


def test_api_evidence_and_live_disabled(indexed, monkeypatch):
    monkeypatch.delenv('ENABLE_LIVE_LLM', raising=False)
    client = TestClient(create_app(indexed[0]))
    assert client.post('/api/ask', json={'question': 'NIPRUSS'}).json()['evidence']
    assert client.post('/api/ask', json={'question': 'NIPRUSS', 'use_llm': True}).status_code == 403
    assert client.post('/api/ask', json={'question': 'a'*1001}).status_code == 422
    assert client.get('/api/quality').json()['runs'][0]['status'] == 'success'


def test_document_chunk_provenance(tmp_path):
    (tmp_path / 'corpus').mkdir()
    (tmp_path / 'corpus/documents.json').write_text(json.dumps([{
        'id': 'official', 'title': 'Lieferengpass', 'text': 'Lieferengpass ' * 400,
        'source_url': 'https://gesund.bund.de', 'source_locator': 'Definition',
        'observed_at': '2026-10-28T08:00:00Z'}]))
    db = Database(tmp_path / 'data/test.sqlite')
    result = build_index(tmp_path, db)
    assert result['chunks'] == 3
    evidence, _ = retrieve(tmp_path, 'Lieferengpass')
    assert evidence[0]['source_locator'] == 'Definition'
    db.close()
