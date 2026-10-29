# Code review before the finish-project changes

Reviewed on 28 October 2026. I read `src/medsupply`, all tests, the dbt models and tests, the scripts and all three existing workflows. Remote source files were compared with the local working files. The local CI YAML had newer action versions than `main`; the published workflow was checked separately.

The README-only review was partly right about unfinished acceptance and the presentation. It was not enough to conclude the repo was only a generated shell. The implementation contains real parsing, transaction handling, rejection gates, snapshots, SQL comparisons, an API and behavior tests. The pre-change suite passed with 38 tests and one PostgreSQL skip. Code style alone cannot establish authorship or copying. I found no evidence of copying from another project, but did not run a plagiarism search.

## Findings

| Finding | Evidence and response |
|---|---|
| No daily collection | Existing workflows only validated code, imported the archive or opted into LLM acceptance. Added scheduled collection with restored cumulative state and one observation per UTC day. |
| Legacy archive dependency | The disabled importer still referenced `MedSupply-Monitor.zip` and pushed to `main`. Replaced it with a read-only retirement notice. The release manifest had no runtime consumers. The two obsolete files are removed from the branch. No other files are deleted. |
| Power BI has a separate data path | M partitions read CSVs. They do not query dbt. Kept this route and documented its setup cost and duplicated transformation logic. Desktop results remain unverified. |
| Bootstrap overwrote report files | It called `build(root)` on every run. Regeneration now requires `--rebuild-powerbi`. Added a test preserving an authored report file. |
| Document timestamps could change on checkout | `prepare_corpus.py` used filesystem modification times. It now preserves hash-matched saved provenance. Unknown provenance stays unknown. Cached pages are still not automatically refreshed. |
| No real LLM evidence | Provider tests mock HTTP. Citation-ID checks do not establish grounding. The live acceptance script and manual workflow remain available but need a key and human review. |
| Narrow retrieval evaluation | The 30 questions are hand-picked for the baseline. Evaluation is not in CI. Keywords and a small alias map will miss paraphrases. Scope gates are also keyword rules, not a complete classifier. |
| Limited database coverage | The opt-in PostgreSQL test covers success, replay and a date change. Most failure cases run only on SQLite. dbt tests check keys, relationships and reconciliation, not domain completeness. |
| Audit and export limits | Failed schema parsing records zero row counts. Replaying a failed run at exactly the same timestamp can collide with the audit primary key. CSV files are replaced individually, not as an atomic bundle. Do not refresh Desktop during an export. These remain follow-up work. |
| Identity is approximate | ENR, PZN and product label form a key. A renamed product can appear as disappearance and first observation. This is not official episode tracking. |
| Validation docs were stale | The old report said CI and PostgreSQL had never run even though published CI had passed. Updated the record and kept runtime gaps explicit. |

The PostgreSQL adapter is exercised in CI. `check_marts.py` is a local SQL cross-check rather than a replacement for dbt. The Power BI generator is used only by explicit regeneration after this change. The browser checker is optional and tied to the bundled snapshot. None of these is an unexplained unused scaffold.

## What was not verified during review

Power BI Desktop, DAX execution, native report rendering, live paid model calls, factual grounding of generated text, several real days of collection and long-term artifact recovery were not verified. The browser acceptance was recorded in the earlier build; it was not rerun for this maintenance change. No conclusion about the owner's interview readiness follows from passing tests.
