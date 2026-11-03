"""Regression coverage for title vs visible-text recorder behavior."""
import os
from backend.record_js import RECORDER_JS
from backend.locator import locate


def test_recorded_button_name_prefers_visible_text_over_title():
    assert "const body = isEditable ? '' : norm(el.innerText || el.textContent || el.value);" in RECORDER_JS
    assert "labels(el)[0] || body || attr(el,'title')" in RECORDER_JS


def test_recorded_role_locator_replays_real_button_with_title():
    # An actual browser checks the recorder candidates against Playwright's
    # accessibility semantics; no ERP network or account is involved.
    if not os.path.exists('/usr/bin/chromium'):
        import pytest
        pytest.skip('Chromium not installed in test environment')
    from playwright.sync_api import sync_playwright
    captured=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(headless=True,executable_path='/usr/bin/chromium',args=['--no-sandbox'])
        try:
            ctx=browser.new_context()
            ctx.expose_binding('erpRecorderEvent', lambda _source, data: captured.append(data))
            page=ctx.new_page()
            page.set_content('''<button class="nav__child" title="A department asks for material to be bought">Purchase Requisition</button>''')
            page.evaluate(RECORDER_JS)
            page.get_by_role('button',name='Purchase Requisition').click()
            page.wait_for_timeout(250)
            assert captured, 'No click was recorded'
            step=captured[0]
            assert step['locator']=={'kind':'role','role':'button','name':'Purchase Requisition'},step
            assert locate(page,step['locator']).count()==1
            assert locate(page,step['locator']).is_visible()
        finally:
            browser.close()
