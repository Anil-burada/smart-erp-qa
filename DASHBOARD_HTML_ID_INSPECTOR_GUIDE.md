# Smart ERP QA v6.1.7: HTML/ID Locator Inspector

## What changed
- **Workflows > Inspect Current Page IDs & Buttons** shows redacted HTML-like tags of visible controls from the open Playwright ERP tab.
- Prefers a UNIQUE, non-generated `id`, then `data-testid`, then stable attributes. Structural CSS paths are treated as fragile.
- Tests how many matching controls exist on the live page. Duplicate or generated IDs are flagged.
- Copy the proposed JSON locator into the reviewed workflow's JSON (only after confirming that the element is the intended control). Changes to existing approved workflow JSON require re-approval.
- **Replay Start Diagnostic** checks the first saved locator and previously saved alternatives without changing ERP state.
- **Check Start & Run** blocks if the first locator isn't uniquely visible. It never guesses a different button.

## Why JSON->HTML doesn't fix a locator
JSON represents the recorded automation instructions. The ERP web page is the source of HTML. We inspect the live HTML DOM and create safe JSON locator candidates; generating a local HTML file from old JSON wouldn't change the real ERP buttons.

## How to install on your existing laptop
1. Stop the Smart ERP server (Ctrl+C in its PowerShell window) and close the standalone extractor if running.
2. Extract the `Smart_ERP_QA_v617_Full_Windows.zip` ZIP to Downloads.
3. In PowerShell in the **existing project folder** that contains `run.py`, run:

```powershell
$source = "$env:USERPROFILE\Downloads\Smart_ERP_QA_v617_Full_Windows\smart_erp_qa_v617_full_windows"
$target = (Get-Location).Path
Test-Path (Join-Path $target 'run.py')
powershell -NoProfile -ExecutionPolicy Bypass -File (Join-Path $source 'Upgrade-Existing-Windows.ps1') -TargetPath $target
.\.venv\Scripts\python.exe run.py
```

If `Test-Path` is `False`, you are in the wrong folder. Find the current project folder with:

```powershell
Get-ChildItem "$env:USERPROFILE\Downloads" -Filter run.py -Recurse -File -ErrorAction SilentlyContinue | Select-Object -ExpandProperty DirectoryName
```

4. Open http://127.0.0.1:8766 and press Ctrl+Shift+R.
5. Open ERP, log in manually, choose Workflows, click Inspect Current Page IDs & Buttons. To record a new workflow, use Start Teaching ERP only after login.

## What the tool never does
- It does not copy typed field values, passwords, tokens, or raw login form HTML into the inspector.
- It does not click buttons or auto-change existing approved locator libraries.
- It inspects the **main frame**. Cross-frame menus and shadow DOM may require additional mapping.
- An `id` is not automatically unique or stable; framework IDs can change between renders or sessions.
- It cannot infer Purchase Indent -> PO -> GRN business rules without explicit validated mappings.

## New laptop
Extract the same ZIP, enter `smart_erp_qa_v617_full_windows`, run `Install-Windows.bat`, then `Start-Windows.bat`. Python dependencies download on the new laptop; never copy `.venv` across machines.
