"""Self-contained POM tests; never contact a live ERP."""
import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from backend import api, registry, json_workflow as jw, pom
from backend.linked import LinkedPlan, inspect_plan
from backend.locator import Workflow


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'BASE', tmp_path)
    monkeypatch.setattr(registry, 'DB', tmp_path/'data'/'erpqa.sqlite3')
    monkeypatch.setattr(jw, 'BASE', tmp_path)
    monkeypatch.setattr(pom, 'BASE', tmp_path)
    monkeypatch.setattr(api, 'BASE', tmp_path)
    registry.init_db()
    for pid, url, _selector in [('erp_a','http://127.0.0.1:8766/mock','[data-testid="first"]'),
                                ('erp_b','http://127.0.0.1:8767/other','[data-testid="second"]')]:
        registry.save_project(registry.Project(id=pid,name=pid,appName=pid,url=url,environment='test',browser='chromium'))
    return tmp_path


def recording(pid, selector):
    name='purchase_indent'
    recorded=[{'action':'click','locator':{'kind':'css','value':selector}, 'target_text':'Create Indent',
               'observed_count':1, 'field_meta':{'tag':'button','required':False},
               'page_url':registry.get_project(pid)['url']}]
    wf, lib=jw.convert_recording(pid,name,registry.get_project(pid)['url'],recorded)
    jw.save_library(lib)
    wf.reviewed=True
    jw.atomic_json(registry.workflow_path(pid,name),wf.model_dump_json(indent=2))
    return wf,lib


def test_shared_template_uses_different_erp_locators(workspace):
    wa,_=recording('erp_a','#createA')
    tmpl, ma=pom.create_template_from_workflow(wa,'indent_creation')
    assert all('css' not in step.model_dump() for step in tmpl.steps)
    wb,lb=recording('erp_b','#createB')
    mb=pom.ProjectFieldMap(project_id='erp_b',template_name='indent_creation',
                           fields={tmpl.steps[0].field:wb.steps[0].target})
    pom.save_map(mb)
    with pytest.raises(ValueError,match='approved'):
        pom.compile_pom('erp_b','indent_creation')
    pom.approve_map('erp_b','indent_creation')
    a=pom.compile_pom('erp_a','indent_creation')
    b=pom.compile_pom('erp_b','indent_creation')
    assert a['steps'][0]['locator']['value']=='#createA'
    assert b['steps'][0]['locator']['value']=='#createB'
    assert a['start_url'].startswith('http://127.0.0.1:8766/')
    assert b['start_url'].startswith('http://127.0.0.1:8767/')


def test_locator_change_rejects_old_mapping(workspace):
    wf,lib=recording('erp_a','#before')
    pom.create_template_from_workflow(wf,'pi')
    lib.fields[wf.steps[0].target].locator.value='#after'
    jw.save_library(lib)
    with pytest.raises(ValueError,match='changed'):
        pom.compile_pom('erp_a','pi')


def test_missing_runtime_variable_rejected_before_browser(workspace):
    wf,_=recording('erp_a','#item')
    template,mp=pom.create_template_from_workflow(wf,'pi')
    template.steps[0].value='${quantity}'
    jw.atomic_json(pom.template_path('pi'), template.model_dump_json(indent=2))
    pom.approve_map('erp_a','pi')
    with pytest.raises(ValueError,match='quantity'):
        pom.compile_pom('erp_a','pi')
    assert pom.compile_pom('erp_a','pi',{'quantity':12})['steps'][0]['value']==12


def test_second_project_cannot_use_first_project_mapping(workspace):
    wf,_=recording('erp_a','#a')
    pom.create_template_from_workflow(wf,'pi')
    with pytest.raises(ValueError,match='approved'):
        pom.compile_pom('erp_b','pi')


def test_linked_chain_blocks_missing_capture(workspace):
    wf,_=recording('erp_a','#a')
    tmpl,_=pom.create_template_from_workflow(wf,'pi')
    tmpl.steps[0].action='fill'; tmpl.steps[0].value='${indent_number}'
    jw.atomic_json(pom.template_path('pi'),tmpl.model_dump_json(indent=2))
    plan=LinkedPlan(project_id='erp_a',stages=[{'template':'pi'}],allow_test_transactions=True)
    with pytest.raises(ValueError,match='missing runtime values'):
        inspect_plan(plan)


def test_linked_chain_reports_blocked_role_switch(workspace):
    wf,_=recording('erp_a','#a')
    pom.create_template_from_workflow(wf,'pi')
    plan=LinkedPlan(project_id='erp_a',stages=[{'template':'pi','role':'creator'},
        {'template':'pi','role':'approver'}],allow_test_transactions=True)
    with pytest.raises(ValueError,match='different ERP roles'):
        inspect_plan(plan)


def test_linked_chain_capture_supplies_downstream_value(workspace):
    wf,_=recording('erp_a','#a')
    tmpl,_=pom.create_template_from_workflow(wf,'pi')
    tmpl.steps[0].action='capture_text';tmpl.steps[0].output='indent_number'
    jw.atomic_json(pom.template_path('pi'),tmpl.model_dump_json(indent=2))
    pom.approve_map('erp_a','pi')
    next_template=pom.SharedTemplate(name='indent_approval',steps=[pom.POMStep(action='fill',field='indent_reference',value='${indent_number}')])
    jw.atomic_json(pom.template_path('indent_approval'),next_template.model_dump_json(indent=2))
    alias=next_template.steps[0].field
    proj_map=pom.ProjectFieldMap(project_id='erp_a',template_name='indent_approval',fields={alias:wf.steps[0].target})
    pom.save_map(proj_map);pom.approve_map('erp_a','indent_approval')
    plan=LinkedPlan(project_id='erp_a',stages=[{'template':'pi'}, {'template':'indent_approval'}],allow_test_transactions=True)
    info=inspect_plan(plan)
    assert info['ready'] is True and info['available_outputs']==['indent_number']
    assert pom.compile_pom('erp_a','indent_approval',context={'indent_number':'PI/LEO/2026/1111'})['steps'][0]['value']=='PI/LEO/2026/1111'


