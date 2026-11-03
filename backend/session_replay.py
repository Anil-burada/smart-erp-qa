"""Conservative reuse of an ALREADY authenticated ERP browser.

Only a complete, clearly recorded login FORM prefix (username, password,
submit) can be omitted. Mid-flow role changes and unrecognized steps are
NEVER skipped. The controller itself keeps the currently open browser/page.
No credentials, cookies, or storage values are read or persisted.
"""
from __future__ import annotations

import re
from backend.json_workflow import LocatorLibrary, fingerprint
from backend.locator import Workflow

USER_LABEL = re.compile(r'(?<!\w)(?:user[\s_-]*name|user[\s_-]*id|login[\s_-]*id|email|e-mail)(?!\w)', re.I)
PASS_LABEL = re.compile(r'(?<!\w)(?:password|pass[\s_-]*word|passwd|passcode)(?!\w)', re.I)
SUBMIT_LABEL = re.compile(r'(?<!\w)(?:log[\s_-]*in|sign[\s_-]*in|login|signin)(?!\w)', re.I)


def _control_signature(step: dict, library: LocatorLibrary | None) -> str:
    spec = step.get('locator') or {}
    if not spec and library and step.get('target') in library.fields:
        spec = library.fields[step['target']].locator.model_dump(exclude_none=True)
    # Locator names/attributes are metadata, never recorded field values.
    return ' '.join(str(x) for x in (step.get('target_text'), spec.get('name'), spec.get('value')) if x)


def initial_login_prefix(steps: list[dict], library: LocatorLibrary | None = None) -> int:
    """Return number of safely skippable leading login form actions, or 0.

    Require a username entry AND password entry AND explicit login submit in
    sequence. A standalone Login button, Logout, or later role relogin remains
    part of the business workflow. Never skip arbitrary steps on the URL alone.
    """
    states = []
    for step in steps[:6]:
        action = step.get('action')
        text = _control_signature(step, library)
        if action == 'fill' and USER_LABEL.search(text) and not PASS_LABEL.search(text):
            states.append('user')
        elif action == 'fill' and PASS_LABEL.search(text):
            states.append('password')
        elif action == 'click' and SUBMIT_LABEL.search(text) and not re.search(r'log\s*out|sign\s*out', text, re.I):
            states.append('submit')
            break
        elif action == 'press' and str(step.get('value') or '').casefold() == 'enter' and states and states[-1] == 'password':
            states.append('submit')
            break
        else:
            return 0
    if (len(states) >= 3 and states[-1] == 'submit'
            and 'user' in states[:-1] and 'password' in states[:-1]
            and len(steps) > len(states)):
        return len(states)
    return 0


def planned_existing_session_workflow(workflow: Workflow, library: LocatorLibrary) -> tuple[Workflow, int]:
    """Prepare workflow without editing the user's saved workflow/approval.

    Locator fingerprint is validated against the ORIGINAL approved workflow
    before deriving a temporary, in-memory executable subset.
    """
    if workflow.schema_version == 2 and workflow.locator_fingerprint != fingerprint(workflow, library):
        raise ValueError('Locator mappings changed; review/approve workflow again')
    count = initial_login_prefix([step.model_dump(exclude_none=True) for step in workflow.steps], library)
    if not count:
        return workflow, 0
    prepared = workflow.model_copy(deep=True)
    prepared.steps = prepared.steps[count:]
    # Never permanently edit original file or its reviewed fingerprint.
    if prepared.schema_version == 2:
        prepared.locator_fingerprint = fingerprint(prepared, library)
    return prepared, count
