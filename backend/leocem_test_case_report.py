"""Documented step-by-step Leocem test-case design, distinct from execution results.

Do not use this module to infer that an ERP step passed. The list describes
how the supplied workflow is intended to be tested and is cross-checked against
the saved Python source's top-level function names, without executing it.
"""
from __future__ import annotations
from dataclasses import dataclass
from io import BytesIO
import html
from backend import script_workspace as sw
from backend.module_suite import HEADERS


@dataclass(frozen=True)
class Case:
    id: str
    process: str
    scenario: str
    title: str
    precondition: str
    steps: tuple[str, ...]
    expected: str
    functions: tuple[str, ...]
    category: str = 'Positive'


CASES = (
    Case('LEO-TC-001', 'Authentication', 'Sign in with test account', 'Login to Leocem',
         'Authorized TEST/STAGING URL; existing configured script login',
         ('Open the configured Leocem login page in Chromium', 'Enter the test username and the password using the saved script logic',
          'Submit the login form', 'Verify the ERP navigation/sidebar becomes visible'),
         'Authenticated ERP page visible; not just a Login click', ('login',)),
    Case('LEO-TC-002', 'Purchase Indent', 'Create and submit PI', 'Create Purchase Indent',
         'Authorized test user signed in; available item masters',
         ('Search for Purchase Indent Creation and open CREATE',
          'Select indent type, department, purchase type, section, asset, required date and narration',
          'Add an item and enter a positive indent quantity',
          'Verify quantity is retained, then confirm item editor',
          'Save PI and identify the newly generated PI number',
          'Select that exact PI and click SUBMIT',
          'Verify the PI detail view contains the generated PI number'),
         'New PI number identified and visible in PI detail; submit clicked (final approval status needs separate verification)',
         ('create_indent', 'enter_purchase_indent_quantity', 'commit_purchase_indent_item')),
    Case('LEO-TC-003', 'Purchase Indent Approval', 'Sequential PI approvals', 'Approve the exact Purchase Indent',
         'New PI submitted; authorized approval accounts are available',
         ('Sign out of the previous role and sign in as an authorized approver',
          'Open Purchase Indent Approval', 'Find and select the exact newly generated PI number',
          'Click Approve and capture action/evidence',
          'Repeat for the script-defined approval roles where applicable',
          'Verify final approval status/audit trail separately'),
         'Exact PI selected; approval actions recorded. Final approval is Pass only with ERP status/audit evidence',
         ('approve_indent', 'logout', 'login')),
    Case('LEO-TC-004', 'Local Purchase Order', 'Create LPO for approved PI', 'Create Local Purchase Order',
         'Approved PI available for Local Purchase Order',
         ('Open LPO Creation and click CREATE', 'Select purchase category, PI reference, department and exact PI number',
          'Select vendor and payment terms; enter a unique PO number',
          'Open PO item details; enter quantity, unit price, PGST and discount percentage',
          'Verify inputs have not reset', 'Save only if calculation validations pass',
          'Identify the newly saved LPO transaction from the list'),
         'LPO number identified and linked to the intended PI; Save is not treated as verified persistence until the row is found',
         ('create_lpo', 'capture_created_lpo_number')),
    Case('LEO-TC-005', 'LPO Item Calculations', 'Validate amounts for a PO item', 'Verify Quantity, Rate, Gross, Discount, Tax and Net',
         'LPO item editor open with numeric values and PGST selection',
         ('Read entered quantity, rate and discount percentage',
          'Calculate expected Gross = Quantity × Unit Price',
          'Calculate expected Discount = Gross × Discount% / 100',
          'Calculate expected Tax = (Gross − Discount) × configured tax rate / 100',
          'Calculate expected Net = Gross − Discount + Tax',
          'Compare each ERP displayed amount with calculated expected value',
          'Highlight any mismatch and capture evidence before save'),
         'Each displayed calculation matches expected amount within configured tolerance; mismatches are recorded as Fail',
         ('validate_item', 'compare', 'validate_then_save')),
    Case('LEO-TC-006', 'LPO Summary', 'Verify PO header totals', 'Validate LPO Summary Amounts',
         'LPO line calculations verified and item editor committed',
         ('Read summary Gross, Discount, Tax, Charges and Net Amount',
          'Compute expected summary totals from verified item values and configured charges',
          'Compare actual ERP summary against expected values',
          'Block PO save if a required comparison is wrong or unreadable'),
         'Correct summary amount values; mismatches captured and no false Pass',
         ('validate_summary', 'validate_then_save')),
    Case('LEO-TC-007', 'LPO Submit and Approval', 'Submit and approve exact LPO', 'Submit and Approve Local Purchase Order',
         'New LPO saved and exact transaction number captured',
         ('Select exact generated LPO from creation list and click SUBMIT',
          'Switch to each authorized approval role using script login/logout',
          'Open Purchase Order / LPO Approval', 'Locate same exact LPO transaction',
          'Select row and click Approve once per role',
          'Verify final ERP status/audit trail separately'),
         'Submission and approval actions apply to the intended LPO; status not claimed from clicks alone',
         ('submit_lpo', 'approve_lpo')),
    Case('LEO-TC-008', 'Goods Receipt Note', 'Create GRN against same LPO', 'Create Goods Receipt Note',
         'Approved LPO available for receipt; vendor/warehouse masters configured',
         ('Open Goods Receipt Note creation and click CREATE',
          'Select Local PO reference and matching saved PO vendor master',
          'Select the exact approved LPO transaction from its dropdown',
          'Enter invoice number and required invoice date',
          'Edit GRN item details and warehouse details; confirm each editor with OK',
          'Save GRN and identify generated GRN number'),
         'GRN linked to exact approved LPO with correct vendor, item and warehouse; saved number identified',
         ('save_grn_from_lpo', 'finish_grn_from_invoice_date', 'find_new_grn')),
    Case('LEO-TC-009', 'GRN Submission', 'Submit saved GRN', 'Submit Goods Receipt Note',
         'New GRN saved and identified',
         ('Locate the exact newly saved GRN transaction',
          'Select the matching GRN and click SUBMIT',
          'Check submission status/record details, if available'),
         'Exact GRN is submitted; final persisted status requires ERP confirmation',
         ('submit_saved_grn',)),
    Case('LEO-TC-010', 'ERP Print Validation', 'Compare printed documents to source values', 'Validate PI/LPO/GRN Print Fields',
         'A real PDF was captured from a print action; source values are available',
         ('Capture the ERP-generated PDF response/download when available',
          'Find uniquely mapped labels for transaction, date, department, item and amounts',
          'Compare printed values with the source data',
          'Draw red rectangles for mismatches and green for verified matches',
          'Save annotated PDF and evidence; mark unreadable/unmapped fields Needs Review'),
         'Actual printed values match source where mapped; mismatches are Fail, missing evidence is Needs Review',
         ('validate_erp_print_pdf', 'monitor_print_action')),
    Case('LEO-TC-011', 'Local Negative Guards', 'Reject invalid PI quantities locally', 'Validate Invalid Quantity Inputs (Local Only)',
         'Script quantity validation helper available; no ERP browser required',
         ('Invoke the local PI quantity validator with the script-defined invalid cases',
          'Confirm each invalid value raises the expected validation error',
          'Record each local test independently without creating ERP transactions'),
         'Invalid quantity rejected locally. This is NOT a negative test of Leocem form behavior',
         ('validate_pi_quantity', 'smart_erp_run_negative_scenarios'), 'Negative'),
)



