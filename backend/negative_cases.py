"""Conservative HTML-field negative candidates derived from recorded constraints.

This does NOT infer ERP authorization, pricing, inventory, or approval business rules.
Only constraints that the browser can check with checkValidity() are offered.
"""
from decimal import Decimal, InvalidOperation
from backend.locator import Workflow
from backend.json_workflow import LocatorLibrary, fingerprint


def _below(value: str) -> str | None:
    try:
        return str(Decimal(str(value)) - Decimal(1))
    except (InvalidOperation, ValueError):
        return None


def _above(value: str) -> str | None:
    try:
        return str(Decimal(str(value)) + Decimal(1))
    except (InvalidOperation, ValueError):
        return None


def generate_candidates(workflow: Workflow, library: LocatorLibrary) -> list[dict]:
    if workflow.schema_version != 2:
        raise ValueError('Negative generation requires JSON-driven v2 locator metadata')
    if fingerprint(workflow, library) != workflow.locator_fingerprint:
        raise ValueError('Locator mappings changed; review workflow again')
    proposals=[]
    seen=set()
    for step in workflow.steps:
        if step.action != 'fill' or step.target in seen:
            continue
        seen.add(step.target)
        field=library.fields[step.target]
        metadata=field.constraints
        input_type=str(metadata.get('input_type','text')).lower()
        # Never create negative values for secrets or invisible/sensitive types.
        if input_type in ('password','hidden','file','checkbox','radio','submit'):
            continue
        def add(kind, value, rule):
            if value is None or len(proposals) >= 50:
                return
            proposals.append({
                'id':f'NEG-{len(proposals)+1:03d}',
                'target':step.target,
                'kind':kind,
                'invalid_value':str(value),
                'expected':'browser_rejects_invalid_input',
                'rule_source':rule,
                'reviewed':False
            })
        if metadata.get('required') is True:
            add('required_blank','', 'html_required')
        if input_type in ('number','range'):
            if metadata.get('min','') != '':
                add('below_min',_below(metadata['min']), 'html_min')
            if metadata.get('max','') != '':
                add('above_max',_above(metadata['max']), 'html_max')
        if input_type == 'email':
            add('invalid_email','invalid-email', 'html_type_email')
        if input_type in ('text','search','tel','url','email'):
            length=metadata.get('minlength','')
            if str(length).isdigit() and int(length) > 1:
                add('below_minlength','x'*(int(length)-1), 'html_minlength')
    return proposals
