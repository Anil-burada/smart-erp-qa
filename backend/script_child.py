"""Execute one approved source snapshot, never an arbitrary command string."""
from __future__ import annotations
import json
import os
import sys
import traceback
from pathlib import Path

from backend.script_runtime import emit


def main() -> int:
    snapshot, original, directory = map(Path, sys.argv[1:4])
    # Executed bytes come from the approved immutable snapshot; __file__ stays
    # the editable source location so its sequence/counter data can persist.
    sys.path.insert(0, str(original.parent))
    sys.argv = [str(original)]
    code = compile(snapshot.read_bytes(), str(original), 'exec')
    emit('run_start', source=str(original))
    try:
        do_positive = os.environ.get('SMART_ERP_RUN_POSITIVE', '1') == '1'
        do_negative = os.environ.get('SMART_ERP_RUN_NEGATIVE', '0') == '1'
        if do_negative:
            ns = {'__name__': '__smart_erp_negative_only__', '__file__': str(original), '__package__': None}
            exec(code, ns)
            runner = ns.get('smart_erp_run_negative_scenarios')
            if not callable(runner):
                raise ValueError('The approved script has no executable negative scenario function.')
            runner()
        if do_positive:
            exec(code, {'__name__': '__main__', '__file__': str(original), '__package__': None})
    except SystemExit as exc:
        status = exc.code if isinstance(exc.code, int) else (0 if exc.code is None else 1)
        emit('run_end', exit_code=status)
        return status
    except BaseException as exc:
        traceback.print_exc()
        emit('run_error', message=str(exc)[:2000])
        emit('run_end', exit_code=1)
        return 1
    emit('run_end', exit_code=0)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
