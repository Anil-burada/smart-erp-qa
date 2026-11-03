"""Validate read-only, honest workflow execution counts and filters."""
import sqlite3
from datetime import datetime, timedelta, timezone
from backend import reporting


def test_aggregate_outcomes_by_project_and_period(tmp_path, monkeypatch):
    db = tmp_path / 'executions.sqlite3'
    def conn():
        c = sqlite3.connect(db)
        c.row_factory = sqlite3.Row
        return c
    with conn() as c:
        c.execute('CREATE TABLE executions (id INTEGER PRIMARY KEY, project_id TEXT, workflow_name TEXT, status TEXT, step_number INT, message TEXT, started_at TEXT, ended_at TEXT)')
        now = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')
        past = (datetime.now(timezone.utc) - timedelta(days=70)).strftime('%Y-%m-%d %H:%M:%S')
        for project,status,when in [('p1','PASSED',now),('p1','FAILED',now),('p1','ERROR',now),('p1','COMPLETED_WITH_WARNINGS',now),('p2','SKIPPED',now),('p1','PASSED',past)]:
            c.execute('INSERT INTO executions (project_id,workflow_name,status,started_at) VALUES (?,?,?,?)',(project,'flow',status,when))
    monkeypatch.setattr(reporting,'connect',conn)
    monkeypatch.setattr(reporting,'get_project',lambda project: {'id':project} if project in ('p1','p2') else None)
    recent = reporting.summary('',30)
    assert recent['total']==5
    assert recent['counts']=={'passed':1,'failed':1,'error':1,'skipped':1,'other':1}
    assert recent['pass_rate']==20.0
    assert recent['basis']=='workflow_executions'
    assert len(recent['recent'])==5
    project = reporting.summary('p1',0)
    assert project['total']==5
    assert project['counts']['passed']==2
    assert project['counts']['skipped']==0


def test_category_is_conservative():
    assert reporting.category('PASSED')=='passed'
    assert reporting.category('FAILED')=='failed'
    assert reporting.category('ERROR')=='error'
    assert reporting.category('BLOCKED')=='other'
    assert reporting.category('COMPLETED_WITH_WARNINGS')=='other'
