"""v6.3.5: planned test cases are distinct from actual execution evidence."""
from __future__ import annotations
import io
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from backend import leocem_test_case_report as plan, script_workspace as sw
from backend.api import app
from backend.module_suite import HEADERS


def test_documented_cases_have_numbered_steps_and_blank_results():
    result = plan.definition()
    assert result['cases']
    assert all(c['steps'] and c['precondition'] and c['expected'] for c in result['cases'])
    assert len({c['testcase_id'] for c in result['cases']}) == len(result['cases'])
    assert any(c['category'] == 'Negative' for c in result['cases'])
    assert any('Gross' in c['title'] for c in result['cases'])
    assert all(c['mapped'] for c in result['cases'])  # packaged script has every referenced function
    data = plan.rows(result)
    assert len(data[0]) == 11
    assert '1. ' in data[0][6] and '2. ' in data[0][6]
    assert all(row[8] == '' and row[9] == '' for row in data)  # NO invented Pass/Fail


def test_test_case_report_excel_has_11_columns_and_no_invented_status():
    book = load_workbook(io.BytesIO(plan.excel(plan.definition())))
    sheet = book['Test Case Plan']
    assert [cell.value for cell in sheet[1]] == HEADERS
    assert sheet.max_row == len(plan.CASES) + 1
    assert all(sheet.cell(r, 9).value is None and sheet.cell(r, 10).value is None
               for r in range(2, sheet.max_row+1))
    assert 'not actual run results' in book['About This Plan']['B4'].value.lower()


def test_html_report_is_step_by_step_and_not_actual_results():
    html = plan.html_report(plan.definition())
    assert 'Test Case Report' in html
    assert 'Test steps' in html and '<ol>' in html
    assert 'Expected result' in html
    assert 'Execution Report' in html


def test_report_endpoints_are_distinct():
    client = TestClient(app, base_url="http://127.0.0.1:8766")
    plan_view = client.get('/api/leocem/test-case-report/html')
    assert plan_view.status_code == 200 and 'Test Case Report' in plan_view.text
    plan_sheet = client.get('/api/leocem/test-case-report/xlsx')
    assert plan_sheet.status_code == 200
    assert 'attachment' in plan_sheet.headers['content-disposition']
    book = load_workbook(io.BytesIO(plan_sheet.content))
    assert book['Test Case Plan'].max_row > 1
    json_view = client.get('/api/leocem/test-case-report/json')
    assert json_view.status_code == 200 and len(json_view.json()['cases']) == len(plan.CASES)
    assert client.get('/api/leocem/test-case-report/unknown').status_code == 400


def test_execution_report_retains_only_actual_recorded_checks():
    sample={'run':{'id':'a'*32,'module':'Procurement','process':'PI to LPO to GRN',
                   'sha256':'b'*64,'script_id':'procurement/pi_lpo_grn.py','status':'FAILED',
                   'started_at':'2026-10-28','counts':{'passed':0,'failed':1,'review':0,'blocked':0}},
            'checks':[{'name':'LPO Gross Amount','testcase_id':'SCRIPT-0001','status':'FAILED',
                       'expected':'125.00','actual':'115.00','category':'Positive'}],
            'timeline':[{'at':'2026-10-28T13:22Z','step':'LPO Creation','kind':'stage_end',
                         'status':'FAILED','actual':'Validation failed'}],
            'evidence':[], 'log':'ERP returned 115.00'}
    view=sw.report_html(sample)
    assert 'Test Execution Report' in view
    assert 'Execution steps / timeline' in view
    assert 'LPO Gross Amount' in view and '125.00' in view and '115.00' in view
    assert 'Validation failed' in view
    assert len(sw.report_rows(sample)) == 1


def test_frontend_has_both_buttons_and_pages():
    from pathlib import Path
    content=(Path(__file__).parents[1]/'frontend/workspace.js').read_text()
    assert 'View Test Case Report' in content
    assert 'View Latest Execution Report' in content
    assert 'Test Case Report = what to test' in content
    assert 'Go to Test Execution Reports' in content
