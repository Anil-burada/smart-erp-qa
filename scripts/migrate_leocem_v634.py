"""Optional, idempotent upgrade of the user's editable Leocem script.

Only exact known v6.3.3 fragments are changed. Custom code is never overwritten.
"""
from pathlib import Path
from sys import argv

NEGATIVE_SUPPORT = '''
def validate_pi_quantity(value):
    """The same numeric guard used by the live PI item entry."""
    amount = decimal(value)
    if amount <= 0:
        raise ValueError("Indent Quantity must be greater than zero")
    return amount


def smart_erp_run_negative_scenarios():
    """Non-destructive negative checks of the actual PI quantity guard.

    These do NOT enter invalid values in the Leocem browser or prove that
    live ERP validation rejects them. They are labeled Local negative rules.
    """
    samples = [('Zero indent quantity', 0),
               ('Negative indent quantity', -5),
               ('Alphabetic indent quantity', 'invalid-quantity'),
               ('Mixed numeric indent quantity', '12abc')]
    failures = 0
    for name, invalid in samples:
        try:
            validate_pi_quantity(invalid)
        except (ValueError, ArithmeticError):
            check('Negative / Local PI rule: ' + name, True,
                  'Reject invalid quantity before ERP submission',
                  'Rejected ' + repr(invalid) + ' by the saved script quantity guard',
                  process='Local script validation (no ERP browser)', category='Negative')
        else:
            failures += 1
            check('Negative / Local PI rule: ' + name, False,
                  'Reject invalid quantity before ERP submission',
                  'Unexpectedly accepted ' + repr(invalid),
                  process='Local script validation (no ERP browser)', category='Negative')
    if failures:
        raise AssertionError(str(failures) + ' local negative quantity rule(s) failed')
'''

OLD_GUARD='''    target = decimal(quantity)\n\n\n\n    if target <= 0:\n\n\n\n        raise ValueError(\n\n            "Indent Quantity must be greater than zero"\n\n        )'''


def migrate(path: Path):
    source=path.read_text(encoding='utf-8')
    updated=source
    applied=[]
    if 'def smart_erp_run_negative_scenarios(' not in updated:
        # Never insert tests that don't actually call the live code guard.
        if updated.count(OLD_GUARD)==1 and updated.count('def enter_purchase_indent_quantity(')==1:
            updated=updated.replace(OLD_GUARD,'    target = validate_pi_quantity(quantity)',1)
            updated=updated.replace('def enter_purchase_indent_quantity(', NEGATIVE_SUPPORT+'\n\ndef enter_purchase_indent_quantity(',1)
            applied.append('Non-destructive Negative PI quantity checks (shared live guard)')
        else:
            print('Skipped scenario guard: local script differs from recognized v6.3.3; edit it manually in VS Code.')
    # Take screenshot of the actual red-box annotated PDF preview before it closes.
    marker="            print(f\"PRINT PREVIEW DISPLAYED ({status}): {pdf_path}\")"
    if 'ANNOTATED PRINT SCREENSHOT:' not in updated and updated.count(marker)==1:
        replacement='''            # Capture the rendered ERP print document with the REAL red/green
            # boxes drawn onto the copied PDF, not the plain ERP page underneath.
            if result.get('status') == 'FAIL':
                preview_file = PRINT_REPORTS / (print_safe_name(label) + '_ANNOTATED_PRINT_SCREEN.png')
                preview.screenshot(path=str(preview_file), full_page=True)
                result['annotated_print_screen'] = str(preview_file)
                print('ANNOTATED PRINT SCREENSHOT:', preview_file)
'''+marker
        updated=updated.replace(marker,replacement,1)
        applied.append('Annotated PDF preview screenshot')
    # The literal JS newline bug caused the same-page error banner to fail.
    wrong="box.textContent=messages.join('\\n');document.body.appendChild(box);"
    fixed="box.textContent=messages.join(String.fromCharCode(10));document.body.appendChild(box);"
    if wrong in updated:
        updated=updated.replace(wrong,fixed)
        applied.append('Safe print failure overlay newline')
    # Keep screenshot paths associated with a print_check event for the report.
    before="""            emit('print_check', name=label, status=result.get('status', 'REVIEW'),
                 process='PDF print checks', actual='Print validator result; inspect field-level evidence',
                 expected='Configured printed fields match source values',
                 fields=result.get('fields', []))
            print_show_failure_on_current_page(self.page, label, result)
            self.show_annotated_preview(result, label)"""
    after="""            print_show_failure_on_current_page(self.page, label, result)
            self.show_annotated_preview(result, label)
            artifact = (result.get('annotated_print_screen')
                        or (result.get('screenshots') or [None])[0]
                        or result.get('annotated_pdf'))
            relative = None
            if artifact and run_directory():
                try:
                    relative = Path(artifact).relative_to(run_directory()).as_posix()
                except ValueError:
                    pass
            emit('print_check', name=label, status=result.get('status', 'REVIEW'),
                 process='PDF print checks', actual='Print validator result; inspect field-level evidence',
                 expected='Configured printed fields match source values',
                 evidence=relative, fields=result.get('fields', []))"""
    if updated.count(before)==1:
        updated=updated.replace(before,after,1)
        applied.append('Evidence paths linked to print validation results')
    # Restore screenshots after a DOM annotation fails; the report never claims it is highlighted.
    if updated != source:
        compile(updated, str(path), 'exec')
        path.write_text(updated, encoding='utf-8')
    print('v6.3.4 script improvements:', ', '.join(applied) if applied else 'Already applied or customized')
    return applied

if __name__=='__main__':
    migrate(Path(argv[1]))
