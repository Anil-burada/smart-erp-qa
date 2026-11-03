"""Read-only dashboard aggregates based on persisted workflow EXECUTIONS.

Important: an execution row represents one workflow run, not every test case.
This endpoint does not modify the test database or depend on live browser state.
"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, HTTPException, Query
from backend.registry import connect, get_project

router = APIRouter(prefix='/api/reporting', tags=['reporting'])


def category(status: str) -> str:
    s = (status or '').strip().upper()
    if s in ('PASSED', 'FAILED', 'ERROR', 'SKIPPED'):
        return s.lower()
    return 'other'


@router.get('/summary')
def summary(project_id: str = '', days: int = Query(30, ge=0, le=3650)):
    if project_id and not get_project(project_id):
        raise HTTPException(status_code=404, detail='ERP project not found')
    clauses, args = [], []
    if project_id:
        clauses.append('project_id = ?')
        args.append(project_id)
    if days:
        # Include today and the previous (days - 1) UTC calendar days.
        clauses.append("date(started_at) >= date('now', ?)")
        args.append(f'-{days-1} days')
    where = ' WHERE ' + ' AND '.join(clauses) if clauses else ''
    totals = {x: 0 for x in ('passed','failed','error','skipped','other')}
    per_project = {}
    today = datetime.now(timezone.utc).date()
    chart_days = min(days or 14, 14)
    start = today - timedelta(days=chart_days - 1)
    trend = {str(start + timedelta(days=i)): {'day': str(start + timedelta(days=i)), 'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0, 'other': 0} for i in range(chart_days)}
    with connect() as c:
        rows = c.execute('SELECT project_id, status, COUNT(*) AS n FROM executions' + where + ' GROUP BY project_id, status', args).fetchall()
        for r in rows:
            key = category(r['status'])
            n = int(r['n'])
            totals[key] += n
            row = per_project.setdefault(r['project_id'], {'project_id': r['project_id'], 'passed': 0, 'failed': 0, 'error': 0, 'skipped': 0, 'other': 0, 'total': 0})
            row[key] += n
            row['total'] += n
        trend_where = (where + (' AND ' if where else ' WHERE ') + 'date(started_at) >= ?')
        for r in c.execute('SELECT date(started_at) AS day, status, COUNT(*) AS n FROM executions' + trend_where + ' GROUP BY day, status', args + [str(start)]):
            if r['day'] in trend:
                trend[r['day']][category(r['status'])] += int(r['n'])
        recent = [dict(x) for x in c.execute('SELECT id, project_id, workflow_name, status, step_number, message, started_at, ended_at FROM executions' + where + ' ORDER BY id DESC LIMIT 30', args).fetchall()]
    total = sum(totals.values())
    return {
        'basis': 'workflow_executions',
        'note': 'Counts reflect saved workflow execution records, not individual test cases or unrecorded manual tests.',
        'filters': {'project_id': project_id, 'days': days},
        'total': total,
        'counts': totals,
        'pass_rate': round(100 * totals['passed'] / total, 1) if total else None,
        'trend': list(trend.values()),
        'by_project': sorted(per_project.values(), key=lambda x: (-x['total'], x['project_id'])),
        'recent': recent,
    }
