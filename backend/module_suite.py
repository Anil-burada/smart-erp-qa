"""v6.2.8: module/process selection + exact 11-column Excel QA cases.

Existing Playwright scripts are inert artifacts. Only existing *approved* Smart ERP
JSON workflows are executed by the browser worker. No uploaded code is exec'd.
"""
from __future__ import annotations
import ast
import io
import json
import re
from pathlib import Path
from uuid import uuid4
from datetime import datetime, timezone
from threading import Lock

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, Field, field_validator
from backend.registry import BASE, connect, get_project, PROJECT_PATTERN, WORKFLOW_PATTERN

HEADERS = ['Module', 'Process', 'Test Scenario', 'Test case ID', 'Test case',
           'Pre condition', 'Test Steps', 'Expected Result', 'Actual Result',
           'Status (Pass/Fail)', 'Positive/Negative']

SUITE_LOCK = Lock()
TAG = re.compile(r'^[A-Za-z][A-Za-z0-9 _&/().-]{0,79}$')
CASE_ID = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$')


def init_suite_db():
    with connect() as db:
        db.execute('''CREATE TABLE IF NOT EXISTS module_catalog (
          project_id TEXT NOT NULL, workflow_name TEXT NOT NULL,
          module TEXT NOT NULL, process TEXT NOT NULL,
          PRIMARY KEY(project_id,workflow_name))''')
        db.execute('''CREATE TABLE IF NOT EXISTS module_scripts (
          project_id TEXT NOT NULL, filename TEXT NOT NULL,
          module TEXT NOT NULL, process TEXT NOT NULL,
          analyzed_at TEXT NOT NULL, summary TEXT NOT NULL,
          PRIMARY KEY(project_id,filename))''')
        db.execute('''CREATE TABLE IF NOT EXISTS module_cases (
          project_id TEXT NOT NULL, testcase_id TEXT NOT NULL,
          module TEXT NOT NULL, process TEXT NOT NULL, scenario TEXT NOT NULL,
          title TEXT NOT NULL, precondition TEXT NOT NULL, steps TEXT NOT NULL,
          expected TEXT NOT NULL, actual TEXT NOT NULL DEFAULT '',
          status TEXT NOT NULL DEFAULT 'NOT RUN', polarity TEXT NOT NULL,
          category TEXT NOT NULL DEFAULT 'General',
          workflow_name TEXT NOT NULL DEFAULT '', approved INTEGER NOT NULL DEFAULT 0,
          updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          PRIMARY KEY(project_id,testcase_id))''')
        db.execute('''CREATE TABLE IF NOT EXISTS module_runs (
          id INTEGER PRIMARY KEY AUTOINCREMENT, project_id TEXT NOT NULL,
          status TEXT NOT NULL, selected_modules TEXT NOT NULL,
          selected_processes TEXT NOT NULL, started_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
          ended_at TEXT)''')
        db.execute('''CREATE TABLE IF NOT EXISTS module_results (
          id INTEGER PRIMARY KEY AUTOINCREMENT, run_id INTEGER NOT NULL,
          project_id TEXT NOT NULL, testcase_id TEXT NOT NULL, workflow_name TEXT NOT NULL,
          status TEXT NOT NULL, actual TEXT NOT NULL, screenshot TEXT,
          trace TEXT, report_path TEXT, executed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)''')


def valid_tag(s, key):
    value = str(s or '').strip()
    if not TAG.fullmatch(value):
        raise ValueError(f'{key} must be 1-80 characters: letters, digits, spaces or - _ & / ( ) .')
    return value


class CatalogLink(BaseModel):
    module: str
    process: str

    @field_validator('module', 'process')
    @classmethod
    def check(cls,v): return valid_tag(v, 'Module/process')


class ApprovalInput(BaseModel):
    project_id: str
    testcase_ids: list[str] = Field(min_length=1, max_length=500)
    approve: bool = True


class RunSuiteInput(BaseModel):
    project_id: str
    modules: list[str] = Field(min_length=1, max_length=30)
    processes: list[str] = Field(default_factory=list, max_length=70)
    testcase_ids: list[str] = Field(default_factory=list, max_length=500)
    allow_test_transactions: bool = False


