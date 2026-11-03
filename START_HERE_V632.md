# Smart ERP QA v6.3.2: Start Here

**Leocem login comes from your saved Playwright script. No passwords are required in `.env` for this script.** The supplied login function uses the username as the password, matching the original code. If your authorized test passwords are different, edit `working_scripts/procurement/pi_lpo_grn.py` in VS Code.

For a fresh install, extract into a new folder, open PowerShell inside inner `smart_erp_qa_v632`, run `./Install-Windows.bat` then `./Start-Windows.bat`. You still need a correct, authorized TEST/STAGING Leocem URL and `ERPQA_LEOCEM_ENVIRONMENT=test` in your `.env` file. Production is blocked.

For an existing v6.3.0 or v6.3.1 installation: stop the old server first, then run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Upgrade-To-v632-Windows.ps1 -TargetPath "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
```

The upgrader creates a backup and preserves all other VS Code changes. It only transforms recognized legacy environment-based password blocks. Then run `Start-Windows.bat` from your existing target project, open `http://127.0.0.1:8766`, and refresh with Ctrl+Shift+R. Click **Run Automation**; review the saved revision and test target confirmation.

No ERP has been accessed or modified during packaging. See `README_LOGIN_FROM_SCRIPT_V632.md` for full details.
