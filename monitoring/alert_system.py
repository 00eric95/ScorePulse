import pandas as pd
import sys
import json
import os
from datetime import datetime

# --- Import Project Modules ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils.feature_engineering import FeatureEngineer
from models.model_factory import ModelFactory
from sklearn.metrics import accuracy_score, mean_squared_error

class AlertSystem:
    def __init__(self):
        self.config = Config()
        self.engineer = FeatureEngineer()
        
        # --- DEFINING PERFORMANCE THRESHOLDS ---
        # If a model performs worse than this, we raise an alarm.
        self.thresholds = {
            'WLD': 0.48,        # Alert if Accuracy < 48%
            'BTTS': 0.52,       # Alert if Accuracy < 52%
            'Over25': 0.52,     # Alert if Accuracy < 52%
            'TotalGoals': 2.0   # Alert if MSE > 2.0 (Lower is better for regression)
        }
    def _save_status_file(self, alerts):
        """Saves system health to JSON for the Web Dashboard."""
        # Ensure logs directory exists
        log_dir = self.config.PROJECT_ROOT / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        status_path = log_dir / "system_status.json"
        
        status_data = {
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "CRITICAL" if alerts else "HEALTHY",
            "active_alerts": alerts,
            "models_monitored": list(self.thresholds.keys())
        }
        
        with open(status_path, 'w') as f:
            json.dump(status_data, f, indent=4)
        print(f"   💾 System Status saved to {status_path.name}")

    def check_health(self):
        print("🩺 RUNNING SYSTEM DIAGNOSTICS...")
        print("================================")
        
        # 1. Load Recent Data (Validation Set)
        # In a live system, this would be "Last Week's Games"
        val_path = self.config.PROCESSED_DATA_DIR / "val.csv"
        if not val_path.exists():
            print("⚠️ Critical: No validation data found for monitoring.")
            return
            
        val_df = pd.read_csv(val_path)
        alerts = []
        
        # 2. Check Each Model
        for target_name, threshold in self.thresholds.items():
            filename = f"model_{target_name}.pkl"
            mode = 'regression' if target_name == 'TotalGoals' else 'classification'
            
            # Load Model
            try:
                # We use the factory to load the generic structure, then load weights
                model = ModelFactory.get_model('rf', mode=mode)
                model.load(filename)
            except FileNotFoundError:
                print(f"   ⚠️ {target_name}: Model file missing. Skipping.")
                continue

            # Prepare Data & Predict
            try:
                X_val, y_true = self.engineer.transform(val_df, target_name=target_name)
                preds = model.predict(X_val)
                
                # Calculate Metric
                current_perf = 0
                status = "OK"
                
                if mode == 'classification':
                    current_perf = accuracy_score(y_true, preds)
                    # Alert Logic: Is Accuracy TOO LOW?
                    if current_perf < threshold:
                        status = "CRITICAL"
                        alerts.append(f"🔴 {target_name}: Accuracy {current_perf:.2%} is below threshold {threshold:.2%}")
                    else:
                        print(f"   ✅ {target_name}: Accuracy {current_perf:.2%} (Healthy)")
                        
                else: # Regression (MSE)
                    current_perf = mean_squared_error(y_true, preds)
                    # Alert Logic: Is Error TOO HIGH?
                    if current_perf > threshold:
                        status = "CRITICAL"
                        alerts.append(f"🔴 {target_name}: MSE {current_perf:.2f} is above threshold {threshold:.2f}")
                    else:
                        print(f"   ✅ {target_name}: MSE {current_perf:.2f} (Healthy)")
                        
            except Exception as e:
                print(f"   ❌ Error evaluating {target_name}: {e}")

        # 3. Trigger Alert
        self._trigger_incident_response(alerts)
        
        self._save_status_file(alerts)

    def _trigger_incident_response(self, alerts):
        """
        Simulates sending an alert to Slack/Email/PagerDuty.
        """
        if not alerts:
            print("\n✨ SYSTEM STATUS: GREEN. No intervention needed.")
            return
            
        print("\n🚨 ALERT: MODEL PERFORMANCE DEGRADED 🚨")
        print("=======================================")
        for alert in alerts:
            print(alert)
        print("---------------------------------------")
        print("⚠️  ACTION REQUIRED: The models are failing to predict recent games accurately.")
        print("👉 RECOMMENDED FIX: Run 'python updating/model_retraining.py' to retrain on fresh data.")

if __name__ == "__main__":
    monitor = AlertSystem()
    monitor.check_health()