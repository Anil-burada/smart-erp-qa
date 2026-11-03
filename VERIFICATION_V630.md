# Verification - Smart ERP QA 6.3.0

## Automated checks

`python -m pytest -q`: **189 passed**, 2 FastAPI lifecycle deprecation warnings.
This includes the 168 pre-existing checks and 21 new Script Workspace checks.
The transfer test was updated to verify the new folder name and preservation of
locally edited working_scripts.

New checks cover static-only inspection, path traversal and symlink rejection,
invalid Python, stale source hashes, explicit run approval, production blocking,
managed-session capability requirements, honest treatment of printed PASS text,
structured checks, nonzero exception exits, immutable active snapshots, next-run
source changes, stop/concurrent-run guards, approximate print matches, missing
credentials, and Excel/HTML export safety.

## Browser and UI checks

- Rendered the actual HTML/CSS/JavaScript assets in headless Chromium.
- Used a local HTTP API bridge for rendering because this environment's managed
  browser policy blocks direct localhost navigation; no browser policy was changed.
- Checked 10 navigation pages with zero JavaScript page errors.
- Checked 1500-pixel desktop layout and 390-pixel mobile layout (no horizontal overflow).
- Visually reviewed the Dashboard and Script Workspace screenshots.
- Confirmed desktop sidebar collapse and restore.
- Verified the navy sidebar color and genuine empty/no-run states.

## Managed-session handoff check

A separate script process connected over CDP to a managed Chromium page containing
only an in-memory synthetic DOM. It preserved an existing JavaScript session marker,
updated the same page, and exited without closing that managed browser. No real ERP
URL, credentials, records, account approvals or external transactions were used.

## Verification environment

Linux, Python 3.13.5, Playwright Python 1.57.0, system Chromium,
FastAPI 0.128.2, Pydantic 2.13.5, pytest 9.0.2, openpyxl 3.1.5,
PyMuPDF 1.26.7. The deployable requirements/Docker image are pinned to Playwright
1.64.1, the official documented Docker version at preparation time; this image
was not built or executed here. Test results above describe the local environment,
not certification of every possible target-machine dependency combination.

## Not verified here

- Your real Kagami ERP login, controls, PI/LPO/GRN persistence or approval statuses.
- Windows PowerShell execution and installation on another physical laptop.
- Docker Desktop build/runtime or its embedded browser login on Windows.
- Real OpenAI/Ollama provider calls or newly generated executable negative cases.
- Cross-machine remote browser agents, multi-user permissions or production hosting.

The supplied procurement script still requires authorized test credentials, ERP
locator verification, and appropriate business assertions. A successful control
click is never reported as independent proof of final ERP business status.
