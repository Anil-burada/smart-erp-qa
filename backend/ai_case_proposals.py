"""Optional AI *suggestions* from minimal non-secret workflow structure.

Never sends ERP screenshots, DOM, URLs, credentials, locator values or recorded field
values. Suggestions are untrusted draft ideas, not executable tests or business rules.
"""
from __future__ import annotations
import json
import os
import re
from typing import Literal
import httpx
from pydantic import BaseModel, Field, ConfigDict
from backend.locator import Workflow
from backend.json_workflow import read_library
from backend.approval_plans import read_workflow

MODEL_PATTERN=re.compile(r'^[a-zA-Z0-9._:/-]{1,80}$')


class AiIdea(BaseModel):
    model_config=ConfigDict(extra='ignore')
    category: Literal['positive','negative']
    title:str=Field(min_length=3,max_length=160)
    expectation:str=Field(min_length=3,max_length=300)
    review_needed:bool=True


class Ideas(BaseModel):
    model_config=ConfigDict(extra='ignore')
    cases:list[AiIdea]=Field(default_factory=list,max_length=20)


def workflow_metadata(wf:Workflow):
    """Avoid sending captured selector values, usernames, URLs or test data to AI."""
    lib=read_library(wf.project_id) if wf.schema_version==2 else None
    safe=[]
    for s in wf.steps[:100]:
        field_type='unknown'
        constraints={}
        if lib and s.target and s.target in lib.fields:
            spec=lib.fields[s.target]
            field_type=spec.field_type
            constraints={k:v for k,v in spec.constraints.items() if k in ('required','min','max','minlength','maxlength','type')}
        safe.append({'action':s.action,'type':field_type,'constraints':constraints})
    return {'workflow_steps':safe,'step_count':len(wf.steps)}


def offline_ideas(wf:Workflow):
    steps=workflow_metadata(wf)['workflow_steps']
    ideas=[AiIdea(category='positive',title='Reviewed happy-path execution',
       expectation='Execute the approved steps, then independently check created record IDs and status').model_dump()]
    if any(s['action']=='fill' for s in steps):
        ideas.extend([
          AiIdea(category='negative',title='Required field validation',expectation='Leave a verified mandatory input blank; check for an expected validation error without saving').model_dump(),
          AiIdea(category='negative',title='Invalid numeric boundary',expectation='When a numeric field is identified, test an out-of-range value under approved business rules').model_dump()])
    if any(s['action']=='click' for s in steps):
        ideas.append(AiIdea(category='positive',title='Button workflow status',expectation='Validate server-side status or audit trail after Save, Submit or Approve; clicking is insufficient').model_dump())
    return {'provider':'rules','cases':ideas,'note':'Draft test ideas only; no automation executed. Review required before implementing.'}


def _parse_response(raw:str,provider:str):
    try:
        doc=json.loads(raw)
        parsed=Ideas.model_validate(doc)
    except (ValueError,TypeError) as exc:
        raise ValueError(f'{provider} returned invalid JSON test suggestions') from exc
    return {'provider':provider,'cases':[x.model_dump() for x in parsed.cases],
            'note':'AI-generated suggestions are untrusted and not automatically executable. Verify business rules first.'}


def generate_ideas(project_id:str, workflow_name:str,provider:str,model:str|None=None):
    wf=read_workflow(project_id,workflow_name)
    if not wf:
        raise ValueError('Record a workflow before generating test ideas')
    if provider=='rules':
        return offline_ideas(wf)
    if provider not in ('openai','ollama'):
        raise ValueError('Choose rules, openai, or ollama')
    if model and not MODEL_PATTERN.fullmatch(model):
        raise ValueError('Invalid AI model identifier')
    metadata=workflow_metadata(wf)
    prompt=('You are assisting an ERP QA tester. Based ONLY on sanitized input field ACTION TYPES and constraints, '
        'propose up to 8 non-destructive positive and negative test-case ideas. Do not invent ERP rules or claim tests passed. '
        'No browser actions or executable code. Respond with ONLY JSON object: '
        '{"cases":[{"category":"positive|negative","title":"...","expectation":"...","review_needed":true}]} '\
        'Use no actual credentials, page URLs, or record values. Metadata:\n'+json.dumps(metadata,separators=(',',':')))
    try:
        if provider=='ollama':
            # Loopback only; never accept user-controlled host addresses.
            host='http://127.0.0.1:11434/api/generate'
            selected=model or os.environ.get('ERPQA_OLLAMA_MODEL','llama3.2')
            with httpx.Client(timeout=50.0) as client:
                res=client.post(host,json={'model':selected,'prompt':prompt,'stream':False,'format':'json'})
                res.raise_for_status()
                output=res.json().get('response','')
            return _parse_response(output,'ollama')
        try:
            from dotenv import load_dotenv
            from backend.registry import BASE
            load_dotenv(BASE/'.env',override=False)
        except ImportError:
            pass
        key=os.environ.get('OPENAI_API_KEY','')
        if not key:
            raise ValueError('OPENAI_API_KEY is missing from the local environment')
        selected=model or os.environ.get('ERPQA_OPENAI_MODEL','gpt-5.5')
        # Public official OpenAI Responses endpoint, opt-in only.
        with httpx.Client(timeout=60.0) as client:
            res=client.post('https://api.openai.com/v1/responses',
                headers={'Authorization':f'Bearer {key}','Content-Type':'application/json'},
                json={'model':selected,'input':prompt,'store':False,'max_output_tokens':950})
            res.raise_for_status()
            answer=res.json()
        chunks=[]
        for item in answer.get('output',[]):
            if item.get('type')=='message':
                chunks.extend(c.get('text','') for c in item.get('content',[]) if c.get('type')=='output_text')
        return _parse_response(''.join(chunks),'openai')
    except httpx.HTTPError as exc:
        # Do not return authorization headers or request bodies.
        raise ValueError(f'{provider} service unavailable or rejected the request; check your local model/API key and network') from exc