def catalog(project_id):
    if not get_project(project_id): raise ValueError('Unknown ERP project')
    with connect() as db:
        rows = db.execute('''SELECT w.project_id,w.name AS workflow_name,w.reviewed,w.step_count,
               COALESCE(c.module,'Unassigned') AS module,
               COALESCE(c.process,'Unassigned') AS process
               FROM workflows w LEFT JOIN module_catalog c
               ON c.project_id=w.project_id AND c.workflow_name=w.name
               WHERE w.project_id=? ORDER BY module,process,w.name''', (project_id,)).fetchall()
        scripts = db.execute('SELECT project_id,filename,module,process,analyzed_at,summary FROM module_scripts WHERE project_id=? ORDER BY filename',(project_id,)).fetchall()
    return {'workflows':[dict(r) for r in rows], 'scripts':[dict(r) for r in scripts]}


def link_workflow(project_id, workflow_name, module, process):
    if not WORKFLOW_PATTERN.fullmatch(workflow_name): raise ValueError('Invalid workflow name')
    module,process=valid_tag(module,'Module'),valid_tag(process,'Process')
    with connect() as db:
        if not db.execute('SELECT 1 FROM workflows WHERE project_id=? AND name=?',(project_id,workflow_name)).fetchone():
            raise ValueError('Record and save this workflow before assigning a module/process')
        db.execute('''INSERT INTO module_catalog(project_id,workflow_name,module,process)
                      VALUES(?,?,?,?) ON CONFLICT(project_id,workflow_name)
                      DO UPDATE SET module=excluded.module,process=excluded.process''',(project_id,workflow_name,module,process))
        # Never automatically approve cases when mapping changes.
        db.execute('''UPDATE module_cases SET approved=0,workflow_name='' WHERE project_id=?
                 AND workflow_name=? AND (module<>? OR process<>?)''', (project_id,workflow_name,module,process))
        inferred=_map_workflow(db,project_id,module,process)
        db.execute('''UPDATE module_cases SET workflow_name=?,approved=0
             WHERE project_id=? AND module=? AND process=? AND approved=0''',(inferred,project_id,module,process))
    return {'project_id':project_id,'workflow_name':workflow_name,'module':module,'process':process}


def script_metadata(content:bytes):
    if len(content)>250_000: raise ValueError('Script must be smaller than 250KB')
    try: source=content.decode('utf-8-sig')
    except UnicodeDecodeError as err: raise ValueError('Python script must be UTF-8') from err
    try: tree=ast.parse(source)
    except SyntaxError as err: raise ValueError(f'Invalid Python syntax at line {err.lineno}') from err
    actions=[]; methods={'click','fill','press','select_option','check','uncheck','goto','get_by_role','get_by_label','get_by_text','locator','expect','screenshot','assert_visible'}
    functions=[]
    for node in ast.walk(tree):
        if isinstance(node,(ast.FunctionDef,ast.AsyncFunctionDef)) and len(functions)<80:
            functions.append(node.name)
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            name=node.func.attr
            if name in methods and len(actions)<120: actions.append(name)
    return {'functions':functions,'actions':actions,'action_count':len(actions),'line_count':len(source.splitlines()),
            'has_login_like_steps':any('login' in n.lower() or 'sign_in' in n.lower() for n in functions),
            'note':'Static AST scan only. Uploaded Python will NOT run automatically or attach to your browser. Convert/review as a JSON workflow.'}


def save_script(project_id, filename, module, process, raw):
    if not get_project(project_id): raise ValueError('Unknown ERP project')
    module,process=valid_tag(module,'Module'),valid_tag(process,'Process')
    if filename != Path(filename).name or '\\' in filename:
        raise ValueError('Script filenames cannot include paths')
    filename=Path(filename).name
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\.py',filename):
        raise ValueError('Use a simple .py filename without paths or spaces')
    metadata=script_metadata(raw)
    dest=BASE/'uploaded_scripts'/project_id
    dest.mkdir(parents=True,exist_ok=True)
    # Never overwrite another script; version by assigned stable unique name.
    stored=f'{uuid4().hex[:8]}_{filename}'
    (dest/stored).write_bytes(raw)
    with connect() as db:
        db.execute('''INSERT INTO module_scripts(project_id,filename,module,process,analyzed_at,summary)
                     VALUES(?,?,?,?,?,?)''',(project_id,stored,module,process,
                         datetime.now(timezone.utc).isoformat(), json.dumps(metadata)))
    return {'project_id':project_id,'stored_filename':stored,'module':module,'process':process,'analysis':metadata}


