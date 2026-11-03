"""Local trusted-code workspace. A subprocess is isolation, NOT a security sandbox.

Only .py files under working_scripts are eligible. Explicit hash approval and
TEST/STAGING transaction permission are required for every run. Uploaded AI
analysis files remain inert and are not silently promoted to executable code.
"""
from __future__ import annotations
import ast
import hashlib
import html
import io
import json
import os
import re
import signal
import subprocess
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from uuid import uuid4

from dotenv import dotenv_values
from pydantic import BaseModel, Field
from backend.registry import BASE, connect, get_project
from backend.script_runtime import redact

WORKSPACE = BASE / 'working_scripts'
RUNS = BASE / 'reports' / 'script_runs'
ID = re.compile(r'^[a-f0-9]{32}$')
MAX_SOURCE = 250_000


def utc():
    return datetime.now(timezone.utc).isoformat()


def write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.tmp')
    temp.write_text(json.dumps(data, indent=2, default=str), encoding='utf-8')
    temp.replace(path)


def source_path(script_id: str) -> Path:
    root = WORKSPACE.resolve()
    path = (root / script_id).resolve()
    if not path.is_relative_to(root) or path.suffix != '.py' or not path.is_file():
        raise ValueError('Choose an existing .py file inside working_scripts; external paths are not accepted')
    if path.stat().st_size > MAX_SOURCE:
        raise ValueError('Script must be smaller than 250 KB')
    return path


