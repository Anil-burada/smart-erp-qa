"""No browser required: verify the safe native check never submits a form."""
from backend import browser

class FakeLocator:
    def __init__(self):
        self.value='5'
        self.fills=[]
    def is_visible(self):return True
    def evaluate(self, script):
        if 'typeof el.checkValidity' in script:return True
        return {'valid': not (float(self.value)<1), 'willValidate': True}
    def input_value(self, timeout=None):return self.value
    def fill(self, value, timeout=None):
        self.fills.append(value)
        self.value=value

class FakePage:
    def is_closed(self):return False

def test_negative_runner_only_fills_and_restores(monkeypatch):
    target=FakeLocator()
    monkeypatch.setattr(browser,'unique',lambda page,spec:target)
    worker=browser.BrowserController.__new__(browser.BrowserController)
    worker.page=FakePage()
    worker.active_project={'id':'mock_erp','environment':'test'}
    worker.recording=False
    data=worker._do_negative_check(
        workflow={'project_id':'mock_erp','name':'pi','reviewed':True},
        cases=[{'id':'NEG-001','locator':{'kind':'test_id','value':'quantity'},'invalid_value':'0'}]
    )
    assert data['summary']['PASSED']==1
    assert target.fills==['0','5']
    assert target.value=='5'

def test_production_never_runs_negative_checks():
    worker=browser.BrowserController.__new__(browser.BrowserController)
    worker.page=FakePage()
    worker.active_project={'id':'mock_erp','environment':'production'}
    worker.recording=False
    try:
        worker._do_negative_check({'project_id':'mock_erp','name':'pi','reviewed':True},[])
        assert False, 'Production checks should be blocked'
    except ValueError as err:
        assert 'prohibited on production' in str(err)
