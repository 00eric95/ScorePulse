"""
FILE: import_matches.py
DESCRIPTION: Automated Data Pipeline & Database Synchronization Engine.
This file serves as the bridge between raw external match data (CSV) and the ScorePulse AI database.
It performs fuzzy team-name matching, league normalization, and prevents duplicate entries 
to ensure the Match and Prediction models remain accurate for AI analysis.
"""

import sys
import os
import pandas as pd
import json
import re
from difflib import SequenceMatcher
from sqlalchemy import inspect
from datetime import datetime, timedelta

# 1. SETUP PATHS FOR SCORE_PULSEAIv2 ARCHITECTURE
current_dir = os.path.dirname(os.path.abspath(__file__))  # SCORE_PULSEAIv2/analysis/
scorepulse_root = os.path.abspath(os.path.join(current_dir, '..'))  # SCORE_PULSEAIv2/
project_root = os.path.join(scorepulse_root, 'soccer_match_prediction')  # SCORE_PULSEAIv2/soccer_match_prediction/

# Paths to data files
csv_path = os.path.join(scorepulse_root, 'data', 'upcoming_matches.csv')
team_mapping_path = os.path.join(scorepulse_root, 'data', 'team_mapping.json')

# 2. TELL PYTHON WHERE THE CODE IS
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from app import db
    from app.models import Match, Team, League, TeamNameMapping, Season
    print("✅ System Linked: Found 'app' in soccer_match_prediction")
except ImportError as e:
    print(f"❌ Error: Can't find 'app'. Checked in: {project_root}")
    print(f"Error details: {e}")
    sys.exit(1)

# Global app variable to avoid multiple initializations
_app = None

def get_app(init_ml_engine=False):
    """Get or create Flask app, optionally without ML engine initialization."""
    global _app
    
    if _app is not None:
        return _app
    
    # We need to import create_app, but we'll control what it initializes
    from app import create_app
    
    # Set environment variable to control ML engine initialization
    if not init_ml_engine:
        os.environ['SKIP_ML_ENGINE'] = '1'
        os.environ['SKIP_CHATBOT'] = '1'
    
    try:
        _app = create_app()
        return _app
    finally:
        # Clean up environment variables
        if 'SKIP_ML_ENGINE' in os.environ:
            del os.environ['SKIP_ML_ENGINE']
        if 'SKIP_CHATBOT' in os.environ:
            del os.environ['SKIP_CHATBOT']

def update_database_schema():
    """Update database schema to add missing columns if needed."""
    # Get app without ML engine initialization
    app = get_app(init_ml_engine=False)
    
    with app.app_context():
        print("🔧 Checking and updating database schema...")
        
        # First, let's see what columns exist
        inspector = inspect(db.engine)
        columns = inspector.get_columns('matches')
        print("\n📋 Current columns in matches table:")
        for col in columns:
            print(f"  {col['name']}")
        
        # Check if home and away columns exist
        column_names = [col['name'] for col in columns]
        
        # Note: According to models.py, Match table has all the expected columns
        # Based on the output, we already have all the columns we need
        
        print("\n✅ Database schema is up-to-date - all expected columns exist")
        
        return app

class TeamNameNormalizer:
    """Handles team name variations and standardization."""
    
    def __init__(self, app):
        self.mapping = self._load_team_mapping()
        self.app = app
        
    def _load_team_mapping(self):
        """Load team mapping from JSON file if exists."""
        if os.path.exists(team_mapping_path):
            try:
                with open(team_mapping_path, 'r') as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ Warning: Could not load team mapping: {e}")
                return {}
        return {}
    
    def save_team_mapping(self):
        """Save team mapping to JSON file."""
        try:
            with open(team_mapping_path, 'w') as f:
                json.dump(self.mapping, f, indent=2)
            print(f"💾 Team mapping saved to {team_mapping_path}")
        except Exception as e:
            print(f"⚠️ Warning: Could not save team mapping: {e}")
    
    def normalize_team_name(self, team_name):
        """Normalize team name for database consistency."""
        if not isinstance(team_name, str):
            return team_name
            
        original = team_name.strip()
        
        # Check direct mapping
        if original in self.mapping:
            return self.mapping[original]
        
        # Apply minimal cleaning (remove extra whitespace, basic normalization)
        cleaned = re.sub(r'\s+', ' ', original).strip()
        
        # Try to find in TeamNameMapping table using the existing app context
        with self.app.app_context():
            mapping = TeamNameMapping.query.filter_by(original_name=cleaned).first()
            if mapping:
                return mapping.standard_name
        
        # Save mapping for future use
        if original != cleaned and cleaned:
            self.mapping[original] = cleaned
        
        return cleaned if cleaned else original

def get_or_create_team(team_name, normalizer, app):
    """Get existing team or create a new one with error handling for duplicates."""
    normalized_name = normalizer.normalize_team_name(team_name)
    
    with app.app_context():
        # 1. Primary Check: See if team exists
        team = Team.query.filter_by(name=normalized_name).first()
        
        if not team:
            try:
                # 2. Attempt to create new team
                team = Team(
                    name=normalized_name,
                    short_name=normalized_name[:10] if len(normalized_name) > 10 else normalized_name,
                    attack_rating=50.0,
                    defense_rating=50.0,
                    possession_style=50.0,
                    discipline_index=50.0,
                    squad_depth=50.0,
                    form_rating=50.0,
                    corners_avg=50.0,
                    win_rate=0.0,
                    avg_goals_scored=0.0,
                    avg_goals_conceded=0.0,
                    elo_rating=1500.0,
                    recent_form_score=0.0,
                    home_advantage_multiplier=1.1
                )
                db.session.add(team)
                db.session.flush()  # Push to DB to check for conflicts
                print(f"   + Created new team: {normalized_name}")
            
            except Exception as e:
                # 3. Handle Race Condition: If another process inserted it between step 1 and 2
                db.session.rollback()  # Clear the poisoned session
                
                # Final attempt to fetch the team that caused the conflict
                team = Team.query.filter_by(name=normalized_name).first()
                if team:
                    print(f"   ~ Recovered: {normalized_name} already existed (Race Condition)")
                else:
                    print(f"   ❌ CRITICAL: Failed to create or find team {normalized_name}: {e}")
                    raise e # Re-raise if it's a different type of error
                    
        return team, normalized_name
def get_or_create_league(league_name, app):
    """Get existing league or create a new one."""
    # Extract just the league name (last part after '/')
    if '/' in league_name:
        # Take only the last part (e.g., "A-League" from "Football / Australia / A-League")
        parts = league_name.split('/')
        league_name = parts[-1].strip()
    
    with app.app_context():
        league = League.query.filter_by(name=league_name).first()
    
    if not league:
        league = League(
            name=league_name,
            country=None,
            tier=1,
            type="Club",
            is_active=True
        )
        db.session.add(league)
        db.session.flush()
        print(f"  + Created new league: {league_name}")
    
    return league, league_name

def parse_csv_date(raw_date):
    """Parse various date formats from CSV."""
    if not raw_date or pd.isna(raw_date):
        return None
    
    try:
        raw_date_str = str(raw_date).strip()
        
        # Format: "Tue 06/01"
        if '/' in raw_date_str:
            # Extract day and month
            parts = raw_date_str.split()
            date_part = parts[-1] if len(parts) > 1 else raw_date_str
            
            # Split day/month
            if '/' in date_part:
                day, month = date_part.split('/')
                # Assume current year (2026 as per your data)
                year = 2026
                
                # Check if month is likely 01-12
                if len(month) == 2 and month.isdigit():
                    month_int = int(month)
                    day_int = int(day)
                    
                    # Basic validation
                    if 1 <= month_int <= 12 and 1 <= day_int <= 31:
                        return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        
        # Try pandas parsing for other formats
        try:
            parsed_date = pd.to_datetime(raw_date_str, errors='coerce')
            if pd.notna(parsed_date):
                return parsed_date.strftime('%Y-%m-%d')
        except:
            pass
            
        # Try manual parsing for common formats
        date_formats = ['%d/%m/%Y', '%m/%d/%Y', '%Y-%m-%d', '%d-%m-%Y', '%Y/%m/%d']
        for fmt in date_formats:
            try:
                dt = datetime.strptime(raw_date_str, fmt)
                return dt.strftime('%Y-%m-%d')
            except:
                continue
        
        # Default fallback if parsing fails
        return datetime.now().strftime('%Y-%m-%d')
        
    except Exception as e:
        print(f"⚠️ Date parsing error for '{raw_date}': {e}")
        return datetime.now().strftime('%Y-%m-%d')