# These revised steps follow main() and the supported functions in the packaged source.
# If the user customizes that source, the planned report must be reviewed again.
SOURCE_ALIGNED_STEPS = {
 'LEO-TC-002': (
   'Sign in as DMG0013; open Global Search and navigate to PurchaseIndent Creation',
   'Click CREATE; choose Indent Type and Department using the script round-robin selection',
   'Choose Purchase Type = Local Purchase; select Section and Asset (round-robin)',
   'Set Required Date to today in IST (dd/mm/yyyy); enter the configured record narration',
   'Open item editor; select the round-robin Item and capture its UOM if available',
   'Enter configured positive indent quantity and verify it remains after Tab',
   'Click the item editor OK and confirm the item editor closes',
   'Click Save, identify exactly one NEW generated PI transaction in the grid',
   'Select the exact newly saved PI, click SUBMIT, and confirm its transaction appears in the PI detail view'),
 'LEO-TC-003': (
   'For the submitted PI, return from its detail view to Purchase Indent Approval',
   'While signed in as DMG0013, select the exact generated PI and click Approve',
   'Sign out, sign in as DMG0041, open PI Approval and approve the same PI',
   'Sign out, sign in as DMG0051, open PI Approval and approve the same PI',
   'For each approval, collect the scripted click result; check persisted ERP status/audit trail separately (click-only is Needs Review)'),
 'LEO-TC-004': (
   'Sign out and log in as DMG0041; open LPO Creation and click CREATE',
   'Select Purchase Category by round-robin, PO Reference = PurchaseIndent, same PI Department and exact PI transaction',
   'Select the Vendor and Payment Terms by round-robin; enter a generated four-digit PO number',
   'Enter narration and open Local PO Details using its Edit icon',
   'Enter quantity copied from the PI and a generated unit price, select PGST, enter generated discount percentage',
   'Verify Quantity, Unit Price and Discount% remain populated after ERP recalculation',
   'Validate line-item Gross, Discount Amount, Tax Amount and Net Amount',
   'Confirm the item editor, validate LPO summary totals, and click Save only if checks pass',
   'Identify the newly saved LPO number from a unique new list row; do not reuse a prior PO'),
 'LEO-TC-007': (
   'Select the exact newly saved LPO in LPO Creation and click SUBMIT',
   'While DMG0041 is signed in, approve that exact LPO in LPO Approval',
   'Switch account to DMG0013 and approve that exact LPO',
   'Switch account to DMG0051 and approve that exact LPO',
   'Switch account to DMG0052 and approve that exact LPO',
   'Capture each click-only outcome as Needs Review until ERP status/audit evidence confirms success'),
 'LEO-TC-008': (
   'Sign out of DMG0052 and sign in as DMG0041; open Goods Receipt Note and click CREATE',
   'Select GRN Reference = Local PO',
   'Select the EXACT vendor saved on the LPO by clicking its matching vendor-master option',
   'Select the EXACT generated LPO transaction in the Local PO dropdown',
   'Enter a generated four-digit Invoice No; set Invoice Date to today in IST',
   'Enter the GRN description and open the item/warehouse editors',
   'Enter the warehouse received quantity equal to the saved LPO quantity; verify it is retained',
   'Click OK in Warehouse Details, then GRN Item Details; confirm both editors close',
   'Click SAVE and identify exactly one newly generated GRN transaction'),
 'LEO-TC-009': (
   'From the GRN list, identify the exact newly saved GRN transaction',
   'Select that GRN only and click SUBMIT',
   'Record the click outcome; obtain saved ERP submission status separately rather than counting a click as Pass'),
 'LEO-TC-010': (
   'Before each configured create/submit/approval action, note the existing count of captured PDF documents',
   'Capture only actual ERP PDF downloads, network responses, or resolvable PDF embeds',
   'Compare mapped PI, LPO or GRN fields with the values recorded at creation; include PI item/quantity fields when printable layout permits',
   'Draw green rectangles on verified printed values and red rectangles on mismatches, saving an annotated PDF',
   'Capture screenshots for mismatches; mark unmapped/missing/ambiguous PDF values as Needs Review, not Pass',
   'Open the annotated PDF in the report preview; verify visually that the right printed field was marked'),
}

