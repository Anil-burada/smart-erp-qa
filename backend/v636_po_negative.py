"""Additional non-persistent Leocem LPO negative scenarios.

Never Save, Submit, Approve, Delete, or trigger document persistence. Tests
that require an existing approved Purchase Indent are explicitly BLOCKED unless
an approved test PI is configured. Do not infer success from a button click.
"""
from __future__ import annotations

import os
import re
from playwright.sync_api import expect
from backend.script_runtime import emit, capture_failure
from backend.v636_negative_nav import global_search

LPO_NEGATIVE_CASES = (
    ('po_missing_pi', 'LPO-NEG-001', 'Missing Purchase Indent', 'LocalPO_194.purchaseIndentId', '', 'Purchase Indent is required'),
    ('po_missing_vendor', 'LPO-NEG-002', 'Missing vendor', 'LocalPO_194.vendorId', '', 'Vendor is required'),
    ('po_blank_number', 'LPO-NEG-003', 'Blank PO reference number', 'LocalPO_194.oldpono', '', 'PO number is required'),
    ('po_alpha_number', 'LPO-NEG-004', 'Alphabetic PO number', 'LocalPO_194.oldpono', 'abcd', 'PO number rejects nonnumeric characters'),
    ('po_zero_quantity', 'LPO-NEG-005', 'Zero line quantity', 'LocalPOdetails_195.quantity', '0', 'LPO item quantity must be greater than zero'),
)


def login_for_po(page, timeout):
    """Uses same built-in test role/password convention as supplied positive file."""
    user = os.environ.get('ERPQA_LEOCEM_NEGATIVE_PO_USERNAME', 'DMG0041').strip()
    if not user:
        raise RuntimeError('PO test username is empty')
    secret = os.environ.get('ERPQA_LEOCEM_NEGATIVE_PO_PASSWORD') or user
    expect(page.locator('#username')).to_be_visible(timeout=timeout)
    page.locator('#username').fill(user)
    page.locator('#password').fill(secret)
    page.get_by_role('link', name='LOGIN', exact=True).click()
    expect(page.locator('div.pro-sidebar')).to_be_visible(timeout=timeout)
    print('LPO negative login confirmed for test role:', user, flush=True)


def _field(page, field_id, timeout):
    control = page.locator('[id="' + field_id + '"]')
    expect(control).to_be_visible(timeout=timeout)
    expect(control).to_be_enabled(timeout=timeout)
    return control


def _choose_first(page, field_id, timeout, exact=None):
    field = _field(page, field_id, timeout)
    field.click()
    for _ in range(22):
        options = page.locator('[role="option"]:visible')
        matches = []
        for index in range(options.count()):
            option = options.nth(index)
            label = option.inner_text().strip()
            if label and option.is_enabled() and (exact is None or label.casefold() == exact.casefold()):
                matches.append((label, option))
        if matches:
            if exact is not None and len(matches) != 1:
                raise RuntimeError('Ambiguous required dropdown option: ' + exact)
            matches[0][1].click()
            return matches[0][0]
        page.wait_for_timeout(280)
    raise RuntimeError('Required form dropdown unavailable: ' + field_id)


def open_po_form(page, timeout):
    global_search(page, 'LPO creation', 'LPO Creation')
    expect(page.locator('.ag-root:visible').first).to_be_visible(timeout=timeout)
    create = page.get_by_role('button', name=re.compile(r'^\s*CREATE\s*$', re.I)).and_(page.locator(':visible'))
    expect(create).to_have_count(1, timeout=timeout)
    create.click()
    expect(page.locator('[id="LocalPO_194.poreferenceId"]')).to_be_visible(timeout=timeout)
    print('LPO unsaved form opened; no document persistence actions will be called', flush=True)


def _field_error(page, field, label):
    """Only accept observed field-specific invalidity or related validation text."""
    messages = []
    if field.get_attribute('aria-invalid') == 'true':
        messages.append('Field aria-invalid=true')
    try:
        if field.evaluate('el => typeof el.validity?.valid === "boolean" && !el.validity.valid'):
            messages.append('Browser validity=false')
    except Exception:
        pass
    try:
        parent = field.locator('xpath=ancestor::div[contains(@class,"MuiFormControl") or contains(@class,"fieldPresentation")][1]')
        if parent.count() == 1:
            for message in parent.locator('.MuiFormHelperText-root, [role="alert"]').all_inner_texts():
                if message.strip():
                    messages.append('Field message: ' + message.strip()[:140])
    except Exception:
        pass
    return list(dict.fromkeys(messages))


