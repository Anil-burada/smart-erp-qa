# Smart ERP QA v6.3.6 — test design, captured ERP inputs, day/week/month QA analytics

- **Test Case Report:** numbered, source-aligned procedures and expected outcomes, separate from run status. The Excel plan has 11 columns and intentionally blank Actual/Status.
- **Test Execution Report:** individual verification events, and an additional **Actual ERP Values** section showing PI, LPO and GRN selected values captured by the saved Python script. The Excel execution workbook also contains an `Actual ERP Values` tab. These are *recorded selections*, not evidence of final approval or persistence.
- **Dashboard:** time-stamped reports in India Standard Time, daily/weekly/monthly selector and date picker, navy-themed dimensional pie chart for Passed / Failed / Needs Review / Blocked, and an actual run-level result table. Empty periods show zero without simulated records.
- **Preservation:** Upgrade-To-v636-Windows.ps1 backs up the project and preserves existing .env, database, saved history and the user's customized VS Code script. It only adds a small transaction-capture section to the script if standard insertion anchors are still present; otherwise it reports a warning, preserving custom code.
- Report-value capture will populate **new** runs. Historic runs cannot show PI/PO/GRN values that were never persisted in structured events.
- Date ranges include the selected calendar day, Monday–Sunday week, or calendar month, in IST. A run is counted in the period when it started, not its completion date.
- The pie is a dimensional CSS visualization of actual check counts, not a claim that every automation completed successfully.
- No account/password fields added. The user-authored Python script retains its login logic. Run authorization and TEST/STAGING target checks remain enforced.