def infer_category(row):
    s=(row.get('Test Scenario','')+' '+row.get('Test case','')).lower()
    if any(x in s for x in ('role','permission','authorization','access','manager')): return 'Role-based'
    if any(x in s for x in ('boundary','limit','minimum','maximum','above','below','zero')): return 'Boundary'
    return 'Positive' if row.get('Positive/Negative','Positive')=='Positive' else 'Negative'


def _safe_cell(value):
    if value is None: return ''
    if not isinstance(value,(str,int,float,bool)): raise ValueError('Dates and formulas are not allowed in testcase fields')
    value=str(value).strip()
    if len(value)>2000: raise ValueError('Testcase cell exceeds 2000 characters')
    return value


def _map_workflow(db,project_id,module,process):
    found=db.execute('''SELECT c.workflow_name FROM module_catalog c JOIN workflows w
           ON w.project_id=c.project_id AND w.name=c.workflow_name
           WHERE c.project_id=? AND c.module=? AND c.process=?''',(project_id,module,process)).fetchall()
    return found[0]['workflow_name'] if len(found)==1 else ''


def cases(project_id):
    if not get_project(project_id): raise ValueError('Unknown ERP project')
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM module_cases WHERE project_id=? ORDER BY module,process,testcase_id',(project_id,)).fetchall()]


def import_excel(project_id,content:bytes):
    if not get_project(project_id): raise ValueError('Unknown ERP project')
    if len(content)>4_000_000: raise ValueError('Excel file too large (max 4 MB)')
    try: book=load_workbook(io.BytesIO(content),read_only=True,data_only=False)
    except Exception as err: raise ValueError('Invalid .xlsx workbook') from err
    if 'Test Cases' not in book: raise ValueError('Expected worksheet named Test Cases')
    sheet=book['Test Cases']
    if sheet.max_row>2001: raise ValueError('Maximum 2000 test cases per upload')
    if [_safe_cell(c.value) for c in sheet[1][:11]] != HEADERS:
        raise ValueError('Excel headers must match the 11 required columns in their exact order')
    metadata={}
    if 'Execution Map' in book:
        for cells in list(book['Execution Map'].iter_rows(min_row=2,values_only=True))[:2000]:
            if cells[0]:
                metadata[_safe_cell(cells[0])]={
                    'workflow':_safe_cell(cells[1] if len(cells)>1 else ''),
                    'category':_safe_cell(cells[2] if len(cells)>2 else '')}
    parsed=[]; observed=set()
    for cells in sheet.iter_rows(min_row=2,max_col=11,values_only=True):
        if not any(c is not None and str(c).strip() for c in cells): continue
        if any(isinstance(v,str) and v.startswith('=') for v in cells):
            raise ValueError('Excel formulas are not accepted as testcase data')
        item=dict(zip(HEADERS,[_safe_cell(v) for v in cells]))
        ident=item['Test case ID']
        if not CASE_ID.fullmatch(ident) or ident in observed:
            raise ValueError(f'Invalid or duplicate Test case ID: {ident!r}')
        observed.add(ident)
        item['Module']=valid_tag(item['Module'],'Module')
        item['Process']=valid_tag(item['Process'],'Process')
        if not item['Test Scenario'] or not item['Test case'] or not item['Expected Result']:
            raise ValueError(f'{ident}: Test Scenario, Test case, and Expected Result are required')
        if item['Positive/Negative'].lower() not in ('positive','negative'):
            raise ValueError(f'{ident}: Positive/Negative must be Positive or Negative')
        item['Positive/Negative']=item['Positive/Negative'].capitalize()
        parsed.append(item)
    if not parsed: raise ValueError('No testcase rows found')
    with connect() as db:
        for item in parsed:
            ident=item['Test case ID']; meta=metadata.get(ident,{})
            found=_map_workflow(db,project_id,item['Module'],item['Process'])
            specified=meta.get('workflow','')
            if specified:
                matches=db.execute('''SELECT 1 FROM module_catalog WHERE project_id=? AND workflow_name=? AND module=? AND process=?''',
                    (project_id,specified,item['Module'],item['Process'])).fetchone()
                found=specified if matches else ''
            category=meta.get('category') or infer_category(item)
            if category not in ('Positive','Negative','Boundary','Role-based','General'): category=infer_category(item)
            db.execute('''INSERT INTO module_cases(project_id,testcase_id,module,process,scenario,title,
                precondition,steps,expected,actual,status,polarity,category,workflow_name,approved)
                VALUES(?,?,?,?,?,?,?,?,?,'','NOT RUN',?,?,?,0)
                ON CONFLICT(project_id,testcase_id) DO UPDATE SET module=excluded.module,
                process=excluded.process,scenario=excluded.scenario,title=excluded.title,
                precondition=excluded.precondition,steps=excluded.steps,expected=excluded.expected,
                actual='',status='NOT RUN',polarity=excluded.polarity,category=excluded.category,
                workflow_name=excluded.workflow_name,approved=0,updated_at=CURRENT_TIMESTAMP''',
                (project_id,ident,item['Module'],item['Process'],item['Test Scenario'],item['Test case'],
                item['Pre condition'],item['Test Steps'],item['Expected Result'],item['Positive/Negative'],category,found))
    book.close()
    return {'imported':len(parsed),'approval_reset':True,'note':'All uploaded cases require review and approval. Uploaded Pass/Fail values are ignored.'}


