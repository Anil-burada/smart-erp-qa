"""All Playwright sync calls run in one dedicated browser thread."""
import json
import sys
import os
import queue
import re
import threading
import time
from concurrent.futures import Future
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright
from backend.locator import locate, unique
from backend.pom import BasePage
from backend.login_discovery import probe_login, probe_post_login, save_candidates
from backend.record_js import RECORDER_JS
from backend.nav_recovery import navigation_label, navigation_diagnostic, navigation_recovery
from backend.registry import BASE

CRITICAL_RE = re.compile(r'\b(save|submit|create|approve|post|delete|remove|confirm|release|receive|issue)\b', re.I)


class BrowserController:
    def __init__(self):
        self.commands = queue.Queue()
        self.page = None
        self.browser = None
        self.context = None
        self.active_project = None
        self.embedded = False
        self.electron_attached = False
        self.script_cdp_port = None
        self.embedded_width = 1440
        self.embedded_height = 850
        self.recording = False
        self.paused = False
        self.auto_capture = False
        self.login_verified = False
        self.login_candidates = None
        self.login_setup = None  # Ephemeral two-step wizard state, no credential values.
        self.login_setup_choices = []
        self.steps = []
        self.warnings = []
        self.start_url = ''
        self.lock = threading.Lock()
        # Do NOT start Playwright at FastAPI import time. A quick `python -c
        # "import backend.api"` used to spawn a Node driver and then exit,
        # resulting in confusing EPIPE errors. Browser actions start it lazily.
        self.worker = None
        self.worker_ready = threading.Event()
        self.worker_start_lock = threading.Lock()
        self.worker_error = None

    def _ensure_worker(self):
        with self.worker_start_lock:
            if self.worker is None:
                self.worker = threading.Thread(target=self._loop, name='playwright-browser', daemon=True)
                self.worker.start()
        if not self.worker_ready.wait(timeout=25):
            raise RuntimeError('Playwright worker did not initialize within 25 seconds. Check Python/Playwright dependencies.')
        if self.worker_error is not None:
            raise RuntimeError(f'Playwright worker failed: {self.worker_error}') from self.worker_error
        if not self.worker or not self.worker.is_alive():
            raise RuntimeError('Playwright browser worker exited unexpectedly')

    def call(self, action, **kwargs):
        # The dashboard polls status continuously. An idle status query must
        # never spawn Node/Playwright or make FastAPI startup depend on CDP.
        if action == 'status' and self.worker is None:
            return self._do_status()
        self._ensure_worker()
        future = Future()
        self.commands.put((action, kwargs, future))
        # A running transaction can legitimately take longer than a normal
        # API request; do not start another transaction after a timeout.
        return future.result(timeout=None if action in ('run','run_plan','run_flow','negative_check') else 150)

    def shutdown(self):
        """Close the local browser driver gracefully on normal server shutdown."""
        if self.worker and self.worker.is_alive():
            future = Future()
            self.commands.put(('__shutdown__', {}, future))
            try:
                future.result(timeout=8)
                self.worker.join(timeout=4)
                if not self.worker.is_alive():
                    self.worker = None
                    self.worker_ready.clear()
                    self.worker_error = None
            except Exception:
                pass

    def _loop(self):
        try:
            with sync_playwright() as playwright:
                self.p = playwright
                self.worker_ready.set()
                while True:
                    try:
                        action, kwargs, future = self.commands.get(timeout=.15)
                    except queue.Empty:
                        if self.page and not self.page.is_closed():
                            try:
                                self.page.wait_for_timeout(100)
                            except Exception:
                                pass
                        continue
                    try:
                        if action == '__shutdown__':
                            self._do_close()
                            future.set_result(True)
                            return
                        result = getattr(self, '_do_' + action)(**kwargs)
                        future.set_result(result)
                    except Exception as exc:
                        future.set_exception(exc)
        except Exception as exc:
            self.worker_error = exc
            self.worker_ready.set()
            # Never leave queued requests hanging if Playwright initialization fails.
            while True:
                try:
                    _action, _kwargs, future = self.commands.get_nowait()
                    future.set_exception(RuntimeError(f'Playwright driver unavailable: {exc}'))
                except queue.Empty:
                    break

    def _on_event(self, source, data):
        if not self.recording or not self.active_project or source['page'] != self.page:
            return
        url = urlsplit(str(data.get('page_url', '')))
        root = urlsplit(self.active_project['url'])
        if (url.scheme, url.netloc) != (root.scheme, root.netloc):
            if 'Interaction outside registered ERP origin was excluded' not in self.warnings:
                self.warnings.append('Interaction outside registered ERP origin was excluded')
            return
        # Some ERP routers redirect from /company to /dashboard after login.
        # Follow only same-origin navigation; the reviewer still approves all steps.
        if not (url.path.rstrip('/') == root.path.rstrip('/')
                or url.path.startswith(root.path.rstrip('/') + '/')):
            if os.environ.get('ERPQA_ALLOW_SAME_ORIGIN_PATHS') != '1':
                note = 'Interaction outside registered ERP URL path was excluded. Check the project URL or opt in to same-origin capture.'
                if note not in self.warnings:
                    self.warnings.append(note)
                return
            note = 'ERP navigated outside its initial URL path on the same origin; review captured steps'
            if note not in self.warnings:
                self.warnings.append(note)
        if source['frame'] != self.page.main_frame:
            self.warnings.append('Iframe interaction requires manual configuration in this version')
            return
        if len(self.steps) >= 1500:
            if len(self.warnings) < 30:
                self.warnings.append('Maximum 1500 steps reached; stop recording')
            return
        data['page_url'] = f'{url.scheme}://{url.netloc}{url.path}'
        # First eligible interaction is the start of the demonstrated business process.
        # Login-field interactions are excluded by the DOM recorder.
        if not self.steps:
            self.start_url = data['page_url']
        if not isinstance(data.get('locator'), dict):
            self.warnings.append(f'Unsupported or non-unique interaction: {data.get("target_text", "unknown")[:80]}')
            return
        data['target_text'] = str(data.get('target_text', ''))[:120]
        if data.get('locator_quality') == 'fragile_dom_path':
            warning = 'A clicked control has only a structural CSS locator. It may match different buttons on replay; verify this step before approval.'
            if warning not in self.warnings:
                self.warnings.append(warning)
        data['value'] = data.get('value') if data.get('action') in ('fill','select_option','press') else None
        self.steps.append(data)

    def _on_new_page(self, page):
        if self.recording:
            self.warnings.append('A new tab/popup opened. Multi-tab recording needs manual review in this version')

    def _do_open(self, project, embedded=False):
        self._do_close()
        options = {'headless': bool(embedded) or os.environ.get('ERPQA_HEADLESS') == '1'}
        # Chromium headed window: about 85% of the local display, with a safe
        # fallback when display metrics are unavailable (headless/CI/Linux).
        screen_width, screen_height = 1500, 900
        if sys.platform == 'win32':
            try:
                import ctypes
                screen_width = ctypes.windll.user32.GetSystemMetrics(0)
                screen_height = ctypes.windll.user32.GetSystemMetrics(1)
            except (AttributeError, OSError, ValueError):
                pass
        window_width = self.embedded_width if embedded else max(800, int(screen_width * 0.85))
        window_height = self.embedded_height if embedded else max(600, int(screen_height * 0.85))
        if project['browser'] == 'chromium' and not options['headless']:
            options['args'] = [f'--window-size={window_width},{window_height}', '--window-position=40,40']
        if project['browser'] == 'chromium' and os.environ.get('ERPQA_CHROMIUM_EXECUTABLE'):
            options['executable_path'] = os.environ['ERPQA_CHROMIUM_EXECUTABLE']
        # A loopback-only debugging endpoint lets a trusted local script reuse
        # this exact authenticated page. Never publish this port on a network.
        if project['browser'] == 'chromium':
            import socket
            with socket.socket() as probe:
                probe.bind(('127.0.0.1', 0))
                self.script_cdp_port = probe.getsockname()[1]
            options.setdefault('args', []).extend([
                f'--remote-debugging-port={self.script_cdp_port}',
                '--remote-debugging-address=127.0.0.1'])
        self.browser = getattr(self.p, project['browser']).launch(**options)
        self.context = self.browser.new_context(
            accept_downloads=False,
            **({'no_viewport': True} if project['browser'] == 'chromium' and not options['headless']
               else {'viewport': {'width': window_width, 'height': window_height}})
        )
        self.context.expose_binding('erpRecorderEvent', self._on_event)
        self.context.add_init_script(RECORDER_JS)
        self.context.on('page', self._on_new_page)
        self.page = self.context.new_page()
        self.page.set_default_timeout(12000)
        self.active_project = project
        self.embedded = bool(embedded)
        # Explicit teaching mode only: manual login must not silently become part
        # of the business workflow. Recording starts from the dashboard after login.
        self.auto_capture = False
        self.recording = False
        self.paused = False
        self.steps = []
        self.warnings = []
        self.start_url = project['url'].split('?')[0].split('#')[0]
        try:
            self.page.goto(project['url'], wait_until='domcontentloaded', timeout=45000)
        except Exception:
            self._do_close()
            raise
        # Inspect selectors only; user/password field VALUES are never read.
        self._capture_login_candidates()
        return self._do_status()

    def _do_attach_electron(self, project, cdp_port):
        """Attach to an existing Electron WebContentsView without reloading it.

        CDP is local-only. The selected target must have the project's
        registered origin and must be unambiguous (no guessed page/tab).
        """
        from urllib.parse import urlsplit
        if project['browser'] != 'chromium':
            raise ValueError('Desktop view requires Chromium ERP projects')
        port = int(cdp_port)
        if port < 1024 or port > 65535:
            raise ValueError('Invalid desktop debugging port')
        self._do_close()
        try:
            browser = self.p.chromium.connect_over_cdp(f'http://127.0.0.1:{port}', timeout=30000)
        except Exception as exc:
            raise ValueError('Could not attach Playwright to the local desktop Chromium debugging endpoint. Verify port 9337 is free and that Electron started correctly; CDP compatibility with this Chromium version may require adjustment. Details: ' + str(exc)[:180]) from exc
        expected = urlsplit(project['url'])
        target_origin = (expected.scheme, expected.netloc)
        try:
            matches = []
            # WebContentsView pages may appear asynchronously in CDP.
            for attempt in range(25):
                origin_matches = [(ctx, pg) for ctx in browser.contexts for pg in ctx.pages
                                  if not pg.is_closed() and
                                  (lambda parsed: (parsed.scheme, parsed.netloc) == target_origin)(urlsplit(pg.url))]
                # The built-in mock ERP shares localhost with the dashboard.
                # Prefer the registered ERP path when it disambiguates targets.
                registered_path = expected.path.rstrip('/')
                scoped = [(ctx,pg) for ctx,pg in origin_matches
                          if urlsplit(pg.url).path.rstrip('/') == registered_path or
                          (registered_path and urlsplit(pg.url).path.startswith(registered_path + '/'))]
                matches = scoped if scoped else origin_matches
                if len(matches) == 1:
                    break
                if len(matches) > 1:
                    break
                time.sleep(0.2)
            if len(matches) != 1:
                raise ValueError(f'Expected one Electron ERP tab on {expected.netloc}; found {len(matches)}. Close duplicate ERP windows or reopen the project.')
            ctx, page = matches[0]
            self.browser = browser
            self.context = ctx
            self.page = page
            self.active_project = project
            self.electron_attached = True
            self.script_cdp_port = int(cdp_port)
            self.embedded = False
            self.auto_capture = False
            self.recording = False
            self.paused = False
            self.steps = []
            self.warnings = []
            self.login_verified = False
            self.login_candidates = None
            self.login_setup = None
            self.login_setup_choices = []
            self.start_url = page.url.split('?')[0].split('#')[0]
            page.set_default_timeout(12000)
            # Inject on future navigations AND the already loaded login screen.
            # Register only on the ERP page, never the dashboard page.
            page.expose_binding('erpRecorderEvent', self._on_event)
            page.add_init_script(script=RECORDER_JS)
            page.evaluate(RECORDER_JS)
            ctx.on('page', self._on_new_page)
            self._capture_login_candidates()
            return self._do_status()
        except Exception:
            try:
                browser.close()  # Disconnect CDP, do not close Electron's views.
            except Exception:
                pass
            self.page = None
            self.browser = None
            self.context = None
            self.active_project = None
            self.electron_attached = False
            raise

    def _capture_login_candidates(self):
        if not self.page or self.page.is_closed():
            return {'detected': False, 'reason': 'Browser not open'}
        try:
            candidates = probe_login(self.page)
            if candidates.get('detected') and self.active_project['environment'] in ('test', 'staging'):
                self.login_candidates = candidates
                save_candidates(self.active_project['id'], self.active_project['url'], candidates)
            return candidates
        except Exception:
            return {'detected': False, 'reason': 'Login form could not be inspected'}

    def _do_login_candidates(self):
        if not self.active_project:
            raise ValueError('Open an ERP first')
        # Cached selectors remain accessible after the user logs in manually.
        if self.login_candidates and self.login_candidates.get('detected'):
            result = dict(self.login_candidates)
        else:
            result = self._capture_login_candidates()
        return {'project_id': self.active_project['id'], **result,
                'note': 'Selectors only, no credentials. Post-login success marker must be configured and verified.'}

    def _require_login_setup_page(self):
        if not self.page or self.page.is_closed() or not self.active_project:
            raise ValueError('Open the registered test ERP login screen first')
        if self.active_project['environment'] not in ('test', 'staging'):
            raise ValueError('Automatic login setup is only available for TEST/STAGING')
        if self.recording or self.paused:
            raise ValueError('Stop Teaching ERP before capturing login locators')
        actual = urlsplit(self.page.url)
        registered = urlsplit(self.active_project['url'])
        if (actual.scheme, actual.netloc) != (registered.scheme, registered.netloc):
            raise ValueError('Open the registered ERP origin; external SSO/OTP flows require manual login')

    def _do_login_setup_capture(self):
        """Stage 1: verify 3 unique controls BEFORE the user manually logs in."""
        self._require_login_setup_page()
        candidates = self._capture_login_candidates()
        if not candidates.get('detected'):
            raise ValueError(candidates.get('reason') or 'Cannot identify login fields')
        for field in ('username', 'password', 'submit'):
            found = locate(self.page, candidates[field])
            if found.count() != 1 or not found.is_visible():
                raise ValueError(f'Login {field} selector must match one visible control')
        pre = probe_post_login(self.page)
        if not pre.get('login_form_visible'):
            raise ValueError('Start on the visible ERP login form, before logging in')
        self.login_setup = {
            'project_id': self.active_project['id'],
            'fields': {k:candidates[k] for k in ('username','password','submit')},
            'pre_visible_markers': {json.dumps(c['locator'], sort_keys=True)
                                    for c in pre.get('candidates',[])},
        }
        self.login_setup_choices = []
        return {'captured': True, 'project_id': self.active_project['id'],
                'fields': self.login_setup['fields'],
                'message':'3 unique visible login controls captured. Log in manually, then choose a success marker.'}

    def _do_login_setup_success_options(self):
        """Stage 2: suggest unique post-login markers absent on the login screen."""
        self._require_login_setup_page()
        if not self.login_setup or self.login_setup['project_id'] != self.active_project['id']:
            raise ValueError('Capture the three login fields before signing in first')
        probe = probe_post_login(self.page)
        if probe.get('login_form_visible'):
            raise ValueError('Login form is still visible. Complete manual ERP login first')
        choices = []
        for candidate in probe.get('candidates',[]):
            spec = candidate['locator']
            if json.dumps(spec, sort_keys=True) in self.login_setup['pre_visible_markers']:
                continue
            locator = locate(self.page, spec)
            if locator.count() != 1 or not locator.is_visible():
                continue
            choices.append(candidate)
        self.login_setup_choices = choices[:20]
        return {'project_id':self.active_project['id'], 'candidates':[
            {'index':i, **c} for i,c in enumerate(self.login_setup_choices)],
            'ready':bool(self.login_setup_choices),
            'message':('Select the visible control that reliably indicates successful login.'
                       if self.login_setup_choices else
                       'No reliable post-login marker detected. Use the existing manual login JSON editor or inspect your ERP DOM.')}

    def _do_login_setup_finish(self, choice_index):
        """Stage 3: verify marker again, then return only selector metadata."""
        self._require_login_setup_page()
        if not self.login_setup or self.login_setup['project_id'] != self.active_project['id']:
            raise ValueError('Capture login fields before saving')
        if type(choice_index) is not int or choice_index < 0 or choice_index >= len(self.login_setup_choices):
            raise ValueError('Choose a suggested post-login success marker')
        if self.page.locator('input[type="password"]:visible').count() > 0:
            raise ValueError('Login form is visible; do not save success marker yet')
        spec = self.login_setup_choices[choice_index]['locator']
        if json.dumps(spec, sort_keys=True) in self.login_setup['pre_visible_markers']:
            raise ValueError('Success marker was already visible on the login screen')
        matching = locate(self.page, spec)
        if matching.count() != 1 or not matching.is_visible():
            raise ValueError('Success marker is no longer uniquely visible; recapture post-login options')
        return {'username':self.login_setup['fields']['username'],
                'password':self.login_setup['fields']['password'],
                'submit':self.login_setup['fields']['submit'],
                'success':spec}

    def _do_capture_failure(self, testcase_id='case'):
        """Best-effort screenshot for a runner exception outside _do_run.

        Called on the browser's own worker thread. Never alters the ERP page.
        """
        if not self.page or self.page.is_closed() or not self.active_project:
            return {'screenshot': None}
        name=re.sub(r'[^A-Za-z0-9_.-]', '_', str(testcase_id))[:50] or 'case'
        out=BASE/'artifacts'/self.active_project['id']/'suite_errors'
        out.mkdir(parents=True,exist_ok=True)
        path=out/f'{time.strftime("%Y%m%d-%H%M%S")}-{name}-{time.time_ns()%100000000:08d}.png'
        self.page.screenshot(path=str(path),full_page=True,timeout=6000)
        return {'screenshot':str(path.relative_to(BASE))}

    def _do_status(self):
        ready = bool(self.page and not self.page.is_closed())
        return {
            'open': ready,
            'embedded': bool(getattr(self, 'embedded', False)) if ready else False,
            'electron': bool(getattr(self, 'electron_attached', False)) if ready else False,
            'viewport': {'width': self.embedded_width, 'height': self.embedded_height} if ready and getattr(self, 'embedded', False) else None,
            'project_id': self.active_project['id'] if ready and self.active_project else None,
            'url': (self.page.url.split('?')[0].split('#')[0] if ready else None),
            'recording': self.recording if ready else False,
            'paused': self.paused if ready else False,
            'auto_capture': self.auto_capture if ready else False,
            'login_verified': self.login_verified if ready else False,
            'step_count': len(self.steps),
            'warnings': self.warnings[-8:]
        }

    def _do_health(self):
        if not self.page or self.page.is_closed():
            raise ValueError('Open ERP Application first')
        try:
            probe = self.page.evaluate('''() => ({
                installed: window.__smartErpRecorderInstalled === true,
                version: window.__smartErpRecorderVersion || 'unknown',
                bridge: typeof window.erpRecorderEvent === 'function'
            })''')
        except Exception:
            probe = {'installed': False, 'version': 'unknown', 'bridge': False}
        return {
            'installed': bool(probe['installed'] and probe['bridge']),
            'version': probe['version'],
            'frame_count': len(self.page.frames),
            'recording': self.recording,
            'step_count': len(self.steps),
            'note': ('Perform one click in the ERP and check Workflows live steps.'
                     if probe['installed'] and probe['bridge'] else
                     'Capture script unavailable on this page; close and reopen the ERP browser.'),
        }

    def _do_script_session(self, project_id):
        if not self.page or self.page.is_closed() or not self.active_project:
            raise ValueError('Open the ERP from ERP Applications and log in manually first')
        if self.active_project['id'] != project_id:
            raise ValueError('The live browser belongs to a different ERP project')
        if self.recording or self.paused:
            raise ValueError('Stop recording before handing the page to a script')
        if not self.script_cdp_port:
            raise ValueError('Managed script reuse needs Chromium. Close and reopen the ERP in this version.')
        expected, actual = urlsplit(self.active_project['url']), urlsplit(self.page.url)
        if (expected.scheme, expected.netloc) != (actual.scheme, actual.netloc):
            raise ValueError('Current page is not on the registered ERP origin')
        return {'endpoint': f'http://127.0.0.1:{self.script_cdp_port}', 'url': self.page.url}

    def _do_close(self):
        self.script_cdp_port = None
        self.recording = False
        self.paused = False
        self.auto_capture = False
        self.login_verified = False
        self.login_candidates = None
        self.login_setup = None
        self.login_setup_choices = []
        self.embedded = False
        # Electron owns its existing browser context and ERP view. Never close
        # the context: it may contain the dashboard and authenticated ERP tabs.
        attached = bool(getattr(self, 'electron_attached', False))
        self.electron_attached = False
        objects = (self.browser,) if attached else (self.context, self.browser)
        for obj in objects:
            if obj:
                try:
                    obj.close()
                except Exception:
                    pass
        self.page = None
        self.context = None
        self.browser = None
        self.active_project = None
        self.steps = []
        self.warnings = []
        return {'open': False}

    def _require_embedded(self):
        if not self.embedded or not self.page or self.page.is_closed():
            raise ValueError('Open an ERP using the embedded viewer first')

    def _do_embedded_frame(self):
        """Screenshot of the locally controlled browser viewport (never stored to disk)."""
        self._require_embedded()
        return self.page.screenshot(type='jpeg', quality=64, full_page=False,
                                    animations='disabled', timeout=15000)

    def _do_embedded_action(self, kind, x=None, y=None, text=None, key=None, delta_y=None):
        """User-initiated mouse/keyboard input in the existing Playwright session.

        No arbitrary JS execution and no server-side storage of typed text.
        Recording hooks in the ERP page see the same input sequence as a local browser.
        """
        self._require_embedded()
        if kind in ('click', 'dblclick'):
            if x is None or y is None or not (0 <= x < self.embedded_width and 0 <= y < self.embedded_height):
                raise ValueError('Pointer outside embedded ERP viewport')
            if kind == 'click':
                self.page.mouse.click(x, y)
            else:
                self.page.mouse.dblclick(x, y)
        elif kind == 'scroll':
            if delta_y is None or abs(delta_y) > 1600:
                raise ValueError('Invalid scroll offset')
            self.page.mouse.wheel(0, delta_y)
        elif kind == 'type':
            if not isinstance(text, str) or len(text) > 2048:
                raise ValueError('Invalid text length')
            self.page.keyboard.insert_text(text)
        elif kind == 'press':
            allowed = {'Enter','Tab','Escape','Backspace','Delete',
                       'ArrowUp','ArrowDown','ArrowLeft','ArrowRight','Home','End',
                       'PageUp','PageDown','Space','ControlOrMeta+A','Shift+Tab'}
            if key not in allowed:
                raise ValueError('Unsupported key')
            self.page.keyboard.press(key)
        else:
            raise ValueError('Unsupported embedded ERP input')
        return {'ok': True}

    def _do_prepare_flow(self):
        """Explicitly discard transient recorder buffer, preserving current login.

        Invoked only after operator confirms the unsaved actions may be discarded.
        No existing saved workflows or reviewed locator libraries are touched.
        """
        if not self.page or self.page.is_closed():
            raise ValueError('Open the ERP browser first')
        if self.active_project['environment'] not in ('test','staging'):
            raise ValueError('Flow replay requires a test/staging browser')
        discarded=len(self.steps)
        self.recording=False
        self.paused=False
        self.steps=[]
        self.warnings=[]
        return {'ready':True,'discarded_unsaved_steps':discarded,
                'message':'Recorder paused; authenticated ERP page remains open'}

    def _do_start(self):
        if not self.page or self.page.is_closed():
            raise ValueError('Open an ERP browser session and log in manually first')
        if self.active_project['environment'] == 'production':
            raise ValueError('Recording is disabled for production in this learning version')
        # Explicit Start Fresh Recording discards any passive early capture.
        self.steps = []
        self.warnings = []
        self.paused = False
        self.start_url = self.page.url.split('?')[0].split('#')[0]
        self.recording = True
        return self._do_status()

    def _do_pause(self):
        if not self.recording:
            raise ValueError('No active recorder to pause')
        self.recording = False
        self.paused = True
        return self._do_status()

    def _do_resume(self):
        if not self.paused or not self.page or self.page.is_closed():
            raise ValueError('No paused browser recorder to resume')
        self.paused = False
        self.recording = True
        return self._do_status()

    def _do_preview(self):
        # Never include browser storage or credentials; expose only the current
        # recording's already filtered action and selector metadata.
        return {'project_id': self.active_project['id'] if self.active_project else None,
                'recording': self.recording, 'paused': self.paused,
                'steps': [{'action': s.get('action'), 'target_text': s.get('target_text'),
                           'locator': s.get('locator'), 'observed_count': s.get('observed_count'),
                           'value': s.get('value') if s.get('action') not in ('click',) else None}
                          for s in self.steps[-50:]],
                'total': len(self.steps), 'warnings': self.warnings[-8:]}

    def _do_stop(self):
        if not self.recording and not self.paused:
            raise ValueError('No recording in progress')
        # Pump pending callbacks before disabling capture, so the last click is not lost.
        if self.page and not self.page.is_closed():
            self.page.wait_for_timeout(250)
        self.recording = False
        self.paused = False
        return {'project_id': self.active_project['id'], 'start_url': self.start_url, 'steps': list(self.steps), 'warnings': list(dict.fromkeys(self.warnings))}

    def _do_login(self, config, username, password):
        """Authenticate using configured locators, never store credentials."""
        if not self.page or self.page.is_closed():
            raise ValueError('Open the registered ERP browser before automatic login')
        if self.recording and not self.auto_capture:
            raise ValueError('Stop recording before automatic login')
        if not self.active_project or self.active_project['environment'] == 'production':
            raise ValueError('Automatic login is disabled for production projects')
        if not username or not password:
            raise ValueError('Username and password must be supplied at runtime')
        url = urlsplit(self.active_project['url'])
        if url.scheme != 'https' and url.hostname not in ('localhost', '127.0.0.1'):
            raise ValueError('Automatic login requires HTTPS except for localhost mock ERP')
        self.login_verified = False
        # Never capture anything entered by the automatic authentication handler.
        resume_capture = self.recording and self.auto_capture
        if resume_capture:
            self.recording = False
        try:
            # A success marker already visible on the login screen cannot
            # independently demonstrate a successful authentication transition.
            pre_success = locate(self.page, config['success'])
            if pre_success.count() == 1 and pre_success.is_visible():
                raise ValueError('Success marker is already visible before login')
            unique(self.page, config['username']).fill(username, timeout=12000)
            unique(self.page, config['password']).fill(password, timeout=12000)
            unique(self.page, config['submit']).click(timeout=12000)
            # A visible post-login element proves this particular login step
            # reached its configured success condition, not general permissions.
            target = locate(self.page, config['success'])
            target.wait_for(state='visible', timeout=30000)
            if target.count() != 1:
                raise AssertionError('Login success selector was not unique')
        except Exception as err:
            # Do not return Playwright exception text: it may include input values.
            raise ValueError('Automatic login was not verified. Check credentials, login locators or MFA requirements.') from err
        finally:
            if resume_capture:
                self.recording = True
        self.login_verified = True
        return {'verified': True, 'project_id': self.active_project['id']}

    def _do_inspect_dom(self):
        """Read-only, redacted live-DOM controls from the authenticated main frame.

        Display only safe HTML-like metadata, never page HTML, field values,
        cookies, password attributes, auth tokens or account numbers.
        """
        if not self.page or self.page.is_closed() or not self.active_project:
            raise ValueError('Open an ERP browser and log in manually before inspecting')
        result = self.page.evaluate(r"""() => {
          const sensitive = /pass(word)?|token|secret|auth|otp|pin|cvv|card|account.?number|ssn|api.?key/i;
          const clean = v => String(v || '').replace(/\s+/g, ' ').trim().slice(0, 100);
          const escapeCSS = v => CSS.escape(String(v));
          const safeAttr = (el,k) => { const v = el.getAttribute(k) || ''; return sensitive.test(k) || sensitive.test(v) ? '' : clean(v); };
          const visible = el => !!(el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden' && getComputedStyle(el).display !== 'none');
          const count = sel => { try { return document.querySelectorAll(sel).length; } catch (_) { return 0; } };
          const quote = v => JSON.stringify(String(v));
          const candidates = 'button,a[href],input:not([type="hidden"]),textarea,select,[role="button"],[role="menuitem"],[role="tab"],[role="option"],[role="combobox"],[contenteditable="true"],[data-testid]';
          const controls = [];
          for (const el of document.querySelectorAll(candidates)) {
            if (controls.length >= 100) break;
            if (!visible(el)) continue;
            const tag = el.tagName.toLowerCase();
            const typ = safeAttr(el,'type');
            if (typ === 'password' || typ === 'hidden' || typ === 'email' && el.closest('form')?.querySelector('input[type="password"]')) continue;
            if (el.closest('form')?.querySelector('input[type="password"]')) continue;
            if ([safeAttr(el,'name'),safeAttr(el,'id'),safeAttr(el,'placeholder'),safeAttr(el,'aria-label')].some(v => sensitive.test(v))) continue;
            const id = safeAttr(el,'id');
            const testid = safeAttr(el,'data-testid');
            const name = safeAttr(el,'name');
            const role = safeAttr(el,'role') || (tag === 'button' ? 'button' : tag === 'a' ? 'link' : '');
            const title = safeAttr(el,'title');
            const label = clean(tag === 'input' || tag === 'textarea' || tag === 'select' ? (safeAttr(el,'placeholder') || safeAttr(el,'aria-label')) : (safeAttr(el,'aria-label') || el.innerText || title));
            if (sensitive.test(label)) continue;
            const isGenerated = /^:r\d+:$|^(mui|radix|react-select|headlessui)-/i.test(id);
            const selectors = [];
            if (testid) selectors.push({spec:{kind:'test_id',value:testid},matches:count('[data-testid='+quote(testid)+']'),source:'data-testid'});
            if (id && !isGenerated) selectors.push({spec:{kind:'css',value:'#'+escapeCSS(id)},matches:count('#'+escapeCSS(id)),source:'id'});
            if (name) selectors.push({spec:{kind:'css',value:tag+'[name='+quote(name)+']'},matches:count(tag+'[name='+quote(name)+']'),source:'name'});
            for (const key of ['data-qa','data-test']) {
              const val=safeAttr(el,key);
              if (val) selectors.push({spec:{kind:'css',value:tag+'['+key+'='+quote(val)+']'},matches:count(tag+'['+key+'='+quote(val)+']'),source:key});
            }
            // Role candidates are suggestions only; DOM text does not fully
            // implement the accessibility name computation used by Playwright.
            const winner=selectors.find(c=>c.matches===1);
            const selector = winner ? winner.spec : null;
            const matches = winner ? winner.matches : (selectors[0]?.matches ?? 0);
            const attrs = [['id',id],['data-testid',testid],['name',name],['role',safeAttr(el,'role')],['title',title]]
              .filter(([,v])=>!!v).map(([k,v])=>' '+k+'='+quote(v)).join('');
            const html = '<'+tag+attrs+'>'+((tag === 'input' || tag === 'select' || tag === 'textarea') ? '' : label)+'</'+tag+'>';
            controls.push({tag,label,id,testid,name,role,title,html:html.slice(0,280),locator:selector,
              matches,source:winner?.source || '',unique:!!winner,generated_id:!!isGenerated,
              issue: isGenerated ? 'Generated ID, may change between sessions' : (id && count('#'+escapeCSS(id))>1 ? 'Duplicate ID in current page' : (!winner ? 'No stable unique selector found; re-record or review' : ''))});
          }
          return {page_url:location.origin+location.pathname,frame:'main',scanned:controls.length,controls};
        }""")
        result['project_id'] = self.active_project['id']
        result['note'] = 'Read-only main-frame inspection. HTML-like snippets are redacted summaries, not full source. Unique locators must still be reviewed before replay.'
        return result

    def _do_test_locator(self, spec):
        if not self.page or self.page.is_closed():
            raise ValueError('Open an ERP browser first')
        target = unique(self.page, spec)
        return {'count': 1, 'visible': target.is_visible(), 'text': (target.inner_text(timeout=1500) if target.is_visible() else '')[:100]}

    def _do_preflight_first(self, project_id, workflow_name, first_step, start_url, reviewed):
        """Read-only screen/locator check; no clicks, fills, or navigation."""
        if not self.page or self.page.is_closed() or not self.active_project:
            raise ValueError('Open your ERP in the Playwright browser, then log in manually')
        if self.active_project['id'] != project_id:
            raise ValueError('Open the matching ERP project before diagnosing its workflow')
        if not isinstance(first_step, dict) or not isinstance(first_step.get('locator'), dict):
            raise ValueError('First workflow step has no valid locator')
        current_url = self.page.url.split('?')[0].split('#')[0]
        start_url = str(start_url).split('?')[0].split('#')[0]
        current = urlsplit(current_url)
        expected = urlsplit(start_url)
        if (current.scheme, current.netloc) != (expected.scheme, expected.netloc):
            raise ValueError('Current browser is on a different origin. Return to the registered ERP page')
        spec = first_step['locator']
        loc = locate(self.page, spec)
        count = loc.count()
        visible = sum(1 for i in range(min(count, 20)) if loc.nth(i).is_visible())
        # Captured alternative selectors are diagnostic evidence, never automatic
        # replacement targets. Checking them must not click or edit the ERP.
        candidates = []
        seen = set()
        for saved in first_step.get('observed_candidates', [])[:15]:
            if not isinstance(saved, dict) or not isinstance(saved.get('spec'), dict):
                continue
            candidate = saved['spec']
            key = json.dumps(candidate, sort_keys=True)
            if key in seen or candidate == spec:
                continue
            seen.add(key)
            try:
                check = locate(self.page, candidate)
                matches = check.count()
                shown = sum(bool(check.nth(i).is_visible()) for i in range(min(matches, 20)))
                candidates.append({'locator': candidate, 'matches': matches,
                                   'visible_matches': shown,
                                   'uniquely_visible': matches == 1 and shown == 1,
                                   'captured_match_count': saved.get('observed_count', -1)})
            except Exception:
                continue
        # Read visible controls only. Never inspect field values, storage, cookies,
        # password data, or the entire document HTML.
        controls = self.page.evaluate('''() => {
          const nodes = document.querySelectorAll('button,[role="button"],[role="menuitem"],[role="tab"],a[href],input[type="button"],input[type="submit"]');
          return Array.from(nodes).filter(el => {
            const b = el.getBoundingClientRect(), s = getComputedStyle(el);
            return b.width > 0 && b.height > 0 && s.display !== 'none' && s.visibility !== 'hidden';
          }).slice(0,120).map(el => ({
            role: el.getAttribute('role') || (el.matches('a[href]') ? 'link' : 'button'),
            text: (el.getAttribute('aria-label') || el.innerText || el.textContent || el.getAttribute('title') || '').replace(/\\s+/g,' ').trim().slice(0,90)
          })).filter(x=>x.text).slice(0,40);
        }''')
        login_visible = self.page.locator('input[type="password"]:visible').count() > 0
        same_start_page = current_url.rstrip('/') == start_url.rstrip('/')
        # A strict route equality check used to reject every workflow after
        # ordinary ERP SPA navigation, despite a unique recorded control being
        # visible. A different route may be accepted ONLY for the first
        # harmless navigation click, with matching visible target identity.
        # Never auto-navigate, auto-replace locators or make unsafe guesses.
        target_text = str(first_step.get('target_text') or '').strip()
        action = first_step.get('action')
        safe_navigation = bool(action == 'click' and target_text and
                               not CRITICAL_RE.search(target_text))
        normalized_target = ' '.join(target_text.casefold().split())
        verified_first_target = False
        if not same_start_page and safe_navigation and count == 1 and visible == 1:
            kind = spec.get('kind')
            if kind == 'role' and spec.get('role') in ('button','link','tab','menuitem'):
                verified_first_target = ' '.join(str(spec.get('name') or '').casefold().split()) == normalized_target
            elif kind in ('css', 'test_id', 'text'):
                # All values come from a read-only locator. Never inspect input
                # values, cookies, passwords, authentication state or raw HTML.
                try:
                    node = loc.nth(0)
                    actual_labels = [node.get_attribute('aria-label'), node.get_attribute('title')]
                    if action == 'click':
                        actual_labels.append(node.inner_text(timeout=1000))
                    verified_first_target = any(
                        ' '.join(str(label or '').casefold().split()) == normalized_target
                        for label in actual_labels
                    )
                except Exception:
                    verified_first_target = False
        route_verified = bool(not same_start_page and verified_first_target)
        ready = bool(visible == 1 and count == 1 and not login_visible and reviewed
                     and (same_start_page or route_verified))
        problems = []
        if login_visible:
            problems.append('LOGIN REQUIRED: A login form is visible. Log in manually in the embedded ERP before replay.')
        if not count:
            problems.append('0 MATCHES: Step 1 locator was not found. Navigate to the start screen, or review its locator JSON against the live ERP.')
        elif not visible:
            problems.append('HIDDEN ELEMENT: Step 1 exists but is not visible. Open the relevant ERP menu or panel.')
        elif count != 1 or visible != 1:
            problems.append(f'AMBIGUOUS LOCATOR: Step 1 matched {count} elements ({visible} visible). Use an exact, unique locator; never click an arbitrary match.')
        if not same_start_page:
            if route_verified:
                problems.append('ROUTE VERIFIED: The URL differs, but Step 1 is a uniquely visible navigation control with a verified matching label. No auto-navigation or target replacement will occur.')
            else:
                problems.append('WRONG START ROUTE: Current ERP URL differs from the first recorded step. Return to that page. A route mismatch is not bypassed for fields, destructive buttons or unverified locators.')
        if any(x['uniquely_visible'] for x in candidates) and not (count == 1 and visible == 1):
            problems.append('ALTERNATIVE FOUND: A recorded alternative matches uniquely. Inspect the intended control and manually update/approve its mapping; No alternative was clicked.')
        if not reviewed:
            problems.append('REVIEW REQUIRED: Workflow approval or locator fingerprint is no longer valid; approve the current recording first.')
        if ready:
            problems.append('LOCATOR READY: Step 1 is uniquely visible. Later steps and business validations still require independent checks.')
        if login_visible:
            reason_code = 'LOGIN_REQUIRED'
        elif count == 0:
            reason_code = 'LOCATOR_NOT_FOUND'
        elif count != 1 or visible != 1:
            reason_code = 'LOCATOR_NOT_UNIQUE_OR_HIDDEN'
        elif not reviewed:
            reason_code = 'REVIEW_REQUIRED'
        elif not same_start_page and not route_verified:
            reason_code = 'START_ROUTE_MISMATCH'
        elif route_verified:
            reason_code = 'ROUTE_VERIFIED'
        else:
            reason_code = 'READY'
        return {'project_id':project_id,'workflow':workflow_name,'current_url':current_url,
                'recorded_start_url':start_url,'first_step_action':action,
                'first_step_target':target_text[:120],
                'first_step_locator':spec,'matches':count,'visible_matches':visible,
                'login_visible':login_visible,'reviewed':bool(reviewed),'ready':ready,
                'route_verified':route_verified,'reason_code':reason_code,
                'visible_controls':controls,'candidate_checks':candidates,'findings':problems,
                'note':'Read-only diagnostic: no clicks, navigation, or locator changes. Route changes are allowed only with an exact verified navigation control.'}

    def _do_run(self, workflow, allow_writes=False, allow_nav_repair=False):
        if not self.page or self.page.is_closed():
            raise ValueError('Open browser and log in manually before replay')
        if self.active_project['id'] != workflow['project_id']:
            raise ValueError('Workflow and browser project mismatch')
        if self.active_project['environment'] == 'production':
            raise ValueError('Replay on production is disabled')
        if self.recording:
            # Fresh-browsers opened by Run From Login have passive capture enabled.
            # Don't capture or replay internal automation actions.
            if self.auto_capture and not self.steps:
                self.recording = False
            else:
                raise ValueError('Finish & Save your manual demonstration before replay')
        if not workflow['reviewed']:
            raise ValueError('Workflow must be reviewed and approved before replay')
        if len(workflow['steps']) > 200:
            raise ValueError('Maximum 200 executable steps per workflow; split into smaller reviewed modules')
        root = urlsplit(self.active_project['url'])
        first = urlsplit(workflow['start_url'])
        if (first.scheme, first.netloc) != (root.scheme, root.netloc):
            raise ValueError('Workflow start URL does not belong to the registered ERP origin')
        current = urlsplit(self.page.url)
        if (current.scheme, current.netloc) != (root.scheme, root.netloc):
            raise ValueError('The current browser page is outside the registered ERP origin; return to the ERP')
        if os.environ.get('ERPQA_ALLOW_SAME_ORIGIN_PATHS') != '1':
            allowed = lambda path: (path.rstrip('/') == root.path.rstrip('/') or
                                    path.startswith(root.path.rstrip('/') + '/'))
            if not allowed(first.path) or not allowed(current.path):
                raise ValueError('Workflow/current page is outside registered ERP URL path. Return to the ERP or explicitly enable same-origin paths.')
        critical = any(CRITICAL_RE.search((s.get('target_text') or '') + ' ' + (s.get('logical_field') or '')) for s in workflow['steps'] if s['action'] == 'click')
        if critical and not allow_writes:
            raise ValueError('This workflow may create or approve records. Explicit test-transaction confirmation is required')
        # A fresh report; never auto-retry a failed Save, Submit, or Approve.
        now = time.strftime('%Y%m%d-%H%M%S')
        out = BASE / 'artifacts' / workflow['project_id'] / f'{now}-{workflow["name"]}-{time.time_ns()%1000000000:09d}'
        out.mkdir(parents=True, exist_ok=True)
        status = 'PASSED'
        message = f'{len(workflow["steps"])} actions completed; business assertions are not implemented yet'
        failed_step = None
        screenshot = None
        trace = None
        performed = 0
        failed_step_index = None
        outputs = {}
        repairs = []
        self.context.tracing.start(screenshots=True, snapshots=True, sources=True)
        try:
            # IMPORTANT: Do not reload recorded start_url. Navigating here can
            # redirect the authenticated user back to /login in some ERPs.
            # Caller must position the current authenticated page at the first
            # recorded step. Run From Login leaves the browser on the verified
            # post-login page.
            if self.page.locator('input[type="password"]:visible').count() > 0:
                raise ValueError('ERP login screen is still visible. Log in and verify the post-login page before replay.')
            for index, step in enumerate(workflow['steps'], start=1):
                failed_step_index = index
                failed_step = step.get('original_step_number', index)
                action = step['action']
                value = step.get('value')
                if action == 'click' and allow_nav_repair and navigation_label(step):
                    # An old role=button mapping may be stale after UI changes.
                    # Before ANY click, check exact, uniquely visible navigation
                    # alternatives from the reviewed recording/current DOM.
                    primary = locate(self.page, step['locator'])
                    target = None
                    if primary.count() == 1 and primary.is_visible():
                        target = primary
                    elif primary.count() != 1 or not primary.is_visible():
                        recovered = navigation_recovery(self.page, step)
                        if recovered is not None:
                            target, reason = recovered
                            repairs.append({'step': failed_step, 'target': navigation_label(step), 'reason': reason})
                    if target is None:
                        target = BasePage(self.page).element(step['locator'])
                else:
                    target = BasePage(self.page).element(step['locator'])
                if action == 'click':
                    target.click(timeout=12000)
                elif action == 'fill':
                    target.fill(str(value if value is not None else ''), timeout=12000)
                elif action == 'select_option':
                    target.select_option(str(value), timeout=12000)
                elif action == 'check':
                    target.check(timeout=12000)
                elif action == 'uncheck':
                    target.uncheck(timeout=12000)
                elif action == 'press':
                    target.press(str(value), timeout=12000)
                elif action == 'capture_text' or action == 'capture_value':
                    output_key = step.get('output')
                    if not output_key or not re.fullmatch(r'[a-z][a-z0-9_]{0,79}', output_key):
                        raise ValueError('Capture step requires a named runtime output')
                    if target.get_attribute('type') == 'password':
                        raise ValueError('Password values may not be captured')
                    output_value = (target.inner_text(timeout=12000) if action == 'capture_text' else target.input_value(timeout=12000)).strip()
                    if not output_value or len(output_value) > 150:
                        raise ValueError('Captured value was blank or too long')
                    outputs[output_key] = output_value
                elif action == 'assert_text':
                    assert target.inner_text(timeout=12000).strip() == str(value).strip(), 'Exact text assertion failed'
                elif action == 'assert_value':
                    assert target.input_value(timeout=12000) == str(value), 'Exact value assertion failed'
                elif action == 'assert_visible':
                    assert target.is_visible(), 'Element not visible'
                else:
                    raise ValueError(f'Unsupported action: {action}')
                performed += 1
            failed_step = None
            if repairs:
                message += f'; {len(repairs)} verified navigation locator recovery(s) applied (see report)'
        except Exception as exc:
            status = 'FAILED'
            detail = str(exc)
            if failed_step_index and failed_step_index <= len(workflow['steps']):
                failing = workflow['steps'][failed_step_index - 1]
                diagnostic = navigation_diagnostic(self.page, failing)
                if diagnostic.get('eligible') and 'Element not visible on current page' in detail:
                    visible_nav = diagnostic.get('unique_visible_controls')
                    if visible_nav == 1:
                        detail += (' | Exactly one visible navigation control has the recorded label, '
                                   'but the saved locator did not match. Recheck the approved '
                                   'mapping or enable navigation-only recovery for a reviewed run.')
                    elif visible_nav == 0:
                        detail += (' | No visible navigation control has the recorded label. '
                                   'Check the logged-in role, expanded menus, or the previous step.')
                    elif isinstance(visible_nav, int):
                        detail += (' | Multiple navigation controls share the label. '
                                   'Provide a unique reviewed locator; no control was guessed.')
            # Explain the two most common causes of replay step-1 failures.
            # Never auto-navigate, guess another element, or retry state-changing clicks.
            if failed_step_index == 1 and 'Element not visible on current page' in detail:
                expected_page = (workflow['steps'][0].get('page_url')
                                 or workflow.get('start_url') or '')
                current_page = str(getattr(self.page, 'url', 'unknown'))
                if expected_page.rstrip('/') != current_page.rstrip('/'):
                    detail += (f' | First-step recorded page: {expected_page}. '
                               'Replay does not navigate automatically. Open that ERP screen '
                               'manually after login, then test the first locator.')
                else:
                    detail += (' | Current page matches the recorded URL, but this '
                               'locator is not visible. Inspect the element name/text '
                               'and correct the project-specific locator JSON if needed.')
            message = f'Failed at step {failed_step}: {detail[:850]}'
            screenshot_path = out / 'failure.png'
            try:
                self.page.screenshot(path=str(screenshot_path), full_page=True, timeout=6000)
                screenshot = str(screenshot_path.relative_to(BASE))
            except Exception:
                pass
        finally:
            trace_path = out / 'trace.zip'
            try:
                self.context.tracing.stop(path=str(trace_path))
                trace = str(trace_path.relative_to(BASE))
            except Exception:
                pass
        report = {'project_id': workflow['project_id'], 'workflow': workflow['name'], 'status': status, 'completed_steps': performed, 'failed_step': failed_step, 'message': message, 'screenshot': screenshot, 'trace': trace, 'assertions': 'supported_for_explicit_assert_steps', 'outputs':outputs, 'navigation_recoveries': repairs,
                  'session_reused': bool(workflow.get('reuse_existing_login', False)),
                  'skipped_initial_login_steps': int(workflow.get('skipped_initial_login_steps', 0))}
        (out / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        report['report_path'] = str((out / 'report.json').relative_to(BASE))
        return report


    def _do_run_flow(self, flow, stages, allow_writes, test_data):
        """Run already-approved same-session stages without guessing navigation.

        This is one Playwright worker command. Runtime document IDs captured in
        earlier stages can be referenced as ${pi_number} in later stage values.
        """
        from backend.json_workflow import resolve_locators, read_library, LocatorLibrary
        from backend.locator import Workflow
        if not self.active_project or flow['project_id'] != self.active_project['id']:
            raise ValueError('Open the matching ERP project first')
        if self.active_project['environment'] not in ('test', 'staging'):
            raise ValueError('Flow execution is restricted to TEST/STAGING')
        if not allow_writes:
            raise ValueError('Explicit transaction authorization required')
        if self.recording and self.steps:
            raise ValueError('Stop and save your recording before running a business flow')
        variables = dict(test_data)
        results = []
        for index, (stage, spec) in enumerate(zip(flow['stages'], stages), start=1):
            if stage.get('different_account'):
                raise ValueError('Automatic account switching belongs in Approval Plans')
            try:
                wf = Workflow.model_validate(spec)
                library = (read_library(flow['project_id']) if wf.schema_version == 2
                           else LocatorLibrary(project_id=flow['project_id']))
                executable = resolve_locators(wf, library, variables)
                result = self._do_run(executable, allow_writes=True)
                results.append({'number':index,'phase':stage['phase'], 'workflow':stage['workflow'],
                                'status':result['status'], 'message':result['message'],
                                'completed_steps': result['completed_steps'],
                                'failed_step':result.get('failed_step'),
                                'report_path':result.get('report_path')})
                if result['status'] != 'PASSED':
                    break
                for key, value in result.get('outputs', {}).items():
                    if key in variables and variables[key] != value:
                        raise ValueError('A captured document identifier conflicts with a previous value')
                    variables[key] = value
            except Exception as exc:
                results.append({'number':index,'phase':stage['phase'], 'workflow':stage['workflow'],
                                'status':'FAILED', 'message':f'{type(exc).__name__}: {str(exc)[:450]}',
                                'completed_steps':0,'failed_step':None})
                break
        ok = len(results) == len(stages) and all(s['status']=='PASSED' for s in results)
        report = {'project_id':flow['project_id'], 'workflow':flow['name'],
                  'status':'PASSED' if ok else 'FAILED', 'completed_stages':sum(s['status']=='PASSED' for s in results),
                  'total_stages':len(stages), 'completed_steps':sum(s.get('completed_steps',0) for s in results),
                  'failed_step':next((s['number'] for s in results if s['status']!='PASSED'),None),
                  'message':('All reviewed stages and explicit assertions completed; business correctness needs separate checks.'
                             if ok else 'Stopped at stage '+str(len(results))+': '+results[-1]['message']),
                  'stages':results,'outputs':{k:v for k,v in variables.items() if k not in test_data},
                  'report_path':None}
        now = time.strftime('%Y%m%d-%H%M%S')
        folder = BASE / 'artifacts' / flow['project_id'] / f'{now}-flow-{flow["name"]}-{time.time_ns()%1000000000:09d}'
        folder.mkdir(parents=True, exist_ok=True)
        (folder / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
        report['report_path'] = str((folder / 'report.json').relative_to(BASE))
        return report

    def _do_run_plan(self, plan, workflows, login_config, accounts, allow_writes, test_data):
        """Run a reviewed chain in this one browser thread, preserving captured IDs.

        After each approval, require an explicit reviewed post-action assertion.
        Account switching requires a reviewed logout workflow and verified login.
        A failed stage immediately stops the plan, so later approvals/GRN do not run.
        """
        from backend.locator import Workflow, locate
        from backend.json_workflow import resolve_locators, read_library
        if not self.active_project or self.active_project['id'] != plan['project_id']:
            raise ValueError('Open the browser for the selected ERP project first')
        if self.active_project['environment'] == 'production':
            raise ValueError('Approval plans cannot execute against production')
        if not self.page or self.page.is_closed():
            raise ValueError('Browser is not available')
        if self.recording:
            if self.auto_capture and not self.steps:
                self.recording=False
            else:
                raise ValueError('Stop and save manual recording before running a plan')
        all_results=[]
        variables=dict(test_data)
        current_account=None
        status='PASSED'
        explanation='All planned actions and configured post-action assertions completed. This is not an independent ERP audit.'
        for seq,stage in enumerate(plan['stages'],start=1):
            alias=stage.get('account')
            try:
                if alias and alias != current_account:
                    if current_account is not None:
                        if not plan.get('logout_workflow'):
                            raise ValueError('Logout workflow must be configured for account switching')
                        logout_workflow=Workflow.model_validate(workflows[plan['logout_workflow']])
                        logout_exec=resolve_locators(logout_workflow,read_library(plan['project_id']),variables)
                        logout_report=self._do_run(logout_exec,allow_writes=False)
                        if logout_report['status']!='PASSED':
                            raise RuntimeError('Reviewed logout workflow failed; next login blocked')
                        # We need to see the configured login field before entering another account.
                        login_username=locate(self.page,login_config['username'])
                        if login_username.count()!=1 or not login_username.is_visible():
                            raise RuntimeError('Logout was not verified by a visible unique login field')
                    else:
                        login_username=locate(self.page,login_config['username'])
                        if login_username.count()!=1 or not login_username.is_visible():
                            raise ValueError('Start the plan on the login screen (close any manual session first)')
                    account=accounts[alias]
                    self._do_login(login_config,account['username'],account['password'])
                    current_account=alias
                workflow=Workflow.model_validate(workflows[stage['workflow']])
                executable=resolve_locators(workflow,read_library(plan['project_id']),variables)
                report=self._do_run(executable,allow_writes=allow_writes)
                result={'stage':seq,'name':stage['name'],'phase':stage['phase'],
                        'account':alias,'workflow':workflow.name,'status':report['status'],
                        'message':report['message'],'assertion_required':stage['require_assertion'],
                        'completed_steps':report['completed_steps'],
                        'report_path':report.get('report_path'),
                        'outputs':report.get('outputs',{})}
                all_results.append(result)
                if report['status']!='PASSED':
                    status='FAILED'
                    explanation=f"Stopped at {stage['name']}: {report['message']}"
                    break
                for key,value in report.get('outputs',{}).items():
                    if key in variables and variables[key]!=value:
                        raise ValueError('Captured variable conflicts with earlier value: '+key)
                    variables[key]=value
            except Exception as exc:
                status='FAILED'
                # No usernames, passwords or raw browser trace text returned here.
                explanation=f'Plan stopped at stage {seq} ({stage["name"]}): {type(exc).__name__}: {str(exc)[:220]}'
                all_results.append({'stage':seq,'name':stage['name'],'workflow':stage['workflow'],
                                    'phase':stage['phase'],'account':alias,'status':'FAILED',
                                    'message':explanation})
                break
        return {'project_id':plan['project_id'],'workflow':plan['name'],'status':status,
                'completed_stages':sum(x['status']=='PASSED' for x in all_results),
                'total_stages':len(plan['stages']), 'stages':all_results,
                'outputs':{k:v for k,v in variables.items() if k not in test_data},
                'message':explanation}

    def _do_negative_check(self, workflow, cases):
        """Evaluate browser-native invalid-input rules on the CURRENT form only.

        Does NOT navigate, replay setup clicks, save, submit, approve or persist data.
        Unsupported/custom validations are reported as NEEDS_RULES, not PASSED.
        """
        if not self.page or self.page.is_closed() or not self.active_project:
            raise ValueError('Open an ERP test browser on the form before negative checks')
        if self.active_project['environment'] not in ('test', 'staging'):
            raise ValueError('Negative checks are prohibited on production')
        if self.recording:
            raise ValueError('Finish & Save automatic capture before running negative checks')
        if workflow['project_id'] != self.active_project['id'] or not workflow.get('reviewed'):
            raise ValueError('Choose an approved workflow belonging to the active project')
        if len(cases) > 50:
            raise ValueError('Too many negative cases')
        results=[]
        for case in cases:
            spec=case['locator']
            try:
                target=unique(self.page, spec)
                if not target.is_visible():
                    raise ValueError('Field not visible on current form')
                # checkValidity() may only represent native HTML5 rules, not ERP business rules.
                native=target.evaluate('el => typeof el.checkValidity === "function"')
                if not native:
                    results.append({'id':case['id'], 'status':'NEEDS_RULES', 'reason':'Custom control lacks native validity checking'})
                    continue
                original=target.input_value(timeout=2500)
                try:
                    target.fill(str(case['invalid_value']),timeout=3500)
                    verdict=target.evaluate('el => ({valid: el.checkValidity(), willValidate: el.willValidate})')
                finally:
                    target.fill(original,timeout=3500)
                if not verdict['willValidate']:
                    status='NEEDS_RULES'
                    reason='No browser-native constraint applicable; configure ERP business assertion'
                elif verdict['valid'] is False:
                    status='PASSED'
                    reason='Browser-native HTML constraint rejected invalid input'
                else:
                    status='FAILED'
                    reason='Browser-native constraint did not reject invalid input'
                results.append({'id':case['id'],'status':status,'reason':reason})
            except Exception:
                results.append({'id':case['id'],'status':'BLOCKED','reason':'Cannot test this field on the current form; navigate to it and verify its locator'})
        return {'project_id':workflow['project_id'],'workflow':workflow['name'], 'kind':'native_negative_checks',
                'summary':{key:sum(r['status']==key for r in results) for key in ('PASSED','FAILED','BLOCKED','NEEDS_RULES')},
                'cases':results, 'note':'No Save/Submit/Approve clicked. HTML constraint checks only; ERP business rules not validated.'}