def test_step4_unverified_can_be_verified_on_matching_page(workspace,monkeypatch):
    raw=[{'action':'click','locator':{'kind':'css','value':f'#button{i}'},
          'target_text':f'Button {i}', 'observed_count':0 if i==4 else 1,
          'field_meta':{'tag':'button'}, 'page_url':'http://127.0.0.1:8766/mock'} for i in range(1,6)]
    wf,lib=jw.convert_recording('erp_a','recorded_flow','http://127.0.0.1:8766/mock',raw)
    jw.save_library(lib)
    jw.atomic_json(registry.workflow_path('erp_a','recorded_flow'),wf.model_dump_json(indent=2))
    with registry.connect() as c:
        c.execute('INSERT INTO workflows(project_id,name,step_count) VALUES(?,?,?)',('erp_a','recorded_flow',5))
    def mock_call(action,**kwargs):
        if action=='status':return {'open':True,'project_id':'erp_a','url':'http://127.0.0.1:8766/mock'}
        if action=='test_locator':return {'count':1,'visible':True,'text':'Button 4'}
        raise RuntimeError(action)
    monkeypatch.setattr(api.controller,'call',mock_call)
    client=TestClient(api.app, base_url='http://127.0.0.1:8766')
    result=client.post('/api/workflows/erp_a/recorded_flow/step-review/4/verify',json={'confirm_intended_element':True})
    assert result.status_code==200, result.text
    changed=Workflow.model_validate_json(registry.workflow_path('erp_a','recorded_flow').read_text())
    assert changed.steps[3].observed_count==1
    assert jw.read_library('erp_a').fields[changed.steps[3].target].observed_count==1
    assert changed.reviewed is False


def test_unreviewed_step_rejected_without_confirm(workspace):
    client=TestClient(api.app, base_url='http://127.0.0.1:8766')
    result=client.post('/api/workflows/erp_a/none/step-review/4/verify',json={'confirm_intended_element':False})
    assert result.status_code!=200


def test_template_rejects_unreviewed_workflow(workspace):
    wf,_=recording('erp_a','#a')
    wf.reviewed=False
    with pytest.raises(ValueError,match='Review and approve'):
        pom.create_template_from_workflow(wf,'pi')


def test_template_edit_requires_project_mapping_reapproval(workspace):
    wf,_=recording('erp_a','#a')
    template,_=pom.create_template_from_workflow(wf,'pi')
    template.steps[0].description='A different business action'
    pom.save_template('pi',template)
    with pytest.raises(ValueError,match='Template or mapped locators changed'):
        pom.compile_pom('erp_a','pi')
    pom.approve_map('erp_a','pi')
    assert pom.compile_pom('erp_a','pi')['name']=='pi'


def test_pom_negative_candidates_from_project_constraints(workspace):
    recorded=[{'action':'fill','locator':{'kind':'css','value':'#qty'}, 'target_text':'Quantity',
               'observed_count':1,'field_meta':{'tag':'input','required':True,'input_type':'number','min':'1'},
               'page_url':'http://127.0.0.1:8766/mock','value':'2'}]
    wf,lib=jw.convert_recording('erp_a','fill_quantity','http://127.0.0.1:8766/mock',recorded)
    jw.save_library(lib);wf.reviewed=True
    pom.create_template_from_workflow(wf,'pi')
    cases=pom.pom_native_negative_candidates('erp_a','pi')
    assert {(c['kind'],c['invalid_value']) for c in cases}=={('required_blank',''),('below_min','0')}


def test_pom_requires_test_environment(workspace):
    project=registry.Project(id='prod_erp',name='PROD',appName='Example',url='http://127.0.0.1:8768/erp',environment='production')
    registry.save_project(project)
    with pytest.raises(ValueError,match='TEST/STAGING'):
        pom.compile_pom('prod_erp','pi')


def test_optional_ai_receives_generic_locator_kinds_only(monkeypatch):
    import io
    from backend import ai_assistant
    req_contents=[]
    class Resp:
        def __enter__(self):return self
        def __exit__(self,*args):pass
        def read(self,*args):return json.dumps({'response':'{"index":0}'}).encode()
    def fake_open(req,timeout):
        req_contents.append(req.data.decode())
        return Resp()
    monkeypatch.setattr(ai_assistant,'urlopen',fake_open)
    result=ai_assistant.rank_locator_candidates_local([
        {'locator':{'kind':'css','value':'#SECRET_PRIVATE_SELECTOR'},'usable_candidate':True},
        {'locator':{'kind':'role','role':'button','name':'CONFIDENTIAL'},'usable_candidate':True}], 'click')
    assert result['auto_apply'] is False
    assert 'SECRET_PRIVATE_SELECTOR' not in req_contents[0] and 'CONFIDENTIAL' not in req_contents[0]
