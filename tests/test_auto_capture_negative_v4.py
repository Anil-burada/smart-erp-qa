"""Tests for passive capture and conservative native negative suggestions."""
import json
from pathlib import Path
import pytest
from fastapi.testclient import TestClient
from backend import api, json_workflow, registry
from backend.browser import BrowserController
from backend.locator import Workflow
from backend.negative_cases import generate_candidates


def test_implicit_capture_flags_and_safe_replay_switch():
    src=(Path(__file__).resolve().parents[1]/'backend'/'browser.py').read_text()
    assert 'self.auto_capture = False' in src
    assert 'self.recording = False' in src
    assert 'if self.auto_capture and not self.steps' in src
    js=(Path(__file__).resolve().parents[1]/'backend'/'record_js.py').read_text()
    assert "document.querySelectorAll('input[type=password]')" in js


def test_negative_candidates_only_from_grounded_html_constraints():
    wf=Workflow(schema_version=2,project_id='mock_erp',name='intent',start_url='http://127.0.0.1:8766/mock/',
        steps=[{'action':'fill','target':'intent.step_001','observed_count':1}],reviewed=True,locator_fingerprint='pending')
    lib=json_workflow.LocatorLibrary(project_id='mock_erp', fields={'intent.step_001':{
        'locator':{'kind':'test_id','value':'quantity'},'field_type':'text','required':True,
        'observed_count':1,'constraints':{'tag':'input','input_type':'number','required':True,'min':'1','max':'100'}
    }})
    wf.locator_fingerprint=json_workflow.fingerprint(wf,lib)
    proposed=generate_candidates(wf,lib)
    assert [p['kind'] for p in proposed]==['required_blank','below_min','above_max']
    assert proposed[1]['invalid_value']=='0'
    assert proposed[2]['invalid_value']=='101'
    assert all(p['reviewed'] is False for p in proposed)


def test_plain_input_without_rules_does_not_invent_cases():
    wf=Workflow(schema_version=2,project_id='mock_erp',name='intent',start_url='http://127.0.0.1:8766/mock/',
        steps=[{'action':'fill','target':'intent.step_001','observed_count':1}],reviewed=True,locator_fingerprint='pending')
    lib=json_workflow.LocatorLibrary(project_id='mock_erp', fields={'intent.step_001':{
        'locator':{'kind':'test_id','value':'quantity'},'constraints':{'input_type':'text','required':False}
    }})
    wf.locator_fingerprint=json_workflow.fingerprint(wf,lib)
    assert generate_candidates(wf,lib)==[]


def test_negative_api_does_not_touch_browser_when_no_constraints(tmp_path,monkeypatch):
    monkeypatch.setattr(registry,'DB', tmp_path/'erpqa.sqlite3')
    monkeypatch.setattr(json_workflow,'BASE',tmp_path)
    monkeypatch.setattr(api,'workflow_path',lambda p,n:tmp_path/'workflows'/p/(n+'.json'))
    registry.init_db()
    client=TestClient(api.app,base_url='http://127.0.0.1:8766')
    project={'id':'mock_erp','name':'Mock','appName':'Mock','url':'http://127.0.0.1:8766/mock/','environment':'test','browser':'chromium','description':''}
    assert client.post('/api/projects',json=project).status_code==200
    with registry.connect() as c:
        c.execute('INSERT INTO workflows (project_id,name,reviewed,step_count) VALUES (?,?,?,?)',('mock_erp','intent',1,1))
    wf,lib=json_workflow.convert_recording('mock_erp','intent',project['url'],[
        {'action':'fill','locator':{'kind':'test_id','value':'item'},'observed_count':1,'value':'Paper','field_meta':{'tag':'input','input_type':'text','required':False}}
    ])
    wf.reviewed=True
    path=tmp_path/'workflows'/'mock_erp'/'intent.json';path.parent.mkdir(parents=True)
    path.write_text(wf.model_dump_json(),encoding='utf-8')
    json_workflow.save_library(lib)
    assert client.get('/api/workflows/mock_erp/intent/negative-candidates').json()['cases']==[]
    assert client.post('/api/workflows/run-negative',json={'project_id':'mock_erp','name':'intent','confirm_safe_test':True}).status_code==400
    assert client.post('/api/workflows/run-negative',json={'project_id':'mock_erp','name':'intent'}).status_code==400


def test_frontend_has_no_manual_start_requirement():
    src=(Path(__file__).resolve().parents[1]/'frontend'/'app.js').read_text()
    assert 'Finish Demonstration & Save JSON' in src
    assert 'data-action="generate-negative"' in src
    assert 'data-action="run-negative"' in src


def test_stop_save_creates_workflow_locators_and_negative_json(tmp_path,monkeypatch):
    monkeypatch.setattr(registry,'DB',tmp_path/'erpqa.sqlite3')
    monkeypatch.setattr(json_workflow,'BASE',tmp_path)
    monkeypatch.setattr(api,'workflow_path',lambda p,n:tmp_path/'workflows'/p/(n+'.json'))
    registry.init_db()
    client=TestClient(api.app,base_url='http://127.0.0.1:8766')
    project={'id':'mock_erp','name':'Mock','appName':'Mock','url':'http://127.0.0.1:8766/mock/','environment':'test','browser':'chromium','description':''}
    assert client.post('/api/projects',json=project).status_code==200
    example={'project_id':'mock_erp','start_url':project['url'],'warnings':[],
             'steps':[{'action':'fill','locator':{'kind':'test_id','value':'quantity'},
                       'observed_count':1,'value':'2','page_url':project['url'],
                       'field_meta':{'required':False,'input_type':'number','min':'1','max':''}}]}
    def fake(action,**kwargs):
        if action=='status':return {'recording':True,'project_id':'mock_erp'}
        if action=='stop':return example
        raise AssertionError(action)
    monkeypatch.setattr(api.controller,'call',fake)
    r=client.post('/api/recorder/stop',json={'name':'purchase_indent'})
    assert r.status_code==200,r.text
    assert r.json()['negative_candidates']==1
    assert (tmp_path/'workflows'/'mock_erp'/'purchase_indent.json').exists()
    assert (tmp_path/'projects'/'mock_erp'/'locators.json').exists()
    neg=json.loads((tmp_path/'workflows'/'mock_erp'/'purchase_indent.negative_cases.json').read_text())
    assert neg['reviewed'] is False
    assert neg['cases'][0]['kind']=='below_min'
    assert neg['cases'][0]['invalid_value']=='0'
