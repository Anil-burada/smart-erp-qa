"""Optional Smart ERP QA AI designer and change-aware, read-only regression lab.

No arbitrary model-supplied Python runs. Models return structured target IDs from a
local, reviewed locator catalog; server generates fixed-template Playwright code only
after explicit user approval. External model prompts intentionally omit locators,
ERP URLs, recordings, values, credentials, and screenshots.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.registry import BASE, get_project

router = APIRouter(prefix='/api/optional-ai', tags=['Optional AI Test Lab'])
ROOT = BASE / 'data' / 'optional_ai_lab'
DRAFTS = ROOT / 'drafts'
BASELINES = ROOT / 'baselines'
GENERATED = BASE / 'working_scripts' / 'ai_generated'
MODULE_VERSION = '636-ai-lab-1'
_LOCK = RLock()
_CONTROLLER = None
_SCRIPT_MANAGER = None
SENSITIVE = re.compile(r'password|passcode|username|token|api.?key|secret|otp|pin|credential|account.?number|ssn|auth', re.I)
SIDE_EFFECTS = re.compile(r'\b(save|submit|approve|reject|delete|remove|post|finali[sz]e|pay|upload|confirm|place order|create|update|apply|cancel|yes|ok)\b', re.I)
MODEL_NAME = re.compile(r'^[a-zA-Z0-9._:/-]{1,80}$')
SAFE_ACTIONS = {'click', 'fill', 'assert_visible', 'assert_text'}


def configure(controller, script_manager):
    global _CONTROLLER, _SCRIPT_MANAGER
    _CONTROLLER, _SCRIPT_MANAGER = controller, script_manager


def error(detail: str, status=400):
    raise HTTPException(status_code=status, detail=detail)


def ensure_project(pid):
    project = get_project(pid)
    if not project:
        error('Project not found', 404)
    if project.get('environment') not in ('test', 'staging'):
        error('Optional AI Test Lab is restricted to TEST/STAGING projects', 403)
    return project


def digest(data):
    return hashlib.sha256(json.dumps(data, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')).hexdigest()


def save_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix('.new')
    temp.write_text(json.dumps(value, indent=2, ensure_ascii=False), encoding='utf-8')
    temp.replace(path)


def load_json(path):
    return json.loads(path.read_text(encoding='utf-8'))


def clean(value, length=140):
    return re.sub(r'\s+', ' ', str(value or '')).strip()[:length]


def catalog(pid):
    """Only locators explicitly reviewed in this project's local locator library."""
    path = BASE / 'projects' / pid / 'locators.json'
    if not path.is_file():
        return []
    doc = load_json(path)
    results = []
    for target, field in (doc.get('fields') or {}).items():
        if not isinstance(field, dict) or not re.fullmatch(r'[A-Za-z0-9_.-]{3,100}', target):
            continue
        spec = field.get('locator') or {}
        if not isinstance(spec, dict) or spec.get('kind') not in ('css', 'role', 'test_id', 'text'):
            continue
        if int(field.get('observed_count') or 0) != 1:
            continue
        ident = clean(spec.get('name') or spec.get('value') or '', 160)
        label = clean(spec.get('name') or field.get('label') or target, 140)
        if any(SENSITIVE.search(x) for x in (target, ident, label)):
            continue
        if spec['kind'] == 'role' and (not spec.get('role') or not spec.get('name')):
            continue
        if spec['kind'] in ('css', 'text', 'test_id') and not spec.get('value'):
            continue
        results.append({'id': target, 'label': label, 'field_type': str(field.get('field_type') or 'unknown')[:40],
                        'locator_kind': spec['kind'], 'locator': spec})
    return results[:400]


def describe_targets(targets):
    # No actual CSS selector, ID value, field value, URL or account details in external prompts.
    return [{'id': x['id'], 'control_type': x['field_type'], 'locator_kind': x['locator_kind']}
            for x in targets]


def parse_model_json(raw):
    txt = clean(raw, 14000)
    if txt.startswith('```'):
        txt = re.sub(r'^```(?:json)?\s*|\s*```$', '', txt, flags=re.I)
    try:
        obj = json.loads(txt)
    except (TypeError, json.JSONDecodeError) as exc:
        raise ValueError('AI returned invalid JSON. No script was generated.') from exc
    if not isinstance(obj, dict) or not isinstance(obj.get('steps'), list):
        raise ValueError('AI response must contain a steps array')
    return obj['steps'][:20]


