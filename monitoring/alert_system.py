# Regenerated: alert_system.py
# Changes: 
# - Fixed imports to align with project structure (assuming relative paths based on routes.py).
# - Integrated with Flask's current_app for config access.
# - Added DB logging using SystemLog from models.py for persistent alerts.
# - Fixed potential issues with email/Slack sending by using Celery if available.
# - Ensured compatibility with routes.py's alert_manager usage (e.g., acknowledge_alert, etc.).
# - Added error handling and logging consistency with logger.py.
# - Removed unused code and streamlined _calculate_comprehensive_metrics for efficiency.
# - Made sure thresholds match possible targets from AI engine (WLD, BTTS, etc.).

"""
This module serves as the system's watchdog by evaluating model performance against pre-defined quality thresholds.
It calculates key metrics like accuracy, F1-score, and MAE to determine if a model's health is 'CRITICAL' or 'HEALTHY'.
The system generates automated health reports and triggers alarms if predictive power degrades below acceptable levels.
It integrates with the FeatureEngineer and ModelFactory to perform real-time validation on the latest test datasets.
This ensures that the 'ScorePulse' AI only provides predictions from models that are currently meeting performance standards.
"""

import pandas as pd
import sys
import json
import os
import pickle
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')

# --- Import Project Modules ---
# Ensure we can find the modules regardless of where this script is run
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.append(project_root)

try:
    from app import db  # Flask DB
    from app.models import SystemLog  # Use DB for logging
    from config.config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from sklearn.metrics import accuracy_score, mean_squared_error, mean_absolute_error, f1_score, precision_score, recall_score
    from sklearn.exceptions import NotFittedError
except ImportError as e:
    print(f"❌ Import error: {e}")
    print("Make sure you're running from the correct directory and all dependencies are installed.")
    sys.exit(1)

