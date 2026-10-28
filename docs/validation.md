# Validation report

## GitHub acceptance update — 28 October 2026

The [source import](https://github.com/Darpen24/medsupply-monitor/actions/runs/40668305519) succeeded and the complete project folders are published. The [first full CI run](https://github.com/Darpen24/medsupply-monitor/actions/runs/40668616742) passed both jobs: local checks (17 seconds) and PostgreSQL integration plus dbt build (51 seconds). PostgreSQL and dbt execution are therefore no longer pending. The one-time import workflow was disabled after publication. Power BI Desktop execution and live LLM generation remain unverified.

The original local-build record below is retained for provenance; its PostgreSQL/GitHub pending rows describe the earlier build environment, superseded by the linked CI run. The bundled ZIP and release manifest describe that original build snapshot.

Build date: **28 October 2026**. This report distinguishes executed checks from supplied but unexecuted integration paths.

## Executed

| Check | Result | Evidence |
|---|---|---|
| Official CSV acquisition | HTTP 200, 328,412 source bytes | `data/sample/manifest.json` and bundled unmodified CSV |
| Baseline reconciliation | 896 source rows = 893 accepted + 3 quarantined | `data/exports/QualityAudit.csv` |
| Local unit/behavior/API tests | **35 passed, 1 skipped** | `tests/`; PostgreSQL test is the skip |
| Static lint | Passed | `ruff check src scripts tests` |
| Fresh-directory cached bootstrap | Passed; reproduced 893 accepted and 3 quarantined | `scripts/bootstrap.py --cached` |
| Safe replay | Second run returns `already_processed`; counts unchanged | Pipeline tests and cached-bootstrap replay |
| dbt parsing | Passed with installed dbt / PostgreSQL adapter | `dbt parse --project-dir dbt --profiles-dir dbt` |
| dbt model SELECTs on SQLite | Six models executed; reconciliations passed | `scripts/check_marts.py` |
| Retrieval/scope benchmark | 18/18 retrieval hits at 3; MRR@3 1.0; 12/12 scope outcomes | `docs/evaluation.json` |
| Evidence index | 899 chunks: 893 report observations + 6 official document sections | `medsupply index` output |
| Web app browser interaction | Passed at 1440×1100 and 390×844; no JavaScript errors or mobile horizontal overflow | `docs/previews/browser-validation.json` |
| Power BI JSON schemas | **26 native project/report JSON files validated** | `docs/powerbi-validation.json` |
| Power BI model references | Five tables, four relationships; visual field/measure references valid | `scripts/validate_powerbi.py` |
| Optional model-provider adapter | Mocked request contract and citation rejection passed | `tests/test_generation.py` |

The test run emits one dependency deprecation warning from the installed Starlette/httpx test-client combination. It did not fail the tests; it is recorded rather than suppressed.

## Source quality findings

1. One Xenpozyme record has fewer CSV columns than the header; classification is missing and a preceding value appears shifted. It is quarantined without attempting to repair source meaning.
2. Two Scintimun rows have identical ENR/PZN/product identity and different report IDs/expected ends. Both are quarantined rather than selecting one.
3. The source has placeholder PZN values; IDs remain strings, and product identity also includes ENR and product label.
4. Multiple PZNs share report IDs. Accepted packages and distinct source reports have separate measures.

## Browser checks performed

- Loaded official accepted data from the running local API.
- Confirmed 15-row pagination and working filter submission.
- Searched NIPRUSS and opened its product-scoped explanation.
- Confirmed official evidence links and original source explanations.
- Opened the quality page and confirmed all three quarantined rows.
- Captured desktop and mobile application previews and checked for JavaScript errors and page-width overflow.

The images in `docs/previews/` are web app captures. No native Power BI screenshots or PDFs are claimed.

## Benchmark interpretation

The 30 questions are hand-selected for this baseline snapshot: 12 named-product questions, six official-document questions, and 12 scope/no-match/history questions. Products and document selectors are explicit in `scripts/evaluate.py`. This is an inspectable smoke benchmark, not an independent held-out measurement of general retrieval quality. It does not evaluate live generation, hallucination, semantic paraphrases, multilingual coverage, or production safety.

## Not executed

| Path | Reason / concrete next check |
|---|---|
| PostgreSQL integration | No usable PostgreSQL service in the build environment. `POSTGRES_TEST_URL` test and isolated GitHub Actions service are supplied. |
| PostgreSQL dbt materialization/data tests | Run `dbt build` against the supplied dedicated service; only dbt parsing and the exact portable SELECTs were executed locally. |
| Power BI Desktop import/refresh | Desktop was unavailable. Open PBIP, set `SourceFolder`, refresh, reconcile cards and exercise filters. |
| Native DAX execution and report rendering | Structural schema validation is not runtime acceptance. Record Desktop version, totals and export images here after running it. |
| Live model generation | No model credentials were supplied. Adapter tests use mocked responses, not real LLM output. |
| GitHub CI | Workflow supplied, but no new repository was created or workflow executed. |
| Multi-day source history | Only one real acquisition is bundled. Change behavior is tested using isolated synthetic fixtures, never mixed into the official dashboard. |

No hosting, daily job, cloud resources, paid subscription or paid API usage has been activated.

## Desktop acceptance record (fill after execution)

- Desktop version:
- Refresh date and source-folder path:
- Observation counts match the selected snapshot:
- Monitoring and audit filters behave as documented:
- Baseline note visible with only one snapshot:
- Native report export inspected:
