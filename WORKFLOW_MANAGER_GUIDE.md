# Smart ERP QA v6.1.8 — Manage Saved Workflows

## What changed

Inside **Workflows**, click **Manage Saved Workflows**. A project filter and table appear, listing every saved workflow with its project ID, name, step count, review status and last update. Each row has **Open** and **Remove**.

Removing a workflow requires typing `project_id/workflow_name` exactly. The backend moves its active JSON and any `*.negative_cases.json` or `*.v1-backup.json` companions into:

```
workflow_archive/<project_id>/<workflow_name>/<UTC-timestamp>_<random>/
```

The SQLite `workflows` index row is removed, so the workflow disappears from the dashboard and cannot be replayed until restored. Old execution rows and artifacts remain. The shared `projects/<id>/locators.json` file is kept to avoid invalidating other workflows.

Removal is rejected when the saved workflow is still referenced from an **Approval Plan** or **Business Flow**. Modify those definitions first. The delete endpoint is local-only and scoped to a specific registered ERP project.

## Upgrade existing installation from PowerShell

Stop the existing server first (Ctrl+C; answer Y if asked to terminate the job). Extract the downloaded full-project ZIP. From PowerShell, enter:

```powershell
$source = "$env:USERPROFILE\Downloads\Smart_ERP_QA_v618\smart_erp_qa_v618_full_windows"
$target = "C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
Test-Path "$target\run.py"
powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Windows.ps1" -TargetPath $target
Set-Location $target
.\.venv\Scripts\python.exe run.py
```

The `Test-Path` command must display `True`. If your existing folder differs, replace `$target` with the exact folder containing `run.py` and `.venv`. The upgrade copies only changed source files and missing backend Python modules, and backs up originals.

Then visit `http://127.0.0.1:8766`, press Ctrl+Shift+R, and open Workflows → Manage Saved Workflows.

## API

- `GET /api/workflows` — list active workflows (already existed).
- `GET /api/workflows?project_id=leocem_ba` — filter by ERP.
- `DELETE /api/workflows/{project_id}/{name}` — archive one workflow and remove its backend index.

Possible responses: 200 removed; 404 unknown workflow; 409 invalid identifiers or dependencies (Business Flows / Approval Plans). The HTTP API is reachable only on the local dashboard and enforces origin restrictions.

## Recovery

Stop the application, back up `data/erpqa.sqlite3`, and find the original JSON under `workflow_archive/...`. Recovery requires restoring the JSON to the matching `workflows/<project_id>/` and rebuilding the SQLite `workflows` row. There is no one-click Restore control yet, so keep the archive and request help before manually editing SQLite.

**This update does not fix automatically recorded locator mismatches.** Those should still be inspected and reviewed before replaying ERP transactions.