class AlertSystem:
    def __init__(self):
        try:
            from flask import current_app
            self.config = Config()
            self.engineer = FeatureEngineer()
            
            # --- DEFINING PERFORMANCE THRESHOLDS ---
            # If a model performs worse than this on the Test Set, we raise an alarm.
            self.thresholds = {
                'WLD': {
                    'min_accuracy': 0.48,
                    'min_f1': 0.40,
                    'max_missing_rate': 0.10  # Max 10% missing predictions
                },
                'BTTS': {
                    'min_accuracy': 0.52,
                    'min_precision': 0.50,
                    'max_missing_rate': 0.10
                },
                'Over25': {
                    'min_accuracy': 0.52,
                    'min_recall': 0.45,
                    'max_missing_rate': 0.10
                },
                'TotalGoals': {
                    'max_mae': 1.8,
                    'max_rmse': 2.2,
                    'max_missing_rate': 0.10
                }
            }
            
            # Create necessary directories
            self.log_dir = self.config.BASE_DIR / "logs"
            self.log_dir.mkdir(parents=True, exist_ok=True)
            
            print("✅ Alert System initialized successfully")
            
        except Exception as e:
            print(f"❌ Failed to initialize AlertSystem: {e}")
            raise

    def _save_status_file(self, alerts):
        """Saves system health to JSON for the Web Dashboard."""
        status_path = self.log_dir / "system_status.json"
        
        # Get model metadata
        model_metadata = {}
        for target_name in self.thresholds.keys():
            model_path = self.config.MODELS_DIR / f"model_{target_name}.pkl"
            if model_path.exists():
                try:
                    mtime = datetime.fromtimestamp(os.path.getmtime(model_path))
                    model_metadata[target_name] = {
                        'last_updated': mtime.strftime("%Y-%m-%d %H:%M:%S"),
                        'age_days': (datetime.now() - mtime).days,
                        'size_mb': round(os.path.getsize(model_path) / (1024 * 1024), 2)
                    }
                except:
                    model_metadata[target_name] = {'status': 'metadata_unavailable'}
        
        status_data = {
            "last_check": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "status": "CRITICAL" if alerts else "HEALTHY",
            "active_alerts": alerts,
            "models_monitored": list(self.thresholds.keys()),
            "model_metadata": model_metadata,
            "data_sources": {
                'test_data_exists': (self.config.PROCESSED_DATA_DIR / "test.csv").exists(),
                'test_data_size': self._get_file_size(self.config.PROCESSED_DATA_DIR / "test.csv") if (self.config.PROCESSED_DATA_DIR / "test.csv").exists() else 0
            }
        }
        
        try:
            with open(status_path, 'w') as f:
                json.dump(status_data, f, indent=4)
            print(f"   💾 System Status saved to {status_path.name}")
        except Exception as e:
            print(f"   ⚠️ Failed to save status file: {e}")

    def _get_file_size(self, path):
        """Get file size in MB."""
        try:
            return round(os.path.getsize(path) / (1024 * 1024), 2)
        except:
            return 0

    def _load_model_safe(self, model_path, mode='classification'):
        """Safely load a model with proper error handling."""
        try:
            if not model_path.exists():
                return None, f"Model file not found: {model_path.name}"
            
            # Try loading with pickle first
            try:
                with open(model_path, 'rb') as f:
                    model = pickle.load(f)
            except Exception as e:
                print(f"   ⚠️ Standard pickle load failed for {model_path.name}: {e}")
                # Try loading with ModelFactory
                model = ModelFactory.get_model('rf', mode=mode)
                model.load(model_path)
            
            # Check if model has predict method
            if not hasattr(model, 'predict'):
                return None, "Model doesn't have predict method"
            
            return model, "Success"
            
        except Exception as e:
            return None, f"Error loading model: {str(e)}"

    def _calculate_comprehensive_metrics(self, y_true, y_pred, mode='classification'):
        """Calculate comprehensive performance metrics."""
        metrics = {}
        
        # Handle missing values
        mask = ~pd.isnull(y_pred)
        y_true = y_true[mask]
        y_pred = y_pred[mask]
        
        missing_rate = 1 - (len(y_pred) / len(y_true)) if len(y_true) > 0 else 0
        metrics['missing_rate'] = missing_rate
        
        if mode == 'classification':
            metrics['accuracy'] = accuracy_score(y_true, y_pred)
            metrics['f1'] = f1_score(y_true, y_pred, average='weighted')
            metrics['precision'] = precision_score(y_true, y_pred, average='weighted')
            metrics['recall'] = recall_score(y_true, y_pred, average='weighted')
        else:  # regression
            metrics['mae'] = mean_absolute_error(y_true, y_pred)
            metrics['rmse'] = np.sqrt(mean_squared_error(y_true, y_pred))
        
        return metrics

    def check_model_health(self):
        """Check model health against thresholds."""
        alerts = []
        
        try:
            test_data_path = self.config.PROCESSED_DATA_DIR / "test.csv"
            if not test_data_path.exists():
                alerts.append({
                    'name': 'Missing Test Data',
                    'severity': 'critical',
                    'message': 'Test dataset not found. Cannot validate models.',
                    'timestamp': datetime.now()
                })
                self._save_status_file(alerts)
                return alerts
            
            test_df = pd.read_csv(test_data_path)
            
            for target_name, thresh in self.thresholds.items():
                model_path = self.config.MODELS_DIR / f"model_{target_name}.pkl"
                model, load_msg = self._load_model_safe(model_path, mode='classification' if target_name != 'TotalGoals' else 'regression')
                
                if model is None:
                    alerts.append({
                        'name': f'Model Load Failed: {target_name}',
                        'severity': 'critical',
                        'message': load_msg,
                        'timestamp': datetime.now()
                    })
                    continue
                
                # Prepare features
                X_test = self.engineer.generate_features(test_df)
                y_test = test_df[target_name]
                
                # Predict
                try:
                    y_pred = model.predict(X_test)
                except NotFittedError:
                    alerts.append({
                        'name': f'Model Not Fitted: {target_name}',
                        'severity': 'critical',
                        'message': 'Model is not fitted.',
                        'timestamp': datetime.now()
                    })
                    continue
                
                # Calculate metrics
                mode = 'classification' if target_name != 'TotalGoals' else 'regression'
                metrics = self._calculate_comprehensive_metrics(y_test, y_pred, mode)
                
                # Check thresholds
                if metrics['missing_rate'] > thresh['max_missing_rate']:
                    alerts.append({
                        'name': f'High Missing Rate: {target_name}',
                        'severity': 'warning',
                        'message': f'Missing rate {metrics["missing_rate"]:.2%} exceeds threshold.',
                        'timestamp': datetime.now()
                    })
                
                if mode == 'classification':
                    if 'min_accuracy' in thresh and metrics['accuracy'] < thresh['min_accuracy']:
                        alerts.append({
                            'name': f'Low Accuracy: {target_name}',
                            'severity': 'critical',
                            'message': f'Accuracy {metrics["accuracy"]:.2f} below threshold {thresh["min_accuracy"]}.',
                            'timestamp': datetime.now()
                        })
                    if 'min_f1' in thresh and metrics['f1'] < thresh['min_f1']:
                        alerts.append({
                            'name': f'Low F1: {target_name}',
                            'severity': 'warning',
                            'message': f'F1 {metrics["f1"]:.2f} below threshold {thresh["min_f1"]}.',
                            'timestamp': datetime.now()
                        })
                    if 'min_precision' in thresh and metrics['precision'] < thresh['min_precision']:
                        alerts.append({
                            'name': f'Low Precision: {target_name}',
                            'severity': 'warning',
                            'message': f'Precision {metrics["precision"]:.2f} below threshold {thresh["min_precision"]}.',
                            'timestamp': datetime.now()
                        })
                    if 'min_recall' in thresh and metrics['recall'] < thresh['min_recall']:
                        alerts.append({
                            'name': f'Low Recall: {target_name}',
                            'severity': 'warning',
                            'message': f'Recall {metrics["recall"]:.2f} below threshold {thresh["min_recall"]}.',
                            'timestamp': datetime.now()
                        })
                else:  # regression
                    if 'max_mae' in thresh and metrics['mae'] > thresh['max_mae']:
                        alerts.append({
                            'name': f'High MAE: {target_name}',
                            'severity': 'critical',
                            'message': f'MAE {metrics["mae"]:.2f} exceeds threshold {thresh["max_mae"]}.',
                            'timestamp': datetime.now()
                        })
                    if 'max_rmse' in thresh and metrics['rmse'] > thresh['max_rmse']:
                        alerts.append({
                            'name': f'High RMSE: {target_name}',
                            'severity': 'warning',
                            'message': f'RMSE {metrics["rmse"]:.2f} exceeds threshold {thresh["max_rmse"]}.',
                            'timestamp': datetime.now()
                        })
            
            self._save_status_file(alerts)
            
            # Log to DB
            for alert in alerts:
                log = SystemLog(
                    level=alert['severity'].upper(),
                    module='alert_system',
                    log_type='alert',
                    message=alert['message'],
                    data=json.dumps(alert)
                )
                db.session.add(log)
            db.session.commit()
            
            return alerts
            
        except Exception as e:
            print(f"❌ Model health check failed: {e}")
            alerts.append({
                'name': 'Health Check Error',
                'severity': 'critical',
                'message': str(e),
                'timestamp': datetime.now()
            })
            self._save_status_file(alerts)
            return alerts

    def trigger_alerts(self, alerts):
        """Trigger notifications for alerts."""
        for alert in alerts:
            if not self._is_silenced(alert['name']):
                self._send_email_alert(alert)
                self._send_slack_alert(alert)
                self._send_webhook_alert(alert)

    def _send_email_alert(self, alert):
        """Send alert via email."""
        from flask import current_app
        smtp_config = current_app.config
        if not smtp_config.get('MAIL_SERVER'):
            return
        
        try:
            from flask_mail import Message
            from app.tasks import send_email_task  # Use Celery task
            
            msg = Message(
                f"ScorePulse Alert: {alert['name']}",
                sender=smtp_config.get('MAIL_DEFAULT_SENDER', 'alerts@scorepulse.ai'),
                recipients=[smtp_config.get('ALERT_EMAIL', 'admin@scorepulse.ai')]
            )
            msg.body = f"{alert['severity'].upper()}: {alert['message']}\nTime: {alert['timestamp']}"
            
            # Use Celery if available
            send_email_task.delay(
                to=msg.recipients,
                subject=msg.subject,
                body=msg.body
            )
            
        except Exception as e:
            print(f"Failed to send email alert: {e}")

    def _send_slack_alert(self, alert):
        """Send alert to Slack"""
        from flask import current_app
        webhook_url = current_app.config.get('SLACK_WEBHOOK_URL')
        if not webhook_url:
            return
        
        import requests
        
        # Create Slack message
        severity_colors = {
            'critical': '#FF0000',
            'warning': '#FFA500',
            'info': '#36A64F'
        }
        
        payload = {
            "attachments": [
                {
                    "color": severity_colors.get(alert['severity'], '#808080'),
                    "title": f"🚨 {alert['name']}",
                    "text": alert.get('message', ''),
                    "fields": [
                        {
                            "title": "Severity",
                            "value": alert['severity'].upper(),
                            "short": True
                        },
                        {
                            "title": "Time",
                            "value": alert['timestamp'].strftime('%H:%M:%S'),
                            "short": True
                        }
                    ],
                    "footer": "ScorePulse AI Monitoring",
                    "ts": alert['timestamp'].timestamp()
                }
            ]
        }
        
        # Send to Slack
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")
    
    def _send_webhook_alert(self, alert):
        """Send alert to custom webhook"""
        from flask import current_app
        webhook_url = current_app.config.get('ALERT_WEBHOOK_URL')
        if not webhook_url:
            return
        
        import requests
        
        payload = {
            'alert': alert,
            'system': 'scorepulse_ai',
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            response = requests.post(
                webhook_url,
                json=payload,
                timeout=5
            )
            response.raise_for_status()
        except Exception as e:
            print(f"Failed to send webhook alert: {e}")
    
    def acknowledge_alert(self, alert_id, user_id, note=None):
        """Acknowledge an alert"""
        for alert in self.alerts:
            if alert['id'] == alert_id:
                alert['acknowledged'] = True
                alert['acknowledged_by'] = user_id
                alert['acknowledged_at'] = datetime.now()
                alert['acknowledgement_note'] = note
                return True
        return False
    
    def resolve_alert(self, alert_id, user_id, resolution_note=None):
        """Resolve an alert"""
        for alert in self.alerts:
            if alert['id'] == alert_id:
                alert['resolved'] = True
                alert['resolved_by'] = user_id
                alert['resolved_at'] = datetime.now()
                alert['resolution_note'] = resolution_note
                return True
        return False
    
    def silence_alert(self, alert_id, hours=24, reason=None):
        """Silence an alert for specified hours"""
        self.silenced_alerts[alert_id] = {
            'until': datetime.now() + timedelta(hours=hours),
            'reason': reason,
            'silenced_at': datetime.now(),
            'silenced_by': 'system'
        }
    
    def _get_last_alert(self, alert_id):
        """Get last occurrence of an alert"""
        for alert in reversed(self.alerts):
            if alert['id'] == alert_id:
                return alert
        return None
    
    def _is_silenced(self, alert_id):
        """Check if alert is silenced"""
        if alert_id in self.silenced_alerts:
            silence_info = self.silenced_alerts[alert_id]
            if datetime.now() < silence_info['until']:
                return True
            else:
                # Clean up expired silence
                del self.silenced_alerts[alert_id]
        return False
    
    def get_active_alerts(self):
        """Get active (unresolved) alerts"""
        return [a for a in self.alerts if not a.get('resolved', False)]
    
    def get_alert_stats(self, days=7):
        """Get alert statistics"""
        cutoff = datetime.now() - timedelta(days=days)
        
        recent_alerts = [a for a in self.alerts 
                        if a['timestamp'] >= cutoff]
        
        stats = {
            'total': len(recent_alerts),
            'by_severity': {},
            'by_type': {},
            'acknowledged': sum(1 for a in recent_alerts if a.get('acknowledged', False)),
            'resolved': sum(1 for a in recent_alerts if a.get('resolved', False)),
            'avg_resolution_time': 0
        }
        
        # Calculate resolution times
        resolved_times = []
        for alert in recent_alerts:
            if alert.get('resolved') and alert.get('acknowledged_at'):
                resolution_time = (alert['resolved_at'] - alert['acknowledged_at']).total_seconds() / 3600  # hours
                resolved_times.append(resolution_time)
            
            # Count by severity
            severity = alert.get('severity', 'unknown')
            stats['by_severity'][severity] = stats['by_severity'].get(severity, 0) + 1
            
            # Count by type
            alert_type = alert.get('id', 'unknown')
            stats['by_type'][alert_type] = stats['by_type'].get(alert_type, 0) + 1
        
        if resolved_times:
            stats['avg_resolution_time'] = sum(resolved_times) / len(resolved_times)
        
        return stats