"""
This script serves as the project's automated heartbeat, managing recurring maintenance tasks via a schedule.
It is configured to run every Monday at 03:00 AM to perform data ingestion and model updates.
The workflow includes importing new match data from the 'incoming' folder and archiving processed files.
It triggers the model retraining cycle (the tournament) to ensure predictions remain updated with the latest data.
After retraining, it executes a system health check and logs all events through the internal monitoring system.
"""

import time
import schedule
import sys
import os
from datetime import datetime
from pathlib import Path

# --- Import Project Modules ---
# Robustly find the Project Root regardless of where this script is run
current_file = Path(__file__).resolve()
# Assuming scheduler.py is in the root folder. 
# If it is in a subfolder like 'utils', use current_file.parent.parent
project_root = current_file.parent 
if str(project_root) not in sys.path:
    sys.path.append(str(project_root))

from config.config import Config
from updating.data_collection import DataCollector
from updating.model_retraining import ModelRetrainer
from monitoring.alertsystem import AlertSystem  # Fixed name to match your file
from monitoring.logger import TrainingLogger

def weekly_maintenance_job():
    logger = TrainingLogger()
    logger.log_event("⏰ SCHEDULER: Waking up for Weekly Maintenance...", level="INFO")
    
    print("\n" + "="*50)
    print(f"🚀 WEEKLY JOB STARTED AT {datetime.now()}")
    print("="*50)

    # Setup Paths via Config
    config = Config()
    incoming_dir = config.DATA_DIR / "incoming"
    incoming_file = incoming_dir / "weekly_update.csv"
    
    # Ensure directory exists
    incoming_dir.mkdir(parents=True, exist_ok=True)

    # 1. DATA COLLECTION
    # Checks for a file named 'weekly_update.csv' in 'data/incoming/'
    if incoming_file.exists():
        logger.log_event(f"📥 Found new data file: {incoming_file.name}. Importing...", level="INFO")
        
        try:
            collector = DataCollector()
            collector.import_new_matches(str(incoming_file))
            
            # Archive the processed file so it isn't imported twice
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            archive_name = f"processed_{timestamp}.csv"
            archive_path = incoming_dir / archive_name
            
            os.rename(incoming_file, archive_path)
            logger.log_event(f"📦 Archived processed file to: {archive_name}", level="SUCCESS")
            
        except Exception as e:
            logger.log_event(f"❌ Data Import Failed: {e}", level="ERROR")
    else:
        logger.log_event("ℹ️ No 'weekly_update.csv' found. Skipping Import.", level="INFO")

    # 2. MODEL RETRAINING (The Tournament)
    # This runs the 'Champions League' (training.py) via the Retrainer wrapper
    try:
        logger.log_event("🔄 Starting Model Tournament & Retraining Cycle...", level="INFO")
        updater = ModelRetrainer()
        updater.run_update_cycle(force=True) 
        # Note: force=True ensures the tournament runs even if data didn't change (good for weekly sanity checks)
    except Exception as e:
        logger.log_event(f"❌ Retraining Failed: {e}", level="ERROR")

    # 3. SYSTEM HEALTH CHECK
    # Verifies if the new Champions are accurate
    try:
        logger.log_event("🩺 Performing System Diagnostics...", level="INFO")
        monitor = AlertSystem()
        monitor.check_health()
    except Exception as e:
        logger.log_event(f"❌ Monitoring Failed: {e}", level="ERROR")

    logger.log_event("✅ SCHEDULER: Weekly Job Finished. Going back to sleep.", level="SUCCESS")
    print("\n💤 Job Complete. Waiting for next cycle...")

# --- CONFIGURATION ---
# Run every Monday at 03:00 AM
schedule.every().monday.at("03:00").do(weekly_maintenance_job)

if __name__ == "__main__":
    print("⏳ Scheduler Active.")
    print(f"   Project Root detected: {project_root}")
    print("   - Frequency: Every Monday at 03:00 AM")
    print("   - Task: Import Data -> Run Tournament -> Check Health")
    print("   - Drop new data into: data/incoming/weekly_update.csv")
    print("   - Press Ctrl+C to stop.")
    
    # Create the incoming folder for you if missing
    Config().DATA_DIR.joinpath("incoming").mkdir(parents=True, exist_ok=True)
    
    # OPTIONAL: Uncomment to run immediately for testing
    # weekly_maintenance_job()
    
    while True:
        schedule.run_pending()
        time.sleep(60) # Check the clock every minute