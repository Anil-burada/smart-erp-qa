"""Contract checks for reviewed JSON -> Page Object Model bundle; never uses live ERP."""
import json
import os
import sys
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from backend import registry, json_workflow as jw, api
from backend.pom_bundle import create_bundle
from backend.locator import Workflow

@pytest.fixture
def sandbox(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'BASE', tmp_path)
    monkeypatch.setattr(registry, 'DB', tmp_path/'data'/'erpqa.sqlite3')
    monkeypatch.setattr(jw, 'BASE', tmp_path)
    registry.init_db()
    registry.save_project(registry.Project(id='erp_test', name='ERP Test', appName='Procurement',url='http://127.0.0.1:18991/mock',environment='test'))
    steps=[
       {'action':'click','locator':{'kind':'css','value':'#open'},'target_text':'Open', 'observed_count':1,'page_url':'http://127.0.0.1:18991/mock'},
       {'action':'fill','locator':{'kind':'css','value':'#qty'},'target_text':'Quantity', 'value':'${quantity}','observed_count':1,'page_url':'http://127.0.0.1:18991/mock','field_meta':{'tag':'input','required':True,'input_type':'number','min':'1'}},
       {'action':'assert_visible','locator':{'kind':'css','value':'#continue'},'target_text':'Continue', 'observed_count':1,'page_url':'http://127.0.0.1:18991/mock'},
    ]
    wf,lib=jw.convert_recording('erp_test','pi_flow','http://127.0.0.1:18991/mock',steps)
    lib.fields["pi_flow.step_002"].constraints = {"required":True,"input_type":"number","min":"1"}
    jw.save_library(lib)
    wf.locator_fingerprint = jw.fingerprint(wf,lib)
    wf.reviewed=True
    jw.atomic_json(registry.workflow_path('erp_test','pi_flow'), wf.model_dump_json(indent=2))
    with registry.connect() as con:
        con.execute('INSERT INTO workflows(project_id,name,reviewed,step_count) VALUES(?,?,?,?)',('erp_test','pi_flow',1,3))
    return wf,lib


def test_generate_pom_zip_structure_and_generated_code(sandbox,tmp_path):
    wf,_=sandbox
    data=create_bundle(wf)
    with zipfile.ZipFile(BytesIO(data)) as z:
        assert z.testzip() is None
        names=z.namelist()
        assert any(x.endswith('/pages/erp_pages.py') for x in names)
        assert any(x.endswith('/tests/test_positive.py') for x in names)
        assert any(x.endswith('/tests/test_negative.py') for x in names)
        manifest=json.loads(z.read(next(x for x in names if x.endswith('/manifest.json'))))
        assert manifest['steps']==3
        assert manifest['explicit_assertions']==1
        assert manifest['native_negative_cases']>=1
        assert manifest['environment']=='test'
        z.extractall(tmp_path/'extract')
        extracted=tmp_path/'extract'/names[0].split('/')[0]
    for f in extracted.rglob('*.py'):
        compile(f.read_text(encoding='utf-8'),str(f),'exec')
    assert 'password' not in json.dumps(manifest)


def test_only_reviewed_workflows_accepted(sandbox):
    wf,_=sandbox
    wf.reviewed=False
    with pytest.raises(ValueError,match='reviewed'):
        create_bundle(wf)


def test_locator_drift_blocks_generated_package(sandbox):
    wf,lib=sandbox
    lib.fields['pi_flow.step_001'].locator.value='#changed'
    jw.save_library(lib)
    with pytest.raises(ValueError,match='changed'):
        create_bundle(wf)


def test_api_zip_attachment(sandbox):
    client=TestClient(api.app, base_url="http://127.0.0.1:8766")
    result=client.get('/api/workflows/erp_test/pi_flow/pom-bundle')
    assert result.status_code==200, result.text
    assert result.headers['content-type'].startswith('application/zip')
    with zipfile.ZipFile(BytesIO(result.content)) as z:
        assert any(name.endswith('/README.md') for name in z.namelist())


def test_generated_playwright_pom_smoke(sandbox,tmp_path):
    if not os.path.exists('/usr/bin/chromium'):
        pytest.skip('Local Chromium not installed')
    from playwright.sync_api import sync_playwright
    wf,_=sandbox
    with zipfile.ZipFile(BytesIO(create_bundle(wf))) as z:
        z.extractall(tmp_path)
        base=tmp_path/z.namelist()[0].split('/')[0]
    sys.path.insert(0,str(base))
    try:
        import importlib
        runner=importlib.import_module('workflows.pi_flow')
        html='''<html><body><button id="open" onclick="document.querySelector('#continue').hidden=false">Open</button>
        <input id="qty" type="number" min="1" required><button id="continue" hidden>Continue</button></body></html>'''
        with sync_playwright() as playwright:
            browser=playwright.chromium.launch(headless=True, executable_path='/usr/bin/chromium',args=['--no-sandbox'])
            try:
                page=browser.new_page()
                # Sandbox Chromium network navigation is restricted; use about:blank HTML.
                # URL guard is independently tested elsewhere.
                runner.PROJECT_ROOT = 'about:blank'
                page.set_content(html)
                runner.replay(page,{'quantity':5})
                assert page.locator('#qty').input_value() == '5'
                assert page.locator('#continue').is_visible()
            finally:
                browser.close()
    finally:
        sys.path.remove(str(base))
        for mod in ['pages','pages.erp_pages','pages.base_page','workflows','workflows.pi_flow']:
            sys.modules.pop(mod,None)

def test_nonunique_recording_not_exported(sandbox):
    wf,_=sandbox
    wf.steps[0].observed_count = 9
    with pytest.raises(ValueError, match='unique locator'):
        create_bundle(wf)


def test_production_export_is_refused(sandbox):
    wf,_=sandbox
    with registry.connect() as con:
        con.execute("UPDATE projects SET environment='production' WHERE id='erp_test'")
    with pytest.raises(ValueError, match='TEST/STAGING'):
        create_bundle(wf)


def test_dangerous_comment_text_is_never_generated_as_python(sandbox):
    wf,_=sandbox
    wf.steps[0].target_text = 'Open\nraise RuntimeError("untrusted")'
    with zipfile.ZipFile(BytesIO(create_bundle(wf))) as z:
        name=next(n for n in z.namelist() if n.endswith('/workflows/pi_flow.py'))
        code=z.read(name).decode('utf-8')
    assert '\nraise RuntimeError' not in code
    compile(code, 'workflow.py', 'exec')
