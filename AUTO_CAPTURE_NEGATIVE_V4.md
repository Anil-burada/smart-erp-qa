# Smart ERP QA v4 — Auto-Capture + Safe Negative Test Candidates

## What this update does

- Keeps the existing green-and-white FastAPI dashboard, project registry, and v3 login configuration.
- **Auto-capture starts when Open ERP opens a registered TEST or STAGING browser.** There is no Start Recording button to press. Finish the demonstration using **Finish Demonstration & Save JSON** in Workflows.
- Auto-capture **does not run on production**. When a visible password field is present, login-page interactions are not captured. Password fields and common secret-like inputs are excluded.
- Stores captured steps in `workflows/<project_id>/<workflow_name>.json` and locators in `projects/<project_id>/locators.json` as in v2.
- Adds native field constraint metadata (required, input type, numeric min/max, minlength) to locator JSON, when available.
- Adds **Generate Negative Cases** for native HTML-field constraints and **Run Safe Negative Checks (Current Form)**. It never clicks Save, Submit, or Approve during these checks.
- Does not modify or delete your `data/erpqa.sqlite3` database or previously recorded workflows.

## IMPORTANT: Known limitations

- **Capturing actions is not the same as understanding the business process.** Only supported HTML/DOM interactions are captured. ERP-specific MUI/React controls, Ctrl+Space shortcuts, iframes, editable grids, dialogs, role switches, print/PDF validation, and complex navigation may need extensions.
- The workflow still requires your **review/approval** before positive replay. A uniquely observed locator does not prove semantic correctness.
- The negative cases use **browser-native HTML validity checks only**. They do not verify server-side validation, accounting rules, quantities, statuses or authorization rules. A result of `PASSED` means an invalid value was rejected by `checkValidity()`, not that a complete ERP negative test passed.
- The safe negative runner operates only on the **current form page**. Navigate manually to the correct field before running these checks. It doesn't navigate, submit, approve, or post records.
- Input values for non-secret fields may be stored in workflow JSON. Use fake or approved synthetic test data. Review and redact the JSON before sharing.
- Automatic login is separate: edit `projects/<project_id>/login.json` (locators only); provide credentials at runtime for **Run From Login**. MFA/SSO may require manual login.
- Existing optional Ollama AI only provides generic **failure diagnosis**; it does not discover every business rule, generate full ERP scenarios, or execute unreviewed actions.

## Apply to your existing Windows project (no loss of registered projects)

1. Open VS Code in the inner folder containing `run.py`.
2. Stop the application using Ctrl+C.
3. Back up the whole folder, especially `data/erpqa.sqlite3`, `projects/`, `workflows/`, and your previous Python modules.
4. Put the v4 patch ZIP into the folder containing `run.py`.
5. From PowerShell **in the inner folder containing `run.py`**, run:

   ```powershell
   Test-Path .\run.py
   Expand-Archive -Path '.\smart_erp_auto_capture_negative_patch_v4.zip' -DestinationPath '.' -Force
   ..\.venv\Scripts\python.exe -m pytest -v
   ..\.venv\Scripts\python.exe run.py
   ```

   If the virtual environment is in a different folder, change the Python path accordingly. Do not create a new database or move folders.
6. Open `http://127.0.0.1:8766` and press Ctrl+Shift+R.

## First test (mock ERP, not Leocem)

1. In Registered ERP Projects choose the `mock_erp` project at `http://127.0.0.1:8766/mock/` (register it if needed).
2. Click **Open ERP**. Auto-capture starts for a TEST project (even before manual login); login-page input is ignored for security.
3. Log in using *dummy* credentials. In the mock ERP page click **Create New Indent**, select a Department, enter an Item and a Quantity of 2. **Do not Save.**
4. Return to **Workflows**, enter a unique workflow name, and click **Finish Demonstration & Save JSON**.
5. Inspect both new JSON files and the captured step list. Approve only if correct.
6. Click **Generate Negative Cases**. For the mock numeric Quantity field (`min="1"`), a proposed case should use `0`.
7. Keep the mock ERP browser on the same form and click **Run Safe Negative Checks (Current Form)**. A browser-native numeric `min` rejection may show `PASSED`; unsupported fields are reported explicitly.
8. For positive replay, return to the correct initial page and use the existing **Run Reviewed Workflow** with synthetic test data. Avoid Save/Submit initially.

## Safety and execution outcomes

- Positive replay works as in v3 and requires review/approval. Existing v3 automatic login is still available.
- Negative checks are best-effort non-submitting HTML constraint checks. `BLOCKED` and `NEEDS_RULES` are **not** passes.
- For real ERP negative scenarios (quantity exceeding stock, invalid vendor, role permissions, total calculations, and approval failures), add explicit business-rule configuration and assertions in the next phase. Never perform negative Submit/Approve on production.

## Test status

Unit and API tests can run on a machine with the project dependencies installed. The packaged build's graphical Playwright/ERP behavior has **not** been verified against your live Leocem ERP and must be tested locally in Windows using the mock ERP first.
