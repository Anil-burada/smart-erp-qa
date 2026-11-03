"""Leocem negative testing: source-referenced, non-persistent Playwright checks.

This is a separate dashboard script. It never clicks the parent form's Save,
Submit, Approve, or Delete controls. Only a PI item editor's OK control is
used to test whether an invalid quantity is rejected before it can be added.
The real ERP, role permissions, selectors and validation text can change.
Unverified outcomes are REVIEW, never a fabricated PASS.
"""
from __future__ import annotations

import os
import re
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright, expect, TimeoutError as PlaywrightTimeout
from backend.script_runtime import emit, capture_failure, check
from backend.v636_negative_nav import global_search
from backend import v636_po_negative as po

SMART_ERP_REQUIRED_CREDENTIALS = []
TIMEOUT = 25000
PI_QTY = '[id="PurchaseIndentItemDetails_92.indentQty"]'
ITEM_ID = '[id="PurchaseIndentItemDetails_92.itemId"]'
CASES = (
    ('PI-NEG-001', 'Zero quantity', '0', 'PI rejects zero quantity'),
    ('PI-NEG-002', 'Negative quantity', '-1', 'PI rejects negative quantity'),
    ('PI-NEG-003', 'Empty quantity', '', 'PI requires a nonempty quantity'),
    ('PI-NEG-004', 'Alphabetic quantity', 'abc', 'PI rejects nonnumeric quantity'),
)

# The login, PI, approval and LPO controls below are taken from the reviewed
# PI -> LPO -> GRN positive source. Invalid credentials are NOT guessed and
# no failed-password retry loop is used (account-lockout risk).
LOGIN_CASES = (
    ('AUTH-NEG-001', 'Login with empty username', 'username', 'ERP does not authenticate with an empty username'),
    ('AUTH-NEG-002', 'Login with empty password', 'password', 'ERP does not authenticate with an empty password'),
)
PI_FORM_CASES = (
    ('PI-NEG-005', 'PI missing department', 'PurchaseIndent_37.departmentId',
     'Department must be required before a Purchase Indent can be created'),
)
APPROVAL_CASES = (
    ('PI-NEG-006', 'PI approval without record selection',
     'Approve action is unavailable until a PI has been explicitly selected'),
)


def _report(case, status, expected, actual, page=None):
    name = case[0] + ' | ' + case[1]
    evidence = None
    if status in ('FAILED', 'REVIEW', 'BLOCKED') and page is not None:
        evidence = capture_failure(page, name, expected, actual)
    emit('check', name=name, status=status, expected=expected,
         actual=actual, process='Purchase Indent input validation',
         category='Negative', evidence=evidence,
         testcase_id=os.environ.get('SMART_ERP_CASE_ID') or case[0])
    print(f'{status}: {name}: {actual}', flush=True)


def _report_scenario(case_id, title, status, expected, actual, page, process):
    evidence = capture_failure(page, case_id + ' | ' + title, expected, actual) \
        if status in ('FAILED', 'REVIEW', 'BLOCKED') and page is not None else None
    emit('check', name=case_id + ' | ' + title, status=status, expected=expected,
         actual=actual, category='Negative', process=process, evidence=evidence,
         testcase_id=os.environ.get('SMART_ERP_CASE_ID') or case_id)
    print(f'{status}: {case_id}: expected={expected}; actual={actual}', flush=True)
    return status


def _error_messages(page, field=None, search=r'required|empty|missing|invalid|enter|username|password|department'):
    """Only visible and field-specific errors count; an unchanged form is not PASS."""
    messages = []
    if field is not None:
        try:
            if field.get_attribute('aria-invalid') == 'true':
                messages.append('Field aria-invalid=true')
            invalid = field.evaluate('el => !!el.validity && !el.validity.valid')
            if invalid:
                messages.append('Browser marked field invalid')
        except Exception:
            pass
    for selector in ('[role="alert"]:visible', '.MuiFormHelperText-root:visible',
                     '.MuiAlert-message:visible', '.Mui-error:visible',
                     '.invalid-feedback:visible'):
        try:
            for message in page.locator(selector).all_inner_texts():
                message = message.strip()
                if message and re.search(search, message, re.I):
                    messages.append(message[:140])
        except Exception:
            pass
    return list(dict.fromkeys(messages))


