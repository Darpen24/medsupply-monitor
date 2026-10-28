# Start here

I built this to follow reported medicine shortages in Germany. I wanted one project where I could practise ingestion, SQL models, evidence search and Power BI with real public data.

Start with the setup in the README. Use `--cached` first. That makes the results repeatable while you read the code.

## Follow one record

Search for NIPRUSS in the web app. Open its evidence. Find the report ID, PZN and observation time. Then locate the same record in `data/exports/FactObservation.csv`.

Read `parse()` in `src/medsupply/pipeline.py`. It keeps PZN as text so leading zeros stay intact. It converts dates and checks required fields. Rejected rows go to quarantine. The bundled CSV has 896 rows. The accepted 893 package observations contain 512 distinct report IDs.

Read `ingest()` next. It saves the original bytes under their SHA-256 hash. It writes an accepted snapshot in a transaction. More than 5% rejected rows blocks publication. The first snapshot is a baseline. Later snapshots compare field values and feed membership. A missing record is not labelled resolved.

Run `python scripts/bootstrap.py --cached` twice. The second run should say `already_processed`. That checks a replay of the same timestamp and bytes. It is different from observing unchanged data on a new day.

## Follow the analytics path

`export()` writes the four CSVs used by Power BI. The `dbt/models` folder is a separate PostgreSQL route. Read `fact_observation.sql`, then `mart_current_shortages.sql`. The fact grain is one product key in one snapshot. The current mart selects the newest observation timestamp.

Run `python scripts/check_marts.py` after bootstrap. It runs those model SELECTs on SQLite. A real `dbt build` runs against PostgreSQL in CI. Power BI does not consume those views yet. It imports CSVs to keep local setup simple.

## Follow an evidence question

Read `build_index()`, `retrieve()` and `ask()` in `src/medsupply/retrieval.py`. The index contains current reported explanations and a few official document sections. BM25 ranks words. Default answers quote passages. Counts are handled separately from retrieval.

`generate()` is the optional model call. It sends retrieved passages as context and checks citation numbers in the answer. That check does not establish factual support. Tests mock the provider. Real calls and human review are still needed.

The 30 questions in `scripts/evaluate.py` are examples selected for this snapshot. They do not establish general accuracy.

## Build real history

Read `scripts/collect_daily.py` and `.github/workflows/daily-snapshot.yml`. The workflow carries raw files and dated manifests forward in an artifact. The collector skips a day that already has a successful observation. It rebuilds SQLite from verified history on a fresh runner.

The schedule starts after merge to the default branch. A manual run and its same-day rerun can check collection and restoration. Only future days can establish real multi-day history. Keep a backup of the history artifact. Actions retention is limited.

## Finish Power BI on Windows

Open `powerbi/MedSupply.pbip`. Set `SourceFolder` to your local `data/exports` folder and refresh. For the bundled snapshot compare 893 packages, 512 reports, 198 critical observations and 247 hospital-relevant observations. The audit should show 896 = 893 + 3.

Test the slicer and chart filters. Save a PBIX and take actual screenshots of both pages. Record the Desktop version and date in `docs/validation.md`. No Desktop result is claimed until that is done. Bootstrap will preserve your authored report files unless you explicitly request regeneration.

## What I built and what I would change

I built a small data pipeline that keeps reported evidence instead of replacing yesterday's data. I added tests for bad rows, reruns and snapshot changes. The web app makes those records easier to inspect.

The next steps are real collection over several days, Windows report acceptance and review of real LLM answers. I would later replace artifact storage with longer lived storage and connect Power BI to the dbt views. I would improve retrieval with questions I did not choose while building it. I would also review identity rules before treating product changes as shortage episodes.

I used AI assistance. My responsibility is to understand this code and explain its limits honestly. The quickest way to learn it is to trace one record from the raw CSV through the database to an export and an evidence result.
