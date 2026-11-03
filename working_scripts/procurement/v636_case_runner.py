"""Reviewed test-case adapter. Reads, but NEVER modifies, the existing PI -> GRN script.
Runs only actions authorized by the local case registry and pinned source hash.
"""
from __future__ import annotations
import hashlib
import os
import runpy
import traceback
from pathlib import Path
from playwright.sync_api import sync_playwright, expect
from backend.script_runtime import emit, check, capture_failure

VALID={'login_only','pi_creation','pi_approvals','lpo_creation','full_flow'}

def main():
    action=os.environ.get('SMART_ERP_CASE_ACTION','')
    case_id=os.environ.get('SMART_ERP_CASE_ID','')
    expected=os.environ.get('SMART_ERP_CASE_EXPECTED','')
    if action not in VALID or not case_id:raise RuntimeError('No reviewed case action or testcase ID supplied.')
    source=Path(__file__).with_name('pi_lpo_grn.py')
    expected_sha=os.environ.get('SMART_ERP_CASE_SOURCE_SHA','')
    if not expected_sha or hashlib.sha256(source.read_bytes()).hexdigest()!=expected_sha:
        raise RuntimeError('The positive source script changed since review. Reload and approve again.')
    # run_name is never __main__, so the full script main() cannot start accidentally.
    funcs=runpy.run_path(str(source),run_name='smart_erp_reviewed_case_module')
    emit('case_start',testcase_id=case_id,action=action,expected=expected)
    if action=='full_flow':
        funcs['main']()
        emit('check',name=f'{case_id}: Full procurement flow completed',testcase_id=case_id,
             status='REVIEW',expected=expected,actual='Script completed; check persisted ERP statuses and transaction IDs',
             category='Positive',process='Excel/manual test-case runner')
        return
    url=funcs['ERP_URL'];timeout=funcs['TIMEOUT']
    if not url:raise RuntimeError('ERP URL was not provided by authorized TEST/STAGING project.')
    page=None
    with sync_playwright() as playwright:
        browser,context,page,owns=funcs['open_script_browser'](playwright,url,timeout)
        try:
            page.set_default_timeout(timeout)
            page.goto(url,wait_until='domcontentloaded',timeout=60000)
            user='DMG0013';funcs['login'](page,user)
            sidebar=page.locator('div.pro-sidebar')
            expect(sidebar).to_be_visible(timeout=timeout)
            check(f'{case_id}: Login and authenticated navigation',True,
                  'ERP navigation/sidebar visible','Authenticated sidebar visible',page=page,
                  process='Authentication')
            if action=='login_only':return
            record=funcs['TEST_DATA'][0]
            pi=funcs['create_indent'](page,record)
            if not pi or not pi.get('transaction'):raise RuntimeError('PI creation returned no transaction number.')
            emit('check',name=f'{case_id}: PI created and submitted',testcase_id=case_id,
                 status='REVIEW',expected=expected,actual='PI identified as '+pi['transaction']+
                 '; final persisted SUBMITTED status not independently verified',category='Positive',
                 process='Purchase Indent')
            if action=='pi_creation':return
            number=pi['transaction']
            funcs['approve_indent'](page,number,user,from_pi_view=True)
            for next_user in ('DMG0041','DMG0051'):
                funcs['logout'](page,user);user=next_user;funcs['login'](page,user)
                funcs['approve_indent'](page,number,user)
            emit('check',name=f'{case_id}: PI approval clicks',testcase_id=case_id,
                 status='REVIEW',expected=expected,actual='PI approval actions completed for saved roles; final ERP status not independently verified',
                 category='Positive',process='Purchase Indent')
            if action=='pi_approvals':return
            funcs['logout'](page,user);user='DMG0041';funcs['login'](page,user)
            lpo=funcs['create_lpo'](page,pi)
            emit('check',name=f'{case_id}: LPO creation',testcase_id=case_id,
                 status='REVIEW',expected=expected,actual='LPO creation step finished: '+str(lpo.get('transaction',''))+
                 '; final ERP persistence needs review',category='Positive',process='Local Purchase Order')
        except Exception as exc:
            emit('check',name=f'{case_id}: {action}',testcase_id=case_id,
                 status='FAILED',expected=expected or 'Complete selected case',actual=str(exc)[:1200],
                 evidence=capture_failure(page,case_id,expected,str(exc)),category='Positive',process='Selected test case')
            raise
        finally:
            if owns:browser.close()

if __name__=='__main__': main()
