# Daily source history

The workflow in `.github/workflows/daily-snapshot.yml` requests a run every day at 06:23 UTC. GitHub may delay scheduled runs. The schedule only takes effect on the default branch after merge. The workflow has read permissions and does not commit to any branch. During review it also runs when its own YAML changes on `finish-project`. This allows a real source and artifact check before merge without activating a schedule on `main`.

## State and reruns

1. On a rerun first look for this run's own saved history. Otherwise find the last successful run of this workflow on the same branch.
2. Restore its `daily-shortage-history` artifact. A failed restoration stops the run. A first attempt with no successful previous run starts an empty history. A rerun without recoverable state fails rather than downloading a replacement baseline.
3. Verify every dated manifest against the hash of its original CSV. Replay accepted observations in date order into local SQLite.
4. If today's UTC manifest exists, skip the feed request. The first successful observation wins for that day even if the source changes later that day.
5. Otherwise download the live feed and run the existing ingestion checks. Save the actual acquisition time, source URL, SHA-256 and snapshot ID only after ingestion succeeds.
6. Rebuild the CSV exports and evidence index. Store the cumulative history and a separate export artifact.

The concurrency group serialises runs for each branch. A retry sees the state of the last successful run. Failed downloads and rejected feeds do not mark a day complete. When raw bytes are unchanged across days there are still two observations but only one raw file. A day's absence means no successful collection, not zero shortages.

This workflow does not mix the bundled sample or synthetic test fixtures into the collected history. Its first successful day is its baseline. Local manual use should start with an empty directory for the same separation. `DATABASE_URL` must be unset for this collector.

```bash
python scripts/collect_daily.py --root collected --history history
```

On a fresh runner the script reconstructs the database from `history`. It does not require a previous SQLite file. A history hash mismatch stops processing.

## Files to keep

`daily-shortage-history` contains `YYYY-MM-DD.json` manifests, content-addressed `raw/*.csv` files and a state marker. `daily-powerbi-exports` contains the four CSV tables and `summary.json`. The app database and index are rebuilt and are not the archive.

Each successful run uploads the full history again with a requested retention of 90 days. Repository policy can shorten retention. This is rolling state, not permanent storage. Download and back it up independently. Artifact size and replay time grow with history. Longer use should move the raw archive and manifests to persistent object storage with a retention policy.

If Actions is paused long enough for the last successful artifact to expire, the next run fails. Recover the saved history from your backup and run the collector locally. Do not delete the old run merely to make a fresh baseline look continuous. Restoring a backup to hosted collection needs a reviewed workflow change or an artifact upload from a recovery run. That path has not been automated.

## Manual acceptance after merge

Run **Collect daily shortage snapshot** manually. Check that acquisition used the live source and inspect the manifest and quality export. Run it again on the same UTC day. The log should say `already_collected` and the snapshot count must stay the same. On the next real day check that a second dated manifest exists and that exports contain both snapshots. Counts may differ from the bundled 28 October example.

For Power BI download and extract the latest `daily-powerbi-exports` artifact into your local `data/exports` folder. Keep all four CSVs from the same run together. Set `SourceFolder` in Desktop, refresh and compare with that artifact's `summary.json`. This is a manual download and refresh, not a Power BI Service scheduled refresh.

CI tests the collector with isolated fixtures. A manual hosted run tests source access, restoration and artifact handling. Several real days are still needed to demonstrate an actual history. No future dates are generated or backfilled.
