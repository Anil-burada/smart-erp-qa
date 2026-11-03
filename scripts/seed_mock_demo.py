"""Create a fully isolated DEMO project and reviewed workflows for the harmless mock ERP.

Run once: python scripts/seed_mock_demo.py. Existing saved workflows are NOT overwritten.
"""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from backend.registry import init_db, get_project, save_project, Project, workflow_path, connect
from backend.locator import Workflow
from backend.json_workflow import atomic_json
from backend.auth_config import LoginConfig,save_login_config,login_path
from backend.approval_plans import ApprovalPlan, save_plan,plan_path

ID='mock_erp'
URL='http://127.0.0.1:8766/mock/'

def step(action, selector, value=None, output=None, target_text=''):
    d={'action':action,'locator':{'kind':'css','value':selector},'observed_count':1,
       'page_url':URL,'target_text':target_text}
    if value is not None:d['value']=value
    if output:d['output']=output
    return d

stages={
'mock_pi_create':[
 step('click','#create',target_text='Create New Indent'),
 step('select_option','#department','Stores'),
 step('fill','#item','Demo Material'),
 step('fill','#qty','12'),
 step('click','#save',target_text='Save Indent'),
 step('assert_visible','#saved-number'),
 step('capture_text','#saved-number',output='pi_number')],
'mock_pi_approve':[
 step('click','#viewLatest'),
 step('click','#approve',target_text='Approve Indent'),
 step('assert_text','#status','Approved')],
'mock_lpo_create':[
 step('click','#viewLatest'),
 step('click','#createLpo',target_text='Create Local PO'),
 step('assert_visible','#lpo-number'),
 step('capture_text','#lpo-number',output='lpo_number')],
'mock_lpo_approve':[
 step('click','#viewLatest'),
 step('click','#approveLpo',target_text='Approve Local PO'),
 step('assert_text','#po-status','Approved')],
'mock_grn_create':[
 step('click','#viewLatest'),
 step('click','#createGrn',target_text='Create GRN'),
 step('assert_visible','#grn-number'),
 step('capture_text','#grn-number',output='grn_number')],
'mock_logout':[
 step('click','#logout',target_text='Logout'),
 step('assert_visible','#loginPanel')],
}

def main():
    init_db()
    old=get_project(ID)
    if old and old['url'].rstrip('/')!=URL.rstrip('/'):
        raise ValueError('Existing mock_erp URL belongs to another project; refusing overwrite')
    if not old:
        save_project(Project(id=ID,name='Demo Procurement ERP',appName='Safe Mock ERP',url=URL,environment='test',browser='chromium',description='Harmless offline demo for multi-role Indent -> PO -> GRN'))
    if not login_path(ID).exists():
        save_login_config(ID,LoginConfig(schema_version=1,project_id=ID,project_url=get_project(ID)['url'],
            username={'kind':'css','value':'#username'},password={'kind':'css','value':'#password'},
            submit={'kind':'css','value':'#loginBtn'},success={'kind':'css','value':'#dashboard'}))
    for name, steps in stages.items():
        path=workflow_path(ID,name)
        if path.exists():
            print('Preserved existing',name)
            wf=Workflow.model_validate_json(path.read_text(encoding='utf-8'))
        else:
            wf=Workflow(schema_version=1,project_id=ID,name=name,start_url=get_project(ID)['url'],steps=steps,reviewed=True)
            atomic_json(path,wf.model_dump_json(indent=2))
        # Always reconcile SQLite with existing on-disk sample JSON: a fresh
        # installation may ship workflows/ but start with an empty database.
        with connect() as c:
            c.execute('INSERT OR IGNORE INTO workflows (project_id,name,reviewed,step_count) VALUES(?,?,?,?)',
                      (ID,name,int(wf.reviewed),len(wf.steps)))
    plan=ApprovalPlan(schema_version=1,project_id=ID,name='demo_indent_to_grn',
      description='Fully local harmless demo; user accounts are fake test names in .env, not ERP credentials',
      logout_workflow='mock_logout',stages=[
        {'name':'Create Purchase Indent','workflow':'mock_pi_create','account':'creator','phase':'create','require_assertion':True},
        {'name':'Manager approves Indent','workflow':'mock_pi_approve','account':'manager','phase':'approval','require_assertion':True},
        {'name':'Create Local PO','workflow':'mock_lpo_create','account':'buyer','phase':'create','require_assertion':True},
        {'name':'GM approves PO','workflow':'mock_lpo_approve','account':'gm','phase':'approval','require_assertion':True},
        {'name':'Create Goods Receipt Note','workflow':'mock_grn_create','account':'warehouse','phase':'grn','require_assertion':True}])
    if not plan_path(ID,plan.name).exists():save_plan(plan)
    print('Mock demo is ready. Register/Open project mock_erp and run Approval Plans -> demo_indent_to_grn.')
    print('Configure only FAKE demo usernames and passwords in .env. Real ERP accounts must NEVER be used in mock.')

if __name__=='__main__':main()
