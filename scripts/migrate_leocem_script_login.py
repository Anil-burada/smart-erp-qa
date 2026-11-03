"""One-time surgical migration of v6.3.0/6.3.1 Leocem script login.

Preserves edits, does not execute ERP code, and never prints credentials.
"""
import sys
import re
from pathlib import Path

ORIGINAL_REQUIRED = 'SMART_ERP_REQUIRED_CREDENTIALS = ["ERPQA_KAGAMI_DMG0013_PASSWORD", "ERPQA_KAGAMI_DMG0041_PASSWORD", "ERPQA_KAGAMI_DMG0051_PASSWORD", "ERPQA_KAGAMI_DMG0052_PASSWORD"]'
ORIGINAL_LOGIN = '    password = os.environ.get(f"ERPQA_KAGAMI_{username}_PASSWORD", "")\n    if not password:\n        raise RuntimeError(f"Set ERPQA_KAGAMI_{username}_PASSWORD in your local .env file")\n    password_input.fill(password)'
ORIGINAL_CHECK = '    missing = [u for u in ("DMG0013", "DMG0041", "DMG0051", "DMG0052")\n               if not os.environ.get(f"ERPQA_KAGAMI_{u}_PASSWORD")]\n    if missing:\n        raise RuntimeError("Missing local test-account passwords for: " + ", ".join(missing))\n\n'
NEW_REQUIRED = 'SMART_ERP_REQUIRED_CREDENTIALS = []  # This script handles its own login values.'
NEW_LOGIN = ('    # Preserves the supplied login behavior: password uses the username.\n    # Edit this login function in VS Code if your test accounts use other passwords.\n    password_input.fill(username)')


def migrate(path: Path):
    text = path.read_text(encoding='utf-8')
    # Never replace unknown, customized login blocks or credential mappings.
    if 'ERPQA_KAGAMI_{username}_PASSWORD' in text and ORIGINAL_LOGIN not in text:
        raise ValueError('Existing script has customized environment-based login. Review it manually before updating.')
    if 'ERPQA_KAGAMI_{u}_PASSWORD' in text and ORIGINAL_CHECK not in text:
        raise ValueError('Existing script has customized pre-run password validation. Review it manually.')
    updated = text.replace(ORIGINAL_LOGIN, NEW_LOGIN).replace(ORIGINAL_CHECK, '')
    if ORIGINAL_REQUIRED in updated:
        updated = updated.replace(ORIGINAL_REQUIRED, NEW_REQUIRED)
    elif re.search(r'(?m)^SMART_ERP_REQUIRED_CREDENTIALS\s*=\s*\[(?!\s*\])', updated):
        raise ValueError('Custom required-credentials list found. Check it manually before running.')
    if updated == text:
        return False
    # Protect users against migration of unexpected script variants.
    compile(updated, str(path), 'exec')
    path.write_text(updated, encoding='utf-8')
    return True


if __name__ == '__main__':
    if len(sys.argv) != 2:
        sys.exit('Usage: migrate_leocem_script_login.py <script_path>')
    target = Path(sys.argv[1])
    if not target.is_file():
        sys.exit('Script path is missing')
    try:
        changed = migrate(target)
    except (ValueError, UnicodeError, SyntaxError) as error:
        sys.exit('Migration stopped; original script preserved: ' + str(error))
    print('Leocem login migration: ' + ('updated compatible legacy login' if changed else 'no changes needed'))
