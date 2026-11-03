"""Safe login locator candidate discovery. Never reads field values or cookies.

Suggestions are NOT a verified login configuration. A human must verify the
success selector before automatic login can be enabled.
"""
from __future__ import annotations

from pathlib import Path
import json

from backend.registry import BASE
from backend.json_workflow import atomic_json

PROBE_JS = r'''() => {
  const visible = el => !!el && !!el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden';
  const css = el => {
    if (!el) return null;
    if (el.id && document.querySelectorAll('#' + CSS.escape(el.id)).length === 1)
      return {kind:'css',value:'#' + CSS.escape(el.id)};
    if (el.name) {
      const value = el.name.replace(/\\/g,'\\\\').replace(/"/g,'\\"');
      const sel = el.tagName.toLowerCase() + '[name="' + value + '"]';
      if (document.querySelectorAll(sel).length === 1) return {kind:'css',value:sel};
    }
    if (el.tagName === 'A' || el.tagName === 'BUTTON') {
      const name = (el.getAttribute('aria-label') || el.textContent || '').trim().replace(/\s+/g, ' ');
      if (name && name.length <= 120) {
        const role = el.tagName === 'A' ? 'link' : 'button';
        const matching = [...document.querySelectorAll(el.tagName.toLowerCase())].filter(
          other => (other.getAttribute('aria-label') || other.textContent || '').trim().replace(/\s+/g,' ') === name
        );
        if (matching.length === 1) return {kind:'role',role,name};
      }
    }
    return null;
  };
  const pass = [...document.querySelectorAll('input[type="password"]')].filter(visible);
  if (pass.length !== 1) return {detected:false,reason:'Expected exactly one visible password field'};
  const pwd = pass[0];
  const form = pwd.closest('form') || document;
  const users = [...form.querySelectorAll('input')].filter(el => visible(el) &&
    !['hidden','password','checkbox','radio','submit','button','file'].includes(el.type));
  const preferred = users.filter(el => /user|email|login|identifier/i.test(
    [el.id,el.name,el.placeholder,el.autocomplete].join(' ')));
  const user = preferred.length === 1 ? preferred[0] : users.length === 1 ? users[0] : null;
  const buttons = [...form.querySelectorAll('button,input[type="submit"],a')].filter(visible);
  const preferredButtons = buttons.filter(el => /log.?in|sign.?in/i.test(
    (el.textContent||el.value||el.getAttribute('aria-label')||'').trim()));
  const submit = preferredButtons.length === 1 ? preferredButtons[0] : buttons.length === 1 ? buttons[0] : null;
  const result = {detected:false,username:css(user),password:css(pwd),submit:css(submit)};
  result.detected = Boolean(result.username && result.password && result.submit);
  if (!result.detected) result.reason = 'Login controls ambiguous or lack unique stable IDs/names';
  return result;
}'''


def probe_login(page) -> dict:
    """Return only locator metadata; no username/password values can escape."""
    return page.evaluate(PROBE_JS)


def save_candidates(project_id: str, project_url: str, candidates: dict) -> Path | None:
    if not all(candidates.get(key) for key in ('username','password','submit')):
        return None
    path = BASE / 'projects' / project_id / 'login_candidates.json'
    safe = {key:candidates[key] for key in ('username','password','submit')}
    atomic_json(path, json.dumps({
        'project_id':project_id,
        'project_url':project_url,
        'note':'Locator suggestions only. Supply and verify a unique post-login success selector before login.json.',
        'candidates':safe
    }, indent=2))
    return path


# Post-login markers are suggested from the LIVE DOM only. We do not inspect
# storage, cookies, request bodies, form field values or visible account names.
# Candidates are never silently accepted without a unique post-login match.
POST_LOGIN_JS = r'''() => {
  const visible = el => Boolean(el && el.getClientRects().length &&
    getComputedStyle(el).display !== 'none' && getComputedStyle(el).visibility !== 'hidden');
  const safeId = value => /^[a-zA-Z][a-zA-Z0-9_:-]{1,80}$/.test(value || '');
  const unique = selector => { try { return document.querySelectorAll(selector).length === 1; } catch (_) { return false; } };
  const clean = value => String(value || '').trim().replace(/\s+/g, ' ').slice(0, 70);
  const choices = [];
  const used = new Set();
  const add = (loc, label, reason, score) => {
    const key = JSON.stringify(loc);
    if (used.has(key)) return;
    used.add(key);
    choices.push({locator:loc,label:label.slice(0,90),reason,score});
  };
  const elements = document.querySelectorAll('main,nav,aside,section,header,[role="main"],[role="navigation"],[role="menu"],[role="menuitem"],a,button,h1,h2,[data-testid]');
  for (const el of elements) {
    if (!visible(el)) continue;
    if (el.matches('input,textarea,[contenteditable],select')) continue;
    const tag = el.tagName.toLowerCase();
    const id = clean(el.id);
    const tid = clean(el.getAttribute('data-testid'));
    const aria = clean(el.getAttribute('aria-label'));
    const txt = (tag==='a' || tag==='button' || /^h[12]$/.test(tag) || el.getAttribute('role')==='menuitem') ? clean(el.textContent) : '';
    const name = aria || txt;
    const semantic = /dashboard|navigation|sidebar|main[-_]?content|workspace|logout|log.?out|sign.?out|procurement|home|menu/i;
    const safeAction = /^(dashboard|home|procurement|menu|sign\s?out|log\s?out|logout|purchase indent|purchase requisition)$/i;
    let loc = null, score = 0, reason = '';
    if (safeId(id) && semantic.test(id)) {
      const selector = '#' + CSS.escape(id);
      if (unique(selector)) { loc = {kind:'css',value:selector}; score = /dashboard|logout|sign.?out/i.test(id)?100:85; reason='Unique visible page ID'; }
    }
    if (!loc && safeId(tid) && semantic.test(tid)) {
      const selector = '[data-testid="' + tid + '"]';
      if (unique(selector)) {loc={kind:'test_id',value:tid};score=90;reason='Unique visible test ID';}
    }
    if (!loc && (tag==='nav' || tag==='main') && document.querySelectorAll(tag).length === 1) {
      loc={kind:'css',value:tag};score=72;reason='Unique visible main/navigation region';
    }
    if (!loc && (tag==='a' || tag==='button' || el.getAttribute('role')==='menuitem') && safeAction.test(name)) {
      const role = el.getAttribute('role') || (tag==='a' ? 'link' : 'button');
      // Playwright will recheck uniqueness and visibility before saving.
      loc={kind:'role',role,name};score=/sign.?out|log.?out/i.test(name)?95:75;
      reason='Visible navigation control with a safe exact label';
    }
    if (!loc && /^h[12]$/.test(tag) && /^(dashboard|home|procurement)$/i.test(name)) {
      loc={kind:'role',role:'heading',name};score=65;reason='Visible page heading';
    }
    if (loc) add(loc, id||tid||name||tag,reason,score);
  }
  choices.sort((a,b)=>b.score-a.score || a.label.localeCompare(b.label));
  return {login_form_visible:[...document.querySelectorAll('input[type="password"]')].some(visible),
          candidates:choices.slice(0,25)};
}'''


def probe_post_login(page) -> dict:
    """Read safe visible marker selectors only; never read user/field values."""
    return page.evaluate(POST_LOGIN_JS)