def provider_steps(provider, model, scenario, expected, targets):
    if provider == 'rules':
        terms = set(re.findall(r'[a-z0-9]+', (scenario + ' ' + expected).lower()))
        candidates = sorted(targets, key=lambda x: (len(terms & set(re.findall(r'[a-z0-9]+', x['label'].lower()))),
                                                    len(terms & set(re.findall(r'[a-z0-9]+', x['id'].lower())))), reverse=True)
        # Offline mode offers suggested targets; it does not fabricate executable assertions.
        return [{'action': 'assert_visible', 'target_id': x['id'], 'value': '', 'expected': 'Control must be visible'}
                for x in candidates[:3] if len(terms & set(re.findall(r'[a-z0-9]+', x['label'].lower()))) >= 1]
    if provider not in ('openai', 'ollama'):
        raise ValueError('Choose Rules, OpenAI, or Ollama')
    if model and not MODEL_NAME.fullmatch(model):
        raise ValueError('Invalid model name')
    prompt = ('You are a QA test-step planner. Return JSON only: '
              '{"steps":[{"action":"click|fill|assert_visible|assert_text",'
              '"target_id":"one of supplied IDs","value":"","expected":""}]}. '
              'ONLY use target_id from the supplied catalog. Choose at most 12 steps. '
              'Do not include credentials, code, selectors, Save, Submit, Approve, Delete or any record-changing action. '
              'If no safe mapping is possible return {"steps":[]}. '
              'Do not assume any validation message exists. Manual QA input:\n'
              + json.dumps({'scenario': scenario, 'expected': expected,
                            'allowed_targets': describe_targets(targets[:200])}, ensure_ascii=False))
    try:
        if provider == 'ollama':
            with httpx.Client(timeout=70) as client:
                res = client.post('http://127.0.0.1:11434/api/generate', json={
                    'model': model or os.environ.get('ERPQA_OLLAMA_MODEL', 'llama3.2'),
                    'prompt': prompt, 'stream': False, 'format': 'json'})
                res.raise_for_status()
                return parse_model_json(res.json().get('response', ''))
        try:
            from dotenv import load_dotenv
            load_dotenv(BASE / '.env', override=False)
        except ImportError:
            pass
        key = os.environ.get('OPENAI_API_KEY') or ''
        if not key:
            raise ValueError('Set OPENAI_API_KEY in the existing .env; do not enter it into a test case')
        with httpx.Client(timeout=80) as client:
            res = client.post('https://api.openai.com/v1/responses',
                  headers={'Authorization': 'Bearer ' + key},
                  json={'model': model or os.environ.get('ERPQA_OPENAI_MODEL', 'gpt-5.5'),
                        'input': prompt, 'store': False, 'max_output_tokens': 1800})
            res.raise_for_status()
            payload = res.json()
            answer = ''.join(part.get('text', '') for item in payload.get('output', [])
                             if item.get('type') == 'message' for part in item.get('content', [])
                             if part.get('type') == 'output_text')
            return parse_model_json(answer)
    except httpx.HTTPError as exc:
        raise ValueError('AI provider request failed. Verify the local Ollama service or your OpenAI key/network.') from exc


def review_steps(steps, targets, category):
    allowed = {x['id']: x for x in targets}
    good, blocked = [], []
    if not isinstance(steps, list):
        raise ValueError('Steps must be a JSON array')
    for index, item in enumerate(steps[:20], 1):
        if not isinstance(item, dict):
            blocked.append(f'Step {index}: invalid object')
            continue
        action = item.get('action')
        target = item.get('target_id')
        if action not in SAFE_ACTIONS or target not in allowed:
            blocked.append(f'Step {index}: action/locator is not in the reviewed allowlist')
            continue
        label = allowed[target]['label']
        value = str(item.get('value') or '')[:200]
        expected = str(item.get('expected') or '')[:200]
        if SENSITIVE.search(label) or SENSITIVE.search(target):
            blocked.append(f'Step {index}: sensitive control is excluded')
            continue
        if action == 'click' and (SIDE_EFFECTS.search(label) or SIDE_EFFECTS.search(target)):
            blocked.append(f'Step {index}: a record-changing button requires separately reviewed automation')
            continue
        if action == 'fill' and (SIDE_EFFECTS.search(label) or SENSITIVE.search(value)):
            blocked.append(f'Step {index}: unsafe field value')
            continue
        if action == 'assert_text' and not value.strip():
            blocked.append(f'Step {index}: expected text value is required')
            continue
        good.append({'action': action, 'target_id': target, 'value': value, 'expected': expected,
                     'label': label})
    return good, blocked


