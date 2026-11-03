"""Embedded ERP session: safety, UI contract, and local API behavior."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from backend.api import app
from backend.browser import BrowserController


class Mouse:
    def __init__(self): self.events=[]
    def click(self,x,y,**kwargs): self.events.append(('click',x,y))
    def dblclick(self,x,y,**kwargs): self.events.append(('dblclick',x,y))
    def wheel(self,x,y): self.events.append(('wheel',x,y))

class Keyboard:
    def __init__(self): self.events=[]
    def insert_text(self,text): self.events.append(('type',text))
    def press(self,key): self.events.append(('press',key))

class Page:
    def __init__(self): self.mouse=Mouse();self.keyboard=Keyboard()
    def is_closed(self): return False
    def screenshot(self,**options):
        assert options['type']=='jpeg' and not options.get('full_page')
        return b'\xff\xd8test\xff\xd9'


def controller_stub():
    ctl=BrowserController.__new__(BrowserController)
    ctl.page=Page();ctl.embedded=True;ctl.embedded_width=1440;ctl.embedded_height=850
    return ctl


def test_embedded_controls_are_dispatches_to_same_page():
    ctl=controller_stub()
    assert ctl._do_embedded_frame().startswith(b'\xff\xd8')
    ctl._do_embedded_action('click',x=123,y=221)
    ctl._do_embedded_action('dblclick',x=500,y=200)
    ctl._do_embedded_action('scroll',delta_y=260)
    ctl._do_embedded_action('type',text='Purchase Indent')
    ctl._do_embedded_action('press',key='Enter')
    assert ctl.page.mouse.events==[('click',123,221),('dblclick',500,200),('wheel',0,260)]
    assert ctl.page.keyboard.events==[('type','Purchase Indent'),('press','Enter')]

@pytest.mark.parametrize('action',[
    {'kind':'click','x':1440,'y':4},
    {'kind':'click','x':-1,'y':4},
    {'kind':'press','key':'F12'},
    {'kind':'type','text':'x'*2049},
    {'kind':'scroll','delta_y':1800},
    {'kind':'evaluate','text':'alert(1)'},
])
def test_embedded_rejects_unsafe_or_bad_actions(action):
    with pytest.raises(ValueError): controller_stub()._do_embedded_action(**action)


def test_requires_embedded_session():
    ctl=controller_stub();ctl.embedded=False
    with pytest.raises(ValueError):ctl._do_embedded_frame()
    with pytest.raises(ValueError):ctl._do_embedded_action('click',x=1,y=1)


def test_local_embedded_api(monkeypatch):
    from backend import api as api_module
    calls=[]
    def mocked_call(name, **kwargs):
        calls.append((name,kwargs))
        if name=='embedded_frame':return b'\xff\xd8hi\xff\xd9'
        return {'ok':True}
    monkeypatch.setattr(api_module.controller,'call',mocked_call)
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        frame=client.get('/api/browser/embedded/frame')
        assert frame.status_code==200 and frame.headers['content-type']=='image/jpeg'
        assert frame.headers['cache-control']=='no-store, private'
        action=client.post('/api/browser/embedded/action',json={'kind':'click','x':1,'y':2})
        assert action.status_code==200 and calls[-1][1]['x']==1
        bad=client.post('/api/browser/embedded/action',json={'kind':'click','x':-5,'y':2})
        assert bad.status_code==422
        assert client.post('/api/browser/embedded/action',json={'kind':'type','text':'x'*2050}).status_code==422


def test_dashboard_has_embedded_view_and_workflow_manager():
    root=Path(__file__).parents[1]
    js=(root/'frontend/app.js').read_text(encoding='utf-8')
    css=(root/'frontend/styles.css').read_text(encoding='utf-8')
    assert 'embeddedPanel()' in js
    assert "embedded:true" in js
    assert "go('projects')" in js
    assert 'Manage Saved Workflows' in js
    assert 'remove-saved-workflow' in js
    assert '95vh' in css
