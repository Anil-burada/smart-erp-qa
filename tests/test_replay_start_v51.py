"""Regression tests for replay-without-forced-redirect and selector-only discovery."""
from backend import browser, login_discovery


def test_replay_does_not_navigate_back_to_recorded_root(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, 'BASE', tmp_path)
    calls = []

    class FakeLocator:
        def __init__(self, selector):
            self.selector = selector
        def count(self):
            return 0 if self.selector == 'input[type="password"]:visible' else 1
        def click(self, **_):
            calls.append('click')
    class FakePage:
        url = 'https://test.example/erp/dashboard'
        def is_closed(self):return False
        def goto(self, *_args, **_kwargs):
            raise AssertionError('Must not reload recorded start URL after login')
        def locator(self, spec):return FakeLocator(spec)
        def screenshot(self, **_): pass
    class Trace:
        def start(self, **_): pass
        def stop(self, **_): pass
    class Context:
        tracing = Trace()

    c = browser.BrowserController.__new__(browser.BrowserController)
    c.page = FakePage()
    c.context = Context()
    c.active_project = {'id': 'erp', 'url': 'https://test.example/erp', 'environment': 'test'}
    c.recording = False
    c.auto_capture = False
    report = c._do_run({
        'project_id':'erp', 'name':'safe_navigation', 'reviewed':True,
        'start_url':'https://test.example/erp',
        'steps':[{'action':'click','locator':{'kind':'css','value':'#safe'},'target_text':'Open menu'}]
    })
    assert report['status'] == 'PASSED'
    assert report['completed_steps'] == 1
    assert calls == ['click']


def test_cached_login_selector_candidates_have_no_credentials():
    c = browser.BrowserController.__new__(browser.BrowserController)
    c.active_project = {'id':'erp', 'url':'https://test.example/erp'}
    c.login_candidates = {
        'detected': True,
        'username': {'kind':'css','value':'#username'},
        'password': {'kind':'css','value':'#password'},
        'submit': {'kind':'css','value':'#loginBtn'},
    }
    result=c._do_login_candidates()
    assert result['detected'] is True
    assert result['password']['value']=='#password'
    assert 'secret' not in str(result).lower()
    assert set(result) == {'project_id', 'detected', 'username', 'password', 'submit', 'note'}


def test_login_candidates_json_contains_only_selectors(tmp_path, monkeypatch):
    monkeypatch.setattr(login_discovery, 'BASE', tmp_path)
    data={'username':{'kind':'css','value':'#username'},
          'password':{'kind':'css','value':'#password'},
          'submit':{'kind':'css','value':'#loginBtn'},
          'untrusted_extra':'do not save'}
    result=login_discovery.save_candidates('erp','https://test.example/erp',data)
    assert result.exists()
    text=result.read_text()
    assert 'untrusted_extra' not in text
    assert '#password' in text


def test_authenticated_replay_does_not_run_while_login_visible(tmp_path, monkeypatch):
    monkeypatch.setattr(browser, 'BASE', tmp_path)
    class FakeLocator:
        def count(self): return 1
    class FakePage:
        url = 'https://test.example/erp/login'
        def is_closed(self): return False
        def locator(self, selector):
            assert selector == 'input[type="password"]:visible'
            return FakeLocator()
        def goto(self, *_a, **_kw):
            raise AssertionError('Must never reload automatically')
        def screenshot(self, **_): pass
    class Tracing:
        def start(self, **_):pass
        def stop(self, **_):pass
    class Context:
        tracing = Tracing()
    c = browser.BrowserController.__new__(browser.BrowserController)
    c.page=FakePage()
    c.context=Context()
    c.active_project={'id':'erp','url':'https://test.example/erp','environment':'test'}
    c.recording=False
    c.auto_capture=False
    r=c._do_run({'project_id':'erp','name':'safe_flow','reviewed':True,
                 'start_url':'https://test.example/erp',
                 'steps':[{'action':'click','locator':{'kind':'css','value':'#continue'},'target_text':'Open menu'}]})
    assert r['status']=='FAILED'
    assert r['completed_steps']==0
    assert 'login screen' in r['message'].lower()
