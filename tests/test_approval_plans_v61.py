"""Offline regression tests for multi-ERP approvals without touching any real ERP."""
import os
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from backend.api import app
from backend.approval_plans import (
    ApprovalPlan,PlanStage,load_plan,preview_plan,assertion_after_action,local_accounts)
from backend.locator import Workflow
from backend.browser import BrowserController


def test_two_erps_have_different_approval_sequences():
    a=load_plan('kagami_ba','indent_to_grn')
    b=load_plan('erp_two','indent_to_grn')
    assert len([s for s in a.stages if s.phase=='approval'])==7
    assert len([s for s in b.stages if s.phase=='approval'])==3
    assert a.project_id!=b.project_id


def test_approval_without_assertion_is_rejected():
    with pytest.raises(ValidationError):
        PlanStage(name='Manager',workflow='approval_manager',phase='approval',account='manager',require_assertion=False)


def test_assertion_must_come_after_last_action():
    def s(action):
        return {'action':action,'locator':{'kind':'css','value':'#unique'},'observed_count':1}
    a=Workflow(project_id='mock_erp',name='sample',start_url='http://127.0.0.1:8766/mock',steps=[s('assert_visible'),s('click')])
    b=Workflow(project_id='mock_erp',name='sample',start_url='http://127.0.0.1:8766/mock',steps=[s('click'),s('assert_text')])
    assert not assertion_after_action(a)
    assert assertion_after_action(b)


def test_preview_does_not_treat_unrecorded_erp_as_ready():
    info=preview_plan(load_plan('erp_three','indent_to_grn'))
    assert not info['ready']
    assert any('Register ERP' in x for x in info['issues'])
    assert info['stages'][0]['ready'] is False


def test_mock_project_has_real_preflight_and_captured_ids():
    info=preview_plan(load_plan('mock_erp','demo_indent_to_grn'))
    assert info['ready']
    assert info['produced_variables']==['grn_number','lpo_number','pi_number']
    assert len(info['stages'])==5


def test_test_account_alias_credentials_not_in_plan(monkeypatch):
    monkeypatch.setenv('ERPQA_MOCK_ERP_CREATOR_USERNAME','fake_creator')
    monkeypatch.setenv('ERPQA_MOCK_ERP_CREATOR_PASSWORD','fake_password')
    plan=load_plan('mock_erp','demo_indent_to_grn')
    assert 'fake_password' not in plan.model_dump_json()
    assert local_accounts('mock_erp',['creator'])['creator']['password']=='fake_password'


def test_missing_password_rejected(monkeypatch):
    monkeypatch.setenv('ERPQA_MOCK_ERP_CREATOR_USERNAME','dummy')
    monkeypatch.setenv('ERPQA_MOCK_ERP_CREATOR_PASSWORD','')
    with pytest.raises(ValueError,match='Missing local credentials'):
        local_accounts('mock_erp',['creator'])


def test_dashboard_api_preview_and_sample_plans():
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        r=client.get('/api/approval-plans')
        assert r.status_code==200
        ids={(p['project_id'],p['name']) for p in r.json()}
        assert ('kagami_ba','indent_to_grn') in ids
        assert ('mock_erp','demo_indent_to_grn') in ids
        r=client.get('/api/approval-plans/mock_erp/demo_indent_to_grn/preview')
        assert r.status_code==200 and r.json()['ready']
        # Never run without explicit write confirmation.
        r=client.post('/api/approval-plans/run',json={
            'project_id':'mock_erp','name':'demo_indent_to_grn','allow_test_transactions':False})
        assert r.status_code==400


def test_controller_account_switching_and_runtime_id_transfer(monkeypatch):
    """Pure fake browser: no network and no business writes.
    Verifies logout -> login -> next stage and PI output crosses stage boundary.
    """
    import backend.locator as loc_module
    import backend.json_workflow as json_wf
    from backend.json_workflow import LocatorLibrary
    class DummyLocator:
        def count(self):return 1
        def is_visible(self):return True
    class FakePage:
        def is_closed(self):return False
    browser=BrowserController.__new__(BrowserController)
    browser.page=FakePage()
    browser.active_project={'id':'mock_erp','environment':'test'}
    browser.recording=False
    browser.auto_capture=False
    browser.steps=[]
    logged=[]
    run_calls=[]
    def fake_login(config,username,password):
        logged.append(username)
    def fake_run(workflow,allow_writes=False):
        run_calls.append(workflow)
        assert allow_writes or workflow['name']=='logout'
        if workflow['name']=='make_pi':
            return {'status':'PASSED','completed_steps':1,'message':'Mock PI created','outputs':{'pi_number':'PI-MOCK-123'}}
        return {'status':'PASSED','completed_steps':1,'message':'Mock stage verified','outputs':{}}
    browser._do_login=fake_login
    browser._do_run=fake_run
    monkeypatch.setattr(loc_module,'locate',lambda page,spec:DummyLocator())
    monkeypatch.setattr(json_wf,'read_library',lambda project_id:LocatorLibrary(project_id=project_id))
    w1=Workflow(project_id='mock_erp',name='make_pi',start_url='http://127.0.0.1:8766/mock',reviewed=True,
       steps=[{'action':'capture_text','locator':{'kind':'css','value':'#pi'},'output':'pi_number'}])
    w2=Workflow(project_id='mock_erp',name='approve_pi',start_url='http://127.0.0.1:8766/mock',reviewed=True,
       steps=[{'action':'assert_text','locator':{'kind':'css','value':'#pi'},'value':'${pi_number}'}])
    logout=Workflow(project_id='mock_erp',name='logout',start_url='http://127.0.0.1:8766/mock',reviewed=True,
       steps=[{'action':'click','locator':{'kind':'css','value':'#logout'}},{'action':'assert_visible','locator':{'kind':'css','value':'#loginPanel'}}])
    result=browser._do_run_plan(
        plan={'project_id':'mock_erp','name':'unit_plan','logout_workflow':'logout','stages':[
            {'name':'Make PI','workflow':'make_pi','phase':'create','account':'creator','require_assertion':False},
            {'name':'Approve PI','workflow':'approve_pi','phase':'approval','account':'manager','require_assertion':True}]},
        workflows={w.name:w.model_dump() for w in (w1,w2,logout)},
        login_config={'username':{'kind':'css','value':'#username'}},
        accounts={'creator':{'username':'fake1','password':'secret1'},'manager':{'username':'fake2','password':'secret2'}},
        allow_writes=True,test_data={})
    assert result['status']=='PASSED'
    assert logged==['fake1','fake2']
    assert [x['name'] for x in run_calls]==['make_pi','logout','approve_pi']
    assert run_calls[-1]['steps'][0]['value']=='PI-MOCK-123'
    assert result['outputs']['pi_number']=='PI-MOCK-123'
