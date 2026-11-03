# Smart ERP QA v6.2.3 - Browser-Link Teaching Feedback

The local **web dashboard** runs at `http://127.0.0.1:8766` in Chrome. No Electron or `Start-Desktop-Windows.bat` is required. The local FastAPI service must be running first; a bookmark alone cannot start Python.

## Getting started on Windows

1. Install Python project dependencies with `Install-Windows.bat` if `.venv` is missing.
2. Double-click **Open-Smart-ERP-Web.bat** once. It starts FastAPI in the background and opens the dashboard URL in your default browser.
3. After that, open or bookmark `http://127.0.0.1:8766` in Chrome. If the laptop restarts or the local backend exits, run the launcher again.
4. In **ERP Projects**, click **Open ERP** (web integrated view). Log in manually.
5. Click **Start Teaching ERP**. A persistent Recording ON indicator appears at the top and above the ERP view.
6. When a supported action is captured, the dashboard shows a toast with the step count, action and control label. Input values and passwords are never displayed by the toast.
7. Select **Finish / Save & Replay**, enter a unique workflow name, click **Finish Demonstration & Save JSON**. Verify your actions and locators, approve, return the ERP to the starting screen, then click **Check & Replay Approved Workflow**.
8. Review Passed/Failed results in **Overview**.

## Important limitations

The web dashboard shows an interactive **Playwright screenshot mirror**, not a browser engine embedded in Chrome. Many normal controls work, but some native keyboard shortcuts, file dialogs, cross-origin popups, drag/drop and custom ERP widgets cannot be reliably forwarded. A third-party site cannot generally be hosted as a fully interactive Chrome webpage inside a different webpage because of iframe/CSP/cookie restrictions. For those operations, use an actual desktop embedded Chromium experience or a separate Playwright browser.

A displayed 'recording on' status proves the recorder is enabled, not that every interaction has been saved. Only a step-count increase/notification confirms a captured action. If the count does not advance, check **Recorder Health**, the registered URL and action support. Never execute unreviewed Save/Submit/Approve actions.

The replay button no longer stays silently disabled: it explains which prerequisite is missing (approved workflow, browser session, or correct ERP). Missing/ambiguous selectors are never clicked by guessing.
