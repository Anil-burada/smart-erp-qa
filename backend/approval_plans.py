"""Multiple ERP approval plans: no credentials stored, no unverified approval chaining."""
from __future__ import annotations
import json
import os
import re
from pathlib import Path
from typing import Any, Literal
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from backend.registry import BASE, PROJECT_PATTERN, WORKFLOW_PATTERN, get_project, workflow_path
from backend.locator import Workflow
from backend.json_workflow import atomic_json, read_library, fingerprint

ALIASES = re.compile(r'^[a-z][a-z0-9_]{0,31}$')
SAFE_VARIABLE = re.compile(r'^\$\{([a-z][a-z0-9_]*)\}$')
PLAN_DIR = BASE / 'approval_plans'


class PlanStage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    name: str = Field(min_length=1, max_length=100)
    workflow: str
    account: str | None = None
    phase: Literal['create','submit','approval','grn','navigation','verification'] = 'navigation'
    require_assertion: bool = False

    @field_validator('workflow')
    @classmethod
    def validate_workflow(cls, value):
        if not WORKFLOW_PATTERN.fullmatch(value):
            raise ValueError('Invalid workflow ID')
        return value

    @field_validator('account')
    @classmethod
    def validate_alias(cls, value):
        if value is not None and not ALIASES.fullmatch(value):
            raise ValueError('Account must be a lower-case alias, e.g. gm')
        return value

    @model_validator(mode='after')
    def safe_approval(self):
        # An approval is not verified merely by clicking Approve.
        if self.phase == 'approval' and not self.require_assertion:
            raise ValueError('Every approval stage must require a post-action assertion')
        return self


class ApprovalPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: Literal[1] = 1
    project_id: str
    name: str
    description: str = Field(default='', max_length=500)
    logout_workflow: str | None = None
    stages: list[PlanStage] = Field(min_length=1, max_length=40)

    @field_validator('project_id')
    @classmethod
    def project_id_valid(cls,v):
        if not PROJECT_PATTERN.fullmatch(v):
            raise ValueError('Invalid project ID')
        return v

    @field_validator('name','logout_workflow')
    @classmethod
    def name_valid(cls,v):
        if v is not None and not WORKFLOW_PATTERN.fullmatch(v):
            raise ValueError('Invalid plan or logout workflow name')
        return v

    @model_validator(mode='after')
    def validate_accounts(self):
        if any(s.account is not None for s in self.stages) and self.logout_workflow is None:
            raise ValueError('Account-switching plans require an approved logout workflow')
        return self


def plan_path(project_id: str,name: str) -> Path:
    if not PROJECT_PATTERN.fullmatch(project_id) or not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid plan ID')
    return PLAN_DIR / project_id / f'{name}.json'


def save_plan(plan: ApprovalPlan):
    if get_project(plan.project_id) is None:
        raise ValueError('Register the ERP project before saving its approval plan')
    # only store project ID, stage names and aliases, no usernames, passwords, URLs or browser tokens
    path=plan_path(plan.project_id,plan.name)
    atomic_json(path,plan.model_dump_json(indent=2))
    return plan.model_dump()


def load_plan(project_id,name):
    path=plan_path(project_id,name)
    if not path.is_file():
        raise FileNotFoundError('Approval plan not found')
    plan=ApprovalPlan.model_validate_json(path.read_text(encoding='utf-8'))
    if plan.project_id != project_id or plan.name != name:
        raise ValueError('Stored approval plan identity mismatch')
    return plan


def list_plans():
    result=[]
    for path in sorted(PLAN_DIR.glob('*/*.json')):
        try:
            plan=ApprovalPlan.model_validate_json(path.read_text(encoding='utf-8'))
            if plan_path(plan.project_id,plan.name).resolve() != path.resolve():
                continue
            result.append({'project_id':plan.project_id,'name':plan.name,
                           'description':plan.description,'stages':len(plan.stages),
                           'registered':get_project(plan.project_id) is not None})
        except (ValueError, OSError):
            continue
    return result


def read_workflow(project_id,name):
    path=workflow_path(project_id,name)
    if not path.exists():
        return None
    wf=Workflow.model_validate_json(path.read_text(encoding='utf-8'))
    if wf.project_id != project_id or wf.name != name:
        raise ValueError('Workflow project mismatch')
    return wf


def assertion_after_action(wf: Workflow) -> bool:
    """Require an explicit visible/text/value assertion AFTER the last mutating click."""
    actions={'click','fill','press','select_option','check','uncheck'}
    last=max((i for i,s in enumerate(wf.steps) if s.action in actions),default=-1)
    return any(s.action in {'assert_text','assert_value','assert_visible'} for s in wf.steps[last+1:])


