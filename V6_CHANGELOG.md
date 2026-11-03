## v6.2.7 — Reuse Already Logged-In ERP + Yes/No Workflow Removal
- Current-session Check & Replay never opens a browser or logs in again; checks the current page before executing.
- Conservatively skips a **complete** initial recorded username/password/sign-in prefix in memory (and only if present); preserves workflow JSON, approval fingerprints and original step numbers.
- Explicit session mode and skipped-step count in replay JSON report. Run From Login stays a separate, opt-in action.
- Manage Saved Workflows: real **Yes, Remove** / **No, Keep** dialog, Escape cancels, archived workflow and dependency checks unchanged.
- Code-only Windows upgrade with backups; does not overwrite user projects, workflows or databases.
- Local tests only; authenticated Kagami ERP replay not verified in this build environment.

## v6.2.5 - Run From Login and Step 2 Navigation Repair
- New browser or inside-dashboard automatic login, with explicit config check and runtime-only credentials.
- Opt-in, exact-label, uniquely visible navigation locator recovery; no write-action auto-fixes or JSON mutation.
- Added logged-in Step 2 diagnostics and per-run recovery evidence in JSON reports.
- Code-only Windows upgrade preserving all projects, logins, locators, data, and reports.
- Direct Kagami/Surajlabs login and replay were not tested from this build environment.

# V6 targeted recorder / Python export changes

Modified:
- `backend/browser.py` - headed Chromium window sizing, explicit fresh recording, pause/resume, live preview while preserving existing replay.
- `backend/api.py` - pause/resume/preview endpoints and Python download route.
- `backend/record_js.py` - codegen-style locator preference and reduced duplicate input clicks.
- `frontend/app.js` - recording controls, live preview, Python export, clearer manual login flow.

Added:
- `backend/python_export.py` - safe project-specific Playwright Python exporter.
- `tests/test_integrated_v6.py` - export, project isolation, capture lifecycle tests.
- `UPGRADE_V6_RECORDER.md` - exact Windows upgrade steps and limitations.

No previously saved database rows, JSON workflows, locator files or approval flags were intentionally edited by this patch.

## v6.2.2 — reviewed JSON → POM export
- Exports project-specific Python Page Objects, ordered orchestration, safe pytest example tests and test-data templates from APPROVED steps.
- Validates the locator-library fingerprint, observed uniqueness and TEST/STAGING environment before generating.
- Adds dashboard Generate POM ZIP to the selected saved workflow.
- Existing Playwright replay/negative-check actions remain the live dashboard execution path; no silent workflow data mutation.

## v6.2.4 — Common replay validation and multi-workflow diagnostics
- Fixed strict start-route preflight for uniquely verified navigation controls.
- Preserved strict blocking for unsafe first actions, missing/duplicate selectors, login screens and unreviewed workflows.
- Added read-only Diagnose All Workflows for Open ERP and specific reason codes in notifications.
- Added code-only Windows upgrade with per-file backups, no changes to projects or saved data.

## v6.2.6 — Guided Login Selector Wizard

- Capture three unique login controls on the live ERP login page without reading their entered values.
- After manual login, choose a unique post-login success element that was not visible before login.
- Verify selected locator again and save `projects/<id>/login.json`, backing up any previous file first.
- Show the 3-step configuration flow in Browser Session and the embedded ERP web view.
- Preserve existing login/replay options, POM generator, workflows, and reports.
- Included five new offline/local Chromium tests. Kagami production/staging pages were not available for direct validation.
