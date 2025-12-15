import pandas as pd
import os
from datetime import datetime
from pathlib import Path

class TrainingLogger:
    def __init__(self):
        # 1. Determine the Root Directory (Go up two levels from monitoring/logger.py)
        self.project_root = Path(__file__).resolve().parent.parent
        self.log_dir = self.project_root / "logs"
        
        # 2. Create logs directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Define File Paths
        self.history_file = self.log_dir / "training_history.csv"
        self.event_file = self.log_dir / "system_events.log"
        
        # 4. Initialize History CSV with headers if missing
        if not self.history_file.exists():
            df = pd.DataFrame(columns=['Timestamp', 'Target', 'ModelType', 'Metric', 'Value'])
            df.to_csv(self.history_file, index=False)

    def log_event(self, message, level="INFO"):
        """
        Logs a text event to system_events.log and prints to console.
        Handles Windows Unicode errors safely.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [{level}] {message}\n"
        
        # A. Print to Console (Safe Method)
        try:
            print(f"📝 {message}")
        except UnicodeEncodeError:
            # Fallback for old terminals that hate emojis
            clean_msg = message.encode('ascii', 'ignore').decode('ascii')
            print(f"Log: {clean_msg}")

        # B. Save to File (UTF-8 Enforced)
        try:
            with open(self.event_file, "a", encoding="utf-8") as f:
                f.write(entry)
        except Exception as e:
            print(f"❌ Logging Failed: {e}")

    def log_metric(self, target, model_type, metric_name, value):
        """
        Appends a numeric metric to the CSV for the Dashboard.
        """
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        new_row = {
            'Timestamp': timestamp,
            'Target': target,
            'ModelType': model_type,
            'Metric': metric_name,
            'Value': value
        }
        
        # Append to CSV safely
        try:
            df = pd.DataFrame([new_row])
            df.to_csv(self.history_file, mode='a', header=False, index=False)
        except Exception as e:
            print(f"❌ Failed to save metric: {e}")
            