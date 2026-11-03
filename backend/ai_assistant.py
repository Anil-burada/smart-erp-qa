"""Explicitly opt-in *local* Ollama failure hints, never autonomous actions.

Only send a categorical failure description, step number and action type.
Never send ERP HTML, screenshots, URLs, raw exceptions, recorded values,
credentials, cookies, locator strings or business records to the model.
"""
from __future__ import annotations

import json
import os
from urllib.error import URLError
from urllib.request import Request, urlopen


VALID_ACTIONS = {'click', 'fill', 'select_option', 'press', 'check', 'uncheck', 'unknown'}


def reason_category(message: str) -> str:
    s = message.casefold()
    if 'locator matched 0' in s or 'matches 0' in s:
        return 'locator_not_found'
    if 'locator matched' in s or 'strict mode violation' in s:
        return 'ambiguous_locator'
    if 'timeout' in s or 'timed out' in s:
        return 'timeout'
    if 'not visible' in s or 'not enabled' in s:
        return 'element_not_interactable'
    if 'navigation' in s or 'net::err' in s:
        return 'navigation_failure'
    return 'other_failure'


def safe_summary(*, message: str, step_number: int | None, action: str | None) -> dict:
    """Reduces an error to non-identifying metadata, including no raw strings."""
    return {
        'reason': reason_category(message),
        'step_number': max(0, min(int(step_number or 0), 9999)),
        'action': action if action in VALID_ACTIONS else 'unknown',
    }


def diagnose_local(summary: dict, model: str | None = None) -> str:
    model = model or os.environ.get('ERPQA_OLLAMA_MODEL', 'llama3.2')
    if not isinstance(model, str) or not (1 <= len(model) <= 90):
        raise ValueError('Invalid Ollama model name')
    # All fields here come from a fixed allowlist and are safe to disclose.
    safe = {
        'reason': summary.get('reason') if summary.get('reason') in {
            'locator_not_found', 'ambiguous_locator', 'timeout',
            'element_not_interactable', 'navigation_failure', 'other_failure'
        } else 'other_failure',
        'step_number': max(0, min(int(summary.get('step_number', 0)), 9999)),
        'action': summary.get('action') if summary.get('action') in VALID_ACTIONS else 'unknown',
    }
    prompt = (
        'You are a Playwright QA helper. A TEST workflow failed. '
        'Given only the generic failure category, step index, and action type, '
        'suggest up to 4 safe checks to diagnose this failure. '
        'Never invent locators, assume a transaction succeeded, or suggest '
        'automatically re-submitting/approving any ERP record. '
        'Explain that the diagnosis is a suggestion, not a verified cause.\n'
        + json.dumps(safe, sort_keys=True)
    )
    body = json.dumps({
        'model': model, 'prompt': prompt, 'stream': False,
        'options': {'temperature': 0.2, 'num_predict': 250},
    }).encode('utf-8')
    request = Request(
        'http://127.0.0.1:11434/api/generate',
        data=body,
        headers={'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=45) as response:
            result = json.load(response)
    except (OSError, URLError, TimeoutError, ValueError) as err:
        raise RuntimeError(
            'Local Ollama is not available. Install Ollama and pull the configured model, '
            'or use the framework without AI.'
        ) from err
    answer = result.get('response', '')
    if not isinstance(answer, str) or not answer.strip():
        raise RuntimeError('Ollama did not return a diagnostic suggestion')
    return answer[:4000]


def rank_locator_candidates_local(candidates: list[dict], action: str) -> dict:
    """Optional Ollama suggestion based on non-sensitive locator kinds only.

    Send neither raw selector strings nor DOM text to AI. Result is advice, not
    locator repair; a human must review and verify the intended target.
    """
    if not candidates:
        raise ValueError('No uniquely visible locator candidates. Inspect/re-record the element.')
    allowed={'test_id','css','label','role','placeholder','text'}
    safe=[]
    for i,c in enumerate(candidates[:8]):
        kind=c.get('locator',{}).get('kind')
        if kind not in allowed or not c.get('usable_candidate'):
            continue
        safe.append({'index':i,'kind':kind})
    if not safe:
        raise ValueError('No tested, uniquely visible candidates')
    model=os.environ.get('ERPQA_OLLAMA_MODEL','llama3.2')
    prompt=('You review generic Playwright locator TYPES only, not any ERP page or sensitive text. '
            'Return JSON {"index": NUMBER} selecting a good stable locator kind from the given '
            'already-unique candidates. This is only a suggestion, never permission to click. '
            'Prefer test ID or user-facing accessible identifiers over brittle CSS. '
            'Use only one of the provided indices.\n'+json.dumps({'action':action if action in VALID_ACTIONS else 'unknown','candidates':safe}))
    data=json.dumps({'model':model,'prompt':prompt,'stream':False,
                     'format':'json','options':{'temperature':0,'num_predict':75}}).encode()
    req=Request('http://127.0.0.1:11434/api/generate',data=data,
                headers={'Content-Type':'application/json'},method='POST')
    try:
        with urlopen(req,timeout=30) as response:
            output=json.load(response)
        result=json.loads(output.get('response','{}'))
        index=result.get('index')
        if type(index) is not int or index not in {c['index'] for c in safe}:
            raise ValueError('Model returned an unverified candidate index')
    except Exception as err:
        raise RuntimeError('Local Ollama locator suggestion is unavailable or invalid; use the tested candidates manually.') from err
    return {'candidate_index':index,'candidate_kind':candidates[index]['locator']['kind'],
            'auto_apply':False,'verification':'Human semantic review required; Playwright only confirmed uniqueness and visibility'}
