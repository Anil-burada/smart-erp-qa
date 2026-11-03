"""Project-mapped, reviewed business flows using one reusable Playwright engine.

A flow does not infer business rules, choose locators across ERPs, or change
accounts. Each ERP must supply its own reviewed workflow per stage.
"""
from __future__ import annotations
import re
from pathlib import Path
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.registry import BASE, PROJECT_PATTERN, WORKFLOW_PATTERN, get_project
from backend.json_workflow import atomic_json, read_library, fingerprint
from backend.approval_plans import read_workflow, assertion_after_action

VARIABLE = re.compile(r'^\$\{([a-z][a-z0-9_]*)\}$')
VAR_NAME = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
PHASES = ('indent_create', 'indent_approval', 'requisition', 'po_create',
          'po_approval', 'grn_create', 'grn_verify', 'other')


class FlowStage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    phase: str = Field(max_length=50)
    workflow: str
    require_assertion: bool = True
    different_account: bool = False

    @field_validator('workflow')
    @classmethod
    def valid_workflow(cls, v):
        if not WORKFLOW_PATTERN.fullmatch(v):
            raise ValueError('Each stage needs a real recorded workflow name')
        return v

    @field_validator('phase')
    @classmethod
    def valid_phase(cls, v):
        if v not in PHASES:
            raise ValueError('Unsupported phase: use one of ' + ', '.join(PHASES))
        return v


class BusinessFlow(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project_id: str
    name: str
    description: str = Field(default='', max_length=300)
    stages: list[FlowStage] = Field(min_length=1, max_length=20)

    @field_validator('project_id')
    @classmethod
    def valid_project(cls, v):
        if not PROJECT_PATTERN.fullmatch(v):
            raise ValueError('Invalid ERP project ID')
        return v

    @field_validator('name')
    @classmethod
    def valid_name(cls, v):
        if not WORKFLOW_PATTERN.fullmatch(v):
            raise ValueError('Flow name must be lowercase letters, digits, - or _')
        return v

    @model_validator(mode='after')
    def validate_version(self):
        if self.schema_version != 1:
            raise ValueError('Unknown flow schema')
        return self


def flow_path(project_id: str, name: str) -> Path:
    if not PROJECT_PATTERN.fullmatch(project_id) or not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid flow path')
    return BASE / 'flows' / project_id / (name + '.json')


def save_flow(flow: BusinessFlow) -> dict:
    if not get_project(flow.project_id):
        raise ValueError('Register this ERP first')
    path = flow_path(flow.project_id, flow.name)
    atomic_json(path, flow.model_dump_json(indent=2))
    return flow.model_dump()


def load_flow(project_id: str, name: str) -> BusinessFlow:
    path = flow_path(project_id, name)
    if not path.is_file():
        raise ValueError('Flow was not saved for this ERP project')
    data = BusinessFlow.model_validate_json(path.read_text(encoding='utf-8'))
    if data.project_id != project_id or data.name != name:
        raise ValueError('Flow project/name mismatch')
    return data


def list_flows() -> list[dict]:
    root = BASE / 'flows'
    result = []
    if not root.is_dir():
        return result
    for file in sorted(root.glob('*/*.json')):
        try:
            item = BusinessFlow.model_validate_json(file.read_text(encoding='utf-8'))
            if flow_path(item.project_id, item.name) == file:
                result.append({'project_id': item.project_id, 'name': item.name,
                               'stages': len(item.stages)})
        except (ValueError, OSError):
            continue
    return result


def starter_flow(project_id: str) -> dict:
    if not get_project(project_id):
        raise ValueError('Register this ERP first')
    return {'schema_version': 1, 'project_id': project_id, 'name': 'indent_to_grn',
            'description': 'Replace workflow values with actual reviewed recordings for this ERP. Omit unused phases.',
            'stages': [{'phase': phase, 'workflow': 'replace_me', 'require_assertion': True,
                        'different_account': False} for phase in
                       ('indent_create', 'indent_approval', 'po_create', 'grn_create', 'grn_verify')]}


def preview_flow(flow: BusinessFlow, test_data: dict | None = None) -> dict:
    """Preflight every stage before transactions; no browser action occurs here."""
    test_data = test_data or {}
    issues = []
    if not isinstance(test_data, dict) or len(test_data) > 100 or any(not VAR_NAME.fullmatch(k) for k in test_data):
        raise ValueError('Runtime test data must be a small object of named variables')
    for k, val in test_data.items():
        if not isinstance(val, (str, float, int, bool)) or len(str(val)) > 1000:
            raise ValueError('Invalid runtime variable: ' + k)
    project = get_project(flow.project_id)
    if not project or project['environment'] not in ('test', 'staging'):
        issues.append('Register this flow ERP as TEST or STAGING. Production is not supported.')
    available = set(test_data)
    stages = []
    for i, stage in enumerate(flow.stages, 1):
        blockers = []
        wf = read_workflow(flow.project_id, stage.workflow)
        if stage.different_account:
            blockers.append('Requires a different user: use the reviewed Approval Plans runner with local credential aliases')
        if wf is None:
            blockers.append('Record workflow ' + stage.workflow + ' in ' + flow.project_id)
        else:
            if not wf.reviewed:
                blockers.append('Review and approve workflow ' + stage.workflow)
            if wf.schema_version == 2:
                try:
                    if wf.locator_fingerprint != fingerprint(wf, read_library(flow.project_id)):
                        blockers.append('Locator mapping changed: approve workflow again')
                except ValueError as exc:
                    blockers.append('Locator library error: ' + str(exc)[:100])
            if stage.require_assertion and not assertion_after_action(wf):
                blockers.append('Add an explicit status/visibility assertion AFTER final action')
            for step in wf.steps:
                if isinstance(step.value, str) and step.value.startswith('${'):
                    match = VARIABLE.fullmatch(step.value)
                    if not match:
                        blockers.append('Invalid runtime variable expression')
                    elif match.group(1) not in available:
                        blockers.append('Missing runtime value ${' + match.group(1) + '} from test data or earlier captured stage')
                if step.action in ('capture_text','capture_value'):
                    if not step.output or not VAR_NAME.fullmatch(step.output):
                        blockers.append('Capture step needs a valid output key')
                    elif step.output in available:
                        blockers.append('Captured output key already exists: ' + step.output)
                    else:
                        available.add(step.output)
        stages.append({'number': i, 'phase': stage.phase, 'workflow': stage.workflow,
                       'step_count': len(wf.steps) if wf else 0,
                       'ready': not blockers, 'issues': list(dict.fromkeys(blockers))})
        issues.extend(blockers)
    return {'project_id': flow.project_id, 'name': flow.name, 'ready': not issues,
            'issues': list(dict.fromkeys(issues)), 'stages': stages,
            'runtime_variables': sorted(available),
            'note': 'This validates recorded actions and explicit assertions, not ERP business-rule correctness. One manually authenticated user only.'}