def python_locator(spec):
    kind = spec['kind']
    if kind == 'role':
        return f"page.get_by_role({spec['role']!r}, name={spec['name']!r}, exact=True)"
    if kind == 'test_id':
        return f"page.get_by_test_id({spec['value']!r})"
    if kind == 'text':
        return f"page.get_by_text({spec['value']!r}, exact=True)"
    return f"page.locator({spec['value']!r})"


def generate_python(draft, targets, steps):
    by_id = {x['id']: x for x in targets}
    lines = [
        '# Generated by Smart ERP QA Optional AI Test Lab; reviewed steps only.',
        '# TEST/STAGING only. Existing authenticated browser session is REQUIRED.',
        '# Original procurement scripts are not altered by this file.',
        'SMART_ERP_SUPPORTS_EXISTING_SESSION = True',
        'SMART_ERP_REQUIRED_CREDENTIALS = []',
        'import os',
        'from playwright.sync_api import sync_playwright, expect',
        'from backend.script_runtime import open_script_browser, check, capture_failure, emit',
        '',
        'def main():',
        '    if not os.environ.get("SMART_ERP_CDP_URL"):',
        '        raise RuntimeError("Use Existing Session mode after manually logging in to a TEST/STAGING ERP")',
        '    url = os.environ.get("ERP_URL", "")',
        '    if not url:',
        '        raise RuntimeError("ERP_URL is missing")',
        '    with sync_playwright() as pw:',
        '        browser, context, page, owned = open_script_browser(pw, url, 15000)',
        '        try:',
    ]
    for idx, step in enumerate(steps, 1):
        locator = python_locator(by_id[step['target_id']]['locator'])
        lines.extend([
            f'            # Step {idx}: {step["action"]} reviewed target {step["target_id"]}',
            f'            target = {locator}',
            '            if target.count() != 1:',
            f'                raise AssertionError("Step {idx}: approved locator is not unique in this ERP screen")',
        ])
        action = step['action']
        if action == 'click':
            lines.append('            target.click(timeout=12000)')
        elif action == 'fill':
            lines.append(f'            target.fill({step["value"]!r}, timeout=12000)')
        elif action == 'assert_visible':
            lines.append('            expect(target).to_be_visible(timeout=12000)')
        elif action == 'assert_text':
            lines.append(f'            expect(target).to_contain_text({step["value"]!r}, timeout=12000)')
        if action.startswith('assert_'):
            lines.append(f'            check({("UI assertion / " + step["label"][:65])!r}, True, {step["expected"] or step["value"] or "Element must be visible"!r}, "UI assertion observed in browser; business status needs separate verification", page=page, category={draft["category"]!r}, process="AI-generated UI assertions")')
    lines.extend([
        '        except BaseException as exc:',
        f'            capture_failure(page, {draft["scenario"][:80]!r}, {draft["expected"][:120]!r}, type(exc).__name__)',
        '            emit("blocked", name="AI-designed test stopped", expected="Review and execute approved locators", actual=type(exc).__name__, status="FAILED")',
        '            raise',
        '        finally:',
        '            if owned:',
        '                browser.close()',
        '',
        'if __name__ == "__main__":',
        '    main()',
        '',
    ])
    return '\n'.join(lines)


class DesignIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')
    scenario: str = Field(min_length=8, max_length=1500)
    expected: str = Field(min_length=4, max_length=1000)
    category: str = 'Positive'
    provider: str = 'rules'
    model: str = Field(default='', max_length=80)


class ApproveIn(BaseModel):
    draft_id: str = Field(pattern=r'^[a-f0-9]{32}$')
    project_id: str
    reviewed_catalog_hash: str = Field(pattern=r'^[a-f0-9]{64}$')
    steps: list[dict] = Field(min_length=1, max_length=20)
    approve_code: bool = False


class LiveIn(BaseModel):
    project_id: str = Field(min_length=1, max_length=80, pattern=r'^[a-zA-Z0-9_-]+$')


@router.get('/status')
def status():
    return {'installed': True, 'version': MODULE_VERSION, 'providers': ['rules', 'openai', 'ollama'],
            'ai_is_optional': True, 'scripts_run_only_after_review': True}


@router.get('/projects/{project_id}/targets')
def targets(project_id: str):
    ensure_project(project_id)
    items = catalog(project_id)
    return {'project_id': project_id, 'count': len(items), 'catalog_hash': digest(items),
            'targets': [{'id': x['id'], 'label': x['label'], 'control_type': x['field_type']} for x in items]}


