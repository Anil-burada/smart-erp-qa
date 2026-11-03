# Smart ERP QA 6.3.0 - Navy & White + Editable Script Workspace

This is a full local Windows/Docker project, based on v6.2.8. It includes your
PI -> approvals -> LPO -> approvals -> GRN script as an editable Python file.
The supplied ERP workflow has NOT been executed against your actual ERP here.

## 1. Recommended route: visible browser on Windows

1. Extract the complete ZIP into a new folder. Keep the old installation as a backup.
2. Stop the old dashboard (Ctrl+C in its terminal). Only one server may use port 8766.
3. Run `Install-Windows.bat`. This installs the project dependencies and Chromium.
4. Edit the generated `.env` locally. Fill the four password variables below.
5. Run `Start-Windows.bat` and open `http://127.0.0.1:8766`.
6. In **Add ERP Application**, register your authorized TEST/STAGING ERP URL with
   Chromium. The included Demo Procurement ERP is a separate local demo; do not
   select it for the Kagami-specific PI/LPO/GRN script.
7. Open your ERP from **ERP Applications**, then log in manually as the script's
   initial account, DMG0013. Stop any recording before starting a script.
8. Open **Script Workspace**, select your ERP and `pi_lpo_grn.py`, review the
   confirmations and choose **Review & Run Latest**.

Required local variables (no actual passwords are distributed):

```dotenv
ERPQA_KAGAMI_DMG0013_PASSWORD=
ERPQA_KAGAMI_DMG0041_PASSWORD=
ERPQA_KAGAMI_DMG0051_PASSWORD=
ERPQA_KAGAMI_DMG0052_PASSWORD=
```

All four roles are needed by your supplied approval flow, even when its initial
login is skipped. The code no longer assumes a password equals its username.
The original script's tax, quantity, discount and tolerance settings are retained;
review them against your authorized test environment before using them.

## 2. Your VS Code editing workflow

Open the extracted project root in VS Code. Edit:

```text
working_scripts/procurement/pi_lpo_grn.py
```

Or run from the project root in PowerShell:

```powershell
code .\working_scripts\procurement\pi_lpo_grn.py
```

Save with Ctrl+S. Click **Review & Run Latest** again. Smart ERP reads the saved
file, checks Python syntax and asks you to confirm its current SHA-256 revision.
Each run stores the exact executed source snapshot. Editing while a run is active
does not change that run; your edits apply to the next run.

There is no need to upload the script again or rebuild Docker for source edits.
Changes to frontend/backend application code still require the normal restart or
Docker rebuild. Unsaved VS Code changes cannot be detected by the runner.

Add future trusted .py scripts under another `working_scripts/<module>/` folder.
Click Refresh files. A script must be adapted to accept a managed page before it
can support existing-session mode. A generic standalone script can use New browser
mode, but structured result reporting is not automatic: use the explicit functions
in `backend/script_runtime.py`. Exit code zero alone is **Completed - review**, not
proof that generated test cases passed. This version launches one script at a time.

## 3. Browser modes

**Continue in my managed logged-in browser** reuses the Chromium page opened by
Smart ERP on this installation. It does not reload the login URL or perform the
first login. You confirm the initial role is DMG0013; this is not an automatic
identity assertion. Your existing approval flow STILL deliberately logs out and
logs in as the configured approvers later. The managed browser remains open at the
end. An unrelated ordinary Chrome window is not automatically attachable.

**New browser** launches a separate browser and performs your script's original
initial login. On Windows it is visible; inside Docker it is headless. This mode
does not reuse your Windows browser session. At the end, that separate browser
closes without waiting for terminal input.

Only Chromium supports this managed script handoff. The local debugging endpoint
is loopback-only and is never published from Docker. Do not expose it externally.
CDP limitations remain relevant; see the official documentation below.

## 4. What changed in your script

ERP locator bodies, calculation formulas, random value selection, dropdown round
robin, sequence files and approval order were retained. Integration changes are:

- Optional managed-browser reuse, with no initial navigation/login in that mode.
- Local .env passwords instead of the username-as-password assumption.
- Explicit stage/calculation events for the dashboard; console text is not counted.
- Failure screenshots enabled, plus an independent screenshot attempt if a stage
  fails. Screenshot/trace capture can still fail after browser crashes.
