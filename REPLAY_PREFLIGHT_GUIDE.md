# v6.1.5 - Replay Start Diagnostic (read-only)

## Why this feature exists

A recording can fail even if its saved URL is the same as the current URL. Many ERPs are single-page applications; the same URL can display different modules, tabs, menus or dialogs. Example: a `purchase_indent` recording asks for the `+ Purchase Order` button on step 1; that button may be on a different screen or a different workflow may have been recorded.

## Safe workflow

1. Open the **correct registered ERP project** from Browser Session and log in manually.
2. In Workflows, load the exact reviewed workflow and check the first recorded action's text and context.
3. Click **Diagnose Replay Start (No Clicks)** before replay. It will show current URL, recorded first-step URL, locator matches, visibility, and visible button/link labels.
4. If Step 1 is NOT READY, navigate manually to the required screen, then diagnose again. If the actual first step belongs to another business stage (e.g., a PO button in an indent workflow), re-record the correct stage from a consistent known starting screen instead of renaming the wrong element.
5. If the locator is incorrect, use View/Edit Locator JSON. Test the intended locator on the page, save, re-review and approve. Do not replace a locator with one that points to a different action just to make a test pass.
6. Use Business Flows to chain separate reviewed Indent, PO and GRN stage workflows with explicit business assertions and document-ID capture.

Preflight is read-only. It never clicks controls, changes workflow locators, reloads ERP pages, logs in or executes transactions. It checks **only the first step**, not overall workflow correctness or business rules. Visible controls are suggestions for manual inspection, not auto-repairs; only main-document controls are shown.

## PowerShell upgrade, existing v6.1.4 installation

Stop the dashboard (Ctrl+C or `Terminate batch job? Y`), then from the **extracted v6.1.5 source** folder run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Upgrade-Existing-Windows.ps1 -TargetPath 'C:\Users\Nikitha\Downloads\Smart_ERP_QA_v6.1.3_Full_Windows_Deployment\smart_erp_qa_v613_full_windows'
```

Restart from your existing target folder:

```powershell
cd 'C:\Users\Nikitha\Downloads\Smart_ERP_QA_v6.1.3_Full_Windows_Deployment\smart_erp_qa_v613_full_windows'
.\.venv\Scripts\python.exe run.py
```

Press Ctrl+Shift+R in the dashboard. Read-only endpoint: `GET /api/workflows/{project_id}/{name}/preflight-first`.

## Safety and limits

Use test/staging data only. No automatic selector substitutions or transaction retries. Never put ERP passwords in workflow JSON. Manual login is not proof of permissions; approval/submission workflow stages still require explicit validation.
