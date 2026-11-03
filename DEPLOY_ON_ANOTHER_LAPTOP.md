# Smart ERP QA v6.2.7 — Full deployment on another Windows laptop

**This ZIP contains the complete v6.2.7 application, not just an update patch.**
It includes the Python FastAPI backend, Playwright automation / recorder,
POM generator, green/white web frontend, reviewed workflow replay, reports,
login wizard, local mock ERP, automated tests, installation scripts, and the
latest existing-session replay and Yes/No workflow-removal changes.

The dashboard is opened through **http://127.0.0.1:8766**. No Electron or Node
installation is needed for **web mode**. The localhost link belongs to each
individual laptop; it is not a remote shared server.

## A. Brand-new installation on laptop 2 (code + bundled sample data)

1. Install Python 3.12 or 3.13 for Windows (64-bit recommended), with the `py`
   launcher enabled. Python 3.11+ is supported by the project, but using a
   stable Python release is recommended. Have an internet connection for
   first-time Python packages and the Playwright Chromium download.
2. Copy **Smart_ERP_QA_v627_Complete_Portable_Deployment.zip** to laptop 2.
   Right-click it -> **Extract All**. Do not launch files inside the ZIP viewer.
3. Open the extracted `smart_erp_qa_v627_portable` folder.
4. Double-click **`1_INSTALL_ON_NEW_LAPTOP.bat`**. This makes a fresh `.venv`,
   installs the Python requirements, installs Playwright Chromium, prepares
   `.env` from `.env.example`, and initializes the harmless mock ERP when
   no existing SQLite database is present.
5. Double-click **`2_OPEN_SMART_ERP_WEB.bat`**. Open
   **http://127.0.0.1:8766** in Chrome/Edge.
6. Register/verify projects, configure login selectors using the wizard,
   and log in manually before running a reviewed workflow in test/staging.

**These steps deploy the full app but do not magically include state that
exists only on laptop 1.** The base ZIP includes the bundled sample projects
and recordings but NOT the live updated SQLite database or new workflows from
your existing laptop. See section B to migrate those too.

## B. Make a single ZIP that includes your REAL saved workflows and history

On **laptop 1**, close the Smart ERP backend first (usually Ctrl+C in the
PowerShell window where it was launched; the kit also includes
`3_STOP_SMART_ERP_WEB.bat` for a verified local backend). Avoid copying an
open SQLite database.

1. Extract the full v6.2.7 ZIP into any folder on laptop 1; do not delete your
   existing installed project.
2. Inside the extracted folder, double-click **`Create-Portable-Transfer.bat`**.
3. When asked for your installed project folder, paste:

   `C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp`

   Or run directly from PowerShell in the extracted portable folder:

   ```powershell
   .\Create-Portable-Transfer.ps1 -CurrentProjectPath "C:\Users\Anil\Downloads\smart_erp_qa_v61_multi_erp_complete\smart_erp_qa_v61_multi_erp"
   ```

4. The script creates **`Downloads\Smart_ERP_QA_Transfer_With_My_Data.zip`**.
   It combines the full **v6.2.7 code** from this package with your actual:

   - `projects/` — ERP project-specific locator libraries and saved login selectors
   - `workflows/` — saved, reviewed and draft workflows
   - `approval_plans/` — multi-role approval plans and flow configurations
   - `data/` — SQLite database, project registry, execution history
   - `artifacts/`, `reports/` — execution evidence, screenshots, traces, exports
   - `legacy/screenshots`, `legacy/reports` — if present

5. Move that **single transfer ZIP** securely to laptop 2, **Extract All**,
   then double-click `1_INSTALL_ON_NEW_LAPTOP.bat` and
   `2_OPEN_SMART_ERP_WEB.bat` in the extracted project folder.

You now have the same saved projects, workflows, login selector configs, and
execution history. **Browser cookies, active login sessions, Python virtual
environments, downloaded Chromium, passwords and API keys are not portable.**
You need to log in again and re-enter secrets on laptop 2.

### Security

- The transfer ZIP **excludes the root `.env`** file, which may contain real
  account passwords and API keys. Re-enter secrets in the new `.env` on laptop 2,
  or transfer `.env` separately through a private secure channel. Recorded data
  may independently contain sensitive test inputs; inspect before sharing.
- The transfer ZIP may contain internal ERP URLs, user IDs, screenshots, and
  form values in saved JSON or reports. Treat it as **private**. Do not upload
  it publicly or share it in a public repository.
- The export refuses to run while port 8766 is listening and does not change
  the source installation. The destination ZIP must not already exist, to
  prevent accidental replacement.
- The export includes the **v6.2.7 source code from this package**, not unknown
  custom code changes made only in your existing project folder.

## C. Verify on laptop 2

Open PowerShell in the extracted project folder and run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
Invoke-RestMethod http://127.0.0.1:8766/api/health
```

The second command requires the dashboard to be started. In the UI, check that
ERP Projects, Workflows and Overview list the migrated items. Test with a safe
mock or disposable test/staging record before any live ERP changes.

### Troubleshooting

- **Port 8766 in use**: open the existing dashboard first or stop the old
  server terminal before restarting. Do not force-stop an unrecognized process.
- **`python` not installed**: install a supported Python from python.org,
  with the launcher enabled, then run the installer again.
- **Chromium cannot launch**: run
  `.\.venv\Scripts\python.exe -m playwright install chromium`.
- **Workflow blocked**: verify the active ERP page matches the workflow's
  start page, review locator alternatives, and ensure the browser is logged in.
- **No records after moving**: use the personalized transfer ZIP from section B;
  a plain code ZIP does not contain your old laptop's newest data.

The project has a screenshot-based ERP web viewer, not a native embedded Chrome
session. Complex controls may require re-verification on the second laptop.
