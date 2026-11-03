"""Trusted-script regression checks. All test programs are local synthetic code."""
import hashlib
import io
import json
import time
from pathlib import Path

import pytest
from openpyxl import load_workbook
from backend import registry, script_workspace as sw


class IdleBrowser:
    def call(self, name, **kwargs):
        if name == 'status': return {'open': False, 'recording': False}
        raise ValueError('No managed browser')


@pytest.fixture
def work(tmp_path, monkeypatch):
    root = tmp_path / 'working_scripts'
    root.mkdir()
    monkeypatch.setattr(sw, 'WORKSPACE', root)
    monkeypatch.setattr(sw, 'RUNS', tmp_path / 'reports')
    monkeypatch.setattr(registry, 'DB', tmp_path / 'data' / 'erpqa.sqlite3')
    registry.init_db()
    registry.save_project(registry.Project(id='qa1',name='Local synthetic test',appName='Test',url='http://127.0.0.1:8766/mock'))
    manager = sw.ScriptManager()
    yield root, manager
    manager.stop()
    for _ in range(100):
        if not manager.busy: break
        time.sleep(.05)


def put(root, source):
    path = root / 'sample.py'
    path.write_text(source, encoding='utf-8')
    return sw.inspect_source('sample.py')[0]


def body(info, **changes):
    data = dict(project_id='qa1',script_id=info['id'],reviewed_sha256=info['sha256'],
                mode='new',trust_local_code=True,allow_test_transactions=True)
    data.update(changes)
    return sw.ScriptRunInput(**data)


def wait(manager, run):
    deadline = time.monotonic()+15
    while manager.busy and time.monotonic() < deadline: time.sleep(.05)
    assert not manager.busy, 'Synthetic script did not finish'
    return manager.detail(run['id'])


def test_static_analysis_does_not_run_imports(work):
    root, manager = work
    marker = root / 'unexpected'
    info = put(root, f'from pathlib import Path\nPath({str(marker)!r}).write_text("bad")\n')
    assert info['valid'] and not marker.exists()


@pytest.mark.parametrize('path', ['../outside.py','/etc/passwd','sample.txt','missing.py'])
def test_paths_are_scoped(work, path):
    with pytest.raises(ValueError): sw.source_path(path)


def test_symlink_outside_workspace_blocked(work, tmp_path):
    root, _ = work
    outside=tmp_path/'outside.py';outside.write_text('print(1)')
    (root/'linked.py').symlink_to(outside)
    with pytest.raises(ValueError):sw.source_path('linked.py')


def test_invalid_python_is_visible_but_not_executable(work):
    root, manager=work
    info=put(root,'def nope(\n')
    assert not info['valid']
    with pytest.raises(ValueError):manager.start(body(info),IdleBrowser())


def test_changed_revision_requires_confirmation(work):
    root, manager=work
    info=put(root,'print("old")\n')
    put(root,'print("new")\n')
    with pytest.raises(ValueError,match='changed'):manager.start(body(info),IdleBrowser())


@pytest.mark.parametrize('flag',['trust_local_code','allow_test_transactions'])
def test_explicit_permission_required(work,flag):
    root,manager=work;info=put(root,'print(1)')
    with pytest.raises(ValueError):manager.start(body(info,**{flag:False}),IdleBrowser())


def test_production_blocked(work):
    root,manager=work;info=put(root,'print(1)')
    registry.save_project(registry.Project(id='qa1',name='Prod',appName='Test',url='http://127.0.0.1:8766/mock',environment='production'))
    with pytest.raises(ValueError,match='Production'):manager.start(body(info),IdleBrowser())


def test_existing_mode_requires_adapter(work):
    root,manager=work;info=put(root,'print(1)')
    with pytest.raises(ValueError,match='managed-session'):manager.start(body(info,mode='existing'),IdleBrowser())


def test_console_pass_does_not_invent_test_passes(work):
    root,manager=work;info=put(root,'print("PASS: all fine")\n')
    detail=wait(manager,manager.start(body(info),IdleBrowser()))
    assert detail['run']['status']=='COMPLETED_REVIEW'
    assert detail['run']['counts']['passed']==0