- Exception propagation so an automation failure cannot end with a false success.
- Separate per-run print/evidence directories to avoid overwriting prior reports.
- Dashboard runs do not open the standalone Tk emergency window or wait on input.
- Traces are captured where available. Stop may interrupt trace finalization.

The flow is dependent. A failed PI/LPO stage stops its downstream GRN work; the
remaining stages are reported as one blocked dependency group, not invented
individual test-case results. Independent approved cases in Module Tests retain
the existing suite continuation behavior. Stop is not a transaction rollback.

Approval/submit functions in your source only confirm clicks, not persisted final
ERP status. These stages are **Needs review**, not Passed. Your original PDF item
code similarity policy is retained in its validator, but approximate/partial
matches do not become exact-verification passes in the dashboard.

## 5. Dashboard and reports

The interface uses navy navigation and primary buttons, white cards and pale-blue
surfaces. Green, red and amber are used only for result meaning.

Dashboard: real Excel/AI case totals, latest case states, recent test results,
workspace shortcuts and the latest script run. Script checks are separate counts.

Script Workspace: local file selection, module filters, saved revision, project,
browser mode, Run, Stop, live logs, structured checks, screenshots, traces and
Excel/HTML/JSON report downloads.

Module Tests & Excel: your multi-module/process chips, AI drafts, case approval,
existing workflow mapping and exact 11-column import/export remain available.

Your report columns remain:
Module | Process | Test Scenario | Test case ID | Test case | Pre condition |
Test Steps | Expected Result | Actual Result | Status (Pass/Fail) | Positive/Negative.

Needs-review and blocked script checks leave the Pass/Fail cell blank and state
the reason in Actual Result. Report rows are not automatically executable tests.
Download/edit/upload automation still requires an approved executable workflow
mapping and explicit assertions. To analyze your current local file, click
**Analyze for AI / Excel**, then choose the stored revision/provider in Module
Tests. AI-generated drafts are never automatically approved or executed.

## 6. Docker on this or another laptop

Run `START_WITH_DOCKER.bat`. The setup creates .env from the example if absent.
Docker Desktop must already be installed and running with Linux containers.

`working_scripts` is bind-mounted into the container, so VS Code edits on the host
are read on the next run. Edit the HOST file under the extracted project root, not
the displayed internal `/workspace/...` worker path. The Copy VS Code command is
relative to the extracted project root and works from that folder.

In Docker the managed browser is INSIDE Docker. Log in through the existing
embedded viewer, not a separate ordinary Windows Chrome window. A native Windows
installation is the recommended route for direct visible-browser interaction.
Do not run Windows native and Docker dashboards simultaneously on port 8766.
Do not copy a Python .venv from another laptop; install dependencies there.
Authenticated browser sessions and passwords are not transferred automatically.
This remains a LOCAL single-operator backend, not an authenticated multi-user
production/team server. Docker Desktop/Windows deployment was not executed here.

## 7. Upgrading an existing installation without deleting your data

Stop the old dashboard first. From this new extracted folder run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Upgrade-To-v630-Windows.ps1 -TargetPath "C:\Your\Existing\SmartERP"
```

Replace the target with the actual old project root containing backend and
frontend. The script creates a backup, updates application code, preserves your
.env/database/workflows/reports and does not overwrite existing working_scripts.
It updates Python dependencies and Chromium using that installation's virtual environment.
Then start the existing installation with `Start-Windows.bat` and press Ctrl+F5
in the dashboard browser. Read the upgrade output for any installation error.

## 8. Security and evidence

Only explicitly trusted local Python under working_scripts can run. AI uploads
are still inert analysis inputs. The subprocess is NOT a sandbox and has your
user's permissions. Syntax analysis is not proof of safe code. TEST/STAGING labels
are safeguards, not proof that a URL is really non-production: verify the URL.

Passwords remain in your local .env. Logs redact configured secret values, but
screenshots and Playwright traces may still contain confidential ERP data or
credential-bearing actions. Store reports securely; inspect/redact evidence before
sharing. Do not commit .env, reports, auth files or browser profiles to Git.

## Official implementation references

- https://playwright.dev/python/docs/api/class-browsertype#browser-type-connect-over-cdp
- https://playwright.dev/python/docs/docker
- https://docs.docker.com/engine/storage/bind-mounts/
- https://docs.python.org/3/library/subprocess.html

## Verification performed

See `VERIFICATION_V630.md` for the exact test scope. No live ERP transaction,
account approval, real-role login or real ERP calculation was verified here.