def inspect_source(script_id: str):
    path = source_path(script_id)
    raw = path.read_bytes()
    data = {'id': script_id, 'path': str(path), 'filename': path.name,
            'module': path.relative_to(WORKSPACE.resolve()).parts[0].replace('_', ' ').title()
                      if len(path.relative_to(WORKSPACE.resolve()).parts) > 1 else 'General',
            'process': 'PI to LPO to GRN' if path.name == 'pi_lpo_grn.py' else path.stem.replace('_', ' ').title(),
            'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
            'modified_at': datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(),
            'valid': True, 'supports_existing': False, 'supports_negative': False, 'required_credentials': [], 'warnings': []}
    try:
        tree = ast.parse(raw.decode('utf-8-sig'))
        compile(tree, str(path), 'exec')
        data['functions'] = [n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
        data['supports_negative'] = 'smart_erp_run_negative_scenarios' in data['functions']
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id in ('SMART_ERP_SUPPORTS_EXISTING_SESSION', 'SMART_ERP_REQUIRED_CREDENTIALS'):
                        value = ast.literal_eval(node.value)
                        if target.id == 'SMART_ERP_SUPPORTS_EXISTING_SESSION':
                            data['supports_existing'] = value is True
                        elif isinstance(value, list) and all(isinstance(x, str) for x in value):
                            data['required_credentials'] = value
        data['warnings'].append('Trusted local Python executes with your account permissions. Review it before running.')
        if path.name == 'pi_lpo_grn.py':
            data['warnings'] += ['This complete dependent flow changes accounts for approvals.',
                                  'Approval and submission clicks without final-state assertions remain Needs review.',
                                  'Edits to this file take effect on the next run; running snapshots never change.']
    except (SyntaxError, ValueError, UnicodeDecodeError) as exc:
        data.update(valid=False, error=str(exc))
    return data, raw


def catalog():
    WORKSPACE.mkdir(parents=True, exist_ok=True)
    entries = []
    for path in sorted(WORKSPACE.rglob('*.py'))[:100]:
        if '__pycache__' in path.parts:
            continue
        try:
            entries.append(inspect_source(path.relative_to(WORKSPACE).as_posix())[0])
        except ValueError:
            continue
    return {'root': str(WORKSPACE), 'scripts': entries, 'local_only': True}


class ScriptRunInput(BaseModel):
    project_id: str
    script_id: str = Field(min_length=1, max_length=200)
    reviewed_sha256: str = Field(pattern=r'^[a-f0-9]{64}$')
    mode: Literal['existing', 'new'] = 'existing'
    trust_local_code: bool = False
    allow_test_transactions: bool = False
    initial_role_confirmed: bool = False
    timeout_seconds: int = Field(default=3600, ge=30, le=14400)
    positive_scenarios: bool = True
    negative_scenarios: bool = False
    case_action: str = ""
    case_test_id: str = ""
    case_expected: str = ""
    case_source_sha: str = ""


def normalized_results(directory: Path):
    """Read only real instrumented events, including old run PDF field results.

    Never derive a passing test from console text or a button click.
    """
    events = []
    path = directory / 'events.jsonl'
    if path.exists():
        for line in path.read_text(encoding='utf-8', errors='replace').splitlines()[-20000:]:
            try:
                item = json.loads(line)
                if isinstance(item, dict):
                    events.append(item)
            except json.JSONDecodeError:
                continue

    records = []
    def add(event):
        record = dict(event)
        raw_status = str(record.get('status') or 'REVIEW').upper()
        status = {'PASS': 'PASSED', 'PASSED': 'PASSED',
                  'FAIL': 'FAILED', 'FAILED': 'FAILED', 'FAIL_NO_PDF': 'FAILED',
                  'BLOCKED': 'BLOCKED'}.get(raw_status, 'REVIEW')
        record['status'] = status
        record['testcase_id'] = str(record.get('testcase_id') or ('SCRIPT-' + str(len(records) + 1).zfill(4)))
        record['expected'] = str(record.get('expected') if record.get('expected') is not None else '')
        record['actual'] = str(record.get('actual') if record.get('actual') is not None else 'Not available')
        record.setdefault('process', 'Leocem procurement')
        record.setdefault('category', 'Positive')
        records.append(record)

    for event in events:
        if event.get('kind') not in ('stage_end', 'check', 'print_check', 'blocked'):
            continue
        if event.get('kind') == 'print_check':
            # A previous release summarized the whole PDF as one row and hid
            # individual field results. Keep summary and expand REAL PDF fields.
            summary = dict(event)
            fields = event.get('fields') or []
            if str(summary.get('status')).upper() in ('PASS', 'PASSED'):
                if any(str(f.get('status', '')).upper() not in ('PASS', 'PASSED') or
                       f.get('similarity_percent', 100) < 100 for f in fields):
                    summary['status'] = 'REVIEW'
                    summary['actual'] = 'One or more printed fields need review.'
            add(summary)
            for field in fields:
                raw = str(field.get('status', 'UNMAPPED')).upper()
                status = ('PASSED' if raw == 'PASS' and
                          field.get('similarity_percent', 100) == 100 else
                          'FAILED' if raw == 'FAIL' else 'REVIEW')
                actual = field.get('actual')
                if actual is None:
                    actual = 'NOT LOCATED IN PRINT (UNMAPPED)'
                if raw == 'PARTIAL_MATCH':
                    actual = str(actual) + ' (approximate match; review required)'
                if raw == 'PASS' and field.get('similarity_percent', 100) < 100:
                    actual = str(actual) + ' (approximate item code; review required)'
                add({'kind': 'pdf_field', 'name': str(event.get('name', 'PDF')) +
                     ' | Printed ' + str(field.get('field', 'unknown')).replace('_', ' ').title(),
                     'process': 'PDF Print Validation', 'status': status,
                     'expected': field.get('expected', ''), 'actual': actual,
                     'page': field.get('page'), 'category': 'Positive',
                     'evidence': event.get('evidence')})
        else:
            add(event)
    return records, events


class ScriptManager:
    def __init__(self):
        self.lock = threading.RLock()
        self.active_id = None
        self.process = None
        self.stop_reason = None

    @property
    def busy(self):
        with self.lock:
            return self.active_id is not None

    def start(self, body: ScriptRunInput, controller):
        with self.lock:
            if self.active_id:
                raise ValueError('A script is already running. Wait for completion or stop it first.')
            from backend.module_suite import SUITE_LOCK
            if SUITE_LOCK.locked():
                raise ValueError('An Excel test suite is running. Finish it before starting a script.')
            project = get_project(body.project_id)
            if not project or project['environment'] not in ('test', 'staging'):
                raise ValueError('Select a registered TEST or STAGING project. Production execution is blocked.')
            if not body.trust_local_code or not body.allow_test_transactions:
                raise ValueError('Review trusted local code and explicitly authorize TEST/STAGING transactions')
            info, raw = inspect_source(body.script_id)
            if not info['valid']: raise ValueError(info.get('error', 'Invalid script'))
            if not body.positive_scenarios and not body.negative_scenarios:
                raise ValueError('Switch on Positive or Negative scenarios to run.')
            if body.negative_scenarios and not info.get('supports_negative'):
                raise ValueError('This saved script has no executable negative scenarios. Add reviewed negative checks in VS Code before enabling Negative.')
            if body.reviewed_sha256 != info['sha256']:
                raise ValueError('The saved script changed. Refresh, inspect the new revision, and confirm Run again.')
            env = os.environ.copy()
            # Reload .env for each launch, but do not pass unrelated API secrets.
            for key, value in dotenv_values(BASE / '.env').items():
                if value is not None and key.startswith(('ERPQA_', 'ERP_')):
                    env[key] = value
            for key in list(env):
                if ('API_KEY' in key or 'TOKEN' in key) and not key.startswith('ERP'):
                    env.pop(key, None)
            missing = [key for key in info['required_credentials'] if not env.get(key)]
            if missing:
                raise ValueError('Set these local .env password variables first: ' + ', '.join(missing))
            env.pop('SMART_ERP_CDP_URL', None)
            env.pop('SMART_ERP_TARGET_URL', None)
            if body.mode == 'existing':
                if not info['supports_existing']:
                    raise ValueError('This file does not declare managed-session support. Adapt it or use New browser mode.')
                if not body.initial_role_confirmed:
                    raise ValueError('Confirm the managed browser is already logged in as the script initial account')
                session = controller.call('script_session', project_id=project['id'])
                env['SMART_ERP_CDP_URL'] = session['endpoint']
                env['SMART_ERP_TARGET_URL'] = session['url']
            else:
                # Existing recorder/workflow session is untouched in this mode.
                if controller.call('status').get('recording'):
                    raise ValueError('Stop recording before starting a script')
            ident = uuid4().hex
            directory = RUNS / ident
            directory.mkdir(parents=True)
            (directory / 'source.py').write_bytes(raw)
            meta = {'id': ident, 'script_id': body.script_id, 'project_id': project['id'],
                    'module': info['module'], 'process': info['process'], 'sha256': info['sha256'],
                    'mode': body.mode, 'scenarios': {'positive': body.positive_scenarios, 'negative': body.negative_scenarios},
                    'status': 'RUNNING', 'started_at': utc(), 'ended_at': None,
                    'counts': {'passed': 0, 'failed': 0, 'review': 0, 'blocked': 0},
                    'note': 'Structured script checks are separate from approved Excel test cases.'}
            write_json(directory / 'run.json', meta)
            env.update(SMART_ERP_RUN_DIR=str(directory), ERP_URL=project['url'],
                       SMART_ERP_RUN_POSITIVE='1' if body.positive_scenarios else '0',
                       SMART_ERP_RUN_NEGATIVE='1' if body.negative_scenarios else '0',
                       PYTHONUNBUFFERED='1', PYTHONIOENCODING='utf-8',
                       PYTHONPATH=str(BASE) + os.pathsep + env.get('PYTHONPATH', ''))
            # v6.3.6 reviewed case IDs only; the uploaded Excel text is never Python.
            positive_actions = ('login_only', 'pi_creation', 'pi_approvals', 'lpo_creation', 'full_flow')
            negative_actions = ('neg_pi_all', 'neg_pi_zero', 'neg_pi_negative', 'neg_pi_empty', 'neg_pi_alpha',
                                'neg_po_all', 'neg_po_missing_pi', 'neg_po_missing_vendor',
                                'neg_po_blank_number', 'neg_po_alpha_number', 'neg_po_zero_qty', 'neg_all'
                                'neg_login_all',
                                'neg_login_blank_username',
                                'neg_login_blank_password',
                                'neg_pi_missing_department',
                                'neg_pi_approval_guard',)
            if body.case_action:
                valid_positive = (body.script_id == 'procurement/v636_case_runner.py' and
                                  body.case_action in positive_actions and body.positive_scenarios and not body.negative_scenarios)
                valid_negative = (body.script_id == 'procurement/v636_pi_po_negative.py' and
                                  body.case_action in negative_actions and body.negative_scenarios and not body.positive_scenarios)
                if not (valid_positive or valid_negative):
                    raise ValueError('Case action, reviewed script, and Positive/Negative mode do not agree.')
                if not body.case_test_id or len(body.case_test_id) > 60 or len(body.case_expected) > 2000:
                    raise ValueError('Invalid selected test case reference.')
                env.update(SMART_ERP_CASE_ACTION=body.case_action,
                           SMART_ERP_CASE_ID=body.case_test_id,
                           SMART_ERP_CASE_EXPECTED=body.case_expected,
                           SMART_ERP_CASE_SOURCE_SHA=body.case_source_sha)
            elif body.script_id == 'procurement/v636_case_runner.py':
                raise ValueError('Positive selected-case adapter requires an approved test case.')
            elif body.script_id == 'procurement/v636_pi_po_negative.py':
                if not body.negative_scenarios or body.positive_scenarios:
                    raise ValueError('Negative PI/LPO runner requires Negative mode only.')
            options = {'start_new_session': True} if os.name != 'nt' else {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP}
            self.active_id = ident
            self.stop_reason = None
            try:
                self.process = subprocess.Popen(
                    [sys.executable, '-u', '-m', 'backend.script_child', str(directory / 'source.py'),
                     str(source_path(body.script_id)), str(directory)],
                    cwd=str(BASE), env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT, text=True, encoding='utf-8', errors='replace',
                    shell=False, **options)
            except Exception as exc:
                self.active_id = None
                meta.update(status='ERROR', ended_at=utc(), message=str(exc))
                write_json(directory / 'run.json', meta)
                raise
            timer = threading.Timer(body.timeout_seconds, lambda: self.stop(ident, 'TIMED_OUT'))
            timer.daemon = True
            timer.start()
            threading.Thread(target=self._watch, args=(ident, self.process, timer, env), daemon=True).start()
            return meta

    def _watch(self, ident, process, timer, env):
        directory = RUNS / ident
        log_size = 0
        try:
            with (directory / 'console.log').open('w', encoding='utf-8') as out:
                for line in iter(process.stdout.readline, ''):
                    text = line
                    for key, value in env.items():
                        if len(value) >= 4 and any(k in key for k in ('PASSWORD', 'SECRET', 'TOKEN', 'API_KEY')):
                            text = text.replace(value, '[REDACTED]')
                    if log_size < 8_000_000:
                        out.write(text)
                        out.flush()
                        log_size += len(text.encode('utf-8'))
            code = process.wait()
            records, events = normalized_results(directory)
            counts = {k: sum(r['status'] == v for r in records)
                      for k, v in {'passed': 'PASSED', 'failed': 'FAILED', 'review': 'REVIEW', 'blocked': 'BLOCKED'}.items()}
            meta = json.loads((directory / 'run.json').read_text())
            with self.lock:
                reason = self.stop_reason
            status = (reason or ('FAILED' if code or counts['failed'] else
                       'COMPLETED_REVIEW' if counts['review'] or counts['blocked'] or not records else 'PASSED'))
            meta.update(status=status, exit_code=code, ended_at=utc(), counts=counts)
            write_json(directory / 'run.json', meta)
            write_json(directory / 'results.json', {'run': meta, 'checks': records})
        except Exception as exc:
            meta = json.loads((directory / 'run.json').read_text())
            meta.update(status='ERROR', ended_at=utc(), message=redact(exc))
            write_json(directory / 'run.json', meta)
        finally:
            timer.cancel()
            with self.lock:
                if self.active_id == ident:
                    self.active_id = None
                    self.process = None
                    self.stop_reason = None

    def stop(self, ident=None, reason='STOPPED'):
        with self.lock:
            if not self.active_id or ident and ident != self.active_id:
                return {'stopped': False, 'message': 'No matching active script'}
            self.stop_reason = reason
            process = self.process
            if process and process.poll() is None:
                if os.name == 'nt':
                    subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                                   shell=False, capture_output=True, timeout=15)
                else:
                    os.killpg(process.pid, signal.SIGTERM)
                    try: process.wait(timeout=5)
                    except subprocess.TimeoutExpired: os.killpg(process.pid, signal.SIGKILL)
            return {'stopped': True, 'id': self.active_id,
                    'message': 'Stop requested. Already saved ERP transactions are not rolled back.'}

    def detail(self, ident):
        directory = run_path(ident)
        meta = json.loads((directory / 'run.json').read_text(encoding='utf-8'))
        if meta['status'] == 'RUNNING' and ident != self.active_id:
            meta.update(status='INTERRUPTED', message='Backend restarted; this run is not active. Check ERP before retrying.')
            write_json(directory / 'run.json', meta)
        records, events = normalized_results(directory)
        meta['counts'] = {k: sum(r['status'] == v for r in records)
                          for k, v in {'passed': 'PASSED', 'failed': 'FAILED', 'review': 'REVIEW', 'blocked': 'BLOCKED'}.items()}
        log = directory / 'console.log'
        log_text = ''
        if log.exists():
            with log.open('rb') as stream:
                stream.seek(max(0, log.stat().st_size - 24000))
                log_text = stream.read().decode('utf-8', errors='replace')
        evidence = [p.relative_to(directory).as_posix() for p in directory.rglob('*')
                    if p.is_file() and p.suffix.lower() in ('.png', '.pdf', '.zip')][:200]
        timeline = []
        for event in events:
            if event.get('kind') in ('stage_start', 'stage_end'):
                timeline.append({'at': event.get('at', ''),
                                 'step': event.get('name', 'Unnamed stage'),
                                 'kind': event.get('kind'),
                                 'status': event.get('status', 'STARTED') if event.get('kind') == 'stage_end' else 'STARTED',
                                 'expected': event.get('expected', ''),
                                 'actual': event.get('actual', '')})
        selections = [{'at': e.get('at', ''), 'process': e.get('process', ''),
                       'transaction': e.get('transaction') or '', 'values': e.get('values', {}),
                       'note': e.get('note', '')} for e in events
                      if e.get('kind') == 'erp_values' and isinstance(e.get('values'), dict)]
        return {'run': meta, 'checks': records[-500:], 'timeline': timeline[-500:],
                'selections': selections[-100:], 'log': log_text, 'evidence': evidence}

    def history(self, project_id='', limit=100):
        if not RUNS.exists(): return []
        result = []
        for directory in sorted(RUNS.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:max(1, min(int(limit), 5000))]:
            if ID.fullmatch(directory.name) and (directory / 'run.json').is_file():
                meta = self.detail(directory.name)['run']
                if not project_id or meta['project_id'] == project_id:
                    result.append(meta)
        return result


