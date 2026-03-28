import os
import sys
import pandas as pd

# --- PATH FIXER ---
# The Flask app is in 'soccer_match_prediction/app/', so add that directory to sys.path
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # SCORE_PULSEAIv2/
flask_app_dir = os.path.join(project_root, 'soccer_match_prediction')
if flask_app_dir not in sys.path:
    sys.path.insert(0, flask_app_dir)

# Now import the app and db
from app import create_app, db
from app.models import Team, League  # Assuming these models exist; if not, check soccer_match_prediction/app/models.py

# The rest of your code...
def seed_teams_and_leagues():
    app = create_app()  # Create the app instance
    with app.app_context():
        # 1. Load Data
        try:
            df = pd.read_csv('data/raw/matches.csv')
        except FileNotFoundError:
            print("Error: data/raw/matches.csv not found.")
            return

        # 2. Handle Leagues First (Dependency)
        if 'League' in df.columns:
            unique_leagues = df['League'].dropna().unique()
            for L_name in unique_leagues:
                # Only add if it doesn't exist
                if not League.query.filter_by(name=L_name).first():
                    db.session.add(League(name=L_name))
            db.session.commit()
            print(f"✅ Leagues processed.")

        # 3. Handle Teams with Duplicate Prevention
        # Get all unique teams from both columns
        home_teams = df['HomeTeam'].dropna().unique()
        away_teams = df['AwayTeam'].dropna().unique()
        unique_team_names = set(home_teams) | set(away_teams)

        added_count = 0
        skipped_count = 0

        for name in unique_team_names:
            # Check if team already exists in DB
            existing_team = Team.query.filter_by(name=name).first()
            
            if not existing_team:
                new_team = Team(name=name)
                db.session.add(new_team)
                added_count += 1
            else:
                skipped_count += 1

        # 4. Final Commit
        db.session.commit()
        print(f"🏁 Seeding Complete: Added {added_count}, Skipped {skipped_count} existing.")

if __name__ == "__main__":
    seed_teams_and_leagues()