def definition():
    """A test design: steps and expected results, never execution success."""
    source, _ = sw.inspect_source('procurement/pi_lpo_grn.py')
    names = set(source.get('functions', []))
    cases = []
    for case in CASES:
        mapped = source['valid'] and all(n in names for n in case.functions)
        steps = SOURCE_ALIGNED_STEPS.get(case.id, case.steps)
        cases.append({'testcase_id': case.id, 'module': 'Procurement', 'process': case.process,
                      'scenario': case.scenario, 'title': case.title,
                      'precondition': case.precondition,
                      'steps': list(steps), 'expected': case.expected,
                      'category': case.category, 'mapped': mapped, 'functions': list(case.functions)})
    return {'source': source['id'], 'revision': source['sha256'], 'cases': cases,
            'note': 'Test Case Report is a documented plan, not execution evidence. Empty Actual Result and Status are intentional. Confirm steps against your saved source if you customize it.'}


def rows(plan):
    return [[c['module'], c['process'], c['scenario'], c['testcase_id'], c['title'],
             c['precondition'], '\n'.join(f'{idx}. {step}' for idx, step in enumerate(c['steps'], 1)),
             c['expected'], '', '', c['category']] for c in plan['cases']]


def excel(plan):
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Alignment
    from openpyxl.utils import get_column_letter
    book = Workbook(); sheet = book.active; sheet.title = 'Test Case Plan'
    sheet.append(HEADERS)
    for row in rows(plan):
        sheet.append(["'" + str(x) if isinstance(x, str) and x[:1] in ('=', '+', '-', '@') else x for x in row])
        for cell in sheet[sheet.max_row]:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            cell.font = Font(name='Aptos', size=10, color='18365B')
        sheet.row_dimensions[sheet.max_row].height = min(175, 26 * max(2, len(row[6].splitlines())))
    for idx, width in enumerate([20,28,37,19,43,44,90,82,26,26,22], 1):
        sheet.column_dimensions[get_column_letter(idx)].width = width
    for c in sheet[1]:
        c.fill = PatternFill('solid', fgColor='142E52'); c.font = Font(name='Aptos', color='FFFFFF', bold=True)
        c.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[1].height = 31
    sheet.freeze_panes = 'G2'; sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.showGridLines = False
    meta = book.create_sheet('About This Plan')
    for line in [('Report', 'TEST CASE REPORT — Step-by-step design'),
                 ('Source script', plan['source']), ('Saved revision SHA256', plan['revision']),
                 ('Executed?', 'NO — this report documents planned scenarios, not actual run results.'),
                 ('Actual Result / Status', 'Blank by design; see Test Execution Report for actual results.'),
                 ('Negative scenarios', 'Local quantity guard only; not ERP form-level negative testing.')]:
        meta.append(line)
    meta.column_dimensions['A'].width = 28; meta.column_dimensions['B'].width = 110
    for c in meta[1]: c.fill = PatternFill('solid', fgColor='142E52'); c.font = Font(color='FFFFFF', bold=True)
    meta.sheet_view.showGridLines = False
    stream = BytesIO(); book.save(stream); return stream.getvalue()