def _negative_login(page, case):
    case_id, title, blank_field, expected = case
    try:
        username = page.locator('#username')
        password = page.locator('#password')
        expect(username).to_be_visible(timeout=TIMEOUT)
        expect(password).to_be_visible(timeout=TIMEOUT)
        # Exactly the #username/#password and LOGIN link from the positive login().
        test_user = os.environ.get('ERPQA_LEOCEM_NEGATIVE_USERNAME', 'DMG0013').strip()
        username.fill('' if blank_field == 'username' else test_user)
        password.fill('' if blank_field == 'password' else 'unused')
        # Never print credentials; never perform repeated bad-password attempts.
        login_button = page.get_by_role('link', name='LOGIN', exact=True)
        expect(login_button).to_be_visible(timeout=TIMEOUT)
        if login_button.get_attribute('aria-disabled') == 'true':
            return _report_scenario(case_id, title, 'PASSED', expected,
                'LOGIN control visibly disabled by ERP before submission', page, 'Authentication')
        login_button.click()
        page.wait_for_timeout(950)
        if page.locator('div.pro-sidebar:visible').count():
            return _report_scenario(case_id, title, 'FAILED', expected,
                'Authenticated sidebar appeared despite the missing required credential', page, 'Authentication')
        messages = _error_messages(page, username if blank_field == 'username' else password)
        if messages:
            return _report_scenario(case_id, title, 'PASSED', expected,
                'ERP/browser validation: ' + '; '.join(messages), page, 'Authentication')
        if page.locator('#username:visible').count():
            return _report_scenario(case_id, title, 'REVIEW', expected,
                'Login page remained visible, but no explicit validation or disabled control was observed', page, 'Authentication')
        return _report_scenario(case_id, title, 'BLOCKED', expected,
            'Neither login form nor sidebar was observable after the attempt', page, 'Authentication')
    except Exception as exc:
        return _report_scenario(case_id, title, 'BLOCKED', expected,
            'Could not verify login validation: ' + str(exc)[:350], page, 'Authentication')


def _negative_pi_header(page, case):
    case_id, title, field_id, expected = case
    try:
        _open_pi_creation(page)
        field = page.locator('[id="' + field_id + '"]')
        expect(field).to_be_visible(timeout=TIMEOUT)
        # The form is newly opened. Never clear an unknown pre-populated field,
        # and never click Save or Submit to trigger a server-side rule.
        value = (field.input_value() or '').strip()
        if value:
            return _report_scenario(case_id, title, 'BLOCKED', expected,
                'Field was already populated; refusing to clear an unknown value', page,
                'Purchase Indent required fields')
        field.press('Tab')
        page.wait_for_timeout(430)
        messages = _error_messages(page, field, r'department|required|select|invalid|missing')
        if messages:
            return _report_scenario(case_id, title, 'PASSED', expected,
                'Unsaved field validation appeared: ' + '; '.join(messages), page,
                'Purchase Indent required fields')
        return _report_scenario(case_id, title, 'REVIEW', expected,
            'Empty field remained but no explicit validation before Save; Save deliberately not clicked',
            page, 'Purchase Indent required fields')
    except Exception as exc:
        return _report_scenario(case_id, title, 'BLOCKED', expected,
            'PI header form or field unavailable: ' + str(exc)[:350], page,
            'Purchase Indent required fields')


def _negative_pi_approval(page, case):
    case_id, title, expected = case
    try:
        # Same global-search module and Approve button name as approve_indent().
        global_search(page, 'purchaseindent approval', 'Purchase Indent Approval')
        expect(page.locator('.ag-root:visible').first).to_be_visible(timeout=TIMEOUT)
        approval = page.get_by_role('button', name='Approve', exact=True).and_(page.locator(':visible'))
        count = approval.count()
        if count == 0:
            return _report_scenario(case_id, title, 'PASSED', expected,
                'No visible Approve action before selecting a PI (UI-only check)',
                page, 'PI approval guard')
        if count == 1 and not approval.is_enabled():
            return _report_scenario(case_id, title, 'PASSED', expected,
                'Approve control is disabled without a selected PI (UI-only check)',
                page, 'PI approval guard')
        return _report_scenario(case_id, title, 'REVIEW', expected,
            f'Observed {count} visible Approve control(s), possibly enabled. No action clicked; authorization not proven.',
            page, 'PI approval guard')
    except Exception as exc:
        return _report_scenario(case_id, title, 'BLOCKED', expected,
            'Approval screen/locator unavailable: ' + str(exc)[:350], page, 'PI approval guard')


