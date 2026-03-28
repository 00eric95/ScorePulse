"""
An algorithmic factory that derives complex performance indicators like 'Attack Efficiency' and 'Defense Resilience.'
It focuses on rolling averages and momentum-based features to capture the current 'form' of home and away teams.
The generator uses epsilon-safe division to prevent mathematical errors when processing teams with zero goals or shots.
It calculates 'Dominance Ratios' by combining shots and corners to estimate the pressure exerted during a match.
This module adds the 'Expert Knowledge' layer to the raw data, identifying the subtle patterns that drive match outcomes.
"""

import pandas as pd
import numpy as np
import sys
import os

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

class AdvancedFeatureGenerator:
    def __init__(self, use_data_loader_features=True):
        """
        Initialize feature generator.
        
        Args:
            use_data_loader_features: If True, will check for existing DataLoader features
                                     and only add missing advanced features
        """
        self.use_data_loader_features = use_data_loader_features
        
        # Define expected DataLoader feature names to check for
        self.dataloader_features = [
            'Home_Avg_Goals', 'Away_Avg_Goals', 'Home_Avg_Conceded', 'Away_Avg_Conceded',
            'Home_Form', 'Away_Form', 'Home_Streak', 'Away_Streak',
            'Home_Elo', 'Away_Elo', 'H_Attack', 'A_Attack', 'H_Defense', 'A_Defense',
            'HomeTeam', 'AwayTeam', 'Date', 'FTHG', 'FTAG', 'FTR', 'TotalGoals'
        ]

    def _has_dataloader_features(self, df):
        """Check if DataLoader features are already present."""
        existing_features = [col for col in self.dataloader_features if col in df.columns]
        return len(existing_features) > 10  # If most features are present

    def generate(self, df):
        """
        Enriches the dataframe with Lagged (History), Context, and Derived features.
        Uses existing DataLoader features when available to avoid duplication.
        """
        print("⚡ Generating Advanced Features...")
        
        # Check if we need to compute basic features or can use DataLoader's
        if self.use_data_loader_features and self._has_dataloader_features(df):
            print("   ✓ Using existing DataLoader features")
            # Rename DataLoader features to match our expected names
            rename_map = {}
            if 'Home_Avg_Goals' in df.columns and 'Home_AvgGoals' not in df.columns:
                rename_map['Home_Avg_Goals'] = 'Home_AvgGoals'
            if 'Away_Avg_Goals' in df.columns and 'Away_AvgGoals' not in df.columns:
                rename_map['Away_Avg_Goals'] = 'Away_AvgGoals'
            if 'Home_Avg_Conceded' in df.columns and 'Home_AvgConceded' not in df.columns:
                rename_map['Home_Avg_Conceded'] = 'Home_AvgConceded'
            if 'Away_Avg_Conceded' in df.columns and 'Away_AvgConceded' not in df.columns:
                rename_map['Away_Avg_Conceded'] = 'Away_AvgConceded'
            
            if rename_map:
                df = df.rename(columns=rename_map)
            
            # Use existing Date column if available
            date_col = 'Date' if 'Date' in df.columns else 'MatchDate'
            
            # Prepare team-centric data only for shots, corners, and rest days
            return self._generate_advanced_only(df, date_col)
        else:
            print("   ⚠️ DataLoader features not found, generating all features from scratch")
            # Generate all features including basic ones
            return self._generate_all_features(df)

    def _generate_all_features(self, df):
        """Generate all features from scratch (legacy behavior)."""
        # --- STEP 1: PREPARE TEAM-CENTRIC DATA ---
        date_col = 'MatchDate' if 'MatchDate' in df.columns else 'Date'
        
        # Check for required columns
        required_cols = [date_col, 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTResult']
        missing_cols = [col for col in required_cols if col not in df.columns]
        if missing_cols:
            raise ValueError(f"Missing required columns: {missing_cols}")
        
        # Use FTResult if available, otherwise FTR
        result_col = 'FTResult' if 'FTResult' in df.columns else 'FTR'
        
        home_cols = [date_col, 'HomeTeam', 'FTHG', 'FTAG', result_col]
        home_df = df[home_cols].copy()
        home_df.columns = ['Date', 'Team', 'GoalsFor', 'GoalsAgainst', 'Result']
        home_df['Points'] = home_df['Result'].map({'H': 3, 'D': 1, 'A': 0})
        
        away_cols = [date_col, 'AwayTeam', 'FTAG', 'FTHG', result_col]
        away_df = df[away_cols].copy()
        away_df.columns = ['Date', 'Team', 'GoalsFor', 'GoalsAgainst', 'Result']
        away_df['Points'] = away_df['Result'].map({'H': 0, 'D': 1, 'A': 3})
        
        team_df = pd.concat([home_df, away_df]).sort_values(['Team', 'Date'])
        
        # --- STEP 2: CALCULATE ROLLING STATS ---
        grouped = team_df.groupby('Team')
        
        # Rolling Windows (Last 5 Games)
        team_df['Roll_Goals'] = grouped['GoalsFor'].transform(
            lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
        )
        team_df['Roll_Conceded'] = grouped['GoalsAgainst'].transform(
            lambda x: x.shift(1).rolling(window=5, min_periods=1).mean()
        )
        team_df['Roll_Points'] = grouped['Points'].transform(
            lambda x: x.shift(1).rolling(window=5, min_periods=1).sum()
        )
        
        # Calculate Rest Days
        team_df['LastMatchDate'] = grouped['Date'].shift(1)
        team_df['RestDays'] = (team_df['Date'] - team_df['LastMatchDate']).dt.days
        team_df['RestDays'] = team_df['RestDays'].fillna(7).clip(upper=14)
        
        team_df = team_df.fillna(0)

        # --- STEP 3: MERGE BACK TO MAIN DATAFRAME ---
        cols_to_merge = ['Date', 'Team', 'Roll_Goals', 'Roll_Conceded', 'Roll_Points', 'RestDays']
        
        # Merge Home Stats
        df = df.merge(team_df[cols_to_merge], 
                     left_on=[date_col, 'HomeTeam'], 
                     right_on=['Date', 'Team'], 
                     how='left')
        df = df.rename(columns={
            'Roll_Goals': 'Home_AvgGoals', 
            'Roll_Conceded': 'Home_AvgConceded', 
            'Roll_Points': 'Home_RecentPoints', 
            'RestDays': 'Home_RestDays'
        }).drop(columns=['Date', 'Team'])
        
        # Merge Away Stats
        df = df.merge(team_df[cols_to_merge], 
                     left_on=[date_col, 'AwayTeam'], 
                     right_on=['Date', 'Team'], 
                     how='left')
        df = df.rename(columns={
            'Roll_Goals': 'Away_AvgGoals', 
            'Roll_Conceded': 'Away_AvgConceded', 
            'Roll_Points': 'Away_RecentPoints', 
            'RestDays': 'Away_RestDays'
        }).drop(columns=['Date', 'Team'])
        
        # --- STEP 4 & 5: GENERATE ADVANCED FEATURES ---
        df = self._generate_advanced_metrics(df)
        
        print(f"✅ All Features Generated. (Rows: {len(df)}, Features: {len(df.columns)})")
        return df

    def _generate_advanced_only(self, df, date_col='Date'):
        """
        Generate only advanced metrics, assuming basic features already exist.
        """
        # Check for required basic features
        basic_features = ['Home_AvgGoals', 'Away_AvgGoals', 'Home_AvgConceded', 'Away_AvgConceded']
        missing_basic = [f for f in basic_features if f not in df.columns]
        
        if missing_basic:
            print(f"   ⚠️ Missing basic features: {missing_basic}. Generating from scratch.")
            return self._generate_all_features(df)
        
        # Generate advanced metrics
        df = self._generate_advanced_metrics(df)
        
        print(f"✅ Advanced Features Added. (Rows: {len(df)}, Total Features: {len(df.columns)})")
        return df

    def _generate_advanced_metrics(self, df):
        """Generate advanced metrics only."""
        # --- Elo Metrics (if Elo columns exist) ---
        if 'HomeElo' in df.columns and 'AwayElo' in df.columns:
            df['EloDifference'] = df['HomeElo'] - df['AwayElo']
            total_elo = df['HomeElo'] + df['AwayElo']
            df['EloAdvantage'] = df['EloDifference'] / (total_elo + 1e-5)
        else:
            df['EloDifference'] = 0
            df['EloAdvantage'] = 0

        # --- Momentum (if Form columns exist) ---
        form_columns = ['Form3Home', 'Form5Home', 'Form3Away', 'Form5Away']
        if all(col in df.columns for col in form_columns):
            df['Home_Momentum'] = df['Form3Home'] - (df['Form5Home'] - df['Form3Home'])
            df['Away_Momentum'] = df['Form3Away'] - (df['Form5Away'] - df['Form3Away'])
        else:
            # Try alternative column names
            if 'Home_Form' in df.columns and 'Away_Form' in df.columns:
                df['Home_Momentum'] = df['Home_Form']
                df['Away_Momentum'] = df['Away_Form']
            else:
                df['Home_Momentum'] = 0
                df['Away_Momentum'] = 0

        # --- Market Metrics (Odds) ---
        odds_columns = ['OddHome', 'OddDraw', 'OddAway']
        if all(col in df.columns for col in odds_columns):
            with np.errstate(divide='ignore', invalid='ignore'):
                df['ImpliedProbHome'] = 1 / df['OddHome']
                df['ImpliedProbDraw'] = 1 / df['OddDraw']
                df['ImpliedProbAway'] = 1 / df['OddAway']
            
            # Clean up
            cols_to_check = ['ImpliedProbHome', 'ImpliedProbDraw', 'ImpliedProbAway']
            df[cols_to_check] = df[cols_to_check].replace([np.inf, -np.inf], np.nan).fillna(0)
            df['MarketMargin'] = (df['ImpliedProbHome'] + df['ImpliedProbDraw'] + df['ImpliedProbAway']) - 1
        else:
            # Check for alternative odds columns
            alt_odds = ['B365H', 'B365D', 'B365A']
            if all(col in df.columns for col in alt_odds):
                with np.errstate(divide='ignore', invalid='ignore'):
                    df['ImpliedProbHome'] = 1 / df['B365H']
                    df['ImpliedProbDraw'] = 1 / df['B365D']
                    df['ImpliedProbAway'] = 1 / df['B365A']
                
                df[['ImpliedProbHome', 'ImpliedProbDraw', 'ImpliedProbAway']] = \
                    df[['ImpliedProbHome', 'ImpliedProbDraw', 'ImpliedProbAway']].replace([np.inf, -np.inf], np.nan).fillna(0)
                df['MarketMargin'] = (df['ImpliedProbHome'] + df['ImpliedProbDraw'] + df['ImpliedProbAway']) - 1
            else:
                df['ImpliedProbHome'] = 0
                df['ImpliedProbDraw'] = 0
                df['ImpliedProbAway'] = 0
                df['MarketMargin'] = 0

        # --- Advanced Metrics (Efficiency & Dominance) ---
        epsilon = 1e-5
        
        # Attack Efficiency (Goals per Shot) - estimate shots if not available
        if 'Home_AvgShots' not in df.columns:
            df['Home_AvgShots'] = df['Home_AvgGoals'] * 10  # Estimate
        if 'Away_AvgShots' not in df.columns:
            df['Away_AvgShots'] = df['Away_AvgGoals'] * 10  # Estimate
        
        h_shots_safe = df['Home_AvgShots'] + epsilon
        a_shots_safe = df['Away_AvgShots'] + epsilon
        
        df['Home_AttackEff'] = df['Home_AvgGoals'] / h_shots_safe
        df['Away_AttackEff'] = df['Away_AvgGoals'] / a_shots_safe

        # Defense Resilience (Shots Faced per Goal Conceded)
        h_conceded_safe = df['Home_AvgConceded'] + epsilon
        a_conceded_safe = df['Away_AvgConceded'] + epsilon
        
        df['Home_DefenseRes'] = (df['Home_AvgConceded'] * 8) / h_conceded_safe
        df['Away_DefenseRes'] = (df['Away_AvgConceded'] * 8) / a_conceded_safe
        
        # Dominance Ratio
        if 'Home_AvgCorners' not in df.columns:
            df['Home_AvgCorners'] = df['Home_AvgGoals'] * 5  # Estimate
        if 'Away_AvgCorners' not in df.columns:
            df['Away_AvgCorners'] = df['Away_AvgGoals'] * 5  # Estimate
        
        h_vol = df['Home_AvgShots'] + df['Home_AvgCorners']
        a_vol = df['Away_AvgShots'] + df['Away_AvgCorners']
        
        df['Home_Dominance'] = h_vol / ((df['Home_AvgConceded'] * 8) + 5 + epsilon)
        df['Away_Dominance'] = a_vol / ((df['Away_AvgConceded'] * 8) + 5 + epsilon)

        # Expected Goal Difference Proxy (xG Diff)
        df['Home_xG_Proxy'] = df['Home_AvgShots'] * df['Home_AttackEff']
        df['Away_xG_Proxy'] = df['Away_AvgShots'] * df['Away_AttackEff']
        df['xG_Diff'] = df['Home_xG_Proxy'] - df['Away_xG_Proxy']

        return df