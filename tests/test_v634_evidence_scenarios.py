"""Offline regression for Leocem scenario choice, annotated evidence and report preview."""
import io
import json
import os
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
from backend import script_runtime as sr, script_workspace as sw
from scripts.migrate_leocem_v634 import migrate

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'working_scripts' / 'procurement' / 'pi_lpo_grn.py'


def test_local_negative_mode_executes_real_guard_without_erp_browser(tmp_path):
    env = dict(os.environ, SMART_ERP_RUN_DIR=str(tmp_path),
               SMART_ERP_RUN_POSITIVE='0', SMART_ERP_RUN_NEGATIVE='1',
               PYTHONPATH=str(ROOT))
    result = subprocess.run([sys.executable, '-m', 'backend.script_child',
                             str(SCRIPT), str(SCRIPT), str(tmp_path)],
                            cwd=ROOT, env=env, text=True, capture_output=True, timeout=25)
    assert result.returncode == 0, result.stderr
    events = [json.loads(x) for x in (tmp_path / 'events.jsonl').read_text().splitlines()]
    checks = [x for x in events if x['kind'] == 'check']
    assert len(checks) == 4
    assert all(x['category'] == 'Negative' and x['status'] == 'PASSED' for x in checks)
    assert all('Local script validation' in x['process'] for x in checks)
    assert not any(x['kind'] == 'stage_start' for x in events)
    assert not (tmp_path / 'trace.zip').exists()  # no browser launched


def test_scenario_support_detected_in_saved_ast():
    info, _ = sw.inspect_source('procurement/pi_lpo_grn.py')
    assert info['supports_negative'] is True and info['valid'] is True


def test_existing_script_migration_does_not_rewrite_edited_file(tmp_path):
    target = tmp_path / 'script.py'
    target.write_bytes(SCRIPT.read_bytes())
    baseline = target.read_bytes()
    assert migrate(target) == []
    assert target.read_bytes() == baseline
    assert 'password_input.fill(username)' in target.read_text()


def test_captured_failed_check_annotates_erp_before_screenshot(tmp_path, monkeypatch):
    monkeypatch.setattr(sr, 'run_directory', lambda: tmp_path)
    page = Mock()
    page.evaluate.return_value = None
    path = sr.capture_failure(page, 'Wrong net amount', '100.00', '95.00')
    assert path.startswith('evidence/') and path.endswith('.png')
    js, payload = page.evaluate.call_args_list[0].args
    assert '4px solid #dc173b' in js
    assert payload == {'label': 'Wrong net amount', 'expected': '100.00', 'actual': '95.00'}
    assert 'evidence' in page.screenshot.call_args.kwargs['path']
    assert page.evaluate.call_count == 2  # cleanup after screenshot


def test_report_html_contains_preview_and_live_values():
    sample = {
        'run': {'id':'a'*32,'module':'Procurement','process':'PI to LPO to GRN',
                'sha256':'b'*64,'script_id':'procurement/pi_lpo_grn.py','status':'FAILED',
                'started_at':'2026-10-28','counts': {'passed':0,'failed':1,'review':0,'blocked':0}},
        'checks': [{'name':'Gross amount','testcase_id':'SCRIPT-0001',
                    'status':'FAILED','expected':'100.00','actual':'90.00',
                    'process':'Local Purchase Order', 'category':'Positive'}],
        'log':'Actual gross not equal expected',
        'evidence':['print_validation/wrong_DYNAMIC_GREEN_RED.pdf', 'evidence/gross_FAIL.png']
    }
    html = sw.report_html(sample)
    assert 'Gross amount' in html and '90.00' in html and '100.00' in html
    assert 'evidence-preview-link' in html and 'evidenceModal' in html
    assert 'Download' in html and '?preview=true' in html
    assert 'PNG' not in html or 'wrong_DYNAMIC_GREEN_RED.pdf' in html


