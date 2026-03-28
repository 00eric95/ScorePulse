# football_analytics_system.py
import pandas as pd
import numpy as np
import os
import glob
import sys
import json
import time
from datetime import datetime, timedelta
import warnings
import re
from collections import defaultdict, Counter
warnings.filterwarnings('ignore')

# Add feature generator
sys.path.append(os.path.dirname(__file__))
try:
    from utils.feature_generator import AdvancedFeatureGenerator
except:
    print("Note: feature_generator.py not found, using basic features")
    

class FootballDataProcessor:
    """Process and analyze football match data from Kaggle dataset"""
    
    def __init__(self, data_path):
        self.data_path = data_path
        self.df = None
        self.leagues_data = {}
        self.teams_data = {}
        self.features = None
        self.seasons = {}
        self.predictor = None
        
    def set_predictor(self, predictor):
        """Allows the Orchestrator to inject itself into this agent"""
        self.predictor = predictor
        
        
    def export_to_orchestrator(self, format='json'):
        """Package data for PitchCommander orchestrator"""
        export_data = {
            'metadata': {
                'export_timestamp': datetime.now().isoformat(),
                'total_matches': len(self.df),
                'data_quality_score': self._calculate_data_quality_score(),
                'coverage_period': {
                    'start': self.df['Date'].min().isoformat() if len(self.df) > 0 else None,
                    'end': self.df['Date'].max().isoformat() if len(self.df) > 0 else None
                }
            },
            'analytical_insights': {
                'team_performance': self.teams_data,
                'league_analysis': self.leagues_data,
                'trends': self._extract_key_trends(),
                'anomalies': self._detect_anomalies()
            },
            'predictive_features': {
                'available_features': list(self.df.columns),
                'feature_importance': self._calculate_feature_importance(),
                'recommended_features': self._recommend_predictive_features()
            },
            'live_context_engine': {
                'team_contexts': self._generate_team_contexts(),
                'venue_effects': self._analyze_venue_effects(),
                'temporal_patterns': self._analyze_temporal_patterns()
            }
        }
        
        if format == 'json':
            return json.dumps(export_data, default=str)
        elif format == 'dataframe':
            return {
                'main_data': self.df,
                'team_stats': pd.DataFrame(self.teams_data).T,
                'league_stats': pd.DataFrame(self.leagues_data).T
            }
        
        return export_data

    def set_orchestrator_hooks(self, orchestrator):
        """Establish bidirectional communication with orchestrator"""
        self.orchestrator = orchestrator
        
        # Register data update callback
        orchestrator.register_data_update_callback(self._on_orchestrator_update)
        
        # Set up real-time data feeds
        self.real_time_feed = {
            'team_updates': self._stream_team_updates,
            'match_events': self._stream_match_events,
            'market_changes': self._stream_market_changes
        }
    
    def _on_orchestrator_update(self, data):
        """Handle updates from orchestrator"""
        pass
    
    def _stream_team_updates(self):
        """Stream team updates"""
        pass
    
    def _stream_match_events(self):
        """Stream match events"""
        pass
    
    def _stream_market_changes(self):
        """Stream market changes"""
        pass
    
    def _calculate_data_quality_score(self):
        """Calculate data quality score"""
        if self.df is None or len(self.df) == 0:
            return 0
        return min(100, (len(self.df.columns) / 30 * 100))
    
    def _extract_key_trends(self):
        """Extract key trends from data"""
        return {}
    
    def _detect_anomalies(self):
        """Detect anomalies in data"""
        return {}
    
    def _calculate_feature_importance(self):
        """Calculate feature importance"""
        return {}
    
    def _recommend_predictive_features(self):
        """Recommend predictive features"""
        return []
    
    def _generate_team_contexts(self):
        """Generate team contexts"""
        return {}
    
    def _analyze_venue_effects(self):
        """Analyze venue effects"""
        return {}
    
    def _analyze_temporal_patterns(self):
        """Analyze temporal patterns"""
        return {}
        
    def load_data(self):
        """Load and preprocess football data from Kaggle dataset"""
        print("📊 Loading football match data...")
        
        # Find all CSV files
        csv_files = []
        for root, dirs, files in os.walk(self.data_path):
            for file in files:
                if file.endswith('.csv'):
                    csv_files.append(os.path.join(root, file))
        
        print(f"Found {len(csv_files)} CSV files")
        
        # Try to find specific league files
        league_patterns = ['premier', 'la liga', 'bundesliga', 'serie a', 'ligue 1']
        league_files = {}
        
        all_dfs = []
        for file in csv_files:
            try:
                df_temp = pd.read_csv(file, encoding='latin-1')
                
                # Extract league name from filename or content
                league_name = self._detect_league(file, df_temp)
                
                # Add league column
                df_temp['League'] = league_name
                
                # Standardize column names
                df_temp = self._standardize_columns(df_temp)
                
                # Filter for 2010 onwards
                if 'Date' in df_temp.columns:
                    df_temp['Date'] = pd.to_datetime(df_temp['Date'], errors='coerce')
                    df_temp = df_temp[df_temp['Date'] >= '2010-01-01']
                
                if len(df_temp) > 0:
                    all_dfs.append(df_temp)
                    print(f"  ✓ {league_name}: {len(df_temp)} matches")
                    
            except Exception as e:
                continue
        
        if not all_dfs:
            # Create sample data for demonstration
            print("⚠️ No valid CSV files found, creating sample data...")
            self.df = self._create_sample_data()
        else:
            self.df = pd.concat(all_dfs, ignore_index=True)
            print(f"\n✅ Loaded {len(self.df)} matches total")
        
        return self.df
    
    def _detect_league(self, filepath, df):
        """Detect league name from filepath or dataframe"""
        filename = os.path.basename(filepath).lower()
        
        # Check filename for league names
        league_map = {
            'premier': 'Premier League',
            'epl': 'Premier League',
            'england': 'Premier League',
            'laliga': 'La Liga',
            'spain': 'La Liga',
            'bundesliga': 'Bundesliga',
            'germany': 'Bundesliga',
            'serie': 'Serie A',
            'italy': 'Serie A',
            'ligue': 'Ligue 1',
            'france': 'Ligue 1',
            'champions': 'Champions League',
            'europa': 'Europa League'
        }
        
        for key, league in league_map.items():
            if key in filename:
                return league
        
        # Check dataframe columns for hints
        for col in df.columns:
            col_lower = str(col).lower()
            for key, league in league_map.items():
                if key in col_lower:
                    return league
        
        return os.path.basename(os.path.dirname(filepath)) or "Unknown League"
    
    def _standardize_columns(self, df):
        """Standardize column names across different datasets"""
        column_mapping = {
            # Date columns
            'date': 'Date', 'MatchDate': 'Date', 'match_date': 'Date',
            
            # Team columns
            'HomeTeam': 'HomeTeam', 'AwayTeam': 'AwayTeam',
            'Home': 'HomeTeam', 'Away': 'AwayTeam',
            'home_team': 'HomeTeam', 'away_team': 'AwayTeam',
            
            # Score columns
            'FTHG': 'FTHG', 'FTAG': 'FTAG',
            'HG': 'FTHG', 'AG': 'FTAG',
            'home_score': 'FTHG', 'away_score': 'FTAG',
            'HomeGoals': 'FTHG', 'AwayGoals': 'FTAG',
            
            # Result columns
            'FTR': 'FTR', 'Result': 'FTR',
            'full_time_result': 'FTR',
            
            # Odds columns
            'B365H': 'B365H', 'B365D': 'B365D', 'B365A': 'B365A',
            'AvgH': 'AvgH', 'AvgD': 'AvgD', 'AvgA': 'AvgA',
            
            # Stats columns
            'HS': 'HS', 'AS': 'AS',  # Shots
            'HST': 'HST', 'AST': 'AST',  # Shots on target
            'HC': 'HC', 'AC': 'AC',  # Corners
            'HF': 'HF', 'AF': 'AF',  # Fouls
            'HY': 'HY', 'AY': 'AY',  # Yellow cards
            'HR': 'HR', 'AR': 'AR',  # Red cards,
        }
        
        # Rename columns
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        # Create result if not present
        if 'FTR' not in df.columns and 'FTHG' in df.columns and 'FTAG' in df.columns:
            conditions = [
                df['FTHG'] > df['FTAG'],
                df['FTHG'] < df['FTAG'],
                df['FTHG'] == df['FTAG']
            ]
            choices = ['H', 'A', 'D']
            df['FTR'] = np.select(conditions, choices, default='D')
        
        # Create total goals
        if 'FTHG' in df.columns and 'FTAG' in df.columns:
            df['TotalGoals'] = df['FTHG'] + df['FTAG']
        
        return df
    
    def _normalize_team_name(self, name):
        """Resolve team name variations using database mapping"""
        try:
            from models import TeamNameMapping, db
            mapping = TeamNameMapping.query.filter_by(alias=name).first()
            return mapping.standard_name if mapping else name
        except:
            return name

    def create_team_alias_mapping(self):
        """Generate comprehensive team name mapping"""
        all_teams = set(list(self.df['HomeTeam'].unique()) + 
                        list(self.df['AwayTeam'].unique()))
        
        mapping_data = []
        for team in all_teams:
            if pd.isna(team):
                continue
            
            # Find variations
            variations = []
            # Check for common abbreviations
            if 'Manchester' in team:
                variations.append(team.replace('Manchester', 'Man'))
            if 'United' in team:
                variations.append(team.replace('United', 'Utd'))
            
            # Add to mapping
            mapping_data.append({
                'standard_name': team,
                'aliases': variations
            })
        
        return mapping_data
    
    def _create_sample_data(self):
        """Create comprehensive sample data for demonstration"""
        print("Creating sample data for demonstration...")
        
        teams = [
            'Manchester United', 'Manchester City', 'Liverpool', 'Chelsea', 'Arsenal',
            'Tottenham', 'Leicester', 'West Ham', 'Everton', 'Newcastle',
            'Real Madrid', 'Barcelona', 'Atletico Madrid', 'Sevilla', 'Valencia',
            'Bayern Munich', 'Borussia Dortmund', 'RB Leipzig', 'Bayer Leverkusen', 'Wolfsburg',
            'Juventus', 'Inter Milan', 'AC Milan', 'Napoli', 'Roma',
            'PSG', 'Marseille', 'Lyon', 'Monaco', 'Lille'
        ]
        
        leagues = ['Premier League', 'La Liga', 'Bundesliga', 'Serie A', 'Ligue 1']
        team_leagues = {}
        
        # Assign teams to leagues
        for i, team in enumerate(teams):
            league_idx = i // 6
            if league_idx < len(leagues):
                team_leagues[team] = leagues[league_idx]
        
        dates = pd.date_range('2010-01-01', '2024-12-31', periods=5000)
        np.random.seed(42)
        
        data = []
        for i in range(5000):
            home_team = np.random.choice(teams)
            away_team = np.random.choice([t for t in teams if t != home_team])
            
            # League based on home team
            league = team_leagues.get(home_team, 'Unknown')
            
            # Generate realistic scores based on team strength
            home_strength = teams.index(home_team) / len(teams)
            away_strength = teams.index(away_team) / len(teams)
            
            # Home advantage factor
            home_advantage = 0.3
            
            # Expected goals
            home_expected = 1.5 + home_strength * 1.5 + home_advantage
            away_expected = 1.5 + away_strength * 1.5 - home_advantage
            
            # Generate actual goals (Poisson distribution)
            home_goals = np.random.poisson(home_expected)
            away_goals = np.random.poisson(away_expected)
            
            # Determine result
            if home_goals > away_goals:
                result = 'H'
            elif home_goals < away_goals:
                result = 'A'
            else:
                result = 'D'
            
            # Generate match stats
            home_shots = np.random.randint(8, 25)
            away_shots = np.random.randint(8, 25)
            home_corners = np.random.randint(3, 12)
            away_corners = np.random.randint(3, 12)
            
            # Generate realistic odds
            if result == 'H':
                odds = [1.8 + np.random.random()*0.5, 3.5 + np.random.random()*1, 4.5 + np.random.random()*1.5]
            elif result == 'A':
                odds = [4.5 + np.random.random()*1.5, 3.5 + np.random.random()*1, 1.8 + np.random.random()*0.5]
            else:
                odds = [3.0 + np.random.random()*1, 2.2 + np.random.random()*0.5, 3.0 + np.random.random()*1]
            
            match_data = {
                'Date': dates[i % len(dates)],
                'HomeTeam': home_team,
                'AwayTeam': away_team,
                'FTHG': home_goals,
                'FTAG': away_goals,
                'FTR': result,
                'HS': home_shots,
                'AS': away_shots,
                'HST': max(2, int(home_shots * 0.35)),
                'AST': max(2, int(away_shots * 0.35)),
                'HC': home_corners,
                'AC': away_corners,
                'HF': np.random.randint(8, 20),
                'AF': np.random.randint(8, 20),
                'HY': np.random.randint(0, 5),
                'AY': np.random.randint(0, 5),
                'B365H': odds[0],
                'B365D': odds[1],
                'B365A': odds[2],
                'League': league,
                'Season': f"{dates[i % len(dates)].year}-{dates[i % len(dates)].year+1}" if dates[i % len(dates)].month >= 7 else f"{dates[i % len(dates)].year-1}-{dates[i % len(dates)].year}"
            }
            
            data.append(match_data)
        
        df = pd.DataFrame(data)
        df['TotalGoals'] = df['FTHG'] + df['FTAG']
        return df
    
    def generate_features(self):
        """Generate advanced features using the feature generator"""
        print("\n⚡ Generating advanced features...")
        
        try:
            # Use the AdvancedFeatureGenerator
            feature_gen = AdvancedFeatureGenerator(use_data_loader_features=False)
            self.df = feature_gen.generate(self.df)
            print(f"✅ Features generated. Total columns: {len(self.df.columns)}")
        except Exception as e:
            print(f"⚠️ Could not use feature generator: {e}")
            print("Using basic feature generation...")
            self._generate_basic_features()
        
        return self.df
    
    def _get_team_matches(self, team_name):
        """Get all matches for a team (helper method)"""
        home_matches = self.df[self.df['HomeTeam'] == team_name].copy()
        away_matches = self.df[self.df['AwayTeam'] == team_name].copy()
        
        # Create unified view
        team_matches = []
        
        for idx, row in home_matches.iterrows():
            team_matches.append({
                'Date': row['Date'],
                'Team': row['HomeTeam'],
                'Opponent': row['AwayTeam'],
                'GoalsFor': row['FTHG'],
                'GoalsAgainst': row['FTAG'],
                'Points': 3 if row['FTR'] == 'H' else 1 if row['FTR'] == 'D' else 0,
                'Result': row['FTR']
            })
        
        for idx, row in away_matches.iterrows():
            team_matches.append({
                'Date': row['Date'],
                'Team': row['AwayTeam'],
                'Opponent': row['HomeTeam'],
                'GoalsFor': row['FTAG'],
                'GoalsAgainst': row['FTHG'],
                'Points': 3 if row['FTR'] == 'A' else 1 if row['FTR'] == 'D' else 0,
                'Result': 'H' if row['FTR'] == 'A' else 'A' if row['FTR'] == 'H' else 'D'
            })
        
        if not team_matches:
            return pd.DataFrame()
        
        df = pd.DataFrame(team_matches)
        df['Date'] = pd.to_datetime(df['Date'])
        df = df.sort_values('Date')
        
        return df
    
    def calculate_team_form(self, team_name, window=5):
        """Calculate comprehensive form metrics"""
        # Get team matches
        team_matches = self._get_team_matches(team_name)
        
        if len(team_matches) < window:
            return None
        
        # Rolling statistics
        metrics = {
            'points_trend': [],
            'goals_scored_trend': [],
            'goals_conceded_trend': [],
            'xG_trend': [],  # Expected goals if available
            'possession_trend': [],
            'momentum_score': 0
        }
        
        # Calculate sliding window metrics
        for i in range(len(team_matches) - window + 1):
            window_matches = team_matches.iloc[i:i+window]
            
            # Points in window
            points = window_matches['Points'].sum()
            metrics['points_trend'].append(points)
            
            # Goals
            metrics['goals_scored_trend'].append(window_matches['GoalsFor'].mean())
            metrics['goals_conceded_trend'].append(window_matches['GoalsAgainst'].mean())
            
            # Momentum calculation (weighted by recency)
            momentum = points * 0.4 + \
                      (window_matches['GoalsFor'].mean() - window_matches['GoalsAgainst'].mean()) * 0.3 + \
                      (window_matches.iloc[-1]['Points'] * 1.5 if i == 0 else 0)  # Latest match bonus
        
        # Calculate form rating (0-100)
        if len(metrics['points_trend']) >= 3:
            recent_points = sum(metrics['points_trend'][-3:])
            goal_difference = (sum(metrics['goals_scored_trend'][-3:]) - 
                             sum(metrics['goals_conceded_trend'][-3:]))
        else:
            recent_points = sum(metrics['points_trend']) if metrics['points_trend'] else 0
            goal_difference = 0
        
        form_rating = min(100, max(0, 
            (recent_points / 9) * 60 +  # Points contribution (max 60)
            (goal_difference + 3) * 10 +  # Goal diff contribution (max 40)
            (1 if len(metrics['points_trend']) > 1 and metrics['points_trend'][-1] > metrics['points_trend'][-2] else -5)  # Trend
        ))
        
        return {
            'form_rating': form_rating,
            'momentum': 'rising' if form_rating > 60 else 'falling' if form_rating < 40 else 'stable',
            'last_5_points': sum(metrics['points_trend'][-5:]) if len(metrics['points_trend']) >= 5 else sum(metrics['points_trend']),
            'goals_scored_last_3': sum(metrics['goals_scored_trend'][-3:]) if len(metrics['goals_scored_trend']) >= 3 else sum(metrics['goals_scored_trend']),
            'goals_conceded_last_3': sum(metrics['goals_conceded_trend'][-3:]) if len(metrics['goals_conceded_trend']) >= 3 else sum(metrics['goals_conceded_trend']),
            'clean_sheets_last_5': len([x for x in metrics['goals_conceded_trend'][-5:] if x == 0]) if len(metrics['goals_conceded_trend']) >= 5 else 0
        }
    
    def get_enhanced_head_to_head(self, team1, team2, venue_specific=True, recency_weight=True):
        """Comprehensive H2H analysis with advanced metrics"""
        matches = self.df[
            ((self.df['HomeTeam'] == team1) & (self.df['AwayTeam'] == team2)) |
            ((self.df['HomeTeam'] == team2) & (self.df['AwayTeam'] == team1))
        ].sort_values('Date')
        
        if len(matches) == 0:
            return None
        
        analysis = {
            'overall': defaultdict(int),
            'home_advantage': {},
            'recent_trend': {},
            'scoring_patterns': {},
            'market_insights': {}
        }
        
        # Venue-specific analysis
        for idx, row in matches.iterrows():
            venue = 'home' if row['HomeTeam'] == team1 else 'away'
            weight = 1.0  # Base weight
            
            # Apply recency weighting
            if recency_weight:
                years_ago = (pd.Timestamp.now() - row['Date']).days / 365
                weight = max(0.1, 1.0 - (years_ago * 0.1))  # 10% decay per year
            
            # Update statistics
            if venue == 'home':
                if row['FTR'] == 'H':
                    analysis['overall']['team1_wins'] += weight
                elif row['FTR'] == 'A':
                    analysis['overall']['team2_wins'] += weight
                else:
                    analysis['overall']['draws'] += weight
            else:
                if row['FTR'] == 'A':
                    analysis['overall']['team1_wins'] += weight
                elif row['FTR'] == 'H':
                    analysis['overall']['team2_wins'] += weight
                else:
                    analysis['overall']['draws'] += weight
        
        # Calculate dominance metrics
        total_weight = sum(analysis['overall'].values())
        for key in list(analysis['overall'].keys()):
            analysis['overall'][f'{key}_rate'] = (
                analysis['overall'][key] / total_weight * 100
            ) if total_weight > 0 else 0
        
        # Scoring patterns
        analysis['scoring_patterns'] = {
            'avg_goals_per_match': matches['TotalGoals'].mean(),
            'high_scoring_rate': len(matches[matches['TotalGoals'] > 2.5]) / len(matches) * 100,
            'first_half_goals': matches.apply(
                lambda x: (x['FTHG'] + x['FTAG']) / 2, axis=1
            ).mean() if 'HTHG' in matches.columns else None,
            'comeback_occurrences': self._count_comebacks(matches, team1, team2)
        }
        
        # Market insights (if odds available)
        if 'B365H' in matches.columns:
            analysis['market_insights'] = {
                'avg_home_odds': matches['B365H'].mean(),
                'avg_draw_odds': matches['B365D'].mean(),
                'avg_away_odds': matches['B365A'].mean(),
                'upset_rate': len(matches[
                    ((matches['FTR'] == 'A') & (matches['B365A'] > matches['B365H'])) |
                    ((matches['FTR'] == 'H') & (matches['B365H'] > matches['B365A']))
                ]) / len(matches) * 100
            }
        
        return analysis
    
    def _count_comebacks(self, matches, team1, team2):
        """Count comeback occurrences in matches"""
        comebacks = 0
        for idx, row in matches.iterrows():
            if row['HomeTeam'] == team1:
                if row['FTHG'] < row['FTAG'] and row['FTR'] == 'H':  # Team1 was losing but won
                    comebacks += 1
                elif row['FTHG'] > row['FTAG'] and row['FTR'] == 'A':  # Team1 was winning but lost
                    comebacks += 1
            else:
                if row['FTAG'] < row['FTHG'] and row['FTR'] == 'A':  # Team1 was losing but won
                    comebacks += 1
                elif row['FTAG'] > row['FTHG'] and row['FTR'] == 'H':  # Team1 was winning but lost
                    comebacks += 1
        return comebacks
    
    def get_live_match_context(self, home_team, away_team, minute, score, venue=None):
        """Provide real-time contextual analysis"""
        context = {
            'historical_precedents': [],
            'comeback_likelihood': {},
            'expected_goals_remaining': {},
            'momentum_indicators': {}
        }
        
        # Get historical similar situations
        similar_matches = self.df[
            ((self.df['HomeTeam'] == home_team) | (self.df['AwayTeam'] == home_team)) &
            ((self.df['HomeTeam'] == away_team) | (self.df['AwayTeam'] == away_team))
        ].copy()
        
        if len(similar_matches) > 0:
            # Analyze goal timing patterns
            context['historical_precedents'] = self._analyze_goal_timing(similar_matches)
            
            # Calculate comeback statistics
            home_goals, away_goals = score
            goal_difference = home_goals - away_goals
            
            context['comeback_likelihood'] = {
                'home_team_comeback_rate': self._calculate_comeback_rate(
                    home_team, goal_difference * -1, minute
                ) if goal_difference < 0 else 0,
                'away_team_comeback_rate': self._calculate_comeback_rate(
                    away_team, goal_difference, minute
                ) if goal_difference > 0 else 0,
                'draw_probability': self._calculate_draw_probability(
                    home_team, away_team, goal_difference, minute
                )
            }
            
            # Expected goals remaining based on historical data
            context['expected_goals_remaining'] = {
                'home_team': self._calculate_expected_goals_remaining(
                    home_team, minute, 'home' if venue == 'home' else 'away'
                ),
                'away_team': self._calculate_expected_goals_remaining(
                    away_team, minute, 'away' if venue == 'home' else 'home'
                )
            }
        
        return context
    
    def _analyze_goal_timing(self, matches):
        """Analyze goal timing patterns"""
        return []
    
    def _calculate_draw_probability(self, home_team, away_team, goal_difference, minute):
        """Calculate draw probability"""
        return 0
    
    def _calculate_expected_goals_remaining(self, team, minute, venue):
        """Calculate expected goals remaining"""
        return 0

    def _calculate_comeback_rate(self, team, deficit, minute):
        """Calculate historical comeback rate for a team"""
        team_matches = self._get_team_matches(team)
        
        if len(team_matches) == 0:
            return 0
        
        # Filter matches where team was trailing by same deficit at similar minute
        # Note: This is a simplified version - in reality you'd need more sophisticated logic
        comeback_matches = team_matches
        
        if len(comeback_matches) == 0:
            return 0
        
        successful_comebacks = 0
        for idx, match in team_matches.iterrows():
            # Simplified logic - in reality you'd check the actual match state at specific minute
            if match['GoalsFor'] < match['GoalsAgainst'] and match['Points'] > 0:
                successful_comebacks += 1
        
        return (successful_comebacks / len(comeback_matches)) * 100 if len(comeback_matches) > 0 else 0
    
    def _generate_basic_features(self):
        """Generate basic features if advanced generator fails"""
        # Calculate rolling averages for each team
        all_matches = []
        
        for idx, row in self.df.iterrows():
            # Home team perspective
            home_match = {
                'Date': row['Date'],
                'Team': row['HomeTeam'],
                'Opponent': row['AwayTeam'],
                'GoalsFor': row['FTHG'],
                'GoalsAgainst': row['FTAG'],
                'Result': row['FTR'],
                'Home': True,
                'League': row.get('League', 'Unknown')
            }
            
            # Away team perspective
            away_match = {
                'Date': row['Date'],
                'Team': row['AwayTeam'],
                'Opponent': row['HomeTeam'],
                'GoalsFor': row['FTAG'],
                'GoalsAgainst': row['FTHG'],
                'Result': 'H' if row['FTR'] == 'A' else 'A' if row['FTR'] == 'H' else 'D',
                'Home': False,
                'League': row.get('League', 'Unknown')
            }
            
            all_matches.extend([home_match, away_match])
        
        # Create team matches dataframe
        team_matches = pd.DataFrame(all_matches)
        team_matches['Date'] = pd.to_datetime(team_matches['Date'])
        team_matches = team_matches.sort_values(['Team', 'Date'])
        
        # Calculate rolling stats
        team_stats = []
        for team in team_matches['Team'].unique():
            team_data = team_matches[team_matches['Team'] == team].copy()
            team_data = team_data.sort_values('Date')
            
            # Rolling averages (last 5 matches)
            for window in [3, 5, 10]:
                team_data[f'AvgGoals_{window}'] = team_data['GoalsFor'].shift(1).rolling(window=window, min_periods=1).mean()
                team_data[f'AvgConceded_{window}'] = team_data['GoalsAgainst'].shift(1).rolling(window=window, min_periods=1).mean()
                
                # Form (points: 3 for win, 1 for draw)
                team_data['Points'] = team_data['Result'].map({'H': 3, 'A': 0, 'D': 1})
                team_data[f'Form_{window}'] = team_data['Points'].shift(1).rolling(window=window, min_periods=1).sum()
            
            team_stats.append(team_data)
        
        team_stats_df = pd.concat(team_stats)
        
        # Merge back to main dataframe
        # Home team stats
        home_stats = team_stats_df[team_stats_df['Home'] == True].copy()
        home_stats = home_stats.rename(columns={
            f'AvgGoals_5': 'Home_AvgGoals',
            f'AvgConceded_5': 'Home_AvgConceded',
            f'Form_5': 'Home_Form'
        })
        
        self.df = self.df.merge(
            home_stats[['Date', 'Team', 'Home_AvgGoals', 'Home_AvgConceded', 'Home_Form']],
            left_on=['Date', 'HomeTeam'],
            right_on=['Date', 'Team'],
            how='left'
        ).drop(columns=['Team'])
        
        # Away team stats
        away_stats = team_stats_df[team_stats_df['Home'] == False].copy()
        away_stats = away_stats.rename(columns={
            f'AvgGoals_5': 'Away_AvgGoals',
            f'AvgConceded_5': 'Away_AvgConceded',
            f'Form_5': 'Away_Form'
        })
        
        self.df = self.df.merge(
            away_stats[['Date', 'Team', 'Away_AvgGoals', 'Away_AvgConceded', 'Away_Form']],
            left_on=['Date', 'AwayTeam'],
            right_on=['Date', 'Team'],
            how='left'
        ).drop(columns=['Team'])
        
        # Fill missing values
        for col in ['Home_AvgGoals', 'Home_AvgConceded', 'Home_Form', 
                   'Away_AvgGoals', 'Away_AvgConceded', 'Away_Form']:
            self.df[col] = self.df[col].fillna(0)
        
        # Calculate additional features
        self.df['GoalDifference'] = self.df['FTHG'] - self.df['FTAG']
        self.df['TotalShots'] = self.df.get('HS', 0) + self.df.get('AS', 0)
        self.df['TotalCorners'] = self.df.get('HC', 0) + self.df.get('AC', 0)
        
        if 'B365H' in self.df.columns:
            self.df['AvgOdds'] = (self.df['B365H'] + self.df['B365D'] + self.df['B365A']) / 3
        
        print(f"✅ Basic features generated. Total columns: {len(self.df.columns)}")
    
    def analyze_teams(self):
        """Analyze team performance across all seasons"""
        print("\n🔍 Analyzing team performance...")
        
        team_analysis = {}
        
        for team in self.df['HomeTeam'].unique():
            if pd.isna(team):
                continue
            
            # Get all matches for this team
            home_matches = self.df[self.df['HomeTeam'] == team]
            away_matches = self.df[self.df['AwayTeam'] == team]
            
            if len(home_matches) == 0 and len(away_matches) == 0:
                continue
            
            # Combine all matches
            team_matches = []
            for idx, row in home_matches.iterrows():
                team_matches.append({
                    'Date': row['Date'],
                    'Team': team,
                    'Opponent': row['AwayTeam'],
                    'GoalsFor': row['FTHG'],
                    'GoalsAgainst': row['FTAG'],
                    'Result': row['FTR'],
                    'Home': True,
                    'League': row.get('League', 'Unknown')
                })
            
            for idx, row in away_matches.iterrows():
                team_matches.append({
                    'Date': row['Date'],
                    'Team': team,
                    'Opponent': row['HomeTeam'],
                    'GoalsFor': row['FTAG'],
                    'GoalsAgainst': row['FTHG'],
                    'Result': 'H' if row['FTR'] == 'A' else 'A' if row['FTR'] == 'H' else 'D',
                    'Home': False,
                    'League': row.get('League', 'Unknown')
                })
            
            if not team_matches:
                continue
            
            team_df = pd.DataFrame(team_matches)
            team_df = team_df.sort_values('Date')
            
            # Overall stats
            total_matches = len(team_df)
            wins = len(team_df[team_df['Result'] == 'H'])
            draws = len(team_df[team_df['Result'] == 'D'])
            losses = len(team_df[team_df['Result'] == 'A'])
            
            # Home/Away stats
            home_df = team_df[team_df['Home'] == True]
            away_df = team_df[team_df['Home'] == False]
            
            home_wins = len(home_df[home_df['Result'] == 'H'])
            home_draws = len(home_df[home_df['Result'] == 'D'])
            home_losses = len(home_df[home_df['Result'] == 'A'])
            
            away_wins = len(away_df[away_df['Result'] == 'A'])  # Away win is 'A' in Result column
            away_draws = len(away_df[away_df['Result'] == 'D'])
            away_losses = len(away_df[away_df['Result'] == 'H'])
            
            # Calculate points
            points = (wins * 3) + draws
            
            # Goals statistics
            avg_goals_for = team_df['GoalsFor'].mean()
            avg_goals_against = team_df['GoalsAgainst'].mean()
            avg_goal_difference = avg_goals_for - avg_goals_against
            
            # Recent form (last 5 matches)
            recent_matches = team_df.tail(5)
            recent_wins = len(recent_matches[recent_matches['Result'] == 'H'])
            recent_draws = len(recent_matches[recent_matches['Result'] == 'D'])
            recent_losses = len(recent_matches[recent_matches['Result'] == 'A'])
            recent_points = (recent_wins * 3) + recent_draws
            
            # League performance
            leagues = team_df['League'].value_counts().to_dict()
            
            team_analysis[team] = {
                'total_matches': total_matches,
                'wins': wins,
                'draws': draws,
                'losses': losses,
                'win_rate': (wins / total_matches * 100) if total_matches > 0 else 0,
                'points': points,
                'avg_goals_for': avg_goals_for,
                'avg_goals_against': avg_goals_against,
                'avg_goal_difference': avg_goal_difference,
                'home_record': {'wins': home_wins, 'draws': home_draws, 'losses': home_losses},
                'away_record': {'wins': away_wins, 'draws': away_draws, 'losses': away_losses},
                'recent_form': {'wins': recent_wins, 'draws': recent_draws, 'losses': recent_losses, 'points': recent_points},
                'leagues': leagues,
                'first_match': team_df['Date'].min(),
                'last_match': team_df['Date'].max()
            }
        
        self.teams_data = team_analysis
        print(f"✅ Analyzed {len(team_analysis)} teams")
        return team_analysis
    
    def analyze_leagues(self):
        """Analyze league statistics"""
        print("\n🏆 Analyzing league performance...")
        
        league_analysis = {}
        
        for league in self.df['League'].unique():
            if pd.isna(league):
                continue
            
            league_df = self.df[self.df['League'] == league]
            
            if len(league_df) == 0:
                continue
            
            # Basic statistics
            total_matches = len(league_df)
            home_wins = len(league_df[league_df['FTR'] == 'H'])
            away_wins = len(league_df[league_df['FTR'] == 'A'])
            draws = len(league_df[league_df['FTR'] == 'D'])
            
            # Goals statistics
            avg_goals = league_df['TotalGoals'].mean()
            avg_home_goals = league_df['FTHG'].mean()
            avg_away_goals = league_df['FTAG'].mean()
            
            # Cards statistics (if available)
            avg_yellows = None
            avg_reds = None
            if 'HY' in league_df.columns and 'AY' in league_df.columns:
                avg_yellows = (league_df['HY'].mean() + league_df['AY'].mean())
            if 'HR' in league_df.columns and 'AR' in league_df.columns:
                avg_reds = (league_df['HR'].mean() + league_df['AR'].mean())
            
            # Team count
            teams = set(list(league_df['HomeTeam'].unique()) + list(league_df['AwayTeam'].unique()))
            
            # Season range
            seasons = league_df['Season'].nunique() if 'Season' in league_df.columns else 1
            
            # Competitive balance (std of goal difference)
            competitive_balance = league_df['GoalDifference'].abs().std() if 'GoalDifference' in league_df.columns else None
            
            league_analysis[league] = {
                'total_matches': total_matches,
                'home_win_rate': (home_wins / total_matches * 100) if total_matches > 0 else 0,
                'away_win_rate': (away_wins / total_matches * 100) if total_matches > 0 else 0,
                'draw_rate': (draws / total_matches * 100) if total_matches > 0 else 0,
                'avg_goals_per_match': avg_goals,
                'avg_home_goals': avg_home_goals,
                'avg_away_goals': avg_away_goals,
                'avg_yellow_cards': avg_yellows,
                'avg_red_cards': avg_reds,
                'unique_teams': len(teams),
                'seasons_covered': seasons,
                'competitive_balance': competitive_balance,
                'teams': list(teams)[:20]  # First 20 teams
            }
        
        self.leagues_data = league_analysis
        print(f"✅ Analyzed {len(league_analysis)} leagues")
        return league_analysis
    
    def get_head_to_head(self, team1, team2):
        """Get head-to-head statistics between two teams"""
        matches = self.df[
            ((self.df['HomeTeam'] == team1) & (self.df['AwayTeam'] == team2)) |
            ((self.df['HomeTeam'] == team2) & (self.df['AwayTeam'] == team1))
        ]
        
        if len(matches) == 0:
            return None
        
        team1_wins = 0
        team2_wins = 0
        draws = 0
        
        for idx, row in matches.iterrows():
            if row['HomeTeam'] == team1:
                if row['FTR'] == 'H':
                    team1_wins += 1
                elif row['FTR'] == 'A':
                    team2_wins += 1
                else:
                    draws += 1
            else:  # team1 is away
                if row['FTR'] == 'A':
                    team1_wins += 1
                elif row['FTR'] == 'H':
                    team2_wins += 1
                else:
                    draws += 1
        
        total_matches = len(matches)
        team1_goals = matches.apply(
            lambda x: x['FTHG'] if x['HomeTeam'] == team1 else x['FTAG'], axis=1
        ).sum()
        team2_goals = matches.apply(
            lambda x: x['FTHG'] if x['HomeTeam'] == team2 else x['FTAG'], axis=1
        ).sum()
        
        # Recent matches (last 5)
        recent_matches = matches.sort_values('Date').tail(5)
        
        return {
            'team1': team1,
            'team2': team2,
            'total_matches': total_matches,
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'team1_win_rate': (team1_wins / total_matches * 100) if total_matches > 0 else 0,
            'team2_win_rate': (team2_wins / total_matches * 100) if total_matches > 0 else 0,
            'draw_rate': (draws / total_matches * 100) if total_matches > 0 else 0,
            'team1_goals': team1_goals,
            'team2_goals': team2_goals,
            'goal_difference': team1_goals - team2_goals,
            'recent_matches': recent_matches[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']].to_dict('records'),
            'first_match': matches['Date'].min(),
            'last_match': matches['Date'].max()
        }
    
    def get_team_form(self, team, last_n=5):
        """Get recent form of a team"""
        # Get all matches for the team
        home_matches = self.df[self.df['HomeTeam'] == team].copy()
        away_matches = self.df[self.df['AwayTeam'] == team].copy()
        
        # Add result from team's perspective
        home_matches['TeamResult'] = home_matches['FTR'].apply(lambda x: 'W' if x == 'H' else 'D' if x == 'D' else 'L')
        away_matches['TeamResult'] = away_matches['FTR'].apply(lambda x: 'W' if x == 'A' else 'D' if x == 'D' else 'L')
        
        # Combine and sort
        team_matches = pd.concat([
            home_matches[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'TeamResult']].rename(
                columns={'HomeTeam': 'Team', 'AwayTeam': 'Opponent'}
            ),
            away_matches[['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'TeamResult']].rename(
                columns={'AwayTeam': 'Team', 'HomeTeam': 'Opponent'}
            )
        ])
        
        team_matches = team_matches.sort_values('Date').tail(last_n)
        
        return team_matches.to_dict('records')
    
    def predict_match(self, home_team, away_team, league=None):
        """Make a simple prediction based on historical data"""
        # Get team statistics
        home_stats = self.teams_data.get(home_team, {})
        away_stats = self.teams_data.get(away_team, {})
        
        if not home_stats or not away_stats:
            return None
        
        # Head to head
        h2h = self.get_head_to_head(home_team, away_team)
        
        # Calculate prediction factors
        factors = {}
        
        # 1. Overall win rate
        factors['home_win_rate'] = home_stats.get('win_rate', 0)
        factors['away_win_rate'] = away_stats.get('win_rate', 0)
        
        # 2. Home/Away specific
        home_record = home_stats.get('home_record', {})
        home_total = home_record.get('wins', 0) + home_record.get('losses', 0) + home_record.get('draws', 0)
        factors['home_home_win_rate'] = (home_record.get('wins', 0) / home_total * 100) if home_total > 0 else 0
        
        away_record = away_stats.get('away_record', {})
        away_total = away_record.get('wins', 0) + away_record.get('losses', 0) + away_record.get('draws', 0)
        factors['away_away_win_rate'] = (away_record.get('wins', 0) / away_total * 100) if away_total > 0 else 0
        
        # 3. Recent form
        factors['home_recent_form'] = home_stats.get('recent_form', {}).get('points', 0) / 5 if home_stats.get('recent_form', {}).get('points', 0) else 0
        factors['away_recent_form'] = away_stats.get('recent_form', {}).get('points', 0) / 5 if away_stats.get('recent_form', {}).get('points', 0) else 0
        
        # 4. Head to head
        if h2h:
            factors['h2h_advantage'] = h2h.get('team1_win_rate', 0) if h2h['team1'] == home_team else h2h.get('team2_win_rate', 0)
        else:
            factors['h2h_advantage'] = 50
        
        # 5. Goal difference
        factors['home_goal_diff'] = home_stats.get('avg_goal_difference', 0)
        factors['away_goal_diff'] = away_stats.get('avg_goal_difference', 0)
        
        # Calculate probabilities (simplified model)
        home_advantage = 15  # Base home advantage
        
        home_prob = (
            factors['home_win_rate'] * 0.2 +
            factors['home_home_win_rate'] * 0.3 +
            factors['home_recent_form'] * 20 * 0.2 +
            factors['h2h_advantage'] * 0.1 +
            factors['home_goal_diff'] * 2 * 0.1 +
            home_advantage * 0.1
        )
        
        away_prob = (
            factors['away_win_rate'] * 0.2 +
            factors['away_away_win_rate'] * 0.3 +
            factors['away_recent_form'] * 20 * 0.2 +
            (100 - factors['h2h_advantage']) * 0.1 +
            (-factors['away_goal_diff']) * 2 * 0.1
        )
        
        # Normalize
        total = home_prob + away_prob + 30  # 30% for draw
        home_prob = home_prob / total * 100
        away_prob = away_prob / total * 100
        draw_prob = 30 / total * 100
        
        # Expected score
        expected_home_goals = max(0.5, home_stats.get('avg_goals_for', 1.5) * 0.7 + away_stats.get('avg_goals_against', 1.2) * 0.3)
        expected_away_goals = max(0.5, away_stats.get('avg_goals_for', 1.2) * 0.7 + home_stats.get('avg_goals_against', 1.5) * 0.3)
        
        # Confidence based on data quality
        h2h_matches = h2h['total_matches'] if h2h else 0
        confidence = min(85, max(40, 
            (home_stats.get('total_matches', 0) / 100) * 25 +
            (away_stats.get('total_matches', 0) / 100) * 25 +
            (h2h_matches) * 2
        ))
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'prediction': {
                'home_win_probability': round(home_prob, 1),
                'draw_probability': round(draw_prob, 1),
                'away_win_probability': round(away_prob, 1),
                'expected_score': f"{expected_home_goals:.1f}-{expected_away_goals:.1f}",
                'most_likely_result': 'Home Win' if home_prob > away_prob and home_prob > draw_prob else 
                                    'Away Win' if away_prob > home_prob and away_prob > draw_prob else 'Draw',
                'confidence': round(confidence, 1)
            },
            'key_factors': {
                'home_form': f"{home_stats.get('recent_form', {}).get('points', 0)} pts in last 5",
                'away_form': f"{away_stats.get('recent_form', {}).get('points', 0)} pts in last 5",
                'head_to_head': f"{h2h['team1_wins'] if h2h and h2h['team1'] == home_team else h2h['team2_wins'] if h2h else 0}-{h2h['draws'] if h2h else 0}-{h2h['team2_wins'] if h2h and h2h['team1'] == home_team else h2h['team1_wins'] if h2h else 0}" if h2h else "No history",
                'home_advantage': f"{home_stats.get('home_record', {}).get('wins', 0)}W-{home_stats.get('home_record', {}).get('draws', 0)}D-{home_stats.get('home_record', {}).get('losses', 0)}L at home"
            }
        }


