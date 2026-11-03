# Smart ERP QA v6.2.2 — Recorded workflow to Python POM

This is a **code generator from approved recorder data**, not an AI-guessed business flow.

## Workflow in the dashboard

1. **ERP Projects** > Open ERP (desktop Chromium preferred). Log in manually. Avoid credentials in recordings.
2. **Workflows** > Start Teaching ERP. Demonstrate the process in the real application.
3. Finish Demonstration & Save JSON. This creates a workflow and project-specific locator JSON.
4. Load the saved workflow, review all clicks, values, selectors, and step order. Test unique locators and approve it.
5. Under **Generate Page Object Model automation**, click **Generate POM Python + pytest (ZIP)**. A ZIP will download in your browser/desktop downloads location.
6. The ZIP includes `pages/base_page.py`, generated `pages/erp_pages.py`, `workflows/<name>.py`, `tests/`, a locator snapshot, candidate negative cases, and a README.
7. To **execute and report directly in the dashboard**, use the existing **Replay Approved JSON with Playwright** action and the **Run Safe Negative Checks** action on the right test form. The Overview dashboard shows built-in execution results.

## Running generated pytest POM (advanced)

- The generated ZIP has its own README with environment variables and pytest commands.
- Open and manually log into the exact project in Electron desktop before connecting pytest over CDP. Connect to `http://127.0.0.1:9337` by default. Do not leave duplicate tabs on the same project URL.
- Run the offline `tests/test_structure.py` first, then opt in to positive replay with `SMART_ERP_TEST_RUN=1`. Approve write actions only in a test/staging ERP (`SMART_ERP_ALLOW_WRITES=1`).
- Run native-form negative checks separately, with the correct form open and `SMART_ERP_NEGATIVE=1`. No Save/Submit/Approve actions are performed by negative tests; HTML constraints are not ERP business rules.
- pytest JUnit reports generated here remain with the exported package. The dashboard's reporting counters are based on its backend execution history, not the external pytest session.

## Restrictions and caveats

- A locator's uniqueness at recording time is not guaranteed forever. No selector is silently changed or replaced with `.first()`.
- The generator groups page objects by recorded URL. In single-page ERPs, PI, PO and GRN may share the same route, so consider using Business Flows for named stages.
- **Only explicitly recorded assertions** are exported. Without assertions, a successful replay does not prove calculation or inventory correctness.
- Purchase Indent > Purchase Order > GRN is an ERP-specific sequence: capture and approve the actual stages and role transitions per ERP.
- This is a Windows desktop beta. Electron CDP connection and live enterprise ERP behavior still require a validation run on the deployment laptop.
- The upgrade script replaces only code/UI and test files, and does not modify `.env`, existing SQLite data, saved workflows, projects, or approval plans.
