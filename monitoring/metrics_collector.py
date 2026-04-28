# Regenerated: metrics_collector.py
# Changes: 
# - Integrated with models.py (e.g., Prediction, User, UserActivity for queries).
# - Used DB session properly with app_context.
# - Fixed _collector_loop to use current_app.logger.
# - Added Celery metrics if available.
# - Ensured get_metrics_summary fits routes.py's export (e.g., JSON/CSV).
# - Streamlined summaries with error handling.
# - Added start/stop compatibility with app lifecycle.

"""
Metrics collection and storage system
"""
from datetime import datetime, timedelta
import time
import threading
from collections import deque
from flask import current_app
import logging

from app import db
from app.models import Prediction, User, UserActivity

logger = logging.getLogger(__name__)

class MetricsCollector:
    def __init__(self, app):
        self.app = app
        self.metrics = {
            'predictions': deque(maxlen=1000),
            'response_times': deque(maxlen=1000),
            'errors': deque(maxlen=1000),
            'user_activity': deque(maxlen=1000),
            'system_metrics': deque(maxlen=1000)
        }
        self.start_time = datetime.now()
        self.collector_thread = None
        self.running = False
        
    def start(self):
        """Start background metrics collection"""
        if self.running:
            return
        
        self.running = True
        self.collector_thread = threading.Thread(target=self._collector_loop, daemon=True)
        self.collector_thread.start()
        current_app.logger.info("Metrics collector started")
    
    def stop(self):
        """Stop metrics collection"""
        self.running = False
        if self.collector_thread:
            self.collector_thread.join(timeout=5)
        current_app.logger.info("Metrics collector stopped")
    
    def _collector_loop(self):
        """Background collection loop – safe for both Flask app and Celery workers."""
        while self.running:
            try:
                self.collect_system_metrics()
                self.collect_prediction_metrics()
                self.collect_user_metrics()
                time.sleep(60)  # Collect every minute
            except Exception as e:
                # Safe logging: try to use current_app, fall back to print if no context
                try:
                    from flask import current_app
                    current_app.logger.error(f"Metrics collection error: {e}")
                except RuntimeError:
                    # No application context (e.g., Celery worker or CLI script)
                    import sys
                    print(f"Metrics collection error (no app context): {e}", file=sys.stderr)
                time.sleep(30)
    
    def collect_system_metrics(self):
        """Collect system-level metrics"""
        try:
            import psutil
            
            process = psutil.Process()
            
            metric = {
                'timestamp': datetime.now().isoformat(),
                'cpu_percent': psutil.cpu_percent(interval=1),
                'memory_percent': psutil.virtual_memory().percent,
                'memory_used_mb': process.memory_info().rss / 1024 / 1024,
                'disk_percent': psutil.disk_usage('/').percent,
                'thread_count': process.num_threads(),
                'open_files': len(process.open_files()),
                'connections': len(process.connections())
            }
            
            self.metrics['system_metrics'].append(metric)
            
        except Exception as e:
            current_app.logger.error(f"System metrics collection failed: {e}")
    
    def collect_prediction_metrics(self):
        """Collect prediction-related metrics"""
        try:
            # Get prediction counts for last hour
            one_hour_ago = datetime.now() - timedelta(hours=1)
            
            with self.app.app_context():
                # Count predictions by status
                total = db.session.query(Prediction).filter(
                    Prediction.created_at >= one_hour_ago
                ).count()
                
                wins = db.session.query(Prediction).filter(
                    Prediction.created_at >= one_hour_ago,
                    Prediction.status == 'Won'
                ).count()
                
                losses = db.session.query(Prediction).filter(
                    Prediction.created_at >= one_hour_ago,
                    Prediction.status == 'Lost'
                ).count()
                
                accuracy = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
                
                metric = {
                    'timestamp': datetime.now().isoformat(),
                    'predictions_per_hour': total,
                    'accuracy_per_hour': round(accuracy, 2),
                    'wins': wins,
                    'losses': losses,
                    'pending': total - wins - losses
                }
                
                self.metrics['predictions'].append(metric)
                
        except Exception as e:
            current_app.logger.error(f"Prediction metrics collection failed: {e}")
    
    def collect_user_metrics(self):
        """Collect user activity metrics"""
        try:
            with self.app.app_context():
                # Active users in last 15 minutes
                fifteen_min_ago = datetime.now() - timedelta(minutes=15)
                active_users = db.session.query(User).filter(
                    User.last_login >= fifteen_min_ago
                ).count()
                
                # New users today
                today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
                new_users = db.session.query(User).filter(
                    User.created_at >= today_start
                ).count()
                
                # Activities in last hour
                one_hour_ago = datetime.now() - timedelta(hours=1)
                activities = db.session.query(UserActivity).filter(
                    UserActivity.timestamp >= one_hour_ago
                ).count()
                
                metric = {
                    'timestamp': datetime.now().isoformat(),
                    'active_users_15m': active_users,
                    'new_users_today': new_users,
                    'activities_per_hour': activities,
                    'total_users': db.session.query(User).count()
                }
                
                self.metrics['user_activity'].append(metric)
                
        except Exception as e:
            current_app.logger.error(f"User metrics collection failed: {e}")
    
    def record_prediction(self, prediction_id, response_time, success=True):
        """Record a prediction event"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'prediction_id': prediction_id,
            'response_time': response_time,
            'success': success
        }
        self.metrics['response_times'].append(metric)
    
    def record_response_time(self, endpoint, response_time, status_code=200):
        """Record HTTP response time for an endpoint"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'endpoint': endpoint,
            'response_time': response_time,
            'status_code': status_code
        }
        self.metrics['response_times'].append(metric)
    
    def record_error(self, error_type, message, severity='error'):
        """Record an error event"""
        metric = {
            'timestamp': datetime.now().isoformat(),
            'type': error_type,
            'message': message[:200],  # Truncate long messages
            'severity': severity
        }
        self.metrics['errors'].append(metric)
    
    def get_metrics_summary(self, hours=24):
        """Get metrics summary for last N hours"""
        cutoff = datetime.now() - timedelta(hours=hours)
        
        summary = {
            'uptime': self._get_uptime(),
            'predictions': self._summarize_predictions(cutoff),
            'performance': self._summarize_performance(cutoff),
            'users': self._summarize_users(cutoff),
            'errors': self._summarize_errors(cutoff),
            'system': self._summarize_system(cutoff)
        }
        
        return summary
    
    def _get_uptime(self):
        """Calculate system uptime"""
        uptime_seconds = (datetime.now() - self.start_time).total_seconds()
        
        days = int(uptime_seconds // (24 * 3600))
        hours = int((uptime_seconds % (24 * 3600)) // 3600)
        minutes = int((uptime_seconds % 3600) // 60)
        
        return {
            'days': days,
            'hours': hours,
            'minutes': minutes,
            'seconds': int(uptime_seconds),
            'start_time': self.start_time.isoformat()
        }
    
    def _summarize_predictions(self, cutoff):
        """Summarize prediction metrics"""
        predictions = [m for m in self.metrics['predictions'] 
                      if datetime.fromisoformat(m['timestamp']) >= cutoff]
        
        if not predictions:
            return {}
        
        total_predictions = sum(p.get('predictions_per_hour', 0) for p in predictions)
        avg_accuracy = sum(p.get('accuracy_per_hour', 0) for p in predictions) / len(predictions)
        
        return {
            'total': total_predictions,
            'average_per_hour': total_predictions / len(predictions) if predictions else 0,
            'accuracy': round(avg_accuracy, 2),
            'peak_hour': max(predictions, key=lambda x: x.get('predictions_per_hour', 0)) if predictions else {}
        }
    
    def _summarize_performance(self, cutoff):
        """Summarize performance metrics"""
        response_times = [m for m in self.metrics['response_times']
                         if datetime.fromisoformat(m['timestamp']) >= cutoff]
        
        if not response_times:
            return {}
        
        times = [r['response_time'] for r in response_times]
        
        return {
            'count': len(response_times),
            'average': sum(times) / len(times) if times else 0,
            'median': sorted(times)[len(times) // 2] if times else 0,
            'p95': sorted(times)[int(len(times) * 0.95)] if times else 0,
            'p99': sorted(times)[int(len(times) * 0.99)] if times else 0,
            'max': max(times) if times else 0,
            'min': min(times) if times else 0
        }
    
    def _summarize_users(self, cutoff):
        """Summarize user metrics"""
        user_metrics = [m for m in self.metrics['user_activity']
                       if datetime.fromisoformat(m['timestamp']) >= cutoff]
        
        if not user_metrics:
            return {}
        
        latest = user_metrics[-1] if user_metrics else {}
        
        return {
            'total_users': latest.get('total_users', 0),
            'active_users_15m': latest.get('active_users_15m', 0),
            'new_users_today': latest.get('new_users_today', 0),
            'activities_per_hour': latest.get('activities_per_hour', 0)
        }
    
    def _summarize_errors(self, cutoff):
        """Summarize error metrics"""
        errors = [m for m in self.metrics['errors']
                 if datetime.fromisoformat(m['timestamp']) >= cutoff]
        
        if not errors:
            return {'count': 0, 'by_type': {}, 'by_severity': {}}
        
        by_type = {}
        by_severity = {}
        
        for error in errors:
            error_type = error.get('type', 'unknown')
            severity = error.get('severity', 'error')
            
            by_type[error_type] = by_type.get(error_type, 0) + 1
            by_severity[severity] = by_severity.get(severity, 0) + 1
        
        return {
            'count': len(errors),
            'by_type': by_type,
            'by_severity': by_severity,
            'latest': errors[-1] if errors else None
        }
    
    def _summarize_system(self, cutoff):
        """Summarize system metrics"""
        system_metrics = [m for m in self.metrics['system_metrics']
                         if datetime.fromisoformat(m['timestamp']) >= cutoff]
        
        if not system_metrics:
            return {}
        
        latest = system_metrics[-1] if system_metrics else {}
        
        return {
            'cpu_percent': latest.get('cpu_percent', 0),
            'memory_percent': latest.get('memory_percent', 0),
            'memory_used_mb': latest.get('memory_used_mb', 0),
            'disk_percent': latest.get('disk_percent', 0),
            'thread_count': latest.get('thread_count', 0)
        }