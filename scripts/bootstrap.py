"""One-command cached demo or fresh public-feed observation."""
import argparse
import json
from pathlib import Path

from medsupply.pipeline import Database, database_url, export, fetch, ingest
from medsupply.retrieval import build_index
from build_powerbi import build
from prepare_corpus import prepare


parser=argparse.ArgumentParser()
parser.add_argument('--root',default='.')
parser.add_argument('--cached',action='store_true',help='Reproduce the bundled 28 October 2026 official snapshot')
parser.add_argument('--rebuild-powerbi', action='store_true', help='Regenerate report files; overwrites authored Power BI edits')
args=parser.parse_args()
root=Path(args.root).resolve()
if args.cached:
    manifest=json.loads((root/'data/sample/manifest.json').read_text())
    source=(root/'data/sample/bfarm-2026-10-28.csv').read_bytes()
    import hashlib
    assert hashlib.sha256(source).hexdigest()==manifest['sha256'], 'Bundled snapshot integrity failure'
    db=Database(database_url(root))
    existing=db.rows('SELECT * FROM snapshots')
    db.close()
    if not existing or any(x['observed_at']==manifest['observed_at'] for x in existing):
        print(json.dumps(ingest(root,source,manifest['observed_at']),indent=2))
    else:
        raise SystemExit('Cached baseline cannot be inserted into a database containing later observations. Use a clean demo directory.')
else:
    print(json.dumps(ingest(root,fetch()),indent=2))
prepare(root)
export(root)
db=Database(database_url(root))
print(json.dumps(build_index(root,db),indent=2))
db.close()
if args.rebuild_powerbi:
    build(root)
print('Ready. From the project directory run: uvicorn medsupply.api:app --host 127.0.0.1 --port 8000')
