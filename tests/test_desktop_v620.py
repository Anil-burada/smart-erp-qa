"""Desktop CDP integration contract; no live ERP required."""
from pathlib import Path
from types import SimpleNamespace
import pytest
from fastapi.testclient import TestClient
from backend.browser import BrowserController
from backend.api import app

ROOT=Path(__file__).resolve().parents[1]

class StubPage:
    def __init__(self,url): self.url=url;self.scripts=[];self.bindings=[];self.timeout=None;self.closed=False
    def is_closed(self):return self.closed
    def set_default_timeout(self, n):self.timeout=n
    def expose_binding(self,name,func):self.bindings.append(name)
    def add_init_script(self,script):self.scripts.append(script)
    def evaluate(self,script):self.scripts.append(script)
class StubContext:
    def __init__(self,pages):self.pages=pages;self.events=[];self.closed=False
    def on(self,*args):self.events.append(args[0])
    def close(self):self.closed=True
class StubBrowser:
    def __init__(self,contexts):self.contexts=contexts;self.closed=False
    def close(self):self.closed=True

@pytest.fixture
def ctrl():
    ctl=BrowserController.__new__(BrowserController)
    ctl.page=None;ctl.browser=None;ctl.context=None;ctl.active_project=None
    ctl.login_candidates=None;ctl.login_verified=False;ctl.electron_attached=False
    ctl.embedded=False;ctl.recording=False;ctl.paused=False;ctl.steps=[];ctl.warnings=[]
    ctl.auto_capture=False;ctl.start_url='';ctl.embedded_width=1440;ctl.embedded_height=850
    ctl._capture_login_candidates=lambda: {'detected':False}
    return ctl

def test_attach_same_origin_and_no_navigation(ctrl):
    dashboard=StubPage('http://127.0.0.1:8766/')
    erp=StubPage('https://ba.kagamierp.com/leocem')
    ctx=StubContext([dashboard,erp]);br=StubBrowser([ctx])
    calls=[]
    ctrl.p=SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda endpoint,timeout: (calls.append(endpoint) or br)))
    result=ctrl._do_attach_electron({'id':'leocem_ba','url':erp.url,'browser':'chromium','environment':'test'},9337)
    assert calls==['http://127.0.0.1:9337']
    assert result['electron'] is True
    assert result['url']==erp.url
    assert erp.bindings==['erpRecorderEvent']
    assert len(erp.scripts)==2
    assert not dashboard.scripts
    ctrl._do_close()
    assert not ctx.closed  # Never closes Electron's browser context.
    assert br.closed       # Only CDP connection is released.

def test_ambiguous_target_fail_closed(ctrl):
    pg=StubPage('https://ba.kagamierp.com/leocem')
    br=StubBrowser([StubContext([pg,StubPage(pg.url)])])
    ctrl.p=SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda *a,**kw:br))
    with pytest.raises(ValueError, match='Expected one Electron ERP tab'):
        ctrl._do_attach_electron({'id':'test','url':pg.url,'browser':'chromium','environment':'test'},9337)
    assert br.closed and ctrl.page is None

def test_desktop_endpoint_gated(monkeypatch):
    monkeypatch.delenv('SMART_ERP_DESKTOP',raising=False)
    with TestClient(app,base_url='http://127.0.0.1:8766') as client:
        r=client.post('/api/browser/electron/attach',json={'project_id':'x','cdp_port':9337})
        assert r.status_code==403
        assert client.get('/api/health').json()['desktop_enabled'] is False

def test_desktop_code_contract():
    main=(ROOT/'desktop/main.js').read_text()
    js=(ROOT/'frontend/app.js').read_text()
    assert 'WebContentsView' in main and 'nodeIntegration:false' in main
    assert 'contextIsolation:true' in main and 'sandbox:true' in main
    assert 'remote-debugging-address' in main
    assert "desktop:open-erp" in main and "desktop:close-erp" in main
    assert 'window.smartERPDesktop.openERP' in js
    assert "window.smartERPDesktop.setPage(state.page)" in js


def test_same_origin_dashboard_not_mistaken_for_mock_erp(ctrl):
    erp=StubPage('http://127.0.0.1:8766/mock')
    dashboard=StubPage('http://127.0.0.1:8766/')
    ctx=StubContext([dashboard,erp]);br=StubBrowser([ctx])
    ctrl.p=SimpleNamespace(chromium=SimpleNamespace(connect_over_cdp=lambda *a,**kw:br))
    result=ctrl._do_attach_electron({'id':'mock_erp','url':erp.url,'browser':'chromium','environment':'test'},9337)
    assert result['url']==erp.url and ctrl.page is erp
