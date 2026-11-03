"""Mocked browser preflight/API tests. No real ERP transactions."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import registry, json_workflow, api
from backend.locator import Workflow


def project(id, url):
    return {'id':id,'name':id,'appName':'ERP','url':url,'environment':'test','browser':'chromium','description':''}

@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(registry,'DB',tmp_path/'erpqa.sqlite3')
    monkeypatch.setattr(json_workflow,'BASE',tmp_path)
    monkeypatch.setattr(api,'workflow_path', lambda proj,name: registry.workflow_path(proj,name) if False else tmp_path/'workflows'/proj/(name+'.json'))
    registry.init_db()
    return TestClient(api.app,base_url='http://127.0.0.1:8766'),tmp_path


def recorded():
    return [
       {'action':'click','locator':{'kind':'role','role':'button','name':'Create New Indent'},'target_text':'Create New Indent','observed_count':1},
       {'action':'fill','locator':{'kind':'test_id','value':'item'},'value':'${item}','observed_count':1},
       {'action':'fill','locator':{'kind':'test_id','value':'qty'},'value':'${quantity}','observed_count':1},
    ]


def test_convert_recording_is_project_isolated(isolated):
    client,root=isolated
    assert client.post('/api/projects',json=project('erp_a','https://one.example.com/erp')).status_code==200
    assert client.post('/api/projects',json=project('erp_b','https://two.example.com/erp')).status_code==200
    a,lib=json_workflow.convert_recording('erp_a','purchase_indent','https://one.example.com/erp',recorded())
    assert a.schema_version==2 and a.steps[0].locator is None
    assert a.steps[0].target=='purchase_indent.step_001'
    json_workflow.save_library(lib)
    assert 'purchase_indent.step_001' in client.get('/api/projects/erp_a/locators').json()['fields']
    assert client.get('/api/projects/erp_b/locators').json()['fields']=={}
    with pytest.raises(ValueError,match='mismatch'):
        json_workflow.fingerprint(a,json_workflow.read_library('erp_b'))


def test_variable_resolution_and_missing_input(isolated):
    client,_=isolated
    client.post('/api/projects',json=project('erp_a','https://one.example.com/erp'))
    workflow,lib=json_workflow.convert_recording('erp_a','purchase_indent','https://one.example.com/erp',recorded())
    with pytest.raises(ValueError,match='Missing test data input: item'):
        json_workflow.resolve_locators(workflow,lib,{})
    executable=json_workflow.resolve_locators(workflow,lib,{'item':'Paper','quantity':12})
    assert executable['steps'][1]['value']=='Paper'
    assert executable['steps'][2]['value']==12
    assert executable['steps'][2]['locator']['value']=='qty'
    assert workflow.steps[2].value=='${quantity}'


def test_locator_change_prevents_replay_without_reapproval(isolated):
    client,root=isolated
    client.post('/api/projects',json=project('erp_a','https://one.example.com/erp'))
    workflow,lib=json_workflow.convert_recording('erp_a','purchase_indent','https://one.example.com/erp',recorded())
    lib.fields['purchase_indent.step_001'].locator.name='Different button'
    with pytest.raises(ValueError,match='changed'):
        json_workflow.resolve_locators(workflow,lib,{'item':'Paper','quantity':12})


def test_legacy_to_v2_and_approval_reset(isolated):
    client,root=isolated
    client.post('/api/projects',json=project('erp_a','https://one.example.com/erp'))
    path=root/'workflows'/'erp_a'/'old.json'
    path.parent.mkdir(parents=True)
    legacy=Workflow(project_id='erp_a',name='old',start_url='https://one.example.com/erp',steps=[{'action':'click','locator':{'kind':'test_id','value':'create'},'observed_count':1}],reviewed=True)
    path.write_text(legacy.model_dump_json(indent=2))
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,reviewed,step_count) VALUES(?,?,?,?)',('erp_a','old',1,1))
    convert=client.post('/api/workflows/erp_a/old/convert-v2')
    assert convert.status_code==200,convert.text
    assert convert.json()['schema_version']==2
    assert path.with_suffix('.v1-backup.json').exists()
    assert client.get('/api/workflows/erp_a/old').json()['reviewed'] is False
    assert client.post('/api/workflows/erp_a/old/approve').status_code==200
    lib=client.get('/api/projects/erp_a/locators').json()
    lib['fields']['old.step_001']['locator']['value']='new-test-id'
    edit=client.put('/api/projects/erp_a/locators',json=lib)
    assert edit.status_code==200,edit.text
    assert client.get('/api/workflows/erp_a/old').json()['reviewed'] is False
    # Old saved fingerprint no longer authorizes replay
    run=client.post('/api/workflows/run',json={'project_id':'erp_a','name':'old'})
    assert run.status_code==400
    assert 'changed' in run.text
    assert client.post('/api/workflows/erp_a/old/approve').status_code==400
    # Updating the workflow reconfirms the new locator set, but still requires review.
    wf=client.get('/api/workflows/erp_a/old').json()
    assert client.put('/api/workflows/erp_a/old',json=wf).status_code==200
    assert client.post('/api/workflows/erp_a/old/approve').status_code==200


def test_existing_schema_one_still_supported(isolated):
    client,_=isolated
    client.post('/api/projects',json=project('erp_a','https://one.example.com/erp'))
    legacy=Workflow(project_id='erp_a',name='old',start_url='https://one.example.com/erp',steps=[{'action':'click','locator':{'kind':'test_id','value':'go'},'observed_count':1}])
    executable=json_workflow.resolve_locators(legacy,json_workflow.LocatorLibrary(project_id='erp_a'),{})
    assert executable['steps'][0]['locator']['value']=='go'


def test_frontend_has_new_controls_and_fixed_submit():
    root=Path(__file__).resolve().parents[1]
    script=(root/'frontend'/'app.js').read_text()
    assert "e.target.matches('form#projectForm')" in script
    assert "data-action=\"locators-toggle\"" in script
    assert 'testDataJSON' in script

def test_api_executes_resolved_locator_refs_and_runtime_values(isolated,monkeypatch):
    client,root=isolated
    client.post('/api/projects',json=project('erp_a','https://one.example.com/erp'))
    workflow,lib=json_workflow.convert_recording('erp_a','purchase_indent','https://one.example.com/erp',recorded())
    json_workflow.save_library(lib)
    wfpath=root/'workflows'/'erp_a'/'purchase_indent.json'
    wfpath.parent.mkdir(parents=True)
    wfpath.write_text(workflow.model_dump_json(indent=2))
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,reviewed,step_count) VALUES(?,?,0,3)',('erp_a','purchase_indent'))
    assert client.post('/api/workflows/erp_a/purchase_indent/approve').status_code==200
    received=[]
    def fake_call(action, **kwargs):
        assert action=='run'
        received.append(kwargs['workflow'])
        return {'status':'PASSED','message':'Actions completed in mock', 'failed_step':None,'report_path':'artifacts/report.json'}
    monkeypatch.setattr(api.controller,'call',fake_call)
    r=client.post('/api/workflows/run',json={
        'project_id':'erp_a', 'name':'purchase_indent',
        'test_data':{'item':'Paper','quantity':12}})
    assert r.status_code==200,r.text
    assert len(received)==1
    assert received[0]['steps'][2]['locator']['value']=='qty'
    assert received[0]['steps'][2]['value']==12
    assert received[0]['steps'][1]['value']=='Paper'
    assert client.get('/api/executions').json()[0]['status']=='PASSED'
