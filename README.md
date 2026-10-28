# MedSupply Monitor

I built this project to practise data engineering with a real problem in Germany: reported medicine shortages. It uses the public BfArM/PharmNet CSV. The data does not come from Kaggle or Hugging Face.

The pipeline keeps each download, checks the rows and compares accepted snapshots. A small web app shows the results and lets me find the source behind a reported shortage. Power BI imports CSV exports. PostgreSQL and dbt provide a separate set of analytics views.

The core pipeline and evidence search work. Power BI Desktop refresh and real LLM calls still need manual acceptance. The screenshot below is the web app, not Power BI.

![Web app using the bundled official snapshot](docs/previews/monitor.png)

## Run it locally

Use Python 3.11 or newer. The checks use Python 3.12.

```bash
python -m venv .venv
# Linux or macOS
source .venv/bin/activate
# Windows PowerShell: .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/bootstrap.py --cached
uvicorn medsupply.api:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. The API docs are at http://127.0.0.1:8000/docs. No API key is needed for evidence search.

`--cached` loads the official observation from 28 October 2026. It is a reproducible example, not today's live status. Run `python scripts/bootstrap.py` for a fresh download. Keep `data/medsupply.sqlite` and `data/raw/` between local runs.

Bootstrap updates the data and index. It no longer rewrites the Power BI report. Set the export folder in Desktop yourself. Report regeneration is available with `--rebuild-powerbi` but it overwrites authored report files.

## What the bundled data contains

| Measure | Value |
|---|---:|
| Source rows | 896 |
| Accepted package observations | 893 |
| Quarantined rows | 3 |
| Distinct source report IDs | 512 |
| Raw ingredient labels | 248 |
| Manufacturer or authorisation-holder labels | 122 |
| Supply-critical package observations | 198 |
| Hospital-relevant package observations | 247 |

These are counts from one accepted observation. They are not national stock levels. Several packages can share one report ID. One incomplete row and two conflicting identity rows are quarantined. The original timestamp and file hash are in [the sample manifest](data/sample/manifest.json).

## Real daily history

[The daily workflow](.github/workflows/daily-snapshot.yml) is set to run at 06:23 UTC. GitHub schedules start only after the workflow is on the default branch. This pull request does not activate that schedule or push data to `main`.

Each run restores the last successful history artifact for its branch. It downloads the real feed and keeps at most one successful observation per UTC day. A rerun on that day skips the download. The next day gets a new observation even if the bytes are unchanged. Raw files are stored once per SHA-256 hash. SQLite and exports are rebuilt from the saved observations.

Download `daily-shortage-history` to keep the raw files and dated manifests. Download `daily-powerbi-exports` for the report. Artifacts are requested for 90 days, subject to repository policy. Each successful run carries the complete history forward. This is not permanent archival storage. If the previous artifact expires or cannot be restored, the workflow fails instead of starting over. Back it up outside Actions before a long pause. See [daily collection and recovery](docs/daily-history.md).

Only one real acquisition was bundled when this project was built. Tests use separate fixtures to check changes. A workflow run today cannot prove that collection works across several real days.

## Power BI uses CSVs

Power BI reads four files from `data/exports`: `FactObservation.csv`, `FactChange.csv`, `Snapshot.csv` and `QualityAudit.csv`. Power Query builds `DimProduct` from the observations. It does **not** query the dbt views.

I kept this route so someone can open the report without running PostgreSQL or setting database credentials. The tradeoff is that I maintain two transformation paths. `scripts/check_marts.py` checks the dbt SELECTs on SQLite. The PostgreSQL CI job runs the real dbt build. These checks do not execute DAX or prove that every Power BI calculation matches dbt.

Open `powerbi/MedSupply.pbip` in Power BI Desktop. Set **Transform data > Manage parameters > SourceFolder** to the absolute path of `data/exports`. Refresh and compare the cards with `summary.json`. The quality page totals all exported runs and does not follow product filters. The monitoring measures are intended to use the latest timestamp within the selected snapshot context.

Desktop refresh, DAX execution and native rendering have not been verified here. There is no populated PBIX in the repo. I will refresh it on Windows and add actual screenshots with the Desktop version and date. Follow [the acceptance steps](docs/finish-acceptance.md). Do not treat the web screenshots as proof of Power BI working.

## PostgreSQL and dbt

```bash
python -m pip install -e ".[dev,postgres]"
docker compose up -d postgres
```

Set `DATABASE_URL=postgresql://medsupply:medsupply_local@localhost:5432/medsupply` in your shell. PowerShell uses `$env:DATABASE_URL = "postgresql://..."`.