def _authorized_url():
    url = os.environ.get('ERP_URL', '').strip()
    mode = os.environ.get('ERPQA_LEOCEM_ENVIRONMENT', '').strip().lower()
    parts = urlsplit(url)
    hostname = (parts.hostname or '').lower()
    if mode not in ('test', 'staging') or parts.scheme != 'https' or (
        hostname != 'kagamierp.com' and not hostname.endswith('.kagamierp.com')
    ) or parts.path.rstrip('/').lower() != '/leocem':
        raise RuntimeError('Negative test is allowed only on a configured HTTPS Leocem test/staging URL')
    return url


def _login(page):
    user = os.environ.get('ERPQA_LEOCEM_NEGATIVE_USERNAME', 'DMG0013').strip()
    # The supplied positive test script uses username == password for these test accounts.
    # Override locally in .env if credentials differ; never print a password.
    password = os.environ.get('ERPQA_LEOCEM_NEGATIVE_PASSWORD') or user
    if not user:
        raise RuntimeError('ERPQA_LEOCEM_NEGATIVE_USERNAME is blank')
    username = page.locator('#username')
    if username.is_visible(timeout=7000):
        expect(page.locator('#password')).to_be_visible(timeout=TIMEOUT)
        username.fill(user)
        page.locator('#password').fill(password)
        page.get_by_role('link', name='LOGIN', exact=True).click()
    expect(page.locator('div.pro-sidebar')).to_be_visible(timeout=TIMEOUT)
    print('Login confirmed for negative test account', flush=True)


def _open_pi_creation(page):
    """Open the unsaved PI form using conservative, observable search controls."""
    global_search(page, 'PurchaseIndent Creation', 'Purchase Indent Creation')
    expect(page.locator('.ag-root:visible').first).to_be_visible(timeout=TIMEOUT)
    create = page.get_by_role('button', name=re.compile(r'^\s*CREATE\s*$', re.I)).and_(page.locator(':visible'))
    expect(create).to_have_count(1, timeout=TIMEOUT)
    create.click()


def _option_list(page, field):
    listbox = field.get_attribute('aria-controls')
    if listbox:
        scoped = page.locator('[id="' + listbox.replace('"', '\\"') + '"] [role="option"]:visible')
        if scoped.count():
            return scoped
    return page.locator('[role="option"]:visible')


def _select_first(page, field_id, exact=None):
    """Use selection only on this unsaved form, never change master data."""
    field = page.locator('[id="' + field_id + '"]')
    expect(field).to_be_visible(timeout=TIMEOUT)
    field.click()
    deadline = time.monotonic() + 12
    while time.monotonic() < deadline:
        choices = _option_list(page, field)
        options = []
        for i in range(choices.count()):
            choice = choices.nth(i)
            if choice.is_enabled():
                label = choice.inner_text().strip()
                if label and (exact is None or label.casefold() == exact.casefold()):
                    options.append((label, choice))
        if options:
            if exact is not None and len(options) != 1:
                raise RuntimeError(f'Ambiguous form option {exact!r}')
            label, choice = options[0]
            choice.click()
            print(f'Form value set for {field_id}: {label}', flush=True)
            return
        page.wait_for_timeout(300)
    raise RuntimeError(f'No selectable option for field {field_id}')


def _prepare_item_editor(page):
    # Header fields follow the supplied positive source; all remain UNSAVED.
    _select_first(page, 'PurchaseIndent_37.indentTypeId')
    _select_first(page, 'PurchaseIndent_37.departmentId')
    _select_first(page, 'PurchaseIndent_37.purchaseTypeId', 'Local Purchase')
    _select_first(page, 'PurchaseIndent_37.sectionId')
    _select_first(page, 'PurchaseIndent_37.assetMasterId')
    # Only the item editor is needed to exercise negative quantity rules.
    add = page.locator('svg[data-testid="PlaylistAddOutlinedIcon"]:visible')
    expect(add).to_have_count(1, timeout=TIMEOUT)
    add.click()
    _select_first(page, 'PurchaseIndentItemDetails_92.itemId')
    qty = page.locator(PI_QTY)
    expect(qty).to_be_visible(timeout=TIMEOUT)
    expect(qty).to_be_enabled(timeout=TIMEOUT)
    return qty


