# Smart ERP QA v3 — JSON replay from login + optional local AI

This is a **patch for your working v2 local backend**. It does not replace your green-and-white dashboard or change your SQLite project registry. **Do not upload it to a Hugging Face Static Space.**

## 1. Files changed

- **Replace** `backend/api.py` — new login-config, auto-run, AI endpoints
- **Replace** `backend/browser.py` — verified login operation in the dedicated Playwright worker
- **Replace** `frontend/app.js` — UI to configure login locators and run from login; AI hints
- **Add** `backend/auth_config.py` — project-specific `login.json` loader/validation
- **Add** `backend/ai_assistant.py` — optional privacy-minimized local Ollama diagnosis
- **Add** `tests/test_auto_login_ai_v3.py` — new tests
- **Add** this guide

**Do not replace** `run.py`, the database in `data/`, your existing `workflows/`, your `projects/*/locators.json`, `frontend/index.html`, or `frontend/styles.css`.

## 2. Install patch in VS Code on Windows

1. Press **Ctrl+C** in the server terminal to stop `run.py`.
2. Open the **inner** project folder **containing `run.py`**. Run `Test-Path .\run.py` and confirm it says `True`.
3. Back up SQLite and your previous code. In PowerShell, from the folder containing `run.py`:

   ```powershell
   if (Test-Path .\data\erpqa.sqlite3) { Copy-Item .\data\erpqa.sqlite3 .\data\erpqa.before_v3.sqlite3 }
   Copy-Item .\backend\api.py .\backend\api.before_v3.py
   Copy-Item .\backend\browser.py .\backend\browser.before_v3.py
   Copy-Item .\frontend\app.js .\frontend\app.before_v3.js
   ```

4. Copy `smart_erp_autologin_ai_patch.zip` into that same inner folder. Extract:

   ```powershell
   Expand-Archive -Path '.\smart_erp_autologin_ai_patch.zip' -DestinationPath '.' -Force
   ```

5. With your existing virtual environment activated, run:

   ```powershell
   python -m pip install -r requirements.txt
   python -m pytest -v
   python run.py
   ```

   If `python` points at the wrong interpreter, use your virtual environment's Python executable instead (`..\.venv\Scripts\python.exe` or `..\venv\Scripts\python.exe`, depending on your folder).

6. In Chrome open `http://127.0.0.1:8766`, then press **Ctrl+Shift+R**.
7. Confirm your saved ERP projects are still listed. Existing workflows remain untouched.
8. To keep internal locator details out of Git, add `projects/*/login.json` to `.gitignore`.

## 3. Where JSON files are saved

After **Workflows → Start Recording → Stop & Save** (start recording *after* manual login), v2/v3 saves:

```text
projects/<project_id>/locators.json
workflows/<project_id>/<workflow_name>.json
```

No manual copying of those files is necessary. The JSON workflow keeps step order and input values or `${variable}` test-data references. The locator library holds selectors. Each ERP has its own isolated files.

The login configuration is a **separate** file:

```text
projects/<project_id>/login.json
```

This contains the username/password **element locators**, the login button locator and a post-login success locator. It never contains the actual username or password. Do not paste any credentials into these JSON files.

## 4. One-time login setup

1. Open **Browser Session** in the green-and-white dashboard.
2. Choose the registered project.
3. Select **Load Login Locator JSON**. If no file exists, you'll see sample locators for the bundled mock ERP (not necessarily your ERP).
4. Inspect your real login page and replace those four selectors. Also keep `project_id` and `project_url` matched to the registered project.
5. Click **Save Login Locator JSON**.
6. While an ERP browser is open at the **login page**, choose **Test 3 Login Locators**. All three (username, password, submit) should be unique and visible. The **success** selector is verified after login.

For the bundled **Mock ERP**, the starter config is correct:

```json
{
  "schema_version": 1,
  "project_id": "mock_erp",
  "project_url": "http://127.0.0.1:8766/mock",
  "username": {"kind": "css", "value": "#username"},
  "password": {"kind": "css", "value": "#password"},
  "submit": {"kind": "css", "value": "#loginBtn"},
  "success": {"kind": "css", "value": "#dashboard"}
}
```

> The framework normalizes trailing slashes when registering URLs. Use the dashboard-generated `project_url` value rather than copying the mock sample URL if it differs.

For **Leocem**, `#username`, `#password` and a link labeled `LOGIN` were previously observed, but they must be validated on the **current** login page. The post-login success marker must be configured and verified too.

## 5. Replay from login to recorded workflow

1. Open **Workflows** and select a saved workflow (e.g. `purchase_indent_smoke`).
2. Review and approve the recorded steps and all test data. Use TEST/STAGING only.
3. In **Run from Login → ERP workflow**, enter **test username** and **test password**. These values are sent to the loopback API for this invocation and are not written to SQLite, workflow JSON or login JSON. They can be visible in local browser developer tools/network debugging, so use approved test accounts only.
4. If your flow writes records, explicitly check the TEST transaction box. Don't do this for your first smoke test.
5. Click **Run From Login (New Browser)**.
6. The backend opens a fresh Playwright browser on the registered ERP URL, verifies login using the configured success selector, then executes the approved JSON steps.
7. A step failure stops replay; it does not auto-retry a Save/Submit/Approve.

If login uses MFA, CAPTCHA, federated identity, custom controls, or an extra role selection, use **manual login → Run Reviewed Workflow** until that flow is configured safely. This version supports **one login identity per run**; role switching and indent/LPO/GRN variable linking remain future work.

## 6. Optional AI diagnosis (no API key)

The core recorder/replay **does not require AI**. If you want suggestions for a failed run:

1. Install the **Ollama Windows application** from `https://ollama.com/download`.
2. In a terminal run `ollama pull llama3.2` (you may choose another installed model by setting `ERPQA_OLLAMA_MODEL`).
3. Make sure Ollama is running locally at `127.0.0.1:11434`.
4. In Workflows, click **AI Analyze Latest Failure**.
5. Read the suggestion and manually inspect the actual ERP. AI does **not** change locators or click buttons.

Only the failure reason category, step index, and action type go to Ollama. No ERP DOM, URLs, screenshots, locator strings or input values are sent.

If Ollama isn't installed/running, this button shows a clear error; all other automation still works.

## 7. What is NOT built yet

- AI locator repair/replacement or business rule inference
- Multi-role approval/session orchestration
- Capture/pass indent, LPO, and GRN generated numbers between workflows
- Round-robin selection for custom dropdowns
- Reliable coverage of iframes, dynamic ERP grids, dialogs and popups
- ERP record-creation/status/calculation assertions and exact PDF comparison
- Persistent unattended login for MFA flows

**A recorded click is not proof that a transaction succeeded.** Add assertions and business-rule configuration before treating procurement workflows as complete.

## 8. Troubleshooting

- `Test-Path .\run.py` says False: you are in the wrong folder. Open the *inner* project folder containing `run.py`.
- `ModuleNotFoundError`: activate the virtual environment or run with its Python executable.
- `Login configuration ... mismatch`: your registered URL changed; load and recheck the login config.
- Login not verified: inspect username/password/submit selectors, post-login success selector, and MFA/SSO requirements.
- AI unavailable: confirm Ollama is installed, started and the model is pulled. AI is optional.
- JSON saved but replay fails: inspect the recorded action order, locator uniqueness, and target page state. Do not automatically retry critical actions.
- Already recorded projects are missing: confirm you're opening the same inner folder and `data/erpqa.sqlite3` database as before.

**Testing:** The packaged source passes unit/API tests. A Chromium mock login DOM test also passed in the build environment. End-to-end real ERP login/recording/replay has not been verified on your Windows computer.
