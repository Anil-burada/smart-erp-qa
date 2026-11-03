"""Project-isolated locator library + language-neutral JSON workflow converter.

Steps reference keys; locators live only in projects/<project_id>/locators.json.
All existing schema-v1 workflows continue to load and run unchanged.
"""
from __future__ import annotations
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any
from pydantic import BaseModel, ConfigDict, Field, field_validator
from backend.locator import LocatorSpec, Workflow
from backend.registry import BASE, PROJECT_PATTERN, WORKFLOW_PATTERN, get_project

TARGET_PATTERN = re.compile(r"^[a-z][a-z0-9_-]{0,59}\.step_[0-9]{3,4}$")
VARIABLE_PATTERN = re.compile(r"^\$\{([a-z][a-z0-9_]*)\}$")

class FieldSpec(BaseModel):
    model_config = ConfigDict(extra='forbid')
    locator: LocatorSpec
    field_type: str = 'unknown'
    required: bool = False
    selection_mode: str = 'fixed'
    observed_count: int = -1
    constraints: dict[str, str | bool] = Field(default_factory=dict)
    @field_validator('selection_mode')
    @classmethod
    def selection_valid(cls, v):
        if v not in ('fixed', 'runtime'):
            raise ValueError('Only fixed/runtime values supported in this phase; round-robin is later')
        return v

class LocatorLibrary(BaseModel):
    model_config = ConfigDict(extra='forbid')
    schema_version: int = 1
    project_id: str
    fields: dict[str, FieldSpec] = Field(default_factory=dict)
    @field_validator('fields')
    @classmethod
    def fields_valid(cls,v):
        if not all(TARGET_PATTERN.fullmatch(key) for key in v):
            raise ValueError('Invalid locator field key')
        return v


def locator_path(project_id: str) -> Path:
    if not PROJECT_PATTERN.fullmatch(project_id) or not get_project(project_id):
        raise ValueError('Unregistered ERP project ID')
    return BASE / 'projects' / project_id / 'locators.json'


def read_library(project_id: str) -> LocatorLibrary:
    path=locator_path(project_id)
    if not path.exists():
        return LocatorLibrary(project_id=project_id)
    result=LocatorLibrary.model_validate_json(path.read_text(encoding='utf-8'))
    if result.project_id != project_id:
        raise ValueError('Locator file project mismatch')
    return result


def atomic_json(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp=path.with_name(path.name+'.tmp')
    tmp.write_text(content,encoding='utf-8')
    os.replace(tmp,path)


def save_library(library: LocatorLibrary) -> None:
    read_library(library.project_id)  # validate registered ID and existing library
    atomic_json(locator_path(library.project_id),library.model_dump_json(indent=2))


def fingerprint(workflow: Workflow, lib: LocatorLibrary) -> str:
    if workflow.project_id != lib.project_id:
        raise ValueError('Workflow and locator project mismatch')
    fields={}
    for step in workflow.steps:
        if not step.target or step.target not in lib.fields:
            raise ValueError(f'Missing locator target: {step.target}')
        fields[step.target]=lib.fields[step.target].locator.model_dump(exclude_none=True)
    raw=json.dumps(fields,sort_keys=True,separators=(',',':'))
    return hashlib.sha256(raw.encode('utf-8')).hexdigest()


def convert_recording(project_id: str, name: str, start_url: str, recorded_steps: list[dict]):
    if not get_project(project_id) or not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid or unregistered project / workflow name')
    lib=read_library(project_id)
    steps=[]
    for index,raw in enumerate(recorded_steps,start=1):
        key=f'{name}.step_{index:03d}'
        if key in lib.fields:
            raise ValueError(f'Locator target exists already: {key}')
        kind={'click':'button','fill':'text','select_option':'select','press':'text','check':'checkbox','uncheck':'checkbox'}.get(raw.get('action'),'unknown')
        lib.fields[key]=FieldSpec(locator=LocatorSpec.model_validate(raw['locator']),field_type=kind,observed_count=raw.get('observed_count',-1),required=raw.get('field_meta',{}).get('required',False),constraints=raw.get('field_meta',{}))
        step={k:v for k,v in raw.items() if k!='locator'}
        step['target']=key
        steps.append(step)
    workflow=Workflow(schema_version=2,project_id=project_id,name=name,start_url=start_url,steps=steps,reviewed=False,locator_fingerprint='pending')
    workflow.locator_fingerprint=fingerprint(workflow,lib)
    return workflow,lib


def resolve_locators(workflow: Workflow, lib: LocatorLibrary, test_data: dict[str,Any] | None=None) -> dict:
    """Pure preflight: rejects missing locators/data before any Playwright action."""
    test_data=test_data or {}
    if workflow.schema_version==2 and workflow.locator_fingerprint != fingerprint(workflow,lib):
        raise ValueError('Locator mappings changed; review/approve workflow again')
    result=workflow.model_dump()
    for step in result['steps']:
        if workflow.schema_version == 2:
            spec=lib.fields[step['target']]
            step['locator']=spec.locator.model_dump(exclude_none=True)
        value=step.get('value')
        if isinstance(value,str) and value.startswith('${'):
            match=VARIABLE_PATTERN.fullmatch(value)
            if not match:
                raise ValueError(f'Invalid runtime variable: {value[:80]}')
            key=match.group(1)
            if key not in test_data:
                raise ValueError(f'Missing test data input: {key}')
            replacement=test_data[key]
            if not isinstance(replacement,(str,int,float,bool)) or len(str(replacement))>1000:
                raise ValueError(f'Invalid input for variable: {key}')
            step['value']=replacement
    return result