def _visible_validation(page, qty):
    """Do not claim a rejection from the script's own numeric guard."""
    errors = []
    invalid = qty.get_attribute('aria-invalid') == 'true'
    try:
        invalid = invalid or not qty.evaluate('el => el.validity.valid')
    except Exception:
        pass
    if invalid:
        errors.append('Quantity field marked invalid by the browser/ERP')
    for selector in (
        '[role="alert"]:visible', '.MuiFormHelperText-root:visible',
        '.MuiAlert-message:visible', '.Mui-error:visible'
    ):
        for raw in page.locator(selector).all_inner_texts():
            message = raw.strip()
            if message and re.search(r'quantit|qty|required|invalid|greater|zero|number|enter', message, re.I):
                if message not in errors:
                    errors.append(message[:170])
    return errors


def _run_case(page, case):
    _id, _name, invalid_value, expected = case
    _open_pi_creation(page)
    qty = _prepare_item_editor(page)
    try:
        qty.fill(invalid_value)
    except Exception as exc:
        # A number input may refuse to accept letters before ERP validation.
        if invalid_value == 'abc' and qty.get_attribute('type') == 'number':
            _report(case, 'PASSED', expected,
                    'Numeric browser field refused alphabetic characters before item confirmation', page)
            return 'PASSED'
        _report(case, 'REVIEW', expected, 'Cannot prove validation from input failure: ' + str(exc)[:180], page)
        return 'REVIEW'
    qty.press('Tab')
    page.wait_for_timeout(400)
    errors = _visible_validation(page, qty)
    if errors:
        _report(case, 'PASSED', expected, 'Rejected before item OK: ' + '; '.join(errors), page)
        return 'PASSED'

    # The item-editor OK is NOT the document Save/Submit. Click once to invoke
    # any item-level validation; never click the outer form Save/Submit/Approve.
    ok = page.get_by_role('button', name=re.compile(r'^\s*ok\s*$', re.I)).and_(
        page.locator(':visible'))
    if ok.count() != 1:
        _report(case, 'REVIEW', expected,
                f'Cannot uniquely trigger item-level validation (OK count={ok.count()})', page)
        return 'REVIEW'
    ok.click()
    page.wait_for_timeout(900)
    try:
        editor_still_open = qty.is_visible()
    except Exception:
        editor_still_open = False
    errors = _visible_validation(page, qty) if editor_still_open else []
    if editor_still_open and errors:
        _report(case, 'PASSED', expected, 'Item editor remains open; ' + '; '.join(errors), page)
        return 'PASSED'
    if not editor_still_open:
        _report(case, 'FAILED', expected,
                f'Item editor closed after invalid quantity {invalid_value!r}; invalid item may have been accepted in unsaved form', page)
        return 'FAILED'
    _report(case, 'REVIEW', expected,
            'Editor remains open but no unambiguous validation message/invalidity was detected', page)
    return 'REVIEW'


LOGIN_ACTIONS = {
    'neg_login_blank_username': 'AUTH-NEG-001',
    'neg_login_blank_password': 'AUTH-NEG-002',
}
PI_ACTIONS = {
    'neg_pi_zero': 'PI-NEG-001',
    'neg_pi_negative': 'PI-NEG-002',
    'neg_pi_empty': 'PI-NEG-003',
    'neg_pi_alpha': 'PI-NEG-004',
    'neg_pi_missing_department': 'PI-NEG-005',
}
APPROVAL_ACTIONS = {'neg_pi_approval_guard': 'PI-NEG-006'}
PO_ACTIONS = {
    'neg_po_missing_pi': 'LPO-NEG-001',
    'neg_po_missing_vendor': 'LPO-NEG-002',
    'neg_po_blank_number': 'LPO-NEG-003',
    'neg_po_alpha_number': 'LPO-NEG-004',
    'neg_po_zero_qty': 'LPO-NEG-005',
}
ALL_ACTIONS = (set(LOGIN_ACTIONS) | set(PI_ACTIONS) | set(APPROVAL_ACTIONS) |
               set(PO_ACTIONS) | {'neg_login_all', 'neg_pi_all', 'neg_po_all', 'neg_all'})


