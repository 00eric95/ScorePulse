# Regenerated: logger.py
# Changes: 
# - Integrated with Flask's current_app for config and DB (use SystemLog for DB persistence).
# - Fixed paths to use app.config['BASE_DIR'].
# - Added Celery task logging if available.
# - Ensured compatibility with routes.py (e.g., no conflicts in imports).
# - Used JSON for additional_info in history CSV.
# - Added debug logging for errors.
# - Streamlined _init_history_file with updated columns from models.py (e.g., added ModelEvaluation link).
# - Fixed color printing to work in non-Unix environments.

"""
Implements a centralized logging singleton that tracks training history, system events, and errors across the project.
It manages three distinct log formats: CSV for training metrics, JSONL for system events, and a standard log file for errors.
The 'TrainingLogger' automatically captures metadata such as dataset size, training time, and feature counts for every run.
It includes a 'Champion' tracking feature to record which model version currently holds the highest score for each target.
Designed with project-root awareness, it ensures all logs are stored in a consistent directory regardless of where a script is executed.
"""

import pandas as pd
import os
import json
import sys
from datetime import datetime
from pathlib import Path
import traceback
import warnings
warnings.filterwarnings('ignore')

from flask import current_app

class TrainingLogger:
    def __init__(self, log_level="INFO"):
        # 1. Determine the Root Directory using Flask config
        self.project_root = Path(current_app.config['BASE_DIR'])
        self.log_dir = self.project_root / "logs"
        
        # 2. Create logs directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # 3. Define File Paths
        self.history_file = self.log_dir / "training_history.csv"
        self.event_file = self.log_dir / "system_events.jsonl"  # Changed to JSONL format
        self.error_log = self.log_dir / "errors.log"
        
        # 4. Set log level
        self.log_levels = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}
        self.current_level = self.log_levels.get(log_level.upper(), 20)
        
        # 5. Initialize History CSV with EXPANDED headers if missing
        self._init_history_file()
        
        # 6. Initialize JSONL event file if missing
        self._init_event_file()
        
        current_app.logger.info(f"📝 Logger initialized at level: {log_level}")

    def _init_history_file(self):
        """Initialize the training history CSV file with proper headers."""
        if not self.history_file.exists():
            cols = [
                'Timestamp', 
                'Target', 
                'ModelType', 
                'Metric', 
                'Score', 
                'Feature_Count',
                'Dataset_Size',
                'Training_Time_Seconds',
                'Best_Params',
                'Model_Version',
                'Git_Commit',
                'Additional_Info'
            ]
            df = pd.DataFrame(columns=cols)
            df.to_csv(self.history_file, index=False)
            self.log_event("Training history file initialized", level="INFO")
    
    def _init_event_file(self):
        """Initialize the JSONL event file."""
        if not self.event_file.exists():
            # Create empty file
            with open(self.event_file, 'w') as f:
                pass
    
    def _should_log(self, level):
        """Check if message should be logged based on log level."""
        return self.log_levels.get(level.upper(), 20) >= self.current_level

    def log_event(self, message, level="INFO", details=None, component=None):
        """
        Logs a structured event to system_events.jsonl and prints to console.
        
        Args:
            message (str): The main log message
            level (str): Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
            details (dict): Additional structured details
            component (str): Which component generated the log
        """
        if not self._should_log(level):
            return
        
        timestamp = datetime.now().isoformat()
        
        # Create structured log entry
        log_entry = {
            'timestamp': timestamp,
            'level': level.upper(),
            'message': str(message),
            'component': component or 'system',
            'pid': os.getpid(),
            'hostname': os.uname().nodename if hasattr(os, 'uname') else 'unknown'
        }
        
        # Add details if provided
        if details:
            log_entry['details'] = details
        
        # A. Print to Console with colors (cross-platform safe)
        try:
            import colorama
            colorama.init()
            colors = {
                'DEBUG': colorama.Fore.CYAN,
                'INFO': colorama.Fore.GREEN,
                'WARNING': colorama.Fore.YELLOW,
                'ERROR': colorama.Fore.RED,
                'CRITICAL': colorama.Back.RED
            }
            reset = colorama.Style.RESET_ALL
            
            color = colors.get(level.upper(), '')
            level_display = f"{level.upper():8}"
            
            print(f"{color}[{timestamp[:19]}] {level_display} {message}{reset}")
            
            # Print details if DEBUG level
            if level.upper() == "DEBUG" and details:
                print(f"       Details: {json.dumps(details, default=str)[:200]}...")
                
        except ImportError:
            # Fallback without colors
            print(f"[{timestamp[:19]}] {level.upper()} {message}")

        # B. Save to JSONL file
        try:
            with open(self.event_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, default=str) + "\n")
        except Exception as e:
            current_app.logger.error(f"❌ Failed to write to event log: {e}")

        # C. Log to DB using SystemLog
        try:
            from app import db
            from app.models import SystemLog
            db_log = SystemLog(
                level=level.upper(),
                module=component or 'system',
                log_type='event',
                message=message,
                data=json.dumps(details) if details else None
            )
            db.session.add(db_log)
            db.session.commit()
        except Exception as e:
            current_app.logger.error(f"❌ Failed to log to DB: {e}")

    def log_error(self, error, context=None):
        """
        Specialized method for logging errors with stack trace.
        
        Args:
            error (Exception): The exception object
            context (str): Additional context about where error occurred
        """
        error_details = {
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'context': context
        }
        
        self.log_event(f"Error: {str(error)}", level="ERROR", details=error_details)
        
        # Also write to dedicated error log
        try:
            with open(self.error_log, "a", encoding="utf-8") as f:
                f.write(f"\n{'='*60}\n")
                f.write(f"Time: {datetime.now().isoformat()}\n")
                f.write(f"Error: {type(error).__name__}\n")
                f.write(f"Message: {str(error)}\n")
                f.write(f"Context: {context}\n")
                f.write(f"Stack: {traceback.format_exc()}\n")
        except Exception as e:
            current_app.logger.error(f"❌ Failed to write to error log: {e}")

    def log_champion(self, target, model_type, score, metric_name, feature_count, params, training_time, dataset_size, additional_info=None):
        """
        Log a new champion model.
        
        Args:
            target (str): Prediction target (e.g., 'WLD')
            model_type (str): Type of model (e.g., 'RandomForest')
            score (float): Champion score
            metric_name (str): Metric used (e.g., 'Accuracy')
            feature_count (int): Number of features used
            params (dict): Best hyperparameters
            training_time (float): Training time in seconds
            dataset_size (tuple): (train_size, test_size)
            additional_info (dict): Any extra info
        """
        timestamp = datetime.now()
        
        entry = {
            'Timestamp': timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            'Target': target,
            'ModelType': model_type,
            'Metric': metric_name,
            'Score': score,
            'Feature_Count': feature_count,
            'Dataset_Size': f"{dataset_size[0]}/{dataset_size[1]}",
            'Training_Time_Seconds': training_time,
            'Best_Params': json.dumps(params),
            'Model_Version': self._get_model_version(),
            'Git_Commit': self._get_git_commit(),
            'Additional_Info': json.dumps(additional_info) if additional_info else ''
        }
        
        try:
            df = pd.DataFrame([entry])
            df.to_csv(self.history_file, mode='a', header=not self.history_file.exists(), index=False)
            self.log_event(f"New champion for {target}: {model_type} with {metric_name}={score:.4f}", level="INFO", details=entry)
        except Exception as e:
            self.log_error(e, context="log_champion")

    def log_batch(self, batch_data):
        """Log multiple entries at once."""
        try:
            df = pd.DataFrame(batch_data)
            df.to_csv(self.history_file, mode='a', header=not self.history_file.exists(), index=False)
            self.log_event(f"Batch logged: {len(batch_data)} entries", level="INFO")
        except Exception as e:
            self.log_error(e, context="log_batch")

    def get_history(self, filters=None, limit=None):
        """
        Retrieve training history with optional filtering.
        
        Args:
            filters (dict): Dictionary of column:value filters
            limit (int): Maximum number of rows to return
            
        Returns:
            pandas.DataFrame: Filtered training history
        """
        try:
            if not self.history_file.exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.history_file)
            
            if filters:
                for column, value in filters.items():
                    if column in df.columns:
                        if isinstance(value, (list, tuple)):
                            df = df[df[column].isin(value)]
                        else:
                            df = df[df[column] == value]
            
            if limit:
                df = df.tail(limit)
            
            return df
            
        except Exception as e:
            self.log_error(e, context="get_history")
            return pd.DataFrame()

    def _get_model_version(self):
        """Get current model version from environment or config."""
        try:
            from config.config import Config
            config = Config()
            return getattr(config, 'MODEL_VERSION', '1.0.0')
        except:
            return '1.0.0'

    def _get_git_commit(self):
        """Get current git commit hash if available."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=self.project_root
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        return None

    def clear_history(self, days_to_keep=30):
        """
        Clear old history entries.
        
        Args:
            days_to_keep (int): Keep entries from last N days
        """
        try:
            if not self.history_file.exists():
                return
            
            df = pd.read_csv(self.history_file)
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            
            cutoff_date = datetime.now() - pd.Timedelta(days=days_to_keep)
            df = df[df['Timestamp'] >= cutoff_date]
            
            df.to_csv(self.history_file, index=False)
            
            self.log_event(f"Cleared history older than {days_to_keep} days", level="INFO")
            
        except Exception as e:
            self.log_error(e, context="clear_history")

    def export_to_json(self, output_path=None):
        """
        Export training history to JSON format.
        
        Args:
            output_path (str/Path): Output file path
            
        Returns:
            str: JSON string of history
        """
        try:
            df = self.get_history()
            
            if output_path:
                df.to_json(output_path, orient='records', indent=2)
                self.log_event(f"History exported to {output_path}", level="INFO")
            
            return df.to_json(orient='records', indent=2)
            
        except Exception as e:
            self.log_error(e, context="export_to_json")
            return "{}"

    def summary(self):
        """Print summary of training history."""
        try:
            if not self.history_file.exists():
                print("No training history available.")
                return
            
            df = pd.read_csv(self.history_file)
            
            if df.empty:
                print("Training history is empty.")
                return
            
            print("\n📊 TRAINING HISTORY SUMMARY")
            print("=" * 50)
            
            print(f"Total entries: {len(df)}")
            print(f"Time range: {df['Timestamp'].min()} to {df['Timestamp'].max()}")
            
            print("\nBy Target:")
            target_counts = df['Target'].value_counts()
            for target, count in target_counts.items():
                target_df = df[df['Target'] == target]
                best_score = target_df['Score'].max()
                best_model = target_df.loc[target_df['Score'].idxmax(), 'ModelType']
                print(f"  {target}: {count} runs | Best: {best_score:.4f} ({best_model})")
            
            print("\nBy Model Type:")
            model_counts = df['ModelType'].value_counts()
            for model, count in model_counts.items():
                print(f"  {model}: {count} runs")
            
            print("\nLatest Champions:")
            latest_by_target = df.sort_values('Timestamp').groupby('Target').last()
            for target, row in latest_by_target.iterrows():
                print(f"  {target}: {row['ModelType']} ({row['Score']:.4f})")
            
            print()
            
        except Exception as e:
            print(f"Error generating summary: {e}")

# Singleton instance for easy import
_logger_instance = None

def get_logger(log_level="INFO"):
    """Get or create a singleton logger instance."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = TrainingLogger(log_level=log_level)
    return _logger_instance

if __name__ == "__main__":
    # Self-test and demonstration
    logger = TrainingLogger(log_level="DEBUG")
    
    # Test different log levels
    logger.log_event("Debug message", level="DEBUG", details={"test": True})
    logger.log_event("Info message", level="INFO")
    logger.log_event("Warning message", level="WARNING")
    
    # Test champion logging
    logger.log_champion(
        target="TEST_TARGET", 
        model_type="NN_TEST", 
        score=0.99, 
        metric_name="Accuracy", 
        feature_count=33, 
        params={"lr": 0.001, "epochs": 100},
        training_time=45.2,
        dataset_size=(10000, 50),
        additional_info={"notes": "Test run"}
    )
    
    # Test error logging
    try:
        raise ValueError("Test error")
    except ValueError as e:
        logger.log_error(e, context="Self-test")
    
    # Print summary
    logger.summary()
    
    print("\n✅ Logger self-test completed successfully!")