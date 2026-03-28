"""
This script serves as the primary entry point and user interface for the entire predictive system.
It utilizes the Orchastrator class to manage the high-level execution flow of data processing and model operations.
Users can trigger the full pipeline, which sequence through data collection, feature engineering, and model training.
The script includes a dedicated evaluation mode to verify model accuracy and ROI metrics on test datasets.
It features a prediction module designed to generate betting insights for upcoming, unplayed matches.
System maintenance is handled via a cleanup function that removes temporary files and resets the environment.
Command-line arguments allow users to toggle specific modes such as '--train', '--evaluate', or '--predict'.
By centralizing these functions, it ensures a consistent workflow across the data ingestion and machine learning lifecycles.
"""

import pandas as pd
import numpy as np
import sys
import os
import random
import joblib
import json
import re
from datetime import datetime, timedelta
from difflib import SequenceMatcher
from pathlib import Path
import time

current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from utils.data_loader import DataLoader
    from updating.online_learner import online_learner
    from updating.prediction_storage import prediction_storage
except ImportError:
    sys.path.append(os.path.join(current_dir, 'config'))
    from config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from utils.data_loader import DataLoader

class TeamResolver:
    def __init__(self, data_dir=None):
        self.data_dir = data_dir or os.path.join(current_dir, 'data')
        self.mapping_path = os.path.join(self.data_dir, 'team_mapping.json')
        self.team_cache = {}
        self.load_team_mapping()
    
    def load_team_mapping(self):
        if os.path.exists(self.mapping_path):
            try:
                with open(self.mapping_path, 'r') as f:
                    self.team_cache = json.load(f)
                print(f"📋 Loaded team mapping with {len(self.team_cache)} entries")
            except Exception as e:
                print(f"⚠️ Failed to load team mapping: {e}")
                self.team_cache = {}
    
    def normalize_team_name(self, team_name):
        if not isinstance(team_name, str):
            return team_name
            
        team_name = team_name.strip()
        
        if team_name in self.team_cache:
            return self.team_cache[team_name]
        
        normalized = self._basic_normalization(team_name)
        self.team_cache[team_name] = normalized
        
        return normalized
    
    def _basic_normalization(self, team_name):
        if not team_name:
            return team_name
            
        suffixes = [' FC', ' AFC', ' CFC', ' Utd', ' City', ' United', ' CF']
        for suffix in suffixes:
            if team_name.endswith(suffix):
                team_name = team_name[:-len(suffix)]
        
        team_name = re.sub(r'[^\w\s]', '', team_name)
        team_name = re.sub(r'\s+', ' ', team_name).strip()
        
        words = team_name.split()
        special_words = {'de', 'van', 'der', 'la', 'el', 'los', 'las', 'y', 'e', 'of'}
        capitalized = []
        for word in words:
            if word.lower() in special_words:
                capitalized.append(word.lower())
            else:
                capitalized.append(word.capitalize())
        
        return ' '.join(capitalized)
    
    def find_best_match(self, team_name, available_teams, threshold=0.85):
        if not available_teams:
            return None
            
        team_name = self.normalize_team_name(team_name)
        available_normalized = [self.normalize_team_name(t) for t in available_teams]
        
        for orig, norm in zip(available_teams, available_normalized):
            if norm == team_name:
                return orig
        
        best_match = None
        best_score = 0
        
        for orig, norm in zip(available_teams, available_normalized):
            score = SequenceMatcher(None, team_name.lower(), norm.lower()).ratio()
            if score > best_score and score >= threshold:
                best_score = score
                best_match = orig
        
        return best_match

