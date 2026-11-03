# Smart ERP QA 6.3.0

Start with **START_HERE_V630.md** for the navy/white dashboard and VS Code script workflow.
Your editable script: `working_scripts/procurement/pi_lpo_grn.py`.
Use **Upgrade-To-v630-Windows.ps1** to upgrade an existing installation safely.

---

## Earlier project documentation (historical)

# Smart ERP QA v6.2.8 — Module Test Runner + Excel + Docker

**Start here for the latest release:** `README_V628_MODULE_RUNNER.md`.
This is the complete Smart ERP v6.2.7-based application with a new
**Module Test Runner**, multi-select Module/Process filters, 11-column Excel
import/export, review/approval of test cases, safe static Python script analysis,
real Playwright execution reports, and Docker Compose scripts for another Windows laptop.
The green/white classic UI and previous dashboard pages are preserved.

**Docker on Windows:** double-click `START_WITH_DOCKER.bat` after Docker Desktop
is installed and running (WSL2/Linux containers). Visit http://127.0.0.1:8766.
Docker uses its *own* managed authenticated browser, not a Windows Chrome tab.
**Native Windows mode:** `1_INSTALL_ON_NEW_LAPTOP.bat`, then
`2_OPEN_SMART_ERP_WEB.bat`. For migrating your live laptop data, use
`Create-Portable-Transfer.bat`; this release does not contain unuploaded data.

---

# Smart ERP QA v6.2.7 — Complete Portable Windows Deployment

**For another laptop, start with `README_DEPLOY_FIRST.md` and `DEPLOY_ON_ANOTHER_LAPTOP.md`.**
This is the full application, including all updated backend/frontend/POM/replay code,
not an upgrade patch. On a NEW laptop, extract the ZIP, run
`1_INSTALL_ON_NEW_LAPTOP.bat`, then `2_OPEN_SMART_ERP_WEB.bat` and use
`http://127.0.0.1:8766`. No Electron setup is required for this link-based mode.

To move the **same saved projects, workflows and history** from laptop 1, use
`Create-Portable-Transfer.bat` after stopping its local backend. The downloaded
ZIP by itself does not include your unuploaded current laptop data or passwords.

---

# Smart ERP QA v6.2.7 — Resume from Your Existing Login

**New:** Keep using your link-based dashboard. After you manually log in inside **ERP Projects → Open ERP**, use **Check & Replay Approved Workflow (Already Logged In)** to replay business actions **without opening a new browser or logging in again**. A recognizable initial login-action prefix is skipped in memory; unrecognized login actions are never guessed. Use **Run From Login** only if you intentionally want automatic login instead.

**Remove workflow:** Workflows → Manage Saved Workflows → Remove now shows **No, Keep** and **Yes, Remove**, with no need to retype the flow name. The workflow is archived before removal.

**Existing installation:** See `REPLAY_EXISTING_SESSION_GUIDE_V627.md` and use `Upgrade-Existing-Session-Windows.ps1` with your existing Smart ERP project folder. This is a code-only upgrade, preserving `.env`, `projects`, `workflows`, `data`, `login.json`, executions and reports.

---

# Smart ERP QA v6.2.5 - Run From Login repair

Open the **web dashboard** with `Open-Smart-ERP-Web.bat` and visit `http://127.0.0.1:8766` in Chrome. You do not need Electron for link-only usage.

**Latest update:** Runtime login and replay now have visible setup checks, an inside-dashboard mode, and an explicit navigation-only exact-label locator recovery option for failures like `Procurement` at Step 2. See `LOGIN_REPLAY_GUIDE_V625.md` for setup and limits. All ERP credentials are runtime-only; selectors and workflow approvals are ERP-specific.

**Existing users:** Extract this ZIP, stop the current backend, and run `Upgrade-Existing-Login-Replay-Windows.ps1 -TargetPath <existing Smart ERP QA project folder>`. The upgrade backs up replaced code and does not modify `projects`, `workflows`, `data`, `.env`, screenshots, or saved reports.

---

# Smart ERP QA v6.2.3 - Web Link Teaching & Replay

**Recommended for this installation:** use `Open-Smart-ERP-Web.bat` instead of Electron. It launches FastAPI locally and opens http://127.0.0.1:8766 in Chrome. After startup, the browser link alone works while FastAPI is running.

See `WEB_DASHBOARD_GUIDE.md` for recording status, per-click notifications, saving workflow JSON, approval and replay.

**Important:** A Chrome webpage cannot contain a general-purpose native Chrome browser for arbitrary ERP sites. This web-only version mirrors a headless Playwright-controlled browser. Advanced keyboard, file dialogs and some custom controls may remain limited.

---

# Smart ERP QA v6.2.2 — POM Automation Upgrade

See **POM_GENERATOR_GUIDE.md** for Generate POM ZIP, reviewed replay, safe negative tests and Windows upgrade instructions.

# Smart ERP QA Desktop v6.2.1 — Complete Windows project

**Start here:** [DESKTOP_GUIDE.md](DESKTOP_GUIDE.md). Includes the existing FastAPI dashboard, SQLite storage, workflows, reporting, and Electron Chromium ERP view.

**New in 6.2.1:** Playwright initializes only on demand (the FastAPI health server no longer starts a Node Playwright driver during module import), more robust Electron startup, persistent backend logs, Node/npm.cmd checks and read-only diagnostics. This addresses a specific source of `EPIPE` and improves diagnosis if FastAPI is unavailable. Native Electron CDP attachment still needs to be verified on your ERP and Windows laptop; do not assume all websites or popups are supported.

**Existing laptop:** Extract this ZIP to a new folder, stop the old dashboard, run `Upgrade-Existing-Desktop-Windows.ps1 -TargetPath <your existing folder containing run.py>`, and then `Install-Desktop-Windows.ps1` if Electron was not installed. Existing `.env`, `data`, `projects`, `workflows`, `flows`, `approval_plans`, and `artifacts` are never replaced by the upgrade.

**New laptop:** In this extracted folder, run `Install-Desktop-Windows.ps1` and then `Start-Desktop-Windows.bat`. Setup requires Python and Node.js LTS + npm; Electron is downloaded with npm.

**Basic fallback:** To use your web dashboard even if the desktop/CDP portion fails, run `.\.venv\Scripts\python.exe run.py` (without `SMART_ERP_DESKTOP=1`) and open http://127.0.0.1:8766. This uses the old Playwright browser workflow, not the native desktop view.

### v6.2.6 Guided Automatic Login Setup

From the web dashboard at `http://127.0.0.1:8766`: **ERP Projects → Open ERP → Configure Login**. Follow the 3-step wizard: **Capture Login Fields → manual sign-in → Find Success Marker → Verify & Save Login Setup**. This creates `projects/<id>/login.json` with selector metadata only. For details, see `LOGIN_WIZARD_GUIDE_V626.md`. Live ERP selectors still require local verification.