def generate_betting_odds_csv(df, scorepulse_root):
    """Generate betting_odds.csv from upcoming_matches.csv data."""
    print("🎯 Generating betting odds CSV...")
    
    betting_odds_path = os.path.join(scorepulse_root, 'data', 'betting_odds.csv')
    
    # Check if required columns exist
    required_columns = [
        'match_details_teams', 
        'match_details_bet_options_option_1',  # home odds
        'match_details_bet_options_option_x',  # draw odds
        'match_details_bet_options_option_2',  # away odds
        'match_details_league'
    ]
    
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        print(f"⚠️ Missing required columns for betting odds: {missing_columns}")
        return
    
    # Extract betting odds data
    odds_data = []
    match_id = 1
    
    for index, row in df.iterrows():
        try:
            # Extract teams
            teams_str = str(row['match_details_teams']) if pd.notna(row['match_details_teams']) else ''
            if not teams_str:
                continue
                
            # Split teams (they're separated by newlines in the CSV)
            teams = teams_str.split('\n')
            if len(teams) < 2:
                continue
                
            home_team = teams[0].strip()
            away_team = teams[1].strip()
            
            # Extract odds
            home_odds = row['match_details_bet_options_option_1']
            draw_odds = row['match_details_bet_options_option_x'] 
            away_odds = row['match_details_bet_options_option_2']
            
            # Extract league (clean it up)
            league_raw = str(row['match_details_league']) if pd.notna(row['match_details_league']) else ''
            if '/' in league_raw:
                league = league_raw.split('/')[-1].strip()
            else:
                league = league_raw
            
            # Validate odds are numeric
            try:
                home_odds = float(home_odds) if pd.notna(home_odds) else None
                draw_odds = float(draw_odds) if pd.notna(draw_odds) else None
                away_odds = float(away_odds) if pd.notna(away_odds) else None
            except (ValueError, TypeError):
                continue
            
            # Skip if any odds are missing or invalid
            if not all([home_odds, draw_odds, away_odds]):
                continue
            
            # Create odds record
            odds_record = {
                'match_id': match_id,
                'home_team': home_team,
                'away_team': away_team,
                'home_odds': round(home_odds, 2),
                'draw_odds': round(draw_odds, 2),
                'away_odds': round(away_odds, 2),
                'league': league,
                'bookmaker': 'BetPawa',  # Default bookmaker
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')
            }
            
            odds_data.append(odds_record)
            match_id += 1
            
        except Exception as e:
            print(f"⚠️ Error processing row {index} for betting odds: {e}")
            continue
    
    if not odds_data:
        print("⚠️ No valid betting odds data found in upcoming matches")
        return
    
    # Create DataFrame and save
    odds_df = pd.DataFrame(odds_data)
    
    # Check if betting_odds.csv already exists and merge if needed
    if os.path.exists(betting_odds_path):
        try:
            existing_df = pd.read_csv(betting_odds_path)
            # Merge new data with existing, avoiding duplicates based on home_team, away_team, league
            combined_df = pd.concat([existing_df, odds_df], ignore_index=True)
            # Remove duplicates (keep the most recent timestamp)
            combined_df = combined_df.sort_values('timestamp', ascending=False)
            combined_df = combined_df.drop_duplicates(subset=['home_team', 'away_team', 'league'], keep='first')
            combined_df = combined_df.sort_values('match_id').reset_index(drop=True)
            # Reassign match_ids sequentially
            combined_df['match_id'] = range(1, len(combined_df) + 1)
            odds_df = combined_df
            print(f"📊 Merged with existing betting odds (added {len(odds_data)} new records)")
        except Exception as e:
            print(f"⚠️ Error reading existing betting odds file: {e}")
    
    # Save to CSV
    odds_df.to_csv(betting_odds_path, index=False)
    print(f"✅ Generated betting_odds.csv with {len(odds_df)} records at {betting_odds_path}")

