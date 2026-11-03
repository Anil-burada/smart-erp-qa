# Smart ERP QA v6.3.4 - Leocem reports, scenario switches, annotated evidence

## Scope of this release

- Dashboard shows actual script-run counters, completed/failed/review checks and recent events, with reduced-motion-aware count animation and a running indicator. Old runs remain available.
- Positive toggle runs the **existing live Leocem PI -> LPO -> GRN automation** exactly as supplied, including the existing login logic in your local Python script.
- Negative toggle runs four **non-destructive local script quantity-guard tests** (zero, negative, alphabetic, mixed numeric). These do **not** exercise live Leocem form validators or submit invalid ERP data. This distinction is clearly shown in test-case reports. For actual ERP negative UI tests, add reviewed negative scripts later.
- Both toggles ON runs those local rule checks followed by the existing live positive workflow. Both OFF is blocked.
- `View report` opens a full HTML report showing real captured expected/actual values, stages, prints and evidence, as well as the 11-column Excel export.
- Click `.png`/`.pdf` evidence to preview in the dashboard or HTML report; use **Download** at the top. Trace `.zip` stays a download.
- Failed script checks capture a screenshot with a red error banner and red field outline when a unique matching DOM element is found. No guessed outlines or fabricated visual evidence.
- For actual print PDFs, the monitored PDF is copied, annotated with red/green boxes, and (for FAIL) captured as an annotated print preview screenshot before the temporary preview tab closes. **This is the rendered annotated print**, not a screenshot of the native browser's PDF viewer. Browser blob/cross-origin PDF capture can still fail; if it does the result is NOT_CAPTURED/REVIEW rather than Pass.
- Old screenshots remain plain. Old test history is preserved; fresh screenshots show annotations only when a live run captures them.

## Upgrade existing local installation

1. Stop the existing backend on port 8766 (Ctrl+C in its terminal).
2. Extract this ZIP under Downloads (do not overwrite your working installation during extraction).
3. In PowerShell, change into the folder containing this README and run:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Upgrade-To-v634-Windows.ps1 -TargetPath "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
```

4. The upgrade makes a dated backup, preserves `.env`, database, reports, your existing `working_scripts` and only adds recognized script improvements. Customized script sections are skipped, not overwritten.
5. Restart the old installed project:

```powershell
cd "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
.\Start-Windows.bat
```

6. Visit http://127.0.0.1:8766 and press Ctrl+Shift+R. Select Positive and/or Negative, then Run Automation. Confirm script revision and authorization.

No new username/password fields are required in `.env`; the script retains its own login logic. The authorized TEST/STAGING URL and environment must remain configured as before. Production use is blocked. Stop never rolls back ERP transactions.

**Source status:** Unit and integration tests run offline. Real Leocem login, actual ERP print layout, and Windows process behavior need validation on the authorized test system. No claim is made that the ERP-side validation itself passed.
