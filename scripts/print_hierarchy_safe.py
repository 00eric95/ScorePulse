import json
import importlib.util
from pathlib import Path
import sys

base = Path(__file__).resolve().parent.parent
main_file = base / 'main.py'
if not main_file.exists():
    print(json.dumps({"error": "main.py not found"}))
    sys.exit(1)

spec = importlib.util.spec_from_file_location('mp_main', str(main_file))
mp = importlib.util.module_from_spec(spec)
try:
    spec.loader.exec_module(mp)
except Exception as e:
    print(json.dumps({"error": f"failed to exec main.py: {e}"}, ensure_ascii=False))
    raise

if not hasattr(mp, 'MatchPredictor'):
    print(json.dumps({"error": "MatchPredictor not found in main.py"}))
    sys.exit(1)

try:
    m = mp.MatchPredictor()
    h = m.get_team_hierarchy()
except Exception as e:
    print(json.dumps({"error": str(e)}))
    raise

# compact sample
sample = {}
for i, country in enumerate(list(h.keys())[:40]):
    leagues = h[country]
    first_league = list(leagues.keys())[0] if leagues else ''
    teams = leagues.get(first_league, [])[:10]
    sample[country] = {first_league: teams}

print(json.dumps(sample, ensure_ascii=False, indent=2))
