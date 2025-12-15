import time
import schedule
import sys
import os
from datetime import datetime

# --- Import Project Modules ---
# Ensure we can find the modules
sys.path.append(os.path.abspath(os.path.dirname(__file__)))

from updating.data_collection import DataCollector
from updating.model_retraining import ModelRetrainer
from monitoring.alert_system import AlertSystem
from monitoring.logger import TrainingLogger

def weekly_maintenance_job():
    logger = TrainingLogger()
    logger.log_event("⏰ SCHEDULER: Waking up for Weekly Maintenance...")
    
    print("\n" + "="*50)
    print(f"🚀 WEEKLY JOB STARTED AT {datetime.now()}")
    print("="*50)

    # 1. DATA COLLECTION (Optional / Placeholder)
    # If you have an API fetching script, call it here. 
    # For now, we assume you might have dropped a 'new_results.csv' into a specific folder.
    incoming_data = "data/incoming/weekly_update.csv"
    if os.path.exists(incoming_data):
        logger.log_event("📥 Found new data file. Importing...")
        collector = DataCollector()
        collector.import_new_matches(incoming_data)
        # Rename processed file so we don't import it again next week
        os.rename(incoming_data, f"data/incoming/processed_{datetime.now().strftime('%Y%m%d')}.csv")
    else:
        logger.log_event("ℹ️ No 'weekly_update.csv' found in data/incoming/. Skipping import.")

    # 2. MODEL RETRAINING & DRIFT CHECK
    # This script automatically checks if the new data is enough (>500 rows) to justify retraining.
    try:
        logger.log_event("🔄 Checking Model Health & Drift...")
        updater = ModelRetrainer()
        # We run the standard cycle. It handles the "check_necessity" logic internally.
        updater.run_update_cycle(force=False) 
    except Exception as e:
        logger.log_event(f"❌ Retraining Failed: {e}", "ERROR")

    # 3. SYSTEM HEALTH CHECK
    # Verifies if the current models are accurate on the latest validation set
    try:
        logger.log_event("🩺 Performing System Diagnostics...")
        monitor = AlertSystem()
        monitor.check_health()
    except Exception as e:
        logger.log_event(f"❌ Monitoring Failed: {e}", "ERROR")

    logger.log_event("✅ SCHEDULER: Weekly Job Finished. Going back to sleep.")
    print("\n💤 Job Complete. Waiting for next cycle...")

# --- CONFIGURATION ---
# Run every 7 days (e.g., every Monday at 3:00 AM)
# You can change this to .every().monday.at("03:00")
schedule.every(7).days.at("03:00").do(weekly_maintenance_job)

if __name__ == "__main__":
    print("⏳ Scheduler Active.")
    print("   - Frequency: Every 7 Days at 03:00 AM")
    print("   - Task: Import Data -> Retrain Models -> Check Health")
    print("   - Press Ctrl+C to stop.")
    
    # OPTIONAL: Run once immediately on startup to verify everything works
    # Uncomment the next line if you want to test it right now
    # weekly_maintenance_job()
    
    while True:
        schedule.run_pending()
        time.sleep(60) # Check the clock every minute