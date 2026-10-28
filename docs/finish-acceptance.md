# Finish runtime acceptance

Two checks remain distinct: Power BI must execute M/DAX and render the native report in Desktop; the model path must make real provider calls. Neither is established by JSON schema or mocked-provider tests.

## A. Power BI Desktop on Windows

Use a current standard Power BI Desktop release supporting PBIP/PBIR, not the Report Server edition. Download or clone the current repository source. If using Download ZIP, extract it completely first. Run these commands from the project folder in PowerShell:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[dev]"
.\.venv\Scripts\python.exe scripts\bootstrap.py --cached
Start-Process .\powerbi\MedSupply.pbip
```

No activation or PowerShell execution-policy change is needed. The bootstrap generates the CSV exports. It preserves authored report files. Set the local `SourceFolder` parameter yourself in Desktop before refreshing.

1. In Desktop, open **Transform data → Manage parameters**. Confirm `SourceFolder` points to this extracted checkout's `data/exports` directory.
2. Select **Close & Apply**, then **Home → Refresh**. All five model tables must load without errors. Record any exact error rather than deleting or skipping a failing table.
3. Confirm the monitor page displays the following baseline values:

| Card | Expected |
|---|---:|
| Package Observations | 893 |
| Source Reports | 512 |
| Critical Observations | 198 |
| Hospital Relevant | 247 |

4. On the quality page, verify **896 source rows**, **893 accepted**, **3 rejected**; acceptance is about **99.7%**. The report has one accepted snapshot, so its baseline note must be visible.
5. Click a bar on the monitoring page. The relevant observation cards and other monitoring chart must respond. Clear the selection and confirm the four full baseline numbers return. The disconnected quality audit should keep its documented totals.
6. Confirm both report pages render without blank/error visuals, clipped titles, or unreadable labels. The snapshot slicer must expose the bundled observation timestamp. A one-snapshot dataset cannot demonstrate switching between different real observations; do not invent a trend.
7. Save a populated `.pbix` as `acceptance/MedSupply-validated.pbix` and export both report pages to `acceptance/MedSupply-validated.pdf`.
8. Record the Desktop version, refresh date, table-loading result, four monitoring values, audit values, filter result and export review in the acceptance template below.

If Desktop reports that PBIP support is disabled, enable the project-related option under File → Options and settings → Options → Preview features if your installed version still requires it, restart Desktop and reopen. If opening or refresh fails, keep the exact message and the full project folder intact for diagnosis. Structural schema validation did not guarantee runtime import would work.

## B. Real LLM calls using GitHub Actions

The implemented provider is OpenAI. API billing is separate from ChatGPT subscriptions. Do not add the key to code, README, screenshots or chat. The workflow runs only when manually dispatched and makes two short API requests; output is capped at 512 completion tokens per request, plus input tokens.

1. Create a project API key in your OpenAI API account and ensure that API billing and the selected model are available. Do not assume a ChatGPT subscription supplies API credit.
2. In this GitHub repository, open **Settings → Secrets and variables → Actions → Secrets → New repository secret**. Name it **`OPENAI_API_KEY`** and enter the key yourself.
3. On the **Variables** tab, add **`OPENAI_MODEL`**, using an available model that supports the Chat Completions endpoint and the `max_completion_tokens` parameter.
4. Open **Actions → Verify live LLM → Run workflow → finish-project (or main after merge) → Run workflow**. This is your explicit opt-in to the provider calls. No schedule or push trigger is configured for this workflow.
5. The job must pass. Download **live-llm-acceptance** from the run's artifacts and open `live-llm-results.json`.
6. Confirm `real_model_calls_completed` is **2** and `automated_contract_checks` is **passed**. Then manually compare every factual claim with its numbered source passage. NIPRUSS should report the published supply explanation; it must not invent available stock, guarantee an end date, or recommend patient treatment. The definition question should distinguish a reported delivery disruption from patient-level supply impact.
7. Record the run URL, selected model, date and human review result. `human_groundedness_review` intentionally remains `pending` in machine output: valid citation numbers alone do not prove the answer is supported.

HTTP 401 usually needs key/authentication review; 403 needs permission/model-access review; 429 can reflect exhausted quota or rate limits. The script reports the status without dumping provider error bodies or secrets. Correct the underlying account/configuration issue before rerunning.

### Alternative: run the same check locally

After the cached bootstrap, configure the environment without placing a key in source files or command history. In PowerShell 7:

```powershell
$env:OPENAI_API_KEY = Read-Host 'OpenAI API key' -MaskInput
$env:OPENAI_MODEL = Read-Host 'Available chat-completions model ID'
.\.venv\Scripts\python.exe scripts\verify_live_llm.py --run-live
Remove-Item Env:OPENAI_API_KEY
```

Review `acceptance/live-llm-results.json`. Do not commit credentials. Save only reviewed non-sensitive output and the verification record.

## Acceptance record

```text
Power BI Desktop version:
Refresh date and source folder:
All five tables loaded without errors:
Cards: 893 / 512 / 198 / 247:
Audit: 896 = 893 + 3:
Filter interaction and reset checked:
Both report pages visually reviewed:
Populated PBIX and native PDF saved:

Live model/provider:
Verification date and workflow run URL:
Two real calls completed:
Automated contract checks passed:
Every factual claim checked against cited passages:
Invented causes, inventory, guaranteed dates or clinical advice found:
Final human groundedness review result:
```

Do not mark either component fully accepted until its actual execution and evidence review are complete. A failed check is useful evidence to fix the project, not a reason to relabel it as passed.
