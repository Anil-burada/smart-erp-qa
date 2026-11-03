# Smart ERP QA v6.2.1 Desktop — Windows guide

The new desktop app contains your existing Smart ERP dashboard plus an Electron `WebContentsView` Chromium ERP view. Manual login, workflow recording, saved JSON, and reviewed replay remain project-specific. In desktop mode Playwright attaches through the localhost Chrome DevTools Protocol (CDP), which is a beta integration and needs live Windows/ERP testing.

## On the CURRENT laptop (preserve work)

1. Stop FastAPI (`Ctrl+C`) and close any running Smart ERP Electron windows.
2. Extract `Smart_ERP_QA_v621_Desktop_Full_Windows.zip` into Downloads. Do **not** delete the existing project.
3. Open PowerShell in the **extracted** directory containing `Upgrade-Existing-Desktop-Windows.ps1`:

```powershell
$target = 'C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp'
Test-Path "$target\run.py"
powershell -NoProfile -ExecutionPolicy Bypass -File .\Upgrade-Existing-Desktop-Windows.ps1 -TargetPath $target
Set-Location $target
powershell -NoProfile -ExecutionPolicy Bypass -File .\Check-Desktop-Setup.ps1
```

If Node / Electron dependencies are missing, run (after installing Node.js LTS):

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Install-Desktop-Windows.ps1
```

Launch:

```powershell
.\Start-Desktop-Windows.bat
```

The Electron app starts FastAPI itself. Do not run a second `run.py` simultaneously. If port 8766 is already in use, stop the old server using its original PowerShell terminal and retry. Do not kill unknown processes.

## On a NEW Windows laptop

Install Python 3.11+ and Node.js LTS. Extract the ZIP, open its `smart_erp_qa_v621_desktop` folder, run `Install-Desktop-Windows.ps1` and `Start-Desktop-Windows.bat`. Reconfigure the `.env` locally. Python virtual environments and node_modules are intentionally not bundled. To migrate private ERP project data, carefully copy only your own `data`, `projects`, `workflows`, `approval_plans`, `flows`, and `artifacts` from a backup with both apps stopped.

## If the desktop fails again

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\Check-Desktop-Setup.ps1
```

Read `logs\desktop_backend.stdout.log` and `logs\desktop_backend.stderr.log` in the current project folder. Share the **first backend traceback**, not only the final Node `EPIPE` message. These logs may include URLs and technical metadata; remove passwords and tokens if any appear.

The FastAPI health URL is `http://127.0.0.1:8766/api/health`. Check this only while the app is actually running. Playwright is now *lazy*: the health endpoint can run without launching a Playwright driver. When an ERP browser action first starts, the worker initializes; failures surface as explicit errors.

## Safe smoke test

1. Launch desktop and open the built-in mock ERP, if configured.
2. Login manually (do not record credentials).
3. Click Start Teaching and make a harmless navigation-only workflow.
4. Finish and save JSON, review step locators and verify match count before approving.
5. Only after a clean replay, proceed with business transactions in TEST/STAGING. Do not auto-resume failed Save/Approve steps.

## Known limits

- Electron embeds Chromium, not branded Google Chrome.
- The debugger runs on localhost port 9337 and can inspect logged-in ERP content. Keep it local and shut down the app when unused.
- CDP attachment may differ from Playwright-launched Chromium; popups, embedded iframes, downloads and some rich ERP inputs need separate testing.
- This ZIP contains full project source, not a prebuilt EXE. Electron runtime installs through npm on Windows.
- Existing incorrect workflow locators are not changed or silently repaired.
