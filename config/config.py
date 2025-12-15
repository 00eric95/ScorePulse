import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from a .env file if present (for local dev)
load_dotenv()

class Config:
    # ==========================================
    # 1. BASE PATHS & WEB SETTINGS (Cloud Ready)
    # ==========================================
    
    # Project Root: SCORE_PULSEv2/
    PROJECT_ROOT = Path(__file__).resolve().parent.parent
    BASE_DIR = PROJECT_ROOT # Alias for web app usage
    
    # Security (Cloud Secret or Local Dev Key)
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-please-change-in-production'
    
    # Database Setup (Cloud Postgres vs Local SQLite)
    uri = os.environ.get('DATABASE_URL')
    if uri:
        # Fix for Render/Heroku postgres:// vs postgresql://
        if uri.startswith("postgres://"):
            uri = uri.replace("postgres://", "postgresql://", 1)
        SQLALCHEMY_DATABASE_URI = uri
    else:
        # Local Development Fallback
        # Points to: SCORE_PULSEv2/soccer_match_prediction/instance/site.db
        db_path = PROJECT_ROOT / 'soccer_match_prediction' / 'instance' / 'site.db'
        SQLALCHEMY_DATABASE_URI = f'sqlite:///{db_path}'

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ==========================================
    # 2. MACHINE LEARNING PATHS (From your file)
    # ==========================================
    
    RAW_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "matches.csv"
    RAW_DATA_DIR = PROJECT_ROOT / "data" / "raw" # Added alias for flexibility
    ELO_DATA_PATH = PROJECT_ROOT / "data" / "raw" / "elo_ratings.csv"
    
    PROCESSED_DATA_DIR = PROJECT_ROOT / "data" / "processed"
    MODELS_DIR = PROJECT_ROOT / "models"
    
    # Ensure this path matches exactly where training.py saves the scaler
    SCALER_PATH = MODELS_DIR / "saved" / "scaler.pkl" 

    # ==========================================
    # 3. DATA DEFINITIONS (From your file)
    # ==========================================
    
    COL_DATE = "MatchDate"
    COL_HOME = "HomeTeam"
    COL_AWAY = "AwayTeam"
    COL_RESULT = "FTResult"
    COL_HOME_GOALS = "FTHG" # Updated to match standard CSVs (FTHG/FTAG)
    COL_AWAY_GOALS = "FTAG"

    # ==========================================
    # 4. FEATURE DEFINITIONS (Critical for ML)
    # ==========================================
    
    FEATURES_NUMERIC = [
        # 1. Strength & Elo
        "HomeElo", "AwayElo", 
        "EloDifference", "EloAdvantage",
        
        # 2. Form & Momentum
        "Form5Home", "Form5Away",
        "Home_RecentPoints", "Away_RecentPoints",
        "Home_Momentum", "Away_Momentum",
        
        # 3. Goal Potency (Lagged)
        "Home_AvgGoals", "Away_AvgGoals",
        "Home_AvgConceded", "Away_AvgConceded",
        
        # 4. Underlying Stats
        "Home_AvgShots", "Away_AvgShots",
        "Home_AvgCorners", "Away_AvgCorners",
        
        # 5. Context
        "Home_RestDays", "Away_RestDays",
        
        # 6. Market Data
        "OddHome", "OddDraw", "OddAway",
        "ImpliedProbHome", "ImpliedProbAway", "MarketMargin"
    ]

    # ==========================================
    # 5. TARGET DEFINITIONS
    # ==========================================
    
    # The computed target names used by training.py and main.py
    TARGETS = {
        "WLD": "Target_WLD",       # Win/Loss/Draw
        "Over25": "Target_Over25", # Over 2.5 Goals
        "BTTS": "Target_BTTS",     # Both Teams To Score
        "TotalGoals": "Target_Goals" # Exact number (Regression)
    }
    
    # Mappings
    RESULT_MAP = {'H': 2, 'D': 1, 'A': 0} # Standard: 2=Home, 1=Draw, 0=Away
    INV_RESULT_MAP = {2: 'H', 1: 'D', 0: 'A'}
    
    # Settings
    TRAIN_SPLIT = 0.80
    VAL_SPLIT = 0.10
    
    @staticmethod
    def ensure_dirs():
        """Creates necessary directories if they don't exist."""
        Config.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        Config.MODELS_DIR.mkdir(parents=True, exist_ok=True)
        (Config.MODELS_DIR / "saved").mkdir(parents=True, exist_ok=True)