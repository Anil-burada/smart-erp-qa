# Smart ERP QA - Integrated Codegen-style Recording Update

This is a **targeted upgrade** to the supplied v4/v5.1 local FastAPI + Playwright project. It is not a finished multi-user Team Edition or an OpenAI/Ollama test generator.

## Why the same automation engine works with multiple ERP apps

A registered ERP has a unique `project_id`, URL, browser, environment and project-scoped `locators.json` file. The shared Python Playwright engine can execute any **reviewed** workflow in the selected project; it resolves that project's locator keys at execution time. A shared POM template can be mapped to each ERP's corresponding fields, if the business workflow actually matches. This does not mean CSS/role locators from ERP A will work unchanged in ERP B.

For example:

- ERP A -> `projects/leocem/locators.json` and `workflows/leocem/purchase_indent.json`.
- ERP B -> `projects/erp_b/locators.json` and `workflows/erp_b/purchase_order.json`.
- Backend engine -> the **same** `backend/browser.py`, `backend/json_workflow.py` and `backend/pom.py`.

## What has changed in this patch

1. `Open ERP` launches a Chromium browser window at approximately 85% of the local display (headed Windows). Window managers, DPI, browser chrome and other engines can alter the final usable size.
2. You can type a test username and password **in the ERP browser directly**. The recorder excludes ordinary password-form interactions, but you should still review captured data.
3. The **Workflows** page now has **Start Fresh Recording**, **Pause**, **Resume** and **Finish Demonstration & Save JSON**.
4. Opening a test/staging ERP **still starts passive capture** for backward compatibility; click **Start Fresh Recording after login** to clear earlier steps and start exactly where you want.
5. Shows live action previews (last 50) on the Workflows page, without navigating away from the ERP browser.
6. The recorder prefers uniquely observed accessible roles, labels, and test IDs where available, while preserving its existing fallback locators and capture schema.
7. A saved workflow has **Download Playwright Python (.py)**. This exports inspectable, project-specific code from the same JSON and locator library. It does **not** launch a browser, automatically sign in, or replace reviewed JSON replay.
8. Existing workflows, SQLite project registry, POM mapping, safe native negative candidates, trace/evidence and v5.1 authenticated-page replay fix are retained.

**This is an integrated Codegen-style DOM recorder, not a direct embedding of Playwright's Inspector.** Official Playwright `codegen` remains a separate tool for generating reference scripts.

## Apply to your existing Windows project (recommended)

1. Close the running dashboard (`Ctrl+C` in its PowerShell terminal) and close the Playwright browser.
2. Back up the **entire existing project folder**, especially `data/`, `projects/`, `workflows/`, and any existing changes.
3. Open PowerShell **inside the folder containing your existing `run.py`**.
4. Expand the `smart_erp_qa_v6_recorder_patch.zip` into that exact folder, overwriting only the patched source files:

   ```powershell
   Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\smart_erp_qa_v6_recorder_patch.zip" -DestinationPath "." -Force
   ```

   Change the ZIP path if downloaded somewhere else. The patch does **not** include or overwrite your SQLite DB, saved workflows, locator JSONs, or `.env`.

5. Activate your *working* virtual environment and run:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m playwright install chromium
   .\.venv\Scripts\python.exe -m pytest -q
   .\.venv\Scripts\python.exe run.py
   ```

   If `.venv` is outside the project folder, adjust its path. Do not run `run.py` from a different working folder.

6. Open `http://127.0.0.1:8766` on the same machine; hard-refresh with `Ctrl+Shift+R` to load new JS.

## How to test without affecting real business records

1. Register the included mock ERP with project ID `mock_erp`, URL `http://127.0.0.1:8766/mock/` and environment `test`.
2. On Browser Session, select it and choose **Open ERP Application**.
3. Log in using dummy mock data in that browser.
4. On Workflows, enter a new workflow name, then **Start Fresh Recording**.
5. Demonstrate **navigation and ordinary field entry only**, avoiding Save, Approve, Submit and any real business updates.
6. **Pause**, check the step count and preview, then **Resume** as necessary.
7. Choose **Finish Demonstration & Save JSON**, open the new draft, inspect locators, and download its generated Python.
8. Review and approve only when every step is valid. Replay the approved flow only in a controlled TEST/STAGING ERP. For replay, position the already-authenticated browser on the first step's screen; v5.1 intentionally does not navigate back to a saved `start_url`.

## Runtime and security notes

- Browser automation is local: a browser window opens on the computer where `run.py` executes. A shared server will need a separate tester/browser-agent architecture with authentication and isolated sessions, not just this patch.
- There is one active browser controlled by this process. Concurrent tester sessions are **not implemented**.
- The recorder captures supported DOM actions, **not** guaranteed correct business assertions. Custom dropdowns, dynamic grids, iframe interactions, popups/new tabs and shadow DOM may need manual handling.
- Password fields are excluded; do not type secrets into other ordinary fields. Review workflow JSON before approving, sharing or exporting code.
- Script export from an unapproved workflow is available for **review only**. Do not execute unapproved code or production write actions.
- A green action replay confirms that recorded Playwright actions finished. ERP calculation/status correctness requires separate verified assertions.
- OpenAI API plus selectable Ollama positive/negative test generation is **not included in this targeted recorder patch**. The original optional local diagnostics remain.
- No live connection to your private Kagami ERP was attempted during development. Tests here are offline/unit tests; verify the browser workflow yourself on your own authorized system.
