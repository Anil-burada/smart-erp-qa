"""Regressions for multi-project Python exports and dashboard recording controls."""
import ast
import json
import pytest
from fastapi.testclient import TestClient
from backend import api, registry, json_workflow
from backend.browser import BrowserController
from backend.python_export import generate_python


@pytest.fixture
def configured(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'DB', tmp_path/'qa.sqlite')
    monkeypatch.setattr(json_workflow, 'BASE', tmp_path)
    monkeypatch.setattr(api, 'workflow_path', lambda p,n: tmp_path/'workflows'/p/(n+'.json'))
    registry.init_db()
    for pid in ('erp_a', 'erp_b'):
        registry.save_project(registry.Project(id=pid,name=pid,appName='ERP',url=f'https://{pid}.example.com/erp',environment='test',browser='chromium'))
    return tmp_path


def test_export_uses_project_own_locator_not_another(configured):
    for pid, selector in (('erp_a', '#a-save'),('erp_b', '#b-save')):
        wf, library = json_workflow.convert_recording(pid, 'common_flow', f'https://{pid}.example.com/erp', [{
            'action':'click','locator':{'kind':'css','value':selector},
            'target_text':'Save', 'observed_count':1
        }])
        json_workflow.save_library(library)
        output = generate_python(wf)
        assert selector in output
        assert ('#b-save' if pid=='erp_a' else '#a-save') not in output
        assert 'allow_writes=True' in output
        ast.parse(output)


def test_export_endpoint_returns_downloadable_python(configured):
    wf, library = json_workflow.convert_recording('erp_a','small', 'https://erp_a.example.com/erp', [{
        'action':'fill','locator':{'kind':'test_id','value':'qty'},
        'value':'${quantity}', 'observed_count':1
    }])
    json_workflow.save_library(library)
    filename=configured/'workflows'/'erp_a'/'small.json'
    filename.parent.mkdir(parents=True)
    filename.write_text(wf.model_dump_json())
    r=TestClient(api.app,base_url='http://127.0.0.1:8766').get('/api/workflows/erp_a/small/python')
    assert r.status_code==200,r.text
    assert 'filename="small.py"' in r.headers['content-disposition']
    assert "test_data['quantity']" in r.text
    assert 'get_by_test_id' in r.text
    assert 'page.goto' not in r.text


def test_explicit_start_pause_resume_and_stop():
    class FakePage:
        url='https://erp_a.example.com/erp/home'
        def is_closed(self): return False
        def wait_for_timeout(self,ms): assert ms == 250
    c=BrowserController.__new__(BrowserController)
    c.page=FakePage();c.active_project={'id':'erp_a','environment':'test'}
    c.recording=True;c.auto_capture=True;c.paused=False;c.login_verified=False
    c.steps=[{'action':'click','target_text':'Earlier step'}];c.warnings=['old warning']
    s=c._do_start()
    assert s['recording'] and s['step_count']==0
    c.steps=[{'action':'fill','target_text':'Quantity','value':'12','locator':{'kind':'test_id','value':'quantity'}}]
    assert c._do_pause()['paused']
    assert c._do_preview()['steps'][0]['target_text']=='Quantity'
    assert c._do_resume()['recording']
    assert c._do_stop()['steps'][0]['value']=='12'
    assert not c.paused and not c.recording


def test_export_rejects_cross_project_or_modified_locator(configured):
    wf, library=json_workflow.convert_recording('erp_a','flow','https://erp_a.example.com/erp',[{
        'action':'click','locator':{'kind':'css','value':'#a'},'observed_count':1
    }])
    json_workflow.save_library(library)
    library.fields['flow.step_001'].locator.value='#tampered'
    json_workflow.save_library(library)
    with pytest.raises(ValueError,match='changed'):
        generate_python(wf)
