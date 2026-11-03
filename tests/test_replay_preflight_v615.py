"""Read-only first-step replay preflight tests: never guess/click ERP targets."""
from types import SimpleNamespace
import pytest
from backend.browser import BrowserController

class FakeLocator:
    def __init__(self, vis): self.vis = vis
    def count(self): return len(self.vis)
    def nth(self, index): return SimpleNamespace(is_visible=lambda: self.vis[index])

class FakePage:
    def __init__(self, url, vis, login=False):
        self.url = url
        self.vis=vis
        self.login=login
        self.evaluations=0
    def is_closed(self): return False
    def get_by_role(self, role, name, exact):
        assert role=='button' and exact
        assert name=='+ Purchase Order'
        return FakeLocator(self.vis)
    def locator(self, selector):
        assert selector=='input[type="password"]:visible'
        return FakeLocator([True] if self.login else [])
    def evaluate(self, code):
        assert 'querySelectorAll' in code
        self.evaluations+=1
        return [{'role':'button','text':'Purchase Indent'}, {'role':'button','text':'Purchase Order'}]
    def click(self, *args, **kwargs):
        pytest.fail('Preflight must not click anything')
    def goto(self, *args, **kwargs):
        pytest.fail('Preflight must not navigate')


def make_controller(url, matches, login=False):
    obj=BrowserController.__new__(BrowserController)
    obj.active_project={'id':'surajlabs'}
    obj.page=FakePage(url,matches,login)
    return obj

FIRST={'locator':{'kind':'role','role':'button','name':'+ Purchase Order'},'action':'click','target_text':'+ Purchase Order'}
URL='https://d1pocupw4rivlh.cloudfront.net/'

def test_missing_first_locator_explains_navigation_and_never_clicks():
    ctl=make_controller(URL, [])
    result=ctl._do_preflight_first('surajlabs','purchase_indent',FIRST,URL,True)
    assert not result['ready']
    assert result['matches']==0
    assert any('Navigate' in text for text in result['findings'])
    assert result['visible_controls'][0]['text']=='Purchase Indent'


def test_visible_first_step_ready_with_review():
    ctl=make_controller(URL,[True])
    result=ctl._do_preflight_first('surajlabs','po_create',FIRST,URL,True)
    assert result['ready']
    assert result['visible_matches']==1
    assert result['first_step_action']=='click'


def test_login_and_draft_are_not_ready_even_when_button_visible():
    ctl=make_controller(URL,[True],login=True)
    result=ctl._do_preflight_first('surajlabs','po_create',FIRST,URL,False)
    assert not result['ready']
    assert result['login_visible']
    assert any('approval' in text for text in result['findings'])


def test_wrong_project_and_origin_cannot_be_inspected():
    ctl=make_controller(URL,[True])
    with pytest.raises(ValueError,match='matching ERP'):
        ctl._do_preflight_first('wrong','po_create',FIRST,URL,True)
    with pytest.raises(ValueError,match='different origin'):
        ctl._do_preflight_first('surajlabs','po_create',FIRST,'https://different.example/',True)


def test_preflight_http_route_wires_real_workflow_without_execution(monkeypatch):
    from fastapi.testclient import TestClient
    from backend import api
    from backend.locator import Workflow, Step, LocatorSpec
    wf=Workflow(project_id='surajlabs',name='purchase_indent',start_url=URL,reviewed=True,
                steps=[Step(action='click',locator=LocatorSpec(kind='role',role='button',name='+ Purchase Order'),
                            page_url=URL,target_text='+ Purchase Order')])
    monkeypatch.setattr(api,'load_workflow',lambda pid,name:wf)
    calls=[]
    def fake_call(action,**kwargs):
        calls.append((action,kwargs))
        return {'ready':False,'matches':0,'visible_controls':[],'findings':['Not visible']}
    monkeypatch.setattr(api.controller,'call',fake_call)
    response=TestClient(api.app,base_url='http://127.0.0.1:8766').get('/api/workflows/surajlabs/purchase_indent/preflight-first')
    assert response.status_code==200
    assert response.json()['matches']==0
    assert calls[0][0]=='preflight_first'
    assert calls[0][1]['first_step']['locator']['name']=='+ Purchase Order'
