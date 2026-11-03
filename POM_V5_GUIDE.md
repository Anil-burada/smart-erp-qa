# Smart ERP QA v5 — Reusable Page Object Model (POM)

This update preserves the v4 green/white dashboard, existing FastAPI app, recorder, JSON workflows, SQLite projects, native negative checks and local Ollama failure hints. **Use only an authorized TEST/STAGING ERP.** Production replay remains disabled.

## Windows upgrade — do not remove saved data

1. Close the running dashboard/backend using `Ctrl+C`.
2. In VS Code open the **inner folder containing `run.py`** (not a same-named parent folder).
3. Back up your original project folder. In particular, preserve `data/erpqa.sqlite3`, `projects/`, `workflows/` and `shared_workflows/` if present.
4. Download `smart_erp_pom_v5_patch.zip` and copy it into the folder with `run.py`.
5. From that folder:

```powershell
Test-Path .\run.py
Expand-Archive -Path '.\smart_erp_pom_v5_patch.zip' -DestinationPath '.' -Force
..\.venv\Scripts\python.exe -m pytest -v
..\.venv\Scripts\python.exe run.py
```

If the previous `.venv` is INSIDE the current folder rather than its parent, use `.\.venv\Scripts\python.exe` for both Python commands. If the environment does not exist, create one with `py -m venv .venv`, run `.\.venv\Scripts\python.exe -m pip install -r requirements.txt` and `.\.venv\Scripts\python.exe -m playwright install chromium`.

Open http://127.0.0.1:8766 and hard refresh using `Ctrl+Shift+R`.

The PATCH **does not contain a database or recorded ERP data**.

## What has changed

**New backend files:**
- `backend/pom.py`: generic BasePage + logical shared template engine; project-specific mapping and fingerprints.
- `backend/linked.py`: dependency preflight and same-login chain plan validation.

**Updated:**
- `backend/api.py`: Step N verification, POM template/mapping APIs, shared replay, safe negative checks, optional local AI candidate ranking, linked preview/run.
- `backend/browser.py`: explicit capture/assert actions, transaction ID outputs and fail-fast workflow runs.
- `backend/locator.py`: new language-neutral step actions (`capture_text`, `capture_value`, `assert_text`, `assert_value`, `assert_visible`).
- `backend/ai_assistant.py`: optional generic locator-*type* suggestion, without sending DOM/locators/ERP data to the model.
- `frontend/app.js`: step-specific validation and POM/linked controls on the existing Workflows page.

## First test — fix the previously blocked Step 4

1. Go to **ERP Projects** and **Open ERP** for the same registered project used to record `purchase_indent`.
2. Log in manually. Navigate to the **same page** where Step 4 was originally recorded.
3. In **Workflows**, load your `purchase_indent` workflow.
4. Under **Verify a specific recorded step**, enter `4`, click **Inspect Step** then **Check Candidate Locators**.
5. If a candidate matches the **correct** element, edit `locators.json` through **View/Edit Locator JSON** to use its stable selector (if necessary). Save your changes.
6. Click **Verify Intended Locator on Current Page** and confirm only when you actually inspected its meaning. Verification checks unique visibility but makes no click.
7. All other steps must also have `observed_count=1` before approval. Approve the complete workflow only after checking all steps and values.

**Important**: A locator with count=1 can still point at the WRONG business action. The UI cannot prove intent without your review. Do not set `observed_count=1` manually simply to bypass the check.

## Generate a shared Page Object Model

1. Once `purchase_indent` is fully reviewed and approved, open the **Shared Page Object Model (POM)** section of **Workflows**.
2. Enter a template name such as `purchase_indent`, then click **Create Shared POM from Reviewed Workflow**.
3. The system creates:

```text
shared_workflows/purchase_indent.json        <- portable business action sequence, NO CSS/URL
projects/leocem/module_maps/purchase_indent.json <- Leocem logical fields -> captured locator keys
projects/leocem/locators.json                <- actual Leocem selectors (already captured)
```

4. Choose the shared template and a registered ERP project. Click **Load POM Mapping**.
5. For a second ERP, map each logical field name to a locator key from **that ERP's own** `locators.json`, save the draft, and approve only after verifying it.
6. Click **Preview POM**. Only after the dry preflight passes and you explicitly authorize test transactions, click **Run Shared POM**.

