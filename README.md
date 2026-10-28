# MedSupply Monitor

**German reported medicine shortage intelligence: an auditable data pipeline, Power BI project, and cited evidence application.**

Pharmacy procurement analysts need to know what was reported, what changed, and where the explanation came from. This project preserves official observations over time and separates calculated metrics from retrieved text.

![Working web application, captured with Chromium](docs/previews/monitor.png)

## Start in five minutes

Python 3.11+; Python 3.12 was used for validation. From this project directory:

```bash
python -m venv .venv
# Linux / macOS:
source .venv/bin/activate
# Windows PowerShell instead:
# .\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
python scripts/bootstrap.py --cached
uvicorn medsupply.api:app --host 127.0.0.1 --port 8000
```

Open **http://127.0.0.1:8000**. API documentation: **http://127.0.0.1:8000/docs**.
No model credentials are required for the default evidence-search application.

`--cached` reproduces the bundled official 28 October 2026 observation. It does not present that observation as today's live status. For a fresh observation:

```bash
python scripts/bootstrap.py
```

The raw feed and timestamped database observations are preserved in `data/`. Keep that directory between runs. Run the fresh command daily with your OS scheduler if you want to accumulate measured history. No external schedule or hosting has been activated.

## Verified baseline

| Measure | Value |
|---|---:|
| Source CSV rows | 896 |
| Accepted package observations | 893 |
| Quarantined source rows | 3 |
| Distinct source report IDs among accepted observations | 512 |
| Distinct ingredient labels, not normalized chemical entities | 248 |
| Distinct manufacturer / authorization-holder labels | 122 |
| Supply-critical package observations (`verskri`) | 198 |
| Hospital-relevant package observations (`ja`) | 247 |

Source acquisition timestamp and SHA-256 are in [the sample manifest](data/sample/manifest.json). Counts describe the accepted observation, not all medicine availability in Germany.

## What works now

- Live BfArM/PharmNet CSV download, retry, encoding detection and schema validation.
- Immutable content-addressed raw files, safe same-timestamp reruns and transactionally published snapshots.
- Quarantine, run audit, >5% rejection gate and source-to-output reconciliation.
- Baseline-aware change detection, including expected-end-date changes and feed membership changes.
- SQLite local baseline and PostgreSQL adapter with Docker Compose and opt-in integration test.
- Six dbt models and two reconciliation tests; additional model key/relationship tests.
- FastAPI application with searchable records, pagination, product-scoped evidence, change history and quality audit.
- BM25 retrieval across current report explanations and six extracted official document sections.
- SQL-backed expected-end-date extension investigation. Ask **“Which expected end dates were extended?”** after collecting two snapshots.
- Optional live OpenAI generation with explicit configuration and citation-ID checks.
- Native Power BI PBIP/PBIR project: five tables, four relationships, eleven DAX measures, two report pages.
- Automated tests, CI configuration, reproducible scripts and a 30-question retrieval/scope benchmark.

## Validation status — read before making portfolio claims

**Executed here:** live source download; local ingestion; replay/idempotency; failure-path and API tests; exact portable dbt SELECT statements on SQLite; dbt parsing; real Chromium desktop/mobile interaction; retrieval/scope evaluation; Microsoft report JSON schema validation.

**Not executed here:** PostgreSQL server integration and `dbt build` on PostgreSQL; Power BI Desktop refresh, DAX execution and native report rendering; live LLM API calls. Dedicated checks and setup steps are supplied. The PostgreSQL integration test is skipped without a dedicated test service. The CI workflow has not been executed on GitHub.

The UI screenshots are **web application captures**, not Power BI exports. No PBIX with a populated imported model is supplied. Open the PBIP and refresh it in Desktop to produce one.

## Open the Power BI project

1. Run the cached bootstrap first; it generates exports and configures the local export-folder parameter.
2. Open [`powerbi/MedSupply.pbip`](powerbi/MedSupply.pbip) in a recent Power BI Desktop release supporting PBIP and PBIR.
3. In **Transform data → Manage parameters**, confirm `SourceFolder` points to this checkout's `data/exports` folder.
4. Refresh. Reconcile the monitoring cards against `data/exports/summary.json`.
5. Validate the snapshot slicer and cross-filtering. The measures default to the latest timestamp in the selected snapshot context.
6. The quality page intentionally aggregates all exported runs and is disconnected from product filters. Use its run table to inspect individual attempts.

