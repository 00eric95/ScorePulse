import pandas as pd
import numpy as np

class AdvancedFeatureGenerator:
    def __init__(self):
        pass

    def generate(self, df):
        """
        Enriches the dataframe with Lagged (History), Context, and Derived features.
        """
        print("⚡ Generating Advanced Features (Momentum, Elo, Odds, Fatigue)...")
        
        # --- STEP 1: PREPARE TEAM-CENTRIC DATA ---
        home_cols = ['MatchDate', 'HomeTeam', 'FTHome', 'FTAway', 'FTResult', 'HomeShots', 'HomeCorners']
        home_df = df[home_cols].copy()
        home_df.columns = ['Date', 'Team', 'GoalsFor', 'GoalsAgainst', 'Result', 'Shots', 'Corners']
        home_df['Points'] = home_df['Result'].map({'H': 3, 'D': 1, 'A': 0})
        
        away_cols = ['MatchDate', 'AwayTeam', 'FTAway', 'FTHome', 'FTResult', 'AwayShots', 'AwayCorners']
        away_df = df[away_cols].copy()
        away_df.columns = ['Date', 'Team', 'GoalsFor', 'GoalsAgainst', 'Result', 'Shots', 'Corners']
        away_df['Points'] = away_df['Result'].map({'H': 0, 'D': 1, 'A': 3})
        
        team_df = pd.concat([home_df, away_df]).sort_values(['Team', 'Date'])
        
        # --- STEP 2: CALCULATE ROLLING STATS ---
        grouped = team_df.groupby('Team')
        
        team_df['Roll_Goals'] = grouped['GoalsFor'].transform(lambda x: x.rolling(window=5, closed='left').mean())
        team_df['Roll_Conceded'] = grouped['GoalsAgainst'].transform(lambda x: x.rolling(window=5, closed='left').mean())
        team_df['Roll_Points'] = grouped['Points'].transform(lambda x: x.rolling(window=5, closed='left').sum())
        team_df['Roll_Shots'] = grouped['Shots'].transform(lambda x: x.rolling(window=5, closed='left').mean())
        team_df['Roll_Corners'] = grouped['Corners'].transform(lambda x: x.rolling(window=5, closed='left').mean())
        
        team_df['LastMatchDate'] = grouped['Date'].shift(1)
        team_df['RestDays'] = (team_df['Date'] - team_df['LastMatchDate']).dt.days
        team_df['RestDays'] = team_df['RestDays'].fillna(7).clip(upper=14)
        
        team_df = team_df.fillna(0)

        # --- STEP 3: MERGE BACK ---
        cols_to_merge = ['Date', 'Team', 'Roll_Goals', 'Roll_Conceded', 'Roll_Points', 'Roll_Shots', 'Roll_Corners', 'RestDays']
        
        df = df.merge(team_df[cols_to_merge], left_on=['MatchDate', 'HomeTeam'], right_on=['Date', 'Team'], how='left')
        df = df.rename(columns={
            'Roll_Goals': 'Home_AvgGoals', 'Roll_Conceded': 'Home_AvgConceded', 
            'Roll_Points': 'Home_RecentPoints', 'Roll_Shots': 'Home_AvgShots', 
            'Roll_Corners': 'Home_AvgCorners', 'RestDays': 'Home_RestDays'
        }).drop(columns=['Date', 'Team'])
        
        df = df.merge(team_df[cols_to_merge], left_on=['MatchDate', 'AwayTeam'], right_on=['Date', 'Team'], how='left')
        df = df.rename(columns={
            'Roll_Goals': 'Away_AvgGoals', 'Roll_Conceded': 'Away_AvgConceded', 
            'Roll_Points': 'Away_RecentPoints', 'Roll_Shots': 'Away_AvgShots', 
            'Roll_Corners': 'Away_AvgCorners', 'RestDays': 'Away_RestDays'
        }).drop(columns=['Date', 'Team'])

        # --- STEP 4: DERIVED FEATURES (The Fix is Here) ---
        
        # Elo Metrics
        df['EloDifference'] = df['HomeElo'] - df['AwayElo']
        
        # Safe Division for Elo Advantage
        total_elo = df['HomeElo'] + df['AwayElo']
        df['EloAdvantage'] = df['EloDifference'] / total_elo
        df['EloAdvantage'] = df['EloAdvantage'].replace([np.inf, -np.inf], 0).fillna(0)
        
        # Momentum
        if 'Form3Home' in df.columns and 'Form5Home' in df.columns:
            df['Home_Momentum'] = df['Form3Home'] - (df['Form5Home'] - df['Form3Home'])
            df['Away_Momentum'] = df['Form3Away'] - (df['Form5Away'] - df['Form3Away'])
        else:
            df['Home_Momentum'] = 0
            df['Away_Momentum'] = 0

        # Market Metrics - SAFE DIVISION
        # We replace 0 with NaN first to avoid division by zero error, or handle inf after
        with np.errstate(divide='ignore'):
            df['ImpliedProbHome'] = 1 / df['OddHome']
            df['ImpliedProbDraw'] = 1 / df['OddDraw']
            df['ImpliedProbAway'] = 1 / df['OddAway']

        # CRITICAL FIX: Replace Infinity with NaN
        # This allows data_loader.py to drop these bad rows later
        cols_to_check = ['ImpliedProbHome', 'ImpliedProbDraw', 'ImpliedProbAway']
        df[cols_to_check] = df[cols_to_check].replace([np.inf, -np.inf], np.nan)
        
        # Market Margin
        df['MarketMargin'] = (df['ImpliedProbHome'] + df['ImpliedProbDraw'] + df['ImpliedProbAway']) - 1

        print(f"✅ Advanced Features Generated. (Sanitized {len(df)} rows)")
        return df