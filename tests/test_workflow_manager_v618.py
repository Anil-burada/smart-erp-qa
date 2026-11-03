"""Deletion list management: archive, project isolation, dependency protection."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.api import app
from backend import registry
from backend import workflow_manage


@pytest.fixture
def isolated_project(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'BASE', tmp_path)
    monkeypatch.setattr(registry, 'DB', tmp_path / 'data' / 'erpqa.sqlite3')
    monkeypatch.setattr(workflow_manage, 'BASE', tmp_path)
    registry.init_db()
    for pid in ('test_erp', 'other_erp'):
        registry.save_project(registry.Project(
            id=pid, name=pid, appName=pid, url='http://127.0.0.1:8766/'+pid,
            environment='test', browser='chromium'))
    for pid, name in [('test_erp', 'purchase_indent'),('test_erp', 'po_create'),
                      ('other_erp', 'purchase_indent')]:
        path = registry.workflow_path(pid, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({'project_id': pid, 'name': name, 'steps': []}), encoding='utf-8')
        with registry.connect() as conn:
            conn.execute('INSERT INTO workflows (project_id,name,reviewed,step_count) VALUES(?,?,?,?)',
                         (pid,name,1,3))
    return tmp_path


def test_archives_one_and_preserves_other_projects_and_executions(isolated_project):
    base=isolated_project
    path=registry.workflow_path('test_erp','purchase_indent')
    sidecar=path.with_name('purchase_indent.negative_cases.json')
    sidecar.write_text('{"cases": []}',encoding='utf-8')
    with registry.connect() as c:
        c.execute("INSERT INTO executions (project_id,workflow_name,status) VALUES ('test_erp','purchase_indent','FAILED')")
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        result=client.delete('/api/workflows/test_erp/purchase_indent')
        assert result.status_code==200, result.text
        data=result.json()
        assert data['removed'] and data['archived_files']==2
        backup=base/data['archive_path']
        assert (backup/'purchase_indent.json').exists()
        assert (backup/'purchase_indent.negative_cases.json').exists()
        assert not path.exists() and not sidecar.exists()
        names={(x['project_id'],x['name']) for x in client.get('/api/workflows').json()}
        assert ('test_erp','purchase_indent') not in names
        assert ('test_erp','po_create') in names
        assert ('other_erp','purchase_indent') in names
        with registry.connect() as c:
            assert c.execute('SELECT count(*) FROM executions WHERE workflow_name=?',
                             ('purchase_indent',)).fetchone()[0]==1
        assert client.delete('/api/workflows/test_erp/purchase_indent').status_code==404


def test_blocks_when_used_by_business_flow(isolated_project):
    root=isolated_project/'flows'/'test_erp'
    root.mkdir(parents=True)
    (root/'indent_to_grn.json').write_text(json.dumps({
        'project_id':'test_erp','name':'indent_to_grn',
        'stages':[{'workflow':'purchase_indent'}]}))
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        r=client.delete('/api/workflows/test_erp/purchase_indent')
        assert r.status_code==409 and 'Business flow' in r.json()['detail']
        assert registry.workflow_path('test_erp','purchase_indent').exists()
        assert ('test_erp','purchase_indent') in {(x['project_id'],x['name']) for x in client.get('/api/workflows').json()}


def test_blocks_when_used_by_approval_plan_or_logout(isolated_project):
    root=isolated_project/'approval_plans'/'test_erp'
    root.mkdir(parents=True)
    (root/'manager.json').write_text(json.dumps({
        'project_id':'test_erp','name':'manager','logout_workflow':'po_create',
        'stages':[{'workflow':'purchase_indent'}]}))
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        for name in ('purchase_indent','po_create'):
            r=client.delete(f'/api/workflows/test_erp/{name}')
            assert r.status_code==409 and 'Approval plan' in r.json()['detail']
            assert registry.workflow_path('test_erp',name).exists()


def test_invalid_identifiers_do_not_escape_project(isolated_project):
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        assert client.delete('/api/workflows/test_erp/INVALID').status_code==409
        assert client.delete('/api/workflows/other_erp/no_such_workflow').status_code==404
        assert client.delete('/api/workflows/test_erp/%2E%2E').status_code in (400, 404, 409)
    assert registry.workflow_path('other_erp','purchase_indent').exists()


def test_dashboard_has_manage_toggle_and_confirmed_delete():
    from backend.registry import BASE
    source=(Path(__file__).parents[1]/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'Manage Saved Workflows' in source
    assert "action==='remove-saved-workflow'" in source
    assert 'if(!await confirmRemoveWorkflow(key))return' in source
    assert 'typed.trim()!==key' not in source
    assert 'workflowManagerProject' in source
    assert "'DELETE'" in source
