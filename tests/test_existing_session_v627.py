"""v6.2.7: replay AFTER manual login and one-click archive confirmation."""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from backend import api, browser, registry
from backend.json_workflow import FieldSpec, LocatorLibrary, fingerprint
from backend.locator import Workflow, Step, LocatorSpec
from backend.session_replay import initial_login_prefix, planned_existing_session_workflow

URL = 'https://test.example/erp'

def steps():
    return [
        {'action':'fill','target_text':'Username','locator':{'kind':'css','value':'#signin-username'},'value':'${login_user}', 'page_url':URL},
        {'action':'fill','target_text':'Password','locator':{'kind':'css','value':'#signin-password'},'value':'${login_password}', 'page_url':URL},
        {'action':'click','target_text':'Sign in','locator':{'kind':'role','role':'button','name':'Sign in'},'page_url':URL},
        {'action':'click','target_text':'Procurement','locator':{'kind':'role','role':'button','name':'Procurement'}, 'page_url':URL},
    ]

def wf_v1():
    return Workflow(project_id='test_erp',name='procurement',start_url=URL,
                    reviewed=True,steps=[Step.model_validate(s) for s in steps()])

def test_login_prefix_is_strict_and_never_skips_business_steps():
    assert initial_login_prefix(steps()) == 3
    assert initial_login_prefix(steps()[3:]) == 0
    assert initial_login_prefix([steps()[3], *steps()]) == 0
    assert initial_login_prefix([{'action':'click','target_text':'Sign in','locator':{'kind':'role','role':'button','name':'Sign in'}}, steps()[3]]) == 0
    assert initial_login_prefix([{'action':'click','target_text':'Sign out'}, *steps()]) == 0
    assert initial_login_prefix(steps()[:3]) == 0  # cannot skip the entire workflow
    assert initial_login_prefix([steps()[0], steps()[1], {'action':'click','target_text':'Submit Purchase Indent'},steps()[3]]) == 0


def test_in_memory_skip_preserves_original_review_and_locator_fingerprint():
    original=wf_v1()
    planned,count=planned_existing_session_workflow(original,LocatorLibrary(project_id='test_erp'))
    assert count == 3
    assert planned.steps[0].target_text == 'Procurement'
    assert len(original.steps) == 4
    assert original.reviewed and planned.reviewed
    # v2 fingerprint checked against full approved workflow before temporary slicing.
    lib=LocatorLibrary(project_id='test_erp')
    for i,step in enumerate(steps(),1):
        lib.fields[f'procurement.step_{i:03d}']=FieldSpec(locator=LocatorSpec.model_validate(step['locator']))
    converted=[]
    for i,s in enumerate(steps(),1):
        entry={k:v for k,v in s.items() if k!='locator'}
        entry['target']=f'procurement.step_{i:03d}'
        converted.append(Step.model_validate(entry))
    v2=Workflow(schema_version=2,project_id='test_erp',name='procurement',start_url=URL,
                reviewed=True,locator_fingerprint='pending',steps=converted)
    v2.locator_fingerprint=fingerprint(v2,lib)
    planned,count=planned_existing_session_workflow(v2,lib)
    assert count==3 and len(planned.steps)==1
    assert fingerprint(planned,lib) == planned.locator_fingerprint
    assert len(v2.steps)==4 and v2.locator_fingerprint!=planned.locator_fingerprint
    lib.fields['procurement.step_004'].locator=LocatorSpec(kind='css',value='#changed')
    with pytest.raises(ValueError,match='review/approve'):
        planned_existing_session_workflow(v2,lib)


def test_preflight_current_session_diagnoses_first_business_action(monkeypatch):
    workflow=wf_v1()
    monkeypatch.setattr(api,'load_workflow',lambda project_id,name: workflow)
    calls=[]
    def fake_call(action,**kwargs):
        calls.append((action,kwargs))
        return {'ready':True,'matches':1,'visible_matches':1,'findings':['LOCATOR READY']}
    monkeypatch.setattr(api.controller,'call',fake_call)
    r=TestClient(api.app,base_url='http://127.0.0.1:8766').get(
        '/api/workflows/test_erp/procurement/preflight-first?reuse_existing_login=true')
    assert r.status_code==200,r.text
    assert r.json()['first_executable_step_number']==4
    assert r.json()['skipped_initial_login_steps']==3
    assert calls[0][0]=='preflight_first'
    assert calls[0][1]['first_step']['target_text']=='Procurement'
    assert all(action not in ('open','login') for action,_ in calls)