def run_path(ident):
    if not ID.fullmatch(ident): raise ValueError('Invalid run ID')
    path = RUNS / ident
    if not (path / 'run.json').is_file(): raise ValueError('Run not found')
    return path


def report_rows(detail):
    """Exact 11-column QA template; every row comes from an executed script check."""
    results = []
    for item in detail['checks']:
        status = {'PASSED': 'Pass', 'FAILED': 'Fail'}.get(item['status'], '')
        actual = str(item.get('actual') if item.get('actual') is not None else '')
        if not status:
            actual += ' [' + item['status'] + ': not an independently verified Pass/Fail]'
        results.append([
            detail['run']['module'], item.get('process') or detail['run']['process'],
            item.get('name') or item['testcase_id'], item['testcase_id'],
            item.get('name') or item['testcase_id'],
            'Authorized test/staging environment; script revision ' + detail['run']['sha256'][:12],
            'Execute ' + str(item.get('name') or 'the scripted validation') +
                '; compare actual ERP behavior with expected result',
            str(item.get('expected') or ''), actual, status,
            item.get('category') or 'Positive'
        ])
    return results


def report_excel(detail):
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment
    from openpyxl.utils import get_column_letter
    from backend.module_suite import HEADERS
    book = Workbook()
    sheet = book.active
    sheet.title = 'Test Cases'
    sheet.append(HEADERS)
    for row in report_rows(detail):
        # Avoid Excel formula injection from external ERP values.
        sheet.append(["'" + cell if isinstance(cell, str) and
                      cell[:1] in ('=', '+', '-', '@') else cell for cell in row])
        for cell in sheet[sheet.max_row]:
            cell.alignment = Alignment(vertical='top', wrap_text=True)
            cell.font = Font(color='194C35' if cell.column == 10 and cell.value == 'Pass'
                             else 'AA2536' if cell.column == 10 and cell.value == 'Fail'
                             else '1B3456', size=10)
        sheet.row_dimensions[sheet.max_row].height = 48
    sheet.freeze_panes = 'E2'
    sheet.auto_filter.ref = sheet.dimensions
    sheet.sheet_view.showGridLines = False
    widths = [20, 31, 36, 20, 42, 34, 48, 45, 55, 23, 22]
    for i, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(i)].width = width
    for cell in sheet[1]:
        cell.fill = PatternFill('solid', fgColor='132B50')
        cell.font = Font(color='FFFFFF', bold=True)
        cell.alignment = Alignment(wrap_text=True, vertical='center')
    sheet.row_dimensions[1].height = 32
    note = book.create_sheet('Run Summary')
    note.append(['Test Execution Report field', 'Value'])
    pairs = [('Run ID', detail['run']['id']), ('Source revision', detail['run']['sha256']),
             ('Source', detail['run']['script_id']), ('Execution status', detail['run']['status']),
             ('Executed checks', len(detail['checks'])),
             ('Passed', detail['run']['counts']['passed']),
             ('Failed', detail['run']['counts']['failed']),
             ('Needs review', detail['run']['counts']['review']),
             ('Blocked', detail['run']['counts']['blocked']),
             ('Report policy', 'TEST EXECUTION REPORT: only actual instrumented checks. No fabricated positive/negative tests.'),
             ('Needs review', 'Actions without a final ERP assertion and unmapped PDF fields stay unverified.'),
             ('Test case Excel status', 'Review/Blocked remains blank; the Actual Result column explains why.')]
    for pair in pairs:
        note.append(pair)
    note.column_dimensions['A'].width = 26
    note.column_dimensions['B'].width = 105
    note.freeze_panes = 'A2'
    for cell in note[1]:
        cell.fill = PatternFill('solid', fgColor='132B50')
        cell.font = Font(color='FFFFFF', bold=True)
    for row in note:
        for cell in row: cell.alignment = Alignment(wrap_text=True, vertical='top')
    note.sheet_view.showGridLines = False
    fields_sheet = book.create_sheet('Actual ERP Values')
    fields_sheet.append(['Captured at (UTC)', 'Process', 'Transaction', 'Field', 'Captured value', 'Verification note'])
    for selection in detail.get('selections', []):
        for key, value in selection.get('values', {}).items():
            text = '' if value is None else str(value)
            if text.startswith(('=', '+', '-', '@')): text = "'" + text
            fields_sheet.append([selection.get('at',''), selection.get('process',''), selection.get('transaction',''),
                                 str(key), text, selection.get('note', '')])
    for idx, width in enumerate([27,28,28,27,54,86], 1):
        fields_sheet.column_dimensions[get_column_letter(idx)].width=width
    fields_sheet.freeze_panes='A2'; fields_sheet.sheet_view.showGridLines=False
    fields_sheet.auto_filter.ref=fields_sheet.dimensions
    for cell in fields_sheet[1]:
        cell.fill=PatternFill('solid',fgColor='132B50');cell.font=Font(color='FFFFFF',bold=True)
    for row in fields_sheet.iter_rows(min_row=2):
        for cell in row: cell.alignment=Alignment(wrap_text=True,vertical='top')
    stream = io.BytesIO()
    book.save(stream)
    return stream.getvalue()


