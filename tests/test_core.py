import json
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from backend import registry
from backend.locator import Workflow, unique


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'DB', tmp_path / 'erpqa.sqlite3')
    registry.init_db()
    from backend.api import app
    return TestClient(app, base_url="http://127.0.0.1:8766")


def example(id='leocem', url='https://example.com/leocem'):
    return {'id':id,'name':id,'appName':'ERP','url':url,'environment':'test','browser':'chromium','description':''}


def test_empty_db_and_dashboard(client):
    assert client.get('/api/health').json()['ok']
    assert client.get('/api/projects').json() == []
    assert client.get('/').status_code == 200
    assert 'SMART ERP' in client.get('/').text


def test_projects_isolated_and_overlap_denied(client):
    assert client.post('/api/projects',json=example()).status_code == 200
    assert client.post('/api/projects',json=example('other','https://other.example.com/erp')).status_code == 200
    assert len(client.get('/api/projects').json()) == 2
    r=client.post('/api/projects',json=example('conflict','https://example.com/leocem/subpage'))
    assert r.status_code == 400
    assert 'overlap' in r.json()['detail']


def test_same_host_different_path_allowed(client):
    client.post('/api/projects',json=example())
    assert client.post('/api/projects',json=example('other','https://example.com/sales')).status_code == 200


def test_bad_id_and_url_rejected(client):
    assert client.post('/api/projects',json=example('../evil')).status_code == 422
    assert client.post('/api/projects',json=example('bad','javascript:alert(1)')).status_code == 422
    assert client.post('/api/projects',json=example('cred','https://u:p@example.com')).status_code == 422


def test_project_delete_preserves_workflows(client):
    client.post('/api/projects',json=example())
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,step_count) VALUES (?,?,?)',('leocem','test',1))
    assert client.delete('/api/projects/leocem').status_code == 400
    assert client.get('/api/projects').json()


def test_workflow_model_roundtrip():
    work=Workflow(project_id='leocem',name='indent',start_url='https://example.com/leocem',steps=[{'action':'click','locator':{'kind':'test_id','value':'create'},'observed_count':1}])
    assert Workflow.model_validate_json(work.model_dump_json()).steps[0].locator.value=='create'
    with pytest.raises(ValueError):
        Workflow(project_id='leocem',name='x',start_url='a',steps=[{'action':'execute_js','locator':{'kind':'css','value':'button'}}])


def test_no_silent_ambiguous_locator():
    class FakeLocator:
        def count(self): return 2
    class FakePage:
        def locator(self, selector): return FakeLocator()
    with pytest.raises(AssertionError,match='2 elements'):
        unique(FakePage(),{'kind':'css','value':'button'})


def test_local_only_origin_restrictions(client):
    assert client.get('/api/health',headers={'origin':'https://attacker.example'}).status_code==403
    assert client.get('/api/health',headers={'host':'bad.example'}).status_code==403


def test_mock_erp(client):
    r=client.get('/mock/')
    assert r.status_code==200
    assert 'Save Indent' in r.text
    assert 'data-testid="item"' in r.text


def test_workflow_api_scoped(client, monkeypatch, tmp_path):
    client.post('/api/projects',json=example())
    from backend import api
    monkeypatch.setattr(api, 'workflow_path', lambda project,name: tmp_path / project / f'{name}.json')
    p=tmp_path/'leocem'/'indent.json'
    p.parent.mkdir()
    raw=Workflow(project_id='leocem',name='indent',start_url='https://example.com/leocem',steps=[{'action':'click','locator':{'kind':'css','value':'#create'},'observed_count':1}])
    p.write_text(raw.model_dump_json())
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,step_count) VALUES (?,?,?)',('leocem','indent',1))
    assert client.get('/api/workflows/leocem/indent').status_code==200
    assert client.post('/api/workflows/leocem/indent/approve').status_code==200
    assert client.get('/api/workflows/leocem/indent').json()['reviewed']
    assert client.get('/api/workflows/other/indent').status_code==404


def test_approval_rejects_unverified_steps(client, monkeypatch, tmp_path):
    client.post('/api/projects',json=example())
    from backend import api
    monkeypatch.setattr(api, 'workflow_path', lambda project,name: tmp_path / project / f'{name}.json')
    p=tmp_path/'leocem'/'indent.json'
    p.parent.mkdir()
    p.write_text(Workflow(project_id='leocem',name='indent',start_url='https://example.com/leocem',steps=[{'action':'click','locator':{'kind':'css','value':'#create'},'observed_count':3}]).model_dump_json())
    assert client.post('/api/workflows/leocem/indent/approve').status_code==400


def test_project_url_cannot_change_after_recording(client):
    client.post('/api/projects',json=example())
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,step_count) VALUES (?,?,?)',('leocem','indent',3))
    changed=client.post('/api/projects',json=example('leocem','https://new.example.com/erp'))
    assert changed.status_code==400
    assert client.get('/api/projects').json()[0]['url']=='https://example.com/leocem'


def test_browser_controller_rejects_cross_project_event():
    from backend.browser import BrowserController
    class Frame:pass
    class Page:
        main_frame=Frame()
    controller=BrowserController.__new__(BrowserController)
    controller.recording=True
    controller.page=Page()
    controller.active_project={'id':'project1','url':'https://example.com/one'}
    controller.steps=[]
    controller.warnings=[]
    event={'page_url':'https://example.com/two/page','action':'click','locator':{'kind':'css','value':'button'}}
    controller._on_event({'page':controller.page,'frame':controller.page.main_frame},event)
    assert controller.steps==[]
    assert 'outside' in controller.warnings[0]
