import pandas as pd
import os

def check_inventory():
    try:
        df = pd.read_csv("data/processed/train.csv") # Or matches.csv
        
        print("📊 SYSTEM INVENTORY")
        print("===================")
        
        # 1. Leagues
        leagues = df['Division'].unique()
        print(f"🏆 Total Leagues: {len(leagues)}")
        print(f"   Codes: {', '.join(leagues)}")
        
        # 2. Teams
        home = df['HomeTeam'].unique()
        away = df['AwayTeam'].unique()
        all_teams = sorted(list(set(home) | set(away)))
        
        print(f"⚽ Total Teams: {len(all_teams)}")
        print(f"   First 5: {all_teams[:5]}")
        print(f"   Last 5:  {all_teams[-5:]}")
        
    except FileNotFoundError:
        print("❌ Data file not found. Run 'utils/data_loader.py' first.")

if __name__ == "__main__":
    check_inventory()
 