def _report(case, status, actual, page):
    key, case_id, name, _field_id, _data, expected = case
    evidence = capture_failure(page, case_id + ' ' + name, expected, actual) if status in ('FAILED', 'REVIEW', 'BLOCKED') else None
    emit('check', name=case_id + ' | ' + name, status=status, expected=expected,
         actual=actual, process='Local Purchase Order form validation',
         category='Negative', evidence=evidence,
         testcase_id=os.environ.get('SMART_ERP_CASE_ID') or case_id)
    print(f'{status}: {case_id}: expected={expected}; actual={actual}', flush=True)
    return status


def run_po_case(page, case, timeout):
    key, case_id, name, field_id, invalid_value, expected = case
    try:
        open_po_form(page, timeout)
        if key in ('po_missing_pi', 'po_zero_quantity'):
            _choose_first(page, 'LocalPO_194.purchaseCategoryId', timeout)
            _choose_first(page, 'LocalPO_194.poreferenceId', timeout, exact='PurchaseIndent')
        if key == 'po_zero_quantity':
            approved_pi = os.environ.get('ERPQA_LEOCEM_NEGATIVE_APPROVED_PI', '').strip()
            if not approved_pi:
                return _report(case, 'BLOCKED',
                  'Approved test PI not supplied. Set ERPQA_LEOCEM_NEGATIVE_APPROVED_PI to an approved PI number; no arbitrary PI was chosen.', page)
            _choose_first(page, 'LocalPO_194.departmentId', timeout)
            pi_control = _field(page, 'LocalPO_194.purchaseIndentId', timeout)
            pi_control.click()
            if pi_control.get_attribute('readonly') is None:
                pi_control.fill(approved_pi)
            options = page.locator('[role="option"]:visible')
            matching = []
            for i in range(options.count()):
                option = options.nth(i)
                if option.is_enabled() and approved_pi.casefold() in option.inner_text().casefold():
                    matching.append(option)
            if len(matching) != 1:
                return _report(case, 'BLOCKED',
                    f'Expected a unique approved PI {approved_pi}; found {len(matching)} matching options. No other PI selected.', page)
            matching[0].click()
            icon = page.locator('svg[data-testid="EditOutlinedIcon"]:visible')
            expect(icon).to_have_count(1, timeout=timeout)
            button = icon.locator('xpath=ancestor::button[1]')
            (button if button.count()==1 else icon).click()
        control = _field(page, field_id, timeout)
        try:
            control.fill(invalid_value)
        except Exception as exc:
            # Rejection is observable only when the actual browser field refused entry.
            if key == 'po_alpha_number' and control.get_attribute('type') == 'number':
                return _report(case, 'PASSED', 'Numeric browser input refused alphabetic characters', page)
            return _report(case, 'REVIEW', 'Could not prove validation from field input failure: ' + str(exc)[:180], page)
        control.press('Tab')
        page.wait_for_timeout(450)
        actual_value = control.input_value().strip()
        invalidity = _field_error(page, control, name)
        if invalidity:
            return _report(case, 'PASSED', f'Value={actual_value!r}; ERP/browser rejected input: {"; ".join(invalidity)}', page)
        if key in ('po_missing_pi', 'po_missing_vendor', 'po_blank_number'):
            return _report(case, 'REVIEW', 'Field left blank; no field-specific rejection appeared on blur. Save/Submit were deliberately not clicked.', page)
        if key == 'po_alpha_number' and actual_value != invalid_value:
            return _report(case, 'PASSED', f'Input sanitized from {invalid_value!r} to {actual_value!r}', page)
        return _report(case, 'REVIEW',
            f'Invalid value {invalid_value!r} remained {actual_value!r}; no visible rejection before Save/Submit (not clicked).', page)
    except Exception as exc:
        return _report(case, 'BLOCKED', 'LPO form prerequisite or locator unavailable: ' + str(exc)[:340], page)
