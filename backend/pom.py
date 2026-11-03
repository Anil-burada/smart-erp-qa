"""Project-agnostic Page Object Model, backed by project-specific locator JSON.

One business template can be mapped to a different ERP's recorded locator keys.
Templates describe *what* to do; mappings describe *where* for one ERP project.
No selectors, URLs, or credentials are embedded in business templates.
"""
from __future__ import annotations

import re
import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from backend.json_workflow import atomic_json, read_library, VARIABLE_PATTERN
from backend.locator import locate, unique, Workflow
from backend.registry import BASE, WORKFLOW_PATTERN, get_project

ALIAS_RE = re.compile(r'^[a-z][a-z0-9_]{0,79}$')
ACTIONS = {'click', 'fill', 'select_option', 'check', 'uncheck', 'press',
           'capture_text', 'capture_value', 'assert_text', 'assert_value', 'assert_visible'}
VARIABLE_RE = VARIABLE_PATTERN


class BasePage:
    """Shared POM methods used across ERP applications."""
    def __init__(self, page):
        self.page = page

    def element(self, locator_spec: dict):
        return unique(self.page, locator_spec)

    def click(self, spec):
        self.element(spec).click()

    def fill(self, spec, value):
        self.element(spec).fill(str(value))

    def select(self, spec, value):
        self.element(spec).select_option(str(value))

    def visible(self, spec):
        return self.element(spec).is_visible()


class POMStep(BaseModel):
    model_config = ConfigDict(extra='forbid')
    action: str
    field: str
    value: str | float | int | bool | None = None
    output: str | None = None
    description: str = ''

    @field_validator('action')
    @classmethod
    def valid_action(cls, value):
        if value not in ACTIONS:
            raise ValueError('Unsupported POM action')
        return value

    @field_validator('field')
    @classmethod
    def valid_field(cls, value):
        if not ALIAS_RE.fullmatch(value):
            raise ValueError('Use a simple logical field name, e.g. indent_quantity')
        return value

    @field_validator('output')
    @classmethod
    def valid_output(cls, value):
        if value is not None and not ALIAS_RE.fullmatch(value):
            raise ValueError('Invalid runtime output variable')
        return value

    @model_validator(mode='after')
    def check_output(self):
        if self.action.startswith('capture_') and not self.output:
            raise ValueError('Capture step requires output, e.g. indent_number')
        return self


class SharedTemplate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    name: str
    start_suffix: str = ''
    steps: list[POMStep] = Field(min_length=1)

    @field_validator('name')
    @classmethod
    def valid_name(cls, name):
        if not WORKFLOW_PATTERN.fullmatch(name):
            raise ValueError('Invalid template name')
        return name

    @field_validator('start_suffix')
    @classmethod
    def valid_suffix(cls, suffix):
        if suffix and (not suffix.startswith('/') or '//' in suffix or '?' in suffix or '#' in suffix or '..' in suffix):
            raise ValueError('Template start suffix must be a relative URL path below the registered ERP root')
        return suffix


