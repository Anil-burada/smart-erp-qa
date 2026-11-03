"""Regression tests for backend startup stability and EPIPE prevention."""
import threading
from fastapi.testclient import TestClient
from backend.browser import BrowserController
from backend.api import app


def test_browser_worker_does_not_start_on_controller_construction():
    ctrl=BrowserController()
    assert ctrl.worker is None
    assert ctrl.call('status')['open'] is False
    assert ctrl.worker is None
    assert ctrl.worker_error is None
    ctrl.shutdown()
    assert ctrl.worker is None


def test_health_endpoint_does_not_spawn_playwright(monkeypatch):
    from backend import api
    ctrl=BrowserController()
    monkeypatch.setattr(api,'controller',ctrl)
    with TestClient(app, base_url='http://127.0.0.1:8766') as client:
        assert client.get('/api/health').json()['ok'] is True
        assert ctrl.worker is None


def test_worker_starts_only_on_first_browser_command(monkeypatch):
    ctrl=BrowserController()
    def fake_loop():
        ctrl.worker_ready.set()
        action, data, future=ctrl.commands.get(timeout=3)
        assert action=='open'
        future.set_result({'open':False})
    monkeypatch.setattr(ctrl,'_loop',fake_loop)
    assert ctrl.worker is None
    assert ctrl.call('open') == {'open':False}
    assert ctrl.worker is not None
    ctrl.worker.join(3)


def test_windows_launcher_contract():
    from pathlib import Path
    root=Path(__file__).resolve().parents[1]
    main=(root/'desktop/main.js').read_text()
    bat=(root/'Start-Desktop-Windows.bat').read_text()
    assert 'desktop_backend.stderr.log' in main
    assert "['-u','run.py']" in main
    assert 'npm.cmd start' in bat
    assert (root/'Check-Desktop-Setup.ps1').exists()
