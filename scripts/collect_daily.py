"""Keep one successful real observation per UTC day and rebuild local outputs.

The history folder is the portable state. Failed downloads or rejected feeds do
not claim a day. Replays verify raw bytes before reconstructing the database.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

from medsupply.pipeline import Database, SOURCE_URL, database_url, export, fetch, ingest
from medsupply.retrieval import build_index


def collect(root, history, now=None, download=fetch):
    if os.environ.get('DATABASE_URL'):
        raise ValueError('Daily collection uses a local SQLite database; unset DATABASE_URL')
    root, history = Path(root), Path(history)
    stamp = now or datetime.now(timezone.utc)
    if stamp.tzinfo is None:
        raise ValueError('Collection time must include a timezone')
    stamp = stamp.astimezone(timezone.utc)
    history.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(history.glob('????-??-??.json')):
        entry = json.loads(path.read_text(encoding='utf-8'))
        observed = datetime.fromisoformat(entry['observed_at'])
        if observed.tzinfo is None or observed.astimezone(timezone.utc).date().isoformat() != path.stem:
            raise ValueError('History date does not match its observation timestamp')
        digest = entry['sha256']
        if len(digest) != 64 or any(c not in '0123456789abcdef' for c in digest):
            raise ValueError('Invalid history digest')
        data = (history / 'raw' / f'{digest}.csv').read_bytes()
        if hashlib.sha256(data).hexdigest() != digest:
            raise ValueError('History raw bytes failed integrity check')
        entries.append((entry, data))
    for entry, data in entries:
        ingest(root, data, entry['observed_at'], entry['source_url'])
    day = stamp.date().isoformat()
    target = history / f'{day}.json'
    if target.exists():
        result = {'status': 'already_collected', 'day': day}
    else:
        # Record acquisition time after the download, not a fictional midnight.
        data = download()
        observed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
        if observed_at[:10] != day:
            raise ValueError('Download crossed UTC midnight; rerun to assign the correct day')
        result = ingest(root, data, observed_at, SOURCE_URL)
        digest = hashlib.sha256(data).hexdigest()
        raw = history / 'raw' / f'{digest}.csv'
        raw.parent.mkdir(exist_ok=True)
        if raw.exists() and raw.read_bytes() != data:
            raise ValueError('History raw bytes failed integrity check')
        raw.write_bytes(data)
        entry = {'observed_at': observed_at, 'sha256': digest, 'source_url': SOURCE_URL,
                 'snapshot_id': result['snapshot_id']}
        temporary = target.with_suffix('.json.tmp')
        temporary.write_text(json.dumps(entry, indent=2) + '\n', encoding='utf-8')
        temporary.replace(target)
    export(root)
    db = Database(database_url(root))
    try:
        build_index(root, db)
    finally:
        db.close()
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--history', default='history')
    args = parser.parse_args()
    print(json.dumps(collect(args.root, args.history), indent=2))