After moving the checkout, run `python scripts/build_powerbi.py --root .` to reset the parameter. This regenerates the authored report; do not run it over personal Desktop edits without preserving them first. `powerbi/power-query/` and `powerbi/measures.dax` expose the logic for learning.

## Optional PostgreSQL and dbt

```bash
python -m pip install -e ".[postgres,dev]"
docker compose up -d postgres
```

Set `DATABASE_URL=postgresql://medsupply:medsupply_local@localhost:5432/medsupply` in your shell, then:

```bash
python scripts/bootstrap.py --cached
dbt build --project-dir dbt --profiles-dir dbt
```

PowerShell environment syntax: `$env:DATABASE_URL = "postgresql://..."`.
For custom credentials also set `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD` and `PGDATABASE` for dbt. The sample local password is for the loopback-only development service. `.env.example` documents variables; Python commands do not automatically load `.env`.

The dbt marts are independently inspectable. The current Power BI delivery imports validated CSV exports from the operational store, not dbt views. Both paths share the same underlying observation grain; [check_marts.py](scripts/check_marts.py) executes the dbt SELECTs on the local baseline and checks reconciliation. Connecting Power BI directly to the PostgreSQL marts is a documented extension, not a dependency for viewing the project.

## Optional live generation

Configure `OPENAI_API_KEY`, `OPENAI_MODEL` (a model available to your account), and `ENABLE_LIVE_LLM=true` in your shell. The CLI `medsupply ask --live` is an explicit opt-in; the API additionally requires the enable flag.

```bash
medsupply ask "Why is NIPRUSS reported in shortage?" --live
```

The API accepts `POST /api/ask` with `{"question":"...","use_llm":true}`. Retrieved text is sent to the configured provider. The browser defaults to extractive evidence mode; it never silently makes paid model calls. API usage is separate from a ChatGPT or Claude subscription.

BM25 is a lexical baseline, not semantic embedding search. A model-backed RAG path is implemented but needs credentials for live acceptance. Citation-ID validation prevents invalid reference numbers; it does **not** prove every generated sentence is supported. Further groundedness and adversarial evaluation is required before relying on live generated answers.

## Reproduce checks

```bash
pytest -q
ruff check src scripts tests
python scripts/check_marts.py
python scripts/evaluate.py
python scripts/validate_powerbi.py
dbt parse --project-dir dbt --profiles-dir dbt
```

Optional browser check: `pip install playwright==1.51.0`, `playwright install chromium`, then `python scripts/check_browser.py`. It starts its own local server and captures desktop and mobile previews. It expects the bundled baseline dataset.

For PostgreSQL integration use an **empty dedicated test database**, set `POSTGRES_TEST_URL`, then run `pytest tests/test_postgres.py`. No test truncates an existing database. The CI PostgreSQL job supplies an isolated service and runs the integration test plus `dbt build`.

## Read and learn

- [START_HERE.md](START_HERE.md): a hands-on walkthrough and demo.
- [Architecture and design decisions](docs/architecture.md).
- [Data contract, counting rules and limitations](docs/data-contract.md).
- [Validation report](docs/validation.md).
- [Retrieval evaluation results](docs/evaluation.json).

## Sources and rights

Primary dataset: [BfArM/PharmNet public shortage CSV](https://anwendungen.pharmnet-bund.de/lieferengpassmeldungen/public/csv).
Context: [German federal health portal](https://gesund.bund.de/arzneimittel-mit-und-ohne-rezept) and [German administrative-data register description](https://www.verwaltungsdaten-informationsplattform.de/register/270).
Reference only: [BfArM critical ingredient list](https://www.bfarm.de/SharedDocs/Downloads/DE/Arzneimittel/Zulassung/amInformationen/Lieferengpaesse/Liste_versorgungskritischer_wirkstoffe.pdf?__blob=publicationFile).

Raw source downloads and extracted passages retain their source terms and attribution; they are not relicensed by this project's MIT code license. Public accessibility does not by itself establish CC0 rights. Review the publishers' terms before redistributing source files in a publicly hosted product. Source contact columns are preserved in immutable raw bytes but excluded from the analytics contract and search interface.

This monitors reported supply disruptions; it does not advise on treatment, substitution, hospital stock or patient outcomes. It cannot establish resolution from an elapsed expected end date or a record disappearing from a feed.
