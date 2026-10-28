"""Explicit opt-in acceptance check: two real model calls plus two local scope checks.

Never prints credentials or provider error bodies. Passing means real calls and valid
citation IDs, not proven groundedness. A human must review the saved answers.
"""
import argparse
import json
import os
import re
import sys
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

from medsupply.pipeline import Database, database_url
from medsupply.retrieval import ask


def verify(root):
    root = Path(root)
    if not os.environ.get('OPENAI_API_KEY') or not os.environ.get('OPENAI_MODEL'):
        raise ValueError('Set OPENAI_API_KEY and OPENAI_MODEL in the environment; never paste a key into source code.')
    db = Database(database_url(root))
    cases = [
        ('Why is NIPRUSS reported in shortage?', 'live_llm'),
        ('Explain the difference between Lieferengpass and Versorgungsengpass using the published evidence.', 'live_llm'),
        ('What dosage should I take?', 'refused'),
        ('zxqv987unknown', 'no_evidence'),
    ]
    results = []
    try:
        for question, expected in cases:
            result = ask(root, db, question, use_llm=True)
            if result['mode'] != expected:
                raise ValueError(f"Expected mode {expected}; received {result['mode']}")
            if expected == 'live_llm':
                refs = [int(x) for x in re.findall(r'\[(\d+)\]', result['answer'])]
                if not refs or any(n < 1 or n > len(result['evidence']) for n in refs):
                    raise ValueError('Live response failed citation validation')
            results.append({'question': question, 'mode': result['mode'], 'answer': result['answer'],
                            'snapshot_id': result.get('snapshot_id'),
                            'sources': [{'citation': i, 'title': e['title'], 'url': e['source_url'],
                                         'locator': e.get('source_locator', ''), 'passage': e['text'],
                                         'observed_at': e.get('observed_at')}
                                        for i, e in enumerate(result['evidence'], 1)]})
    finally:
        db.close()
    report = {'verified_at': datetime.now(timezone.utc).isoformat(), 'provider': 'OpenAI',
              'model': os.environ['OPENAI_MODEL'], 'real_model_calls_completed': 2,
              'automated_contract_checks': 'passed', 'human_groundedness_review': 'pending',
              'note': 'Citation-ID validity does not establish factual support. Review each answer against its sources.',
              'results': results}
    folder = root/'acceptance'
    folder.mkdir(exist_ok=True)
    (folder/'live-llm-results.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print('Two real model calls and two scope checks passed. Review acceptance/live-llm-results.json.')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default='.')
    parser.add_argument('--run-live', action='store_true', help='Explicitly authorize two billable API requests')
    args = parser.parse_args()
    if not args.run_live:
        parser.error('--run-live is required; this command makes two real API requests')
    try:
        verify(args.root)
    except urllib.error.HTTPError as exc:
        print(f'Live validation failed: provider returned HTTP {exc.code}. Check account billing, model access and key permissions.', file=sys.stderr)
        return 1
    except (ValueError, OSError, KeyError, TypeError) as exc:
        # No provider response body or credential value is included in the error report.
        print(f'Live validation did not complete ({type(exc).__name__}). Check configuration, accepted data and index.', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
