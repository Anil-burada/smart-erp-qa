# Smart ERP QA v6.3.3 — Leocem executed test cases and reports

The fixed Leocem **Run Automation** action remains unchanged; no ERP selection and no mandatory `.env` passwords. The saved Python script controls account login. Only an authorized test/staging Leocem URL and an explicit run confirmation are required. Do not run production writes.

## Upgrade an existing Windows installation

1. In the existing Smart ERP PowerShell window press **Ctrl+C**. Confirm port 8766 is free.
2. Extract `Smart_ERP_QA_v633_Leocem_Reports_Fix.zip` to `C:\Users\Anil\Downloads\Smart_ERP_v633_Extracted`.
3. In PowerShell:

```powershell
cd "C:\Users\Anil\Downloads\Smart_ERP_v633_Extracted\smart_erp_qa_v633"
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\Upgrade-To-v633-Windows.ps1 -TargetPath "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
cd "C:\Users\Anil\Downloads\Smart_ERP_QA_v630_Navy_White_VSCode_Script_Runner\smart_erp_qa_v630"
.\Start-Windows.bat
```

4. Visit http://127.0.0.1:8766 and refresh with **Ctrl+Shift+R**.
5. Open **Dashboard** to see the latest script's actual check totals, **Test Cases & Excel** for the executed checks in the exact 11-column layout, and **Reports → View report** for the detailed HTML report in a new tab.
6. Excel and HTML reports are generated from actual stored script events. The old script run is automatically re-read, so its recorded PDF fields can now be shown even without rerunning or modifying ERP records.

## Reporting policy

- Expected, actual and result are shown only for instrumented validations. Printed PDF fields are expanded. `UNMAPPED` and approximate matches are **Needs review**; click-only approval remains **Needs review**.
- New script runs additionally instrument entered-and-confirmed PI quantity, LPO item quantity, unit price and discount percentage, GRN warehouse receipt quantity. Existing gross, discount, tax and net amount checks remain.
- Full print/PDF and trace files generated on new script runs are saved under their run directory. A PDF page overlay syntax bug was corrected.
- Test Case Excel's *Status (Pass/Fail)* remains blank for Needs Review or Blocked; the Actual Result field explains the non-verification.
- The updater creates a timestamped backup, preserves `.env`, local database, reports and existing local Python customizations. It only inserts checks into exact recognized sections and otherwise prints `Not changed (customized source)`.

## Limitations

- We cannot validate live Leocem UI or your previous run's data from local screenshots. A PDF mismatch must be reviewed against the captured PDF before being classified as an ERP bug.
- Any checks that failed before producing an event cannot be reconstructed from console text and will not become a fake Pass.
- Rerunning may create/approve new records and does not roll back prior transactions.
