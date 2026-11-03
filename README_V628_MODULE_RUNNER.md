# Smart ERP QA v6.2.8 — Module Test Runner + Excel + portable Docker

This is a full v6.2.7-based build, not a patch. Old pages and scripts were kept.

## Windows laptop 2: Docker
1. Install Docker Desktop and WSL2, start Docker Desktop (Linux containers).
2. Extract this full ZIP to a writable folder, do not run it inside ZIP preview.
3. Double-click `START_WITH_DOCKER.bat` or in PowerShell run
   `powershell -ExecutionPolicy Bypass -File .\1_START_DOCKER_WINDOWS.ps1`.
4. Open `http://127.0.0.1:8766` on the **same laptop**.
5. Open an ERP through **ERP Projects**, log in manually in the interactive
   embedded viewer, then use **Module Test Runner**.
   For Ollama in Docker, start the Ollama service on the host and configure it
   to accept Docker-to-host connections securely. Otherwise use OpenAI or rules.
6. Stop with `STOP_DOCKER.bat` (data remains), back up with
   `3_BACKUP_DOCKER_DATA_WINDOWS.ps1` while stopped.

Docker runs Playwright's **own Chromium inside the container**. It reuses the
logged-in session within that managed browser. It cannot attach to a separate
Chrome window already open on Windows. If your target app needs native desktop
popups/windows rather than the mirrored viewer, instead use the existing
`1_INSTALL_ON_NEW_LAPTOP.bat` / `2_OPEN_SMART_ERP_WEB.bat` native Python mode.

First Docker build needs Internet access to download its Playwright image and
Python packages. Dashboard binds to localhost only, not a public server.
To test a server hosted on Windows localhost from inside Docker, use
`host.docker.internal` in the ERP project URL rather than `127.0.0.1`.

## Module Test Runner
1. Open **Module Test Runner** in the sidebar.
2. Choose **one** registered ERP project.
3. Assign existing saved workflows to `Module` and `Process` using the mapping form.
   The mapping is metadata only; your existing workflow JSON is unchanged.
4. Choose one or more module chips, then optionally process chips.
5. Download the Excel template with exactly the requested 11 columns.
6. Import the completed Excel. Upload **resets approval**, and any actual/status
   values pasted into Excel are ignored (only real executions produce results).
7. Review each case and map it to a unique, **reviewed** workflow. Then approve
   selected case IDs.
8. Open the ERP and log in manually, finish recording if active. Run all approved
   cases in the selected scope or just checked cases.
9. Use the Results table for screenshot, trace and JSON report links.

## Uploading existing Playwright Python scripts
Upload `.py`, assign module/process. Smart ERP does a safe **static AST scan**;
no uploaded script is ever directly executed. Generate AI/RULE candidate test cases
(positive, negative, boundary, role-based) with OpenAI API, local Ollama, or rules.
To **execute** your existing Python script, its actions must be converted into a
reviewed Smart ERP JSON workflow / compatible adapter first. The current upload
feature is an analysis and generation entry point, not a generic Python runner.

Run sequencing is synchronous for local beta. Failure screenshots are captured
by the existing Playwright worker. The executor continues with subsequent cases;
it does not retry actions or relogin. It doesn't reset ERP state between tests,
so use separate independent workflows and verify preconditions. Unimplemented
negative/boundary/role adapters are marked BLOCKED (never an invented pass).

## Preserved features
Original Overview, Register ERP, ERP Projects, Workflows, Browser Session,
Approval Plans, Business Flows, local mock ERP, Yes/No delete, and legacy native
Windows deployment remain in this full release.

## Limitations / safety
- No shared multi-user server or central browser farm in this beta.
- No arbitrary uploaded Python execution, no automatic rewrite of Python code,
  no magical business-rule derivation.
- Excel main worksheet contains exactly 11 specified columns; the extra
  Execution Map worksheet holds workflow mapping and scenario category without
  changing the required columns.
- Only workflows containing actual assertions can be counted as PASS. Run
  assertions must reflect real approved ERP rules.
- Avoid actual production transactions. Keep ZIP, DB and screenshot data private.
- The .env with passwords/API keys is excluded from portable code archives.
