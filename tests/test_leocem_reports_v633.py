"""v6.3.3 regression tests: actual script events, not invented Excel cases."""
import io
import json
from pathlib import Path
from openpyxl import load_workbook
from backend import script_workspace as sw
from backend.module_suite import HEADERS
from scripts.migrate_leocem_reporting_v633 import migrate


def make_old_run(tmp_path):
    root = tmp_path / 'reports' / ('a' * 32)
    root.mkdir(parents=True)
    meta = {'id': 'a' * 32, 'script_id': 'procurement/pi_lpo_grn.py', 'project_id': 'leocem_automation',
            'module': 'Procurement', 'process': 'PI to LPO to GRN', 'sha256': 'b' * 64,
            'started_at': '2026-10-28T08:00:00Z', 'status': 'FAILED',
            'counts': {'passed': 0, 'failed': 0, 'review': 0, 'blocked': 0}}
    (root / 'run.json').write_text(json.dumps(meta))
    events = [
        {'kind': 'check', 'name': 'Item Gross Amount', 'status': 'PASSED', 'expected': '120.00', 'actual': '120.00'},
        {'kind': 'check', 'name': 'Item Net Amount', 'status': 'FAILED', 'expected': '135.00', 'actual': '132.00'},
        {'kind': 'stage_end', 'name': 'PI: approve', 'status': 'REVIEW', 'expected': 'approved', 'actual': 'Approve clicked'},
        {'kind': 'print_check', 'name': 'PI approval PDF', 'status': 'FAIL',
         'fields': [{'field': 'department', 'status': 'FAIL', 'expected': 'Roadworks', 'actual': 'Office'},
                    {'field': 'qty', 'status': 'UNMAPPED', 'expected': '12', 'actual': None},
                    {'field': 'item_code', 'status': 'PASS', 'expected': 'ABC12345', 'actual': 'ABC1234', 'similarity_percent': 93}]},
    ]
    (root / 'events.jsonl').write_text('\n'.join(json.dumps(e) for e in events))
    (root / 'console.log').write_text('real execution details')
    return root


def synthetic_detail(tmp_path, monkeypatch):
    root = make_old_run(tmp_path)
    monkeypatch.setattr(sw, 'RUNS', root.parent)
    data = sw.ScriptManager().detail(root.name)
    assert len(data['checks']) == 7
    assert data['run']['counts'] == {'passed': 1, 'failed': 3, 'review': 3, 'blocked': 0}
    qty = next(c for c in data['checks'] if 'Printed Qty' in c['name'])
    assert qty['status'] == 'REVIEW' and 'NOT LOCATED' in qty['actual']
    approx = next(c for c in data['checks'] if 'Printed Item Code' in c['name'])
    assert approx['status'] == 'REVIEW'
    return data


def test_previous_failed_run_is_populated_without_replay(tmp_path, monkeypatch):
    synthetic_detail(tmp_path, monkeypatch)


def test_generated_excel_is_11_columns_and_has_real_values(tmp_path, monkeypatch):
    detail = synthetic_detail(tmp_path, monkeypatch)
    payload = sw.report_excel(detail)
    book = load_workbook(io.BytesIO(payload))
    sheet = book['Test Cases']
    assert [x.value for x in sheet[1]] == HEADERS
    assert sheet.max_row == 8
    assert sheet['E2'].value == 'Item Gross Amount'
    assert sheet['H2'].value == '120.00'
    assert sheet['I2'].value == '120.00'
    assert sheet['J2'].value == 'Pass'
    assert sheet['J3'].value == 'Fail'
    assert sheet['J4'].value == '' or sheet['J4'].value is None
    assert 'NOT LOCATED' in sheet['I7'].value
    assert 'Run Summary' in book.sheetnames
    assert sheet['A1'].fill.fgColor.rgb.endswith('132B50')


def test_html_view_has_11_columns_and_escapes_erp_text(tmp_path, monkeypatch):
    detail = synthetic_detail(tmp_path, monkeypatch)
    detail['checks'][0]['actual'] = '<script>alert(1)</script>'
    output = sw.report_html(detail)
    assert 'Leocem' in output and 'Item Gross Amount' in output
    assert 'Printed Qty' in output
    assert 'Status (Pass/Fail)' in output
    assert '&lt;script&gt;' in output
    assert '<script>alert(1)</script>' not in output


def test_script_instrumentation_is_idempotent_and_preserves_login(tmp_path):
    package = Path(__file__).resolve().parents[1]
    source = (package / 'working_scripts/procurement/pi_lpo_grn.py').read_text()
    script = tmp_path / 'copy.py'
    script.write_text(source)
    old = script.read_bytes()
    assert migrate(script)['applied'] == []
    assert script.read_bytes() == old
    assert 'password_input.fill(username)' in script.read_text()
    assert "messages.join('\\\\n')" in script.read_text()


def test_ui_has_leocem_cases_and_report_link():
    root = Path(__file__).resolve().parents[1]
    js = (root / 'frontend/workspace.js').read_text()
    assert 'function leocemTestCasesPage' in js
    assert '/export/html?view=true' in js
    assert 'recent_script_checks' in js
    assert 'latest_script_checks' in js


def test_view_report_opens_inline_and_dashboard_reads_run(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from backend.api import app
    from backend import registry
    from backend.module_suite import init_suite_db
    root = make_old_run(tmp_path)
    monkeypatch.setattr(sw, 'RUNS', root.parent)
    monkeypatch.setattr(registry, 'DB', tmp_path / 'db' / 'erpqa.sqlite3')
    registry.init_db()
    init_suite_db()
    registry.save_project(registry.Project(
        id='leocem_automation', name='Test Leocem', appName='Leocem',
        url='https://staging.kagamierp.com/leocem', environment='test'))
    client = TestClient(app, base_url="http://127.0.0.1:8766")
    resp = client.get('/api/script-workspace/runs/' + root.name + '/export/html?view=true')
    assert resp.status_code == 200
    assert resp.headers['content-disposition'].startswith('inline')
    assert 'Printed Department' in resp.text
    resp = client.get('/api/script-workspace/runs/' + root.name + '/export/xlsx')
    assert resp.status_code == 200 and resp.content[:2] == b'PK'
    resp = client.get('/api/automation-dashboard?project_id=leocem_automation')
    assert resp.status_code == 200
    data = resp.json()
    assert data['latest_script_checks']['total'] == 7
    assert data['latest_script_checks']['failed'] == 3
    assert data['recent_script_checks']
