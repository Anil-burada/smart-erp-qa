# Smart ERP QA 6.3.2 - Leocem login from supplied Python script

Your Leocem one-click automation uses the original login logic inside `working_scripts/procurement/pi_lpo_grn.py`. **No DMG user passwords need to be entered in `.env` for this script.** The supplied code fills both username and password with the account ID; if these test accounts use different passwords, update the script's `login()` function in VS Code and save before running. Do not put real production credentials in your source or share the script publicly.

The Leocem *test/staging URL and environment* are still checked in `.env` (`ERPQA_LEOCEM_TEST_URL`, `ERPQA_LEOCEM_ENVIRONMENT`) so one-click automation cannot silently target production. Approval/review and source SHA-256 confirmation remain unchanged.

## Upgrade an existing v6.3.0 or v6.3.1 Windows installation

1. Stop old dashboard (Ctrl+C). Extract this ZIP to a NEW directory, then open PowerShell inside `smart_erp_qa_v632`.
2. Run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`.
3. Run `./Upgrade-To-v632-Windows.ps1 -TargetPath "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"` using your actual target root.
4. The upgrader backs up your existing `working_scripts` and edits **only the recognized legacy environment-password snippets**. Other script modifications are preserved. If login was customized in a way the updater cannot identify, the migration stops and asks for manual review.
5. Keep your already-approved `ERPQA_LEOCEM_TEST_URL` and `ERPQA_LEOCEM_ENVIRONMENT` settings. There is no need to add role-password settings.
6. Start the upgraded project with `./Start-Windows.bat` and reload the browser (`Ctrl+Shift+R`).

## Normal run

Open the local dashboard at http://127.0.0.1:8766, review the saved script and authorized test/staging URL, then click **Run Automation**. The latest saved VS Code script runs; no ERP picker and no `.env` role password prompts.

**Safety:** This flow CREATES, SUBMITS and APPROVES ERP records. Test only in an explicitly authorized non-production environment. Login, approval status and transactions have not been verified against your live ERP here.
