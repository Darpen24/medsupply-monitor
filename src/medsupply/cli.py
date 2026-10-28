import argparse
import json
from pathlib import Path

from .pipeline import Database, database_url, export, fetch, ingest
from .retrieval import ask, build_index


def main():
    parser = argparse.ArgumentParser(description="MedSupply Monitor")
    parser.add_argument("--root", default=".")
    subs = parser.add_subparsers(dest="command", required=True)
    run = subs.add_parser("run", help="Fetch/import, validate, publish snapshot, export and index")
    run.add_argument("--file")
    run.add_argument("--observed-at")
    subs.add_parser("export")
    subs.add_parser("index")
    question = subs.add_parser("ask")
    question.add_argument("question")
    question.add_argument("--live", action="store_true")
    args = parser.parse_args()
    if args.command == "run":
        result = ingest(args.root, Path(args.file).read_bytes() if args.file else fetch(), args.observed_at)
        print(json.dumps(result, indent=2))
        export(args.root)
    elif args.command == "export":
        print(json.dumps(export(args.root), indent=2))
    if args.command in {"run", "index", "ask"}:
        db = Database(database_url(args.root))
        try:
            result = ask(args.root, db, args.question, use_llm=args.live) if args.command == "ask" else build_index(args.root, db)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        finally:
            db.close()


if __name__ == "__main__":
    main()
