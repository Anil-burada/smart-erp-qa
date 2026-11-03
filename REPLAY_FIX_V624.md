# Smart ERP QA v6.2.4 — Shared Replay Gate and Diagnostics Repair

## Why many workflows show the same error

Version 6.2.3 runs the same first-step preflight for each saved workflow. It previously
required an exact current-URL match with the first recorded URL. This can block
valid ERP navigation workflows after a safe same-origin route change, even if their
first recorded navigation control is uniquely visible. The error notification also
used one generic text for several different causes.

## What v6.2.4 changes

- Checks the recorded first locator **without clicking**.
- Allows a same-origin URL-path difference **only** for a uniquely visible first
  navigation click whose live control identity matches the recorded label.
- Still blocks invisible, missing, ambiguous, or unapproved locators; login screens;
  different-origin sites; and route mismatch for Save, Submit, Approve, Delete,
  or other potentially record-changing first actions.
- Never guesses a new locator, navigates automatically, retries a write action,
  changes approval status, or edits saved workflows.
- Gives precise notifications: `LOCATOR_NOT_FOUND`,
  `LOCATOR_NOT_UNIQUE_OR_HIDDEN`, `START_ROUTE_MISMATCH`, `LOGIN_REQUIRED`,
  `REVIEW_REQUIRED`, or `ROUTE_VERIFIED`.
- Adds **Diagnose All Workflows for Open ERP** in Workflows. It runs read-only
  Step 1 checks for up to 20 saved workflows for the open project on the **current
  ERP screen**. Results are grouped in a table. Workflows with different expected
  start pages will properly show not ready until you navigate to their page.

## Install to your existing v6.2.3 web dashboard

Close Smart ERP backend and open the v6.2.4 ZIP. From PowerShell, run:

```powershell
$source = "$env:USERPROFILE\Downloads\Smart_ERP_QA_v624\smart_erp_qa_v624_web"
$target = "C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Replay-Windows.ps1" -TargetPath $target
```

Then double-click `Open-Smart-ERP-Web.bat` from the existing project folder;
open http://127.0.0.1:8766/ in Chrome (refresh with Ctrl+Shift+R).

## Test safely

1. Open your registered **test/staging** ERP from ERP Projects, and log in manually.
2. On Workflows, click **Diagnose All Workflows for Open ERP**. No buttons are clicked.
3. Choose a workflow that starts from the current ERP screen. Load and approve if needed.
4. Click **Diagnose Replay Start (No Clicks)** and read the specific reason code.
5. If `ROUTE_VERIFIED` or `READY`, with the correct intended element, confirm
   test transactions and run reviewed replay. If `LOCATOR_NOT_FOUND`, inspect the
   saved target against **Inspect Current Page IDs & Buttons** and fix the mapping.
6. Review the screenshot, trace and status of a failed execution; later steps
   require their own accurate locators and explicit assertions.

## Limits

- This does not recover discarded recording actions or repair incorrect old
  JSON selectors automatically. It cannot prove your Kagami/Surajlabs ERP live
  workflow works, because that would require the recorded data and a logged-in
  test session on your computer.
- A correct first-step preflight does not guarantee later steps succeed.
- Web-only mode uses a screenshot mirror of headless Playwright, not a native
  embedded Chromium view. Some popup, drag/drop and custom controls remain limited.
- Always test on authorized test/staging ERP with disposable data.
