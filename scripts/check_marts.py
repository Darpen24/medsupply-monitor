"""Execute the portable dbt model SELECTs against the local baseline.

This checks model SQL and output invariants; it does not claim PostgreSQL or dbt materialization ran.
"""
import json
import re
import sys
from pathlib import Path

from medsupply.pipeline import Database


def check(root):
    root = Path(root)
    db = Database(root / 'data/medsupply.sqlite')
    models = ['dim_snapshot','dim_product','fact_observation','fact_change','mart_current_shortages','mart_quality']
    for name in models:
        sql = (root/f'dbt/models/{name}.sql').read_text()
        sql = re.sub(r"\{\{\s*source\('operational',\s*'([^']+)'\)\s*\}\}", r'\1', sql)
        sql = re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", r'\1', sql)
        db.execute(f'DROP VIEW IF EXISTS {name}')
        db.execute(f'CREATE VIEW {name} AS '+sql)
    assert db.rows('SELECT COUNT(*) AS n FROM mart_quality WHERE reconciliation_difference<>0')[0]['n'] == 0
    assert db.rows('SELECT COUNT(*) AS n FROM fact_observation')[0]['n'] == db.rows('SELECT COUNT(*) AS n FROM observations')[0]['n']
    assert db.rows('SELECT COUNT(*) AS n FROM dim_product')[0]['n'] == db.rows('SELECT COUNT(DISTINCT product_key) AS n FROM observations')[0]['n']
    for name in ['reconcile_published_snapshots','reconcile_quality']:
        sql = (root/f'dbt/tests/{name}.sql').read_text()
        sql = re.sub(r"\{\{\s*source\('operational',\s*'([^']+)'\)\s*\}\}", r'\1', sql)
        sql = re.sub(r"\{\{\s*ref\('([^']+)'\)\s*\}\}", r'\1', sql)
        assert not db.rows(sql), name
    db.conn.commit()
    result = {name:db.rows(f'SELECT COUNT(*) AS n FROM {name}')[0]['n'] for name in models}
    db.close()
    print(json.dumps({'engine':'SQLite: exact portable dbt SELECT statements','model_rows':result},indent=2))
    return result


if __name__=='__main__':
    check(sys.argv[1] if len(sys.argv)>1 else '.')
