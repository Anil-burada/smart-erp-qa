"""Reviewed workflow -> downloadable, inspectable Playwright POM project.

Exports code only. It never browses, records, approves, or executes ERP mutations.
Business assertions are included only if they exist in the reviewed workflow.
"""
from __future__ import annotations

import io
import json
import keyword
import re
import zipfile
from collections import OrderedDict
from urllib.parse import urlsplit

from backend.json_workflow import fingerprint, read_library
from backend.locator import Workflow
from backend.negative_cases import generate_candidates
from backend.registry import get_project

WRITES = re.compile(r'\b(save|submit|create|approve|post|delete|remove|confirm|release|receive|issue|update)\b', re.I)
VAR = re.compile(r'^\$\{([a-z][a-z0-9_]*)\}$')
ASSERTIONS = {'assert_visible', 'assert_text', 'assert_value'}


def ident(value: str, prefix: str = 'page') -> str:
    clean = re.sub(r'[^a-zA-Z0-9_]+', '_', value).strip('_').lower()
    if not clean or clean[0].isdigit() or keyword.iskeyword(clean):
        clean = prefix + '_' + clean
    return clean[:70]


def _stage_key(url: str, index: int) -> str:
    path = urlsplit(url).path.strip('/')
    # A SPA can retain one URL through multiple forms. Keep the displayed
    # business step sequence even if page class is shared.
    return ident(path.replace('/', '_') or 'home')


def _locator(step, library):
    result = library.fields[step.target].locator if library else step.locator
    return result.model_dump(exclude_none=True)


