import json
from main import MatchPredictor

mp = MatchPredictor()
try:
    h = mp.get_team_hierarchy()
except Exception as e:
    print(json.dumps({"error": str(e)}))
    raise

# Prepare a compact sample: first 30 countries, each with first league and up to 8 teams
sample = {}
for i, country in enumerate(list(h.keys())[:30]):
    leagues = h[country]
    first_league = list(leagues.keys())[0] if leagues else ''
    teams = leagues.get(first_league, [])[:8]
    sample[country] = {first_league: teams}

print(json.dumps(sample, ensure_ascii=False, indent=2))
