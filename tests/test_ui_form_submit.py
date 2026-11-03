"""Guard against the browser form.id shadowing bug."""
from pathlib import Path


def test_project_registration_uses_stable_form_match():
    source = (Path(__file__).resolve().parents[1] / "frontend" / "app.js").read_text(encoding="utf-8")
    assert "e.target.matches('form#projectForm')" in source
    assert "e.target.id!=='projectForm'" not in source
    assert "<form id=\"projectForm\" method=\"post\">" in source
    assert "await api('/projects','POST',raw)" in source
