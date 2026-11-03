"""Local API tests: no live ERP required and no real account credentials."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api, registry, auth_config, json_workflow, ai_assistant
from backend.locator import Workflow


def project(project_id='mock_erp', url='http://127.0.0.1:8766/mock/', environment='test'):
    return {'id': project_id, 'name': project_id, 'appName': 'Test ERP',
            'url': url, 'environment': environment, 'browser': 'chromium',
            'description': ''}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'DB', tmp_path / 'data' / 'erpqa.sqlite3')
    monkeypatch.setattr(auth_config, 'BASE', tmp_path)
    monkeypatch.setattr(json_workflow, 'BASE', tmp_path)
    monkeypatch.setattr(api, 'workflow_path', lambda proj, name: tmp_path / 'workflows' / proj / f'{name}.json')
    registry.init_db()
    return TestClient(api.app, base_url='http://127.0.0.1:8766'), tmp_path


def add_workflow(client, root, project_id='mock_erp', name='smoke'):
    workflow = Workflow(
        project_id=project_id,
        name=name,
        start_url=registry.get_project(project_id)['url'],
        steps=[{'action':'click','locator':{'kind':'test_id','value':'create-indent'},
                'observed_count':1}],
        reviewed=True
    )
    path=root/'workflows'/project_id/f'{name}.json'
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(workflow.model_dump_json(), encoding='utf-8')
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,reviewed,step_count) VALUES (?,?,1,1)',(project_id,name))


def login_config(client, project_id='mock_erp'):
    sample=client.get(f'/api/projects/{project_id}/login-config')
    assert sample.status_code==200
    saved=client.put(f'/api/projects/{project_id}/login-config',json=sample.json())
    assert saved.status_code==200,saved.text
    return saved.json()


def test_login_json_stores_locators_not_credentials(isolated):
    client,root=isolated
    assert client.post('/api/projects',json=project()).status_code==200
    doc=login_config(client)
    assert doc['success']['value']=='#dashboard'
    stored=(root/'projects'/'mock_erp'/'login.json').read_text()
    assert 'password' in stored  # field locators are allowed
    assert 'dummy-test-password' not in stored
    assert 'project_url' in stored
    doc['project_id']='different'
    assert client.put('/api/projects/mock_erp/login-config',json=doc).status_code==400


def test_login_config_rejected_when_project_url_changes(isolated):
    client,root=isolated
    client.post('/api/projects',json=project())
    config=login_config(client)
    assert client.post('/api/projects',json=project(url='http://127.0.0.1:8766/other/')).status_code==200
    bad=client.get('/api/projects/mock_erp/login-config')
    assert bad.status_code==400
    assert 'URL' in bad.text
    assert client.put('/api/projects/mock_erp/login-config',json=config).status_code==400


def test_auto_run_opens_logs_in_then_replays_without_secret_storage(isolated,monkeypatch):
    client,root=isolated
    client.post('/api/projects',json=project())
    login_config(client)
    add_workflow(client,root)
    calls=[]
    def fake_call(action, **kw):
        calls.append(action)
        if action=='run':
            assert kw['workflow']['reviewed'] is True
            return {'project_id':'mock_erp','workflow':'smoke','status':'PASSED',
                    'message':'Action done','failed_step':None,'report_path':'artifacts/dummy/report.json'}
        return {'verified':True}
    monkeypatch.setattr(api.controller,'call',fake_call)
    payload={'project_id':'mock_erp','name':'smoke',
             'username':'dummy-user','password':'dummy-test-password'}
    result=client.post('/api/workflows/run-from-login',json=payload)
    assert result.status_code==200,result.text
    assert result.json()['status']=='PASSED'
    assert calls==['open','login','run']
    saved=(root/'projects'/'mock_erp'/'login.json').read_text()
    assert 'dummy-test-password' not in saved
    with registry.connect() as c:
        rows=[dict(x) for x in c.execute('SELECT * FROM executions').fetchall()]
    assert len(rows)==1 and rows[0]['status']=='PASSED'
    assert 'dummy-test-password' not in str(rows)


def test_auto_login_failure_blocks_downstream_and_masks_message(isolated,monkeypatch):
    client,root=isolated
    client.post('/api/projects',json=project())
    login_config(client)
    add_workflow(client,root)
    actions=[]
    def fake_call(action, **kw):
        actions.append(action)
        if action=='login':
            raise RuntimeError('Wrong password! dummy-test-password')
        return {'open':True}
    monkeypatch.setattr(api.controller,'call',fake_call)
    r=client.post('/api/workflows/run-from-login',json={
        'project_id':'mock_erp','name':'smoke','username':'test',
        'password':'dummy-test-password'})
    assert r.status_code==200
    assert r.json()['status']=='FAILED' and r.json()['failed_step']==0
    assert 'dummy-test-password' not in r.text
    assert actions==['open','login']


def test_production_cannot_auto_run(isolated,monkeypatch):
    client,root=isolated
    client.post('/api/projects',json=project(environment='production'))
    add_workflow(client,root)
    calls=[]
    monkeypatch.setattr(api.controller,'call',lambda a,**kw:calls.append(a))
    r=client.post('/api/workflows/run-from-login',json={
        'project_id':'mock_erp','name':'smoke','username':'test','password':'x'})
    assert r.status_code==400 and not calls


def test_ollama_prompt_sends_only_generic_failure_metadata(monkeypatch):
    captured=[]
    class Reply:
        def __enter__(self):return self
        def __exit__(self,*args):return None
        def read(self):return b'{}'
    def fake_urlopen(req, timeout):
        captured.append(json.loads(req.data))
        class Resp:
            def __enter__(self):return self
            def __exit__(self,*args):return None
            def read(self):return b'{"response":"Check the locator uniqueness first."}'
        return Resp()
    monkeypatch.setattr(ai_assistant,'urlopen',fake_urlopen)
    msg='Timeout -- secret API_KEY=1234 user alice@example.com'
    safe=ai_assistant.safe_summary(message=msg,step_number=5,action='fill')
    result=ai_assistant.diagnose_local(safe,'dummy-local-model')
    assert 'Check' in result
    prompt=captured[0]['prompt']
    assert 'API_KEY' not in prompt and 'alice@example' not in prompt
    assert 'timeout' in prompt and 'fill' in prompt
    assert captured[0]['stream'] is False


def test_frontend_contains_login_and_ai_controls():
    src=(Path(__file__).resolve().parents[1]/'frontend'/'app.js').read_text()
    assert 'run-from-login' in src
    assert 'save-login-config' in src
    assert 'ai-analyze' in src
    assert 'type="password"' in src
