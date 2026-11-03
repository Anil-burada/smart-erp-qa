"""Make one portable Smart ERP QA deployment archive with a laptop's saved state.

Only stdlib Python is required. Do not read, copy or package the root .env.
Run with the Smart ERP backend stopped so SQLite is copied consistently.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shutil
import tempfile
import zipfile

DYNAMIC = ('projects', 'workflows', 'approval_plans', 'data', 'artifacts', 'reports', 'uploaded_scripts', 'working_scripts')
OPTIONAL_LEGACY = ('legacy/screenshots', 'legacy/reports')
SKIP_ROOT = {'.venv', '.env', '.git', 'node_modules', 'logs'}
SKIP_PARTS = {'__pycache__', '.venv', 'node_modules', '.git', '.env'}
REQUIRED = ('run.py', 'backend/api.py', 'frontend/app.js', 'requirements.txt')


def safe_copy_file(src: Path, dst: Path) -> None:
    if src.is_symlink():
        raise ValueError(f'Refusing symlink in transfer: {src}')
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)


def copy_tree_safely(src: Path, dst: Path) -> None:
    """Copy whole trees without following symlinks or including machine-specific files."""
    if src.is_symlink():
        raise ValueError(f'Refusing symlink in transfer: {src}')
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.iterdir():
        if item.name in SKIP_PARTS or item.name.startswith('backup_before_'):
            continue
        if item.is_symlink():
            raise ValueError(f'Refusing symlink in transfer: {item}')
        dest = dst / item.name
        if item.is_dir():
            copy_tree_safely(item, dest)
        elif item.is_file():
            if item.suffix == '.pyc':
                continue
            safe_copy_file(item, dest)


def build_bundle(kit_root: Path, old_root: Path, output: Path) -> tuple[int, list[str]]:
    kit_root = kit_root.expanduser().resolve()
    old_root = old_root.expanduser().resolve()
    output = output.expanduser().resolve()
    for root in (kit_root, old_root):
        for name in REQUIRED[:3]:
            if not (root / name).is_file():
                raise ValueError(f'Not a complete Smart ERP project: {root} (missing {name})')
    if output.exists():
        raise FileExistsError(f'ZIP already exists: {output}. Move/rename it instead of overwriting.')
    output.parent.mkdir(parents=True, exist_ok=True)
    included: list[str] = []
    with tempfile.TemporaryDirectory(prefix='smart_erp_transfer_') as tmp:
        root = Path(tmp)
        project = root / 'smart_erp_qa_v630'
        project.mkdir()
        # Use verified v6.3.0 package code, not possibly obsolete code from laptop 1.
        for item in kit_root.iterdir():
            if item.name in SKIP_ROOT or item.name in DYNAMIC or item.name.startswith('backup_before_'):
                continue
            if item.suffix.lower() == '.zip':
                continue
            target = project / item.name
            if item.is_dir():
                copy_tree_safely(item, target)
            elif item.is_file():
                safe_copy_file(item, target)
            else:
                raise ValueError(f'Unsupported item in kit: {item}')
        for name in DYNAMIC:
            old_path = old_root / name
            target = project / name
            if old_path.is_dir():
                copy_tree_safely(old_path, target)
                included.append(name)
            else:
                kit_data = kit_root / name
                if kit_data.is_dir():
                    copy_tree_safely(kit_data, target)
                else:
                    target.mkdir(exist_ok=True)
        for name in OPTIONAL_LEGACY:
            old_path = old_root / name
            if old_path.is_dir():
                copy_tree_safely(old_path, project / name)
                included.append(name)
        manifest = {
            'edition': 'Smart ERP QA v6.3.0 portable transfer',
            'created_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'copied_from_laptop_folders': included,
            'excluded': ['.env', '.venv', 'node_modules', 'logs', 'backup_before_*'],
            'note': 'Extract on laptop 2 and run 1_INSTALL_ON_NEW_LAPTOP.bat. Enter .env secrets locally.',
        }
        (project / 'TRANSFER_MANIFEST.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
        entries = 0
        with zipfile.ZipFile(output, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6, allowZip64=True) as zipf:
            for path in sorted(project.rglob('*')):
                if not path.is_file():
                    continue
                if path.is_symlink():
                    raise ValueError(f'Refusing symlink in transfer: {path}')
                relative = path.relative_to(root)
                # A nested .env must not leak in a submitted portable ZIP.
                if '.env' in relative.parts:
                    raise ValueError(f'Unexpected .env in transfer staging: {relative}')
                zipf.write(path, relative.as_posix())
                entries += 1
        with zipfile.ZipFile(output) as zipf:
            if zipf.testzip() is not None or any(n.endswith('/.env') for n in zipf.namelist()):
                raise ValueError('Transfer ZIP failed validation')
        if entries < 50:
            output.unlink(missing_ok=True)
            raise ValueError('Transfer ZIP had unexpectedly few files')
    return entries, included


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kit-root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--current-project', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    opts = parser.parse_args()
    count, included = build_bundle(opts.kit_root, opts.current_project, opts.output)
    print('PORTABLE TRANSFER ZIP CREATED SUCCESSFULLY')
    print(f'ZIP: {opts.output.expanduser().resolve()}')
    print(f'Files: {count}')
    print(f'Live data folders: {", ".join(included) or "none (bundled samples only)"}')
    print('Root .env is EXCLUDED. Saved JSON and screenshots might still contain sensitive ERP data.')
    print('On laptop 2: Extract All -> 1_INSTALL_ON_NEW_LAPTOP.bat -> 2_OPEN_SMART_ERP_WEB.bat')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