def report_html(detail):
    from urllib.parse import quote
    from backend.module_suite import HEADERS
    esc = lambda x: html.escape(str(x), quote=True)
    run = detail['run']
    counts = run.get('counts', {})
    rows = ''.join('<tr>' + ''.join('<td>' + esc(x) + '</td>' for x in row) + '</tr>'
                   for row in report_rows(detail))
    evidence = ''.join('<a class="evidence-preview-link" data-evidence-name="' + esc(path) +
                       '" href="/api/script-workspace/runs/' + esc(run['id']) +
                       '/evidence/' + quote(path, safe='/') + '?preview=true" target="_blank" rel="noopener">' +
                       esc(path) + '</a>' for path in detail.get('evidence', []))
    summary = ''.join('<div class="metric"><small>' + esc(name) + '</small><strong>' +
                      esc(counts.get(key, 0)) + '</strong></div>' for name, key in
                      [('Passed','passed'),('Failed','failed'),('Needs review','review'),('Blocked','blocked')])
    selections = ''.join('<section class="qa-erp-selection"><h3>'+esc(item.get('process',''))+
        ' · '+esc(item.get('transaction',''))+'</h3><p class="muted">'+esc(item.get('note',''))+
        '</p><table class="erp-fields"><thead><tr><th>Field</th><th>Captured value</th></tr></thead><tbody>'+
        ''.join('<tr><td>'+esc(key.replace('_',' ').title())+'</td><td>'+esc(value if value is not None else 'Not captured')+'</td></tr>'
                for key,value in item.get('values',{}).items())+'</tbody></table></section>'
        for item in detail.get('selections',[]))
    timeline = ''.join('<tr><td>'+esc(ev.get('at',''))+'</td><td>'+esc(ev.get('step',''))+'</td>'+
                       '<td>'+esc(ev.get('kind',''))+'</td><td>'+esc(ev.get('status',''))+'</td>'+
                       '<td>'+esc(ev.get('actual',''))+'</td></tr>' for ev in detail.get('timeline', []))
    return """<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Leocem Test Execution Report — Actual Results</title>
<style>body{font:14px system-ui;margin:0;color:#142b4f;background:#f5f7fb}header{background:#132b50;color:white;padding:26px 4%}main{padding:24px 4%}h1{margin:0 0 12px}code{overflow-wrap:anywhere}.row{display:flex;gap:12px;flex-wrap:wrap}.metric{background:white;padding:16px 24px;border:1px solid #dae3ee;border-radius:10px;min-width:120px}.metric small{display:block}.metric strong{font-size:25px}.scroll{overflow:auto;background:white;border:1px solid #dce5ee;border-radius:10px;margin-top:16px}table{border-collapse:collapse;width:100%;min-width:1700px}td,th{text-align:left;padding:12px;border-bottom:1px solid #dfe6ef;vertical-align:top;max-width:310px;overflow-wrap:anywhere}th{background:#eaf0f8;position:sticky;top:0}section{margin-top:24px}a{display:inline-block;color:#174c83;padding:7px}.muted{color:#62748c}.qa-erp-selection{background:#fff;padding:18px;border:1px solid #dce5ee;border-radius:12px;margin:12px 0}.qa-erp-selection h3{margin-top:0}.erp-fields{min-width:0;width:100%}.erp-fields th{position:static}.erp-fields td:first-child{font-weight:700;width:35%}</style>"""+f"""
<header><h1>Leocem · Test Execution Report</h1><div>Status: {esc(run['status'])} · {esc(run.get('started_at',''))}</div><p>Script: {esc(run['script_id'])} · Revision: <code>{esc(run['sha256'][:12])}</code></p></header>
<main><div class="row">{summary}</div><p class="muted">This is the Test Execution Report: actual instrumented script checks, including item calculations, workflow stages and PDF fields. Missing/approximate PDF evidence and click-only approvals are Needs Review, not Pass.</p>
<section><h2>Actual PI / PO / GRN Values Selected by the Script</h2><p class="muted">Fields below were captured by the saved automation during the run; these are not automatically a PASS or proof of final approval. The individual validations below show independently checked expected/actual values.</p>
{selections or '<p class="muted">No structured PI, PO, or GRN selections were recorded in this run. Older saved runs may not include this instrumentation.</p>'}</section>
<section><h2>Actual recorded checks · {len(detail['checks'])}</h2><div class="scroll"><table><thead><tr>{''.join('<th>'+esc(h)+'</th>' for h in HEADERS)}</tr></thead><tbody>{rows or '<tr><td colspan="11">No recorded checks</td></tr>'}</tbody></table></div></section>
<section><h2>Execution steps / timeline (recorded stage events)</h2><p class="muted">These timestamps and results are actual script events. A started stage or clicked approval is not automatically a verified Pass.</p><div class="scroll"><table style="min-width:850px"><thead><tr><th>Timestamp</th><th>Step</th><th>Event</th><th>Result</th><th>Actual detail</th></tr></thead><tbody>{timeline or '<tr><td colspan="5">No stage events were instrumented in this run.</td></tr>'}</tbody></table></div></section>
<section><h2>Evidence / Print PDFs</h2><p class="muted">Click a screenshot or PDF to preview. Download from the top of the preview.</p>{evidence or '<p>No evidence files captured inside this run.</p>'}</section>
<section><h2>Execution log</h2><pre style="white-space:pre-wrap;word-break:break-word;background:#122944;color:#e1efff;padding:20px;border-radius:10px">{esc(detail.get('log',''))}</pre></section></main>""" + """
<div id="evidenceModal" role="dialog" aria-modal="true" aria-label="Evidence preview" hidden style="position:fixed;inset:0;background:#101a2bdc;z-index:9999;padding:24px">
<div style="max-width:1100px;margin:auto;background:white;border-radius:12px;overflow:hidden;display:flex;flex-direction:column;height:calc(100vh - 48px)"><header style="background:#152f52;padding:12px;color:white;display:flex;align-items:center;gap:12px"><strong id="evidenceTitle" style="flex:1">Evidence preview</strong><a id="evidenceDownload" download style="background:white;border-radius:6px;padding:8px;color:#16365e">Download</a><button id="evidenceClose" style="padding:9px;cursor:pointer">Close</button></header><div id="evidenceBody" style="flex:1;overflow:auto;text-align:center;background:#e9edf5"></div></div></div>
<script>(function(){const modal=document.getElementById('evidenceModal'),body=document.getElementById('evidenceBody');function close(){modal.hidden=true;body.replaceChildren();}document.getElementById('evidenceClose').onclick=close;modal.onclick=e=>{if(e.target===modal)close()};document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!modal.hidden)close()});document.querySelectorAll('.evidence-preview-link').forEach(a=>{a.onclick=e=>{const name=a.dataset.evidenceName,lower=name.toLowerCase();if(!lower.endsWith('.png')&&!lower.endsWith('.pdf'))return;e.preventDefault();const url=a.href;document.getElementById('evidenceTitle').textContent=name;document.getElementById('evidenceDownload').href=url.replace('?preview=true','');body.replaceChildren();let view;if(lower.endsWith('.pdf')){view=document.createElement('iframe');view.title='Annotated print PDF preview';view.style.cssText='border:0;width:100%;height:100%';}else{view=document.createElement('img');view.alt='Captured and annotated ERP evidence';view.style.cssText='max-width:100%;height:auto';}view.src=url;body.appendChild(view);modal.hidden=false;};});})();</script>
</html>"""
