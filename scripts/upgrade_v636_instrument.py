"""Non-destructive best-effort upgrade for saved Leocem source instrumentation.
The locally edited target file remains authoritative. Never replace custom source.
"""
from pathlib import Path
import ast
import sys


def upgrade(donor_path, target_path):
    donor = Path(donor_path).read_text(encoding='utf-8')
    target_file = Path(target_path)
    if not target_file.is_file():
        print('SKIPPED: Target script not found; no script changed')
        return 0
    target = target_file.read_text(encoding='utf-8')
    if "emit('erp_values'" in target:
        print('SKIPPED: Existing structured ERP selections already found; saved script preserved')
        return 0
    if 'from backend.script_runtime import' not in target or 'emit' not in target.split('from backend.script_runtime import', 1)[1].split('\n', 1)[0]:
        print('SKIPPED: Script has no structured event emitter; retain custom code unchanged')
        return 0
    anchors = [
        '                transaction = pi["transaction"]',
        '                if report["lpo"]["status"] == "LPO_VALIDATION_FAILED_NOT_SAVED":',
        '                print_monitor.validate_new(lpo_pdf_checkpoint, "LPO", lpo_expected,',
        '                print_monitor.validate_new(grn_pdf_checkpoint, "GRN",',
    ]
    revised = target
    for anchor in anchors:
        if target.count(anchor) != 1 or donor.count(anchor) != 1:
            print('SKIPPED: Script differs from recognized source; no changes made:', anchor.strip()[:80])
            return 0
        position = donor.index(anchor)
        prefix = donor[:position]
        insertion_start = prefix.rfind("                emit('erp_values'")
        if insertion_start < 0:
            print('SKIPPED: Packaged source has no structured capture block')
            return 0
        insertion = prefix[insertion_start:position]
        if not insertion.startswith("                emit('erp_values'"):
            return 0
        revised = revised.replace(anchor, insertion + anchor, 1)
    try:
        ast.parse(revised)
    except SyntaxError as exc:
        print('SKIPPED: Script differs too much to insert safely; original preserved:', exc)
        return 0
    target_file.write_text(revised, encoding='utf-8')
    print('SUCCESS: Added structured PI/PO/GRN value capture to saved VS Code script')
    return 0


if __name__ == '__main__':
    raise SystemExit(upgrade(sys.argv[1], sys.argv[2]))
