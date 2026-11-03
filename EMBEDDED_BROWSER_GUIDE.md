# Smart ERP QA v6.1.9 — Integrated ERP Viewer + Workflow Manager

## The two features

- **ERP Projects → Open ERP** starts an embedded, local Playwright Chromium session in the Smart ERP dashboard. The live view is made from in-memory screenshots and user-triggered mouse/keyboard events, not an HTML `<iframe>`. This avoids `X-Frame-Options` and CSP framing restrictions in most third-party ERPs. However it is a remote-view surface rather than a full native Chrome widget.
- **Workflows → Manage Saved Workflows** lists recorded workflows by ERP, review state and step count. `Remove` archives one workflow's JSON, and removes it from the active backend listing. Removal is blocked if a business flow or approval plan depends on it.

## Integrated ERP usage

1. Launch Smart ERP and choose **ERP Projects**.
2. Click **Open ERP** for the desired authorized test ERP.
3. A large interactive image of the ERP appears **above the project cards** and occupies about 95% of the browser workspace. The project cards stay below it.
4. Click inside the ERP view and type via your keyboard. Tab, Enter, Escape, arrows, Backspace and basic scrolling are supported. The **Paste text into currently focused ERP field** control offers an alternative for long inputs. Typed text is sent to localhost Playwright only, not saved by the view.
5. After manual login, click **Start Teaching ERP**. Perform the actions in the embedded view, then select **Workflows** to save the capture; return to **ERP Projects** to continue interacting in the same session.
6. Click **Close Browser** in the view. The ERP view disappears, leaving the project list on the same page.

### Known limits

This is not a full embedded browser engine. It sends screenshots and input through local HTTP endpoints. Tabs/popups, file chooser dialogs, drag-and-drop, WebAuthn/SSO windows, some clipboard operations and complex dropdowns may need the separate headed-browser mode. Use only locally on trusted test/staging ERP instances. Some anti-bot or anti-automation sites will not work in headless mode.

The viewer is not an iframe, so it does not bypass the target application's authentication, cross-origin restrictions, or security protections. Only tests explicitly authorized by the application owner should be performed.

## Workflows and deletion

Open **Workflows → Manage Saved Workflows**. Choose an ERP or show all. `Open` loads the recording; `Remove` requires typing the exact `project_id/workflow_name`. Removed JSON is moved into `workflow_archive` and saved execution history remains. No direct deletion of original ERP transactions occurs.

## Upgrade existing Windows project

- Close Smart ERP (Ctrl+C and terminate batch job Y if asked).
- Extract the full ZIP.
- In PowerShell, point `$source` to the extracted `smart_erp_qa_v619_full_windows` and `$target` to your already installed folder containing `run.py` and `.venv`.
- Execute: `powershell -NoProfile -ExecutionPolicy Bypass -File "$source\Upgrade-Existing-Windows.ps1" -TargetPath $target`
- Start the old project with `.\.venv\Scripts\python.exe run.py` and refresh `http://127.0.0.1:8766` with Ctrl+Shift+R.

The installer saves backups of replaced code. `.env`, `projects`, `data`, `workflows`, `flows`, and existing recordings stay in place.
