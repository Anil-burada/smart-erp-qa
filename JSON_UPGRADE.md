# Smart ERP QA — JSON-Driven Workflow Upgrade (v2)

This is an **incremental upgrade** of the working green-and-white **local** FastAPI + Playwright dashboard. It is **not** the Hugging Face Static version. Preserve your project database and already recorded workflows.

## What changes

- Projects remain in `data/erpqa.sqlite3` (existing project records preserved).
- The **new recorder** produces `projects/<project_id>/locators.json` (element mappings) and `workflows/<project_id>/<name>.json` (the ordered actions with target references).
- `backend/json_workflow.py` preflights project identity, locator references, fingerprints, and supplied runtime test variables before attempting replay.
- The UI lets you view/edit locator mappings. When a referenced mapping changes, the workflow's reviewed status is reset, and replay is blocked until the workflow is reviewed and updated.
- Legacy schema-v1 workflows **continue to run**. A **Convert to JSON Locators** button backs up a legacy workflow to `.v1-backup.json` and converts it to v2; you must review again.

## Update your existing project without losing saved ERP projects (Windows PowerShell)

1. Stop `run.py` with **Ctrl+C**. The server must be stopped while replacing files.
2. In VS Code open the **actual project folder that contains `run.py`**. Do not `cd` into a same-named folder again if you're already there.
3. Back up the database (only if it exists):

   ```powershell
   if (Test-Path 'data\erpqa.sqlite3') { Copy-Item 'data\erpqa.sqlite3' 'data\erpqa.before_v2.sqlite3' }
   ```

4. Download `smart_erp_json_runner_patch.zip` and copy it to your project root. Extract into the folder containing `run.py`, preserving directory structure and replacing files (`backend/api.py`, `backend/locator.py`, and `frontend/app.js`). This patch **does not contain** the database, so existing projects remain.

   ```powershell
   Expand-Archive -Path '.\smart_erp_json_runner_patch.zip' -DestinationPath '.' -Force
   ```

5. Start and test:

   ```powershell
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m pytest -v
   .\.venv\Scripts\python.exe run.py
   ```

6. In the browser open `http://127.0.0.1:8766`, then **Ctrl+Shift+R** to refresh the JS. Verify your previously registered ERP projects still appear in ERP Projects and at `/api/projects`.

## New installation (if no existing project data)

Extract the **complete** `smart_erp_json_runner_v2.zip` and open the inner folder with `run.py` in VS Code.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m playwright install chromium
.\.venv\Scripts\python.exe -m pytest -v
.\.venv\Scripts\python.exe run.py
```

## Try recording only in the local mock ERP first

1. Register `mock_erp` with URL `http://127.0.0.1:8766/mock/`, environment `test`, browser `chromium`.
2. ERP Projects → **Open ERP** → log in with dummy data. The Playwright window stays open.
3. Workflows → name `indent_smoke_01` → Start Recording. In the ERP window click **Create New Indent**, select **Stores**, type **Paper**, enter **2**. First test should **not press Save**.
4. Stop & Save → a v2 workflow and locator library are created.
5. Check the **workflow JSON and locator JSON**. Look for `target` keys like `indent_smoke_01.step_001` and the corresponding `locator` specs in `projects/mock_erp/locators.json`.
6. From workflow JSON editor, you may change an editable `fill` step value to `${quantity}` (no dollar escaping). Save workflow. In the run panel enter `{"quantity": 3}`. The Playwright engine will substitute the value *at runtime*, without changing stored workflow JSON.
7. For replay, navigate to the correct page in your authenticated mock ERP session as needed. Click Approve Reviewed Workflow, then Run Reviewed Workflow. Playwright rechecks locator uniqueness before each action.
8. After this works, you may record a **separate, authorized test** that includes Save. Confirm the write checkbox. Never run high-impact operations against production.

## Data format

`workflows/mock_erp/indent_smoke_01.json` example (abbreviated):

```json
{
  "schema_version": 2,
  "project_id": "mock_erp",
  "name": "indent_smoke_01",
  "start_url": "http://127.0.0.1:8766/mock/",
  "steps": [
    {"action": "click", "target": "indent_smoke_01.step_001", "observed_count": 1},
    {"action": "fill", "target": "indent_smoke_01.step_002", "value": "${quantity}", "observed_count": 1}
  ],
  "reviewed": false,
  "locator_fingerprint": "<computed automatically by recorder>"
}
```

`projects/mock_erp/locators.json` example (abbreviated):

```json
{
  "schema_version": 1,
  "project_id": "mock_erp",
  "fields": {
    "indent_smoke_01.step_001": {"locator":{"kind":"test_id","value":"create-indent"},"field_type":"button","required":false,"selection_mode":"fixed","observed_count":1},
    "indent_smoke_01.step_002": {"locator":{"kind":"test_id","value":"quantity"},"field_type":"text","required":false,"selection_mode":"fixed","observed_count":1}
  }
}
```

These examples are illustrative and **not executable exactly as shown** because the fingerprint is generated automatically and the steps are incomplete.

## Known limitations

- Phase 2 recorder captures a limited set of DOM events. Custom ERP grids, complex MUI dropdowns, iframe interactions, new tabs, dialogs, and downloads are not guaranteed to work and need explicit handlers.
- Saving a workflow does not establish an end-to-end business assertion. No automatic Indent-to-GRN chaining, multi-role login automation, exact PDF verification, AI locator recovery or round-robin data rotation yet.
- No password handling in recorder or runtime JSON. Enter credentials manually in the ERP browser; do **not** put passwords, cookies, payment data or other sensitive information into workflow or locator files.
- A locator observed as unique during recording is not necessarily correct later. The runner always rechecks uniqueness, but business-semantic correctness still needs review.
- Uploaded test data, traces, screenshots and locator mappings may contain business information. They stay local; keep out of Git, encrypt or protect working directories as appropriate.
- Local-only backend at 127.0.0.1; do not expose to the public network or upload these Python backend files to a Hugging Face Static Space.
- Graphical browser navigation could not be tested inside the build environment (blocked by administrator). Run the included mock ERP browser smoke test on your own Windows computer before using a real ERP.
