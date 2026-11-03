"""v6.2.5: login readiness, opt-in nav fallback and real local Chromium smoke tests."""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api, auth_config, registry, json_workflow
from backend.browser import BrowserController
from backend.nav_recovery import navigation_label, navigation_diagnostic, navigation_recovery

PROJECT = {'id':'sample_erp','name':'Sample ERP','appName':'Procurement','url':'http://127.0.0.1:8766/mock/', 'environment':'test', 'browser':'chromium','description':''}


def test_login_setup_status_never_exposes_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(registry,'DB',tmp_path/'data'/'erp.sqlite3')
    monkeypatch.setattr(auth_config,'BASE',tmp_path)
    monkeypatch.setattr(json_workflow,'BASE',tmp_path)
    registry.init_db()
    with TestClient(api.app, base_url='http://127.0.0.1:8766') as client:
        assert client.post('/api/projects',json=PROJECT).status_code==200
        response=client.get('/api/projects/sample_erp/login-ready')
        assert response.status_code==200
        assert response.json()['configured'] is False
        assert response.json()['verified'] is False
        # Even a valid selector config is not proof of real authentication.
        template=client.get('/api/projects/sample_erp/login-config').json()
        assert client.put('/api/projects/sample_erp/login-config',json=template).status_code==200
        response=client.get('/api/projects/sample_erp/login-ready')
        assert response.status_code==200
        assert response.json()['configured'] is True
        assert response.json()['verified'] is False
        assert 'dummy-only-password' not in response.text


def test_navigation_repair_rejects_write_actions():
    assert navigation_label({'action':'click','target_text':'Approve','locator':{'kind':'role','role':'button','name':'Approve'}}) is None
    assert navigation_label({'action':'click','target_text':'Save Indent','locator':{'kind':'role','role':'button','name':'Save Indent'}}) is None
    assert navigation_label({'action':'fill','target_text':'Procurement','locator':{'kind':'role','role':'textbox','name':'Procurement'}}) is None
    assert navigation_label({'action':'click','locator':{'kind':'css','value':'#foo'}}) is None


HTML = '''<!doctype html><html><head><title>Local Test ERP</title></head><body>
<form id="loginForm"><input id="username"><input type="password" id="password"><button id="loginBtn" type="submit">Log in</button></form>
<section id="dashboard" hidden>
  <button id="first">Open Menu</button>
  <nav id="nav" hidden><a href="#procurement" id="procLink">Procurement</a></nav>
  <div id="completed" hidden>Purchase Indent menu opened</div>
</section>
<script>
document.getElementById('loginForm').addEventListener('submit',e=>{
 e.preventDefault();
 const u=document.getElementById('username').value, p=document.getElementById('password').value;
 if(u && p) {document.getElementById('loginForm').hidden=true;document.getElementById('dashboard').hidden=false;}
});
document.getElementById('first').addEventListener('click',()=>document.getElementById('nav').hidden=false);
document.getElementById('procLink').addEventListener('click',e=>{e.preventDefault();document.getElementById('completed').hidden=false;});
</script></body></html>'''


@pytest.fixture
def chromium_page(tmp_path):
    if not Path('/usr/bin/chromium').exists():
        pytest.skip('Local Chromium binary missing; unit tests still run')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
            ctx=browser.new_context()
            page=ctx.new_page()
            # The container blocks local URL navigations; set_content tests the same browser DOM.
            page.set_content(HTML,wait_until='domcontentloaded',timeout=10000)
            yield ctx,page
        finally:
            browser.close()


def test_exact_navigation_recovery_requires_single_control(chromium_page):
    ctx,page=chromium_page
    page.locator('#loginForm').evaluate('(el)=>el.hidden=true')
    page.locator('#dashboard').evaluate('(el)=>el.hidden=false')
    page.locator('#nav').evaluate('(el)=>el.hidden=false')
    step={'action':'click', 'target_text':'Procurement',
          'locator':{'kind':'role','role':'button','name':'Procurement'},
          'observed_candidates':[{'spec':{'kind':'role','role':'link','name':'Procurement'},'observed_count':1}]}
    assert page.get_by_role('button',name='Procurement',exact=True).count()==0
    assert navigation_diagnostic(page,step)['unique_visible_controls']==1
    repaired=navigation_recovery(page,step)
    assert repaired is not None
    locator,reason=repaired
    assert reason=='approved-recording-alternative'
    assert locator.get_attribute('id')=='procLink'
    # An ambiguous second control prevents all automatic recovery.
    page.locator('body').evaluate('(el)=>el.insertAdjacentHTML("beforeend", "<button>Procurement</button>")')
    assert navigation_diagnostic(page,step)['unique_visible_controls']==2
    assert navigation_recovery(page,step) is None