def test_run_from_current_session_never_opens_or_logs_in_and_preserves_steps(monkeypatch):
    workflow=wf_v1()
    monkeypatch.setattr(api,'load_workflow',lambda project_id,name: workflow)
    monkeypatch.setattr(api,'save_execution',lambda *_a,**_kw:None)
    calls=[]
    def fake_call(action,**kwargs):
        calls.append((action,kwargs))
        return {'project_id':'test_erp','workflow':'procurement','status':'PASSED','completed_steps':1,
                'message':'1 business action', 'failed_step':None}
    monkeypatch.setattr(api.controller,'call',fake_call)
    r=TestClient(api.app,base_url='http://127.0.0.1:8766').post('/api/workflows/run',json={
        'project_id':'test_erp','name':'procurement','reuse_existing_login':True
    })
    assert r.status_code==200,r.text
    assert [x[0] for x in calls]==['run']
    prepared=calls[0][1]['workflow']
    assert prepared['reuse_existing_login'] is True
    assert prepared['skipped_initial_login_steps']==3
    assert [s['action'] for s in prepared['steps']]==['click']
    assert prepared['steps'][0]['original_step_number']==4
    # Credential variables in omitted login steps do not need to be supplied.
    assert not any('signin-password' in str(s) for s in prepared['steps'])


def test_runtime_replay_keeps_same_page_and_reports_original_step_number(tmp_path,monkeypatch):
    monkeypatch.setattr(browser,'BASE',tmp_path)
    events=[]
    class FakeLoc:
        def __init__(self,query): self.query=query
        def count(self): return 0 if self.query=='input[type="password"]:visible' else 1
        def click(self,**kwargs): events.append(('click',self.query))
        def wait_for(self,**kwargs): pass
    class FakePage:
        url=URL
        def is_closed(self):return False
        def locator(self,q):return FakeLoc(q)
        def goto(self,*a,**k):raise AssertionError('Current-session replay cannot reload or log in')
    class Trace:
        def start(self,**kwargs):events.append(('trace_start',))
        def stop(self,**kwargs):events.append(('trace_stop',))
    class Context: tracing=Trace()
    ctl=browser.BrowserController.__new__(browser.BrowserController)
    ctl.page=FakePage(); ctl.context=Context()
    ctl.active_project={'id':'test_erp','url':URL,'environment':'test'}
    ctl.recording=False; ctl.auto_capture=False
    report=ctl._do_run({'project_id':'test_erp','name':'procurement','reviewed':True,
        'start_url':URL,'reuse_existing_login':True,'skipped_initial_login_steps':3,
        'steps':[{'action':'click','locator':{'kind':'css','value':'#business-button'},
                  'target_text':'Procurement','original_step_number':4}]})
    assert report['status']=='PASSED',report
    assert report['session_reused'] is True
    assert report['skipped_initial_login_steps']==3
    assert events.count(('click','#business-button'))==1
    assert all('login' not in str(e) for e in events)


