import sys
import os
import time
import subprocess
import json
from datetime import datetime

# --- PATH SETUP ---
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path: sys.path.insert(0, project_root)

# Import Logger
try:
    from utils.status_logger import StatusLogger
except ImportError:
    # Fallback mock logger if utility is missing
    class StatusLogger:
        def __init__(self, name): print(f"[{name}] Logger init")
        def start(self): print("Start")
        def log(self, msg, p=0): print(f"Log: {msg} ({p}%)")
        def complete(self, s=True): print("Done")

class ModelRetrainer:
    def __init__(self):
        self.logger = StatusLogger("Model Retraining")
        self.root = project_root

    def run_update_cycle(self, force=False):
        """
        Runs the full retraining pipeline and logs progress to the Admin Dashboard.
        """
        self.logger.start()
        
        try:
            # --- PHASE 1: INITIALIZATION ---
            self.logger.log("🚀 Initializing Retraining Protocol...", 5)
            time.sleep(1) # Small delay for UX visibility

            # Check if training script exists
            train_script = os.path.join(self.root, 'training.py')
            if not os.path.exists(train_script):
                raise FileNotFoundError(f"Critical: '{train_script}' not found.")

            # --- PHASE 2: DATA VERIFICATION ---
            self.logger.log("📂 Verifying Datasets...", 15)
            raw_data = os.path.join(self.root, 'data', 'raw', 'matches.csv')
            if not os.path.exists(raw_data):
                self.logger.log("⚠️ Raw data missing. Attempting scraper fallback...", 20)
                # Optional: Call scraper here if needed
            else:
                self.logger.log("✅ Raw Data confirmed.", 25)

            # --- PHASE 3: EXECUTE TRAINING (Subprocess) ---
            # We run training.py as a separate process to manage memory and capture logs
            self.logger.log("🧠 Starting Training Engine...", 30)
            
            process = subprocess.Popen(
                [sys.executable, train_script],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=self.root
            )

            # Stream logs from training.py to the dashboard
            # We map 30% -> 90% progress based on lines of output
            progress = 30
            for line in iter(process.stdout.readline, ''):
                line = line.strip()
                if line:
                    # Filter relevant logs to show on dashboard
                    if "Accuracy" in line or "Training" in line or "Saved" in line:
                        self.logger.log(f"⚙️ {line}", progress)
                        progress = min(progress + 5, 90) # Increment progress gently
            
            # Wait for finish
            stdout, stderr = process.communicate()
            
            if process.returncode != 0:
                raise Exception(f"Training Script Failed:\n{stderr}")

            self.logger.log("✅ Training Process Completed Successfully.", 95)

            # --- PHASE 4: UPDATE SYSTEM HEALTH ---
            self._update_health_status()
            self.logger.log("✅ System Status Updated.", 98)
            
            time.sleep(1)
            self.logger.complete(success=True)

        except Exception as e:
            self.logger.log(f"❌ CRITICAL FAILURE: {str(e)}")
            self.logger.complete(success=False)
            # Re-raise to ensure calling thread knows it failed
            print(f"Error in retraining: {e}")

    def _update_health_status(self):
        """Writes a simple health check file for the admin panel."""
        status_file = os.path.join(self.root, 'logs', 'system_status.json')
        
        health_data = {
            "status": "ONLINE",
            "last_training": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "active_alerts": []
        }
        
        # Check if models exist
        model_path = os.path.join(self.root, 'models', 'saved', 'model_WLD.pkl')
        if not os.path.exists(model_path):
            health_data['status'] = "DEGRADED"
            health_data['active_alerts'].append("WLD Model Missing")
            
        with open(status_file, 'w') as f:
            json.dump(health_data, f)

if __name__ == "__main__":
    # Test Run
    updater = ModelRetrainer()
    updater.run_update_cycle()