def test_login_then_approved_workflow_with_step2_navigation_recovery(chromium_page,tmp_path,monkeypatch):
    from backend import browser as browser_module
    monkeypatch.setattr(browser_module,'BASE',tmp_path)
    ctx,page=chromium_page
    ctl=BrowserController()
    ctl.page=page
    ctl.context=ctx
    ctl.active_project=dict(PROJECT)
    cfg={'username':{'kind':'css','value':'#username'},
         'password':{'kind':'css','value':'#password'},
         'submit':{'kind':'css','value':'#loginBtn'},
         'success':{'kind':'css','value':'#dashboard'}}
    result=ctl._do_login(cfg,'local-test-user','dummy-only-password')
    assert result['verified'] is True
    # Local fixture uses about:blank because container URL navigation is blocked.
    # Switch ONLY the _do_run origin check to that isolated fixture URL.
    ctl.active_project['url']=page.url
    workflow={'project_id':'sample_erp','name':'procurement_nav_smoke','reviewed':True,
              'start_url':page.url,
              'steps':[
                {'action':'click','target_text':'Open Menu','locator':{'kind':'css','value':'#first'},'value':None},
                {'action':'click','target_text':'Procurement','locator':{'kind':'role','role':'button','name':'Procurement'},
                 'observed_candidates':[{'spec':{'kind':'role','role':'link','name':'Procurement'},'observed_count':1}]},
                {'action':'assert_visible','target_text':'Purchase Indent','locator':{'kind':'css','value':'#completed'}}
              ]}
    report=ctl._do_run(workflow,allow_writes=False,allow_nav_repair=True)
    assert report['status']=='PASSED',report
    assert report['completed_steps']==3
    assert report['failed_step'] is None
    assert len(report['navigation_recoveries'])==1
    assert report['navigation_recoveries'][0]['step']==2
    assert 'dummy-only-password' not in str(report)
    assert Path(tmp_path/report['report_path']).exists()


def test_login_run_api_passes_browser_mode_and_optin(tmp_path,monkeypatch):
    from backend.locator import Workflow
    monkeypatch.setattr(registry,'DB',tmp_path/'data'/'erp.sqlite3')
    monkeypatch.setattr(auth_config,'BASE',tmp_path)
    monkeypatch.setattr(json_workflow,'BASE',tmp_path)
    monkeypatch.setattr(api,'workflow_path',lambda p,n:tmp_path/'workflows'/p/f'{n}.json')
    registry.init_db()
    with TestClient(api.app, base_url='http://127.0.0.1:8766') as client:
        assert client.post('/api/projects',json=PROJECT).status_code==200
        doc=client.get('/api/projects/sample_erp/login-config').json()
        assert client.put('/api/projects/sample_erp/login-config',json=doc).status_code==200
        wf=Workflow(project_id='sample_erp',name='smoke',start_url=PROJECT['url'],reviewed=True,
                    steps=[{'action':'click','target_text':'Procurement','locator':{'kind':'role','role':'button','name':'Procurement'}}])
        wfpath=tmp_path/'workflows'/'sample_erp'/'smoke.json'
        wfpath.parent.mkdir(parents=True,exist_ok=True)
        wfpath.write_text(wf.model_dump_json(),encoding='utf-8')
        calls=[]
        def stub(action,**kwargs):
            calls.append((action,kwargs))
            if action=='run':
                return {'status':'PASSED','project_id':'sample_erp','workflow':'smoke',
                        'completed_steps':1,'failed_step':None,'message':'Finished',
                        'report_path':None}
            return {'verified':True}
        monkeypatch.setattr(api.controller,'call',stub)
        response=client.post('/api/workflows/run-from-login',json={
            'project_id':'sample_erp','name':'smoke','username':'dummy-user','password':'secret-local',
            'embedded':True,'allow_nav_repair':True})
        assert response.status_code==200,response.text
        assert response.json()['login_verified'] is True
        assert response.json()['run_mode']=='inside_dashboard'
        assert [action for action,_ in calls]==['open','login','run']
        assert calls[0][1]['embedded'] is True
        assert calls[2][1]['allow_nav_repair'] is True
        assert 'secret-local' not in response.text
        with registry.connect() as db:
            messages=[str(r['message']) for r in db.execute('SELECT message FROM executions')]
        assert all('secret-local' not in msg for msg in messages)


def test_dashboard_has_visible_login_modes_and_status():
    src=(Path(__file__).resolve().parents[1]/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'Run From Login (Inside Dashboard)' in src
    assert 'Run From Login (New Browser)' in src
    assert 'data-action="check-login-setup"' in src
    assert 'allowNavRepair' in src
    assert 'if(!w.reviewed)throw' in src
