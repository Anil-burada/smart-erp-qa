"""Validated project registry and SQLite persistence (no credentials)."""
import re
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit
from pydantic import BaseModel, Field, ConfigDict, field_validator

BASE = Path(__file__).resolve().parents[1]
DB = BASE / 'data' / 'erpqa.sqlite3'
PROJECT_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{1,39}$')
WORKFLOW_PATTERN = re.compile(r'^[a-z][a-z0-9_-]{0,59}$')


def normalize_url(value: str) -> str:
    p = urlsplit(value.strip())
    if p.scheme not in ('http', 'https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('Use an HTTP(S) URL without credentials, query or fragment')
    # Reject invalid ports explicitly and normalize default ports.
    port = p.port
    authority = p.hostname.lower()
    if ':' in authority and not authority.startswith('['):
        authority = f'[{authority}]'
    if port and not ((p.scheme == 'http' and port == 80) or (p.scheme == 'https' and port == 443)):
        authority += f':{port}'
    return f'{p.scheme}://{authority}{p.path.rstrip("/")}'


class Project(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    name: str = Field(min_length=1, max_length=100)
    appName: str = Field(min_length=1, max_length=100)
    url: str
    environment: str = 'test'
    browser: str = 'chromium'
    description: str = Field(default='', max_length=500)

    @field_validator('id')
    @classmethod
    def valid_id(cls, v):
        if not PROJECT_PATTERN.fullmatch(v):
            raise ValueError('Project ID must start with lowercase letter and contain 2-40 letters, digits, - or _')
        return v

    @field_validator('url')
    @classmethod
    def valid_url(cls, v):
        return normalize_url(v)

    @field_validator('environment')
    @classmethod
    def valid_environment(cls, v):
        if v not in ('test', 'staging', 'production'):
            raise ValueError('Environment must be test, staging or production')
        return v

    @field_validator('browser')
    @classmethod
    def valid_browser(cls, v):
        if v not in ('chromium', 'firefox', 'webkit'):
            raise ValueError('Unsupported browser')
        return v


def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with connect() as c:
        c.execute('CREATE TABLE IF NOT EXISTS projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, app_name TEXT NOT NULL, url TEXT UNIQUE NOT NULL, environment TEXT NOT NULL, browser TEXT NOT NULL, description TEXT NOT NULL)')
        c.execute('CREATE TABLE IF NOT EXISTS workflows (project_id TEXT NOT NULL, name TEXT NOT NULL, reviewed INTEGER NOT NULL DEFAULT 0, step_count INTEGER NOT NULL, updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (project_id,name))')
        c.execute('CREATE TABLE IF NOT EXISTS executions (id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL, workflow_name TEXT NOT NULL, status TEXT NOT NULL, step_number INTEGER, message TEXT, artifact_path TEXT, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP, ended_at TEXT)')


def list_projects():
    with connect() as c:
        rows = c.execute('SELECT * FROM projects ORDER BY name').fetchall()
    return [{'id': r['id'], 'name': r['name'], 'appName': r['app_name'], 'url': r['url'], 'environment': r['environment'], 'browser': r['browser'], 'description': r['description']} for r in rows]


def get_project(project_id):
    return next((p for p in list_projects() if p['id'] == project_id), None)


def project_conflict(project: Project, existing):
    for other in existing:
        if other['id'] == project.id:
            continue
        a, b = project.url, other['url']
        if a == b or a.startswith(b + '/') or b.startswith(a + '/'):
            raise ValueError(f'URL overlaps another ERP project: {other["id"]}')


def save_project(project: Project):
    project_conflict(project, list_projects())
    old = get_project(project.id)
    if old and old['url'] != project.url:
        with connect() as c:
            count = c.execute('SELECT COUNT(*) FROM workflows WHERE project_id=?',(project.id,)).fetchone()[0]
        if count:
            raise ValueError('Cannot change ERP URL after workflows have been recorded. Create a new project instead')
    with connect() as c:
        c.execute('INSERT INTO projects (id,name,app_name,url,environment,browser,description) VALUES(?,?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET name=excluded.name,app_name=excluded.app_name,url=excluded.url,environment=excluded.environment,browser=excluded.browser,description=excluded.description', (project.id, project.name, project.appName, project.url, project.environment, project.browser, project.description))
    return project.model_dump()


def workflow_path(project_id: str, name: str) -> Path:
    if not PROJECT_PATTERN.fullmatch(project_id) or not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid project/workflow identifier')
    return BASE / 'workflows' / project_id / f'{name}.json'
