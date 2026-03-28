import runpy, io, sys
from pathlib import Path
out = io.StringIO()
old_stdout = sys.stdout
sys.stdout = out
try:
    runpy.run_path('scripts/inspect_eval.py', run_name='__main__')
except SystemExit:
    pass
except Exception as e:
    print('ERROR_RUNNING_INSPECT:', e)
finally:
    sys.stdout = old_stdout
    Path('logs').mkdir(parents=True, exist_ok=True)
    with open('logs/inspect_eval_output.txt', 'w', encoding='utf-8') as f:
        f.write(out.getvalue())
    print('Saved inspect output to logs/inspect_eval_output.txt')