def workbook(project_id=None, template=False):
    if project_id and not get_project(project_id): raise ValueError('Unknown ERP project')
    wb=Workbook(); ws=wb.active; ws.title='Test Cases'
    ws.append(HEADERS)
    examples = [] if not template else [
      ['Procurement','Purchase Requisition','Positive - valid submission','ERP-TC-001','Submit valid purchase requisition','Approved test ERP and authenticated role','Enter valid values; submit','Saved record and approved status verified','','','Positive'],
      ['Procurement','Purchase Requisition','Boundary - above max','ERP-TC-002','Reject quantity over configured limit','Maximum approved business rule available','Enter an out-of-range quantity','Validation error appears; nothing submitted','','','Negative']]
    if template: examples=[]  # Keep templates empty so sample cases cannot be accidentally executed.
    if not template and project_id:
        for c in cases(project_id):
            ws.append([c['module'],c['process'],c['scenario'],c['testcase_id'],c['title'],
                c['precondition'],c['steps'],c['expected'],c['actual'],c['status'] if c['status']!='NOT RUN' else '',c['polarity']])
    meta=wb.create_sheet('Execution Map')
    meta.append(['Test case ID','Linked approved workflow','Scenario Category','Approval Status','Important note'])
    if not template and project_id:
        for c in cases(project_id):
            meta.append([c['testcase_id'],c['workflow_name'],c['category'], 'Approved' if c['approved'] else 'Needs Review',
                         'Approval is controlled in the dashboard, not by Excel edits'])
    if not template and project_id:
        with connect() as db:
            histories=[dict(r) for r in db.execute('SELECT * FROM module_runs WHERE project_id=? ORDER BY id DESC LIMIT 1000',(project_id,)).fetchall()]
            results=[dict(r) for r in db.execute('SELECT * FROM module_results WHERE project_id=? ORDER BY id DESC LIMIT 2000',(project_id,)).fetchall()]
        sh=wb.create_sheet('Run History')
        sh.append(['Run ID','Overall Status','Selected Modules','Selected Processes','Started At','Ended At'])
        for r in histories:
            sh.append([r['id'],r['status'],r['selected_modules'],r['selected_processes'],r['started_at'],r['ended_at']])
        sh2=wb.create_sheet('Execution Results')
        sh2.append(['Run ID','Test case ID','Workflow','Status','Actual Result','Screenshot Path','Trace Path','Executed At'])
        for r in results:
            sh2.append([r['run_id'],r['testcase_id'],r['workflow_name'],r['status'],r['actual'],r['screenshot'],r['trace'],r['executed_at']])
        for shx in (sh,sh2):
            shx.sheet_view.showGridLines=False
            shx.freeze_panes='B2'
            shx.auto_filter.ref=shx.dimensions
            for c in shx[1]:
                c.fill=PatternFill('solid',fgColor='133E4C');c.font=Font(bold=True,color='FFFFFF');c.alignment=Alignment(wrap_text=True)
            for col in range(1,shx.max_column+1):
                shx.column_dimensions[__import__('openpyxl').utils.get_column_letter(col)].width=26 if col!=5 else 70
    guide=wb.create_sheet('Read Me')
    guide.append(['Smart ERP QA - Test case spreadsheet'])
    for line in [
        'Keep the 11 Test Cases headers exactly as provided.',
        'Only Positive or Negative belongs in Positive/Negative. Boundary and Role-based are Scenario Category in Execution Map.',
        'Actual Result and Status are filled by real automation. Uploaded values are discarded.',
        'Review and approve test cases in the dashboard after importing.',
        'Executable test cases must map to a reviewed Smart ERP workflow; pasted manual steps are not automatically executable.',
        'Never put credentials or secrets into test cases or uploaded scripts.']:
        guide.append([line])
    ws.freeze_panes='E2';ws.sheet_view.showGridLines=False
    widths=[20,27,38,19,48,45,60,55,50,22,20]
    for idx,w in enumerate(widths,1): ws.column_dimensions[__import__('openpyxl').utils.get_column_letter(idx)].width=w
    for sheet in (ws,meta):
        sheet.sheet_view.showGridLines=False
        for cell in sheet[1]:
            cell.fill=PatternFill('solid',fgColor='133E4C');cell.font=Font(name='Calibri',size=11,bold=True,color='FFFFFF')
            cell.alignment=Alignment(wrap_text=True,vertical='center')
        sheet.row_dimensions[1].height=30
        sheet.auto_filter.ref=sheet.dimensions
    for col,w in [('A',20),('B',30),('C',22),('D',20),('E',62)]:meta.column_dimensions[col].width=w
    guide.column_dimensions['A'].width=115
    guide['A1'].font=Font(bold=True,size=16,color='0C6B5A')
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment=Alignment(wrap_text=True,vertical='top')
            cell.font=Font(name='Calibri',size=10,color='1D4770' if cell.column in (1,2,3,4,5,6,7,8,11) else '276749')
        ws.row_dimensions[row[0].row].height=41
    pol=DataValidation(type='list',formula1='"Positive,Negative"',allow_blank=False)
    ws.add_data_validation(pol);pol.add('K2:K2001')
    buffer=io.BytesIO();wb.save(buffer);return buffer.getvalue()


def approve_cases(data:ApprovalInput):
    if not get_project(data.project_id):raise ValueError('Unknown ERP project')
    if not all(CASE_ID.fullmatch(v) for v in data.testcase_ids):raise ValueError('Invalid testcase ID')
    with connect() as db:
        for ident in data.testcase_ids:
            row=db.execute('SELECT * FROM module_cases WHERE project_id=? AND testcase_id=?',(data.project_id,ident)).fetchone()
            if not row:raise ValueError(f'{ident}: testcase not found')
            if data.approve:
                if not row['workflow_name']:raise ValueError(f'{ident}: assign exactly one existing workflow to this module/process')
                workflow=db.execute('''SELECT reviewed FROM workflows WHERE project_id=? AND name=?''',
                                   (data.project_id,row['workflow_name'])).fetchone()
                if not workflow or not workflow['reviewed']:raise ValueError(f'{ident}: linked workflow is not approved')
        for ident in data.testcase_ids:
            db.execute('UPDATE module_cases SET approved=? WHERE project_id=? AND testcase_id=?',
                       (int(data.approve),data.project_id,ident))
    return {'updated':len(data.testcase_ids),'approved':data.approve}


def plan_cases(data:RunSuiteInput):
    if not get_project(data.project_id):raise ValueError('Unknown ERP project')
    modules=[valid_tag(v,'Module') for v in data.modules]
    processes=[valid_tag(v,'Process') for v in data.processes]
    if len(modules)!=len(set(modules)) or len(processes)!=len(set(processes)):
        raise ValueError('Duplicate module/process selection')
    candidates=[c for c in cases(data.project_id) if c['module'] in modules and
                (not processes or c['process'] in processes)]
    if not data.testcase_ids:
        candidates=[c for c in candidates if c['approved']]
    if data.testcase_ids:
        selected=set(data.testcase_ids)
        if len(selected)!=len(data.testcase_ids): raise ValueError('Duplicate testcase ID')
        candidates=[c for c in candidates if c['testcase_id'] in selected]
        if {c['testcase_id'] for c in candidates}!=selected:
            raise ValueError('Some selected cases do not belong to the selected modules/processes')
    if not candidates:raise ValueError('No approved test cases match the selected modules/processes')
    if any(not c['approved'] for c in candidates):
        raise ValueError('Selection includes draft/unapproved test cases. Approve or deselect them first.')
    if any(not c['workflow_name'] for c in candidates):
        raise ValueError('Some cases have no reviewed workflow mapping')
    return candidates


def run_totals(project_id):
    with connect() as db:
        base=db.execute('''SELECT status,COUNT(*) AS n FROM module_cases WHERE project_id=?
             GROUP BY status''',(project_id,)).fetchall()
        recent=[dict(r) for r in db.execute('''SELECT * FROM module_results WHERE project_id=? ORDER BY id DESC LIMIT 25''',(project_id,)).fetchall()]
        history=[dict(r) for r in db.execute('''SELECT * FROM module_runs WHERE project_id=? ORDER BY id DESC LIMIT 20''',(project_id,)).fetchall()]
    stats={r['status']:r['n'] for r in base}
    return {'total':sum(stats.values()),'passed':stats.get('PASSED',0),
            'failed':stats.get('FAILED',0),'blocked':stats.get('BLOCKED',0),
            'not_run':stats.get('NOT RUN',0),'recent':recent,'history':history}


def create_run(data:RunSuiteInput):
    with connect() as db:
        cur=db.execute('''INSERT INTO module_runs(project_id,status,selected_modules,selected_processes)
            VALUES(?,?,?,?)''',(data.project_id,'RUNNING',json.dumps(data.modules),json.dumps(data.processes)))
        return cur.lastrowid


def save_case_result(run_id,project_id,case,report):
    status=report['status']; actual=str(report.get('message',''))[:2000]
    with connect() as db:
        db.execute('''UPDATE module_cases SET status=?, actual=?, updated_at=CURRENT_TIMESTAMP
                     WHERE project_id=? AND testcase_id=?''',(status,actual,project_id,case['testcase_id']))
        db.execute('''INSERT INTO module_results(run_id,project_id,testcase_id,workflow_name,status,actual,screenshot,trace,report_path)
                     VALUES(?,?,?,?,?,?,?,?,?)''',(run_id,project_id,case['testcase_id'],case['workflow_name'],status,actual,
                          report.get('screenshot'),report.get('trace'),report.get('report_path')))


def complete_run(run_id,status):
    with connect() as db:
        db.execute('UPDATE module_runs SET status=?,ended_at=CURRENT_TIMESTAMP WHERE id=?',(status,run_id))


def batch_results(run_id):
    with connect() as db:
        return [dict(r) for r in db.execute('SELECT * FROM module_results WHERE run_id=? ORDER BY id',(run_id,)).fetchall()]


