# Smart ERP QA v6.2.7 — Replay after manual login + Yes/No removal

## Goal

Use only `http://127.0.0.1:8766` and the **ERP Projects → Open ERP** embedded viewer. After you sign in manually **inside the Smart ERP Playwright-controlled viewer**, choose the approved recording and click:

**Check & Replay Approved Workflow (Already Logged In)**

This operation:
- Reuses the currently open Playwright ERP tab/context; it does **not** open a new browser window, navigate to the registered login URL, or submit login credentials.
- Runs the approved workflow from its first business step and validates that element *on the current ERP screen* before clicking.
- If and only if the saved workflow begins with a complete recognizable **username fill → password fill → Sign in** sequence, skips those initial login actions in memory. The JSON workflow is not edited, the approval stays unchanged, and later role-change/login steps are never silently omitted.
- Reports how many initial login steps were skipped and retains original step numbers in error reports.
- If the current page still shows a login/password form, it **stops** and asks you to log in manually; it will not perform automatic login to recover.

**Important:** Logging into the ERP in a separate normal Chrome tab is not the same session as the Playwright browser mirrored in this dashboard. Log in inside Smart ERP's ERP viewer. A session that expires or an ERP application that redirects to its login page still needs a new manual login. A missing `Procurement` element is not fixed just by session reuse; verify its saved locator or opt into navigation-only recovery.

## Remove saved workflow

Open **Workflows → Manage Saved Workflows**. Click **Remove**. A dialog with two real buttons appears:
- **No, Keep** — cancel without changes. Escape also cancels.
- **Yes, Remove** — archive this workflow's JSON and remove it from the active workflow list, leaving ERP projects, other workflows, locator libraries, and execution reports intact.

You no longer need to retype the project or workflow name. If a workflow is referenced by an Approval Plan or Business Flow, the backend blocks its removal until the references are updated.

## Windows upgrade from the previous installed project

1. Stop `Open-Smart-ERP-Web.bat` in its PowerShell window (`Ctrl+C`). Close the backend, not only the Chrome tab. Port 8766 must be free before upgrading.
2. Download the v6.2.7 full ZIP into Downloads.
3. In PowerShell (any starting directory):

```powershell
$extract = "$env:USERPROFILE\Downloads\Smart_ERP_v627"
Expand-Archive -LiteralPath "$env:USERPROFILE\Downloads\Smart_ERP_QA_v627_Existing_Session_Full_Windows.zip" -DestinationPath $extract -Force
$source = "$extract\smart_erp_qa_v627_web"
$target = "C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Session-Windows.ps1" -TargetPath $target
```

4. After the successful upgrade:

```powershell
Set-Location $target
.\Open-Smart-ERP-Web.bat
```

5. Go to `http://127.0.0.1:8766` in Chrome, press `Ctrl+Shift+R`, and test.

The installer is **code-only**. It backs up existing code before replacement and never modifies `.env`, `projects`, `workflows`, `data`, SQLite, saved login selectors, reports, `flows` or `approval_plans`.

## Safety and limitations

- Reviewed workflows only; TEST/STAGING only. Approvals for real transaction-changing actions remain mandatory.
- The script does not bypass missing/duplicate locators, SSO, MFA, CAPTCHA, approval-role permissions or business assertions.
- Initial-login skip is deliberately conservative: an unrecognized login sequence is not skipped. Review such recordings, or create a new business-only recording after manual login.
- For multi-user approval workflows, use explicit reviewed Approval Plans with authorized account switching, not an unintended login-step skip.
- Chromium local test and Python regression tests cannot guarantee behavior on authenticated Kagami ERP; confirm in your own local authorized test session.
