"""Safe project-scoped removal of reviewed or draft workflow recordings.

Active JSON + optional sidecar files are MOVED to an archive and the SQLite
index row is deleted. Audit execution history and locator libraries are kept.
Referenced workflows cannot be removed until their flow/plan is updated.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import uuid4

from backend.registry import (BASE, PROJECT_PATTERN, WORKFLOW_PATTERN,
                              connect, get_project, workflow_path)


def _referencing_documents(project_id: str, name: str) -> list[str]:
    references = []
    # Evaluate only documents within this exact ERP project. Unknown/corrupt
    # documents are blockers because their references cannot be ruled out.
    for folder, category in (('flows', 'Business flow'),
                             ('approval_plans', 'Approval plan')):
        root = BASE / folder / project_id
        for path in sorted(root.glob('*.json')):
            try:
                doc = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(doc, dict) or doc.get('project_id') != project_id:
                    raise ValueError('invalid document identity')
                in_stages = any(isinstance(step, dict) and step.get('workflow') == name
                                for step in doc.get('stages', []))
                used_logout = category == 'Approval plan' and doc.get('logout_workflow') == name
                if in_stages or used_logout:
                    references.append(f'{category}: {path.stem}')
            except (OSError, ValueError, TypeError):
                references.append(f'{category}: {path.stem} (unreadable; review before removal)')
    return references


def archive_saved_workflow(project_id: str, name: str) -> dict:
    if not PROJECT_PATTERN.fullmatch(project_id) or not WORKFLOW_PATTERN.fullmatch(name):
        raise ValueError('Invalid project or workflow identifier')
    if get_project(project_id) is None:
        raise FileNotFoundError('ERP project not found')
    source = workflow_path(project_id, name)
    references = _referencing_documents(project_id, name)
    if references:
        raise ValueError('Workflow is referenced by ' + ', '.join(references) +
                         '. Update or remove those plans/flows before deleting this workflow.')
    if not source.is_file():
        raise FileNotFoundError('Workflow JSON was not found; cannot archive a missing file')
    archive_id = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '_' + uuid4().hex[:8]
    archive_dir = BASE / 'workflow_archive' / project_id / name / archive_id
    source_files = [source]
    for suffix in ('.negative_cases.json', '.v1-backup.json'):
        companion = source.with_name(name + suffix)
        if companion.is_file():
            source_files.append(companion)
    moved = []
    # Check and remove the SQLite listing together. Restore files if anything
    # fails mid-operation so the source JSON and index do not diverge.
    try:
        with connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing = c.execute('SELECT 1 FROM workflows WHERE project_id=? AND name=?',
                                 (project_id, name)).fetchone()
            if existing is None:
                raise FileNotFoundError('Workflow not found in active backend registry')
            archive_dir.mkdir(parents=True, exist_ok=False)
            for file in source_files:
                destination = archive_dir / file.name
                file.replace(destination)
                moved.append((file, destination))
            c.execute('DELETE FROM workflows WHERE project_id=? AND name=?',
                      (project_id, name))
    except Exception:
        for original, saved in reversed(moved):
            if saved.exists():
                saved.replace(original)
        raise
    return {'removed': True, 'project_id': project_id, 'name': name,
            'archived_files': len(moved),
            'archive_path': str(archive_dir.relative_to(BASE)).replace('\\', '/') ,
            'note': 'Saved executions and shared locator library were preserved.'}
