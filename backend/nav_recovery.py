"""Opt-in, cautious recovery of *navigation-only* click locators.

This is not general self-healing: no record-changing actions, no guessed text,
no non-interactive elements, and no stored selector mutation. A unique live
control must match the approved recording's exact label before any action.
"""
from __future__ import annotations

import re
from backend.locator import locate

DANGEROUS = re.compile(r'\b(save|submit|create|approve|post|delete|remove|confirm|release|receive|issue|cancel|reject|pay|send|update|accept|sign\s*out|logout)\b', re.I)

# Exclude generic text containers: Click a deliberate interactive element only.
INTERACTIVES = 'button,a[href],[role="button"],[role="link"],[role="tab"],[role="menuitem"],[tabindex]'

# Counts only uniquely visible interactive controls whose label is an exact
# normalized match. No page text, credential, token, or input value is returned.
EXACT_CONTROLS_JS = r'''({label, onlyThis}) => {
    const norm = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const visible = el => {
      const box = el.getBoundingClientRect();
      const style = getComputedStyle(el);
      return box.width > 0 && box.height > 0 && style.visibility !== 'hidden' && style.display !== 'none';
    };
    const text = el => norm(el.getAttribute('aria-label') || el.innerText || el.textContent || el.getAttribute('title'));
    const nodes = Array.from(document.querySelectorAll('button,a[href],[role="button"],[role="link"],[role="tab"],[role="menuitem"],[tabindex]'));
    const matches = nodes.filter(el => visible(el) && text(el) === norm(label));
    return {matches: matches.length};
}'''

# Evaluate a Playwright Locator's actual element; cannot be replaced by a
# similarly named text node elsewhere in the page.
LOCATOR_MATCH_JS = r'''(el, expected) => {
    const norm = value => String(value || '').replace(/\s+/g, ' ').trim().toLowerCase();
    const clickable = el.closest('button,a[href],[role="button"],[role="link"],[role="tab"],[role="menuitem"],[tabindex]');
    if (!clickable) return false;
    const box = clickable.getBoundingClientRect();
    const style = getComputedStyle(clickable);
    if (!(box.width > 0 && box.height > 0 && style.display !== 'none' && style.visibility !== 'hidden')) return false;
    const text = clickable.getAttribute('aria-label') || clickable.innerText || clickable.textContent || clickable.getAttribute('title');
    return norm(text) === norm(expected);
}'''


def navigation_label(step: dict) -> str | None:
    if step.get('action') != 'click':
        return None
    spec = step.get('locator') or {}
    # Never use a CSS selector string as an inferred business-action label.
    label = str(step.get('target_text') or spec.get('name') or '').strip()
    if not label or len(label) > 100 or DANGEROUS.search(label):
        return None
    # Require a real recorded label, not only a CSS or test-id key.
    if spec.get('kind') not in ('role', 'text', 'css', 'test_id', 'label'):
        return None
    if spec.get('kind') == 'role' and spec.get('role') not in ('button','link','tab','menuitem'):
        return None
    return label


def navigation_diagnostic(page, step: dict) -> dict:
    """Read-only count, no secret, arbitrary HTML or input value inspection."""
    label = navigation_label(step)
    if label is None:
        return {'eligible': False, 'reason': 'not a verified non-destructive navigation click'}
    try:
        checked = page.evaluate(EXACT_CONTROLS_JS, {'label': label, 'onlyThis': True})
        return {'eligible': True, 'label': label, 'unique_visible_controls': checked['matches']}
    except Exception:
        return {'eligible': True, 'label': label, 'unique_visible_controls': None}


def navigation_recovery(page, step: dict):
    """Return (locator, recovery_type) for unique, exact visible navigation control.

    Caller must explicitly opt in for this run and must ONLY invoke this before
    a navigation click has been attempted. Never retries after a click timeout.
    """
    label = navigation_label(step)
    if label is None:
        return None
    diag = navigation_diagnostic(page, step)
    if diag['unique_visible_controls'] != 1:
        return None

    original = step['locator']
    seen = set()
    for candidate in step.get('observed_candidates') or []:
        if not isinstance(candidate, dict) or not isinstance(candidate.get('spec'), dict):
            continue
        spec = candidate['spec']
        if candidate.get('observed_count') != 1 or spec == original:
            continue
        if spec.get('kind') not in ('role','text','css','test_id'):
            continue
        key = repr(sorted(spec.items()))
        if key in seen:
            continue
        seen.add(key)
        try:
            loc = locate(page, spec)
            if loc.count() == 1 and loc.is_visible() and loc.evaluate(LOCATOR_MATCH_JS, label):
                return loc, 'approved-recording-alternative'
        except Exception:
            pass

    # Exact visible text, still restricted to an interactive ancestor and
    # just one such control on the current page. No fuzzy/substring matching.
    try:
        loc = page.get_by_text(label, exact=True)
        if loc.count() == 1 and loc.is_visible() and loc.evaluate(LOCATOR_MATCH_JS, label):
            return loc, 'unique-exact-navigation-text'
    except Exception:
        pass
    return None
