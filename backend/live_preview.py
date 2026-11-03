"""Opt-in read-only, masked screenshot preview of a running local Playwright script.

All Playwright calls remain on the script's original sync thread.  No second
browser, CDP port, remote desktop, or client-side control channel is created.
"""
from __future__ import annotations

import os
import hmac
import time
from pathlib import Path

_live_page = None
_live_dir = None
_last = 0.0
_inside = False
_original_sync = None


def enable(page):
    """Register the script-owned page and capture at most ~1 frame/1.5 seconds."""
    global _live_page, _live_dir, _last, _original_sync
    raw = os.environ.get('SMART_ERP_RUN_DIR')
    if not raw or page is None or os.environ.get('SMART_ERP_LIVE_PREVIEW', '1') != '1':
        return
    run_dir = Path(raw).resolve()
    if not (run_dir / 'run.json').is_file():
        return
    _live_page, _live_dir, _last = page, run_dir, 0.0
    if _original_sync is not None:
        return
    # This is limited to the trusted script subprocess. The backend's own
    # Playwright controller does not get patched.
    from playwright._impl._sync_base import SyncBase
    original = SyncBase._sync
    _original_sync = original

    def sync_with_capture(self, coro):
        result = original(self, coro)
        _maybe_capture()
        return result

    SyncBase._sync = sync_with_capture


def _maybe_capture():
    global _last, _inside
    if _inside or _live_page is None or _live_dir is None:
        return
    now = time.monotonic()
    if now - _last < 1.5:
        return
    _last = now
    _inside = True
    try:
        page = _live_page
        if page.is_closed():
            return
        # Mask editable controls (including credentials, selected options and
        # user-entered ERP data) before the image leaves the script process.
        selectors = 'input, textarea, select, [contenteditable="true"], [data-sensitive]'
        image = page.screenshot(
            type='jpeg', quality=48, scale='css', animations='disabled',
            timeout=2000, mask=[page.locator(selectors)],
            mask_color='#132c50')
        if not isinstance(image, bytes) or not image.startswith(b'\xff\xd8'):
            return
        temp = _live_dir / 'live_preview.tmp'
        frame = _live_dir / 'live_preview.jpg'
        temp.write_bytes(image)
        os.replace(temp, frame)
    except Exception:
        # Preview is best-effort; it must not fail or alter ERP transactions.
        pass
    finally:
        _inside = False


def authorized(candidate):
    """Preview requires a separate access code even if dashboard is public."""
    path = Path.home() / '.smart-erp-gateway' / 'live_preview_key.txt'
    try:
        expected = path.read_text(encoding='utf-8').strip()
    except OSError:
        return False
    return bool(expected and isinstance(candidate, str) and hmac.compare_digest(expected, candidate))