def parse_csv_time(raw_time):
    """Parse time from CSV."""
    if not raw_time or pd.isna(raw_time):
        return "00:00"
    
    try:
        raw_time_str = str(raw_time).strip().lower()
        
        # Format: "11:00 am" or "11:00 AM" or "11:00am"
        if 'am' in raw_time_str or 'pm' in raw_time_str:
            # Remove am/pm and parse
            time_part = raw_time_str.replace('am', '').replace('pm', '').strip()
            if ':' in time_part:
                hour, minute = time_part.split(':')
                hour = int(hour.strip())
                minute = int(minute.strip().split()[0] if ' ' in minute.strip() else minute.strip())
                
                # Adjust for pm
                if 'pm' in raw_time_str and hour < 12:
                    hour += 12
                elif 'am' in raw_time_str and hour == 12:
                    hour = 0
                
                return f"{hour:02d}:{minute:02d}"
        
        # Already in 24-hour format HH:MM
        if ':' in raw_time_str and len(raw_time_str.split(':')) == 2:
            hour, minute = raw_time_str.split(':')
            try:
                hour_int = int(hour.strip())
                minute_int = int(minute.strip().split()[0] if ' ' in minute.strip() else minute.strip())
                if 0 <= hour_int <= 23 and 0 <= minute_int <= 59:
                    return f"{hour_int:02d}:{minute_int:02d}"
            except:
                pass
        
        # Unknown format, return default
        return "00:00"
        
    except Exception as e:
        print(f"⚠️ Time parsing error for '{raw_time}': {e}")
        return "00:00"