def test_report_evidence_endpoint_is_inline_only_when_preview_requested(tmp_path, monkeypatch):
    from backend.api import app
    from fastapi.testclient import TestClient
    runid = 'a'*32
    run = tmp_path / runid
    (run / 'evidence').mkdir(parents=True)
    (run / 'run.json').write_text(json.dumps({'id':runid, 'status':'FAILED',
                                               'project_id':'leocem_automation','script_id':'procurement/pi_lpo_grn.py'}))
    (run / 'evidence' / 'annotated.png').write_bytes(b'\x89PNG\r\n\x1a\n' + b'test-bytes')
    (run / 'evidence' / 'note.pdf').write_bytes(b'%PDF-1.4\n%%EOF')
    monkeypatch.setattr(sw, 'RUNS', tmp_path)
    client = TestClient(app, base_url='http://127.0.0.1:8766')
    path = '/api/script-workspace/runs/'+runid+'/evidence/evidence/annotated.png'
    inline = client.get(path+'?preview=true')
    assert inline.status_code == 200
    assert 'inline' in inline.headers['content-disposition']
    download = client.get(path)
    assert download.status_code == 200
    assert 'attachment' in download.headers['content-disposition']
    assert client.get('/api/script-workspace/runs/'+runid+'/evidence/../../.env').status_code != 200
    pdf = client.get('/api/script-workspace/runs/'+runid+'/evidence/evidence/note.pdf?preview=true')
    assert pdf.status_code == 200 and 'inline' in pdf.headers['content-disposition']


def test_ui_controls_and_progress_display_are_present():
    workspace = (ROOT / 'frontend' / 'workspace.js').read_text()
    css = (ROOT / 'frontend' / 'navy.css').read_text()
    app = (ROOT / 'frontend' / 'app.js').read_text()
    assert 'data-leocem-scenario="positive"' in workspace
    assert 'data-leocem-scenario="negative"' in workspace
    assert 'data-qa-count' in workspace
    assert 'Total test cases run' in workspace
    assert 'window.qaAnimateNumbers()' in app
    assert 'prefers-reduced-motion' in css
    assert 'evidence-preview-action' in workspace and 'evidenceOverlay' in workspace


def test_api_guards_both_switches_off():
    from backend.api import leocem_run, LeocemLaunch
    with pytest.raises(Exception) as exc:
        leocem_run(LeocemLaunch(reviewed_sha256='a'*64,positive_scenarios=False,
                                negative_scenarios=False,acknowledge_test_transactions=True,
                                acknowledge_trusted_code=True))
    assert 'Select at least one scenario' in str(exc.value)


def test_leocem_dashboard_finds_old_runs_with_different_project_ids(tmp_path, monkeypatch):
    """An earlier registered ERP ID must not make fixed Leocem totals look empty."""
    from backend.api import app
    from fastapi.testclient import TestClient
    from backend import registry
    from backend.module_suite import init_suite_db
    root = tmp_path / ('f' * 32)
    root.mkdir()
    (root / 'run.json').write_text(json.dumps({
        'id': 'f'*32, 'project_id': 'old_saved_erp_project',
        'script_id': 'procurement/pi_lpo_grn.py',
        'module': 'Procurement', 'process': 'PI to LPO to GRN',
        'status': 'FAILED', 'sha256':'c'*64, 'started_at':'2026-10-28T00:00:00Z',
        'counts': {'passed':0,'failed':0,'review':0,'blocked':0}
    }))
    (root / 'events.jsonl').write_text(json.dumps({'kind':'check','name':'Net Amount',
        'status':'FAILED','expected':'100','actual':'92','category':'Positive'}))
    monkeypatch.setattr(sw, 'RUNS', tmp_path)
    monkeypatch.setattr(registry, 'DB', tmp_path / 'registry.sqlite3')
    registry.init_db()
    init_suite_db()
    client = TestClient(app, base_url='http://127.0.0.1:8766')
    rsp = client.get('/api/automation-dashboard?leocem_only=true')
    assert rsp.status_code == 200
    d = rsp.json()
    assert d['latest_script_checks']['total'] == 1
    assert d['latest_script_checks']['failed'] == 1
    assert d['script_run_count'] == 1
