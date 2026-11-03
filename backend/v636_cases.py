"""Local-only, explicitly mapped Excel/manual test case catalog for the v6.3.6 app.
No spreadsheet values or text are ever compiled or executed as Python.
"""
from __future__ import annotations
import io
import json
import os
import re
from pathlib import Path
from threading import RLock
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import Response
from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.worksheet.datavalidation import DataValidation
from pydantic import BaseModel, Field
from backend.registry import BASE
from backend import leocem_quickrun as leocem, script_workspace as sw

NEGATIVE_SCRIPT_ID = 'procurement/v636_pi_po_negative.py'

ACTIONS = {
    'login_only': ('Login only', 'Verify the Leocem navigation after login; no new ERP record.'),
    'pi_creation': ('Purchase Indent creation', 'Login, create and submit one PI, then stop. Creates a transaction.'),
    'pi_approvals': ('PI creation and approvals', 'Create the PI, perform the three saved approval stages, then stop.'),
    'lpo_creation': ('Create LPO', 'Create and approve PI prerequisites, create LPO, then stop.'),
    'full_flow': ('Full PI to GRN', 'Run the full original PI -> approvals -> LPO -> GRN workflow.'),
}
NEGATIVE_ACTIONS = {
    'neg_login_all': ('Login negative tests', 'Blank username and blank password login validations; no password guessing.'),
    'neg_login_blank_username': ('Login: missing username', 'Verify a blank username cannot authenticate.'),
    'neg_login_blank_password': ('Login: missing password', 'Verify a blank password cannot authenticate.'),
    'neg_pi_all': ('All PI negative tests', 'Unsaved PI form: invalid quantities and missing department.'),
    'neg_pi_zero': ('PI: zero quantity', 'Open unsaved PI form and verify zero quantity is rejected.'),
    'neg_pi_negative': ('PI: negative quantity', 'Open unsaved PI form and verify negative quantity is rejected.'),
    'neg_pi_empty': ('PI: empty quantity', 'Open unsaved PI form and verify missing quantity is rejected.'),
    'neg_pi_alpha': ('PI: alphabetic quantity', 'Open unsaved PI form and verify nonnumeric quantity is rejected.'),
    'neg_pi_missing_department': ('PI: missing department', 'Observe required-field validation without saving PI.'),
    'neg_pi_approval_guard': ('PI Approval: no selected record', 'Read-only UI check that Approve cannot be used without selecting a PI.'),
    'neg_po_all': ('All LPO negative field tests', 'Unsaved LPO form: missing PI, vendor, number, nonnumeric number and zero quantity.'),
    'neg_po_missing_pi': ('LPO: missing PI', 'Verify missing PI is rejected on the unsaved LPO form.'),
    'neg_po_missing_vendor': ('LPO: missing vendor', 'Verify missing vendor is rejected on the unsaved LPO form.'),
    'neg_po_blank_number': ('LPO: blank number', 'Verify blank PO number is rejected on the unsaved LPO form.'),
    'neg_po_alpha_number': ('LPO: alphabetic number', 'Verify alphabetic PO number is rejected or sanitized.'),
    'neg_po_zero_qty': ('LPO: zero item quantity', 'Check zero LPO quantity only with a configured approved test PI.'),
    'neg_all': ('Negative Login through LPO suite', 'Run Login, PI, PI approval guard and LPO UI checks, with no document Save/Submit/Approve.'),
}
ALL_ACTIONS = {**ACTIONS, **NEGATIVE_ACTIONS}
HEADERS = ['Module' ,'Process','Test Scenario','Test case ID','Test case','Pre condition','Test Steps',
           'Expected Result','Actual Result','Status (Pass/Fail)','Positive/Negative','Automation Action ID']
CATALOG_PATH = BASE / 'data' / 'v636_user_cases.json'
_lock = RLock()
ID_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9_-]{1,59}$')

SEED = [
    ('LEO-TC-001','Authentication','Login to Leocem', '1. Open the configured test URL\n2. Login using saved script\n3. Verify navigation/sidebar visible','Authenticated ERP navigation/sidebar visible', 'login_only'),
    ('LEO-TC-002','Purchase Indent','Create Purchase Indent','1. Login\n2. Open Purchase Indent Creation\n3. Fill saved test data and submit PI\n4. Check generated PI detail','New PI identified and shown; final submission status may require review','pi_creation'),
    ('LEO-TC-003','Purchase Indent','Approve Purchase Indent','1. Create PI\n2. Approve with configured roles\n3. Stop after PI approvals','Saved PI approval actions complete; final persisted statuses to be reviewed','pi_approvals'),
    ('LEO-TC-004','Local Purchase Order','Create LPO','1. Create PI\n2. Perform required PI approvals\n3. Create and save LPO','LPO creation completed; final persisted status requires review','lpo_creation'),
    ('LEO-TC-005','Procurement','PI to GRN full workflow','1. Login\n2. PI create and approve\n3. LPO create and approve\n4. GRN create and submit','Workflow reaches GRN submission; final ERP status to be reviewed','full_flow'),
]
NEGATIVE_SEED = [
    ('LEO-NEG-AUTH-001', 'Authentication', 'Login with blank username', '1. Open login page\n2. Leave username blank\n3. Attempt Login once\n4. Observe explicit validation', 'Empty username must not authenticate', 'neg_login_blank_username'),
    ('LEO-NEG-AUTH-002', 'Authentication', 'Login with blank password', '1. Open login page\n2. Enter permitted test username\n3. Leave password blank\n4. Attempt Login once', 'Empty password must not authenticate', 'neg_login_blank_password'),
    ('LEO-NEG-PI-001', 'Purchase Indent', 'PI zero quantity should be rejected', '1. Login to authorized staging ERP\n2. Open unsaved PI form\n3. Enter zero item quantity\n4. Observe validation without document Save', 'ERP rejects zero PI quantity before saving', 'neg_pi_zero'),
    ('LEO-NEG-PI-002', 'Purchase Indent', 'PI negative quantity should be rejected', '1. Login\n2. Open unsaved PI form\n3. Enter quantity -1\n4. Observe validation without Save', 'ERP rejects negative PI quantity', 'neg_pi_negative'),
    ('LEO-NEG-PI-003', 'Purchase Indent', 'PI empty quantity should be rejected', '1. Login\n2. Open unsaved PI form\n3. Leave quantity empty\n4. Observe validation', 'ERP requires PI item quantity', 'neg_pi_empty'),
    ('LEO-NEG-PI-004', 'Purchase Indent', 'PI alphabetic quantity should be rejected', '1. Login\n2. Open unsaved PI form\n3. Enter abc in quantity\n4. Observe validation', 'ERP rejects nonnumeric PI quantity', 'neg_pi_alpha'),
    ('LEO-NEG-PI-005', 'Purchase Indent', 'PI missing department', '1. Login\n2. Open unsaved PI Creation form\n3. Leave department empty\n4. Observe field validation before Save', 'Department is required before PI creation', 'neg_pi_missing_department'),
    ('LEO-NEG-PI-006', 'PI Approval', 'Approve without selecting PI', '1. Login with PI approval test role\n2. Open PI Approval list\n3. Do not select any record\n4. Verify no enabled Approve action', 'Approve action is unavailable until a PI is selected', 'neg_pi_approval_guard'),
    ('LEO-NEG-PO-001', 'Local Purchase Order', 'LPO missing Purchase Indent', '1. Login with authorized PO test role\n2. Open unsaved LPO\n3. Leave Purchase Indent blank\n4. Observe validation', 'ERP requires a Purchase Indent', 'neg_po_missing_pi'),
    ('LEO-NEG-PO-002', 'Local Purchase Order', 'LPO missing vendor', '1. Login with PO test role\n2. Open unsaved LPO\n3. Leave vendor blank\n4. Observe validation', 'ERP requires vendor', 'neg_po_missing_vendor'),
    ('LEO-NEG-PO-003', 'Local Purchase Order', 'LPO blank PO number', '1. Login\n2. Open unsaved LPO\n3. Clear PO number\n4. Observe validation', 'ERP requires PO number', 'neg_po_blank_number'),
    ('LEO-NEG-PO-004', 'Local Purchase Order', 'LPO alphabetic PO number', '1. Login\n2. Open unsaved LPO\n3. Enter abc in PO number\n4. Observe validation', 'ERP rejects alphabetic PO number', 'neg_po_alpha_number'),
    ('LEO-NEG-PO-005', 'Local Purchase Order', 'LPO zero line quantity', '1. Configure approved staging PI\n2. Login\n3. Open unsaved LPO with approved test PI\n4. Enter zero quantity', 'ERP rejects zero LPO line quantity', 'neg_po_zero_qty'),
]

def seed_negative(item):
    item_positive=seed_case(item)
    item_positive['category']='Negative'
    return item_positive

def seed_case(item):
    cid, module, title, steps, expected, action = item
    return {'testcase_id':cid,'module':module,'process':module,'scenario':title,'title':title,
            'precondition':'Authorized Leocem TEST/STAGING URL and existing script login',
            'steps':steps,'expected':expected,'category':'Positive','action':action,'source':'example'}

def read_cases():
    with _lock:
        seeds = [seed_case(item) for item in SEED] + [seed_negative(item) for item in NEGATIVE_SEED]
        if not CATALOG_PATH.exists(): return seeds
        saved = json.loads(CATALOG_PATH.read_text(encoding='utf-8'))
        existing_ids = {item['testcase_id'] for item in saved}
        return saved + [item for item in seeds if item['testcase_id'] not in existing_ids]

def save_cases(items):
    with _lock:
        CATALOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        temp=CATALOG_PATH.with_suffix('.tmp')
        temp.write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
        temp.replace(CATALOG_PATH)

def cellstr(v, size=2000):
    return str(v or '').strip()[:size]

def suggest(title, steps, category='Positive'):
    """Conservative mapping only. Unknown or ambiguous actions require human coding."""
    q=(' '.join([title, steps])).lower()
    if not q.strip():return ''
    if category == 'Negative':
        if re.search(r'\b(delete|submit|save)\b', q):return ''
        # 'Login' occurs as a prerequisite in many PI/PO test steps. Only map
        # authentication negatives when the *test itself* targets login fields.
        auth_focus = ('username' in q or 'password' in q or
                      (('login' in title.lower() or 'authentication' in title.lower())
                       and not any(x in q for x in ('indent','lpo','purchase order','approval'))))
        if auth_focus:
            if 'username' in q and any(w in q for w in ('empty','blank','missing','required')):return 'neg_login_blank_username'
            if 'password' in q and any(w in q for w in ('empty','blank','missing','required')):return 'neg_login_blank_password'
            if any(w in q for w in ('all','suite')):return 'neg_login_all'
            return ''
        if 'approv' in q and ('without' in q or 'no selected' in q or 'not selected' in q):
            return 'neg_pi_approval_guard'
        po = any(w in q for w in ('lpo', 'purchase order', 'po ', 'po-', 'local po'))
        pi = any(w in q for w in ('indent', 'pi ', 'pi-'))
        if po and pi and ('all' in q or 'through' in q or 'suite' in q):return 'neg_all'
        if po:
            if 'vendor' in q and any(w in q for w in ('missing','blank','empty','required')):return 'neg_po_missing_vendor'
            if 'purchase indent' in q and any(w in q for w in ('missing','blank','empty','required')):return 'neg_po_missing_pi'
            if ('number' in q or 'reference' in q or 'oldpono' in q) and any(w in q for w in ('alphabet','letter','abc','nonnumeric','non numeric')):return 'neg_po_alpha_number'
            if ('number' in q or 'reference' in q) and any(w in q for w in ('missing','blank','empty','required')):return 'neg_po_blank_number'
            if ('qty' in q or 'quantity' in q) and ('zero' in q or re.search(r'\b0\b', q)):return 'neg_po_zero_qty'
            if 'all' in q or 'suite' in q or 'negative' in q:return 'neg_po_all'
            return ''
        if pi:
            if 'department' in q and any(w in q for w in ('empty','blank','missing','required')):
                return 'neg_pi_missing_department'
            if ('qty' in q or 'quantity' in q):
                if 'zero' in q or re.search(r'\b0\b', q):return 'neg_pi_zero'
                if '-1' in q or 'below zero' in q or 'negative quantity' in q or 'negative qty' in q:return 'neg_pi_negative'
                if any(w in q for w in ('empty','blank','missing','required')):return 'neg_pi_empty'
                if any(w in q for w in ('alphabet','letter','abc','nonnumeric','non numeric')):return 'neg_pi_alpha'
            if 'all' in q or 'suite' in q:return 'neg_pi_all'
        return ''
    if any(w in q for w in ('negative','invalid','missing','blank','zero qty','0 qty','should reject','error case')):return ''
    if any(w in q for w in ('grn','goods receipt','end to end','end-to-end','full flow')):return 'full_flow' if 'grn' in q or 'full flow' in q or 'end to end' in q or 'end-to-end' in q else ''
    if any(w in q for w in ('lpo','local purchase order','purchase order','po creation','create po')):return 'lpo_creation' if not any(w in q for w in ('approve lpo','po approval','approve po')) else ''
    if 'indent' in q or re.search(r'\bpi\b',q):
        if any(w in q for w in ('approve','approval')):return 'pi_approvals'
        if any(w in q for w in ('create','creation','submit')):return 'pi_creation'
    if any(w in q for w in ('log in','login','sign in','authentication')):return 'login_only'
    return ''

def case_data(data,source='excel'):
    cid=cellstr(data.get('testcase_id'),60)
    if not ID_PATTERN.fullmatch(cid):raise ValueError('Each case needs a unique ID using letters, numbers, - or _.')
    action=cellstr(data.get('action'),80).lower()
    if action not in ALL_ACTIONS:action=''
    if action and ((cat_value := cellstr(data.get('category'),30).title()) not in ('Positive','Negative') or (action in NEGATIVE_ACTIONS) != (cat_value == 'Negative')):action=''
    cat=cellstr(data.get('category'),30).title()
    if cat not in ('Positive','Negative'):cat='Positive'
    return {'testcase_id':cid,'module':cellstr(data.get('module'),100),
            'process':cellstr(data.get('process'),100), 'scenario':cellstr(data.get('scenario'),180),
            'title':cellstr(data.get('title'),180),'precondition':cellstr(data.get('precondition')),
            'steps':cellstr(data.get('steps'),5000),'expected':cellstr(data.get('expected'),2000),
            'category':cat,'action':action,'source':source}

def to_xlsx(items):
    wb=Workbook();ws=wb.active;ws.title='Test Cases'
    ws.append(HEADERS)
    for item in items:
        ws.append([item.get(k,'') for k in ('module','process','scenario','testcase_id','title','precondition','steps','expected')] + ['', '', item.get('category','Positive'),item.get('action','')])
    ws.freeze_panes='D2';ws.sheet_view.showGridLines=False
    fills=['162D4D','EAF3FA']
    for cell in ws[1]:cell.fill=PatternFill('solid',fgColor=fills[0]);cell.font=Font(name='Aptos',bold=True,color='FFFFFF',size=11);cell.alignment=Alignment(wrap_text=True)
    widths=[20,23,31,18,32,46,65,65,28,23,19,25]
    for i,width in enumerate(widths,1):ws.column_dimensions[__import__('openpyxl').utils.get_column_letter(i)].width=width
    for row in ws.iter_rows(min_row=2):
        ws.row_dimensions[row[0].row].height=80
        for cell in row:
            cell.alignment=Alignment(wrap_text=True,vertical='top')
            cell.font=Font(name='Aptos',size=10,color='1758A7' if cell.column not in (9,10) else '697789')
    d=DataValidation(type='list',formula1='"Positive,Negative"',allow_blank=False);ws.add_data_validation(d);d.add('K2:K251')
    how=wb.create_sheet('How to use')
    for text in ['Smart ERP QA v6.3.6 - Excel test case runner','1. Download and edit Test Cases. Add new rows with unique IDs.','2. Upload Excel in Smart ERP QA - Test Case Report page.','3. Action IDs are allowlisted: '+', '.join(ALL_ACTIONS), '4. Typed/Excel steps are documentation, NEVER executable code.','5. Positive and Negative mapped cases may run after explicit review and confirmation.','6. Negative tests cover Login, PI, PI approval UI guard and LPO. No document Save/Submit/Approve.','7. Actual Result and Status are always generated by the real run, not imported from Excel.','8. Authorized TEST/STAGING ERP only; PI / PO actions can create records.','9. Approval/submit clicks alone do not prove persisted status.']:
        how.append([text]);how.column_dimensions['A'].width=125
    out=io.BytesIO();wb.save(out);return out.getvalue()

class ManualCase(BaseModel):
    testcase_id: str=Field(max_length=60)
    title: str=Field(min_length=3,max_length=180)
    steps: str=Field(min_length=3,max_length=5000)
    expected: str=Field(min_length=3,max_length=2000)
    action: str=Field(default='',max_length=80)
    category: str=Field(default='Positive',max_length=20)

class RunCase(BaseModel):
    testcase_id: str
    reviewed_source_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_trusted_code: bool=False
    acknowledge_test_transactions: bool=False

class NegativeLaunch(BaseModel):
    reviewed_sha256: str=Field(pattern=r'^[a-f0-9]{64}$')
    acknowledge_trusted_code: bool=False
    acknowledge_test_transactions: bool=False


def negative_readiness():
    config=leocem.readiness()
    issues=list(config.get('issues') or [])
    source=None
    try:
        source,_=sw.inspect_source(NEGATIVE_SCRIPT_ID)
        if not source['valid'] or not source.get('supports_negative'):
            issues.append('The saved reviewed negative PI/LPO script is not runnable.')
    except (OSError, ValueError) as exc:
        issues.append('Negative PI/LPO script unavailable: '+str(exc))
    return {'ready':not issues,'issues':issues,'script_id':NEGATIVE_SCRIPT_ID,'script':source,
            'url':config.get('url'),'environment':config.get('environment')}


def install(app, script_manager, controller):
    router=APIRouter(prefix='/api/v636-cases')

    @router.get('/catalog')
    def catalog():
        config=leocem.readiness()
        neg=negative_readiness()
        return {'cases':[dict(item, mapping=('Ready' if
                        (item['category']=='Positive' and item['action'] in ACTIONS and config['ready']) or
                        (item['category']=='Negative' and item['action'] in NEGATIVE_ACTIONS and neg['ready'])
                        else 'Needs mapping')) for item in read_cases()],
                'actions':[{'id':k,'title':v[0],'description':v[1],
                            'category':'Negative' if k in NEGATIVE_ACTIONS else 'Positive'}
                           for k,v in ALL_ACTIONS.items()],
                'ready':config['ready'],'issues':config['issues'],
                'negative_ready':neg['ready'],'negative_issues':neg['issues'],
                'negative_revision':(neg.get('script') or {}).get('sha256',''),
                'revision':(config.get('script') or {}).get('sha256','')}

    @router.get('/template')
    def template():
        return Response(to_xlsx(read_cases()),media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
                        headers={'Content-Disposition':'attachment; filename="Smart_ERP_QA_v636_Executable_Test_Cases.xlsx"'})

    @router.post('/upload')
    async def upload(file: UploadFile=File(...)):
        if not file.filename or not file.filename.lower().endswith('.xlsx'):raise HTTPException(400,'Upload an .xlsx file only.')
        blob=await file.read(2_000_001)
        if len(blob)>2_000_000:raise HTTPException(400,'Excel workbook must be smaller than 2MB.')
        try:
            wb=load_workbook(io.BytesIO(blob),read_only=True,data_only=True)
            if 'Test Cases' not in wb.sheetnames:raise ValueError('Workbook must contain a sheet named Test Cases.')
            ws=wb['Test Cases'];ws.reset_dimensions()
            rows=ws.iter_rows(values_only=True)
            header=[cellstr(v,90) for v in next(rows)]
            if header[:11] != HEADERS[:11]:raise ValueError('First 11 Test Cases columns must match the downloaded template.')
            pos={name:idx for idx,name in enumerate(header)}
            incoming=[]
            for i,row in enumerate(rows,2):
                if not any(cell is not None and str(cell).strip() for cell in row):continue
                if len(incoming)>=250:raise ValueError('Maximum 250 cases per upload.')
                get=lambda name: row[pos[name]] if name in pos and pos[name]<len(row) else ''
                item=case_data({'testcase_id':get('Test case ID'),'module':get('Module'),'process':get('Process'),
                                'scenario':get('Test Scenario'),'title':get('Test case'),'precondition':get('Pre condition'),
                                'steps':get('Test Steps'),'expected':get('Expected Result'),
                                'category':get('Positive/Negative'),'action':get('Automation Action ID')},'excel')
                if not item['title'] or not item['steps'] or not item['expected']:raise ValueError(f'Excel row {i}: Title, Test Steps and Expected Result are mandatory.')
                incoming.append(item)
            if not incoming:raise ValueError('No test cases found in workbook.')
            ids=[x['testcase_id'] for x in incoming]
            if len(ids)!=len(set(ids)):raise ValueError('Excel contains duplicate Test case IDs.')
            # Merge instead of deleting manually entered cases. Never take actual/status values from upload.
            old={item['testcase_id']:item for item in read_cases()}
            old.update({item['testcase_id']:item for item in incoming})
            save_cases(list(old.values()))
            return {'uploaded':len(incoming),'executable':sum(bool(i['action']) for i in incoming),
                    'needs_mapping':sum(not i['action'] for i in incoming),'cases':len(old)}
        except (ValueError,StopIteration,KeyError) as exc:
            raise HTTPException(400,str(exc)) from exc
        except Exception as exc:
            raise HTTPException(400,'Invalid XLSX workbook; use the downloaded template.') from exc

    @router.post('/manual')
    def manual(body: ManualCase):
        category=body.category.title()
        if category not in ('Positive','Negative'):raise HTTPException(400,'Category must be Positive or Negative.')
        proposed=suggest(body.title,body.steps,category)
        explicit=body.action.strip().lower()
        if explicit and explicit not in ALL_ACTIONS:raise HTTPException(400,'Unknown automation action.')
        if explicit and (explicit in NEGATIVE_ACTIONS) != (category=='Negative'):
            raise HTTPException(400,'The automation action does not match the selected Positive/Negative category.')
        if explicit and explicit!=proposed:
            raise HTTPException(400,'Selected action does not match the scenario wording. Review the scenario or ask for a new locator/script mapping.')
        item=case_data({'testcase_id':body.testcase_id,'module':'Custom scenario','process':'Leocem procurement',
                        'scenario':body.title,'title':body.title,'precondition':'Authorized test ERP and saved script login',
                        'steps':body.steps,'expected':body.expected,'category':category,'action':explicit},'manual')
        old={entry['testcase_id']:entry for entry in read_cases()}
        old[item['testcase_id']]=item
        save_cases(list(old.values()))
        return {'case':item,'proposed_action':proposed,'mapping':'Ready' if explicit else 'Needs mapping'}

    @router.post('/suggest')
    def suggestion(body: ManualCase):
        action=suggest(body.title,body.steps,body.category.title())
        return {'suggested_action':action,'description':ALL_ACTIONS[action][1] if action else 'No reviewed action matches this scenario. Add/approve Playwright steps first.'}

    @router.get('/negative-ready')
    def neg_ready():
        return negative_readiness()

    @router.post('/negative-run')
    def neg_run(body: NegativeLaunch):
        if not (body.acknowledge_trusted_code and body.acknowledge_test_transactions):
            raise HTTPException(400,'Review and authorize the negative TEST/STAGING script first.')
        neg=negative_readiness()
        if not neg['ready']:raise HTTPException(400,'Negative suite not ready: '+' '.join(neg['issues']))
        if neg['script']['sha256'] != body.reviewed_sha256:
            raise HTTPException(400,'Saved negative script changed. Refresh and review its revision.')
        try:
            cfg=leocem.readiness();project=leocem.ensure_project(cfg)
            request=sw.ScriptRunInput(project_id=project['id'],script_id=NEGATIVE_SCRIPT_ID,
                 reviewed_sha256=body.reviewed_sha256,mode='new',trust_local_code=True,
                 allow_test_transactions=True,positive_scenarios=False,negative_scenarios=True)
            return script_manager.start(request,controller)
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc

    @router.post('/run')
    def run(body: RunCase):
        selected=next((c for c in read_cases() if c['testcase_id']==body.testcase_id),None)
        if not selected:raise HTTPException(404,'Test Case ID not found in uploaded/manual catalog.')
        action=selected.get('action','')
        is_neg = selected.get('category') == 'Negative'
        if not ((is_neg and action in NEGATIVE_ACTIONS) or
                (not is_neg and selected.get('category')=='Positive' and action in ACTIONS)):
            raise HTTPException(400,'Needs mapping: review an action for this test-case category.')
        if not (body.acknowledge_trusted_code and body.acknowledge_test_transactions):
            raise HTTPException(400,'Confirm reviewed script and permission for TEST/STAGING ERP transactions.')
        config=leocem.readiness()
        selected_config=negative_readiness() if is_neg else config
        if not selected_config['ready']:
            raise HTTPException(400,'Leocem not ready: '+' '.join(selected_config['issues']))
        if selected_config['script']['sha256']!=body.reviewed_source_sha256:
            raise HTTPException(400,'Saved Python source revision changed. Refresh and review the current revision.')
        try:
            project=leocem.ensure_project(config)
            runner,_=sw.inspect_source(NEGATIVE_SCRIPT_ID if is_neg else 'procurement/v636_case_runner.py')
            request=sw.ScriptRunInput(project_id=project['id'],script_id=runner['id'],
                       reviewed_sha256=runner['sha256'],mode='new',trust_local_code=True,allow_test_transactions=True,
                       positive_scenarios=not is_neg,negative_scenarios=is_neg,case_action=action,
                       case_test_id=selected['testcase_id'],case_expected=selected['expected'],
                       case_source_sha=body.reviewed_source_sha256)
            return script_manager.start(request,controller)
        except ValueError as exc:raise HTTPException(400,str(exc)) from exc
    app.include_router(router)
