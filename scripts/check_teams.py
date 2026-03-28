import pandas as pd
import os
import sys

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

# --- MAPPING DICTIONARY ---
# Maps division codes (e.g., E0, SP1) to readable Country Names
# You can expand this list based on the data you use.
DIVISION_TO_COUNTRY = {
    # England
    'E0': 'England', 'E1': 'England', 'E2': 'England', 'E3': 'England', 'EC': 'England',
    # Scotland
    'SC0': 'Scotland', 'SC1': 'Scotland', 'SC2': 'Scotland', 'SC3': 'Scotland',
    # Germany
    'D1': 'Germany', 'D2': 'Germany',
    # Italy
    'I1': 'Italy', 'I2': 'Italy',
    # Spain
    'SP1': 'Spain', 'SP2': 'Spain',
    # France
    'F1': 'France', 'F2': 'France',
    # Netherlands
    'N1': 'Netherlands',
    # Belgium
    'B1': 'Belgium',
    # Portugal
    'P1': 'Portugal',
    # Turkey
    'T1': 'Turkey',
    # Greece
    'G1': 'Greece'
}

def generate_team_inventory():
    config = Config()
    
    # 1. Define paths
    input_path = config.PROCESSED_DATA_DIR / "train.csv"
    output_path = config.PROCESSED_DATA_DIR / "teams_db.csv"
    
    try:
        if not input_path.exists():
            print(f"❌ Input file not found: {input_path}")
            print("   -> Run 'utils/data_loader.py' first.")
            return

        print(f"📂 Reading data from: {input_path.name}")
        df = pd.read_csv(input_path)
        
        print("📊 ANALYZING INVENTORY")
        print("======================")

        # 2. Extract Teams & Map to League
        # Get all HomeTeam+Division pairs and AwayTeam+Division pairs
        home_teams = df[['HomeTeam', 'Division']].rename(columns={'HomeTeam': 'Team'})
        away_teams = df[['AwayTeam', 'Division']].rename(columns={'AwayTeam': 'Team'})
        
        # Combine and drop duplicates
        all_teams_df = pd.concat([home_teams, away_teams])
        all_teams_df = all_teams_df.drop_duplicates()
        
        # 3. Add Country Column
        # Map the 'Division' code to a full 'Country' name
        all_teams_df['Country'] = all_teams_df['Division'].map(DIVISION_TO_COUNTRY).fillna('Other')

        # 4. Sorting Strategy
        # Sort by Country (A-Z) -> Division (A-Z) -> Team (A-Z)
        all_teams_df = all_teams_df.sort_values(by=['Country', 'Division', 'Team'])
        
        # Reorder columns for the final CSV
        all_teams_df = all_teams_df[['Country', 'Division', 'Team']]
        
        # 5. Save to CSV
        all_teams_df.to_csv(output_path, index=False)
        
        # 6. Summary Stats
        unique_countries = all_teams_df['Country'].nunique()
        unique_teams = all_teams_df['Team'].nunique()
        
        print(f"✅ GENERATION COMPLETE")
        print(f"   -------------------")
        print(f"   Countries: {unique_countries}")
        print(f"   Teams:     {unique_teams}")
        print(f"   Saved to:  {output_path}")
        print(f"   -------------------")
        
        # Preview
        print("\n👀 Preview (First 5 Rows):")
        print(all_teams_df.head(5).to_string(index=False))
        
    except Exception as e:
        print(f"❌ Error generating inventory: {e}")

if __name__ == "__main__":
    generate_team_inventory()