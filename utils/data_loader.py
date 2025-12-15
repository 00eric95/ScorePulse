import pandas as pd
import sys
import os

# Allow importing from root
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils.feature_generator import AdvancedFeatureGenerator

class DataLoader:
    def __init__(self):
        self.config = Config()
        self.config.ensure_dirs()
        self.feature_gen = AdvancedFeatureGenerator()

    def load_raw_data(self):
        """Loads matches.csv with robust encoding handling."""
        if not self.config.RAW_DATA_PATH.exists():
            raise FileNotFoundError(f"❌ Data not found at: {self.config.RAW_DATA_PATH}")

        print(f"📥 Loading raw data from {self.config.RAW_DATA_PATH.name}...")
        
        df = None
        try:
            df = pd.read_csv(self.config.RAW_DATA_PATH, encoding='utf-8', parse_dates=[self.config.COL_DATE], dtype={'MatchTime': str, 'Division': str}, low_memory=False)
        except UnicodeDecodeError:
            print("⚠️ UTF-8 failed. Retrying with Latin-1...")
            try:
                df = pd.read_csv(self.config.RAW_DATA_PATH, encoding='latin1', parse_dates=[self.config.COL_DATE], dtype={'MatchTime': str, 'Division': str}, low_memory=False)
            except Exception as e:
                print(f"❌ Critical Error loading CSV: {e}")
                sys.exit(1)

        if df is None:
            print("❌ Failed to load dataframe (Unknown error).")
            sys.exit(1)

        print(f"   Rows loaded: {len(df)}")
        return df

    def preprocess(self, df):
        """
        1. Generates Advanced Features.
        2. Creates Targets (Over/Under, BTTS, WLD).
        3. Cleans Missing Data.
        """
        initial_len = len(df)
        
        # 1. Sort by Date
        df = df.sort_values(by=self.config.COL_DATE).reset_index(drop=True)
        
        # 2. Filter invalid matches
        df = df.dropna(subset=[self.config.COL_RESULT, 'FTHome', 'FTAway'])

        # 3. GENERATE ADVANCED FEATURES
        df = self.feature_gen.generate(df)

        # 4. CREATE TARGETS (CRITICAL FIX HERE)
        # Ensure the column names MATCH config.py EXACTLY
        
        # Target 1: Win/Loss/Draw (0, 1, 2)
        # Using self.config.TARGETS['WLD'] ensures the name is 'Target_WLD'
        df[self.config.TARGETS['WLD']] = df[self.config.COL_RESULT].map(self.config.RESULT_MAP)
        
        # Target 2: Total Goals
        df[self.config.TARGETS['TotalGoals']] = df['FTHome'] + df['FTAway']
        
        # Target 3: Over 2.5 Goals
        df[self.config.TARGETS['Over25']] = (df[self.config.TARGETS['TotalGoals']] > 2.5).astype(int)
        
        # Target 4: Both Teams to Score
        df[self.config.TARGETS['BTTS']] = ((df['FTHome'] > 0) & (df['FTAway'] > 0)).astype(int)

        # 5. STRICT FILTERING
        # Check if targets were created successfully
        if self.config.TARGETS['WLD'] not in df.columns:
            print(f"❌ Critical: Failed to create target {self.config.TARGETS['WLD']}")
            sys.exit(1)

        before_drop = len(df)
        # Drop rows where Features OR Targets are NaN
        # We must check targets too, in case mapping failed (e.g., result was 'P' instead of 'H/D/A')
        cols_to_check = self.config.FEATURES_NUMERIC + list(self.config.TARGETS.values())
        
        # Only check columns that actually exist to avoid KeyError during dropna
        existing_cols = [c for c in cols_to_check if c in df.columns]
        df = df.dropna(subset=existing_cols)
        
        dropped_count = before_drop - len(df)
        print(f"🧹 Quality Control: Dropped {dropped_count} rows.")
        print(f"   Final Dataset Size: {len(df)} matches.")
        
        return df

    def save_splits(self, df):
        n = len(df)
        train_end = int(n * self.config.TRAIN_SPLIT)
        val_end = int(n * (self.config.TRAIN_SPLIT + self.config.VAL_SPLIT))

        train = df.iloc[:train_end]
        val = df.iloc[train_end:val_end]
        test = df.iloc[val_end:]

        train.to_csv(self.config.PROCESSED_DATA_DIR / "train.csv", index=False)
        val.to_csv(self.config.PROCESSED_DATA_DIR / "val.csv", index=False)
        test.to_csv(self.config.PROCESSED_DATA_DIR / "test.csv", index=False)

        print(f"💾 Data processed & saved to {self.config.PROCESSED_DATA_DIR}")

if __name__ == "__main__":
    loader = DataLoader()
    raw_df = loader.load_raw_data()
    clean_df = loader.preprocess(raw_df)
    loader.save_splits(clean_df)