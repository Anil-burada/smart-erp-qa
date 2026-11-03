"""Conservative, observable Leocem navigation for local TEST/STAGING Playwright runs.

Avoid exact placeholder assumptions, retry keyboard shortcut and uniquely labeled
search controls. Never guess an ERP route or click an ambiguous menu result.
"""
from __future__ import annotations

import re
import time
from playwright.sync_api import TimeoutError as PlaywrightTimeout


SEARCH_INPUTS = (
    'input[placeholder*="Where Do You Want To Go" i]:visible',
    'input[placeholder*="Where Do You Want" i]:visible',
    'input[placeholder*="Where to go" i]:visible',
    'input[aria-label*="global search" i]:visible',
)
SEARCH_TRIGGERS = (
    'button[aria-label="Global Search" i]:visible',
    '[role="button"][aria-label="Global Search" i]:visible',
    'button[title="Global Search" i]:visible',
    '[role="button"][title="Global Search" i]:visible',
    'button[aria-label="Search" i]:visible',
    'button[title="Search" i]:visible',
    'button:has(svg[data-testid="SearchIcon"]):visible',
    'button:has(svg[data-testid="SearchOutlinedIcon"]):visible',
    'button:has(svg[data-testid="ManageSearchIcon"]):visible',
)


def _search_field(page):
    """Return only a unique visible input; never use .first on ambiguous fields."""
    for selector in SEARCH_INPUTS:
        matching = page.locator(selector)
        if matching.count() == 1:
            return matching
    # Some app updates expose a role=searchbox without the old placeholder.
    boxes = page.get_by_role('searchbox').and_(page.locator(':visible'))
    if boxes.count() == 1:
        return boxes
    return None


def _diagnostics(page):
    """Keep concise visible UI details in exception/report, no form values/passwords."""
    try:
        data = page.evaluate('''() => {
          const visible = e => {const r=e.getBoundingClientRect(),s=getComputedStyle(e);
            return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
          return {
            placeholders:[...document.querySelectorAll('input')].filter(visible)
              .map(x=>x.getAttribute('placeholder')||x.getAttribute('aria-label')||'')
              .filter(Boolean).slice(0,12),
            controls:[...document.querySelectorAll('button,[role="button"]')].filter(visible)
              .map(x=>x.getAttribute('aria-label')||x.getAttribute('title')||x.innerText||'')
              .map(x=>x.trim()).filter(Boolean).slice(0,20),
            sidebar:!!document.querySelector('div.pro-sidebar'),
            frames:document.querySelectorAll('iframe').length
          };
        }''')
        return f"url={page.url!r}; visible placeholders={data.get('placeholders')!r}; controls={data.get('controls')!r}; sidebar={data.get('sidebar')!r}; iframes={data.get('frames')!r}"
    except Exception as exc:
        return f"url={page.url!r}; unable to capture visible-control diagnostics: {type(exc).__name__}"


def open_search(page):
    """Open global search using observed UI controls, not guessed URL navigation."""
    # Login confirmation is not proof app is fully ready. Wait briefly for the
    # dashboard to settle, but never reload the authenticated page.
    try:
        page.locator('div.pro-sidebar').first.wait_for(state='visible', timeout=12000)
    except PlaywrightTimeout:
        raise RuntimeError('Global Search blocked: app sidebar did not become visible after login. ' + _diagnostics(page))

    field = _search_field(page)
    if field is not None:
        return field
    print('NAVIGATION: Global Search input hidden; opening via keyboard shortcut', flush=True)
    # UI shortcut must be sent after login and on the app page, not inside a
    # username/password input. Two attempts only; avoid excessive waiting.
    for attempt in range(2):
        try:
            page.bring_to_front()
            page.keyboard.press('Control+Space')
        except Exception as exc:
            print('NAVIGATION: shortcut attempt failed:', type(exc).__name__, flush=True)
        deadline = time.monotonic() + (3.0 if attempt == 0 else 2.0)
        while time.monotonic() < deadline:
            field = _search_field(page)
            if field is not None:
                print('NAVIGATION: Global Search opened by Control+Space', flush=True)
                return field
            page.wait_for_timeout(200)

    # Fall back only to uniquely identified app search controls.
    for selector in SEARCH_TRIGGERS:
        candidates = page.locator(selector)
        if candidates.count() != 1:
            continue
        try:
            print(f'NAVIGATION: clicking unique app search control {selector}', flush=True)
            candidates.click(timeout=2500)
            deadline = time.monotonic() + 3.5
            while time.monotonic() < deadline:
                field = _search_field(page)
                if field is not None:
                    print('NAVIGATION: Global Search opened using app control', flush=True)
                    return field
                page.wait_for_timeout(200)
        except Exception as exc:
            print('NAVIGATION: search control did not open search:', type(exc).__name__, flush=True)

    raise RuntimeError(
        'Global Search could not be opened after successful login. Expected a visible '
        'search input or an unambiguous Global Search button. Actual: ' + _diagnostics(page) +
        '. Review screenshot/trace and update the search-trigger locator for this ERP build.'
    )


def _click_result(page, expected):
    """Click exactly one leaf result matching the full label, ignoring whitespace."""
    wanted = re.sub(r'[^a-z0-9]', '', expected.casefold())
    return page.evaluate('''target => {
      const norm=v=>(v||'').toLowerCase().replace(/[^a-z0-9]/g,'');
      const visible=e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);
        return r.width>0&&r.height>0&&s.visibility!=='hidden'&&s.display!=='none'};
      const matches=[...document.querySelectorAll('[role="option"],[role="menuitem"],li,a,button')]
        .filter(visible).filter(e=>norm(e.innerText)===target);
      const leaves=matches.filter(e=>!matches.some(o=>o!==e&&e.contains(o)));
      if(leaves.length===1){leaves[0].click();return {clicked:true,count:1}}
      return {clicked:false,count:leaves.length};
    }''', wanted)


def global_search(page, query, expected):
    """Open Global Search and select only a unique exact target action."""
    print('\n' + '=' * 54 + '\nGLOBAL SEARCH: ' + str(query) + '\n' + '=' * 54, flush=True)
    search = open_search(page)
    inputs = list(dict.fromkeys((query, re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', query), expected)))
    for phrase in inputs:
        print(f'NAVIGATION: searching for {phrase!r}', flush=True)
        try:
            search.fill(phrase, timeout=4500)
        except Exception as exc:
            raise RuntimeError('Global Search input was found but could not be filled: ' + _diagnostics(page)) from exc
        deadline = time.monotonic() + 9
        while time.monotonic() < deadline:
            try:
                outcome = _click_result(page, expected)
                if outcome.get('clicked'):
                    print(f'NAVIGATION: opened exact target {expected!r}', flush=True)
                    return
                # Some results are ordinary spans outside a menu container.
                pattern = re.compile(r'^\s*' + r'\s*'.join(map(re.escape, expected.split())) + r'\s*$', re.I)
                matches = page.get_by_text(pattern).and_(page.locator(':visible'))
                if matches.count() == 1:
                    matches.click(timeout=1200)
                    print(f'NAVIGATION: opened exact text result {expected!r}', flush=True)
                    return
            except PlaywrightTimeout:
                pass
            page.wait_for_timeout(300)
    raise RuntimeError(
        f'Global Search opened but no unique result for expected={expected!r} '
        f'(searched {inputs!r}). Actual: ' + _diagnostics(page)
    )
