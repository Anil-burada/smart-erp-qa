# Smart ERP QA v6.2.5 - Run From Login and Procurement Step 2 Repair

## What changed

- Both **Run From Login (Inside Dashboard)** and **Run From Login (New Browser)** are now clickable and display a useful message if the workflow is not approved or login selectors are not set up. The separate-browser option deliberately opens another Chromium window; Inside Dashboard keeps the ERP in Smart ERP's browser pane.
- **Check Login Setup** verifies that a saved, valid `projects/<project_id>/login.json` belongs to the registered ERP project. This is only a configuration check, **not proof of successful login**.
- **Configure Login Selectors** opens the existing Browser Session login editor. You can use the auto-captured username/password/submit **selector suggestions**; a human must still verify a unique post-login success selector before saving.
- Runtime username/password values are sent only to local FastAPI for the current login. They are never written to login.json, the workflow, saved logs or SQLite reports.
- The shared optional **Allow exact-label navigation locator recovery** checkbox works for both current-browser replay and automatic login replay. It handles the recurring 'Procurement' Step 2 failure **only when** the current page contains exactly one visible interactive control with the precise recorded label. It tries approved recorded alternatives first, then a uniquely matching live text locator. If the menu is hidden, absent, or ambiguous, replay still stops.
- No automatic repair is attempted for Save, Submit, Approve, Create, Delete, Logout, or any fill/typing operation. Recorded JSON mappings are not silently altered. The run's report includes the step number and type of any navigation recovery.
- A failed run now explains whether a uniquely visible navigation control exists with the recorded label.

## Browser-only usage

1. Open `Open-Smart-ERP-Web.bat`, then visit `http://127.0.0.1:8766` in Chrome.
2. Open **Workflows**, choose `leocem_ba / purchase_indent88`, and load it.
3. If the workflow is still draft, review and approve its locator JSON and all record-changing steps.
4. Under **Run from Login**, click **Check Login Setup**. If incomplete, click **Configure Login Selectors**, select the registered ERP, open the actual login page, import suggested selectors, and configure the post-login success marker based on the real UI. Save `login.json` without any passwords.
5. Enter the authorized TEST/STAGING username and password. Select **Run From Login (Inside Dashboard)** for link-only use, or **Run From Login (New Browser)** if a new Chromium window is desired.
6. If previous failures were at **Procurement**, optionally check **Allow exact-label navigation locator recovery**. It cannot overcome missing permissions, collapsed menus, a wrong page or multiple matching controls.
7. If the workflow creates or approves records, authorize **test/staging changes**. Run; review the report and the `navigation_recoveries` details. Confirm real ERP business results separately.

### Why Step 2 can fail

The old Step 2 locator was `{'kind':'role','role':'button','name':'Procurement'}`. If the current role's navigation is instead a link, menu item, tab, or hidden submenu, the role=button locator returns 0 matches. A successful login only proves the configured success marker appeared, not that the correct menu is available. This patch tests an exact, uniquely visible alternative, **not** arbitrary clicks.

### Safety and limits

- Production automation is prohibited. CAPTCHA, OTP/MFA, SSO, and unknown login layouts may still require manual login.
- A completed Playwright workflow is not equivalent to validated business rules. Assertions for PI, PO, GRN, approvals and amounts must be recorded/configured separately.
- This release was tested with locally mocked HTML; no direct access to Kagami's authenticated pages is available from the build environment.
- Existing incorrect locators may still need manual repair or new recordings. Never bypass failed checks for record-changing buttons.

## Install on Windows

Close the running FastAPI server before upgrading. If needed, run `powershell -NoProfile -ExecutionPolicy Bypass -File "<extracted v625 folder>\Stop-Smart-ERP-Web.ps1" -TargetPath "<existing project folder>"`; it refuses to stop processes outside that project's Python environment. Extract the ZIP, then from PowerShell:

```powershell
$source = "$env:USERPROFILE\Downloads\Smart_ERP_v625\smart_erp_qa_v625_web"
$target = "$env:USERPROFILE\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Login-Replay-Windows.ps1" -TargetPath $target
```

The script backs up overwritten code and preserves `.env`, `data`, `projects`, `workflows`, credentials config, artifacts and reports.
