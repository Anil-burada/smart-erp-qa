"""Project-specific login LOCATORS, never account credentials.

Login flows using SSO, OTP, CAPTCHA, or custom widgets require manual login.
"""
from __future__ import annotations

from pydantic import BaseModel, ConfigDict, field_validator

from backend.json_workflow import atomic_json
from backend.locator import LocatorSpec
from backend.registry import BASE, PROJECT_PATTERN, get_project


class LoginConfig(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project_id: str
    project_url: str
    username: LocatorSpec
    password: LocatorSpec
    submit: LocatorSpec
    success: LocatorSpec

    @field_validator('schema_version')
    @classmethod
    def supported(cls, value: int) -> int:
        if value != 1:
            raise ValueError('Unsupported login configuration version')
        return value


def login_path(project_id: str):
    if not PROJECT_PATTERN.fullmatch(project_id) or not get_project(project_id):
        raise ValueError('Unknown ERP project')
    return BASE / 'projects' / project_id / 'login.json'


def load_login_config(project_id: str) -> LoginConfig:
    path = login_path(project_id)
    if not path.exists():
        raise ValueError('Configure login locators for this ERP before automatic login')
    result = LoginConfig.model_validate_json(path.read_text(encoding='utf-8'))
    if result.project_id != project_id or result.project_url != get_project(project_id)['url']:
        raise ValueError('Login configuration does not match the registered ERP URL; review locators')
    return result


def save_login_config(project_id: str, config: LoginConfig) -> LoginConfig:
    if config.project_id != project_id or config.project_url != get_project(project_id)['url']:
        raise ValueError('Login configuration project ID or URL mismatch')
    path = login_path(project_id)
    atomic_json(path, config.model_dump_json(indent=2))
    return config


def login_template(project_id: str) -> dict:
    login_path(project_id)  # project validation
    # These locators match the included mock ERP only. Other ERP users must
    # inspect and verify their own login locators before saving the file.
    return {
        'schema_version': 1,
        'project_id': project_id,
        'project_url': get_project(project_id)['url'],
        'username': {'kind': 'css', 'value': '#username'},
        'password': {'kind': 'css', 'value': '#password'},
        'submit': {'kind': 'css', 'value': '#loginBtn'},
        'success': {'kind': 'css', 'value': '#dashboard'},
    }
