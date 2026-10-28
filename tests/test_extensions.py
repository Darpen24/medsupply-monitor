from medsupply.pipeline import Database, ingest
from medsupply.retrieval import ask
from conftest import feed, record


def test_extensions_require_history_and_use_sql(tmp_path):
    ingest(tmp_path, feed([record()]), '2026-10-28T08:00:00Z')
    db = Database(tmp_path/'data/medsupply.sqlite')
    assert ask(tmp_path, db, 'Which expected end dates were extended?')['mode'] == 'insufficient_history'
    ingest(tmp_path, feed([record(**{'Ende':'31.12.2026'})]), '2026-10-29T08:00:00Z')
    result = ask(tmp_path, db, 'Which expected end dates were extended?')
    assert result['mode'] == 'sql_with_evidence' and result['count'] == 1
    assert result['evidence'][0]['text'].startswith('Expected end changed from 2026-11-30 to 2026-12-31')
    db.close()