```bash
python scripts/bootstrap.py --cached
dbt build --project-dir dbt --profiles-dir dbt
```

For custom credentials set `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE` for dbt too. Python does not load `.env` automatically. The sample password is for the local loopback-only service.

The six dbt models cover products, snapshots, observations, changes, current shortages and quality. The views live in `analytics`. The source tables live in `public`. A direct Power BI connection to those views would be a future change requiring new Power Query mappings and Desktop validation.

## Evidence search and optional LLM

`src/medsupply/retrieval.py` uses BM25 keyword ranking. It searches the latest accepted records and six sections from official pages. The normal answer quotes evidence with source links. This is lexical retrieval, not embedding search.

The optional RAG path sends the question and retrieved passages to OpenAI. Configure `OPENAI_API_KEY` and `OPENAI_MODEL`, then run:

```bash
medsupply ask "Why is NIPRUSS reported in shortage?" --live
```

The API also needs `ENABLE_LIVE_LLM=true`. The browser uses evidence search and does not make paid calls. Model tests use mocked responses. Real provider calls remain unverified until the manual **Verify live LLM** workflow runs with your secret and model variable. It makes two paid requests and saves answers with the evidence for human review. See [acceptance steps](docs/finish-acceptance.md).

Citation checks only validate reference numbers. They cannot prove that a sentence is supported. Scope filters use keywords and are incomplete. This project cannot advise on treatment, dosage or substitutions. SQL supplies defined metrics. Retrieval does not calculate totals.

## Checks

```bash
pytest -q
ruff check src scripts tests
python scripts/check_marts.py
python scripts/evaluate.py
python scripts/validate_powerbi.py
```

Run bootstrap before the script checks. `evaluate.py` is a hand-picked 30-question check for the bundled snapshot. It is not a held-out accuracy score and is not part of CI. The Power BI validator checks schemas and references only.

Local review checks passed with 45 tests and one PostgreSQL skip. The [earlier CI run](https://github.com/Darpen24/medsupply-monitor/actions/runs/40671232920) passed before this branch. Check this pull request's CI for the changed code. CI runs pytest, ruff, the local model checks, Power BI schema checks and a PostgreSQL `dbt build`. The PostgreSQL test needs an empty dedicated database through `POSTGRES_TEST_URL`.

## What I built and what I would change

I built the download and validation pipeline, snapshot comparisons, dbt views, evidence API and a Power BI project. I kept the source text in German so I can trace an explanation to what was reported.

I would first collect real daily history and finish the Windows refresh. I would then review real model answers against their passages and add harder retrieval questions. For a longer running service I would move history out of expiring artifacts and make Power BI read the dbt views. I would also improve document refresh and product identity handling. ENR, PZN and product label form a practical key here, not an official shortage episode ID.

I used AI assistance to build and review this project. The code, tests and open limits are here to inspect. I need to understand the choices and be able to trace a record myself.

## Read the code

Start with [START_HERE.md](START_HERE.md). Read [the code review](docs/code-review.md), [data contract](docs/data-contract.md) and [validation record](docs/validation.md) for details.

## Sources and rights

The feed is [BfArM/PharmNet](https://anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv). Background passages come from [gesund.bund.de](https://gesund.bund.de/arzneimittel-mit-und-ohne-rezept) and the [administrative-data register](https://www.verwaltungsdaten-informationsplattform.de/register/270).

The MIT licence covers project code. Downloaded source data and passages keep their publishers' terms. Public access does not establish CC0 rights. Raw downloads retain source contact columns. Those columns are excluded from the analytics fields and search interface.

A reported disruption does not establish hospital stock or patient impact. An elapsed expected end date or a missing feed record does not establish resolution.
