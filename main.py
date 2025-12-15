import pandas as pd
import numpy as np
import sys
import os
import random
import joblib
from datetime import datetime, timedelta

# --- 1. PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- 2. IMPORTS ---
try:
    from config.config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from utils.data_loader import DataLoader
except ImportError:
    sys.path.append(os.path.join(current_dir, 'config'))
    from config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from utils.data_loader import DataLoader

class MatchPredictor:
    def __init__(self):
        self.config = Config()
        self.engineer = FeatureEngineer()
        self.loader = DataLoader()
        
        # Load Stats
        print("📥 [AI Brain] Loading stats database...")
        try:
            self.raw_df = self.loader.load_raw_data()
            self.processed_df = self.loader.preprocess(self.raw_df)
            if 'MatchDate' in self.raw_df.columns:
                self.raw_df['MatchDate'] = pd.to_datetime(self.raw_df['MatchDate'])
            if 'MatchDate' in self.processed_df.columns:
                self.processed_df['MatchDate'] = pd.to_datetime(self.processed_df['MatchDate'])
        except Exception as e:
            print(f"⚠️ [AI Brain] Warning: Data load failed ({e}).")
            self.raw_df = pd.DataFrame()
            self.processed_df = pd.DataFrame()
        
        # Load Schedule
        self.upcoming_path = os.path.join(current_dir, 'data', 'upcoming.csv')
        
        if not self.config.SCALER_PATH.exists():
            print("⚠️ [AI Brain] Notice: Scaler not found.")
        else:
            # Pre-load scaler for efficiency
            try:
                self.engineer.scaler = joblib.load(self.config.SCALER_PATH)
            except:
                print("⚠️ Could not load scaler.")
            
        self.models = {}

    # --- TEAMS & HIERARCHY ---
    def get_team_hierarchy(self):
        if self.raw_df is None or self.raw_df.empty: return {}
        
        two_years_ago = datetime.now() - timedelta(days=730)
        recent_df = self.raw_df[self.raw_df['MatchDate'] >= two_years_ago]
        if recent_df.empty: recent_df = self.raw_df

        DIV_MAP = {
            'E0': ('England', 'Premier League'), 'E1': ('England', 'Championship'),
            'SP1': ('Spain', 'La Liga'), 'D1': ('Germany', 'Bundesliga'),
            'I1': ('Italy', 'Serie A'), 'F1': ('France', 'Ligue 1'),
            'N1': ('Netherlands', 'Eredivisie'), 'P1': ('Portugal', 'Liga NOS'),
            'SC0': ('Scotland', 'Premiership')
        }

        hierarchy = {}
        if 'Division' in recent_df.columns:
            for div in recent_df['Division'].unique():
                country, league = DIV_MAP.get(div, ("International", str(div)))
                teams = sorted(list(set(recent_df[recent_df['Division'] == div]['HomeTeam'].unique()) | 
                                    set(recent_df[recent_df['Division'] == div]['AwayTeam'].unique())))
                if country not in hierarchy: hierarchy[country] = {}
                hierarchy[country][league] = teams
        return hierarchy

    # --- SCHEDULE ---
    def get_upcoming_matches(self, count=10):
        if not os.path.exists(self.upcoming_path): return []
        try:
            df = pd.read_csv(self.upcoming_path)
            df['Date'] = pd.to_datetime(df['Date'])
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            future = df[df['Date'] >= today].sort_values(by='Date')
            matches = []
            for _, r in future.head(count).iterrows():
                matches.append({"date": r['Date'].strftime('%Y-%m-%d'), "home": r['HomeTeam'], "away": r['AwayTeam'], "league": r['League']})
            return matches
        except: return []

    def get_premium_batch(self, count=10):
        sch = self.get_upcoming_matches(count=20)
        preds = []
        for m in sch:
            if len(preds) >= count: break
            res = self.predict_for_web(m['home'], m['away'], 'gold')
            if "error" not in res: preds.append(res)
        return preds

    # --- STATS ---
    def get_team_report_card(self, team_name):
        try:
            df = self.processed_df
            rows = df[(df['HomeTeam']==team_name)|(df['AwayTeam']==team_name)].sort_values('MatchDate')
            if rows.empty: return None
            last = rows.iloc[-1]
            p = 'Home' if last['HomeTeam']==team_name else 'Away'
            
            # Safe access
            avg_g = last.get(f"{p}_AvgGoals", 0)
            avg_c = last.get(f"{p}_AvgConceded", 0)
            avg_s = last.get(f"{p}_AvgShots", 0)
            
            return {
                "name": team_name,
                "rating": int(last.get(f'{p}Elo', 1000)),
                "ppg": round(last.get(f'Form5{p}', 0)/5, 2),
                "gd_trend": f"{'+' if (avg_g-avg_c)>0 else ''}{round((avg_g-avg_c)*5, 1)}",
                "xg": round(avg_s * 0.35 * 0.3, 2),
                "form": last.get(f'Form5{p}', 0)
            }
        except: return None

    def get_matchup_stats(self, home, away):
        try:
            h2h = self.raw_df[((self.raw_df['HomeTeam']==home)&(self.raw_df['AwayTeam']==away))|((self.raw_df['HomeTeam']==away)&(self.raw_df['AwayTeam']==home))].sort_values('MatchDate', ascending=False).head(5)
            res = []
            for _, r in h2h.iterrows():
                w = r['HomeTeam'] if r['FTR']=='H' else r['AwayTeam'] if r['FTR']=='A' else "Draw"
                res.append({"date": r['MatchDate'].strftime('%Y-%m-%d'), "score": f"{int(r['FTHG'])}-{int(r['FTAG'])}", "winner": w})
            return {"h2h": res}
        except: return {"h2h": []}

    # --- PREDICTION ENGINE ---
    def get_latest_stats(self, team):
        df = self.processed_df
        rows = df[(df['HomeTeam']==team)|(df['AwayTeam']==team)].sort_values('MatchDate')
        if rows.empty: raise ValueError(f"Team '{team}' not found.")
        last = rows.iloc[-1]
        p = 'Home' if last['HomeTeam']==team else 'Away'
        s = {'Elo': last[f'{p}Elo'], 'Form5': last[f'Form5{p}'], 'AvgGoals': last[f'{p}_AvgGoals'], 'RestDays': 5}
        for c in ['AvgConceded','AvgShots','AvgCorners','RecentPoints','Momentum']:
            s[c] = last.get(f"{p}_{c}" if c != 'RecentPoints' else f"{p}_RecentPoints", 0)
        return s

    def get_model(self, target, model_type='rf'):
        key = f"{target}_{model_type}"
        if key in self.models: return self.models[key]
        try:
            mode = 'regression' if target=='TotalGoals' else 'classification'
            m = ModelFactory.get_model(model_type, mode=mode)
            m.load(f"model_{target}.pkl"); self.models[key] = m; return m
        except: return None

    def predict_for_web(self, home, away, subscription_tier='free'):
        """
        Main prediction API. 
        Calculates Win Prob, Goals, and enforces score consistency.
        """
        if not self.config.SCALER_PATH.exists(): return {"error": "AI Brain Offline."}
        try: h=self.get_latest_stats(home); a=self.get_latest_stats(away)
        except ValueError as e: return {"error": str(e)}

        input_data = {
            'HomeElo': [h['Elo']], 'AwayElo': [a['Elo']],
            'EloDifference': [h['Elo'] - a['Elo']], 'EloAdvantage': [(h['Elo'] - a['Elo']) / (h['Elo'] + a['Elo'])],
            'Form5Home': [h['Form5']], 'Form5Away': [a['Form5']],
            'Home_RecentPoints': [h.get('RecentPoints',0)], 'Away_RecentPoints': [a.get('RecentPoints',0)],
            'Home_Momentum': [h.get('Momentum',0)], 'Away_Momentum': [a.get('Momentum',0)],
            'Home_AvgGoals': [h['AvgGoals']], 'Away_AvgGoals': [a['AvgGoals']],
            'Home_AvgConceded': [h.get('AvgConceded',0)], 'Away_AvgConceded': [a.get('AvgConceded',0)],
            'Home_AvgShots': [h.get('AvgShots',0)], 'Away_AvgShots': [a.get('AvgShots',0)],
            'Home_AvgCorners': [h.get('AvgCorners',0)], 'Away_AvgCorners': [a.get('AvgCorners',0)],
            'Home_RestDays': [h['RestDays']], 'Away_RestDays': [a['RestDays']],
            'OddHome': [2.5], 'OddDraw': [3.1], 'OddAway': [2.8],
            'ImpliedProbHome': [0.4], 'ImpliedProbAway': [0.35], 'MarketMargin': [0.05]
        }
        
        df = pd.DataFrame(input_data)
        model_type = 'gb' if subscription_tier == 'gold' else 'rf'
        
        response = {
            "home": home, "away": away, "tier": subscription_tier, "model_used": model_type.upper(),
            "home_report": self.get_team_report_card(home) or {},
            "away_report": self.get_team_report_card(away) or {},
            "details": self.get_matchup_stats(home, away) or {}
        }

        # 1. WIN PROBABILITIES
        wld_model = self.get_model('WLD', model_type)
        win_prob = {'home': 33, 'draw': 34, 'away': 33}
        
        if wld_model:
            # Engineer features using pre-loaded scaler
            X = self.engineer.transform(df)
            probs = wld_model.predict_proba(X)[0]
            # Map classes: 0=Away, 1=Draw, 2=Home (Standard sklearn alphabetical)
            # Adjust if your data_loader mapped differently!
            win_prob = {'home': round(probs[2]*100,1), 'draw': round(probs[1]*100,1), 'away': round(probs[0]*100,1)}
            
            top = max(win_prob.values())
            l, c = ("HIGH", "text-green-400") if top > 60 else ("MEDIUM", "text-yellow-400") if top > 45 else ("LOW", "text-red-400")
            response['confidence'] = {'label': l, 'color': c}
        else:
            response['confidence'] = {'label': 'ERR', 'color': 'text-gray-500'}
        
        response['win_prob'] = win_prob

        # 2. TOTAL GOALS
        goals_model = self.get_model('TotalGoals', model_type)
        total_goals = 2.5 # Default fallback
        if goals_model:
            # Re-transform for regression
            X_reg = self.engineer.transform(df)
            total_goals = float(goals_model.predict(X_reg)[0])
            total_goals = max(0.5, min(total_goals, 6.0)) # Clamp
            
        response['total_goals'] = round(total_goals, 2)

        # 3. SCORE GENERATION (WINNER CONSISTENCY FIX)
        # =======================================================
        # Logic: If one team has higher win probability than the other AND draw,
        # they MUST have more goals in the final score prediction.
        
        ph = win_prob['home']
        pa = win_prob['away']
        pd = win_prob['draw']
        
        # Base goals integer (e.g. 2.4 -> 2, 2.6 -> 3)
        base_goals = int(round(total_goals))
        
        score_h = 0
        score_a = 0
        
        if ph > pa and ph > pd:
            # Home Win Scenario
            # Ensure Home has at least 1 goal, and Home > Away
            score_h = max(1, int(base_goals * 0.6) + 1) 
            score_a = max(0, base_goals - score_h)
            if score_h <= score_a: score_h = score_a + 1
            
        elif pa > ph and pa > pd:
            # Away Win Scenario
            score_a = max(1, int(base_goals * 0.6) + 1)
            score_h = max(0, base_goals - score_a)
            if score_a <= score_h: score_a = score_h + 1
            
        else:
            # Draw Scenario
            # Even split
            score_h = max(1, base_goals // 2)
            score_a = score_h
            
        response['score'] = {"home": score_h, "away": score_a}
        # =======================================================

        # Debug Print to Console (Verify 1-1 Loop is broken)
        print(f"\n🔮 [PREDICTION] {home} vs {away}")
        print(f"   📊 Probs: H={ph}% D={pd}% A={pa}%")
        print(f"   ⚽ Goals: {total_goals} -> Score: {score_h}-{score_a}")

        # 4. PREMIUM STATS
        if subscription_tier == 'gold':
            bm = self.get_model('BTTS', 'rf')
            if bm: response['btts'] = round(bm.predict_proba(self.engineer.transform(df))[0][1]*100, 1)
            
            om = self.get_model('Over25', 'rf')
            if om: response['over25'] = round(om.predict_proba(self.engineer.transform(df))[0][1]*100, 1)

        return response

if __name__ == "__main__":
    p = MatchPredictor()
    print("✅ Main loaded.")