"""Regression tests for shared route-aware replay gate; no clicks or writes."""
from pathlib import Path

from backend.browser import BrowserController

ROOT = Path(__file__).resolve().parents[1]


class Locator:
    def __init__(self, visible):
        self.visible = visible
    def count(self):
        return len(self.visible)
    def nth(self, i):
        return self
    def is_visible(self):
        return bool(self.visible[0])
    def click(self, *args, **kwargs):
        raise AssertionError('Preflight must never click')
    def get_attribute(self, name):
        return None
    def inner_text(self, timeout=1000):
        return ''


class Page:
    def __init__(self, url, spec_name='Procurement', matches=1, login=False):
        self.url = url
        self.spec_name = spec_name
        self.matches = matches
        self.login = login
    def is_closed(self):
        return False
    def get_by_role(self, role, name, exact):
        assert exact
        return Locator([True] * self.matches if name == self.spec_name else [])
    def locator(self, text):
        if text == 'input[type="password"]:visible':
            return Locator([True] if self.login else [])
        return Locator([])
    def evaluate(self, script):
        return [{'role':'button', 'text': 'Procurement'}]
    def goto(self, *args, **kwargs):
        raise AssertionError('Preflight must never navigate')


def check(url='https://erp.example/plant/worklist', start='https://erp.example/plant',
          action='click', target='Procurement', name='Procurement', matches=1, reviewed=True, login=False):
    ctl = BrowserController.__new__(BrowserController)
    ctl.page = Page(url, spec_name=name, matches=matches, login=login)
    ctl.active_project = {'id':'plant'}
    first = {'action':action, 'target_text':target,
             'locator':{'kind':'role','role':'button','name':name}}
    return ctl._do_preflight_first('plant','indent',first,start,reviewed)


def test_route_change_accepts_exact_verified_navigation_click():
    result = check()
    assert result['ready'] is True
    assert result['route_verified'] is True
    assert result['reason_code'] == 'ROUTE_VERIFIED'
    assert result['matches'] == 1


def test_route_change_rejects_unverified_nav_label():
    result = check(target='Procurement', name='Other')
    assert not result['ready']
    assert result['reason_code'] == 'START_ROUTE_MISMATCH'


def test_route_change_does_not_allow_critical_button():
    result = check(target='Submit',name='Submit')
    assert not result['ready']
    assert result['reason_code'] == 'START_ROUTE_MISMATCH'


def test_route_change_does_not_allow_fill_or_field():
    result = check(action='fill')
    assert not result['ready']
    assert result['reason_code'] == 'START_ROUTE_MISMATCH'


def test_missing_locator_never_runs_and_explains_missing_match():
    result = check(matches=0)
    assert not result['ready']
    assert result['reason_code'] == 'LOCATOR_NOT_FOUND'
    assert '0 MATCHES' in result['findings'][0]


def test_many_matches_never_runs():
    result = check(matches=9)
    assert not result['ready']
    assert result['reason_code'] == 'LOCATOR_NOT_UNIQUE_OR_HIDDEN'


def test_login_never_runs_even_if_route_and_locator_appear_ready():
    result = check(login=True)
    assert not result['ready']
    assert result['reason_code'] == 'LOGIN_REQUIRED'


def test_reapproval_is_still_required():
    result = check(reviewed=False)
    assert not result['ready']
    assert result['reason_code'] == 'REVIEW_REQUIRED'


def test_dashboard_diagnoses_all_and_shows_specific_blocker():
    js=(ROOT/'frontend'/'app.js').read_text(encoding='utf-8')
    assert 'diagnose-all-replay' in js
    assert 'Replay blocked: ${state.replayPreflight.reason_code' in js
    assert 'current ERP project' in js.lower() or 'currently open ERP project' in js
    assert 'replayStartDiagnostic' in js