@router.post('/design')
def design(body: DesignIn):
    ensure_project(body.project_id)
    if body.category not in ('Positive', 'Negative'):
        error('Category must be Positive or Negative')
    if _SCRIPT_MANAGER and _SCRIPT_MANAGER.busy:
        error('Stop the active script before changing test designs', 409)
    available = catalog(body.project_id)
    if not available:
        error('No reviewed locators available. Record and approve a workflow first.')
    try:
        raw_steps = provider_steps(body.provider, body.model, body.scenario, body.expected, available)
    except ValueError as exc:
        error(str(exc))
    steps, blocked = review_steps(raw_steps, available, body.category)
    draft_id = uuid4().hex
    doc = {'id': draft_id, 'created_at': datetime.now(timezone.utc).isoformat(),
           'project_id': body.project_id, 'scenario': body.scenario, 'expected': body.expected,
           'category': body.category, 'provider': body.provider, 'catalog_hash': digest(available),
           'steps': steps, 'blocked': blocked}
    with _LOCK:
        save_json(DRAFTS / (draft_id + '.json'), doc)
    return {**doc, 'needs_review': True, 'can_approve': bool(steps and any(x['action'].startswith('assert_') for x in steps)),
            'note': 'No code has been generated or executed. Review every locator and expectation.'}


@router.post('/approve')
def approve(body: ApproveIn):
    ensure_project(body.project_id)
    if not body.approve_code:
        error('Explicit code review and approval is required')
    if _SCRIPT_MANAGER and _SCRIPT_MANAGER.busy:
        error('Stop the current script before approving generated code', 409)
    path = DRAFTS / (body.draft_id + '.json')
    if not path.is_file():
        error('Draft not found. Regenerate the test design.', 404)
    draft = load_json(path)
    available = catalog(draft['project_id'])
    current_hash = digest(available)
    if draft['project_id'] != body.project_id or draft['catalog_hash'] != current_hash or current_hash != body.reviewed_catalog_hash:
        error('Locators changed since design. Refresh and review before approval.', 409)
    steps, blocked = review_steps(body.steps, available, draft['category'])
    if blocked or not steps:
        error('Unsupported step(s): ' + '; '.join(blocked or ['empty steps']))
    if not any(x['action'].startswith('assert_') for x in steps):
        error('Add at least one reviewed independent assertion before generating code')
    if draft['category'] == 'Negative':
        # Checking that the quantity input is visible does NOT prove the ERP
        # rejected an invalid value. Demand a real validation assertion.
        by_id = {x['id']: x for x in available}
        validation = any(s['action'] == 'assert_text' or
                         (s['action'] == 'assert_visible' and
                          (by_id[s['target_id']]['field_type'].lower() in ('alert', 'error', 'validation') or
                           re.search(r'error|validation|invalid|required', s['label'], re.I))) for s in steps)
        if not validation:
            error('Negative scenarios require an explicit error/validation assertion. '
                  'First record the validation message locator; a visible input alone is not a valid negative Pass.')
    source = generate_python(draft, available, steps)
    compile(source, '<ai-reviewed-test>', 'exec')
    target = GENERATED / ('ai_' + draft['id'] + '.py')
    if target.exists():
        error('This approved script already exists; edit it in VS Code rather than generating again', 409)
    GENERATED.mkdir(parents=True, exist_ok=True)
    # New fixed-template source only, never raw model code.
    target.write_text(source, encoding='utf-8')
    approved = {**draft, 'steps': steps, 'approved_at': datetime.now(timezone.utc).isoformat(),
                'script_id': 'ai_generated/' + target.name, 'sha256': hashlib.sha256(source.encode('utf-8')).hexdigest()}
    save_json(DRAFTS / (draft['id'] + '.approved.json'), approved)
    return {'approved': True, 'script_id': approved['script_id'], 'sha256': approved['sha256'],
            'source': source, 'note': 'Generated script is saved and reviewable. Run in Existing Session mode after manual login to the matching TEST/STAGING ERP.'}


