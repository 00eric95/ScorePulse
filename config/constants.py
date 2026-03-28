# config/constants.py
class Constants:
    # League mappings (country, league name)
    DIVISION_MAP = {
        # England
        'E0': ('England', 'Premier League'),
        'E1': ('England', 'Championship'),
        'E2': ('England', 'League One'),
        'E3': ('England', 'League Two'),
        'EC': ('England', 'National League'),
        
        # Spain
        'SP1': ('Spain', 'La Liga'),
        'SP2': ('Spain', 'Segunda Division'),
        
        # Germany
        'D1': ('Germany', 'Bundesliga'),
        'D2': ('Germany', '2. Bundesliga'),
        
        # Italy
        'I1': ('Italy', 'Serie A'),
        'I2': ('Italy', 'Serie B'),
        
        # France
        'F1': ('France', 'Ligue 1'),
        'F2': ('France', 'Ligue 2'),
        
        # Netherlands
        'N1': ('Netherlands', 'Eredivisie'),
        
        # Portugal
        'P1': ('Portugal', 'Primeira Liga'),
        
        # Belgium
        'B1': ('Belgium', 'First Division A'),
        
        # Turkey
        'T1': ('Turkey', 'Süper Lig'),
        
        # Scotland
        'SC0': ('Scotland', 'Premiership'),
        'SC1': ('Scotland', 'Championship'),
        'SC2': ('Scotland', 'League One'),
        'SC3': ('Scotland', 'League Two'),
        
        # Others
        'G1': ('Greece', 'Super League'),
        'ARG': ('Argentina', 'Primera Division'),
        'AUT': ('Austria', 'Bundesliga'),
        'BRA': ('Brazil', 'Série A'),
        'DNK': ('Denmark', 'Superliga'),
        'FIN': ('Finland', 'Veikkausliiga'),
        'IRL': ('Ireland', 'Premier Division'),
        'JPN': ('Japan', 'J1 League'),
        'MEX': ('Mexico', 'Liga MX'),
        'NOR': ('Norway', 'Eliteserien'),
        'POL': ('Poland', 'Ekstraklasa'),
        'ROU': ('Romania', 'Liga I'),
        'RUS': ('Russia', 'Premier League'),
        'SWE': ('Sweden', 'Allsvenskan'),
        'SWZ': ('Switzerland', 'Super League'),
        'USA': ('USA', 'MLS'),
    }
    
    # Model thresholds for alert generation (0.0-1.0)
    ALERT_THRESHOLDS = {
        # Match outcome predictions
        'WLD': 0.48,      # Win/Lose/Draw confidence
        '1X2': 0.50,      # Home/Draw/Away
        
        # Goal-based markets
        'BTTS': 0.52,     # Both Teams To Score
        'OVER_1.5': 0.45, # Over 1.5 goals
        'OVER_2.5': 0.48, # Over 2.5 goals
        'OVER_3.5': 0.35, # Over 3.5 goals
        'UNDER_2.5': 0.52, # Under 2.5 goals
        
        # Asian handicaps
        'AH_0.0': 0.50,   # Asian Handicap 0.0
        'AH_0.5': 0.48,   # Asian Handicap ±0.5
        'AH_1.0': 0.46,   # Asian Handicap ±1.0
        
        # Correct score ranges
        'CS_0-0': 0.15,   # 0-0 draw
        'CS_1-0': 0.12,   # 1-0 home win
        'CS_0-1': 0.12,   # 0-1 away win
        'CS_1-1': 0.10,   # 1-1 draw
        
        # Team-specific markets
        'HALF_TIME': 0.40, # Half-time result
        'CLEAN_SHEET': 0.45, # Clean sheet probability
        'WIN_TO_NIL': 0.40, # Win to nil
    }
    
    # Feature definitions for safe model features
    SAFE_FEATURE_KEYWORDS = [
        # Averages
        'Home_Avg', 'Away_Avg',
        'Avg_GF', 'Avg_GA',  # Goals For/Against
        'Avg_xG', 'Avg_xGA', # Expected Goals
        'Avg_Shots', 'Avg_Shots_on_Target',
        'Avg_Corners', 'Avg_Fouls',
        'Avg_Cards', 'Avg_Possession',
        
        # Form indicators
        'Home_Form', 'Away_Form',
        'Form_Last_5', 'Form_Last_10',
        'Home_Form_Last_5', 'Away_Form_Last_5',
        
        # Streaks
        'Win_Streak', 'Loss_Streak',
        'Unbeaten_Streak', 'Winless_Streak',
        'BTTS_Streak', 'Clean_Sheet_Streak',
        
        # Recent performance metrics
        'Recent_GF', 'Recent_GA',
        'Recent_xG', 'Recent_xGA',
        'Recent_Shots', 'Recent_Shots_on_Target',
        
        # Head-to-head historical
        'H2H_Avg_Goals', 'H2H_BTTS_Rate',
        'H2H_Home_Wins', 'H2H_Away_Wins',
        
        # League position metrics
        'Home_Position', 'Away_Position',
        'Position_Difference',
        'Points_Per_Game_Home', 'Points_Per_Game_Away',
        
        # Goal timing patterns
        'Goals_0_15', 'Goals_15_30', 'Goals_30_45',
        'Goals_45_60', 'Goals_60_75', 'Goals_75_90',
        
        # Statistical aggregates
        'Std_Dev_Goals', 'Std_Dev_xG',
        'Median_Goals', 'Mode_Result',
        
        # Derived metrics
        'Goal_Difference', 'xG_Difference',
        'Strength_Index', 'Momentum_Index',
    ]
    
    # Features that should never be used as model inputs (data leakage risks)
    FORBIDDEN_FEATURES = [
        # Identifiers
        'HomeTeam', 'AwayTeam', 'Date', 'Time',
        'Season', 'Div', 'League', 'Country',
        
        # Match result data (target leakage)
        'FTHG', 'FTAG',              # Full Time Home/Away Goals
        'FTR',                       # Full Time Result (H/D/A)
        'HTHG', 'HTAG',              # Half Time Home/Away Goals
        'HTR',                       # Half Time Result
        'HS', 'AS',                  # Shots
        'HST', 'AST',                # Shots on Target
        'HC', 'AC',                  # Corners
        'HF', 'AF',                  # Fouls
        'HY', 'AY', 'HR', 'AR',      # Cards
        'B365H', 'B365D', 'B365A',   # Betting odds
        'BbMxH', 'BbMxD', 'BbMxA',   # Max odds
        'BbAvH', 'BbAvD', 'BbAvA',   # Average odds
        
        # Post-match statistics
        'Referee', 'Attendance',
        'Match_ID', 'Fixture_ID',
        'Match_Link', 'Source_URL',
        
        # Derived from future information
        'Home_Rank_After_Match', 'Away_Rank_After_Match',
        'Home_Points_After_Match', 'Away_Points_After_Match',
        'Promotion_Status', 'Relegation_Status',
        
        # In-play data
        'Live_Score', 'Live_Corners', 'Live_Cards',
        'Live_Substitutions', 'Live_Possession',
        
        # Betting market data
        'Closing_Odds_Home', 'Closing_Odds_Draw', 'Closing_Odds_Away',
        'Opening_Odds_Home', 'Opening_Odds_Draw', 'Opening_Odds_Away',
        'Odds_Movement', 'Market_Volume',
        
        # Advanced metrics requiring post-match calculation
        'Expected_Points', 'xPoints',
        'Post_Match_xG', 'Post_Match_xGA',
        'Performance_Rating', 'Fairness_Index',
    ]
    
    # Additional useful constants
    LEAGUE_LEVELS = {
        'TOP': ['E0', 'SP1', 'D1', 'I1', 'F1'],
        'MID': ['E1', 'SP2', 'D2', 'I2', 'F2', 'N1', 'P1'],
        'LOWER': ['E2', 'E3', 'EC', 'SC0', 'SC1', 'SC2', 'SC3'],
        'INTERNATIONAL': ['ARG', 'BRA', 'MEX', 'USA', 'JPN']
    }
    
    SEASON_MONTHS = {
        'START': 8,   # August (main European leagues)
        'END': 5,     # May
        'WINTER_BREAK': [12, 1],  # December-January
        'SUMMER_BREAK': [6, 7]    # June-July
    }