def test_ui_remove_is_yes_no_and_logged_in_replay_is_explicit():
    source=(Path(__file__).parents[1]/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'if(!await confirmRemoveWorkflow(key))return' in source
    assert 'Yes, Remove' in source and 'No, Keep' in source
    assert 'const typed=prompt(' not in source
    assert 'typed.trim()!==key' not in source
    assert 'reuse_existing_login:true' in source
    assert 'preflight-first?reuse_existing_login=true' in source
    assert 'Already Logged In' in source


def test_browser_chromium_uses_business_action_after_login_without_second_login(tmp_path,monkeypatch):
    chromium=Path('/usr/bin/chromium')
    if not chromium.exists():pytest.skip('Chromium not available')
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr(browser,'BASE',tmp_path)
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=str(chromium),args=['--no-sandbox'])
        try:
            ctx=b.new_context()
            page=ctx.new_page()
            page.set_content('''<form id="login"><input id="signin-username"><input id="signin-password" type="password"><button>Sign in</button></form>
            <section id="app" hidden><button id="business">Procurement</button><div id="done" hidden>Done</div></section>
            <script>document.querySelector('#login').addEventListener('submit',e=>{e.preventDefault();document.querySelector('#login').hidden=true;document.querySelector('#app').hidden=false});
            document.querySelector('#business').addEventListener('click',()=>document.querySelector('#done').hidden=false);</script>''')
            page.locator('#signin-username').fill('test-user')
            page.locator('#signin-password').fill('dummy')
            page.locator('form button').click()
            assert page.locator('input[type="password"]:visible').count()==0
            ctl=browser.BrowserController.__new__(browser.BrowserController)
            ctl.page=page;ctl.context=ctx
            ctl.recording=False;ctl.auto_capture=False
            ctl.active_project={'id':'test_erp','url':page.url,'environment':'test'}
            flow=wf_v1()
            flow.start_url=page.url
            prepared,count=planned_existing_session_workflow(flow,LocatorLibrary(project_id='test_erp'))
            from backend.json_workflow import resolve_locators
            executable=resolve_locators(prepared,LocatorLibrary(project_id='test_erp'))
            executable['steps']=[{'action':'click','locator':{'kind':'css','value':'#business'},
                                  'original_step_number':4,'target_text':'Procurement'}]
            executable['reuse_existing_login']=True
            executable['skipped_initial_login_steps']=count
            report=ctl._do_run(executable)
            assert report['status']=='PASSED',report
            assert page.locator('#done').is_visible()
            assert page.locator('#login').is_hidden()
            assert report['completed_steps']==1
        finally:
            b.close()


def test_replay_failure_reports_original_business_step_number(tmp_path,monkeypatch):
    monkeypatch.setattr(browser,'BASE',tmp_path)
    class FakeLocator:
        def __init__(self,q):self.q=q
        def count(self):return 0
        def wait_for(self,**kwargs):pass
    class Page:
        url=URL
        def is_closed(self):return False
        def locator(self,q):return FakeLocator(q)
        def screenshot(self,**kwargs):pass
        def goto(self,*args,**kwargs):raise AssertionError('No navigation allowed')
    class Tracing:
        def start(self,**kwargs):pass
        def stop(self,**kwargs):pass
    class Context:tracing=Tracing()
    ctl=browser.BrowserController.__new__(browser.BrowserController)
    ctl.page=Page();ctl.context=Context()
    ctl.active_project={'id':'test_erp','url':URL,'environment':'test'}
    ctl.recording=False;ctl.auto_capture=False
    result=ctl._do_run({'project_id':'test_erp','name':'indent','start_url':URL,
        'reviewed':True,'reuse_existing_login':True,'skipped_initial_login_steps':3,
        'steps':[{'action':'click','locator':{'kind':'css','value':'#no-button'},
                  'target_text':'','original_step_number':4}]})
    assert result['status']=='FAILED'
    assert result['failed_step']==4
    assert 'step 4' in result['message'].lower()


def test_remove_modal_yes_no_and_escape_in_chromium():
    chromium=Path('/usr/bin/chromium')
    if not chromium.exists():pytest.skip('Chromium not available')
    from playwright.sync_api import sync_playwright
    source=(Path(__file__).parents[1]/'frontend'/'app.js').read_text(encoding='utf-8')
    start=source.index('function confirmRemoveWorkflow(key){')
    end=source.index('\n}\n',start)+2
    function=source[start:end]
    with sync_playwright() as pw:
        b=pw.chromium.launch(headless=True,executable_path=str(chromium),args=['--no-sandbox'])
        try:
            page=b.new_page()
            page.set_content('<!DOCTYPE html><html><body><main>Workflows</main></body></html>')
            page.add_script_tag(content=function)
            def begin():
                page.evaluate("() => {window.__removeChoice=null;confirmRemoveWorkflow('mock_erp/mock_pi_create').then(v=>window.__removeChoice=v);return 1;}")
                assert page.get_by_text('mock_erp/mock_pi_create').is_visible()
            begin()
            page.get_by_role('button',name='No, Keep').click()
            page.wait_for_function('window.__removeChoice === false')
            assert page.locator('dialog').count()==0
            begin()
            page.get_by_role('button',name='Yes, Remove').click()
            page.wait_for_function('window.__removeChoice === true')
            begin()
            page.keyboard.press('Escape')
            page.wait_for_function('window.__removeChoice === false')
        finally:
            b.close()