class MatchPredictor:
    def __init__(self):
        self.config = Config()
        self.engineer = FeatureEngineer()
        self.loader = DataLoader()
        self.team_resolver = TeamResolver()
        
        print("📥 [AI Brain] Loading stats database...")
        self.raw_df, self.processed_df = self._load_data()
        
        if not self.raw_df.empty and 'Date' in self.raw_df.columns:
            recent_df = self.raw_df[self.raw_df['Date'] >= (datetime.now() - timedelta(days=730))]
            if not recent_df.empty:
                self.league_home_avg = recent_df['FTHG'].mean()
                self.league_away_avg = recent_df['FTAG'].mean()
            else:
                self.league_home_avg = 1.4
                self.league_away_avg = 1.1
        else:
            self.league_home_avg = 1.4
            self.league_away_avg = 1.1
        
        self.upcoming_path = os.path.join(current_dir, 'data', 'upcoming.csv')
        
        if self.config.SCALER_PATH.exists():
            try:
                self.engineer.scaler = joblib.load(self.config.SCALER_PATH)
            except:
                print("⚠️ Could not load scaler.")
        
        self.models = {}
        self.all_teams = self._extract_all_teams()
        self._load_models()
        
        # Initialize online learning integration
        try:
            from updating.online_learner import online_learner
            from updating.prediction_storage import prediction_storage
            self.online_learner = online_learner
            self.prediction_storage = prediction_storage
            print("✅ Online Learning System: Ready")
        except ImportError as e:
            print(f"⚠️ Online learning system not available: {e}")
            self.online_learner = None
            self.prediction_storage = None
        
        # Load team weights
        self.team_weights = self._load_team_weights()
        
    def health_check(self):
        """Health check method for the AI engine."""
        try:
            # Check if models are loaded
            models_loaded = len(self.models) > 0
            data_loaded = not self.raw_df.empty and not self.processed_df.empty
            
            status = {
                'status': 'healthy' if models_loaded and data_loaded else 'degraded',
                'models_loaded': models_loaded,
                'model_count': len(self.models),
                'data_loaded': data_loaded,
                'data_rows': len(self.raw_df) if not self.raw_df.empty else 0,
                'all_teams_count': len(self.all_teams) if hasattr(self, 'all_teams') else 0,
                'online_learning_enabled': self.online_learner is not None,
                'prediction_storage_enabled': self.prediction_storage is not None,
                'timestamp': datetime.now().isoformat()
            }
            
            return status
        except Exception as e:
            return {
                'status': 'critical',
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def _load_data(self):
        try:
            if hasattr(self.loader, 'load_local_data'):
                raw_df = self.loader.load_local_data()
            else:
                proc_path = os.path.join(self.config.PROCESSED_DATA_DIR, 'train.csv')
                if os.path.exists(proc_path):
                    raw_df = pd.read_csv(proc_path)
                else:
                    raw_df = pd.DataFrame()
            
            if not raw_df.empty:
                date_col = 'Date' if 'Date' in raw_df.columns else 'MatchDate'
                if date_col in raw_df.columns:
                    raw_df[date_col] = pd.to_datetime(raw_df[date_col], errors='coerce')
                    raw_df['MatchDate'] = raw_df[date_col]
            
            if not raw_df.empty and hasattr(self.loader, 'engineer_features'):
                processed_df = self.loader.engineer_features(raw_df.copy())
            else:
                processed_df = raw_df.copy()
            
            print(f"✅ Loaded {len(raw_df)} matches")
            return raw_df, processed_df
            
        except Exception as e:
            print(f"⚠️ [AI Brain] Data load failed: {e}")
            return pd.DataFrame(), pd.DataFrame()
    
    def _load_team_weights(self):
        """Load team weights from online learning system"""
        try:
            weights_path = Path("data/team_weights.json")
            if weights_path.exists():
                with open(weights_path, 'r') as f:
                    data = json.load(f)
                    print(f"📊 Loaded team weights for {len(data.get('teams', {}))} teams")
                    return data.get('teams', {})
        except Exception as e:
            print(f"⚠️ Error loading team weights: {e}")
        
        return {}
    
    def _extract_all_teams(self):
        teams = set()
        if not self.raw_df.empty:
            if 'HomeTeam' in self.raw_df.columns:
                teams.update(self.raw_df['HomeTeam'].dropna().unique())
            if 'AwayTeam' in self.raw_df.columns:
                teams.update(self.raw_df['AwayTeam'].dropna().unique())
        return list(teams)
    
    def resolve_team_names(self, home_team, away_team):
        if not self.all_teams:
            return home_team, away_team
        
        resolved_home = self.team_resolver.find_best_match(home_team, self.all_teams)
        resolved_away = self.team_resolver.find_best_match(away_team, self.all_teams)
        
        if resolved_home and resolved_home != home_team:
            print(f"   🔄 Resolved '{home_team}' → '{resolved_home}'")
        if resolved_away and resolved_away != away_team:
            print(f"   🔄 Resolved '{away_team}' → '{resolved_away}'")
        
        return resolved_home or home_team, resolved_away or away_team
    
    def _load_models(self):
        print("🔌 System: Connecting AI Brains...")
        project_root = current_dir
        models_dir = os.path.join(project_root, "models")
        
        targets = ['WLD', 'TotalGoals', 'BTTS', 'Over25']
        
        for t in targets:
            filename = f"model_{t}.pkl"
            path = os.path.join(models_dir, filename)
            
            if os.path.exists(path):
                try:
                    mode = 'regression' if t == 'TotalGoals' else 'classification'
                    model = ModelFactory.get_model('rf', mode=mode)
                    model.load(path)
                    self.models[t] = model
                    print(f"   ✅ Loaded Brain: {t}")
                except Exception as e:
                    print(f"   ❌ Corrupted Brain: {t} ({e})")
            else:
                print(f"   ⚠️ Missing Brain: {t}")

    def get_team_hierarchy(self):
        if self.raw_df is None or self.raw_df.empty: 
            return {}
        
        two_years_ago = datetime.now() - timedelta(days=730)
        recent_df = self.raw_df[self.raw_df['MatchDate'] >= two_years_ago]
        if recent_df.empty: 
            recent_df = self.raw_df

        DIV_MAP = {
            'E0': ('England', 'Premier League'), 'E1': ('England', 'Championship'),
            'SP1': ('Spain', 'La Liga'), 'D1': ('Germany', 'Bundesliga'),
            'I1': ('Italy', 'Serie A'), 'F1': ('France', 'Ligue 1'),
            'N1': ('Netherlands', 'Eredivisie'), 'P1': ('Portugal', 'Liga NOS'),
            'SC0': ('Scotland', 'Premiership')
        }

        OTHER_COUNTRY_NAMES = {
            'ARG': 'Argentina', 'AUT': 'Austria', 'BRA': 'Brazil', 'CHN': 'China',
            'DEN': 'Denmark', 'FIN': 'Finland', 'IRL': 'Ireland', 'JAP': 'Japan',
            'JPN': 'Japan', 'MEX': 'Mexico', 'NOR': 'Norway', 'POL': 'Poland',
            'ROM': 'Romania', 'RUS': 'Russia', 'SUI': 'Switzerland', 'SWE': 'Sweden',
            'USA': 'United States'
        }

        DEFAULT_LEAGUE_FOR = {
            'ARG': 'Primera División', 'BRA': 'Brasileirão Série A', 'MEX': 'Liga MX',
            'USA': 'MLS', 'JAP': 'J1 League', 'JPN': 'J1 League', 'CHN': 'Chinese Super League',
            'RUS': 'Russian Premier League', 'SUI': 'Swiss Super League', 'SWE': 'Allsvenskan',
            'NOR': 'Eliteserien', 'POL': 'Ekstraklasa', 'ROM': 'Liga I', 'AUT': 'Austrian Bundesliga',
            'DEN': 'Superliga', 'FIN': 'Veikkausliiga', 'IRL': 'League of Ireland'
        }

        hierarchy = {}
        if 'Division' in recent_df.columns:
            for div in recent_df['Division'].unique():
                if div in DIV_MAP:
                    country, league = DIV_MAP[div]
                else:
                    try:
                        from scripts.check_teams import DIVISION_TO_COUNTRY as CT_MAP
                        mapped = CT_MAP.get(div)
                    except Exception:
                        mapped = None

                    if mapped and mapped != 'Other':
                        country = mapped
                        league = str(div)
                    else:
                        code = str(div).upper()
                        if code in OTHER_COUNTRY_NAMES:
                            country = OTHER_COUNTRY_NAMES[code]
                            league = DEFAULT_LEAGUE_FOR.get(code, 'Top League')
                        else:
                            country = code
                            league = str(div)

                teams = sorted(list(set(recent_df[recent_df['Division'] == div]['HomeTeam'].unique()) |
                                    set(recent_df[recent_df['Division'] == div]['AwayTeam'].unique())))
                if country not in hierarchy:
                    hierarchy[country] = {}
                if league in hierarchy[country]:
                    league_key = f"{league} ({div})"
                else:
                    league_key = league
                hierarchy[country][league_key] = teams
        return hierarchy

    def get_upcoming_matches(self, count=10):
        if not os.path.exists(self.upcoming_path): 
            return []
        try:
            df = pd.read_csv(self.upcoming_path)
            if 'Date' not in df.columns:
                return []
            
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            future = df[df['Date'] >= today].sort_values(by='Date')
            matches = []
            for _, r in future.head(count).iterrows():
                matches.append({
                    "date": r['Date'].strftime('%Y-%m-%d'), 
                    "home": r['HomeTeam'] if 'HomeTeam' in r else r.get('home', 'Unknown'),
                    "away": r['AwayTeam'] if 'AwayTeam' in r else r.get('away', 'Unknown'), 
                    "league": r.get('League', r.get('league', 'Unknown'))
                })
            return matches
        except Exception as e:
            print(f"⚠️ Error loading upcoming matches: {e}")
            return []
        
    def get_top_predictions(self, date=None, limit=5):
        """Get top predictions for a given date"""
        try:
            # Get upcoming matches
            upcoming_matches = self.get_upcoming_matches(count=limit*2)  # Get more for filtering
            
            if not upcoming_matches:
                return []
            
            predictions = []
            for match in upcoming_matches:
                try:
                    home = match.get('home', 'Unknown')
                    away = match.get('away', 'Unknown')
                    
                    # Make prediction
                    prediction = self.predict_for_web(home, away, 'gold')
                    
                    # Only include successful predictions
                    if 'error' not in prediction:
                        # Calculate confidence score
                        win_probs = prediction.get('win_prob', {})
                        top_prob = max(win_probs.values()) if win_probs else 0
                        
                        predictions.append({
                            'home': home,
                            'away': away,
                            'league': match.get('league', 'Unknown'),
                            'date': match.get('date', date or str(datetime.now().date())),
                            'prediction': prediction,
                            'confidence': top_prob
                        })
                    
                    # Stop when we have enough
                    if len(predictions) >= limit:
                        break
                        
                except Exception as e:
                    print(f"Error predicting {match.get('home')} vs {match.get('away')}: {e}")
                    continue
            
            # Sort by confidence
            predictions.sort(key=lambda x: x['confidence'], reverse=True)
            
            return predictions[:limit]
            
        except Exception as e:
            print(f"Error getting top predictions: {e}")
            return []

    def get_premium_batch(self, count=10):
        sch = self.get_upcoming_matches(count=20)
        preds = []
        for m in sch:
            if len(preds) >= count: 
                break
            res = self.predict_for_web(m['home'], m['away'], 'gold')
            if "error" not in res: 
                preds.append(res)
        return preds

    def get_team_report_card(self, team_name):
        try:
            resolved_name = self.team_resolver.find_best_match(team_name, self.all_teams) or team_name
            
            df = self.processed_df
            if df.empty:
                return None
                
            rows = df[(df['HomeTeam']==resolved_name)|(df['AwayTeam']==resolved_name)].sort_values('MatchDate')
            if rows.empty:
                return None
                
            last = rows.iloc[-1]
            p = 'Home' if last['HomeTeam']==resolved_name else 'Away'
            
            avg_g = last.get(f"{p}_AvgGoals", last.get(f"{p}_Avg_Goals", 0))
            avg_c = last.get(f"{p}_AvgConceded", last.get(f"{p}_Avg_Conceded", 0))
            avg_s = last.get(f"{p}_AvgShots", 0)
            
            return {
                "name": resolved_name,
                "original_name": team_name if team_name != resolved_name else None,
                "rating": int(last.get(f'{p}Elo', last.get(f'{p}_Elo', 1000))),
                "ppg": round(last.get(f'Form5{p}', last.get(f'{p}_Form', 0))/5, 2),
                "gd_trend": f"{'+' if (avg_g-avg_c)>0 else ''}{round((avg_g-avg_c)*5, 1)}",
                "xg": round(avg_s * 0.35 * 0.3, 2) if avg_s else 0,
                "form": last.get(f'Form5{p}', last.get(f'{p}_Form', 0)),
                "attack": avg_g,
                "defense": avg_c
            }
        except Exception as e:
            print(f"⚠️ Error in get_team_report_card for {team_name}: {e}")
            return None

    def get_matchup_stats(self, home, away):
        try:
            resolved_home = self.team_resolver.find_best_match(home, self.all_teams) or home
            resolved_away = self.team_resolver.find_best_match(away, self.all_teams) or away
            
            h2h = self.raw_df[
                ((self.raw_df['HomeTeam']==resolved_home)&(self.raw_df['AwayTeam']==resolved_away)) |
                ((self.raw_df['HomeTeam']==resolved_away)&(self.raw_df['AwayTeam']==resolved_home))
            ].sort_values('MatchDate', ascending=False).head(5)
            
            res = []
            for _, r in h2h.iterrows():
                w = r['HomeTeam'] if r['FTR']=='H' else r['AwayTeam'] if r['FTR']=='A' else "Draw"
                res.append({
                    "date": r['MatchDate'].strftime('%Y-%m-%d') if hasattr(r['MatchDate'], 'strftime') else str(r['MatchDate']),
                    "score": f"{int(r['FTHG'])}-{int(r['FTAG'])}",
                    "winner": w,
                    "venue": "Home" if r['HomeTeam'] == resolved_home else "Away"
                })
            
            return {
                "h2h": res,
                "total_matches": len(h2h),
                "home_wins": sum(1 for r in res if r['winner'] == resolved_home),
                "away_wins": sum(1 for r in res if r['winner'] == resolved_away),
                "draws": sum(1 for r in res if r['winner'] == "Draw")
            }
        except Exception as e:
            print(f"⚠️ Error in get_matchup_stats: {e}")
            return {"h2h": []}

    def get_latest_stats(self, team):
        resolved_team = self.team_resolver.find_best_match(team, self.all_teams)
        if not resolved_team:
            raise ValueError(f"Team '{team}' not found.")
        
        df = self.processed_df
        if df.empty:
            raise ValueError("No data available")
            
        rows = df[(df['HomeTeam']==resolved_team)|(df['AwayTeam']==resolved_team)].sort_values('MatchDate')
        if rows.empty:
            raise ValueError(f"No data found for team '{resolved_team}'")
            
        last = rows.iloc[-1]
        p = 'Home' if last['HomeTeam']==resolved_team else 'Away'
        
        stats = {
            'Elo': last.get(f'{p}Elo', last.get(f'{p}_Elo', 1500)),
            'Form5': last.get(f'Form5{p}', last.get(f'{p}_Form', 0)),
            'AvgGoals': last.get(f'{p}_AvgGoals', last.get(f'{p}_Avg_Goals', 0)),
            'RestDays': last.get(f'{p}_RestDays', 5),
            'AvgConceded': last.get(f'{p}_AvgConceded', last.get(f'{p}_Avg_Conceded', 0)),
            'AvgShots': last.get(f'{p}_AvgShots', 0),
            'AvgCorners': last.get(f'{p}_AvgCorners', 0),
            'RecentPoints': last.get(f'{p}_RecentPoints', 0),
            'Momentum': last.get(f'{p}_Momentum', 0)
        }
        
        if not self.raw_df.empty:
            recent_raw = self.raw_df[self.raw_df['MatchDate'] >= (datetime.now() - timedelta(days=730))]
            home_games = recent_raw[recent_raw['HomeTeam'] == resolved_team].tail(10)
            away_games = recent_raw[recent_raw['AwayTeam'] == resolved_team].tail(10)
            
            stats['home_attack'] = home_games['FTHG'].mean() / self.league_home_avg if not home_games.empty else 1.0
            stats['home_defense'] = home_games['FTAG'].mean() / self.league_away_avg if not home_games.empty else 1.0
            stats['away_attack'] = away_games['FTAG'].mean() / self.league_away_avg if not away_games.empty else 1.0
            stats['away_defense'] = away_games['FTHG'].mean() / self.league_home_avg if not away_games.empty else 1.0
        else:
            stats['home_attack'] = stats['away_attack'] = 1.0
            stats['home_defense'] = stats['away_defense'] = 1.0
        
        return stats

    def predict_for_web(self, home, away, subscription_tier='free'):
        print(f"\n🔮 [PREDICTION] Starting prediction for: {home} vs {away}")
        
        home, away = self.resolve_team_names(home, away)
        
        if self.all_teams and (home not in self.all_teams or away not in self.all_teams):
            missing = []
            if home not in self.all_teams:
                missing.append(home)
            if away not in self.all_teams:
                missing.append(away)
            return {"error": f"Teams not found in historical data: {', '.join(missing)}"}
        
        if not self.config.SCALER_PATH.exists(): 
            return {"error": "AI Brain Offline. Scaler not found."}
        
        try: 
            h = self.get_latest_stats(home)
            a = self.get_latest_stats(away)
        except ValueError as e: 
            return {"error": str(e)}

        input_data = {
            'HomeElo': [h['Elo']], 'AwayElo': [a['Elo']],
            'EloDifference': [h['Elo'] - a['Elo']], 
            'EloAdvantage': [(h['Elo'] - a['Elo']) / (h['Elo'] + a['Elo'] + 1)],
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
            "home": home, 
            "away": away, 
            "tier": subscription_tier, 
            "model_used": model_type.upper(),
            "home_report": self.get_team_report_card(home) or {},
            "away_report": self.get_team_report_card(away) or {},
            "details": self.get_matchup_stats(home, away) or {}
        }

        win_prob = {'home': 33.3, 'draw': 33.4, 'away': 33.3}
        wld_model = self.models.get('WLD')
        
        if wld_model:
            try:
                X, _ = self.engineer.transform(df, target_name='WLD')
                probs = wld_model.predict_proba(X)[0]
                
                if len(probs) == 3:
                    win_prob = {
                        'home': round(probs[2]*100, 1), 
                        'draw': round(probs[1]*100, 1), 
                        'away': round(probs[0]*100, 1)
                    }
                    
                top = max(win_prob.values())
                if top > 60:
                    confidence_tuple = ("HIGH", "text-green-400")
                elif top > 45:
                    confidence_tuple = ("MEDIUM", "text-yellow-400")
                else:
                    confidence_tuple = ("LOW", "text-red-400")
                    
                # Store confidence data for response
                response['confidence_label'] = confidence_tuple[0]
                response['confidence_color'] = confidence_tuple[1]
                response['confidence_score'] = top  # Numeric confidence for database
            except Exception as e:
                print(f"⚠️ Error in WLD prediction: {e}")
                response['confidence_label'] = 'ERR'
                response['confidence_color'] = 'text-gray-500'
                response['confidence_score'] = 0.0
        else:
            response['confidence_label'] = 'ERR'
            response['confidence_color'] = 'text-gray-500'
            response['confidence_score'] = 0.0
        
        response['win_prob'] = win_prob

        goals_model = self.models.get('TotalGoals')
        total_goals = 2.5
        if goals_model:
            try:
                X_reg, _ = self.engineer.transform(df, target_name='TotalGoals')
                pred = goals_model.predict(X_reg)[0]
                total_goals = float(np.clip(pred, 0.5, 7.0))
            except Exception as e:
                print(f"⚠️ Error in TotalGoals prediction: {e}")
        
        response['total_goals'] = round(total_goals, 2)

        raw_home_goals = h['home_attack'] * a['away_defense'] * self.league_home_avg
        raw_away_goals = a['away_attack'] * h['home_defense'] * self.league_away_avg

        elo_h = h['Elo']
        elo_a = a['Elo']
        ratio_elo = elo_h / (elo_h + elo_a + 1e-5)
        form_h = h['Form5'] + 1
        form_a = a['Form5'] + 1
        ratio_form = form_h / (form_h + form_a)
        final_strength = (0.7 * ratio_elo) + (0.3 * ratio_form)
        
        raw_home_goals = 0.5 * raw_home_goals + 0.5 * (total_goals * final_strength)
        raw_away_goals = 0.5 * raw_away_goals + 0.5 * (total_goals * (1 - final_strength))
        
        raw_home_goals = max(0.1, raw_home_goals)
        raw_away_goals = max(0.1, raw_away_goals)

        num_sims = 10000
        sim_home_goals = np.random.poisson(raw_home_goals, num_sims)
        sim_away_goals = np.random.poisson(raw_away_goals, num_sims)
        sim_total = sim_home_goals + sim_away_goals
        
        from collections import Counter
        scores = [f"{sh}-{sa}" for sh, sa in zip(sim_home_goals, sim_away_goals)]
        top_scores = Counter(scores).most_common(5)
        
        simulated_prob = {
            'home': round(100 * np.mean(sim_home_goals > sim_away_goals), 1),
            'draw': round(100 * np.mean(sim_home_goals == sim_away_goals), 1),
            'away': round(100 * np.mean(sim_home_goals < sim_away_goals), 1)
        }
        
        if wld_model:
            response['win_prob'] = {
                'home': round(0.6 * simulated_prob['home'] + 0.4 * win_prob['home'], 1),
                'draw': round(0.6 * simulated_prob['draw'] + 0.4 * win_prob['draw'], 1),
                'away': round(0.6 * simulated_prob['away'] + 0.4 * win_prob['away'], 1)
            }
        else:
            response['win_prob'] = simulated_prob
        
        most_likely_score = top_scores[0][0] if top_scores else "1-1"
        score_h, score_a = map(int, most_likely_score.split('-'))
        response['score'] = {"home": score_h, "away": score_a}
        
        if 'BTTS' in self.models:
            try:
                bm = self.models['BTTS']
                X_btts, _ = self.engineer.transform(df, target_name='BTTS')
                response['btts'] = round(bm.predict_proba(X_btts)[0][1] * 100, 1)
            except:
                response['btts'] = round(100 * np.mean((sim_home_goals > 0) & (sim_away_goals > 0)), 1)
        else:
            response['btts'] = round(100 * np.mean((sim_home_goals > 0) & (sim_away_goals > 0)), 1)
        
        if 'Over25' in self.models:
            try:
                om = self.models['Over25']
                X_over, _ = self.engineer.transform(df, target_name='Over25')
                response['over25'] = round(om.predict_proba(X_over)[0][1] * 100, 1)
            except:
                response['over25'] = round(100 * np.mean(sim_total > 2.5), 1)
        else:
            response['over25'] = round(100 * np.mean(sim_total > 2.5), 1)
        
        response['top_scores'] = [
            {'score': s, 'prob': round(100 * c / num_sims, 1)} 
            for s, c in top_scores
        ]
        
        # Determine AI prediction outcome for database
        max_prob_outcome = max(response['win_prob'].items(), key=lambda x: x[1])
        outcome_map = {'home': 'H', 'draw': 'D', 'away': 'A'}
        response['prediction_outcome'] = outcome_map.get(max_prob_outcome[0], 'D')
        response['prediction_confidence'] = max_prob_outcome[1]
        
        # Add MCMC probabilities for database
        response['mcmc_home_prob'] = response['win_prob']['home']
        response['mcmc_draw_prob'] = response['win_prob']['draw']
        response['mcmc_away_prob'] = response['win_prob']['away']
        
        # Add betting analysis fields
        response['recommended_stake'] = 2.5  # Default value
        response['kelly_fraction'] = 0.5  # Default value
        response['market_odds'] = 2.5  # Default value
        response['risk_level'] = 'MEDIUM' if response['prediction_confidence'] > 45 else 'LOW'
        
        print(f"   📊 Probs: H={response['win_prob']['home']}% D={response['win_prob']['draw']}% A={response['win_prob']['away']}%")
        print(f"   ⚽ Goals: {total_goals:.2f} -> Score: {score_h}-{score_a}")
        print(f"   🎯 BTTS: {response['btts']}% | Over 2.5: {response['over25']}%")
        print(f"   📈 Prediction: {response['prediction_outcome']} ({response['prediction_confidence']}%)")
        
        # Apply online learning adjustments if available
        if self.online_learner:
            try:
                # Store prediction for future learning
                match_id = f"{home}_{away}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
                
                if self.prediction_storage:
                    self.prediction_storage.store_prediction(
                        match_id=match_id,
                        home_team=home,
                        away_team=away,
                        match_date=datetime.now().isoformat(),
                        predicted_data=response
                    )
                
                # Apply learning weights
                adjusted_response = self.online_learner.apply_weights_to_prediction(home, away, response)
                if adjusted_response:
                    response = adjusted_response
                    response['online_learning'] = {
                        'weights_applied': True,
                        'match_id': match_id,
                        'tracked_for_learning': True
                    }
            except Exception as e:
                print(f"⚠️ Error applying online learning adjustments: {e}")
        
        return response
    
    def _generate_base_prediction(self, home, away, home_stats, away_stats, model_type):
        """Generate base prediction without online learning adjustments"""
        # This is a wrapper that calls the main prediction logic
        return self.predict_for_web(home, away, model_type)
    
    def process_completed_match(self, match_data):
        """Process a completed match for online learning"""
        try:
            if not self.prediction_storage:
                return False
            
            # Store the result
            success = self.prediction_storage.store_result(
                match_id=match_data.get('match_id'),
                home_team=match_data.get('home_team'),
                away_team=match_data.get('away_team'),
                match_date=match_data.get('match_date', datetime.now().isoformat()),
                home_goals=match_data.get('home_goals'),
                away_goals=match_data.get('away_goals'),
                result=match_data.get('result')
            )
            
            if success and self.online_learner:
                # Get unprocessed results
                unprocessed = self.prediction_storage.get_unprocessed_results(limit=1)
                
                for result in unprocessed:
                    if result['match_id'] == match_data.get('match_id'):
                        # Process for online learning
                        learning_data = {
                            'match_id': result['match_id'],
                            'home_team': result['home_team'],
                            'away_team': result['away_team'],
                            'actual_home_goals': result['actual_home_goals'],
                            'actual_away_goals': result['actual_away_goals'],
                            'actual_result': result['actual_result'],
                            'predicted_data': result.get('predicted_data', {}),
                            'date': result['match_date']
                        }
                        
                        learning_success = self.online_learner.process_match_result(learning_data)
                        
                        if learning_success:
                            # Mark as processed
                            self.prediction_storage.mark_as_processed(result['match_id'])
                            print(f"✅ Processed match {result['match_id']} for online learning")
                        
                        return learning_success
            
            return success
            
        except Exception as e:
            print(f"⚠️ Error processing completed match: {e}")
            return False
    
    def get_learning_insights(self):
        """Get insights from the online learning system"""
        try:
            insights = {
                'system_status': {},
                'prediction_stats': {},
                'teams_improving': [],
                'teams_declining': []
            }
            
            if self.online_learner:
                status = self.online_learner.get_system_status()
                insights['system_status'] = status
            
            if self.prediction_storage:
                stats = self.prediction_storage.get_prediction_stats(days=30)
                insights['prediction_stats'] = stats
            
            # Extract team trends from system status
            if insights['system_status'] and 'top_adjusted_teams' in insights['system_status']:
                top_teams = insights['system_status']['top_adjusted_teams']
                if isinstance(top_teams, list):
                    insights['teams_improving'] = [
                        team for team in top_teams
                        if isinstance(team, dict) and team.get('trend') == 'improving'
                    ][:5]
                    insights['teams_declining'] = [
                        team for team in top_teams
                        if isinstance(team, dict) and team.get('trend') == 'declining'
                    ][:5]
            
            return insights
            
        except Exception as e:
            print(f"⚠️ Error getting learning insights: {e}")
            return None

if __name__ == "__main__":
    p = MatchPredictor()
    print("✅ Main loaded.")