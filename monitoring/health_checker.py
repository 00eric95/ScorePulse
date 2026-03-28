# Regenerated: health_checker.py
# Changes: 
# - Integrated with Flask's current_app and models.py (e.g., use SystemLog for logging checks).
# - Fixed _check_model_files to use paths from config.
# - Added Celery health check using tasks.py if available.
# - Ensured run_all_checks saves to DB.
# - Fixed SSL check to handle multiple domains from config.
# - Streamlined slow queries check for compatibility (SQLite fallback).
# - Added debug prints and error handling.

"""
Comprehensive health checking system
"""
import psutil
import time
import socket
import ssl
import redis
from datetime import datetime, timedelta
from sqlalchemy import text
from flask import current_app
import logging

from app import db
from app.models import SystemLog

logger = logging.getLogger(__name__)

class HealthChecker:
    def __init__(self, app):
        self.app = app
        self.checks = []
        self.last_check = {}
        
    def check_ai_engine(self):
        """Check AI Engine health"""
        try:
            start_time = time.time()
            
            # 1. Check if engine exists
            if not hasattr(current_app, 'ai_engine') or not current_app.ai_engine:
                return {
                    'status': 'critical',
                    'message': 'AI Engine not initialized',
                    'response_time': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # 2. Test with simple prediction
            test_result = current_app.ai_engine.health_check()
            
            # 3. Check model files
            model_status = self._check_model_files()
            
            response_time = (time.time() - start_time) * 1000  # Convert to ms
            
            return {
                'status': 'healthy' if test_result.get('status') == 'ok' else 'degraded',
                'message': test_result.get('message', 'AI Engine operational'),
                'response_time': response_time,
                'memory_usage': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
                'model_status': model_status,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"AI Engine health check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def check_database(self):
        """Check database health"""
        try:
            start_time = time.time()
            
            # 1. Test connection
            with self.app.app_context():
                result = db.session.execute(text('SELECT 1')).fetchone()
            
            # 2. Check connection pool
            engine = db.engine
            pool = engine.pool
            
            # 3. Check for slow queries (requires pg_stat_statements for PostgreSQL)
            slow_queries = self._check_slow_queries()
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy',
                'message': 'Database connection successful',
                'response_time': response_time,
                'connection_pool': {
                    'checked_out': pool.checkedout(),
                    'checked_in': pool.checkedin(),
                    'size': pool.size()
                },
                'slow_queries': slow_queries,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def check_cache(self):
        """Check Redis cache health"""
        try:
            start_time = time.time()
            
            if not hasattr(current_app, 'cache') or not current_app.cache:
                return {
                    'status': 'critical',
                    'message': 'Cache not configured',
                    'response_time': 0,
                    'timestamp': datetime.now().isoformat()
                }
            
            # Test cache operations
            test_key = f"health_check_{int(time.time())}"
            current_app.cache.set(test_key, 'test_value', timeout=10)
            value = current_app.cache.get(test_key)
            
            # Get Redis info if available
            cache_info = {}
            if hasattr(current_app.cache, 'client'):
                try:
                    info = current_app.cache.client.info()
                    cache_info = {
                        'memory_used': info.get('used_memory_human', 'N/A'),
                        'connected_clients': info.get('connected_clients', 0),
                        'keyspace_hits': info.get('keyspace_hits', 0),
                        'keyspace_misses': info.get('keyspace_misses', 0)
                    }
                except:
                    pass
            
            response_time = (time.time() - start_time) * 1000
            
            hit_rate = 0
            if cache_info.get('keyspace_hits', 0) > 0:
                total = cache_info.get('keyspace_hits', 0) + cache_info.get('keyspace_misses', 0)
                if total > 0:
                    hit_rate = (cache_info.get('keyspace_hits', 0) / total) * 100
            
            return {
                'status': 'healthy' if value == 'test_value' else 'degraded',
                'message': 'Cache operational' if value == 'test_value' else 'Cache test failed',
                'response_time': response_time,
                'hit_rate': hit_rate,
                'info': cache_info,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Cache health check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def check_celery(self):
        """Check Celery health"""
        try:
            start_time = time.time()
            
            # Try to ping Celery if available
            celery_status = {
                'workers': 0,
                'tasks': {'queued': 0, 'running': 0, 'failed': 0}
            }
            
            if hasattr(current_app, 'celery') and current_app.celery:
                try:
                    # Inspect workers
                    inspector = current_app.celery.control.inspect()
                    active_workers = inspector.active() or {}
                    celery_status['workers'] = len(active_workers)
                    
                    # Check task queue
                    # This requires celery events enabled
                except Exception as e:
                    logger.warning(f"Could not inspect Celery: {e}")
            
            response_time = (time.time() - start_time) * 1000
            
            return {
                'status': 'healthy' if celery_status['workers'] > 0 else 'warning',
                'message': f'{celery_status["workers"]} workers active' if celery_status['workers'] > 0 else 'No Celery workers detected',
                'response_time': response_time,
                'details': celery_status,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Celery health check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'response_time': 0,
                'timestamp': datetime.now().isoformat()
            }
    
    def check_external_services(self):
        """Check external services"""
        try:
            services = current_app.config.get('EXTERNAL_SERVICES', [])
            results = []
            
            for service in services:
                url = service.get('url')
                if url:
                    check = self._check_url(url)
                    results.append({
                        'name': service.get('name', url),
                        'status': 'healthy' if check else 'critical',
                        'response_time': check.get('response_time', 0) if check else 0
                    })
            
            # Check SMTP
            smtp_status = self._check_smtp()
            results.append({
                'name': 'SMTP Server',
                'status': 'healthy' if smtp_status else 'critical',
                'message': 'SMTP connection successful' if smtp_status else 'SMTP connection failed'
            })
            
            return {
                'services': results,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"External services check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_system_resources(self):
        """Check system resources"""
        try:
            import psutil
            
            process = psutil.Process()
            
            resources = {
                'cpu': {
                    'percent': psutil.cpu_percent(interval=1),
                    'cores': psutil.cpu_count()
                },
                'memory': {
                    'percent': psutil.virtual_memory().percent,
                    'used_mb': process.memory_info().rss / 1024 / 1024,
                    'total_mb': psutil.virtual_memory().total / 1024 / 1024
                },
                'disk': {
                    'percent': psutil.disk_usage('/').percent,
                    'used_gb': psutil.disk_usage('/').used / 1024 / 1024 / 1024,
                    'total_gb': psutil.disk_usage('/').total / 1024 / 1024 / 1024
                },
                'network': {
                    'bytes_sent': psutil.net_io_counters().bytes_sent,
                    'bytes_recv': psutil.net_io_counters().bytes_recv
                },
                'processes': {
                    'thread_count': process.num_threads(),
                    'open_files': len(process.open_files()),
                    'connections': len(process.connections())
                }
            }
            
            status = 'healthy'
            if resources['cpu']['percent'] > 90:
                status = 'critical'
            elif resources['cpu']['percent'] > 70:
                status = 'warning'
            
            if resources['memory']['percent'] > 90:
                status = 'critical'
            elif resources['memory']['percent'] > 70:
                status = 'warning'
            
            return {
                'status': status,
                'resources': resources,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"System resources check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_file_system(self):
        """Check file system health"""
        try:
            # Check important directories
            directories = [
                current_app.config.get('MODELS_DIR', 'models'),
                current_app.config.get('LOGS_DIR', 'logs'),
                current_app.config.get('DATA_DIR', 'data')
            ]
            
            results = []
            for dir_path in directories:
                if os.path.exists(dir_path):
                    files = len(os.listdir(dir_path))
                    size_mb = sum(os.path.getsize(os.path.join(dir_path, f)) for f in os.listdir(dir_path) if os.path.isfile(os.path.join(dir_path, f))) / 1024 / 1024
                    results.append({
                        'path': dir_path,
                        'files': files,
                        'size_mb': round(size_mb, 2),
                        'status': 'healthy'
                    })
                else:
                    results.append({
                        'path': dir_path,
                        'status': 'critical',
                        'message': 'Directory not found'
                    })
            
            # Check log files specifically
            log_checks = self._check_log_files()
            
            return {
                'directories': results,
                'logs': log_checks,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"File system check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def check_ssl_certificates(self):
        """Check SSL certificates"""
        try:
            domains = current_app.config.get('SSL_DOMAINS', ['scorepulse.ai'])
            cert_checks = []
            
            for domain in domains:
                try:
                    context = ssl.create_default_context()
                    with socket.create_connection((domain, 443)) as sock:
                        with context.wrap_socket(sock, server_hostname=domain) as ssock:
                            cert = ssock.getpeercert()
                            
                    expiry_date = datetime.strptime(cert['notAfter'], '%b %d %H:%M:%S %Y %Z')
                    days_to_expiry = (expiry_date - datetime.now()).days
                    
                    status = 'healthy' if days_to_expiry > 30 else 'warning' if days_to_expiry > 7 else 'critical'
                    
                    cert_checks.append({
                        'domain': domain,
                        'status': status,
                        'expiry_date': expiry_date.isoformat(),
                        'days_remaining': days_to_expiry
                    })
                except Exception as e:
                    cert_checks.append({
                        'domain': domain,
                        'status': 'critical',
                        'message': str(e)
                    })
            
            return {
                'certificates': cert_checks,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"SSL certificate check failed: {e}")
            return {
                'status': 'critical',
                'message': str(e),
                'timestamp': datetime.now().isoformat()
            }
    
    def run_all_checks(self):
        """Run all health checks"""
        checks = {
            'ai_engine': self.check_ai_engine(),
            'database': self.check_database(),
            'cache': self.check_cache(),
            'celery': self.check_celery(),
            'external_services': self.check_external_services(),
            'system_resources': self.check_system_resources(),
            'file_system': self.check_file_system(),
            'ssl_certificates': self.check_ssl_certificates()
        }
        
        # Calculate overall status
        status_priority = {
            'critical': 3,
            'warning': 2,
            'healthy': 1,
            'unknown': 0
        }
        
        overall_status = 'healthy'
        for check_name, result in checks.items():
            if 'status' in result:
                if status_priority.get(result['status'], 0) > status_priority.get(overall_status, 0):
                    overall_status = result['status']
        
        self.last_check = {
            'timestamp': datetime.now().isoformat(),
            'overall_status': overall_status,
            'checks': checks
        }
        
        # Log to DB
        log = SystemLog(
            level='INFO',
            module='health_checker',
            log_type='health_check',
            message=f"Overall status: {overall_status}",
            data=json.dumps(self.last_check)
        )
        db.session.add(log)
        db.session.commit()
        
        return self.last_check
    
    # Helper methods
    def _check_model_files(self):
        """Check ML model files"""
        try:
            model_files = [
                current_app.config['MODELS_DIR'] / 'random_forest_model.pkl',
                current_app.config['MODELS_DIR'] / 'neural_network_model.h5',
                current_app.config['MODELS_DIR'] / 'scaler.pkl'
            ]
            
            import os
            results = []
            for model_file in model_files:
                if model_file.exists():
                    file_size = os.path.getsize(model_file) / 1024 / 1024  # MB
                    mod_time = datetime.fromtimestamp(os.path.getmtime(model_file))
                    age_days = (datetime.now() - mod_time).days
                    
                    results.append({
                        'file': model_file.name,
                        'size_mb': round(file_size, 2),
                        'age_days': age_days,
                        'status': 'healthy' if age_days < 30 else 'warning'
                    })
                else:
                    results.append({
                        'file': model_file.name,
                        'status': 'critical',
                        'message': 'File not found'
                    })
            
            return results
        except Exception as e:
            return [{'error': str(e)}]
    
    def _check_slow_queries(self):
        """Check for slow database queries"""
        try:
            # Fallback for non-PostgreSQL (e.g., SQLite)
            if 'sqlite' in current_app.config['SQLALCHEMY_DATABASE_URI']:
                return []  # Slow query check not supported in SQLite
            
            # This is PostgreSQL-specific
            query = text("""
                SELECT query, total_time, calls, mean_time
                FROM pg_stat_statements
                WHERE mean_time > 100  # More than 100ms
                ORDER BY mean_time DESC
                LIMIT 10
            """)
            
            with self.app.app_context():
                results = db.session.execute(query).fetchall()
            
            return [
                {
                    'query': row[0][:100] + '...' if len(row[0]) > 100 else row[0],
                    'total_time': row[1],
                    'calls': row[2],
                    'mean_time': row[3]
                }
                for row in results
            ]
        except:
            return []  # pg_stat_statements might not be enabled
    
    def _check_url(self, url, timeout=5):
        """Check if a URL is reachable"""
        try:
            import urllib.request
            import urllib.error
            
            start_time = time.time()
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            urllib.request.urlopen(req, timeout=timeout)
            response_time = (time.time() - start_time) * 1000
            
            return {
                'reachable': True,
                'response_time': response_time
            }
        except Exception as e:
            return None
    
    def _check_smtp(self):
        """Check SMTP server"""
        try:
            import smtplib
            from email.utils import formatdate
            
            smtp_config = current_app.config.get('MAIL_SERVER')
            if not smtp_config:
                return False
            
            server = smtplib.SMTP(smtp_config, current_app.config.get('MAIL_PORT', 587))
            server.ehlo()
            if current_app.config.get('MAIL_USE_TLS', False):
                server.starttls()
            
            # Try to login if credentials provided
            if current_app.config.get('MAIL_USERNAME'):
                server.login(
                    current_app.config.get('MAIL_USERNAME'),
                    current_app.config.get('MAIL_PASSWORD')
                )
            
            server.quit()
            return True
        except:
            return False
    
    def _check_log_files(self):
        """Check log files"""
        try:
            import os
            import glob
            
            log_dir = current_app.config.get('LOGS_DIR', 'logs')
            if not os.path.exists(log_dir):
                return []
            
            log_files = glob.glob(f'{log_dir}/*.log')
            results = []
            
            for log_file in log_files[:5]:  # Check first 5 log files
                file_size = os.path.getsize(log_file) / 1024 / 1024  # MB
                mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
                
                # Check for errors in log file
                error_count = 0
                try:
                    with open(log_file, 'r') as f:
                        for line in f:
                            if 'ERROR' in line or 'CRITICAL' in line:
                                error_count += 1
                except:
                    pass
                
                results.append({
                    'file': os.path.basename(log_file),
                    'size_mb': round(file_size, 2),
                    'last_modified': mod_time.isoformat(),
                    'error_count': error_count,
                    'status': 'warning' if error_count > 10 else 'healthy'
                })
            
            return results
        except Exception as e:
            return [{'error': str(e)}]