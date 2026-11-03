# Smart ERP QA v6.2.6 — Guided Login Selector Configuration

## What problem this fixes

The Workflows screen shows **"Login selectors are not saved yet"** even if a username and password have been typed. The backend cannot safely infer the real username, password, submit-button and post-login success locators from those credential values.

This update adds **Guided Automatic Login Setup** to the existing web dashboard at `http://127.0.0.1:8766`. **You do not need Electron or a separate dashboard.** The project URL, data, recordings, `.env` and `login.json` are preserved during installation.

## Configure your ERP once (no HTML editing)

1. Start `Open-Smart-ERP-Web.bat` in your existing Smart ERP project directory, then visit `http://127.0.0.1:8766`.
2. Open **ERP Projects**, select the registered TEST/STAGING ERP, click **Open ERP**, and ensure its *login form is visible*. If already signed in, sign out through the ERP first, then reopen its login page.
3. Click **Configure Login** on the embedded ERP toolbar (scrolls to the guided setup). Click **1. Capture Login Fields**. Three unique controls—username, password, and sign-in—must be found before proceeding. No entered values are read.
4. **Sign in manually** in the embedded ERP view using the test account. Keep the same browser session open. Do not start teaching until login setup is complete.
5. Click **2. Find Success Marker**. Choose a distinctive visible post-login element (e.g. Dashboard or Sign out) that was not visible on the login form. The engine checks for one visible match.
6. Click **3. Verify & Save Login Setup**. Smart ERP saves selector metadata to `projects/<project_id>/login.json`. It **never saves usernames/passwords** there. An existing `login.json` is first backed up as `login.before_wizard_<timestamp>.json`.
7. Return to **Workflows**, load and approve your test workflow, click **Check Login Setup**. Enter the authorized test username and password at runtime and choose **Run From Login (Inside Dashboard)**. The workflow can run only after its post-login marker is verified.

If the login form has OTP, CAPTCHA, SSO, a multistep login, an iframe, or ambiguous controls, use manual login and the existing locator JSON editor. Do not guess a success marker.

## If a workflow still fails at Procurement

Configuring login solves only the *authentication* prerequisite. The recorded Step 2 locator `role=button, name=Procurement` may still be missing, hidden, or the wrong role. Check the Step 2 report and **Diagnose All Workflows**; do not re-record or approve an incorrect destructive action without review. The safe navigation-only recovery option remains available.

## Security and verification

- Only TEST/STAGING projects are supported for automatic login configuration and execution. Production automation remains disabled.
- The guided setup inspects locator metadata and visible DOM elements, not cookies, browser storage, input values, or secrets.
- Login selectors are verified for uniqueness on the login screen and the chosen success marker is verified after manual sign-in; the next automatic login repeats this success check.
- The local browser is an interactive screenshot mirror, not a native embedded browser. Some controls may remain unsupported.
- This patch has been tested against a local HTML/Chromium mock. The live Kagami login page has not been directly inspected; the wizard may require manual locator review there.

## Upgrade (Windows PowerShell)

Close the console running Smart ERP's FastAPI server before upgrading. Extract the v6.2.6 ZIP, then run:

```powershell
$source = "$env:USERPROFILE\Downloads\Smart_ERP_v626\smart_erp_qa_v626_web"
$target = "C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Login-Wizard-Windows.ps1" -TargetPath $target
```

After upgrade:

```powershell
Set-Location $target
.\Open-Smart-ERP-Web.bat
```

Then refresh the dashboard with **Ctrl+Shift+R**.