class DataValidator:
    """Comprehensive data validation system"""
    
    REQUIRED_COLUMNS = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']
    VALID_VALUES = {
        'FTR': ['H', 'A', 'D'],
        'FTHG': lambda x: 0 <= x <= 20,
        'FTAG': lambda x: 0 <= x <= 20
    }
    
    def validate_dataframe(self, df, source_name=""):
        """Perform comprehensive data validation"""
        validation_report = {
            'source': source_name,
            'valid': True,
            'issues': [],
            'warnings': [],
            'statistics': {}
        }
        
        # 1. Check required columns
        missing_columns = [col for col in self.REQUIRED_COLUMNS if col not in df.columns]
        if missing_columns:
            validation_report['valid'] = False
            validation_report['issues'].append(f"Missing columns: {missing_columns}")
        
        # 2. Validate data types
        if 'Date' in df.columns:
            try:
                df['Date'] = pd.to_datetime(df['Date'])
            except:
                validation_report['issues'].append("Invalid date format")
        
        # 3. Check value ranges
        for col, validator in self.VALID_VALUES.items():
            if col in df.columns:
                if callable(validator):
                    invalid_values = df[~df[col].apply(validator)]
                    if len(invalid_values) > 0:
                        validation_report['warnings'].append(
                            f"Invalid values in {col}: {len(invalid_values)} rows"
                        )
                elif isinstance(validator, list):
                    invalid_values = df[~df[col].isin(validator)]
                    if len(invalid_values) > 0:
                        validation_report['issues'].append(
                            f"Invalid categorical values in {col}"
                        )
        
        # 4. Check for duplicates
        duplicates = df.duplicated(subset=['Date', 'HomeTeam', 'AwayTeam']).sum()
        if duplicates > 0:
            validation_report['warnings'].append(f"Found {duplicates} duplicate matches")
        
        # 5. Generate statistics
        validation_report['statistics'] = {
            'total_rows': len(df),
            'date_range': (df['Date'].min(), df['Date'].max()) if 'Date' in df.columns else None,
            'unique_teams': len(set(list(df['HomeTeam'].unique()) + list(df['AwayTeam'].unique()))),
            'null_values': df.isnull().sum().to_dict()
        }
        
        return validation_report
    
    def clean_dataframe(self, df, validation_report):
        """Clean dataframe based on validation issues"""
        # Remove duplicates
        df = df.drop_duplicates(subset=['Date', 'HomeTeam', 'AwayTeam'])
        
        # Fix date formatting
        if 'Date' in df.columns:
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date'])
        
        # Remove invalid result values
        if 'FTR' in df.columns:
            df = df[df['FTR'].isin(self.VALID_VALUES['FTR'])]
        
        # Fix goal values
        for col in ['FTHG', 'FTAG']:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors='coerce')
                df[col] = df[col].clip(lower=0, upper=20)
        
        return df


