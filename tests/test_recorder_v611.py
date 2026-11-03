"""Regression checks for the v6.1.1 capture patch (no live ERP credentials)."""
from pathlib import Path
from backend.browser import BrowserController
from backend.record_js import RECORDER_JS


def test_custom_controls_and_select_changes_supported():
    assert '[role="menuitem"]' in RECORDER_JS
    assert '[role="option"]' in RECORDER_JS
    assert '[role="tab"]' in RECORDER_JS
    assert "document.addEventListener('change',event=>{" in RECORDER_JS
    assert "flushText(el)" in RECORDER_JS
    assert 'input[type=password]' in RECORDER_JS
    assert 'window.erpRecorderEvent(step)' in RECORDER_JS


def test_recorder_health_cannot_read_erp_credentials():
    class Page:
        frames=[object()]
        def is_closed(self): return False
        def evaluate(self,script):
            assert 'password' not in script.lower()
            return {'installed':True,'version':'6.1.2','bridge':True}
    c=BrowserController.__new__(BrowserController)
    c.page=Page();c.recording=True;c.steps=[{}]
    data=c._do_health()
    assert data['installed'] and data['recording'] and data['step_count']==1
    assert not any(k in str(data).lower() for k in ('password','username','token'))


def test_live_dashboard_no_longer_redraws_workflow_form_on_every_click():
    source=(Path(__file__).resolve().parents[1]/'frontend'/'app.js').read_text()
    assert "const live=$('recorderLive')" in source
    assert 'if(changed&&!state.editing&&!state.editingLocators&&!typing)render();' not in source
    assert "action==='recorder-health'" in source
