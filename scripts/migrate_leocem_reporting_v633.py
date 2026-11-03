"""Non-destructive Leocem script report instrumentation (v6.3.3).

Only recognized source snippets are changed, never auth or transaction sequences.
Custom code stays untouched where expected anchors are absent; a backup of the
full project is created by the Windows updater before this script runs.
"""
from pathlib import Path
import sys


def migrate(path: Path):
    text = path.read_text(encoding='utf-8')
    patches = [
        (
            "                    return\n\n\n\n            except Exception:\n\n                pass\n\n\n\n    mark_error(field)",
            "                    check('Purchase Indent: Item Quantity', True, target, field.input_value(),\n"
            "                          page=page, process='Purchase Indent')\n"
            "                    return\n\n\n\n            except Exception:\n\n                pass\n\n\n\n    mark_error(field)",
            'PI item quantity',
        ),
        (
            '            f"Expected={expected} | Actual={actual}"\n\n        )\n\n\n\n\n\n# ============================================================\n\n# SELECT PGST',
            '            f"Expected={expected} | Actual={actual}"\n\n        )\n'
            "        check('Local Purchase Order: ' + {'quantity': 'Item Quantity',\n"
            "              'unitprice': 'Unit Price', 'dispercent': 'Discount Percentage'}[suffix],\n"
            "              True, expected, actual, page=page, process='Local Purchase Order')\n"
            '\n\n\n\n# ============================================================\n\n# SELECT PGST',
            'LPO item quantity/unit price/discount',
        ),
        (
            "    print('PASS - Warehouse quantity:', actual)",
            "    check('Goods Receipt Note: Warehouse Received Quantity', True, received_qty, actual,\n"
            "          page=page, process='Goods Receipt Note')\n"
            "    print('PASS - Warehouse quantity:', actual)",
            'GRN warehouse quantity',
        ),
        (
            '    mark_error(field)\n\n\n\n    raise RuntimeError(\n\n        f"Indent Quantity reset by ERP: "',
            "    check('Purchase Indent: Item Quantity', False, target, field.input_value(),\n"
            "          page=page, process='Purchase Indent')\n"
            '    mark_error(field)\n\n\n\n    raise RuntimeError(\n\n        f"Indent Quantity reset by ERP: "',
            'PI item quantity on failure',
        ),
        (
            '        ):\n\n\n\n            mark_error(field)\n\n\n\n            raise RuntimeError(\n\n                f"{field_id} changed after "',
            '        ):\n\n'
            "            check('Local Purchase Order: ' + {'quantity': 'Item Quantity',\n"
            "                  'unitprice': 'Unit Price', 'dispercent': 'Discount Percentage'}[suffix],\n"
            "                  False, expected, actual, page=page, process='Local Purchase Order')\n"
            '\n            mark_error(field)\n\n\n\n            raise RuntimeError(\n\n                f"{field_id} changed after "',
            'LPO numeric mismatch on failure',
        ),
        (
            "    if actual != received_qty:\n        raise RuntimeError(\n            f'Warehouse quantity changed: expected {received_qty}, got {actual}'",
            "    if actual != received_qty:\n"
            "        check('Goods Receipt Note: Warehouse Received Quantity', False, received_qty, actual,\n"
            "              page=page, process='Goods Receipt Note')\n"
            "        raise RuntimeError(\n            f'Warehouse quantity changed: expected {received_qty}, got {actual}'",
            'GRN warehouse quantity mismatch on failure',
        ),
        (
            "box.textContent=messages.join('\\n');document.body.appendChild(box);",
            "box.textContent=messages.join('\\\\n');document.body.appendChild(box);",
            'PDF failure JavaScript syntax',
        ),
    ]
    applied = []
    skipped = []
    for old, new, label in patches:
        if new in text or (label == 'PI item quantity' and
                           "check('Purchase Indent: Item Quantity', True" in text):
            continue
        if text.count(old) == 1:
            text = text.replace(old, new, 1)
            applied.append(label)
        else:
            skipped.append(label)
    if applied:
        compile(text, str(path), 'exec')
        path.write_text(text, encoding='utf-8')
    print('Report enhancements applied:', ', '.join(applied) or 'Already applied')
    if skipped:
        print('Not changed (customized source):', ', '.join(skipped))
    return {'applied': applied, 'skipped': skipped}


if __name__ == '__main__':
    migrate(Path(sys.argv[1]))