def html_report(plan):
    esc = lambda value: html.escape(str(value), quote=True)
    cards = []
    for case in plan['cases']:
        lis = ''.join('<li>' + esc(step) + '</li>' for step in case['steps'])
        tag = 'Source functions located' if case['mapped'] else 'Script mapping needs review'
        cards.append(f'''<section class="case"><div class="case-head"><div><small>{esc(case['testcase_id'])} · {esc(case['process'])} · {esc(case['category'])}</small><h2>{esc(case['title'])}</h2></div><span class="tag">{tag}</span></div>
        <p><b>Precondition:</b> {esc(case['precondition'])}</p><h3>Test steps</h3><ol>{lis}</ol>
        <p><b>Expected result:</b> {esc(case['expected'])}</p><p class="muted">Actual result and status: Not recorded in this document.</p></section>''')
    return f'''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Leocem Test Case Report — Step-by-step</title>
    <style>body{{font:15px system-ui;color:#162e50;background:#f3f6fa;margin:0}}header{{background:#142e52;color:white;padding:28px max(24px,5%)}}main{{max-width:1000px;margin:25px auto;padding:0 20px}}.case{{background:white;border:1px solid #dbe4ef;border-radius:12px;padding:22px;margin:15px 0}}h1{{margin:0 0 9px}}h2{{margin:5px 0}}h3{{font-size:15px;margin-bottom:5px}}li{{line-height:1.6;padding:3px}}.case-head{{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}}small,.muted{{color:#60778f}}header small{{color:#c5d6e8}}.tag{{border:1px solid #ccdbea;border-radius:30px;padding:8px 12px;font-size:12px;height:max-content}}a{{color:#10406a}}@media print{{.action{{display:none}}}} </style>
    <header><small>SMART ERP QA · LEOCEM PROCUREMENT</small><h1>Test Case Report</h1><p>Step-by-step test-case design — NOT a record of executed outcomes.</p><p>Source revision: {esc(plan['revision'][:12])} · {len(cards)} defined scenarios</p></header>
    <main><p class="action"><a href="/api/leocem/test-case-report/xlsx">Download Test Case Excel (11 columns)</a></p><p>Actual results, PASS/FAIL and screenshots belong in the separate <strong>Test Execution Report</strong> for each run. A mapped script function does not mean its workflow passed.</p>{''.join(cards)}</main></html>'''
