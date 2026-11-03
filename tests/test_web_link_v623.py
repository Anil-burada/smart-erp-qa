"""Web-only mode and recording notification wiring (offline regression)."""
from pathlib import Path
from fastapi.testclient import TestClient
from backend.api import app

ROOT = Path(__file__).resolve().parents[1]


def test_web_entrypoint_and_health():
    with TestClient(app, base_url='http://127.0.0.1:8766') as client:
        r = client.get('/')
        assert r.status_code == 200
        assert 'globalRecordingStatus' in r.text
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json()['ok'] is True


def test_live_notifications_only_on_recorded_steps():
    script = (ROOT / 'frontend' / 'app.js').read_text(encoding='utf-8')
    assert "page!=='browser'" not in script[script.index('render();void refresh();setInterval'):]
    assert "['browser','workflows','projects'].includes(state.page)" in script
    assert 'notifyNewCapturedSteps(state.session,session,preview)' in script
    assert 'recent?.action' in script and 'recent?.target_text' in script
    assert 'recent?.value' not in script


def test_link_launcher_not_desktop():
    content = (ROOT / 'Open-Smart-ERP-Web.ps1').read_text(encoding='utf-8')
    assert "SMART_ERP_DESKTOP = '0'" in content
    assert 'Start-Desktop-Windows.bat' not in content
    assert '127.0.0.1:8766' in content
    assert (ROOT / 'Open-Smart-ERP-Web.bat').exists()


def test_embedded_save_then_review_and_replay():
    script = (ROOT / 'frontend' / 'app.js').read_text(encoding='utf-8')
    assert 'embedded-save' in script
    assert "api('/recorder/stop','POST',{name})" in script
    assert 'Check &amp; Replay Approved Workflow' in script
    assert 'if(!w.reviewed)throw new Error' in script
