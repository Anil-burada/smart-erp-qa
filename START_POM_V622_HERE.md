# Smart ERP QA v6.2.2 — Complete Windows Project

**What is new:** The Workflows page now exports an approved recording as a downloadable **Python Page Object Model + pytest ZIP**. It uses real saved locator JSON and the recorded click/field sequence.

## Upgrade the current Smart ERP installation (recommended)

1. Back up your existing Smart ERP QA project, especially `.env`, `data`, `projects`, `workflows`, and `approval_plans`.
2. Stop the dashboard/Electron application; make sure port 8766 is not occupied.
3. Extract this ZIP. Open a PowerShell terminal in `smart_erp_qa_v622_desktop` (this folder).
4. Run (edit the target path if your copy is elsewhere):

```powershell
$target = 'C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp'
Test-Path "$target\run.py"
powershell -NoProfile -ExecutionPolicy Bypass -File '.\Upgrade-Existing-POM-Windows.ps1' -TargetPath $target
```

5. Run the usual desktop launcher in the **existing** project folder:

```powershell
Set-Location $target
.\Start-Desktop-Windows.bat
```

The upgrade script copies only relevant code/UI files and missing backend Python modules. It backs up replaced code and does **not** delete your recorded workflows, ERP projects, SQLite DB, `.env`, or approval plans.

## New laptop (fresh installation)

Extract the ZIP, open the `smart_erp_qa_v622_desktop` folder and run:

```powershell
.\Install-Windows.bat
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Desktop-Windows.ps1
.\Start-Desktop-Windows.bat
```

Requires installed Python, Node.js LTS, and Internet access during dependency installation. Your current laptop's saved ERP data is not included automatically; back it up and copy it separately.

## Use the POM generator

**ERP Projects → Open ERP → manual login → Workflows → Start Teaching ERP → demonstrate actions → Finish & Save JSON → Review and approve → Generate POM Python + pytest (ZIP).**

For **live execution from the dashboard**, select the approved workflow and use **Replay Approved JSON with Playwright (already logged in)**. Use **Run Safe Negative Checks** separately for native HTML form checks. The dashboard Overview shows run results.

See `POM_GENERATOR_GUIDE.md` and the README inside the generated workflow-specific POM ZIP.

**Important:** A passing click sequence does not prove PI, PO or GRN business correctness unless you recorded actual assertions; use approved business checks, test-only accounts and test/staging data.