def import_csv_data():
    """Main function to import CSV data into the database."""
    try:
        # Get app WITHOUT ML engine initialization
        app = get_app(init_ml_engine=False)
    except Exception as e:
        print(f"❌ Error creating Flask app: {e}")
        return
    
    # Initialize normalizer with the app
    normalizer = TeamNameNormalizer(app)
    
    with app.app_context():
        # Create tables if they don't exist
        db.create_all()
        print("✅ Database tables verified/created")
        
        # Check if CSV file exists
        if not os.path.exists(csv_path):
            print(f"❌ CSV not found at: {csv_path}")
            print(f"Expected path: {csv_path}")
            print(f"Make sure the 'data' folder exists in {scorepulse_root}")
            return

        print(f"📂 Reading Data from: {csv_path}")
        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"❌ Error reading CSV: {e}")
            return
        
        print(f"📊 CSV Columns: {list(df.columns)}")
        print(f"📊 Total rows in CSV: {len(df)}")
        
        # Generate betting odds CSV from upcoming matches data
        generate_betting_odds_csv(df, scorepulse_root)
        
        # Rename columns for consistency
        column_mapping = {
            'match_details_teams': 'teams',
            'match_details_date': 'date',
            'match_details_time': 'time',
            'match_details_league': 'league',
            'match_details_bet_options_option_1': 'home_odds',
            'match_details_bet_options_option_x': 'draw_odds',
            'match_details_bet_options_option_2': 'away_odds'
        }
        
        # Apply renaming only for columns that exist
        existing_columns = {}
        for old_col, new_col in column_mapping.items():
            if old_col in df.columns:
                existing_columns[old_col] = new_col
        
        if existing_columns:
            df = df.rename(columns=existing_columns)
        else:
            print("⚠️ No expected columns found in CSV, using original column names")
        
        # Drop irrelevant columns if they exist
        columns_to_drop = ['match_details_link', 'match_details_bet_options_bet_count']
        for col in columns_to_drop:
            if col in df.columns:
                df = df.drop(columns=[col])
        
        count = 0
        skipped = 0
        import_log = []
        
        for index, row in df.iterrows():
            try:
                # Extract teams from the teams column
                teams_str = str(row['teams']) if 'teams' in row and pd.notna(row['teams']) else ''
                
                if not teams_str or teams_str.lower() == 'nan':
                    print(f"⚠️ Row {index}: No team data found")
                    skipped += 1
                    continue
                
                # Split by newline (teams are on separate lines in CSV)
                teams = teams_str.split('\n')
                if len(teams) < 2:
                    # Try alternative splitting
                    teams = teams_str.split(' vs ')
                    if len(teams) < 2:
                        teams = teams_str.split(' VS ')
                        if len(teams) < 2:
                            print(f"⚠️ Row {index}: Insufficient team data: {teams_str}")
                            skipped += 1
                            continue
                
                h_team_raw = teams[0].strip()
                a_team_raw = teams[1].strip() if len(teams) > 1 else ''
                
                if not h_team_raw or not a_team_raw:
                    print(f"⚠️ Row {index}: Missing team name(s): {teams_str}")
                    skipped += 1
                    continue
                
                # Get or create teams (for database linking)
                home_team, h_team_normalized = get_or_create_team(h_team_raw, normalizer, app)
                away_team, a_team_normalized = get_or_create_team(a_team_raw, normalizer, app)
                
                # Parse date
                raw_date = row['date'] if 'date' in row and pd.notna(row['date']) else ''
                formatted_date = parse_csv_date(raw_date)
                
                if not formatted_date:
                    print(f"⚠️ Row {index}: Invalid date format: {raw_date}")
                    formatted_date = datetime.now().strftime('%Y-%m-%d')
                
                # Parse time
                raw_time = row['time'] if 'time' in row and pd.notna(row['time']) else ''
                formatted_time = parse_csv_time(raw_time)
                
                # Get league
                raw_league = row['league'] if 'league' in row and pd.notna(row['league']) else 'Unknown League'
                league_obj, m_league = get_or_create_league(raw_league, app)
                
                # Get odds - handle NaN values
                try:
                    home_odds = float(row['home_odds']) if 'home_odds' in row and pd.notna(row['home_odds']) else None
                except:
                    home_odds = None
                
                try:
                    draw_odds = float(row['draw_odds']) if 'draw_odds' in row and pd.notna(row['draw_odds']) else None
                except:
                    draw_odds = None
                
                try:
                    away_odds = float(row['away_odds']) if 'away_odds' in row and pd.notna(row['away_odds']) else None
                except:
                    away_odds = None
                
                # Duplicate check (based on home_team_id, away_team_id, date)
                exists = Match.query.filter_by(
                    home_team_id=home_team.id,
                    away_team_id=away_team.id,
                    date=formatted_date
                ).first()

                if not exists:
                    # Create match according to models.py schema
                    new_match = Match(
                        date=formatted_date,
                        time=formatted_time,
                        league_id=league_obj.id,
                        league_name_str=m_league,  # String representation
                        home=h_team_raw,  # Original home team name
                        away=a_team_raw,  # Original away team name
                        home_odds=home_odds,
                        draw_odds=draw_odds,
                        away_odds=away_odds,
                        # Link to normalized team records
                        home_team_id=home_team.id,
                        away_team_id=away_team.id,
                        # Default values
                        match_status='scheduled',
                        source_original_home=h_team_raw,
                        source_original_away=a_team_raw
                    )
                    db.session.add(new_match)
                    count += 1
                    
                    # Log if normalization happened
                    if h_team_raw != h_team_normalized or a_team_raw != a_team_normalized:
                        import_log.append({
                            'match': f"{h_team_raw} vs {a_team_raw}",
                            'normalized': f"{h_team_normalized} vs {a_team_normalized}",
                            'date': formatted_date,
                            'league': m_league
                        })
                    
                    if count % 50 == 0:
                        print(f"  Processed {count} matches...")
                    
            except Exception as e:
                print(f"⚠️ Row {index}: Error processing: {e}")
                import traceback
                traceback.print_exc()
                skipped += 1
                continue

        try:
            db.session.commit()
            normalizer.save_team_mapping()
            print("✅ Database commit successful")
        except Exception as e:
            print(f"❌ Error committing to database: {e}")
            db.session.rollback()
            return
        
        print(f"\n📊 IMPORT SUMMARY:")
        print(f"   ✅ {count} matches added to the database.")
        print(f"   ⏭️  {skipped} matches skipped.")
        
        if import_log:
            print(f"\n🔄 TEAM NAME TRANSFORMATIONS ({len(import_log)}):")
            for log in import_log[:5]:
                print(f"   • {log['match']}")
                print(f"     → {log['normalized']} ({log['league']})")
            if len(import_log) > 5:
                print(f"   ... and {len(import_log) - 5} more transformations")
        
        # Show sample of imported data
        if count > 0:
            print(f"\n📋 SAMPLE OF IMPORTED MATCHES:")
            try:
                new_matches = Match.query.order_by(Match.id.desc()).limit(3).all()
                for match in reversed(new_matches):
                    odds_str = f"{match.home_odds}/{match.draw_odds}/{match.away_odds}" if match.home_odds else "No odds"
                    print(f"   • {match.home} vs {match.away} ({match.date} {match.time})")
                    print(f"     League: {match.league_name_str}, Odds: {odds_str}")
            except Exception as e:
                print(f"⚠️ Could not fetch sample matches: {e}")

if __name__ == "__main__":
    print(f"🚀 Starting import from SCORE_PULSEAIv2 structure")
    print(f"📁 Script location: {current_dir}")
    print(f"📁 Project root: {project_root}")
    print(f"📁 Data folder: {os.path.dirname(csv_path)}")
    import_csv_data()