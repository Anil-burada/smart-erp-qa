"""Explicitly configured, single-login linked workflow plan.

Requires separate reviewed POM templates and actual recorded capture outputs.
A change of ERP user role is blocked until a verified role-switch workflow exists.
"""
from __future__ import annotations
from pydantic import BaseModel, ConfigDict, Field, model_validator
from backend.pom import read_template, read_map, validate_mapping, map_fingerprint, VARIABLE_RE
from backend.registry import get_project


class LinkedStage(BaseModel):
    model_config = ConfigDict(extra='forbid')
    template: str
    role: str = 'creator'


class LinkedPlan(BaseModel):
    model_config = ConfigDict(extra='forbid')
    project_id: str
    stages: list[LinkedStage] = Field(min_length=1, max_length=12)
    test_data: dict[str, str | int | float | bool] = Field(default_factory=dict)
    allow_test_transactions: bool = False

    @model_validator(mode='after')
    def secure(self):
        if not self.allow_test_transactions:
            # POM chain is high-impact by design; explicit opt-in required.
            raise ValueError('Linked execution requires explicit authorization for TEST/STAGING transactions')
        return self


def inspect_plan(plan: LinkedPlan) -> dict:
    project = get_project(plan.project_id)
    if not project or project['environment'] not in ('test','staging'):
        raise ValueError('Linked workflow execution requires registered TEST/STAGING ERP')
    available = set(plan.test_data)
    produced=set()
    details=[]
    roles = set()
    for number,stage in enumerate(plan.stages,1):
        template=read_template(stage.template)
        mapping=read_map(plan.project_id,stage.template)
        validate_mapping(template,mapping)
        if not mapping.reviewed or mapping.locator_fingerprint != map_fingerprint(mapping):
            raise ValueError(f'Unreviewed or changed mapping in stage {number}: {stage.template}')
        needs=set()
        outputs=set()
        for s in template.steps:
            if isinstance(s.value,str) and s.value.startswith('${'):
                matched=VARIABLE_RE.fullmatch(s.value)
                if not matched:
                    raise ValueError(f'Invalid variable in {stage.template}')
                needs.add(matched.group(1))
            if s.action.startswith('capture_'):
                outputs.add(s.output)
        missing = needs - available
        if missing:
            raise ValueError(f'Stage {stage.template} needs missing runtime values: {sorted(missing)}')
        if outputs & produced:
            raise ValueError(f'Stage {stage.template} would overwrite previously captured transaction identifiers')
        available |= outputs
        produced |= outputs
        roles.add(stage.role)
        details.append({'stage':number,'template':stage.template,'role':stage.role,'inputs':sorted(needs),'outputs':sorted(outputs)})
    if len(roles) > 1:
        raise ValueError('Linked workflows use different ERP roles. Automatic role switching is not yet configured; run modules individually with authorized accounts.')
    return {'project_id':plan.project_id,'stages':details,'available_outputs':sorted(produced),
            'ready':True,'note':'Mapping and dependency preflight only. Business assertions still require explicit steps.'}
