"""Regression tests for exact Excel schema, module isolation, script safety and real result counts."""
from io import BytesIO
import json
import pytest
from fastapi.testclient import TestClient
from openpyxl import load_workbook
from backend import registry, module_suite as suite
from backend import api
from backend.locator import Workflow, Step, LocatorSpec


@pytest.fixture
def fresh(tmp_path,monkeypatch):
    monkeypatch.setattr(registry,'BASE',tmp_path)
    monkeypatch.setattr(registry,'DB',tmp_path/'data'/'erpqa.sqlite3')
    monkeypatch.setattr(suite,'BASE',tmp_path)
    registry.init_db();suite.init_suite_db()
    registry.save_project(registry.Project(id='qa1',name='ERP Test',appName='Local ERP',url='http://127.0.0.1:8766/mock',environment='test'))
    def add_wf(name):
        w=Workflow(schema_version=1,project_id='qa1',name=name,start_url='http://127.0.0.1:8766/mock',
            steps=[Step(action='assert_visible',locator=LocatorSpec(kind='css',value='body'))],reviewed=True)
        path=registry.workflow_path('qa1',name);path.parent.mkdir(parents=True,exist_ok=True);path.write_text(w.model_dump_json())
        with registry.connect() as db:db.execute('INSERT INTO workflows(project_id,name,reviewed,step_count) VALUES(?,?,1,1)',('qa1',name))
    add_wf('purchase_requisition');add_wf('sales_order')
    suite.link_workflow('qa1','purchase_requisition','Procurement','Purchase Requisition')
    suite.link_workflow('qa1','sales_order','Sales','Sales Order')
    yield tmp_path


def make_workbook():
    book=load_workbook(BytesIO(suite.workbook('qa1',True)));ws=book['Test Cases']
    ws.append(['Procurement','Purchase Requisition','Valid record','TC-PR-1','Save authorized record','Already logged in',
               'Use approved workflow','Verified record status','','','Positive'])
    ws.append(['Sales','Sales Order','Create sales order','TC-SO-1','Create valid order','Already logged in',
               'Use approved workflow','Verified order status','','','Positive'])
    payload=BytesIO();book.save(payload);return payload.getvalue()


def test_exact_11_column_template_and_filters(fresh):
    data=suite.workbook('qa1',True)
    book=load_workbook(BytesIO(data));assert [x.value for x in book['Test Cases'][1]]==suite.HEADERS
    assert 'Execution Map' in book and book['Test Cases'].max_row==1
    result=suite.import_excel('qa1',make_workbook());assert result['imported']==2
    items=suite.cases('qa1')
    assert {x['workflow_name'] for x in items}=={'purchase_requisition','sales_order'}
    suite.approve_cases(suite.ApprovalInput(project_id='qa1',testcase_ids=['TC-PR-1','TC-SO-1']))
    chosen=suite.plan_cases(suite.RunSuiteInput(project_id='qa1',modules=['Procurement']))
    assert [x['testcase_id'] for x in chosen]==['TC-PR-1']
    chosen=suite.plan_cases(suite.RunSuiteInput(project_id='qa1',modules=['Sales','Procurement'],processes=['Sales Order']))
    assert [x['testcase_id'] for x in chosen]==['TC-SO-1']
    assert suite.import_excel('qa1',make_workbook())['approval_reset']
    assert not any(x['approved'] for x in suite.cases('qa1'))


def test_script_static_analysis_and_no_automatic_approval(fresh):
    source=b'''async def login(page):\n    await page.get_by_role("button",name="Login").click()\nasync def purchase(page):\n    await page.locator("#number").fill("1")\n'''
    r=suite.save_script('qa1','purchase.py','Procurement','Purchase Requisition',source)
    assert r['analysis']['has_login_like_steps'] is True
    assert r['analysis']['action_count']==4
    drafts=suite.propose_from_uploaded_script('qa1',r['stored_filename'])
    assert len(drafts['draft_ids'])==4
    assert all(not c['approved'] for c in suite.cases('qa1'))
    with pytest.raises(ValueError):suite.save_script('qa1','../../outside.py','Procurement','Purchase Requisition',b'exec("hello")')


def test_api_run_only_one_module_and_record_true_assertion_pass(fresh,monkeypatch):
    suite.import_excel('qa1',make_workbook())
    suite.approve_cases(suite.ApprovalInput(project_id='qa1',testcase_ids=['TC-PR-1','TC-SO-1']))
    invoked=[]
    def fake_call(name,**kwargs):
        if name=='status':return {'open':True,'project_id':'qa1','recording':False,'paused':False}
        if name=='run':
            invoked.append(kwargs['workflow']['name'])
            assert kwargs['workflow']['reuse_existing_login'] is True
            return {'project_id':'qa1','workflow':kwargs['workflow']['name'],'status':'PASSED',
                    'message':'Observed assertion passed','failed_step':None,'report_path':None}
        raise AssertionError(name)
    monkeypatch.setattr(api.controller,'call',fake_call)
    client=TestClient(api.app,base_url='http://127.0.0.1:8766')
    r=client.post('/api/suite/run',json={'project_id':'qa1','modules':['Procurement']})
    assert r.status_code==200,r.text
    assert r.json()['passed']==1 and r.json()['failed']==0
    assert invoked==['purchase_requisition']
    metrics=client.get('/api/suite/metrics/qa1').json()
    assert metrics['passed']==1 and metrics['total']==2


def test_excel_formula_not_accepted_and_unapproved_run_blocked(fresh):
    book=load_workbook(BytesIO(suite.workbook('qa1',True)))
    book['Test Cases'].append(['Procurement','Purchase Requisition','=1+1','TC-1','Unsafe value','', '', 'Expected','','','Positive'])
    io=BytesIO();book.save(io)
    with pytest.raises(ValueError,match='formulas'):suite.import_excel('qa1',io.getvalue())
    suite.import_excel('qa1',make_workbook())
    with pytest.raises(ValueError,match='No approved'):suite.plan_cases(suite.RunSuiteInput(project_id='qa1',modules=['Procurement']))
