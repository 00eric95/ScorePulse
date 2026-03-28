"""
Manages a dedicated SQLite database for archiving AI predictions and corresponding actual match results.
The module provides a persistent record for calculating long-term accuracy and ROI metrics.
It includes complex SQL queries to extract performance statistics over specific time windows (e.g., last 30 days).
The storage interface handles the serialization of complex JSON prediction data into relational tables.
This serves as the ground-truth repository for the AlertSystem and PerformanceAnalyzer modules.
"""

import pandas as pd
import numpy as np
import os
import sys
import glob
from pathlib import Path
from typing import Tuple, Dict, Any

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class DataLoader:
    def __init__(self):
        self.config = Config()
        self.raw_path = Path(self.config.RAW_DATA_DIR)
        self.processed_path = Path(self.config.PROCESSED_DATA_DIR)
        
        # Ensure 'data/processed' exists
        self.processed_path.mkdir(parents=True, exist_ok=True)

        # 🛠️ EXACT MAPPING FOR YOUR "MATCHES.CSV"
        self.MAPPING = {
            'Date':      ['MatchDate'],
            'HomeTeam':  ['HomeTeam'],
            'AwayTeam':  ['AwayTeam'],
            'FTHG':      ['FTHome'],
            'FTAG':      ['FTAway'],
            'FTR':       ['FTResult']
        }

    def load_local_data(self) -> pd.DataFrame:
        """
        Loads matches.csv directly from data/raw with improved performance.
        """
        print(f"📂 Scanning {self.raw_path}...")
        
        target_file = self.raw_path / "matches.csv"
        if not target_file.exists():
            files = list(self.raw_path.glob("*.csv"))
            if not files:
                raise FileNotFoundError(f"❌ No CSV files found in {self.raw_path}")
            target_file = files[0]

        print(f"   -> Reading {target_file.name}...")
        
        try:
            # Use dtype specification for known columns to improve memory usage
            dtype_spec = {
                'HomeTeam': 'category',
                'AwayTeam': 'category',
                'FTHG': 'int8',
                'FTAG': 'int8',
                'FTR': 'category'
            }
            
            df = pd.read_csv(target_file, encoding='latin1', low_memory=False)
            
            # 1. Standardize Columns efficiently
            rename_dict = {}
            for std_col, variations in self.MAPPING.items():
                for v in variations:
                    if v in df.columns:
                        rename_dict[v] = std_col
                        break
            
            if rename_dict:
                df = df.rename(columns=rename_dict)
            
            # 2. Check for Essentials
            required = ['Date', 'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR']
            missing = [col for col in required if col not in df.columns]
            
            if missing:
                raise ValueError(f"Missing columns after mapping: {missing}")

            # 3. Clean and optimize data types
            df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            df = df.dropna(subset=['Date']).copy()
            
            # Optimize categorical columns
            df['HomeTeam'] = df['HomeTeam'].astype('category')
            df['AwayTeam'] = df['AwayTeam'].astype('category')
            df['FTR'] = df['FTR'].astype('category')
            
            # Ensure scores are numeric
            df['FTHG'] = pd.to_numeric(df['FTHG'], errors='coerce')
            df['FTAG'] = pd.to_numeric(df['FTAG'], errors='coerce')
            
            # 4. Filter out bad rows
            mask = df[['FTHG', 'FTAG', 'FTR']].notna().all(axis=1)
            df = df[mask].copy()
            
            # Sort by date for chronological processing
            df = df.sort_values('Date').reset_index(drop=True)
            
            print(f"✅ Loaded {len(df)} matches successfully.")
            return df
            
        except Exception as e:
            print(f"❌ Critical Error reading data: {e}")
            raise

    def validate_time_order(self, df: pd.DataFrame) -> None:
        """Ensure data is strictly chronological per team."""
        print("🕒 Validating chronological order...")
        
        for team in df['HomeTeam'].cat.categories:
            # Get all matches for the team (home and away)
            team_matches = df[(df['HomeTeam'] == team) | (df['AwayTeam'] == team)]
            dates = team_matches['Date'].values
            
            # Check if dates are increasing
            if not np.all(np.diff(dates) >= np.timedelta64(0, 'ns')):
                print(f"⚠️  Warning: Non-chronological dates detected for {team}")
    
    def _calculate_elo_ratings(self, df: pd.DataFrame) -> Tuple[pd.Series, pd.Series]:
        """Calculate Elo ratings efficiently."""
        print("   Calculating Elo ratings...")
        
        # Initialize Elo ratings for all teams
        all_teams = pd.unique(pd.concat([df['HomeTeam'], df['AwayTeam']]))
        elo_dict = {team: 1500.0 for team in all_teams}
        
        # Pre-allocate arrays
        h_elos = np.empty(len(df), dtype=np.float32)
        a_elos = np.empty(len(df), dtype=np.float32)
        
        # Map results to scores
        result_map = {'H': 1.0, 'A': 0.0, 'D': 0.5}
        
        for idx, row in enumerate(df.itertuples(index=False)):
            h_team = row.HomeTeam
            a_team = row.AwayTeam
            result = row.FTR
            
            hr = elo_dict[h_team]
            ar = elo_dict[a_team]
            
            h_elos[idx] = hr
            a_elos[idx] = ar
            
            # Calculate Elo update
            prob_h = 1.0 / (1.0 + 10.0 ** ((ar - hr) / 400.0))
            score = result_map.get(result, 0.5)
            
            # Update Elo ratings
            elo_dict[h_team] = hr + 20.0 * (score - prob_h)
            elo_dict[a_team] = ar + 20.0 * ((1.0 - score) - (1.0 - prob_h))
        
        return h_elos, a_elos
    
    def _calculate_rolling_stats(self, df: pd.DataFrame) -> pd.DataFrame:
        """Calculate rolling statistics for each team."""
        print("   Calculating rolling statistics...")
        
        # Create team-view DataFrame
        home_view = df[['Date', 'HomeTeam', 'FTHG', 'FTAG', 'FTR']].copy()
        home_view.columns = ['Date', 'Team', 'Goals_Scored', 'Goals_Conceded', 'Result']
        home_view['Points'] = home_view['Result'].map({'H': 3, 'D': 1, 'A': 0})
        
        away_view = df[['Date', 'AwayTeam', 'FTAG', 'FTHG', 'FTR']].copy()
        away_view.columns = ['Date', 'Team', 'Goals_Scored', 'Goals_Conceded', 'Result']
        away_view['Points'] = away_view['Result'].map({'A': 3, 'D': 1, 'H': 0})
        
        # Combine home and away matches
        team_df = pd.concat([home_view, away_view], ignore_index=True)
        team_df = team_df.sort_values(['Team', 'Date'])
        
        # Drop rows with missing Team
        team_df = team_df.dropna(subset=['Team'])
        
        # Calculate rolling statistics
        rolling_stats = []
        
        for team in team_df['Team'].unique():
            team_matches = team_df[team_df['Team'] == team].copy()
            
            # Calculate shifted rolling statistics
            team_matches['Avg_Goals'] = team_matches['Goals_Scored'].shift(1).rolling(5, min_periods=1).mean()
            team_matches['Avg_Conceded'] = team_matches['Goals_Conceded'].shift(1).rolling(5, min_periods=1).mean()
            team_matches['Form'] = team_matches['Points'].shift(1).rolling(5, min_periods=1).mean()
            team_matches['Streak'] = team_matches['Points'].shift(1).rolling(3, min_periods=1).sum()
            
            rolling_stats.append(team_matches)
        
        # Combine all team statistics
        team_stats = pd.concat(rolling_stats, ignore_index=True)
        team_stats = team_stats.fillna(0)
        
        return team_stats[['Date', 'Team', 'Avg_Goals', 'Avg_Conceded', 'Form', 'Streak']]
    
    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Generates Elo Ratings & Rolling Stats (Anti-Leak) with improved performance.
        """
        print("⚙️  Generating Features (Elo + History)...")
        
        for col in df.select_dtypes(include=['category']).columns:
            if 0 not in df[col].cat.categories:
                df[col] = df[col].cat.add_categories([0])
                
        # --- 1. Elo Calculation ---
        h_elos, a_elos = self._calculate_elo_ratings(df)
        df = df.copy()  # Create a copy to avoid SettingWithCopyWarning
        df['Home_Elo'] = h_elos
        df['Away_Elo'] = a_elos
        
        # --- 2. Rolling Stats (Anti-Leak) ---
        team_stats = self._calculate_rolling_stats(df)
        
        # Merge home team stats
        df = pd.merge(
            df, 
            team_stats.rename(columns={
                'Avg_Goals': 'Home_Avg_Goals',
                'Avg_Conceded': 'Home_Avg_Conceded',
                'Form': 'Home_Form',
                'Streak': 'Home_Streak'
            }),
            left_on=['Date', 'HomeTeam'],
            right_on=['Date', 'Team'],
            how='left'
        ).drop(columns=['Team'])
        
        # Merge away team stats
        df = pd.merge(
            df,
            team_stats.rename(columns={
                'Avg_Goals': 'Away_Avg_Goals',
                'Avg_Conceded': 'Away_Avg_Conceded',
                'Form': 'Away_Form',
                'Streak': 'Away_Streak'
            }),
            left_on=['Date', 'AwayTeam'],
            right_on=['Date', 'Team'],
            how='left'
        ).drop(columns=['Team'])
        
        # --- 3. Attack/Defense Ratings ---
        avg_goals = df['FTHG'].mean() + 0.01
        df['H_Attack'] = df['Home_Avg_Goals'] / avg_goals
        df['A_Attack'] = df['Away_Avg_Goals'] / avg_goals
        df['H_Defense'] = df['Home_Avg_Conceded'] / avg_goals
        df['A_Defense'] = df['Away_Avg_Conceded'] / avg_goals
        
        # --- 4. Create Targets ---
        df['TotalGoals'] = df['FTHG'] + df['FTAG']
        df['Over25'] = (df['TotalGoals'] > 2.5).astype(np.int8)
        df['BTTS'] = ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(np.int8)
        
        # Fill NaN values
        df = df.fillna(0)
        
        # Optimize data types for final DataFrame
        float_cols = df.select_dtypes(include=['float64']).columns
        df[float_cols] = df[float_cols].astype(np.float32)
        
        print(f"✅ Engineered {len(df.columns)} features successfully.")
        return df
    
    def _train_val_test_split(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
        """Split data into train, validation, and test sets chronologically."""
        n = len(df)
        train_idx = int(n * 0.8)
        val_idx = int(n * 0.9)
        
        train = df.iloc[:train_idx].copy()
        val = df.iloc[train_idx:val_idx].copy()
        test = df.iloc[val_idx:].copy()
        
        return train, val, test
    
    def run(self) -> None:
        """Main pipeline execution."""
        print("🚀 Starting Local Data Pipeline...")
        
        # Load and validate data
        df = self.load_local_data()
        self.validate_time_order(df)
        
        # Engineer features
        df = self.engineer_features(df)
        
        # Split data
        train, val, test = self._train_val_test_split(df)
        
        # Save processed data
        train.to_csv(self.processed_path / "train.csv", index=False)
        val.to_csv(self.processed_path / "val.csv", index=False)
        test.to_csv(self.processed_path / "test.csv", index=False)
        
        # Print statistics
        print(f"\n📊 Data Statistics:")
        print(f"   Training set: {len(train)} matches ({len(train)/len(df)*100:.1f}%)")
        print(f"   Validation set: {len(val)} matches ({len(val)/len(df)*100:.1f}%)")
        print(f"   Test set: {len(test)} matches ({len(test)/len(df)*100:.1f}%)")
        print(f"   Total features: {len(df.columns)}")
        print(f"\n✅ Success! Data processed and saved to {self.processed_path}")

if __name__ == "__main__":
    DataLoader().run()