"""Regression checks for replay-start ambiguity across multiple ERP applications."""
from types import SimpleNamespace
from backend.browser import BrowserController
from backend.record_js import RECORDER_JS
from backend.locator import locate

class StubLoc:
    def __init__(self, vis): self.vis=vis
    def count(self): return len(self.vis)
    def nth(self,n): return SimpleNamespace(is_visible=lambda: self.vis[n])

class StubPage:
    url='https://erp.example.com/demo'
    def is_closed(self): return False
    def get_by_role(self, role,name,exact):
        if name=='Procurement':return StubLoc([])
        if name=='Purchase Indent':return StubLoc([True])
        return StubLoc([])
    def locator(self,value):
        if value=='input[type="password"]:visible':return StubLoc([])
        return StubLoc([True]*9)
    def evaluate(self,code):
        return [{'text':'Purchase Indent','role':'button'}]

def test_zero_match_with_safe_alternative_is_diagnostic_only():
    obj=BrowserController.__new__(BrowserController)
    obj.page=StubPage();obj.active_project={'id':'erp'}
    first={'locator':{'kind':'role','role':'button','name':'Procurement'},
           'observed_candidates':[{'spec':{'kind':'role','role':'button','name':'Purchase Indent'},'observed_count':1}],
           'action':'click','target_text':'Procurement'}
    report=obj._do_preflight_first('erp','demo',first,'https://erp.example.com/demo',True)
    assert not report['ready']
    assert report['candidate_checks'][0]['uniquely_visible']
    assert 'No alternative was clicked' in ' '.join(report['findings'])

def test_nine_match_css_never_is_ready():
    obj=BrowserController.__new__(BrowserController)
    obj.page=StubPage();obj.active_project={'id':'erp'}
    first={'locator':{'kind':'css','value':'div > button'},'action':'click'}
    report=obj._do_preflight_first('erp','demo',first,'https://erp.example.com/demo',True)
    assert report['matches']==9
    assert report['ready'] is False


def test_recorder_prefers_stable_attributes_over_css_tree():
    assert "['data-qa','data-test','aria-label']" in RECORDER_JS
    assert 'fragile_dom_path' in RECORDER_JS
    assert 'generatedId' in RECORDER_JS


def test_real_browser_click_uses_unique_role_not_structural_css():
    import os
    if not os.path.exists('/usr/bin/chromium'):
        import pytest
        pytest.skip('No chromium available')
    from playwright.sync_api import sync_playwright
    actions=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
            ctx=browser.new_context()
            ctx.expose_binding('erpRecorderEvent',lambda source,data:actions.append(data))
            page=ctx.new_page()
            page.set_content('''<div><button>Procurement</button><button>Reports</button></div>''')
            page.evaluate(RECORDER_JS)
            page.get_by_role('button',name='Procurement').click()
            page.wait_for_timeout(200)
            assert len(actions)==1,actions
            s=actions[0]
            assert s['locator']=={'kind':'role','role':'button','name':'Procurement'},s
            assert s['locator_quality']=='stable_candidate'
            assert locate(page,s['locator']).count()==1
        finally:
            browser.close()
