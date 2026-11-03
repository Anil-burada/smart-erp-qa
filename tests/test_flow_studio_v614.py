from types import SimpleNamespace
import pytest
from backend import flow_studio as fs
from backend.locator import Workflow, Step
from backend.browser import BrowserController


def wf(project, name, value='test', output=None):
    steps=[Step(action='click', locator={'kind':'role','role':'button','name':'Create'}, target_text='Create'),
           Step(action='assert_visible', locator={'kind':'css','value':'#success'})]
    if output:
        steps.append(Step(action='capture_text', locator={'kind':'css','value':'#document_id'}, output=output))
    if value.startswith('${'):
        steps.insert(0, Step(action='fill', locator={'kind':'css','value':'#reference'}, value=value))
    return Workflow(project_id=project, name=name, start_url='https://test.example/erp',steps=steps,reviewed=True)


def test_flow_preview_accepts_captured_id_from_earlier_stage(monkeypatch):
    f=fs.BusinessFlow(project_id='erp_one',name='indent_to_grn',stages=[
        fs.FlowStage(phase='indent_create',workflow='pi_create'),
        fs.FlowStage(phase='grn_create',workflow='grn_create')])
    flows={'pi_create':wf('erp_one','pi_create',output='pi_number'),
           'grn_create':wf('erp_one','grn_create',value='${pi_number}')}
    monkeypatch.setattr(fs,'get_project',lambda id: {'environment':'test'} if id=='erp_one' else None)
    monkeypatch.setattr(fs,'read_workflow',lambda id,name:flows.get(name))
    result=fs.preview_flow(f)
    assert result['ready'] is True
    assert result['runtime_variables']==['pi_number']


def test_flow_preview_blocks_unknown_variable_and_account_change(monkeypatch):
    f=fs.BusinessFlow(project_id='erp_one',name='g',stages=[
        fs.FlowStage(phase='grn_create',workflow='grn_create',different_account=True)])
    monkeypatch.setattr(fs,'get_project',lambda id: {'environment':'test'})
    monkeypatch.setattr(fs,'read_workflow',lambda id,name:wf(id,name,value='${missing_po_number}'))
    result=fs.preview_flow(f)
    assert not result['ready']
    assert any('different user' in x for x in result['issues'])
    assert any('Missing runtime value' in x for x in result['issues'])


def test_flow_preview_blocks_unreviewed_or_no_assertion(monkeypatch):
    f=fs.BusinessFlow(project_id='erp_one',name='g',stages=[fs.FlowStage(phase='po_create',workflow='po_create')])
    monkeypatch.setattr(fs,'get_project',lambda id: {'environment':'test'})
    x=wf('erp_one','po_create');x.reviewed=False;x.steps=x.steps[:1]
    monkeypatch.setattr(fs,'read_workflow',lambda id,name:x)
    result=fs.preview_flow(f)
    assert not result['ready']
    assert len(result['issues'])==2


def test_replay_flow_stops_after_failure(monkeypatch,tmp_path):
    from backend import browser
    monkeypatch.setattr(browser,'BASE',tmp_path)
    b=BrowserController.__new__(BrowserController)
    b.active_project={'id':'erp_one','environment':'test'}
    b.recording=False;b.steps=[]
    calls=[]
    def replay(workflow,allow_writes):
        calls.append(workflow['name'])
        if workflow['name']=='pi_create':
            return {'status':'PASSED','completed_steps':3,'failed_step':None,'outputs':{'pi_number':'PI-01'},'message':'OK'}
        return {'status':'FAILED','completed_steps':0,'failed_step':1,'outputs':{},'message':'Element missing'}
    b._do_run=replay
    # Resolve is real, but schema-v1 workflows require no project locator library.
    stages=[wf('erp_one','pi_create',output='pi_number').model_dump(),
            wf('erp_one','po_create',value='${pi_number}').model_dump(),
            wf('erp_one','grn_create').model_dump()]
    flow={'project_id':'erp_one','name':'indent_to_grn', 'stages':[
        {'phase':'indent_create','workflow':'pi_create'},
        {'phase':'po_create','workflow':'po_create'},
        {'phase':'grn_create','workflow':'grn_create'}]}
    result=b._do_run_flow(flow, stages, True, {})
    assert result['status']=='FAILED'
    assert calls==['pi_create','po_create']
    assert result['failed_step']==2
    assert result['outputs']['pi_number']=='PI-01'
    assert (tmp_path/result['report_path']).exists()


def test_flow_runner_rejects_production():
    b=BrowserController.__new__(BrowserController)
    b.active_project={'id':'erp_one','environment':'production'}
    with pytest.raises(ValueError,match='TEST/STAGING'):
        b._do_run_flow({'project_id':'erp_one'},[],True,{})