class ProjectFieldMap(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project_id: str
    template_name: str
    fields: dict[str, str] = Field(default_factory=dict)
    reviewed: bool = False
    locator_fingerprint: str | None = None
    template_fingerprint: str | None = None

    @field_validator('fields')
    @classmethod
    def valid_fields(cls, fields):
        if any(not ALIAS_RE.fullmatch(key) for key in fields):
            raise ValueError('Invalid logical field name')
        return fields


def template_path(name: str) -> Path:
    if not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid template name')
    return BASE / 'shared_workflows' / f'{name}.json'


def mapping_path(project_id: str, template_name: str) -> Path:
    if not get_project(project_id):
        raise ValueError('Unknown ERP project')
    template_path(template_name)
    return BASE / 'projects' / project_id / 'module_maps' / f'{template_name}.json'


def read_template(name: str) -> SharedTemplate:
    file = template_path(name)
    if not file.exists():
        raise ValueError(f'Shared template {name} is not configured')
    template = SharedTemplate.model_validate_json(file.read_text(encoding='utf-8'))
    if template.name != name:
        raise ValueError('Shared template name mismatch')
    return template


def list_templates() -> list[str]:
    root = BASE / 'shared_workflows'
    return sorted(p.stem for p in root.glob('*.json') if WORKFLOW_PATTERN.fullmatch(p.stem))


def read_map(project_id: str, name: str) -> ProjectFieldMap:
    path = mapping_path(project_id, name)
    if not path.exists():
        return ProjectFieldMap(project_id=project_id, template_name=name, fields={})
    mapping = ProjectFieldMap.model_validate_json(path.read_text(encoding='utf-8'))
    if mapping.project_id != project_id or mapping.template_name != name:
        raise ValueError('Project POM mapping identity mismatch')
    return mapping


def template_fingerprint(template: SharedTemplate) -> str:
    raw = json.dumps(template.model_dump(),sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode()).hexdigest()

def map_fingerprint(mapping: ProjectFieldMap) -> str:
    lib = read_library(mapping.project_id)
    refs = {alias:lib.fields[target].locator.model_dump(exclude_none=True)
            for alias,target in mapping.fields.items() if target in lib.fields}
    return hashlib.sha256(json.dumps(refs,sort_keys=True,separators=(",",":")).encode()).hexdigest()

def validate_mapping(template: SharedTemplate, mapping: ProjectFieldMap) -> None:
    lib = read_library(mapping.project_id)
    missing = {step.field for step in template.steps if step.field not in mapping.fields}
    if missing:
        raise ValueError('Unmapped POM fields: ' + ', '.join(sorted(missing)))
    for alias, target in mapping.fields.items():
        if target not in lib.fields:
            raise ValueError(f'Mapping for {alias} references missing locator: {target}')
        field = lib.fields[target]
        if field.observed_count != 1:
            raise ValueError(f'Locator {target} needs uniqueness verification before mapping approval')


def save_map(mapping: ProjectFieldMap) -> ProjectFieldMap:
    template = read_template(mapping.template_name)
    if not get_project(mapping.project_id):
        raise ValueError('Unknown ERP project')
    # Save as DRAFT; explicit review/approval is a separate action.
    draft = mapping.model_copy(update={'reviewed': False})
    for alias in draft.fields:
        if alias not in {step.field for step in template.steps}:
            raise ValueError(f'Unrecognized template field: {alias}')
    atomic_json(mapping_path(draft.project_id, draft.template_name), draft.model_dump_json(indent=2))
    return draft


def approve_map(project_id: str, template_name: str) -> ProjectFieldMap:
    template = read_template(template_name)
    mapping = read_map(project_id, template_name)
    validate_mapping(template, mapping)
    mapping.reviewed = True
    mapping.locator_fingerprint = map_fingerprint(mapping)
    mapping.template_fingerprint = template_fingerprint(template)
    atomic_json(mapping_path(project_id, template_name), mapping.model_dump_json(indent=2))
    return mapping


def _slug(text: str) -> str:
    cleaned = re.sub(r'[^a-z0-9]+', '_', text.lower()).strip('_')[:50]
    return cleaned if cleaned and cleaned[0].isalpha() else 'field'


def create_template_from_workflow(workflow: Workflow, template_name: str) -> tuple[SharedTemplate, ProjectFieldMap]:
    """Convert ONE approved recording to a shared template + its project mapping.
    For another project, keep template and create a new mapping, never copy locators.
    """
    if workflow.schema_version != 2 or not workflow.reviewed:
        raise ValueError('Review and approve a v2 recording before building a shared template')
    if template_path(template_name).exists():
        raise ValueError('Template already exists; map another project instead')
    project = get_project(workflow.project_id)
    if not project:
        raise ValueError('ERP project not registered')
    root = urlsplit(project['url']); recorded = urlsplit(workflow.start_url)
    if (root.scheme, root.netloc) != (recorded.scheme, recorded.netloc):
        raise ValueError('Recording URL does not belong to this ERP project')
    root_path = root.path.rstrip('/')
    if not (recorded.path == root_path or recorded.path.startswith(root_path + '/')):
        raise ValueError('Recorded URL is outside ERP project root')
    suffix = recorded.path[len(root_path):]
    lib = read_library(workflow.project_id)
    fields = {}
    steps = []
    used = set()
    for index, step in enumerate(workflow.steps, 1):
        if step.target not in lib.fields:
            raise ValueError(f'Missing source locator: {step.target}')
        if step.observed_count != 1 or lib.fields[step.target].observed_count != 1:
            raise ValueError(f'Step {index} must be verified before template creation')
        base = _slug(f'{step.action}_{step.target_text}')
        alias = base[:68]
        suffix_no = 2
        while alias in used:
            alias = f'{base[:65]}_{suffix_no}'
            suffix_no += 1
        used.add(alias)
        fields[alias] = step.target
        steps.append(POMStep(action=step.action, field=alias, value=step.value, description=step.target_text))
    template = SharedTemplate(name=template_name, start_suffix=suffix, steps=steps)
    mapping = ProjectFieldMap(project_id=workflow.project_id,template_name=template_name,fields=fields,reviewed=True)
    validate_mapping(template,mapping)
    mapping.locator_fingerprint = map_fingerprint(mapping)
    mapping.template_fingerprint = template_fingerprint(template)
    atomic_json(template_path(template_name), template.model_dump_json(indent=2))
    atomic_json(mapping_path(mapping.project_id,template_name), mapping.model_dump_json(indent=2))
    return template, mapping


def save_template(name: str, updated: SharedTemplate) -> SharedTemplate:
    current = read_template(name)
    if updated.name != name:
        raise ValueError('Cannot rename a shared template by editing it')
    # Only modify the template, never any ERP project's locator mappings.
    # Fingerprint change automatically forces each project to reapprove.
    atomic_json(template_path(name),updated.model_dump_json(indent=2))
    return updated


def compile_pom(project_id: str, template_name: str, test_data: dict[str, Any] | None=None, context: dict[str,Any] | None=None) -> dict:
    """Create a validated browser-run specification; does not execute any clicks."""
    project = get_project(project_id)
    if not project or project['environment'] not in ('test','staging'):
        raise ValueError('POM replay requires registered TEST/STAGING project')
    template = read_template(template_name)
    mapping = read_map(project_id,template_name)
    if not mapping.reviewed:
        raise ValueError(f'Project mapping for {template_name} must be reviewed and approved')
    validate_mapping(template,mapping)
    if mapping.locator_fingerprint != map_fingerprint(mapping) or mapping.template_fingerprint != template_fingerprint(template):
        raise ValueError('Template or mapped locators changed; approve project mapping again')
    lib = read_library(project_id)
    values = dict(context or {})
    values.update(test_data or {})
    steps = []
    for action in template.steps:
        value = action.value
        if isinstance(value,str) and value.startswith('${'):
            found = VARIABLE_RE.fullmatch(value)
            if not found:
                raise ValueError(f'Invalid test data variable: {value}')
            key = found.group(1)
            if key not in values:
                raise ValueError(f'Missing required runtime value: {key}')
            value = values[key]
            if not isinstance(value,(str,int,float,bool)) or len(str(value))>1000:
                raise ValueError('Invalid runtime value')
        spec = lib.fields[mapping.fields[action.field]].locator.model_dump(exclude_none=True)
        steps.append({'action':action.action,'locator':spec,'value':value,'output':action.output,
                      'target_text':action.description, 'logical_field':action.field})
    # Relative path is appended only to the project's own registered URL.
    return {'project_id':project_id, 'name':template_name, 'reviewed':True,
            'start_url':project['url'].rstrip('/') + template.start_suffix, 'steps':steps}


def pom_native_negative_candidates(project_id: str, template_name: str) -> list[dict]:
    """Reuse verified HTML constraints in THIS project's mapped locator library.

    No ERP business rule is inferred. Returned cases remain unreviewed drafts.
    """
    from backend.locator import Step, Workflow
    from backend.json_workflow import fingerprint
    from backend.negative_cases import generate_candidates

    project=get_project(project_id)
    if not project or project['environment'] not in ('test','staging'):
        raise ValueError('TEST/STAGING project required')
    template=read_template(template_name)
    mapping=read_map(project_id,template_name)
    if not mapping.reviewed or mapping.locator_fingerprint!=map_fingerprint(mapping) or mapping.template_fingerprint!=template_fingerprint(template):
        raise ValueError('Review the project POM mapping before generating negative cases')
    validate_mapping(template,mapping)
    # Make a temporary in-memory workflow to reuse the existing conservative
    # HTML5 candidate generator, without saving or changing any recorded file.
    steps=[]
    for action in template.steps:
        if action.action == 'fill':
            steps.append(Step(action='fill',target=mapping.fields[action.field],observed_count=1))
    if not steps:
        return []
    lib=read_library(project_id)
    virtual=Workflow(schema_version=2,project_id=project_id,name=template_name,
                     start_url=project['url'],steps=steps,locator_fingerprint='temporary')
    virtual.locator_fingerprint=fingerprint(virtual,lib)
    return generate_candidates(virtual,lib)
