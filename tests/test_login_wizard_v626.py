"""Guided login setup: tests without real ERP credentials or external traffic."""
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import api, registry, auth_config
from backend.browser import BrowserController


def test_local_chromium_login_wizard(monkeypatch):
    """Capture login controls, manually log in, verify unique marker then finish."""
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr('backend.browser.save_candidates', lambda *args: None)
    html = '''<html><body>
    <section id="loginPanel"><input id="username" name="username" placeholder="Username">
    <input id="password" name="password" type="password">
    <button id="loginBtn" onclick="document.querySelector('#loginPanel').style.display='none';
       document.querySelector('#dashboard').style.display='block'">Sign in</button></section>
    <main id="dashboard" style="display:none"><h1>Dashboard</h1>
      <nav id="sidebar"><button id="procurement">Procurement</button></nav>
      <button id="logout">Sign out</button></main>
    </body></html>'''
    with sync_playwright() as pw:
        try:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                        args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip('Local Chromium unavailable: ' + str(exc)[:80])
        try:
            page=browser.new_page()
            page.goto('about:blank')
            page.set_content(html)
            ctrl=BrowserController()
            ctrl.page=page
            ctrl.active_project={'id':'mock_setup','url':'about:blank','environment':'test'}
            captured=ctrl._do_login_setup_capture()
            assert captured['captured']
            assert all(captured['fields'][k]['kind']=='css' for k in ('username','password','submit'))
            with pytest.raises(ValueError,match='Login form is still visible'):
                ctrl._do_login_setup_success_options()
            page.locator('#username').fill('dummy-user')
            page.locator('#password').fill('dummy-do-not-store')
            page.locator('#loginBtn').click()
            options=ctrl._do_login_setup_success_options()
            assert options['ready']
            chosen=next(x['index'] for x in options['candidates'] if x['locator']=={'kind':'css','value':'#dashboard'})
            configured=ctrl._do_login_setup_finish(chosen)
            assert configured['success']=={'kind':'css','value':'#dashboard'}
            assert configured['username']=={'kind':'css','value':'#username'}
            assert 'dummy' not in str(configured)
            with pytest.raises(ValueError,match='Choose a suggested'):
                ctrl._do_login_setup_finish(30)
        finally:
            browser.close()


def test_login_wizard_api_saves_selectors_only(monkeypatch,tmp_path):
    monkeypatch.setattr(registry,'DB',tmp_path/'data'/'erpqa.sqlite3')
    monkeypatch.setattr(auth_config,'BASE',tmp_path)
    registry.init_db()
    client=TestClient(api.app,base_url='http://127.0.0.1:8766')
    project={'id':'wizard_demo','name':'Wizard Demo','appName':'Demo ERP',
             'url':'http://127.0.0.1:8766/mock/','environment':'test',
             'browser':'chromium','description':''}
    assert client.post('/api/projects',json=project).status_code==200
    calls=[]
    def fake_call(action,**kwargs):
        calls.append(action)
        if action=='status':return {'open':True,'project_id':'wizard_demo'}
        if action=='login_setup_capture':return {'captured':True, 'fields':{'username':{'kind':'css','value':'#username'}}}
        if action=='login_setup_success_options':return {'ready':True,'candidates':[{'index':0,'label':'Dashboard'}]}
        if action=='login_setup_finish':
            assert kwargs['choice_index']==0
            return {f:{'kind':'css','value':'#'+f} for f in ('username','password','submit','success')}
        raise AssertionError(action)
    monkeypatch.setattr(api.controller,'call',fake_call)
    preexisting = tmp_path/'projects'/'wizard_demo'/'login.json'
    preexisting.parent.mkdir(parents=True,exist_ok=True)
    preexisting.write_text('{"older":true}',encoding='utf-8')
    assert client.post('/api/projects/wizard_demo/login-setup/capture').status_code==200
    assert client.get('/api/projects/wizard_demo/login-setup/success-options').status_code==200
    assert client.post('/api/projects/wizard_demo/login-setup/save',json={'index':0}).status_code==200
    saved=(tmp_path/'projects'/'wizard_demo'/'login.json').read_text()
    assert '#success' in saved
    backups=list(preexisting.parent.glob('login.before_wizard_*.json'))
    assert len(backups)==1 and backups[0].read_text()=='{"older":true}'
    assert 'dummy-do-not-store' not in saved
    assert 'login_setup_finish' in calls
    status=client.get('/api/projects/wizard_demo/login-ready')
    assert status.json()['configured'] is True


