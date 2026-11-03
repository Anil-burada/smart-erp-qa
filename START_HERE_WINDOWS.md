# Smart ERP QA v6.1 — Full Project (Windows)

## What is delivered

- Your original green-and-white frontend, FastAPI backend, SQLite project registry, project-scoped locator JSON, browser capture, pause/resume/save, Python code export, review/replay and existing reporting.
- A new **Approval Plans** dashboard tab for project-specific, differently ordered workflows.
- Safe multi-account handoff with configured logout, login locators and runtime `.env` credentials.
- Captured ID passing between stages (`pi_number`, `lpo_number`, `grn_number`) through `${pi_number}`, etc.
- A harmless **local mock ERP** with a full Indent → manager approval → PO → GM approval → GRN demo.
- Example workflow plans for `kagami_ba`, `erp_two`, `erp_three` (examples not runnable until their workflows are recorded/reviewed).
- Optional positive/negative **test IDEAS** from offline rules, local Ollama or OpenAI. Suggestions never execute automatically.
- Your original full Kagami PI → LPO → GRN script in `legacy/kagami_indent_to_grn_reference.py` as a **standalone reference**, not part of the generic approval runner. It keeps exact field IDs, PGST validation, print PDF checks and the original approver sequence, but its main function is disabled by default and its login now requires a local secret for each account.

## First run — SAFE local demo

1. Extract the **complete project ZIP** into a **new empty folder** on Windows. Do not delete your old Smart ERP project or overwrite its database.
2. Open PowerShell in the extracted folder (the one containing `run.py`).
3. Create the Python virtual environment and install dependencies:

   ```powershell
   py -3 -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt
   .\.venv\Scripts\python.exe -m playwright install chromium
   ```

4. Copy the configuration template. All included mock values are **fake**, and the mock accepts any non-empty credentials:

   ```powershell
   Copy-Item .env.example .env
   ```

   The example file has empty passwords for Kagami. **Do not fill these with real passwords until you are working in an authorized TEST/STAGING environment.** Never upload `.env` to ChatGPT, GitHub or email.

5. Seed or repair the harmless demonstration (does not overwrite existing workflows):

   ```powershell
   .\.venv\Scripts\python.exe scripts\seed_mock_demo.py
   .\.venv\Scripts\python.exe -m pytest -q
   .\.venv\Scripts\python.exe run.py
   ```

6. Open **http://127.0.0.1:8766** in your normal browser.
7. Go to **Browser Session** → select **Demo Procurement ERP** / `mock_erp` → **Open ERP Application**. **Leave the mock login screen visible**. The approval-plan runner will do the fake account logins for you.
8. Go to **Approval Plans** → select `mock_erp / demo_indent_to_grn` → **Load Plan**. Click **Validate Plan**. The preflight should say **READY** with 5 stages. Check **I confirm authorized test/staging...**, then **Run Reviewed Approval Plan**.
9. Inspect stage results, the returned `pi_number`, `lpo_number` and `grn_number`, and the recent-execution table. All records are browser-local demo objects; nothing is sent to Kagami or another external ERP.

**Note:** When running on a remote Linux or container host, the browser opens on that host, not on your Windows desktop. This project is one local tester session; Team/server multi-user isolation is not yet implemented.

## How to run your real Kagami scenario

1. Register a new ERP project, e.g. `kagami_ba`, using your authorized test/staging Kagami URL. Don't register a production URL as test.
2. Open the ERP browser and log in **directly inside the ERP page** to record each workflow; use **Start Fresh Recording** after login to discard login interactions.
3. Break Indent → GRN into named stages, e.g. `pi_create_submit`, `pi_approval_creator`, `pi_approval_manager`, `pi_approval_final`, `lpo_create`, `lpo_submit`, `lpo_approval_manager`, `lpo_approval_creator`, `lpo_approval_final`, `lpo_approval_last`, `grn_create`, `grn_submit`, and `logout`.
4. Add explicit verification steps after the important submit/approval/create actions. A click alone does **not** prove ERP status changed. Use the workflow JSON editor for `assert_text`/`assert_value`/`assert_visible`, or insert `capture_text`/`capture_value` for IDs. Review and approve each workflow.
5. The included plan `approval_plans/kagami_ba/indent_to_grn.json` is an editable starting point. The original source sequence has **3 PI approvals and 4 LPO approvals**. For another ERP, edit the order, role aliases, and recorded workflow names separately.
6. Configure that ERP's login selectors under **Browser Session**. The success locator must uniquely appear after login.
7. Set **TEST credentials** for the required role aliases in `.env` (see `.env.example`). Don't enter usernames or passwords in the plan JSON.
8. Open the correct ERP and **start at its login screen**, then execute the reviewed plan. The runner switches accounts using the reviewed logout workflow, ensures the login page is visible, logs in as the configured next role, runs the stage and stops on first error.

### Passing one transaction to the next stage

A recorded workflow's JSON can include a step such as:

```json
{"action":"capture_text","locator":{"kind":"css","value":"[data-testid=\"pi-number\"]"},"output":"pi_number","observed_count":1}
```

In a later stage, a field value can reference exactly that captured runtime result:

```json
{"action":"fill","locator":{"kind":"css","value":"#related-pi"},"value":"${pi_number}","observed_count":1}
```

**Replace these example locators with real observed ERP locators.** Never assume the ID format or substitute a different record. Use explicit assertions after selections.

### Automatic approval rules

- All configured approval stages must include an assertion **after** the final mutating action.
- All stages and the logout workflow must be reviewed. If the project has changed its locator mappings, it must be reapproved.
- A missing runtime variable, account secret or workflow blocks the plan **before its first write** wherever the missing item can be detected. A failed live lookup stops the sequence; never blindly retry Save/Approve/Submit.
- There is no generic way for Playwright to infer your ERP's business approval policy. The plan config comes from the tester, and you must verify that its approval audit/status is the expected one.

## How the same script supports ERP 2 and ERP 3

ERP 1/2/3 all call `backend/browser.py` and `backend/approval_plans.py`. Each has its own project URL, saved workflows, locator mappings, optional login selectors and `approval_plans/<project_id>/<name>.json`. For example ERP 2 may have Manager → GM approval while ERP 3 has HOD → Finance → Director. They can both replay through the same engine **after** those project-specific actions have been recorded and verified.

## Optional AI ideas

- **Offline rules**: no model/server needed. Provides basic positive/negative test ideas.
- **Local Ollama**: install and start Ollama locally, select **Ollama** in Approval Plans and supply a model that's already installed (or leave default `llama3.2`).
- **OpenAI**: put `OPENAI_API_KEY=...` into `.env` on your own machine, select **OpenAI API** and confirm the opt-in. The app sends only sanitized action types and HTML-type/constraint metadata; not page URLs, full DOM, recorded values, screenshots, credentials, or locator selectors. API usage may be billed separately.
- **AI suggestions are not executable tests**. Review them, define actual business rules and implement explicit safe assertions. Existing native negative-case executor continues to support verified HTML constraints.

## Important limitations and verification

- The 70 offline tests for this ZIP passed in the authoring environment, and the bundled mock UI's Indent → approved PI → PO → approved PO → GRN actions worked in a Chromium **in-memory UI test**. A full HTTP browser integration run was blocked by this environment's Chromium localhost policy. The actual live Kagami workflow was **not executed or verified**.
- The Kagami legacy original script runs separately if you explicitly permit it; it is not yet split into 12 generic reviewed recorded workflows. This conversion needs you to record or verify their real pages/locators.
- Business calculation checks, round-robin dropdown selection and actual generated PDF validation remain in the Kagami legacy script, not in the generic JSON runner. The generic runner supports user-authored assertions and basic native negative tests, not inferred ERP calculations.
- The local dashboard implements one browser session; **multi-tester shared-server Team Edition**, production execution, protected secrets vault, sophisticated branching/parallel approvals, and fully automated AI-generated negative business tests are not part of this delivered version.
- Avoid actual production approval/write actions unless separately authorized and designed with audit controls. Always back up your original working project first.

## Project structure

```text
backend/
  api.py                 FastAPI endpoints
  browser.py             Shared Playwright browser/record/replay/plan runner
  approval_plans.py      Plan schema, preflight, account mapping
  ai_case_proposals.py   Offline/Ollama/OpenAI test-idea suggestions
  record_js.py           Integrated browser locator/action recorder
  json_workflow.py       Workflow JSON, captured variables and locator resolution
  ...                    Existing POM, reports and other features
frontend/
  index.html, app.js, styles.css
approval_plans/
  kagami_ba/indent_to_grn.json
  erp_two/indent_to_grn.json
  erp_three/indent_to_grn.json
  mock_erp/demo_indent_to_grn.json
projects/                ERP-specific locator libraries + login selectors
workflows/               ERP-specific recorded workflow JSON
legacy/                  Your original complete Kagami PI -> LPO -> GRN Python script
scripts/seed_mock_demo.py
.env.example             Fake demo credentials + empty Kagami password slots
run.py                   Start localhost dashboard
```

## Troubleshooting

- **`127.0.0.1 refused to connect`:** ensure `python run.py` is running, and port 8766 is free. Use `Test-NetConnection 127.0.0.1 -Port 8766` on Windows.
- **Missing browser executable:** run `python -m playwright install chromium` using the project venv.
- **Preflight NOT READY:** inspect the Approval Plans checklist, record/review missing stages and update locator mappings. Demo preflight should be READY after seeding.
- **Account-switch failed:** verify `logout` workflow includes a login-screen assertion, configured login selectors are valid, and aliases have test credentials in `.env`.
- **Missing amount/print checks in the generic runner:** they have not been converted from the Kagami-specific script yet. Review the legacy code to create explicit field/business-rule validators.
- **Production project blocked:** intentional; production automation is disabled in the local training framework.
