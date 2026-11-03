"""Read-only Leocem QA analytics. Periods use IST and reflect recorded script checks only."""
from datetime import date, datetime, time, timedelta, timezone
from calendar import monthrange

IST = timezone(timedelta(hours=5, minutes=30))
UTC = timezone.utc
PERIODS = {'day', 'week', 'month'}


def _bounds(period: str, on: str | None):
    if period not in PERIODS:
        raise ValueError('Choose a daily, weekly, or monthly report.')
    try:
        reference = date.fromisoformat(on) if on else datetime.now(IST).date()
    except (ValueError, TypeError) as exc:
        raise ValueError('Date must have YYYY-MM-DD format.') from exc
    if period == 'week':
        start = reference - timedelta(days=reference.weekday())
        end = start + timedelta(days=7)
    elif period == 'month':
        start = reference.replace(day=1)
        end = date(start.year + (start.month == 12), start.month % 12 + 1, 1)
    else:
        start, end = reference, reference + timedelta(days=1)
    return datetime.combine(start, time.min, IST), datetime.combine(end, time.min, IST), reference


def _timestamp(value):
    try:
        timestamp = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        if timestamp.tzinfo is None:
            timestamp = timestamp.replace(tzinfo=UTC)
        return timestamp.astimezone(IST)
    except (ValueError, TypeError):
        return None


def summary(manager, period='day', on=None):
    start, end, reference = _bounds(period, on)
    result = {'period': period, 'date': reference.isoformat(), 'timezone': 'IST (UTC+05:30)',
              'start': start.isoformat(), 'end_exclusive': end.isoformat(),
              'generated_at': datetime.now(IST).isoformat(), 'run_count': 0,
              'total': 0, 'passed': 0, 'failed': 0, 'review': 0, 'blocked': 0, 'runs': []}
    for run in manager.history(limit=5000):
        if run.get('script_id') != 'procurement/pi_lpo_grn.py':
            continue
        when = _timestamp(run.get('started_at'))
        if when is None or not start <= when < end:
            continue
        detail = manager.detail(run['id'])
        checks = detail.get('checks', [])
        counts = {status: sum(check.get('status') == code for check in checks) for status, code in
                  [('passed', 'PASSED'), ('failed', 'FAILED'), ('review', 'REVIEW'), ('blocked', 'BLOCKED')]}
        for status, n in counts.items():
            result[status] += n
        result['total'] += len(checks)
        result['run_count'] += 1
        result['runs'].append({'id': run['id'], 'started_at': when.isoformat(),
                               'script_id': run['script_id'], 'status': detail['run']['status'],
                               'total': len(checks), **counts})
    return result
