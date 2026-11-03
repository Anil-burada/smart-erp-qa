"""Dashboard live HTML inspector: read only, redact secrets, unique selectors."""
import pytest
from types import SimpleNamespace
from backend.browser import BrowserController
from backend.record_js import RECORDER_JS
from backend.locator import locate


def test_inspector_endpoint_and_dashboard_button_exist():
    from backend.api import app
    routes=[(getattr(r, 'path', ''), getattr(r, 'methods', set())) for r in app.routes]
    assert any(p == '/api/browser/dom-inspector' and 'GET' in methods for p,methods in routes)
    js=open('frontend/app.js',encoding='utf-8').read()
    assert 'Inspect Current Page IDs & Buttons' in js
    assert "action==='inspect-dom'" in js
    assert "action==='copy-dom-locator'" in js


def test_id_priority_and_generated_id_filter_in_recorder():
    assert 'generatedId' in RECORDER_JS
    assert 'idRank' in RECORDER_JS


def test_dom_inspector_in_chromium_is_unique_and_redacted():
    import os
    if not os.path.exists('/usr/bin/chromium'):
        pytest.skip('Chromium not installed in this environment')
    from playwright.sync_api import sync_playwright
    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True, executable_path='/usr/bin/chromium', args=['--no-sandbox'])
        try:
            page=browser.new_page()
            page.set_content('''
                <button id="purchase-indent-new">New Purchase Indent</button>
                <button id="duplicate">Procurement</button><button id="duplicate">Procurement</button>
                <button data-testid="save-record">Save draft</button>
                <input id="quantity" name="quantity" value="123" />
                <form><input type="password" name="password" value="secretpass" />
                  <input id="username" value="private_user" />
                  <button id="sign-in">Login</button></form>
                <button id=":r0:">Generated ID</button>
            ''')
            c=BrowserController.__new__(BrowserController)
            c.page=page
            c.active_project={'id':'test_project'}
            d=c._do_inspect_dom()
            assert d['project_id']=='test_project'
            controls=d['controls']
            assert len(controls)>=5
            new=next(x for x in controls if x['label']=='New Purchase Indent')
            assert new['locator']=={'kind':'css','value':'#purchase-indent-new'}
            assert new['unique'] is True
            assert locate(page,new['locator']).count()==1
            save=next(x for x in controls if x['label']=='Save draft')
            assert save['locator']=={'kind':'test_id','value':'save-record'}
            dup=[x for x in controls if x['label']=='Procurement']
            assert len(dup)==2
            assert all(not x['unique'] for x in dup)
            gen=next(x for x in controls if x['label']=='Generated ID')
            assert gen['generated_id'] is True
            assert gen['locator'] is None
            text=str(d)
            assert 'secretpass' not in text
            assert 'private_user' not in text
            assert 'password' not in text
            assert 'Login' not in text
            quantity=next(x for x in controls if x['id']=='quantity')
            assert '123' not in quantity['html']
        finally:
            browser.close()
