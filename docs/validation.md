# Validation record

## Review branch, 28 October 2026

The code was reviewed before editing. See [the review findings](code-review.md). All changes are on `finish-project`. No change from this work was pushed to `main`.

| Check | Result and limit |
|---|---|
| Local pytest | 50 passed and one PostgreSQL skip. Twelve new tests cover daily collection and script safety. |
| Ruff | Passed for `src`, `scripts` and `tests`. |
| Cached bootstrap | Passed. Replayed the original observation without replacing authored Power BI files. |
| Local model SQL | All six dbt SELECTs and both reconciliation queries passed on SQLite. This is not a local PostgreSQL build. |
| PostgreSQL integration and dbt | Passed in [branch CI](https://github.com/Darpen24/medsupply-monitor/actions/runs/40693563041). An isolated PostgreSQL service runs the integration test and `dbt build`. |
| Power BI structural checks | 26 JSON files validated. Five tables and four relationships passed reference checks. M, DAX and Desktop rendering were not executed. |
| Retrieval benchmark | 18 retrieval questions hit at 3 with MRR 1.0. All 12 scope cases matched expectations. These are the same hand-picked baseline questions, not independent accuracy evidence. |
| Real daily workflow | [First hosted collection](https://github.com/Darpen24/medsupply-monitor/actions/runs/40693563220) succeeded with a live download. It stored cumulative raw history and CSV export artifacts. |
| Hosted same-day repeat | [A separate run](https://github.com/Darpen24/medsupply-monitor/actions/runs/40694121291) restored history from the first run, returned `already_collected` and still exported one snapshot. |
| Web browser acceptance | Recorded in the earlier build at 1440x1100 and 390x844. Not rerun for this maintenance change. |
| LLM adapter | Mocked provider requests passed. No real paid model call or human groundedness review is claimed. |

The local test environment emitted a Starlette/httpx deprecation warning. The collection run also emitted an upload-artifact Node runtime warning. These did not fail the jobs.

## Two different real observations

The bundled example was acquired at `2026-10-28T06:11:05.006816+00:00`. It contains 896 source rows, 893 accepted package observations and three quarantined rows. There are 512 distinct report IDs among accepted rows. Its source hash is in `data/sample/manifest.json`.

The review workflow downloaded the live feed at `2026-10-28T13:07:35.511051+00:00`. It found 890 source rows, 887 accepted observations and three rejected rows. Its SHA-256 was `8091462449dc64b68f568dea29d3f5ac7a7f412bc2f968c8d852eb146522f987`. Its snapshot ID was `0da8db5f48848f7adfae6426`. An early rerun downloaded again because its own prior artifact was unavailable. That exposed a restoration gap. The workflow now refuses an empty-state rerun and records which history it restores. The next separate run restored the saved artifact and skipped collection. This development issue is not evidence of multi-day history.

The retained review history starts at `2026-10-28T13:09:10.473468+00:00` with snapshot ID `bac462414129b23b649e827f`, from that early rerun. Its raw hash is unchanged. The later hosted run restored this history and skipped a second collection. It does not import the bundled baseline or synthetic fixtures. Both acquisitions happened on the same date. They do not establish multi-day collection. Do not replace the bundled expected counts with the live counts without also changing the dataset being checked.

## What remains unverified

- A second real day of collection and later change history.
- The scheduled trigger after merge. A branch push exercised the collection job before merge.
- Long-pause recovery after artifact expiry. Retention is requested for 90 days and needs an independent backup.
- Windows Power BI import, refresh, DAX calculations and native rendering.
- Real LLM calls and factual review against the returned passages.

The original screenshots are web app captures. There are no native Power BI screenshots or populated PBIX files. The original ZIP and release manifest have been removed. Historical validation claims should be checked against their linked workflow runs rather than those old bundles.

## Power BI acceptance record

Fill this only after running Desktop. See [the steps](finish-acceptance.md).

- Desktop version:
- Refresh date and selected dataset:
- SourceFolder:
- All five tables loaded:
- Monitoring counts matched summary.json:
- Audit counts reconciled:
- Snapshot slicer and chart filters checked:
- Both pages visually inspected:
- PBIX saved locally:
- Real screenshots added:

## Live LLM acceptance record

- Workflow run URL and date:
- Provider and model:
- Two real calls completed:
- Each factual claim compared with its numbered passage:
- Unsupported claims found:
- Human review result:
