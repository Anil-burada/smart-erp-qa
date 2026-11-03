"""v6.3.6 real selected values, time filtering, and report separation."""
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from openpyxl import load_workbook
from fastapi.testclient import TestClient
from backend.api import app
from backend import leocem_analytics as qa, leocem_test_case_report as cases, script_workspace as sw


class FakeRuns:
    def history(self, limit=100):
        return [
            {'id':'a'*32,'script_id':'procurement/pi_lpo_grn.py','started_at':'2026-10-28T11:00:00+00:00'},
            {'id':'b'*32,'script_id':'procurement/pi_lpo_grn.py','started_at':'2026-10-27T23:30:00+00:00'},
            {'id':'c'*32,'script_id':'other.py','started_at':'2026-10-28T12:00:00+00:00'},
        ]
    def detail(self, key):
        if key == 'a'*32:
            statuses = ['PASSED', 'FAILED', 'REVIEW']
        else:
            statuses = ['BLOCKED']
        return {'run':{'status':'FAILED' if key=='a'*32 else 'STOPPED'},
                'checks':[{'status':x} for x in statuses]}


def test_ist_day_week_month_filters():
    d=qa.summary(FakeRuns(), 'day', '2026-10-28')
    assert (d['total'],d['passed'],d['failed'],d['review'],d['blocked'])==(4,1,1,1,1)
    assert d['run_count']==2
    assert d['runs'][0]['started_at'].endswith('+05:30')
    assert qa.summary(FakeRuns(),'day','2026-10-27')['total']==0
    assert qa.summary(FakeRuns(),'week','2026-10-28')['total']==4
    assert qa.summary(FakeRuns(),'month','2026-10-02')['total']==4
    try: qa.summary(FakeRuns(),'year','2026-10-28')
    except ValueError: pass
    else: raise AssertionError('invalid period accepted')
    assert qa._bounds('month','2026-12-31')[1].date().isoformat()=='2027-01-01'


def sample_execution():
    return {'run':{'id':'e'*32,'module':'Procurement','process':'PI to LPO to GRN','sha256':'f'*64,
                   'script_id':'procurement/pi_lpo_grn.py','status':'COMPLETED_REVIEW','started_at':'2026-10-28T11:00:00+00:00',
                   'counts':{'passed':1,'failed':0,'review':1,'blocked':0}},
            'checks':[{'name':'LPO Gross','testcase_id':'SCRIPT-0001','status':'PASSED','expected':'100','actual':'100'}],
            'timeline':[],'evidence':[],'log':'',
            'selections':[{'at':'2026-10-28T11:00:00+00:00','process':'Purchase Indent','transaction':'PI/LEO/2026/123',
                           'values':{'department':'PACKING PLANT','item':'bolt','qty':12},'note':'Selected; no final assertion'},
                          {'at':'2026-10-28T11:00:01+00:00','process':'Local Purchase Order','transaction':'LPO/LEO/2026/123',
                           'values':{'quantity':12,'unit_price':100,'net':1350},'note':'Captured only'}]}


def test_execution_values_are_in_separate_section_and_xlsx_sheet():
    detail=sample_execution()
    markup=sw.report_html(detail)
    assert 'Actual PI / PO / GRN Values' in markup
    assert 'PACKING PLANT' in markup and '12' in markup and '1350' in markup
    assert 'not automatically a PASS' in markup
    book=load_workbook(BytesIO(sw.report_excel(detail)))
    assert 'Actual ERP Values' in book.sheetnames
    rows=list(book['Actual ERP Values'].values)
    assert any('PACKING PLANT' in row for row in rows)
    assert len(sw.report_rows(detail))==1  # selections must NOT be counted as checks


def test_case_steps_match_real_script_account_order():
    plan=cases.definition()
    approvals=next(c for c in plan['cases'] if c['testcase_id']=='LEO-TC-003')
    assert 'DMG0013' in ' '.join(approvals['steps'])
    assert 'DMG0041' in ' '.join(approvals['steps'])
    assert 'DMG0051' in ' '.join(approvals['steps'])
    po=next(c for c in plan['cases'] if c['testcase_id']=='LEO-TC-004')
    assert 'PGST' in ' '.join(po['steps'])
    assert all(row[8]=='' and row[9]=='' for row in cases.rows(plan))


def test_endpoint_and_frontend_controls():
    c=TestClient(app,base_url='http://127.0.0.1:8766')
    got=c.get('/api/leocem/dashboard/summary?period=day&date=2026-10-28')
    assert got.status_code==200
    assert got.json()['timezone']=='IST (UTC+05:30)'
    assert c.get('/api/leocem/dashboard/summary?period=invalid').status_code==400
    content=(Path(__file__).parents[1]/'frontend/workspace.js').read_text()
    for marker in ('Daily report','Weekly report','Monthly report','Passed and Failed Report','qaAnalysisDate','qa-pie-stack'):
        assert marker in content
