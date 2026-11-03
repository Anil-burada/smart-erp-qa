"""Portable bundle includes all code and live state, not local .env secrets."""
import json
from pathlib import Path
import zipfile
import pytest

from scripts.build_portable_transfer import build_bundle


def test_transfer_carries_live_workflows_and_db_without_env(tmp_path):
    kit = tmp_path / 'kit'
    old = tmp_path / 'old'
    out = tmp_path / 'transfer.zip'
    for root in (kit, old):
        for name in ('backend/api.py', 'frontend/app.js', 'run.py', 'requirements.txt'):
            p = root / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(f'{root.name}::{name}', encoding='utf-8')
    (kit / 'projects' / 'demo').mkdir(parents=True)
    (kit / 'projects' / 'demo' / 'locators.json').write_text('{}')
    (old / 'projects' / 'leocem_ba').mkdir(parents=True)
    (old / 'projects' / 'leocem_ba' / 'login.json').write_text('{"username":"#signin-username"}')
    (old / 'workflows' / 'leocem_ba').mkdir(parents=True)
    (old / 'workflows' / 'leocem_ba' / 'purchase_indent88.json').write_text('{"steps":[]}')
    (old / 'data').mkdir()
    (old / 'data' / 'erpqa.sqlite3').write_bytes(b'SQLITE-DEMO-DATA')
    (old / 'working_scripts' / 'procurement').mkdir(parents=True)
    (old / 'working_scripts' / 'procurement' / 'custom.py').write_text('print("my_saved_edit")')
    (old / '.env').write_text('OPENAI_API_KEY=private-key')
    (old / 'artifacts').mkdir()
    (old / 'artifacts' / 'result.png').write_bytes(b'PNG demo')
    (old / 'projects' / 'leocem_ba' / '.env').write_text('NESTED_PRIVATE=yes')
    # Make the small mock kit large enough for its >= 50 file sanity threshold.
    (kit / 'frontend').mkdir(exist_ok=True)
    for i in range(51):
        (kit / 'frontend' / f'source_{i}.txt').write_text('x')
    count, data = build_bundle(kit, old, out)
    assert count >= 50
    assert {'projects', 'workflows', 'data', 'artifacts'} <= set(data)
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        prefix = 'smart_erp_qa_v630/'
        assert f'{prefix}workflows/leocem_ba/purchase_indent88.json' in names
        assert f'{prefix}projects/leocem_ba/login.json' in names
        assert f'{prefix}data/erpqa.sqlite3' in names
        assert f'{prefix}artifacts/result.png' in names
        assert f'{prefix}projects/demo/locators.json' not in names
        assert z.read(f'{prefix}working_scripts/procurement/custom.py') == b'print("my_saved_edit")'
        assert f'{prefix}.env' not in names
        assert f'{prefix}projects/leocem_ba/.env' not in names
        assert z.read(f'{prefix}backend/api.py') == b'kit::backend/api.py'
        assert json.loads(z.read(f'{prefix}TRANSFER_MANIFEST.json'))['copied_from_laptop_folders']


def test_transfer_refuses_overwrite(tmp_path):
    p = tmp_path / 'existing.zip'
    p.write_text('keep')
    for name in ('backend/api.py', 'frontend/app.js', 'run.py', 'requirements.txt'):
        f = tmp_path / name
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text('ok')
    with pytest.raises(FileExistsError):
        build_bundle(tmp_path, tmp_path, p)
    assert p.read_text() == 'keep'