def preview_plan(plan: ApprovalPlan, test_data: dict | None = None):
    """Static preflight: tells user exactly what is missing BEFORE any browser work."""
    test_data=test_data or {}
    is_registered=get_project(plan.project_id) is not None
    issues=[] if is_registered else ['Register ERP project '+plan.project_id]
    stages=[]
    produced=set()
    accounts=[]
    for number,stage in enumerate(plan.stages,start=1):
        wf=read_workflow(plan.project_id,stage.workflow)
        problems=[]
        if wf is None:
            problems.append('Record workflow '+stage.workflow)
        else:
            if not wf.reviewed:
                problems.append('Review/approve this recorded workflow')
            if wf.schema_version==2:
                try:
                    if wf.locator_fingerprint!=fingerprint(wf,read_library(plan.project_id)):
                        problems.append('Locator mapping changed; review workflow')
                except ValueError as exc:
                    problems.append('Locator mapping missing/invalid: '+str(exc)[:90])
            if stage.require_assertion and not assertion_after_action(wf):
                problems.append('Add an explicit status/visibility assertion after final action')
            for s in wf.steps:
                if isinstance(s.value,str) and s.value.startswith('${'):
                    match=SAFE_VARIABLE.fullmatch(s.value)
                    if not match:
                        problems.append('Invalid variable expression')
                    elif match.group(1) not in produced and match.group(1) not in test_data:
                        # runtime test_data can supply these values; project preflight does not assume them
                        problems.append('Needs runtime variable '+match.group(1)+' (prior capture or test data)')
                if s.action in ('capture_text','capture_value') and s.output:
                    produced.add(s.output)
        if stage.account and stage.account not in accounts:
            accounts.append(stage.account)
        row={'number':number,'name':stage.name,'phase':stage.phase,'workflow':stage.workflow,
             'account':stage.account,'step_count':len(wf.steps) if wf else 0,
             'ready':not problems,'issues':list(dict.fromkeys(problems))}
        stages.append(row)
        issues.extend(problems)
    if plan.logout_workflow:
        logout=read_workflow(plan.project_id,plan.logout_workflow)
        if not logout or not logout.reviewed:
            issues.append('Record/review logout workflow '+plan.logout_workflow)
        elif not assertion_after_action(logout):
            issues.append('Logout workflow needs a post-logout login-screen assertion')
    return {'project_id':plan.project_id,'name':plan.name,
            'ready':is_registered and not issues,'stages':stages,
            'accounts':accounts,'produced_variables':sorted(produced),
            'issues':list(dict.fromkeys(issues))}


def local_accounts(project_id: str,aliases: list[str]):
    """Load credentials from environment only; never return this mapping from the API."""
    # Optional .env support, not overwritten if environment already has a value.
    try:
        from dotenv import load_dotenv
        load_dotenv(BASE/'.env',override=False)
    except ImportError:
        pass
    result={}
    for alias in aliases:
        if not ALIASES.fullmatch(alias):
            raise ValueError('Invalid credential alias')
        prefix=f'ERPQA_{project_id.upper().replace("-","_")}_{alias.upper()}'
        username=os.environ.get(prefix+'_USERNAME','')
        password=os.environ.get(prefix+'_PASSWORD','')
        if not username or not password:
            raise ValueError(f'Missing local credentials for alias {alias}; configure {prefix}_USERNAME and _PASSWORD in .env')
        result[alias]={'username':username,'password':password}
    return result


def executable_specs(plan:ApprovalPlan,require_ready:bool=True):
    # Validated inputs are sent to the single Playwright worker; resolving runtime
    # values happens stage-by-stage after capture outputs are available.
    preflight=preview_plan(plan)
    if require_ready and not preflight['ready']:
        raise ValueError('Approval plan is not ready: '+'; '.join(preflight['issues'][:8]))
    workflows={}
    for stage in plan.stages:
        wf=read_workflow(plan.project_id,stage.workflow)
        if not wf or not wf.reviewed:
            raise ValueError('Workflow not approved: '+stage.workflow)
        workflows[stage.workflow]=wf.model_dump()
    if plan.logout_workflow:
        wf=read_workflow(plan.project_id,plan.logout_workflow)
        if not wf or not wf.reviewed:
            raise ValueError('Logout workflow not approved')
        workflows[plan.logout_workflow]=wf.model_dump()
    return workflows
