import pandas as pd
import sys
import os
import shutil
from datetime import datetime

# --- Import Project Modules ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class DataCollector:
    def __init__(self):
        self.config = Config()
        self.raw_path = self.config.RAW_DATA_PATH
        
    def import_new_matches(self, new_data_path):
        """
        Safely merges a new CSV of matches into the master dataset.
        """
        print(f"📥 IMPORTING NEW DATA FROM: {new_data_path}")
        print("==========================================")
        
        # 1. Load Master Data
        if not self.raw_path.exists():
            print("❌ Master database not found.")
            return

        try:
            # Try loading with different encodings
            try:
                master_df = pd.read_csv(self.raw_path, encoding='utf-8')
            except UnicodeDecodeError:
                master_df = pd.read_csv(self.raw_path, encoding='latin1')
            
            print(f"   📄 Current Master DB Size: {len(master_df)} rows")
            
            # 2. Load New Data
            new_df = pd.read_csv(new_data_path)
            print(f"   📄 New Data Size: {len(new_df)} rows")
            
            # 3. Validation
            # Ensure new columns match master columns
            missing_cols = [c for c in master_df.columns if c not in new_df.columns]
            if missing_cols:
                # Warnings for optional columns, Error for critical ones
                critical = ['MatchDate', 'HomeTeam', 'AwayTeam', 'FTHome', 'FTAway']
                if any(c in missing_cols for c in critical):
                    print(f"   ❌ CRITICAL ERROR: New data is missing columns: {missing_cols}")
                    return
                else:
                    print(f"   ⚠️ Warning: New data missing non-critical columns. Filling with NaN.")
            
            # 4. Merge & Deduplicate
            # We combine them, then drop duplicates based on Date+Teams to prevent adding the same game twice
            combined_df = pd.concat([master_df, new_df])
            
            # Convert date to ensure proper duplicate checking
            combined_df['MatchDate'] = pd.to_datetime(combined_df['MatchDate'], errors='coerce')
            
            before_dedup = len(combined_df)
            combined_df = combined_df.drop_duplicates(subset=['MatchDate', 'HomeTeam', 'AwayTeam'], keep='last')
            duplicates_removed = before_dedup - len(combined_df)
            
            # Sort by date
            combined_df = combined_df.sort_values(by='MatchDate')
            
            print(f"   🧹 Duplicates removed: {duplicates_removed}")
            print(f"   ✅ New Master DB Size: {len(combined_df)} rows")
            
            # 5. Safety Backup & Save
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = self.config.PROJECT_ROOT / "data" / "raw" / f"matches_backup_{timestamp}.csv"
            shutil.copy(self.raw_path, backup_path)
            print(f"   🛡️  Backup created at: {backup_path.name}")
            
            combined_df.to_csv(self.raw_path, index=False)
            print("   💾 SUCCESS: Master database updated.")
            
        except Exception as e:
            print(f"   ❌ Error during import: {e}")

if __name__ == "__main__":
    # Example Usage:
    # python updating/data_collection.py "path/to/new_matches.csv"
    
    if len(sys.argv) > 1:
        importer = DataCollector()
        importer.import_new_matches(sys.argv[1])
    else:
        print("Usage: python updating/data_collection.py <path_to_new_csv>")