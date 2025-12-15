import json
import os
import time
from datetime import datetime

class StatusLogger:
    def __init__(self, task_name="System"):
        # Find the logs folder relative to this script
        self.root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.log_file = os.path.join(self.root, 'logs', 'active_job.json')
        self.task_name = task_name
        
        # Ensure logs dir exists
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)

    def start(self):
        self._write({"status": "running", "task": self.task_name, "logs": [], "progress": 0})

    def log(self, message, progress=None):
        """Adds a log line and updates progress."""
        data = self._read()
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}] {message}"
        
        print(entry) # Keep console output
        
        data['logs'].append(entry)
        if progress is not None:
            data['progress'] = progress
            
        self._write(data)

    def complete(self, success=True):
        self.log("Task Completed Successfully." if success else "Task Failed.")
        data = self._read()
        data['status'] = "completed" if success else "error"
        data['progress'] = 100
        self._write(data)

    def _read(self):
        if not os.path.exists(self.log_file):
            return {"status": "idle", "logs": [], "progress": 0}
        try:
            with open(self.log_file, 'r') as f:
                return json.load(f)
        except:
            return {"status": "idle", "logs": [], "progress": 0}

    def _write(self, data):
        with open(self.log_file, 'w') as f:
            json.dump(data, f)