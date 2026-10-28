# Start here

You can run the local platform without cloud infrastructure, database servers or model credentials. Follow the README's five-minute setup, then use these exercises to understand it.

## 1. Explain the problem in one sentence

“I help a procurement analyst monitor official reported medicine disruptions and inspect their evidence without losing changes between downloads.”

The data does not contain a hospital's purchases or stock. Do not claim this measures financial exposure or actual patient impact.

## 2. Follow one record

Search **NIPRUSS** in the web app. Inspect the reported reason and additional explanation. Click **Inspect** and follow the official source link. Identify the report ID, PZN and observation timestamp. The reason is attributed to the source, not invented by an LLM.

Open `data/exports/FactObservation.csv` and locate the same report. Then read `parse()` in `src/medsupply/pipeline.py`. Notice how the eight-digit PZN remains text, the German dates become ISO dates, and the report explanation stays in German.

## 3. Understand the counting trap

The downloaded CSV contains 896 rows. One malformed row and two conflicting product-identity rows are quarantined. The 893 accepted rows refer to 512 distinct report IDs. A report can cover several packages.

Use the quality page to explain exactly why the three rows were excluded. The two conflicting Scintimun rows have different report IDs and expected end dates; both remain in quarantine. We do not choose one arbitrarily.

## 4. Prove a rerun is safe

Run `python scripts/bootstrap.py --cached` twice. The second ingestion should say `already_processed`; accepted counts remain unchanged. Read the raw SHA-256 in `data/sample/manifest.json` and compare it with the successful run.

The same source bytes observed at a later timestamp are a new observation. That distinction allows daily snapshots even when no source data changes.

## 5. Learn the change model without faking live history

Run `pytest tests/test_extensions.py tests/test_pipeline.py -q`.

The tests create separate temporary synthetic fixtures, advance an expected end date, remove a record and add another. They verify that changes are detected, the first observation is a baseline, and a missing record is never labelled resolved. These fixtures do not enter the official-data dashboard.

Collect another real snapshot on a later day with `python scripts/bootstrap.py`. Only then does the main dataset have meaningful measured history. Ask “Which expected end dates were extended?” to run the defined SQL comparison and attach reported explanations.

## 6. Understand evidence search versus generation

Read `retrieve()` in `src/medsupply/retrieval.py`. It ranks tokens with BM25 and returns source metadata. The default answer quotes the retrieved record passages and is labelled `extractive_evidence`.

Read `generate()` next. The optional model receives the question and retrieved passages, with instructions to cite those passages. It does not calculate dashboard totals. A live model configuration is supplied separately; live calls were not tested here.

Try an unrelated question, a clinical dosage question, and an aggregate count question. Notice the different outcomes. The small evaluation file shows exactly which 30 questions were assessed; it is not proof of general accuracy.

## 7. Open Power BI and verify, rather than assuming

Open `powerbi/MedSupply.pbip`, confirm `SourceFolder`, and refresh. Check 893 package observations, 512 source reports, 198 supply-critical and 247 hospital-relevant observations. Check that the quality audit reconciles 896 = 893 + 3.

The native files passed structural checks, but Desktop refresh and rendering were not run in the build environment. Record your Desktop version and validation result in `docs/validation.md` before claiming the native report is verified.

## Portfolio demo: three minutes

1. Show the monitor and define its package/report counting rules.
2. Search NIPRUSS, inspect the published explanation and cite the source.
3. Show quarantine and explain the conflicting source records.
4. Explain how immutable snapshots enable comparisons and safe recovery.
5. Show the Power BI model and distinguish calculated metrics from retrieved evidence.

## Interview questions you should be able to answer

- Why does this use snapshots rather than overwriting a current table?
- How does an idempotent replay differ from an unchanged source observed tomorrow?
- Why can 893 package observations refer to only 512 reports?
- What happens when 10% of a source file fails validation?
- Why isn't a missing record evidence that a shortage resolved?
- What do BM25 hit rate and MRR measure, and what do they not measure?
- Why does SQL calculate counts while retrieval supplies explanations?
- Which parts were actually executed, and which still need their own runtime acceptance checks?