class FootballChatbot:
    """Interactive chatbot for football analytics"""
    
    def __init__(self, data_processor):
        self.dp = data_processor
        self.context = {}
        self.user_history = []
        
    def greet(self):
        """Display welcome message"""
        welcome = """
        ╔═══════════════════════════════════════════════════════╗
        ║            ⚽ FOOTBALL ANALYTICS CHATBOT ⚽            ║
        ║            📊 2010-2025 Match Analysis               ║
        ╚═══════════════════════════════════════════════════════╝
        
        I have analyzed football data from 2010-2025 with emphasis on recent performance.
        
        📈 I can help you with:
        • Team performance analysis
        • Head-to-head records
        • League statistics
        • Match predictions
        • Recent form analysis
        • Trend identification
        
        Type 'help' for commands or 'exit' to quit.
        """
        print(welcome)
    
    def process_query(self, query):
        """Process user query and return response"""
        self.user_history.append(query)
        
        query_lower = query.lower().strip()
        
        # Check for exit commands
        if query_lower in ['exit', 'quit', 'bye', 'goodbye']:
            return "exit", None
        
        # Check for help
        if query_lower in ['help', 'commands', 'what can you do', 'options']:
            return "response", self._get_help()
        
        # Check for summary/overview
        if any(word in query_lower for word in ['summary', 'overview', 'statistics', 'stats']):
            return "response", self._get_summary()
        
        # Check for team queries
        team_match = self._extract_teams(query)
        if team_match:
            if ' vs ' in query_lower or ' versus ' in query_lower or ' against ' in query_lower:
                if len(team_match) >= 2:
                    return "response", self._handle_head_to_head(team_match[0], team_match[1])
            elif 'form' in query_lower or 'recent' in query_lower:
                return "response", self._handle_team_form(team_match[0])
            elif 'predict' in query_lower and len(team_match) >= 2:
                return "response", self._handle_prediction(team_match[0], team_match[1])
            else:
                return "response", self._handle_team_analysis(team_match[0])
        
        # Check for league queries
        league_match = self._extract_league(query)
        if league_match:
            return "response", self._handle_league_analysis(league_match)
        
        # Check for trend queries
        if any(word in query_lower for word in ['trend', 'pattern', 'analysis', 'insight']):
            return "response", self._handle_trends()
        
        # Check for comparison queries
        if 'compare' in query_lower:
            return "response", self._handle_comparison(query)
        
        # Default response
        return "response", self._get_default_response(query)
    
    def _extract_teams(self, query):
        """Extract team names from query"""
        # Common team names
        common_teams = list(self.dp.teams_data.keys())[:50]  # First 50 teams
        
        found_teams = []
        for team in common_teams:
            if team.lower() in query.lower():
                found_teams.append(team)
        
        return found_teams if found_teams else None
    
    def _extract_league(self, query):
        """Extract league name from query"""
        leagues = list(self.dp.leagues_data.keys())
        
        for league in leagues:
            if league.lower() in query.lower():
                return league
        
        # Check for common league names
        league_map = {
            'premier': 'Premier League',
            'epl': 'Premier League',
            'english': 'Premier League',
            'la liga': 'La Liga',
            'spanish': 'La Liga',
            'bundesliga': 'Bundesliga',
            'german': 'Bundesliga',
            'serie a': 'Serie A',
            'italian': 'Serie A',
            'ligue 1': 'Ligue 1',
            'french': 'Ligue 1'
        }
        
        for key, league in league_map.items():
            if key in query.lower():
                return league
        
        return None
    
    def _get_help(self):
        """Return help message"""
        help_text = """
        🆘 **COMMAND REFERENCE**
        
        📊 **TEAM ANALYSIS:**
        • "How is [Team] performing?"
        • "Show me [Team]'s statistics"
        • "What is [Team]'s recent form?"
        
        ⚔️ **HEAD-TO-HEAD:**
        • "[Team1] vs [Team2]"
        • "Head to head between [Team1] and [Team2]"
        • "History of [Team1] against [Team2]"
        
        🏆 **LEAGUE ANALYSIS:**
        • "Premier League statistics"
        • "Show me La Liga stats"
        • "Compare leagues"
        
        🔮 **PREDICTIONS:**
        • "Predict [Team1] vs [Team2]"
        • "Who will win between [Team1] and [Team2]?"
        • "Expected score for [Team1] vs [Team2]"
        
        📈 **TRENDS & INSIGHTS:**
        • "Show trends"
        • "Key insights"
        • "Recent patterns"
        
        📋 **GENERAL:**
        • "Summary" - Overall statistics
        • "Top teams" - Best performing teams
        • "Most competitive league" - League analysis
        • "Exit" - End conversation
        
        💡 **Examples:**
        • "Manchester United vs Liverpool"
        • "Barcelona recent form"
        • "Predict Real Madrid vs Barcelona"
        • "Premier League home advantage"
        """
        return help_text
    
    def _get_summary(self):
        """Get overall summary"""
        total_matches = len(self.dp.df)
        total_teams = len(self.dp.teams_data)
        total_leagues = len(self.dp.leagues_data)
        
        # Calculate average goals
        avg_goals = self.dp.df['TotalGoals'].mean() if 'TotalGoals' in self.dp.df.columns else 0
        
        # Home advantage
        home_wins = len(self.dp.df[self.dp.df['FTR'] == 'H'])
        home_win_rate = (home_wins / total_matches * 100) if total_matches > 0 else 0
        
        # Recent 5 years
        recent_date = pd.Timestamp.now() - pd.DateOffset(years=5)
        recent_matches = self.dp.df[self.dp.df['Date'] >= recent_date]
        recent_avg_goals = recent_matches['TotalGoals'].mean() if 'TotalGoals' in recent_matches.columns else 0
        
        # Top teams
        top_teams = sorted(
            self.dp.teams_data.items(),
            key=lambda x: x[1].get('win_rate', 0),
            reverse=True
        )[:5]
        
        top_teams_str = "\n".join([f"  {i+1}. {team}: {stats['win_rate']:.1f}% win rate" 
                                  for i, (team, stats) in enumerate(top_teams)])
        
        summary = f"""
        📊 **FOOTBALL DATA SUMMARY (2010-2025)**
        {'='*60}
        
        📅 **Overview:**
        • Total Matches: {total_matches:,}
        • Unique Teams: {total_teams}
        • Leagues Covered: {total_leagues}
        
        ⚽ **Match Statistics:**
        • Average Goals per Match: {avg_goals:.2f}
        • Home Win Rate: {home_win_rate:.1f}%
        • Recent 5-Year Avg Goals: {recent_avg_goals:.2f}
        
        🏆 **Top Performing Teams:**
        {top_teams_str}
        
        💡 **Key Insights:**
        • Home advantage remains significant ({home_win_rate:.1f}% home wins)
        • Recent matches show {'increasing' if recent_avg_goals > avg_goals else 'decreasing'} scoring
        • Data includes both domestic and European competitions
        """
        
        return summary
    
    def _handle_team_analysis(self, team):
        """Handle team analysis queries"""
        if team not in self.dp.teams_data:
            return f"⚠️ I don't have data for {team}. Try another team."
        
        stats = self.dp.teams_data[team]
        
        # Calculate additional metrics
        points_per_match = stats['points'] / stats['total_matches'] if stats['total_matches'] > 0 else 0
        
        # Get recent form
        recent_form = self.dp.get_team_form(team, 5)
        form_str = ""
        for match in recent_form:
            result_symbol = "✅" if match['TeamResult'] == 'W' else "➖" if match['TeamResult'] == 'D' else "❌"
            form_str += f"{result_symbol} "
        
        response = f"""
        📊 **TEAM ANALYSIS: {team.upper()}**
        {'='*60}
        
        📈 **Overall Performance (2010-2025):**
        • Matches: {stats['total_matches']}
        • Record: {stats['wins']}W - {stats['draws']}D - {stats['losses']}L
        • Win Rate: {stats['win_rate']:.1f}%
        • Points per Match: {points_per_match:.2f}
        
        🏠 **Home Record:**
        • {stats['home_record']['wins']}W - {stats['home_record']['draws']}D - {stats['home_record']['losses']}L
        • Home Win Rate: {(stats['home_record']['wins'] / (stats['home_record']['wins'] + stats['home_record']['draws'] + stats['home_record']['losses']) * 100) if (stats['home_record']['wins'] + stats['home_record']['draws'] + stats['home_record']['losses']) > 0 else 0:.1f}%
        
        ✈️ **Away Record:**
        • {stats['away_record']['wins']}W - {stats['away_record']['draws']}D - {stats['away_record']['losses']}L
        • Away Win Rate: {(stats['away_record']['wins'] / (stats['away_record']['wins'] + stats['away_record']['draws'] + stats['away_record']['losses']) * 100) if (stats['away_record']['wins'] + stats['away_record']['draws'] + stats['away_record']['losses']) > 0 else 0:.1f}%
        
        ⚽ **Goals:**
        • Avg Goals For: {stats['avg_goals_for']:.2f}
        • Avg Goals Against: {stats['avg_goals_against']:.2f}
        • Goal Difference: {stats['avg_goal_difference']:+.2f}
        
        📅 **Recent Form (Last 5):** {form_str}
        • Points in last 5: {stats['recent_form']['points']}/15
        • Record: {stats['recent_form']['wins']}W - {stats['recent_form']['draws']}D - {stats['recent_form']['losses']}L
        
        🏆 **Leagues Played In:** {', '.join(list(stats['leagues'].keys())[:3])}
        """
        
        return response
    
    def _handle_head_to_head(self, team1, team2):
        """Handle head-to-head queries"""
        h2h = self.dp.get_head_to_head(team1, team2)
        
        if not h2h:
            return f"⚠️ No historical matches found between {team1} and {team2}."
        
        response = f"""
        ⚔️ **HEAD-TO-HEAD: {team1.upper()} vs {team2.upper()}**
        {'='*60}
        
        📊 **Overall Record:**
        • Total Matches: {h2h['total_matches']}
        • {team1}: {h2h['team1_wins']} wins ({h2h['team1_win_rate']:.1f}%)
        • {team2}: {h2h['team2_wins']} wins ({h2h['team2_win_rate']:.1f}%)
        • Draws: {h2h['draws']} ({h2h['draw_rate']:.1f}%)
        
        ⚽ **Goals:**
        • {team1}: {h2h['team1_goals']} goals
        • {team2}: {h2h['team2_goals']} goals
        • Goal Difference: {h2h['goal_difference']:+}
        • Average Goals per Match: {(h2h['team1_goals'] + h2h['team2_goals']) / h2h['total_matches']:.2f}
        
        📅 **Recent Matches (Last 5):**
        """
        
        # Add recent matches
        for match in h2h['recent_matches']:
            result_symbol = "🏠" if match['FTR'] == 'H' else "✈️" if match['FTR'] == 'A' else "🤝"
            response += f"  {result_symbol} {match['Date'].strftime('%Y-%m-%d')}: {match['HomeTeam']} {match['FTHG']}-{match['FTAG']} {match['AwayTeam']}\n"
        
        response += f"""
        📆 **History:**
        • First Match: {h2h['first_match'].strftime('%Y-%m-%d')}
        • Last Match: {h2h['last_match'].strftime('%Y-%m-%d')}
        """
        
        return response
    
    def _handle_prediction(self, team1, team2):
        """Handle prediction queries"""
        prediction = self.dp.predict_match(team1, team2)
        
        if not prediction:
            return f"⚠️ Could not generate prediction for {team1} vs {team2}."
        
        response = f"""
        🔮 **MATCH PREDICTION: {team1.upper()} vs {team2.upper()}**
        {'='*60}
        
        📊 **Probabilities:**
        • {team1} Win: {prediction['prediction']['home_win_probability']}%
        • Draw: {prediction['prediction']['draw_probability']}%
        • {team2} Win: {prediction['prediction']['away_win_probability']}%
        
        ⚽ **Expected Score:**
        • Most Likely: {prediction['prediction']['expected_score']}
        • Result: {prediction['prediction']['most_likely_result']}
        
        🎯 **Confidence:**
        • Prediction Confidence: {prediction['prediction']['confidence']}%
        
        📈 **Key Factors:**
        • {team1} Form: {prediction['key_factors']['home_form']}
        • {team2} Form: {prediction['key_factors']['away_form']}
        • Head-to-Head: {prediction['key_factors']['head_to_head']}
        • {team1} Home Record: {prediction['key_factors']['home_advantage']}
        """
        
        return response
    
    def _handle_team_form(self, team):
        """Handle team form queries"""
        form = self.dp.get_team_form(team, 5)
        
        if not form:
            return f"⚠️ No recent form data for {team}."
        
        response = f"""
        📅 **RECENT FORM: {team.upper()} (Last 5 Matches)**
        {'='*60}
        """
        
        for match in form:
            result_symbol = "✅" if match['TeamResult'] == 'W' else "➖" if match['TeamResult'] == 'D' else "❌"
            date_str = match['Date'].strftime('%Y-%m-%d') if hasattr(match['Date'], 'strftime') else str(match['Date'])
            response += f"{result_symbol} {date_str}: {match['Team']} {match['FTHG']}-{match['FTAG']} {match['Opponent']}\n"
        
        return response
    
    def _handle_league_analysis(self, league):
        """Handle league analysis queries"""
        if league not in self.dp.leagues_data:
            return f"⚠️ No data available for {league}."
        
        stats = self.dp.leagues_data[league]
        
        response = f"""
        🏆 **LEAGUE ANALYSIS: {league.upper()}**
        {'='*60}
        
        📊 **Overview:**
        • Total Matches: {stats['total_matches']:,}
        • Unique Teams: {stats['unique_teams']}
        • Seasons Covered: {stats['seasons_covered']}
        
        📈 **Match Outcomes:**
        • Home Wins: {stats['home_win_rate']:.1f}%
        • Away Wins: {stats['away_win_rate']:.1f}%
        • Draws: {stats['draw_rate']:.1f}%
        
        ⚽ **Scoring Patterns:**
        • Avg Goals per Match: {stats['avg_goals_per_match']:.2f}
        • Avg Home Goals: {stats['avg_home_goals']:.2f}
        • Avg Away Goals: {stats['avg_away_goals']:.2f}
        """
        
        if stats['avg_yellow_cards']:
            response += f"• Avg Yellow Cards: {stats['avg_yellow_cards']:.1f}\n"
        if stats['avg_red_cards']:
            response += f"• Avg Red Cards: {stats['avg_red_cards']:.1f}\n"
        
        response += f"""
        🏅 **Competitive Balance:**
        • Goal Difference Std: {stats['competitive_balance']:.2f if stats['competitive_balance'] else 'N/A'}
        
        🏃‍♂️ **Top Teams ({len(stats['teams'])} total):**
        • {', '.join(stats['teams'][:5])}
        """
        
        return response
    
    def _handle_trends(self):
        """Handle trend analysis queries"""
        return """
        📈 **KEY TRENDS (2010-2025)**
        ============================================================
        
        🚀 **Scoring Trends:**
        • Overall goal scoring has remained relatively stable
        • Home advantage persists but may be decreasing slightly
        • More matches are seeing 3+ goals in recent years
        
        🏆 **Competitive Trends:**
        • Top leagues show increasing parity
        • More teams are capable of winning away matches
        • Draw rates have remained consistent
        
        ⚽ **Style Trends:**
        • Possession-based football has become more prevalent
        • High-pressing systems are more common
        • Set-piece efficiency has increased importance
        """
    
    def _handle_comparison(self, query):
        """Handle comparison queries"""
        return """
        🔄 **COMPARISON ANALYSIS**
        ============================================================
        
        To compare teams or leagues, please be more specific:
        
        Examples:
        • "Compare Manchester United and Liverpool"
        • "Compare Premier League and La Liga"
        • "Compare home vs away performance"
        
        I can analyze win rates, goal scoring, form, and more.
        """
    
    def _get_default_response(self, query):
        """Get default response for unrecognized queries"""
        return f"""
        🤔 **I'm not sure how to process: "{query}"**
        ============================================================
        
        Try one of these formats:
        
        • Team Analysis: "How is [Team] performing?"
        • Head-to-Head: "[Team1] vs [Team2]"
        • Predictions: "Predict [Team1] vs [Team2]"
        • League Stats: "Premier League statistics"
        • Form: "[Team] recent form"
        
        Type 'help' for a full list of commands.
        """


class DataCache:
    """Intelligent caching system for performance"""
    
    def __init__(self, max_size=1000):
        self.cache = {}
        self.access_times = {}
        self.max_size = max_size
        self.hit_count = 0
        self.miss_count = 0
    
    def get(self, key, compute_func=None, ttl=300):
        """Get cached data or compute if not available"""
        now = time.time()
        
        # Check cache
        if key in self.cache:
            data, expiry = self.cache[key]
            if now < expiry:
                self.hit_count += 1
                self.access_times[key] = now
                return data
        
        # Cache miss
        self.miss_count += 1
        
        if compute_func:
            # Compute and cache
            data = compute_func()
            self.set(key, data, ttl)
            return data
        
        return None
    
    def set(self, key, data, ttl=300):
        """Store data in cache"""
        # Evict if cache is full
        if len(self.cache) >= self.max_size:
            self._evict_oldest()
        
        expiry = time.time() + ttl
        self.cache[key] = (data, expiry)
        self.access_times[key] = time.time()
    
    def _evict_oldest(self):
        """Evict least recently used items"""
        if not self.access_times:
            return
        
        oldest_key = min(self.access_times.items(), key=lambda x: x[1])[0]
        del self.cache[oldest_key]
        del self.access_times[oldest_key]