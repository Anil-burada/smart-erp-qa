"""Fixed Leocem launch configuration. Never silently target a production URL."""
import os
from urllib.parse import urlsplit
from dotenv import dotenv_values
from backend.registry import BASE, Project, get_project, list_projects, normalize_url, save_project
from backend import script_workspace as sw

SCRIPT_ID = 'procurement/pi_lpo_grn.py'
PROJECT_ID = 'leocem_automation'


def settings():
    local = dotenv_values(BASE / '.env')
    def get(key):
        # Explicit process environment takes precedence, then local .env.
        return str(os.environ.get(key) if os.environ.get(key) is not None else local.get(key) or '').strip()
    return get


def readiness():
    get = settings()
    raw_url = get('ERPQA_LEOCEM_TEST_URL')
    environment = get('ERPQA_LEOCEM_ENVIRONMENT').lower()
    issues = []
    url = ''
    if not raw_url:
        issues.append('Set ERPQA_LEOCEM_TEST_URL to your authorized Leocem TEST/STAGING URL in .env.')
    else:
        try:
            url = normalize_url(raw_url)
            parts = urlsplit(url)
            hostname = (parts.hostname or '').lower()
            if (parts.scheme != 'https' or
                not (hostname == 'kagamierp.com' or hostname.endswith('.kagamierp.com')) or
                parts.path.rstrip('/').lower() != '/leocem'):
                issues.append('The Leocem URL must use HTTPS, a kagamierp.com host, and the /leocem path.')
        except (ValueError, TypeError) as exc:
            issues.append('Invalid Leocem URL: ' + str(exc)[:130])
    if environment not in ('test', 'staging'):
        issues.append('Set ERPQA_LEOCEM_ENVIRONMENT=test or staging in .env. Production is not supported.')
    try:
        source, _ = sw.inspect_source(SCRIPT_ID)
        if not source['valid']:
            issues.append('Saved script has a syntax error: ' + str(source.get('error', 'unknown')))
    except (ValueError, OSError) as exc:
        source = None
        issues.append('Leocem script unavailable: ' + str(exc))
    required = source['required_credentials'] if source else []
    missing = [name for name in required if not get(name)]
    if missing:
        issues.append('Set the required test-account password variables in .env: ' + ', '.join(missing))
    matching = next((p for p in list_projects() if p['url'] == url), None) if url else None
    if matching and matching['environment'] not in ('test', 'staging'):
        issues.append('Configured Leocem URL is registered as production. Execution is blocked.')
    if matching and matching['browser'] != 'chromium':
        issues.append('The matching Leocem project must use Chromium.')
    existing = get_project(PROJECT_ID)
    if existing and url and existing['url'] != url and not matching:
        issues.append('The fixed Leocem project has a different URL. Review the saved project before changing its target.')
    return {
        'ready': not issues, 'issues': issues,
        'script_id': SCRIPT_ID, 'script': source,
        'url': url, 'environment': environment,
        'project_id': matching['id'] if matching else PROJECT_ID,
        'browser_mode': 'new',
        'note': 'New Chromium browser. The script logs in using the configured test accounts, changes roles, and runs the dependent PI to LPO to GRN flow. This can write ERP records.'
    }


def ensure_project(config):
    if not config['ready']:
        raise ValueError('Leocem is not ready: ' + ' '.join(config['issues']))
    current = get_project(config['project_id'])
    if current:
        if current['url'] != config['url'] or current['environment'] not in ('test', 'staging') or current['browser'] != 'chromium':
            raise ValueError('Existing Leocem project no longer matches the reviewed test environment.')
        return current
    return save_project(Project(id=PROJECT_ID, name='Leocem QA Automation',
        appName='Leocem Procurement', url=config['url'], environment=config['environment'],
        browser='chromium', description='Fixed PI to LPO to GRN Playwright workflow; VS Code editable'))
