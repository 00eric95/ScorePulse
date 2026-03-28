"""
Orchestrates the 'Champions League' model comparison cycle to find the most accurate predictors.
It automates the full retraining workflow, from data loading to hyperparameter tuning and evaluation.
The module updates a system_status.json file to provide real-time health updates to the dashboard.
It acts as a 'Tournament Director,' comparing new model versions against current production champions.
The script includes a progress logger to track the multi-stage training process across different targets.
"""

import sys
import os
import time
import subprocess
import json
from datetime import datetime
from pathlib import Path

# --- PATH SETUP ---
# Robust setup to find project root regardless of execution context
current_dir = Path(__file__).resolve().parent
project_root = current_dir.parent
if str(project_root) not in sys.path: sys.path.insert(0, str(project_root))

from config.config import Config

# --- MOCK UI LOGGER ---
# In a full web app, this would write to a database or websocket.
# For now, it prints to console so you can see it working.
class ProgressLogger:
    def __init__(self, name="Tournament Director"): 
        self.name = name
    def start(self): 
        print(f"\n[{self.name}] 🎬 Process Started")
    def log(self, msg, p=0): 
        print(f"[{self.name}] {p}% - {msg}")
    def complete(self, success=True): 
        status = "✅ Completed" if success else "❌ Failed"
        print(f"[{self.name}] {status}\n")

class ModelRetrainer:
    def __init__(self):
        self.logger = ProgressLogger()
        self.config = Config()
        self.root = self.config.BASE_DIR

    def run_update_cycle(self, force=False):
        """
        Runs the full 'Champions League' model comparison pipeline.
        This replaces the old single-model training loop.
        """
        self.logger.start()
        
        try:
            # --- PHASE 1: INITIALIZATION ---
            self.logger.log("🚀 Initializing Tournament Protocol...", 5)
            time.sleep(1)

            # Locate the Tournament Script
            # We look for 'compare_models.py' in the project root
            train_script = self.root / 'compare_models.py'
            if not train_script.exists():
                raise FileNotFoundError(f"Critical: '{train_script}' not found.")

            # --- PHASE 2: DATA CHECK ---
            self.logger.log("📂 Verifying Training Data...", 15)
            processed_data = self.config.PROCESSED_DATA_DIR / 'train.csv'
            
            # If processed data missing, trigger the Data Loader first
            if not processed_data.exists():
                self.logger.log("⚠️ Processed data missing. Running Data Loader...", 20)
                loader_script = self.root / 'utils' / 'data_loader.py'
                
                # Run Data Loader
                subprocess.run([sys.executable, str(loader_script)], check=True)
                self.logger.log("✅ Data Loader finished.", 25)
            else:
                self.logger.log("✅ Training Data confirmed.", 25)

            # --- PHASE 3: EXECUTE TOURNAMENT ---
            self.logger.log("🏟️ Starting Model Tournament (RF vs XGB vs NN)...", 30)
            
            # Execute compare_models.py as a subprocess
            # We capture stdout to display real-time progress on the dashboard
            process = subprocess.Popen(
                [sys.executable, str(train_script)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=str(self.root)
            )

            # Stream logs
            progress = 30
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    # Filter output to show meaningful updates
                    if "Training" in line:
                        # e.g. "Training XGB..."
                        self.logger.log(f"⚙️ {line}", progress)
                        progress = min(progress + 2, 80)
                    elif "CHAMPION" in line:
                        # e.g. "CHAMPION for WLD: XGB"
                        self.logger.log(f"🏆 {line}", progress)
                        progress = min(progress + 5, 90)
                    elif "Score:" in line:
                         self.logger.log(f"📊 {line}", progress)
            
            # Wait for process to finish
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Tournament Script Failed:\n{stderr}")

            self.logger.log("✅ Tournament Completed. Champions Crowned.", 95)

            # --- PHASE 4: UPDATE SYSTEM HEALTH ---
            self._update_health_status()
            self.logger.log("✅ System Status Updated.", 100)
            self.logger.complete(success=True)

        except Exception as e:
            self.logger.log(f"❌ CRITICAL FAILURE: {str(e)}", 0)
            self.logger.complete(success=False)
            print(f"Detailed Error: {e}")

    def _update_health_status(self):
        """Updates the JSON file used by the dashboard to show system health."""
        status_file = self.root / 'logs' / 'system_status.json'
        
        # Check if the main models exist
        wld_model = self.config.MODELS_DIR / 'model_WLD.pkl'
        goals_model = self.config.MODELS_DIR / 'model_TotalGoals.pkl'
        
        models_ok = wld_model.exists() and goals_model.exists()
        
        health_data = {
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "ONLINE" if models_ok else "DEGRADED",
            "last_training": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "active_alerts": [] if models_ok else ["Champions Missing"]
        }
        
        try:
            # Ensure logs dir exists
            status_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(status_file, 'w') as f:
                json.dump(health_data, f, indent=4)
        except Exception as e:
            print(f"Failed to write status file: {e}")

if __name__ == "__main__":
    # Test Run
    updater = ModelRetrainer()
    updater.run_update_cycle()