def propose_from_uploaded_script(project_id,filename,provider='rules',model=None):
    """Create non-executable drafts from a sanitized AST summary, never raw code."""
    import os
    import httpx
    with connect() as db:
        row=db.execute('SELECT * FROM module_scripts WHERE project_id=? AND filename=?',(project_id,filename)).fetchone()
    if not row: raise ValueError('Unknown analyzed script')
    summary=json.loads(row['summary'])
    categories=['Positive','Negative','Boundary','Role-based']
    proposals=[
        {'category':'Positive','title':'Valid business workflow','expectation':'Verify approved postconditions; do not assume clicks mean the ERP saved a record','polarity':'Positive'},
        {'category':'Negative','title':'Required-field validation','expectation':'With a verified mandatory field left blank, confirm no record is saved','polarity':'Negative'},
        {'category':'Boundary','title':'Approved minimum and maximum values','expectation':'Confirm handling of values at, below, and above the approved business limits','polarity':'Negative'},
        {'category':'Role-based','title':'Authorized and unauthorized access','expectation':'Verify the operation with approved role accounts and expected permission outcomes','polarity':'Negative'},
    ]
    if provider not in ('rules','openai','ollama'):raise ValueError('Provider must be rules, openai, or ollama')
    if provider!='rules':
        if model and not re.fullmatch(r'[A-Za-z0-9._:/-]{1,80}',model):raise ValueError('Invalid model')
        prompt=("Propose exactly 4 SAFE ERP QA testcase DRAFTS (Positive,Negative,Boundary,Role-based). "
            "Do not invent business limits or claims of execution. Return JSON array of objects with keys "
            "category,title,expectation,polarity. polarity must be Positive or Negative. "
            "Use only this sanitized Python AST metadata (no code, values, URLs, selectors): "
            + json.dumps({'functions':[f for f in summary['functions'] if not any(x in f.lower() for x in ('password','secret','token'))][:20],
                          'actions':summary['actions'][:50]}))
        try:
            if provider=='openai':
                key=os.environ.get('OPENAI_API_KEY','')
                if not key:raise ValueError('OPENAI_API_KEY is not configured')
                response=httpx.post('https://api.openai.com/v1/chat/completions',
                    headers={'Authorization':'Bearer '+key},
                    json={'model':model or os.environ.get('SMART_ERP_OPENAI_MODEL','gpt-4o-mini'),
                          'messages':[{'role':'user','content':prompt}],
                          'response_format':{'type':'json_object'}},timeout=35.0)
                response.raise_for_status();content=response.json()['choices'][0]['message']['content']
            else:
                endpoint=os.environ.get('SMART_ERP_OLLAMA_URL','http://127.0.0.1:11434/api/generate')
                if endpoint not in ('http://127.0.0.1:11434/api/generate',
                                    'http://host.docker.internal:11434/api/generate'):
                    raise ValueError('Ollama URL must target local computer or Docker host on port 11434')
                response=httpx.post(endpoint,
                    json={'model':model or os.environ.get('SMART_ERP_OLLAMA_MODEL','llama3.2'),
                          'prompt':prompt+' Wrap the array as {"cases":[...]}.','format':'json','stream':False},timeout=90.0)
                response.raise_for_status();content=response.json()['response']
            doc=json.loads(content)
            proposed=doc.get('cases',[]) if isinstance(doc,dict) else []
            validated=[]
            for p in proposed[:12]:
                if not isinstance(p,dict):continue
                cat=p.get('category')
                if cat not in categories:continue
                title=str(p.get('title','')).strip()[:160]
                expectation=str(p.get('expectation','')).strip()[:400]
                polarity=p.get('polarity','Positive' if cat=='Positive' else 'Negative')
                if len(title)<3 or len(expectation)<5 or polarity not in ('Positive','Negative'):continue
                validated.append({'category':cat,'title':title,'expectation':expectation,'polarity':polarity})
            if not validated:raise ValueError('AI returned no valid case proposals')
            proposals=validated
        except (httpx.HTTPError,KeyError,TypeError,json.JSONDecodeError) as err:
            raise ValueError(f'{provider} did not return valid testcase suggestions: {type(err).__name__}') from err
    stored=[]
    with connect() as db:
        linked=_map_workflow(db,project_id,row['module'],row['process'])
        for p in proposals:
            ident='AI-'+uuid4().hex[:12].upper()
            db.execute('''INSERT INTO module_cases(project_id,testcase_id,module,process,scenario,title,
                precondition,steps,expected,actual,status,polarity,category,workflow_name,approved)
                VALUES(?,?,?,?,?,?,?,?,?,'','NOT RUN',?,?,?,0)''',
                (project_id,ident,row['module'],row['process'],p['category']+' - '+p['title'],p['title'],
                 'Authorized TEST/STAGING ERP and approved business rules required',
                 'Draft: QA reviewer must supply concrete inputs, steps and assertions',
                 p['expectation'],p['polarity'],p['category'],linked))
            stored.append(ident)
    return {'provider':provider,'draft_ids':stored,'note':'Drafts only. Review business rules, add executable assertions, and approve in dashboard before running.'}
