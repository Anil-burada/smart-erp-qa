"""No live ERP calls; test script-login migration only."""
import ast
import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / 'working_scripts/procurement/pi_lpo_grn.py'
HELPER = Path(__file__).resolve().parents[1] / 'scripts/migrate_leocem_script_login.py'


def load_helper():
    spec = importlib.util.spec_from_file_location('login_migration', HELPER)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_script_login_uses_own_code_and_has_no_env_requirement():
    source = SCRIPT.read_text(encoding='utf-8')
    ast.parse(source)
    assert 'password_input.fill(username)' in source
    assert 'SMART_ERP_REQUIRED_CREDENTIALS = []' in source
    assert 'Missing local test-account passwords' not in source


def test_upgrade_preserves_other_source_edits(tmp_path):
    helper = load_helper()
    original = SCRIPT.read_text(encoding='utf-8')
    legacy = original.replace(helper.NEW_REQUIRED, helper.ORIGINAL_REQUIRED)
    legacy = legacy.replace(helper.NEW_LOGIN, helper.ORIGINAL_LOGIN)
    legacy = legacy.replace('    with sync_playwright() as p:', helper.ORIGINAL_CHECK + '    with sync_playwright() as p:')
    legacy += '\n# CUSTOM TESTER EDIT PRESERVED\n'
    target = tmp_path / 'pi_lpo_grn.py'
    target.write_text(legacy, encoding='utf-8')
    assert helper.migrate(target) is True
    result = target.read_text(encoding='utf-8')
    assert result == original + '\n# CUSTOM TESTER EDIT PRESERVED\n'
    assert helper.migrate(target) is False


def test_customized_env_login_not_overwritten(tmp_path):
    import pytest
    helper = load_helper()
    target=tmp_path/'script.py'
    source='def login():\n    password = os.environ.get(f"ERPQA_KAGAMI_{username}_PASSWORD", "")\n    print(password)\n'
    target.write_text(source, encoding='utf-8')
    with pytest.raises(ValueError, match='customized'):
        helper.migrate(target)
    assert target.read_text(encoding='utf-8') == source
