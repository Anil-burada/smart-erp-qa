from pathlib import Path
from backend.browser import BrowserController
from backend.record_js import RECORDER_JS

ROOT=Path(__file__).resolve().parents[1]

def test_dashboard_teaching_ui_no_standalone_prompts():
    js=(ROOT/'frontend/app.js').read_text()
    assert 'Start Teaching ERP (After Login)' in js
    assert "action==='teach-erp'" in js
    assert 'Finish Demonstration & Save JSON' in js
    assert 'data-action="close"' in js
    assert (ROOT/'Open-Smart-ERP-Dashboard.bat').exists()

def test_recorder_has_enhanced_button_and_input_capture():
    assert 'findClickControl(event.target)' in RECORDER_JS
    assert '[aria-haspopup]' in RECORDER_JS
    assert "document.addEventListener('input',event=>" in RECORDER_JS
    assert "window.erpRecorderEvent(step)" in RECORDER_JS
    assert 'isLoginArea(el)' in RECORDER_JS

def test_recording_requires_explicit_start_after_login():
    s=(ROOT/'backend/browser.py').read_text()
    assert 'self.auto_capture = False' in s
    assert 'self.recording = False' in s
    assert "def _do_start(self):" in s
