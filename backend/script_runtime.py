"""Explicit result events for trusted, locally maintained automation scripts.

Printed PASS/FAIL messages are never scraped into test counts. This API records
checks the script actually performs. Missing business assertions stay REVIEW.
"""
from __future__ import annotations
import functools
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4


def run_directory() -> Path | None:
    raw = os.environ.get('SMART_ERP_RUN_DIR')
    return Path(raw) if raw else None


def redact(value) -> str:
    text = str(value)
    # Avoid leaking locally configured secrets in an exception or console line.
    for key, secret in os.environ.items():
        if len(secret) >= 4 and any(x in key.upper() for x in ('PASSWORD', 'SECRET', 'API_KEY', 'TOKEN')):
            text = text.replace(secret, '[REDACTED]')
    return text


def emit(kind: str, **payload):
    directory = run_directory()
    if not directory:
        return
    directory.mkdir(parents=True, exist_ok=True)
    event = {'kind': kind, 'at': datetime.now(timezone.utc).isoformat(), **payload}
    with (directory / 'events.jsonl').open('a', encoding='utf-8') as out:
        out.write(redact(json.dumps(event, default=str)) + '\n')


def capture_failure(page, label: str, expected=None, actual=None) -> str | None:
    """Capture the real ERP page with a temporary red mismatch annotation.

    A field gets a red outline only when the actual value identifies exactly
    one visible DOM candidate. Otherwise the screenshot carries a clear red
    error panel, never a guessed rectangle over an unrelated field.
    """
    directory = run_directory()
    if directory is None or page is None:
        return None
    name = re.sub(r'[^A-Za-z0-9_-]', '_', label)[:70] + '_' + uuid4().hex[:8] + '.png'
    path = directory / 'evidence' / name
    path.parent.mkdir(parents=True, exist_ok=True)
    markup = r"""args => {
        const existing = document.getElementById('smart-erp-qa-capture-banner');
        if (existing) existing.remove();
        const text = String(args.actual ?? '').trim();
        const visible = e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);
            return r.width > 0 && r.height > 0 && s.visibility !== 'hidden' && s.display !== 'none';};
        const nodes = [...document.querySelectorAll('input:not([type=password]),textarea,[role=cell],td,span')]
            .filter(e => visible(e) && (e.value ?? e.textContent ?? '').trim() === text);
        if (text.length > 0 && nodes.length === 1) {
            const el=nodes[0];el.dataset.smartErpQaOldOutline=el.style.outline||'';
            el.style.setProperty('outline','4px solid #dc173b','important');
            el.style.setProperty('outline-offset','2px','important');
            el.dataset.smartErpQaCaptured='1';
        }
        const box=document.createElement('aside');box.id='smart-erp-qa-capture-banner';
        box.style.cssText='position:fixed;top:12px;left:12px;max-width:87vw;z-index:2147483647;background:#fff3f3;border:4px solid #ce1231;color:#701121;border-radius:5px;padding:14px;box-shadow:0 4px 20px #0005;font:bold 14px Arial,sans-serif;white-space:pre-wrap';
        box.textContent=['ERP VALIDATION FAILED',String(args.label||''),
            'Expected: '+String(args.expected??'not provided'),
            'Actual: '+String(args.actual??'not provided')].join(String.fromCharCode(10));
        document.body.appendChild(box);
    }"""
    cleanup = r"""() => {
        document.getElementById('smart-erp-qa-capture-banner')?.remove();
        document.querySelectorAll('[data-smart-erp-qa-captured]').forEach(e => {
            e.style.outline=e.dataset.smartErpQaOldOutline||'';
            e.style.removeProperty('outline-offset');
            delete e.dataset.smartErpQaOldOutline;
            delete e.dataset.smartErpQaCaptured;
        });
    }"""
    try:
        try:
            page.evaluate(markup, {'label': label, 'expected': expected, 'actual': actual})
        except Exception as exc:
            emit('evidence_warning', message='Could not add red browser annotation: ' + str(exc)[:300])
        page.screenshot(path=str(path), full_page=True, timeout=10000)
        return 'evidence/' + name
    except Exception as exc:
        emit('evidence_error', message=str(exc)[:500])
        return None
    finally:
        try:
            page.evaluate(cleanup)
        except Exception:
            pass


def check(name, passed, expected, actual, *, page=None, process='Calculation validation', category='Positive'):
    evidence = None if passed else capture_failure(page, name, expected, actual)
    emit('check', name=name, status='PASSED' if passed else 'FAILED',
         expected=str(expected), actual=str(actual), process=process,
         category=category, evidence=evidence)


def stage(name: str, expected: str, verified: bool = True):
    """Wrap a named workflow stage without treating a click as business success."""
    def decorate(fn):
        @functools.wraps(fn)
        def wrapped(*args, **kwargs):
            ident = uuid4().hex
            emit('stage_start', id=ident, name=name, expected=expected, process=name)
            started = time.monotonic()
            page = args[0] if args else kwargs.get('page')
            try:
                result = fn(*args, **kwargs)
                if isinstance(result, dict) and result.get('status') == 'LPO_VALIDATION_FAILED_NOT_SAVED':
                    raise AssertionError('LPO validation failed. Save was not performed; dependent stages are blocked.')
                unverified = (not verified or
                              isinstance(result, str) and 'NOT_INDEPENDENTLY_VERIFIED' in result)
                emit('stage_end', id=ident, name=name, expected=expected, process=name,
                     status='REVIEW' if unverified else 'PASSED',
                     actual=('Action completed, but persisted status is not independently asserted.'
                             if unverified else 'The explicitly coded stage checks completed.'),
                     duration=round(time.monotonic() - started, 3))
                return result
            except BaseException as exc:
                emit('stage_end', id=ident, name=name, expected=expected, process=name,
                     status='FAILED', actual=str(exc)[:2000],
                     evidence=capture_failure(page, name, expected, str(exc)),
                     duration=round(time.monotonic() - started, 3))
                raise
        return wrapped
    return decorate


def open_script_browser(playwright, erp_url: str, timeout: int):
    """Reuse the exact managed page, or explicitly launch a separate script browser."""
    from urllib.parse import urlsplit
    endpoint = os.environ.get('SMART_ERP_CDP_URL')
    if endpoint:
        browser = playwright.chromium.connect_over_cdp(endpoint, timeout=15000)
        expected = urlsplit(erp_url)
        origin = (expected.scheme, expected.netloc)
        target = os.environ.get('SMART_ERP_TARGET_URL', '')
        pages = [(ctx, pg) for ctx in browser.contexts for pg in ctx.pages
                 if not pg.is_closed() and
                 (urlsplit(pg.url).scheme, urlsplit(pg.url).netloc) == origin and
                 (not target or pg.url == target)]
        if len(pages) != 1:
            raise RuntimeError('Expected one managed ERP tab. Do not navigate or open a duplicate ERP tab while starting.')
        context, page = pages[0]
        page.set_default_timeout(timeout)
        return browser, context, page, False
    options = {'headless': os.environ.get('ERPQA_HEADLESS') == '1', 'slow_mo': 500}
    if os.environ.get('ERPQA_CHROMIUM_EXECUTABLE'):
        options['executable_path'] = os.environ['ERPQA_CHROMIUM_EXECUTABLE']
    if not options['headless']:
        options['args'] = ['--window-size=1360,850', '--window-position=30,30']
    browser = playwright.chromium.launch(**options)
    context = browser.new_context(no_viewport=True, accept_downloads=True)
    page = context.new_page()
    page.set_default_timeout(timeout)
    return browser, context, page, True
