r"""Run any approved, project-mapped business flow after MANUAL ERP login.

Example (from project root):
  .\.venv\Scripts\python.exe -m scripts.run_business_flow --project mock_erp --flow indent_to_grn

No ERP locators are hardcoded here. Locator libraries and reviewed workflows
are specific to each registered ERP. This is for authorized TEST/STAGING use.
"""
import argparse
import json
import sys
from backend.browser import BrowserController
from backend.flow_studio import load_flow, preview_flow
from backend.registry import get_project, connect
from backend.approval_plans import read_workflow


def main():
    parser=argparse.ArgumentParser(description='Smart ERP QA reviewed same-user business flow')
    parser.add_argument('--project',required=True,help='Registered test/staging ERP ID')
    parser.add_argument('--flow',required=True,help='Saved flow name')
    parser.add_argument('--data-file',help='Local non-secret JSON of runtime test variables')
    args=parser.parse_args()
    project=get_project(args.project)
    if not project or project['environment'] not in ('test','staging'):
        parser.error('Register a TEST/STAGING ERP project first')
    data=json.load(open(args.data_file,encoding='utf-8')) if args.data_file else {}
    flow=load_flow(args.project,args.flow)
    check=preview_flow(flow,data)
    if not check['ready']:
        print(json.dumps({'ready':False,'issues':check['issues'],'stages':check['stages']},indent=2))
        return 2
    print('Ready:', len(flow.stages),'approved stages. This will execute real TEST/STAGING transactions.')
    print('Please log in manually. No credentials are saved by this script.')
    if input('Open browser for manual login? Type OPEN: ').strip() != 'OPEN':
        return 1
    controller=BrowserController()
    try:
        controller.call('open',project=project)
        input('Log in and navigate to the FIRST recorded stage screen, then press Enter here...')
        current=controller.call('status')
        if current['recording']:
            # Manual login/navigation is setup; do not treat it as an executable flow.
            controller.call('start')
            controller.call('stop')
        if input('I authorize the complete reviewed flow in TEST/STAGING. Type RUN: ').strip()!='RUN':
            return 1
        specs=[read_workflow(args.project, s.workflow).model_dump() for s in flow.stages]
        result=controller.call('run_flow',flow=flow.model_dump(),stages=specs,
                               allow_writes=True,test_data=data)
        with connect() as conn:
            conn.execute('INSERT INTO executions (project_id,workflow_name,status,step_number,message,artifact_path,ended_at) '
                         'VALUES (?,?,?,?,?,?,CURRENT_TIMESTAMP)',
                         (result['project_id'],result['workflow'],result['status'],result['failed_step'],
                          result['message'],result['report_path']))
        print(json.dumps(result,indent=2))
        input('Press Enter to close Playwright browser...')
        return 0 if result['status']=='PASSED' else 2
    finally:
        try:
            controller.call('close')
        except Exception:
            pass


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print('Flow setup failed:',str(exc)[:250],file=sys.stderr)
        sys.exit(2)