def create_bundle(workflow: Workflow) -> bytes:
    if not workflow.reviewed or not workflow.steps:
        raise ValueError('Approve a non-empty reviewed workflow before generating a POM bundle')
    project = get_project(workflow.project_id)
    if not project:
        raise ValueError('ERP project is not registered')
    if project['environment'] not in ('test', 'staging'):
        raise ValueError('POM automation export is permitted only for TEST/STAGING projects')
    library = read_library(workflow.project_id) if workflow.schema_version == 2 else None
    if library and fingerprint(workflow, library) != workflow.locator_fingerprint:
        raise ValueError('Locator library has changed. Re-review and approve the workflow')
    if any(s.observed_count != 1 for s in workflow.steps):
        raise ValueError('Every recorded step must have a verified unique locator')
    if any(s.action == 'fill' and isinstance(s.value, str) and ('password' in (s.target_text or '').lower()) for s in workflow.steps):
        raise ValueError('Sensitive input detected in workflow; re-record without credentials')

    stages = OrderedDict()
    actions = []
    runtime_names = set()
    for index, step in enumerate(workflow.steps, start=1):
        key = _stage_key(step.page_url or workflow.start_url, index)
        if key not in stages:
            stages[key] = len(stages) + 1
        locator = _locator(step, library)
        if step.action in ('capture_text', 'capture_value') and not step.output:
            raise ValueError(f'Step {index} needs a configured output variable')
        if isinstance(step.value, str) and VAR.fullmatch(step.value):
            runtime_names.add(VAR.fullmatch(step.value).group(1))
        actions.append(dict(step=index, page_key=key, action=step.action, locator=locator,
                            label=step.target_text[:120], value=step.value, output=step.output,
                            page_url=step.page_url))

    has_writes = any(s.action == 'click' and WRITES.search((s.target_text or '') + ' ' + (s.target or '')) for s in workflow.steps)
    assertions = sum(s.action in ASSERTIONS for s in workflow.steps)
    project_root = f"{ident(workflow.project_id)}_{ident(workflow.name)}_pom"
    files = {}
    files['pages/__init__.py'] = ''
    files['workflows/__init__.py'] = ''
    files['pages/base_page.py'] = '''"""Reusable Playwright POM locator/action helpers. Never guess a missing control."""
from playwright.sync_api import expect

class BasePage:
    def __init__(self, page):
        self.page = page

    def find(self, spec):
        kind = spec['kind']
        if kind == 'role':
            target = self.page.get_by_role(spec['role'], name=spec['name'], exact=True)
        elif kind == 'css':
            target = self.page.locator(spec['value'])
        elif kind == 'test_id':
            target = self.page.get_by_test_id(spec['value'])
        elif kind == 'label':
            target = self.page.get_by_label(spec['value'], exact=True)
        elif kind == 'placeholder':
            target = self.page.get_by_placeholder(spec['value'], exact=True)
        elif kind == 'title':
            target = self.page.get_by_title(spec['value'], exact=True)
        elif kind == 'text':
            target = self.page.get_by_text(spec['value'], exact=True)
        else:
            raise ValueError(f'Unsupported locator kind: {kind}')
        count = target.count()
        if count != 1:
            raise AssertionError(f'Expected one locator match, got {count}: {spec}')
        target.wait_for(state='visible', timeout=12000)
        if target.count() != 1:
            raise AssertionError(f'Locator changed during wait: {spec}')
        return target

    def perform(self, spec, action, value=None, output=None):
        target = self.find(spec)
        if action == 'click': target.click()
        elif action == 'fill': target.fill('' if value is None else str(value))
        elif action == 'select_option': target.select_option(str(value))
        elif action == 'press': target.press(str(value))
        elif action == 'check': target.check()
        elif action == 'uncheck': target.uncheck()
        elif action == 'assert_visible': expect(target).to_be_visible()
        elif action == 'assert_text': expect(target).to_have_text(str(value))
        elif action == 'assert_value': expect(target).to_have_value(str(value))
        elif action == 'capture_text': return target.inner_text().strip()
        elif action == 'capture_value': return target.input_value().strip()
        else: raise ValueError(f'Unsupported recorded action: {action}')
        return None
'''
    class_names = {}
    page_lines = ['"""Generated page objects grouped by the observed URL; no invented selectors."""', 'from pages.base_page import BasePage', '']
    for key in stages:
        cls = ''.join(s.capitalize() for s in key.split('_')) + 'Page'
        if cls in class_names.values():
            cls = f'{cls}{stages[key]}'
        class_names[key] = cls
        page_lines.extend([f'class {cls}(BasePage):', f'    """Captured screen group {key}."""'])
        for item in [a for a in actions if a['page_key'] == key]:
            page_lines.append(f'    LOCATOR_{item["step"]:03d} = {item["locator"]!r}')
        page_lines += ['', '']
    files['pages/erp_pages.py'] = '\n'.join(page_lines)

    module_name = ident(workflow.name, 'workflow')
    lines = [
        '"""Generated reviewed workflow orchestrator. Manual login is required."""',
        'from urllib.parse import urlsplit',
        'from pages.erp_pages import ' + ', '.join(class_names.values()),
        '',
        f'PROJECT_ROOT = {project["url"]!r}',
        f'PROJECT_ENVIRONMENT = {project["environment"]!r}',
        f'CONTAINS_WRITES = {has_writes!r}',
        f'ASSERTION_COUNT = {assertions}',
        '',
        'def replay(page, test_data=None, allow_writes=False):',
        '    if PROJECT_ENVIRONMENT not in ("test", "staging"):',
        '        raise ValueError("Production automation is prohibited")',
        '    current, root = urlsplit(page.url), urlsplit(PROJECT_ROOT)',
        '    prefix = root.path.rstrip("/")',
        '    if (current.scheme, current.netloc) != (root.scheme, root.netloc) or not (current.path.rstrip("/") == prefix or current.path.startswith(prefix + "/")):',
        '        raise ValueError("ERP browser does not match registered project URL")',
        '    if page.locator("input[type=password]:visible").count():',
        '        raise ValueError("Log in manually before replaying")',
        '    if CONTAINS_WRITES and not allow_writes:',
        '        raise ValueError("Explicitly approve TEST/STAGING transactions before running")',
        '    test_data = test_data or {}',
        '    outputs = {}',
    ]
    for key, cls in class_names.items():
        lines.append(f'    {key}_page = {cls}(page)')
    for item in actions:
        value = item['value']
        if isinstance(value, str) and VAR.fullmatch(value):
            param = VAR.fullmatch(value).group(1)
            value_str = f'test_data[{param!r}]'
        else:
            value_str = repr(value)
        target = f'{item["page_key"]}_page'
        safe_label = re.sub("[\r\n\u2028\u2029]", " ", item["label"])[:80]
        lines.append(f'    # Step {item["step"]}: {item["action"]} — {safe_label}')
        lines.append(f'    result = {target}.perform({target}.LOCATOR_{item["step"]:03d}, {item["action"]!r}, {value_str}, {item["output"]!r})')
        if item['output']:
            lines.append(f'    outputs[{item["output"]!r}] = result')
    lines += ['    return outputs', '']
    files[f'workflows/{module_name}.py'] = '\n'.join(lines)

    tests_init = '''"""Connect to a manually logged-in authorized TEST/STAGING browser.

The fixture never launches a new ERP login and never stores credentials.
"""
import os
import pytest
from playwright.sync_api import sync_playwright
from workflows.WORKFLOW_MODULE import PROJECT_ROOT
from urllib.parse import urlsplit

@pytest.fixture
def erp_page():
    if os.getenv('SMART_ERP_TEST_RUN') != '1':
        pytest.skip('Set SMART_ERP_TEST_RUN=1 to opt into connecting to the live ERP browser')
    endpoint = os.getenv('SMART_ERP_CDP_URL', 'http://127.0.0.1:9337')
    with sync_playwright() as p:
        browser = p.chromium.connect_over_cdp(endpoint, timeout=15000)
        root = urlsplit(PROJECT_ROOT)
        pages = [page for ctx in browser.contexts for page in ctx.pages
                 if urlsplit(page.url).scheme == root.scheme
                 and urlsplit(page.url).netloc == root.netloc
                 and (urlsplit(page.url).path.rstrip('/') == root.path.rstrip('/')
                      or urlsplit(page.url).path.startswith(root.path.rstrip('/') + '/'))]
        if len(pages) != 1:
            pytest.fail(f'Expected one matching logged-in ERP page, got {len(pages)}; open only one matching ERP tab')
        yield pages[0]
    # sync_playwright context ends the CDP client, not the user session.
'''.replace('WORKFLOW_MODULE',module_name)
    files['tests/conftest.py'] = tests_init
    files['tests/test_positive.py'] = f'''"""Replay and verify only the explicit recorded assertions, if any."""
import json
import os
import pytest
from workflows.{module_name} import replay, ASSERTION_COUNT, CONTAINS_WRITES

@pytest.mark.positive
def test_reviewed_workflow(erp_page):
    if CONTAINS_WRITES and os.getenv('SMART_ERP_ALLOW_WRITES') != '1':
        pytest.skip('Set SMART_ERP_ALLOW_WRITES=1 to explicitly authorize TEST/STAGING writes')
    test_data = json.loads(os.getenv('SMART_ERP_TEST_DATA', '{{}}'))
    replay(erp_page, test_data, allow_writes=os.getenv('SMART_ERP_ALLOW_WRITES') == '1')
    if ASSERTION_COUNT == 0:
        # This confirms actions completed, not ERP business correctness.
        print('No business assertions were recorded: action-only replay result')
'''
    candidates = generate_candidates(workflow, library) if library else []
    files['tests/test_negative.py'] = '''"""Safe native HTML field checks only. No Save/Submit/Approve action is executed."""
import os
import pytest
from pages.base_page import BasePage

CANDIDATES = __CANDIDATES__

@pytest.mark.negative
@pytest.mark.parametrize('candidate', CANDIDATES)
def test_native_field_constraint(erp_page, candidate):
    if os.getenv('SMART_ERP_NEGATIVE') != '1':
        pytest.skip('Set SMART_ERP_NEGATIVE=1 only while viewing the corresponding TEST/STAGING form')
    target = BasePage(erp_page).find(candidate['locator'])
    # Negative checks operate only on supported text/number native form fields.
    original = target.input_value()
    try:
        target.fill(candidate['invalid_value'])
        assert target.evaluate('(el) => el.checkValidity()') is False, candidate['id']
    finally:
        target.fill(original)
'''.replace('__CANDIDATES__',repr([{**c, 'locator': library.fields[c['target']].locator.model_dump(exclude_none=True)} for c in candidates] if library else []))
    files['tests/test_structure.py'] = '''"""Offline POM package consistency tests. Safe without an ERP browser."""
from pages.erp_pages import *
from workflows.WORKFLOW_MODULE import ASSERTION_COUNT, CONTAINS_WRITES

def test_generated_module_imports():
    assert ASSERTION_COUNT >= 0
    assert isinstance(CONTAINS_WRITES, bool)
'''.replace('WORKFLOW_MODULE',module_name)
    files['pytest.ini'] = '[pytest]\nmarkers =\n    positive: Reviewed workflow replay\n    negative: Native HTML field-constraint check\n'
    files['test_data.example.json'] = json.dumps({name: f'REPLACE_{name.upper()}' for name in sorted(runtime_names)}, indent=2)
    files['workflow_snapshot.json'] = json.dumps({'project_id': workflow.project_id, 'name': workflow.name,
                                                  'schema_version': workflow.schema_version, 'steps': actions,
                                                  'approved_at_export': True}, indent=2)
    files['negative_candidates.json'] = json.dumps(candidates, indent=2)
    manifest = {'project_id': workflow.project_id, 'workflow': workflow.name, 'environment': project['environment'],
                'steps': len(actions), 'page_objects': list(class_names.values()),
                'explicit_assertions': assertions, 'native_negative_cases': len(candidates),
                'contains_potential_writes': bool(has_writes), 'requires_manual_login': True}
    files['manifest.json'] = json.dumps(manifest, indent=2)
    files['README.md'] = f'''# Smart ERP QA — Generated Page Object Model\n\nProject: `{workflow.project_id}` · Workflow: `{workflow.name}` · Environment: **{project['environment']}**\n\nGenerated from an approved workflow with **{len(actions)}** steps and **{assertions} explicit assertions**.\nThere are **{len(candidates)} native HTML constraint negative candidates** (not inferred business-rule tests).\n\n## Structure\n- `pages/base_page.py`: strict unique/visible locator check and Playwright actions\n- `pages/erp_pages.py`: page objects grouped by recorded URL (SPAs may share a class)\n- `workflows/{module_name}.py`: ordered workflow orchestration and recorded assertions\n- `workflow_snapshot.json`: reviewed action and locator snapshot\n- `tests/test_positive.py`: opt-in live replay against the manually logged-in ERP\n- `tests/test_negative.py`: opt-in HTML validity checks; never clicks Save or Submit\n\n## Run (Windows PowerShell)\nUse the same Python environment that installed Playwright and pytest. Open the exact ERP project in Smart ERP Desktop, log in manually, and return the browser to the starting screen.\n\nRun an offline check (no ERP interaction):\n\n```powershell\n& 'C:\\path\\to\\your\\.venv\\Scripts\\python.exe' -m pytest -q tests/test_structure.py\n```\n\nTo run browser automation, explicitly set `SMART_ERP_TEST_RUN=1` and optionally `SMART_ERP_CDP_URL` (defaults to `http://127.0.0.1:9337`).\nIf the reviewed workflow creates/saves/approves records, also set `SMART_ERP_ALLOW_WRITES=1` for a TEST/STAGING environment only.\nProvide runtime variables through `SMART_ERP_TEST_DATA`, a JSON object, **never passwords**.\n\n```powershell\n$env:SMART_ERP_TEST_RUN = '1'\n$env:SMART_ERP_ALLOW_WRITES = '1'  # ONLY if approved for TEST/STAGING writes\n& 'C:\\path\\to\\your\\.venv\\Scripts\\python.exe' -m pytest -q tests/test_positive.py --junitxml=positive_results.xml\n```\n\nFor safe native-form checks on the current form, set `SMART_ERP_NEGATIVE=1` and run `tests/test_negative.py` separately. No submit or save action occurs.\n\n## Important limits\nA locator that was unique during recording may still fail when the application changes. No automatic element guessing or arbitrary `.first()` fallback is used.\n{assertions} business/assertion steps were recorded; if zero, a passed run means actions succeeded, not that PI/PO/GRN calculations or permissions were verified.\nCross-user approval/login stages require separate authorized sessions and separately reviewed workflows.\nThe generated pytest JUnit report is local to this ZIP; the Smart ERP dashboard records outcomes of its built-in reviewed replay and native negative checks.\n'''
    for filename, content in files.items():
        if filename.endswith('.py'):
            compile(content, filename, 'exec')
    bio = io.BytesIO()
    with zipfile.ZipFile(bio, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for path, content in sorted(files.items()):
            archive.writestr(f'{project_root}/{path}', content)
    return bio.getvalue()