def test_login_wizard_rejects_wrong_browser_and_production(monkeypatch,tmp_path):
    monkeypatch.setattr(registry,'DB',tmp_path/'data'/'erpqa.sqlite3')
    registry.init_db()
    client=TestClient(api.app,base_url='http://127.0.0.1:8766')
    project={'id':'other_demo','name':'Other Demo','appName':'Demo ERP',
             'url':'http://127.0.0.1:8766/mock/','environment':'production',
             'browser':'chromium','description':''}
    assert client.post('/api/projects',json=project).status_code==200
    assert client.post('/api/projects/other_demo/login-setup/capture').status_code==403
    project['environment']='test'
    assert client.post('/api/projects',json=project).status_code==200
    monkeypatch.setattr(api.controller,'call',lambda action,**kw: {'open':True,'project_id':'different'} if action=='status' else None)
    assert client.post('/api/projects/other_demo/login-setup/capture').status_code==400
    assert client.post('/api/projects/other_demo/login-setup/save',json={'index':999}).status_code==422


def test_frontend_has_guided_login_setup():
    src=(Path(__file__).resolve().parents[1]/'frontend'/'app.js').read_text()
    assert 'wizard-capture-login' in src
    assert 'wizard-find-success' in src
    assert 'wizard-save-login' in src
    assert 'Find Success Marker' in src
    assert 'No passwords stored' in src


def test_login_wizard_then_actual_automatic_login(monkeypatch):
    """E2E: one manual sign-in teaches selectors, then a fresh login uses them."""
    from playwright.sync_api import sync_playwright
    monkeypatch.setattr('backend.browser.save_candidates', lambda *args: None)
    html='''<html><body><form id="login">
     <input id="username" name="user" placeholder="Username">
     <input id="password" type="password" name="password">
     <button type="button" id="signin" onclick="document.getElementById('login').hidden=true;
     document.getElementById('dashboard').hidden=false">Sign In</button>
     </form><main id="dashboard" hidden><h1>Dashboard</h1><button id="logout">Log out</button></main>
     </body></html>'''
    with sync_playwright() as pw:
        try:
            browser=pw.chromium.launch(executable_path='/usr/bin/chromium',headless=True,args=['--no-sandbox'])
        except Exception as exc:
            pytest.skip('Local Chromium unavailable: '+str(exc)[:80])
        try:
            page=browser.new_page()
            url='about:blank'
            page.goto(url)
            page.set_content(html)
            ctrl=BrowserController()
            ctrl.page=page
            ctrl.active_project={'id':'e2e','url':url,'environment':'test'}
            assert ctrl._do_login_setup_capture()['captured']
            page.locator('#username').fill('manual-test-user')
            page.locator('#password').fill('dummy-secret')
            page.locator('#signin').click()
            choices=ctrl._do_login_setup_success_options()['candidates']
            idx=next(x['index'] for x in choices if x['locator']=={'kind':'css','value':'#dashboard'})
            config=ctrl._do_login_setup_finish(idx)
            # Reset the DOM to a fresh login state without network access.
            page.set_content(html)
            assert page.locator('#dashboard').is_hidden()
            ctrl.active_project['url']='https://authorized-test.invalid/login'
            report=ctrl._do_login(config,'runtime-test-user','runtime-test-password')
            assert report['verified'] is True
            assert page.locator('#dashboard').is_visible()
            assert 'runtime-test-password' not in str(config)
        finally:
            browser.close()
