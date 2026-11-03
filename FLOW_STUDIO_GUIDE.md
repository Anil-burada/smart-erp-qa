# v6.1.4 — Manual ERP Flow Learning (Purchase Indent to GRN)

This version adds **Business Flows** to the dashboard. It works with the existing Playwright recorder and per-project JSON locator libraries. The engine is shared across ERP applications; recorded workflows and locators are **not** shared blindly across different websites.

## Start on Windows

1. Extract the entire ZIP and open the `smart_erp_qa_v614_full_windows` folder in VS Code.
2. Run `Install-Windows.bat` if not installed on this laptop; otherwise `Start-Windows.bat`.
3. Open `http://127.0.0.1:8766`.
4. Register an authorized **TEST/STAGING** ERP. Under Browser Session, click **Open ERP** and log in directly in Playwright's browser window. Password fields are not captured.
5. Under **Workflows**, choose **Start Fresh Recording**. Perform **one business stage** (e.g. `pi_create`), then **Finish Demonstration & Save JSON**.
6. Inspect all recorded locators and steps. Add required **assertions** and runtime **capture** steps (see below). Verify locators on their respective pages; approve the workflow after review.
7. Repeat for `pi_approve`, `po_create`, `po_approve`, `grn_create`, `grn_verify`, or whichever stages your ERP actually uses. This stage order is an example, not a mandatory ERP model.
8. Open **Business Flows** → choose ERP → **New Indent-to-GRN Flow**. Replace `replace_me` workflow names with your saved, reviewed names, remove phases not used by this ERP, and **Save Flow Mapping**.
9. Enter non-secret runtime test data such as `{ "quantity": 10 }` if a workflow uses `${quantity}`. Click **Validate Dependencies**. Fix all listed issues before execution.
10. Prepare the existing authenticated browser at the **first recorded step's screen**. Click **Stop Passive Capture for Replay** (it discards only unsaved temporary actions; saved workflows and login are preserved), check authorization, then click **Run Validated Business Flow**. It runs the approved stages in order, stops on the first failure, captures a trace/screenshot from failed replay, and adds a record to the reporting dashboard.

## Linking documents across stages

A recorder knows the click/field sequence; it **does not independently know** which value is the new PI/PO/GRN document number. To link records, add a reviewed step to the workflow's JSON:

```json
{"action":"capture_text","target":"pi_create.step_012","output":"pi_number"}
```

That `target` must point to the exact PI number element in the approved project's locator library. For schema-v1 workflows use `locator` instead of `target`. The `capture_text` action stores the document number in memory for that single replay (maximum 150 characters). In a later workflow, replace the recorded PI reference value with:

```json
{"action":"fill","target":"po_create.step_004","value":"${pi_number}"}
```

Both stages must have **explicit assertions** such as `assert_visible`, `assert_text` or `assert_value` after the final business action. The system requires assertions to reduce false passes; they remain app-specific and must be verified manually. Adding a capture step alone is not an assertion.

After changing a workflow, review and approve again. Changing a locator invalidates the workflow's fingerprint, requiring another review.

## Reusable script (optional)

From PowerShell within the project root:

```powershell
.\.venv\Scripts\python.exe -m scripts.run_business_flow --project your_project_id --flow indent_to_grn
```

This script opens Playwright, lets you log in manually, confirms transaction authorization, and runs the **same generic engine** using each ERP's own JSON map. For a different ERP, create another registered project and map different stage workflows to the same conceptual phases. No passwords or ERP-specific selectors are hardcoded in the script.

## Important limits

- There is **no universal automatic understanding** of every ERP's business rules, page layout, approvals, dynamic grids, popups, shadow DOM, or iframe controls.
- New windows/iframes, rich custom dropdowns and some control types may need manual locator work. The recorder reports warnings rather than guessing.
- The screen shown at the start of replay must match the first recorded action. The runner will not auto-guess navigation; your previous `Procurement` button error must still be corrected against the actual ERP screen.
- **Flow Studio uses one logged-in account** for all stages. Separate PI/PO approval users need existing **Approval Plans** with verified login/logout selectors and local credential aliases, never passwords in workflow JSON.
- Workflows with `Save`, `Create`, `Approve`, `Receive` or `Post` may modify test ERP data. Execution requires explicit authorization, and the runner never retries a failed state-changing action.
- The reporting dashboard counts **workflow/flow executions**, not automatically inferred positive/negative test-case results. Explicit business assertions and test cases are needed to assess ERP correctness.
- Your existing laptop's project registry, workflows, captured records, and traces are **not automatically bundled** into this generic deployment. Stop the old server and copy `data`, `projects`, `workflows`, `approval_plans`, and `flows` from your working project if you want to migrate them. Do not casually copy `.env` or secrets.