def _selected():
    action = os.environ.get('SMART_ERP_CASE_ACTION', '').strip()
    if action and action not in ALL_ACTIONS:
        raise RuntimeError('The case action is not mapped to the reviewed negative Login -> LPO runner.')
    everything = (not action or action == 'neg_all')
    login_cases = [c for c in LOGIN_CASES if everything or action == 'neg_login_all' or LOGIN_ACTIONS.get(action) == c[0]]
    pi_cases = [c for c in CASES if everything or action == 'neg_pi_all' or PI_ACTIONS.get(action) == c[0]]
    header_cases = [c for c in PI_FORM_CASES if everything or action == 'neg_pi_all' or PI_ACTIONS.get(action) == c[0]]
    approval_cases = [c for c in APPROVAL_CASES if everything or APPROVAL_ACTIONS.get(action) == c[0]]
    po_cases = [c for c in po.LPO_NEGATIVE_CASES if everything or action == 'neg_po_all' or PO_ACTIONS.get(action) == c[1]]
    return login_cases, pi_cases, header_cases, approval_cases, po_cases


def smart_erp_run_negative_scenarios():
    """Run 13 non-persistent, script-grounded UI negatives from login through LPO.

    Login: 2 empty-credential cases (no password guessing).
    PI: 4 invalid quantities + 1 missing department.
    PI approval: 1 no-selected-record UI guard (does not click Approve).
    LPO: 5 unsaved field validations.
    Each case uses its own fresh browser context; no ERP document is saved.
    """
    url = _authorized_url()
    login_cases, pi_cases, header_cases, approval_cases, po_cases = _selected()
    total = sum(map(len, (login_cases, pi_cases, header_cases, approval_cases, po_cases)))
    if not total:
        raise RuntimeError('The selected negative test case has no reviewed executable step.')
    counters = {'PASSED': 0, 'FAILED': 0, 'REVIEW': 0, 'BLOCKED': 0}
    emit('stage_start', name='Negative Login to LPO', category='Negative',
         expected='Authentication and PI/approval/LPO invalid states are guarded without document persistence')
    print(f'Negative run: {len(login_cases)} login + {len(pi_cases)+len(header_cases)} PI + '
          f'{len(approval_cases)} approval + {len(po_cases)} LPO cases. No Save/Submit/Approve/Delete.', flush=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=False, slow_mo=220)
        try:
            def fresh(run_case, case, login_function=None, on_error=None):
                context = browser.new_context(no_viewport=True)
                page = context.new_page()
                page.set_default_timeout(TIMEOUT)
                try:
                    page.goto(url, wait_until='domcontentloaded', timeout=60000)
                    if login_function:
                        login_function(page)
                    status = run_case(page, case)
                    if status not in counters:
                        raise RuntimeError('Negative test did not return a recognized status')
                except Exception as exc:
                    status = 'BLOCKED'
                    expected = case[-1]
                    if on_error:
                        on_error(case, status, str(exc)[:450], page)
                    else:
                        _report_scenario(case[0], case[1], status, expected,
                            'Precondition/navigation unavailable: ' + str(exc)[:450], page,
                            'Login through LPO negative setup')
                finally:
                    context.close()  # Discard every form; NO ERP document persistence.
                counters[status] += 1

            for case in login_cases:
                fresh(_negative_login, case)  # Starts at login page; no authenticated session.
            for case in pi_cases:
                fresh(_run_case, case, login_function=_login)
            for case in header_cases:
                fresh(_negative_pi_header, case, login_function=_login)
            for case in approval_cases:
                fresh(_negative_pi_approval, case,
                      login_function=lambda page: po.login_for_po(page, TIMEOUT))
            for case in po_cases:
                fresh(lambda page, case: po.run_po_case(page, case, TIMEOUT), case,
                      login_function=lambda page: po.login_for_po(page, TIMEOUT),
                      on_error=lambda case, status, message, page:
                          po._report(case, status, 'LPO precondition unavailable: '+message, page))
        finally:
            browser.close()
    overall = ('FAILED' if counters['FAILED'] else
               'REVIEW' if counters['REVIEW'] or counters['BLOCKED'] else 'PASSED')
    emit('stage_end', name='Negative Login to LPO', status=overall,
         expected='All invalid states rejected without any ERP document Save/Submit/Approve',
         actual=f'Results from {total} attempted cases: {counters}', category='Negative')
    if counters['FAILED']:
        raise AssertionError(f'{counters["FAILED"]} negative test(s) saw an invalid state accepted')
    print('Negative login to LPO checks finished; NO PI or PO document was saved, submitted or approved.', flush=True)


if __name__ == '__main__':
    smart_erp_run_negative_scenarios()
