# Smart ERP QA 6.3.1 — Direct Leocem Run (navy and white)

The default dashboard has FOUR navigation entries: **Dashboard**, **Script Workspace**, **Test Cases & Excel**, and **Reports**. Previous backend functionality is retained but its advanced menus are hidden for the single-Leocem workflow.

## First installation on Windows

1. Keep your earlier Smart ERP folder as a backup. Extract this whole ZIP into a NEW directory. The installer is in the INNER `smart_erp_qa_v631` directory, not the outer ZIP extraction folder.
2. Stop any old Smart ERP application on port `8766` with Ctrl+C in the old PowerShell window. Do not stop unrecognized processes.
3. Open PowerShell in the inner project directory. Run `./Install-Windows.bat` (or `.\Install-Windows.bat` in PowerShell).
4. Edit the local `.env` file. Set `ERPQA_LEOCEM_TEST_URL` to your authorized **TEST/STAGING** Leocem login URL ending in `/leocem` and `ERPQA_LEOCEM_ENVIRONMENT=test` (or `staging`). The URL is not guessed; production is not supported.
5. No role passwords are required in `.env`. The saved Python script handles login using its own `login()` function. Edit this function in VS Code if needed.
6. Run `.\Start-Windows.bat` and open `http://127.0.0.1:8766`; refresh with Ctrl+Shift+R if an earlier dashboard is cached.
7. Click **Run Automation** on the dashboard. Confirm the reviewed file revision and TEST/STAGING URL. The trusted local script starts automatically in a NEW Chromium browser, logs into the authorized ERP, performs the configured PI -> approvals -> LPO -> approvals -> GRN flow, and writes live logs and evidence. There is **no ERP selector**.
8. Script Workspace provides Stop, reports, and failure evidence. Stopping does not roll back ERP records. Do not rerun failed transaction steps without checking their persistence in ERP first.

## VS Code edits: no upload required

Open `working_scripts/procurement/pi_lpo_grn.py` in VS Code and save with **Ctrl+S**. When you click **Run Automation** next time, the backend reads the new file, validates Python syntax, and requires you to confirm its newest SHA-256 digest. Changes made during an active run do not alter that run. For the included script, initial login and later role switching are automatic in this direct-run mode; browser-session reuse is not needed.

## What the dashboard reports

- Real Excel testcase counts and results are distinct from the script's structured checks.
- Approval/submit clicks without independent backend-status verification remain `Needs review`.
- Failure screenshot/trace collection is attempted; it may not succeed after browser failures.
- The supplied workflow is dependent: a failed PI/LPO stage blocks downstream GRN work. Individual independent Excel cases can run separately through Test Cases & Excel when mapped to approved executable assertions.

**Security:** The user has to explicitly confirm running this trusted local code in TEST/STAGING because it writes ERP records. Python code runs with the operating-system account's privileges and is not sandboxed. The API only accepts the fixed `procurement/pi_lpo_grn.py` file; AI-uploaded files are analysis-only. The authorized test/staging URL and environment remain in `.env`; login values come from the saved Python script. Never commit `.env`, browser profiles or evidence with ERP data to source control.

**Scope:** The UI and API can be tested locally without connecting to the real ERP. No live Leocem transactions, user logins, approvals or calculations have been verified here. Native Windows/Docker deployment still needs an actual laptop test.