def test_explicit_checks_count(work):
    root,manager=work;info=put(root,'from backend.script_runtime import check\ncheck("Synthetic arithmetic", 2+2==4,4,4)\n')
    detail=wait(manager,manager.start(body(info),IdleBrowser()))
    assert detail['run']['status']=='PASSED'
    assert detail['run']['counts']['passed']==1


def test_exception_not_success(work):
    root,manager=work;info=put(root,'raise RuntimeError("synthetic failure")\n')
    detail=wait(manager,manager.start(body(info),IdleBrowser()))
    assert detail['run']['status']=='FAILED'
    assert detail['run']['exit_code']==1
    assert 'synthetic failure' in detail['log']


def test_running_snapshot_is_stable_and_next_run_reads_edit(work):
    root,manager=work
    info=put(root,'import time\ntime.sleep(.25)\nprint("REVISION_ONE")\n')
    run=manager.start(body(info),IdleBrowser())
    second=put(root,'print("REVISION_TWO")\n')
    detail=wait(manager,run)
    assert 'REVISION_ONE' in detail['log'] and 'REVISION_TWO' not in detail['log']
    after=wait(manager,manager.start(body(second),IdleBrowser()))
    assert 'REVISION_TWO' in after['log']
    assert detail['run']['sha256']!=after['run']['sha256']


def test_stop_and_concurrent_run_guard(work):
    root,manager=work;info=put(root,'import time\nprint("started",flush=True)\ntime.sleep(30)\n')
    run=manager.start(body(info),IdleBrowser())
    with pytest.raises(ValueError,match='already'):manager.start(body(info),IdleBrowser())
    assert manager.stop()['stopped']
    assert wait(manager,run)['run']['status']=='STOPPED'


def test_unverified_and_approximate_prints_remain_review(work):
    root,manager=work
    code='''from backend.script_runtime import emit
emit('stage_end', name='Click approve', status='REVIEW', expected='Verify status', actual='Click only')
emit('print_check', name='Print', status='PASS', fields=[{'status':'PASS','similarity_percent':75}])
'''
    info=put(root,code);detail=wait(manager,manager.start(body(info),IdleBrowser()))
    # v6.3.3 expands the PDF print field into its own review row.
    assert detail['run']['counts']==dict(passed=0,failed=0,review=3,blocked=0)
    assert detail['run']['status']=='COMPLETED_REVIEW'


def test_missing_credentials_no_browser_call(work):
    root,manager=work
    info=put(root,'SMART_ERP_REQUIRED_CREDENTIALS=["ERPQA_NONEXISTENT_PASSWORD"]\n')
    with pytest.raises(ValueError,match='password variables'):manager.start(body(info),IdleBrowser())


def test_export_exact_headers_formula_safety_and_review_blank(work):
    root,manager=work;info=put(root,'''from backend.script_runtime import emit
emit('check', name='=1+1', status='REVIEW', actual='<script>alert(1)</script>', expected='Explicit result')
''')
    detail=wait(manager,manager.start(body(info),IdleBrowser()))
    book=load_workbook(io.BytesIO(sw.report_excel(detail)))
    from backend.module_suite import HEADERS
    sheet=book['Test Cases'];assert [c.value for c in sheet[1]]==HEADERS
    assert sheet['C2'].data_type!='f'
    assert sheet['J2'].value is None
    report=sw.report_html(detail)
    assert '<script>alert' not in report and '&lt;script&gt;' in report


def test_supplied_script_uses_its_original_username_password_login():
    path=Path(__file__).resolve().parents[1]/'working_scripts/procurement/pi_lpo_grn.py'
    source=path.read_text()
    assert 'password_input.fill(username)' in source
    assert 'SMART_ERP_REQUIRED_CREDENTIALS = []' in source
    assert 'Missing local test-account passwords for:' not in source
    assert 'SMART_ERP_SUPPORTS_EXISTING_SESSION = True' in source
    assert "@stage('Goods Receipt Note: submit'" in source
    assert 'capture_failure(page, "AUTOMATION")' in source
