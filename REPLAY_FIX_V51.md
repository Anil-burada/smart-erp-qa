# Smart ERP QA - Replay/Auto-login Locator Fix v5.1

This is a **targeted update of POM v5**. It does NOT implement verified Leocem-to-GRN business rules, multi-account role switching, or automatic AI repairs.

## What was wrong

`backend/browser.py` previously navigated to `workflow['start_url']` immediately before replay. This could send a logged-in user back to `/login` or a page with no matching `Procurement` button. The original failure `Locator matched 0 elements` is therefore insufficient to declare the locator invalid.

## What is fixed

1. `Run Reviewed Workflow (already logged in)` **does not navigate** away from your current authenticated page. **You must position the browser on the page containing the first recorded action.** The registered project URL is still checked for scope. If a password input is visible, replay refuses to proceed.
2. The locator checker waits up to 12 seconds for an element to become visible; ambiguous matches fail immediately. Test fakes that have no `.first` continue to work.
3. Opening an authorized test/staging ERP automatically **inspects the login screen for unique selectors**. If it recognizes username, password and submit fields, only the selector metadata is saved in `projects/<id>/login_candidates.json`. The field VALUES and passwords are NEVER read or stored. On the Browser Session dashboard, click **Use Auto-Captured Login Selectors** to fill the login JSON editor.
4. **Login configuration still requires a verified `success` locator** which is visible after login and not before login. Then click Save Login Locator JSON, open a login screen, and Test 3 Login Locators. Only then use Run From Login.
5. Replay runs **only the recorded steps**, in order, and stops on the last recorded step or first failure. Auto-capture records only supported browser interactions; review for missing steps, especially custom dropdowns, global shortcuts, date pickers, grids, popups and print views.

## Install on Windows - update existing v5 project

1. Stop `run.py` (Ctrl+C). Make a backup of the complete working project folder and database.
2. Open VS Code terminal in the **folder containing `run.py`**, not the patch folder:

   ```powershell
   Test-Path .\run.py
   ```

   Must print `True`.
3. Download `smart_erp_replay_fix_v51_patch.zip` into Downloads and run:

   ```powershell
   Expand-Archive -Path "$env:USERPROFILE\Downloads\smart_erp_replay_fix_v51_patch.zip" -DestinationPath "." -Force
   ```

4. Use the Python environment that already works in this project (the sample below assumes `.venv` is inside the folder):

   ```powershell
   .\.venv\Scripts\python.exe -m pytest -v
   .\.venv\Scripts\python.exe run.py
   ```

   If `.venv` is one folder above, use `..\.venv\Scripts\python.exe` instead.
5. Open `http://127.0.0.1:8766`, Ctrl+Shift+R, then Browser Session.

## Smoke test without creating a transaction

1. Open the included mock ERP in the Playwright browser; log in manually.
2. Demonstrate ONLY navigation and field entry in an authorized test form; **do not Save/Submit/Approve**. Auto-capture is active for test/staging.
3. Finish Demonstration & Save JSON, inspect the generated locator and workflow JSON, approve when correct.
4. Navigate the same logged-in Playwright browser to the **page where the FIRST recorded step exists** (do not replay from the wrong page).
5. Click Run Reviewed Workflow. It executes only those recorded actions. Check results, including actual field values, not just action completion.

## Automatic login setup

- Click Open ERP in a test/staging project. Before leaving the login screen, the framework attempts to capture selector suggestions. In Browser Session click **Use Auto-Captured Login Selectors**.
- If detection fails, your login form uses unsupported or ambiguous controls; use **Load Login Locator JSON**, then configure locators manually based on your real UI.
- Configure and verify the post-login `success` locator yourself. For example, if your verified success marker is the main ERP sidebar, set its unique selector here. Do not assume it exists on every project.
- Save and test login selectors while on the login page. For a reviewed workflow, choose **Run From Login (New Browser)**, enter credentials for this run, and execute only against approved TEST/STAGING.

## Moving to new ERP projects

The shared `backend/pom.py` supports shared business templates plus individual ERP field/locator maps. Each new ERP project needs its own registered URL, approved locators, login success marker, required data and business rules. The same templates are reusable **where the actual process matches**. Production write automation remains disabled.

## Still pending and not safe to infer from click capture alone

- ERP business validation (expected approval status, calculations, GRN quantities, exact PDF fields).
- Secure multi-role approval chain with separate authorized test credentials.
- Cross-workflow generated-number capture for Indent/LPO/GRN, unless explicitly configured and verified.
- AI locator repair. Existing local AI can suggest diagnostics; no silently replaced locators.
- Browser navigation under multi-tab/iframe MUI custom controls needs specialized handlers.

To integrate your known-working complete login -> Indent -> Approval -> LPO -> Approval -> GRN code, share the code with credentials redacted and the generated locator/workflow JSONs. The framework can then be adapted to those real application-specific steps rather than guessed selectors.
