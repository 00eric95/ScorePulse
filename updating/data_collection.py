"""
This module handles the ingestion and sanitization of new match data into the master database.
It performs a 'Data Quality Audit' to ensure all required fields for feature engineering are present.
The script manages safe merges, removing duplicates based on unique MatchDate and Team combinations.
Automated backups are created before every update to prevent data loss during the merging process.
It acts as the first gate in the pipeline, preparing raw CSV inputs for the ScorePulse AI engine.
"""

import pandas as pd
import sys
import os
import shutil
from datetime import datetime
from pathlib import Path

# --- Import Project Modules ---
# Robust path setup to find config regardless of where script is run
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
sys.path.append(str(project_root))

from config.config import Config

class DataCollector:
    def __init__(self):
        self.config = Config()
        # Ensure we point to the matches.csv defined in Config
        self.raw_path = self.config.RAW_DATA_PATH
        
    def import_new_matches(self, new_data_path):
        """
        Safely merges a new CSV of matches into the master dataset.
        Performs a 'Data Quality Audit' to ensure 'Smart Math' features can be built.
        """
        print(f"\n📥 IMPORTING NEW DATA FROM: {new_data_path}")
        print("==========================================")
        
        # 1. Load Master Data
        if not self.raw_path.exists():
            print(f"   ⚠️ Master database not found at {self.raw_path}. Creating new one.")
            master_df = pd.DataFrame()
        else:
            try:
                # Try loading with different encodings
                try:
                    master_df = pd.read_csv(self.raw_path, encoding='utf-8')
                except UnicodeDecodeError:
                    master_df = pd.read_csv(self.raw_path, encoding='latin1')
                print(f"   📄 Current Master DB Size: {len(master_df)} rows")
            except Exception as e:
                print(f"   ❌ CRITICAL: Could not read master DB: {e}")
                return

        # 2. Load New Data
        try:
            new_df = pd.read_csv(new_data_path, encoding='latin1') # common for football data
            print(f"   📄 New Data Size: {len(new_df)} rows")
        except Exception as e:
            print(f"   ❌ CRITICAL: Could not read new data file: {e}")
            return
            
        # 3. Validation & Quality Audit
        
        # A. Critical Checks (Must have these to function)
        critical_cols = ['MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']
        missing_critical = [c for c in critical_cols if c not in new_df.columns]
        
        if missing_critical:
            # Try to map common aliases before failing
            aliases = {'Date': 'MatchDate', 'Home': 'HomeTeam', 'Away': 'AwayTeam', 'HG': 'FTHome', 'AG': 'FTAway'}
            new_df.rename(columns=aliases, inplace=True)
            
            # Re-check
            missing_critical = [c for c in critical_cols if c not in new_df.columns]
            if missing_critical:
                print(f"   ❌ STOPPING: New data is missing CRITICAL columns: {missing_critical}")
                return

        # B. Smart Data Checks (Needed for AttackEff, Dominance, xG)
        smart_stats = ['HS', 'AS', 'HC', 'AC'] # Home/Away Shots, Corners
        missing_stats = [c for c in smart_stats if c not in new_df.columns]
        
        if missing_stats:
            print(f"   ⚠️  QUALITY WARNING: Missing stats {missing_stats}.")
            print("       -> The models will run, but 'Attack Efficiency' & 'Dominance' features will be less accurate.")
        else:
            print("       ✅ Smart Stats (Shots/Corners) found. Advanced features enabled.")

        # C. Market Data Checks (Needed for Probability Models)
        odds_cols = ['AvgH', 'AvgD', 'AvgA'] # Or B365H etc.
        # Check if ANY odds columns exist
        has_odds = any(col in new_df.columns for col in ['AvgH', 'B365H', 'OddHome'])
        if not has_odds:
             print("   ⚠️  QUALITY WARNING: No Betting Odds found.")
             print("       -> The 'Value Detector' and Probability engine will be significantly weaker.")
        else:
             print("       ✅ Betting Odds found.")

        # 4. Merge & Deduplicate
        try:
            combined_df = pd.concat([master_df, new_df], ignore_index=True)
            
            # Normalize Date Format
            combined_df['MatchDate'] = pd.to_datetime(combined_df['MatchDate'], errors='coerce')
            combined_df = combined_df.dropna(subset=['MatchDate']) # Drop rows with bad dates
            
            # Deduplicate: Keep the LAST entry if Date+Home+Away are identical
            before_dedup = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=['MatchDate', 'HomeTeam', 'AwayTeam'], keep='last')
            duplicates_removed = before_dedup - len(combined_df)
            
            # Sort chronologically
            combined_df = combined_df.sort_values(by='MatchDate')
            
            print(f"   🧹 Duplicates removed: {duplicates_removed}")
            print(f"   ✅ New Master DB Size: {len(combined_df)} rows")
            
            # 5. Safety Backup
            if self.raw_path.exists():
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_dir = self.config.RAW_DATA_DIR / "backups"
                backup_dir.mkdir(exist_ok=True)
                
                backup_path = backup_dir / f"matches_backup_{timestamp}.csv"
                shutil.copy(self.raw_path, backup_path)
                print(f"   🛡️  Backup created at: backups/{backup_path.name}")
            
            # 6. Save
            combined_df.to_csv(self.raw_path, index=False)
            print("   💾 SUCCESS: Master database updated.")
            
        except Exception as e:
            print(f"   ❌ Error during merge/save: {e}")

if __name__ == "__main__":
    # Example Usage:
    # python updating/data_collection.py "path/to/new_matches.csv"
    
    if len(sys.argv) > 1:
        importer = DataCollector()
        importer.import_new_matches(sys.argv[1])
    else:
        print("Usage: python updating/data_collection.py <path_to_new_csv>")