Do not copy Leocem locators into another ERP. The shared template stays the same; each ERP maintains independent locator mappings. Even if two ERP URLs show identical pages, register each environment/project separately unless you've explicitly verified and scoped it.

## Editable shared template example

A template has logical names, not ERP-specific locators:

```json
{
  "schema_version": 1,
  "name": "purchase_indent",
  "start_suffix": "",
  "steps": [
    {"action":"click","field":"create_indent"},
    {"action":"fill","field":"indent_qty","value":"${quantity}"},
    {"action":"click","field":"save_indent"},
    {"action":"capture_text","field":"indent_transaction_number","output":"indent_number"},
    {"action":"assert_text","field":"indent_status","value":"SUBMITTED"}
  ]
}
```

This is an **illustration only**. The five fields must be present in each project's reviewed mapping and the actual expected status must come from your ERP rules. You can edit generated templates in the dashboard; edits require reapproval of each affected project mapping. The `indent_transaction_number` capture locator must actually identify the generated identifier on the page.

A project-specific mapping uses recorded locator **keys**, never pasted URLs from another ERP:

```json
{
  "schema_version": 1,
  "project_id": "leocem",
  "template_name": "purchase_indent",
  "fields": {
    "create_indent": "purchase_indent.step_001",
    "indent_qty": "purchase_indent.step_014",
    "save_indent": "purchase_indent.step_025",
    "indent_transaction_number": "purchase_indent.step_027",
    "indent_status": "purchase_indent.step_029"
  },
  "reviewed": false
}
```

**These step numbers are illustrative—not verified Leocem locator keys.** Save and Approve POM Mapping to calculate the required fingerprints after supplying real keys.

## Linked workflow test

Each stage needs a reviewed shared template and approved project mapping. The first stage must explicitly capture an output name (such as `indent_number`). Later templates may consume it via `${indent_number}`. The same principle applies to `lpo_number` and `grn_number`.

The **Linked procurement (experimental)** panel accepts a plan:

```json
{
  "project_id":"leocem",
  "stages":[
    {"template":"purchase_indent","role":"creator"},
    {"template":"lpo_creation","role":"creator"}
  ],
  "test_data":{"quantity":12},
  "allow_test_transactions":true
}
```

Select **Check Dependencies** first. If a required identifier is absent, a template or mapping is not reviewed, or the plan changes user roles, the preflight **blocks execution** before any action. The system supports running a valid same-login chain, stops on the first failure, and marks downstream stages as BLOCKED. **Creator → approver account switching is not automated yet.** Record and test each authorized role separately while this is being developed.

## Positive and negative checks

- Positive: `Run Shared POM` on the open authenticated browser. Browser actions and any explicit `assert_*` steps execute; real transaction creation/status is only verified when you add assertions.
- Negative: `Run Safe Native Negative Checks` on the currently open form. This tries values violating recorded `required`, `min`, `max`, etc., checks HTML validity and restores fields; it does not Save, Submit or Approve. Business-rule negative cases and server-side rejection are **not** implemented.
- PDF print comparison, stock controls, tax/amount calculations, role switching and full Indent → GRN reporting remain future stages, to be based on demonstrated UI and agreed expected rules.

## AI locator suggestions

`Check Candidate Locators` tests recorded locator candidates **with Playwright**. `Local AI Suggestion` optionally uses a locally installed Ollama model to select a candidate **type**, using only index, type, and action. It sends no raw selectors, DOM, screenshots, credentials, URLs, or ERP values and **never changes the locator**.

To enable local AI, install Ollama separately and run `ollama pull llama3.2`. Without Ollama, Playwright candidate checking works without AI. No auto-approval of Save, Submit or Approve is provided.

## Known limitations

- The screenshot you shared showed Step 4 needing review, but without the actual Leocem locator JSON we cannot accurately fix that selector automatically.
- Frontend/backend integration is designed for localhost. The Hugging Face Static version cannot execute this Python backend.
- Complex MUI dropdowns, date pickers, iframes, multi-tab actions, dynamically populated item lines, and login variations may need specialized handlers.
- PDF comparison and precise business-rule calculations are not included in this stage.
- Current UI and POM tests are automated. **Live Leocem browser replay has not been verified in this environment.** Test a short navigation-only workflow before any real transaction.