def _live_controls(project_id):
    ensure_project(project_id)
    if _CONTROLLER is None:
        error('Browser controller unavailable', 503)
    if _SCRIPT_MANAGER and _SCRIPT_MANAGER.busy:
        error('Stop active automation before a live DOM scan', 409)
    session = _CONTROLLER.call('status')
    if not session.get('open') or session.get('project_id') != project_id:
        error('Open this registered TEST/STAGING ERP in Browser Session and log in manually first')
    if session.get('recording'):
        error('Stop the recorder before capturing a baseline')
    try:
        scan = _CONTROLLER.call('inspect_dom')
    except Exception:
        error('Live DOM inspection failed. Verify the ERP page is open and authenticated.')
    path = clean(scan.get('page_url') or '', 250)
    if not path.startswith(('https://', 'http://')):
        error('Cannot identify the ERP screen')
    # Never persist text, attributes or input values. A metadata-only comparison.
    controls = []
    occurrences = {}
    for c in scan.get('controls', [])[:100]:
        if not isinstance(c, dict):
            continue
        label = clean(c.get('label'), 80)
        if SENSITIVE.search(label):
            continue
        kind = clean((c.get('locator') or {}).get('kind'), 20)
        role = clean(c.get('role'), 40)
        tag = clean(c.get('tag'), 30)
        name = clean(c.get('name'), 80)
        # Stable labels and roles: no raw selector values in baseline or response.
        base_key = '|'.join((tag, role, label.casefold(), name.casefold()))
        occurrences[base_key] = occurrences.get(base_key, 0) + 1
        key = base_key + '#' + str(occurrences[base_key])
        if base_key.strip('|'):
            controls.append({'key': key, 'label': label, 'tag': tag, 'role': role,
                             'locator_kind': kind, 'unique': bool(c.get('unique'))})
    controls.sort(key=lambda c: c['key'])
    return {'project_id': project_id, 'page_url': path, 'captured_at': datetime.now(timezone.utc).isoformat(),
            'controls': controls, 'signature': digest(controls), 'scanned': len(controls)}


def baseline_file(project_id, page_url):
    return BASELINES / project_id / (hashlib.sha256(page_url.encode('utf-8')).hexdigest()[:20] + '.json')


def impacts(project_id, labels):
    words = {s.lower() for s in labels if s and len(s) > 2}
    result=[]
    folder = BASE / 'workflows' / project_id
    if folder.is_dir():
        for path in sorted(folder.glob('*.json'))[:150]:
            if not re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', path.name):
                continue
            try:
                wf=load_json(path)
            except (OSError, ValueError):
                continue
            hit=[]
            for step in (wf.get('steps') or [])[:1500]:
                label=clean(step.get('target_text') or '', 100).lower()
                if label in words or any(w == label or (len(w) > 5 and w in label) for w in words):
                    hit.append(label)
            if hit:
                result.append({'workflow': path.name, 'matched_labels': list(dict.fromkeys(hit))[:7],
                               'recommendation': 'Review recorded locator and rerun regression; not automatically repaired'})
    return result[:75]


@router.post('/baseline')
def baseline(body: LiveIn):
    scan = _live_controls(body.project_id)
    path = baseline_file(body.project_id, scan['page_url'])
    with _LOCK:
        save_json(path, scan)
    return {'created': True, 'page_url': scan['page_url'], 'controls': scan['scanned'],
            'signature': scan['signature'][:16], 'note': 'Read-only baseline saved for this exact ERP screen.'}


@router.post('/compare')
def compare(body: LiveIn):
    current = _live_controls(body.project_id)
    path = baseline_file(body.project_id, current['page_url'])
    if not path.is_file():
        error('No baseline saved for this ERP screen. Open the correct screen and capture its baseline first.', 404)
    old = load_json(path)
    before = {c['key']: c for c in old['controls']}
    after = {c['key']: c for c in current['controls']}
    added = [after[k] for k in sorted(after.keys() - before.keys())]
    removed = [before[k] for k in sorted(before.keys() - after.keys())]
    changed = [{'before': before[k], 'after': after[k]} for k in sorted(before.keys() & after.keys())
               if (before[k]['locator_kind'],before[k]['unique']) != (after[k]['locator_kind'],after[k]['unique'])]
    impacted = impacts(body.project_id, [x['label'] for x in added + removed] +
                     [x['before']['label'] for x in changed])
    return {'page_url': current['page_url'], 'baseline_date': old['captured_at'],
            'compared_at': current['captured_at'], 'same': not (added or removed or changed),
            'added': added[:80], 'removed': removed[:80], 'changed': changed[:80],
            'affected_workflows': impacted, 'advisory':
            'DOM drift is an advisory, not proof the ERP is defective. Review auth state, dynamic controls and impacted tests.'}
