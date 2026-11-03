# Smart ERP QA v6.3.1 - Start here

## New Windows laptop / new installation

Extract the ZIP. Open the **inner `smart_erp_qa_v631` project folder** containing `Install-Windows.bat`. Run that installer first, then edit `.env`, then `Start-Windows.bat`.

You MUST configure:

```
ERPQA_LEOCEM_TEST_URL=https://YOUR-AUTHORIZED-TEST-HOST.kagamierp.com/leocem
ERPQA_LEOCEM_ENVIRONMENT=test
ERPQA_KAGAMI_DMG0013_PASSWORD=YOUR_LOCAL_TEST_PASSWORD
ERPQA_KAGAMI_DMG0041_PASSWORD=YOUR_LOCAL_TEST_PASSWORD
ERPQA_KAGAMI_DMG0051_PASSWORD=YOUR_LOCAL_TEST_PASSWORD
ERPQA_KAGAMI_DMG0052_PASSWORD=YOUR_LOCAL_TEST_PASSWORD
```

Never paste passwords into chat or commit `.env`. The URL above is a PLACEHOLDER, not a known working address. Use an authorized actual TEST/STAGING Leocem URL. The dashboard refuses to run until this is configured.

Stop any older Smart ERP service on port 8766 first. Visit http://127.0.0.1:8766, then click **Run Automation**, review the confirmation, and follow logs in **Script Workspace**. No ERP selector and no manual login are needed for this new-browser mode: the script logs in and rotates the configured test users.

## Existing v6.3.0 installation (keep your saved VS Code script)

1. Stop your current Smart ERP window (`Ctrl+C`) and check port 8766 is free.
2. Extract this new ZIP into a different folder. In PowerShell from the NEW project root, run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Upgrade-To-v631-Windows.ps1 -TargetPath "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
```

3. The upgrade backs up your existing files, leaves your current `.env`, database, reports, and `working_scripts` untouched, and updates the backend/frontend code. Add the two new `ERPQA_LEOCEM_*` entries to your existing `.env` and set them correctly.
4. Start your upgraded project with `Start-Windows.bat` and hard refresh (`Ctrl+Shift+R`).

**This is an explicit test/staging transaction launcher, not a read-only dry run.** See `README_LEOCEM_DIRECT_RUN.md` for behavior, safety, and reporting limitations.
