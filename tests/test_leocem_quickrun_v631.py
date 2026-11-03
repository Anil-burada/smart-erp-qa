"""Direct Leocem selection tests. Never starts a real ERP browser."""
import pytest
from backend import leocem_quickrun as quick
from backend import registry, script_workspace as sw


@pytest.fixture
def local(tmp_path, monkeypatch):
    monkeypatch.setattr(registry, 'DB', tmp_path / 'data' / 'test.sqlite3')
    registry.init_db()
    root=tmp_path/'working_scripts'; (root/'procurement').mkdir(parents=True)
    (root/'procurement'/'pi_lpo_grn.py').write_text('''SMART_ERP_REQUIRED_CREDENTIALS=[]\nprint("synthetic")\n''')
    monkeypatch.setattr(sw,'WORKSPACE',root)
    return tmp_path


def fake_settings(extra=None):
    values=dict(ERPQA_LEOCEM_TEST_URL='https://intraruntime.kagamierp.com/leocem',ERPQA_LEOCEM_ENVIRONMENT='test')
    values.update(extra or {})
    return lambda key: values.get(key,'')


def test_missing_url_fails_closed_but_password_env_not_required(local,monkeypatch):
    monkeypatch.setattr(quick,'settings',lambda:fake_settings({'ERPQA_LEOCEM_TEST_URL':''}))
    assert quick.readiness()['ready'] is False
    monkeypatch.setattr(quick,'settings',lambda:fake_settings())
    assert quick.readiness()['ready'] is True


def test_bad_target_rejected(local,monkeypatch):
    for target in ('https://random.com/leocem','https://intraruntime.kagamierp.com/other','http://intraruntime.kagamierp.com/leocem'):
        monkeypatch.setattr(quick,'settings',lambda target=target:fake_settings({'ERPQA_LEOCEM_TEST_URL':target}))
        assert not quick.readiness()['ready']


def test_production_environment_is_blocked(local,monkeypatch):
    monkeypatch.setattr(quick,'settings',lambda:fake_settings({'ERPQA_LEOCEM_ENVIRONMENT':'production'}))
    assert not quick.readiness()['ready']


def test_ready_registers_fixed_project_without_user_selection(local,monkeypatch):
    monkeypatch.setattr(quick,'settings',lambda:fake_settings())
    result=quick.readiness();assert result['ready'] and result['script_id']=='procurement/pi_lpo_grn.py'
    assert result['project_id']=='leocem_automation'
    project=quick.ensure_project(result)
    assert project['environment']=='test' and project['browser']=='chromium'
    assert project['url']=='https://intraruntime.kagamierp.com/leocem'
    assert quick.readiness()['project_id']=='leocem_automation'


def test_existing_production_project_never_used(local,monkeypatch):
    registry.save_project(registry.Project(id='other1',name='Bad registration',appName='ERP',url='https://intraruntime.kagamierp.com/leocem',environment='production'))
    monkeypatch.setattr(quick,'settings',lambda:fake_settings())
    assert not quick.readiness()['ready']


def test_direct_run_uses_fixed_leocem_script_new_browser(local, monkeypatch):
    """An API request cannot select a different ERP or arbitrary script path."""
    from backend import api
    from fastapi import HTTPException
    monkeypatch.setattr(quick, 'settings', lambda: fake_settings())
    cfg=quick.readiness()
    assert cfg['ready']
    calls=[]
    monkeypatch.setattr(api.script_manager, 'start', lambda body, controller: calls.append(body) or {'id': 'synthetic'})
    with pytest.raises(HTTPException) as denied:
        api.leocem_run(api.LeocemLaunch(reviewed_sha256=cfg['script']['sha256']))
    assert denied.value.status_code==400
    result=api.leocem_run(api.LeocemLaunch(reviewed_sha256=cfg['script']['sha256'], acknowledge_test_transactions=True, acknowledge_trusted_code=True))
    assert result['id']=='synthetic'
    assert calls[0].script_id=='procurement/pi_lpo_grn.py'
    assert calls[0].mode=='new'
    assert calls[0].project_id=='leocem_automation'
    with pytest.raises(HTTPException) as stale:
        api.leocem_run(api.LeocemLaunch(reviewed_sha256='0'*64, acknowledge_test_transactions=True, acknowledge_trusted_code=True))
    assert stale.value.status_code==400
