# app/__init__.py
import time
import sys
import os
import threading
import traceback
import json
from datetime import datetime, timedelta
from dotenv import load_dotenv

from flask import Flask, url_for, request, g, render_template, current_app
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_socketio import SocketIO
from flask_migrate import Migrate
from flask_apscheduler import APScheduler
from celery import Celery, Task
from celery.schedules import crontab
import redis
import pickle

# --- Path Configuration ---
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
sys.path.insert(0, parent_dir)

# Try to import Config
try:
    from settings import Config
except ImportError:
    try:
        from config import Config
    except ImportError:
        print("⚠️ CRITICAL: Could not find settings.py or config.py")
        class Config:
            SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
            SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///scorepulse.db')
            SQLALCHEMY_TRACK_MODIFICATIONS = False
            MAIL_SERVER = 'smtp.gmail.com'
            MAIL_PORT = 587
            MAIL_USE_TLS = True
            MAIL_USERNAME = os.environ.get('MAIL_USERNAME')
            MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
            GOOGLE_OAUTH_ENABLED = True
            APP_NAME = 'ScorePulse AI'
            REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
            REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
            REDIS_DB = int(os.environ.get('REDIS_DB', 0))
            REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
            REDIS_CACHE_TIMEOUT = int(os.environ.get('REDIS_CACHE_TIMEOUT', 3600))
            CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'
            CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL',
                f"redis://{REDIS_HOST}:{REDIS_PORT}/1" if REDIS_PASSWORD is None else
                f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/1")
            CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND',
                f"redis://{REDIS_HOST}:{REDIS_PORT}/2" if REDIS_PASSWORD is None else
                f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/2")
            CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'false').lower() == 'true'
            CELERY_TASK_SERIALIZER = 'json'
            CELERY_RESULT_SERIALIZER = 'json'
            CELERY_ACCEPT_CONTENT = ['json']
            CELERY_TIMEZONE = 'Africa/Nairobi'
            CELERY_ENABLE_UTC = True
            CELERY_WORKER_POOL = 'gevent'


# ==================== Redis Cache (unchanged) ====================
class RedisCache:
    """Hybrid Redis cache with local fallback for performance and reliability."""
    def __init__(self):
        self.redis_client = None
        self.local_cache = {}
        self.config = None
        self.enabled = True
        self.local_cache_max_size = 1000
        self.local_cache_ttl = 300

    def init_app(self, app):
        self.config = app.config
        self.enabled = app.config.get('CACHE_ENABLED', True)
        if self.enabled:
            try:
                self.redis_client = redis.Redis(
                    host=app.config.get('REDIS_HOST', 'localhost'),
                    port=app.config.get('REDIS_PORT', 6379),
                    db=app.config.get('REDIS_DB', 0),
                    password=app.config.get('REDIS_PASSWORD', None),
                    decode_responses=False,
                    socket_timeout=5,
                    socket_connect_timeout=5,
                    retry_on_timeout=True,
                    max_connections=10
                )
                self.redis_client.ping()
                print("✅ Redis Cache connected")
            except Exception as e:
                print(f"⚠️ Redis Cache connection failed: {e}")
                self.redis_client = None
                self.enabled = False
                print("⚠️ Falling back to local cache only")
        else:
            print("⚠️ Redis Cache disabled")
        self._start_cleanup_thread()

    def _start_cleanup_thread(self):
        def cleanup():
            while True:
                time.sleep(60)
                now = time.time()
                expired_keys = [
                    key for key, (value, expiry) in self.local_cache.items()
                    if expiry and expiry < now
                ]
                for key in expired_keys:
                    del self.local_cache[key]
        thread = threading.Thread(target=cleanup, daemon=True)
        thread.start()

    def get(self, key):
        if not self.enabled:
            return None
        if key in self.local_cache:
            value, expiry = self.local_cache[key]
            if expiry is None or expiry > time.time():
                return value
            else:
                del self.local_cache[key]
        if self.redis_client:
            try:
                serialized = self.redis_client.get(key)
                if serialized:
                    value = pickle.loads(serialized)
                    self._set_local(key, value)
                    return value
            except Exception as e:
                print(f"⚠️ Redis get error for {key}: {e}")
        return None

    def set(self, key, value, timeout=None):
        if not self.enabled:
            return
        if timeout is None:
            timeout = self.config.get('REDIS_CACHE_TIMEOUT', 3600)
        self._set_local(key, value, timeout)
        if self.redis_client:
            try:
                serialized = pickle.dumps(value)
                self.redis_client.setex(key, timeout, serialized)
            except Exception as e:
                print(f"⚠️ Redis set error for {key}: {e}")

    def _set_local(self, key, value, timeout=None):
        if len(self.local_cache) >= self.local_cache_max_size:
            oldest_key = next(iter(self.local_cache))
            del self.local_cache[oldest_key]
        expiry = time.time() + timeout if timeout else None
        self.local_cache[key] = (value, expiry)

    def delete(self, key):
        if key in self.local_cache:
            del self.local_cache[key]
        if self.redis_client:
            try:
                self.redis_client.delete(key)
            except Exception as e:
                print(f"⚠️ Redis delete error for {key}: {e}")

    def clear(self, pattern='*'):
        if pattern == '*':
            self.local_cache.clear()
        if self.redis_client:
            try:
                keys = self.redis_client.keys(pattern)
                if keys:
                    self.redis_client.delete(*keys)
            except Exception as e:
                print(f"⚠️ Redis clear error: {e}")

    def exists(self, key):
        if key in self.local_cache:
            value, expiry = self.local_cache[key]
            if expiry is None or expiry > time.time():
                return True
            else:
                del self.local_cache[key]
                return False
        if self.redis_client:
            try:
                return self.redis_client.exists(key) > 0
            except Exception as e:
                print(f"⚠️ Redis exists error: {e}")
        return False

    def increment(self, key, amount=1):
        current = self.get(key)
        if current is None:
            current = 0
        elif not isinstance(current, (int, float)):
            raise ValueError(f"Cannot increment non-numeric key: {key}")
        new_value = current + amount
        self.set(key, new_value)
        return new_value

    def decrement(self, key, amount=1):
        return self.increment(key, -amount)

    def get_stats(self):
        stats = {
            'enabled': self.enabled,
            'redis_connected': False,
            'local_cache_size': len(self.local_cache),
            'local_cache_max_size': self.local_cache_max_size,
            'redis_keys': 0,
            'memory_used': 0
        }
        if self.redis_client and self.enabled:
            try:
                stats['redis_connected'] = self.redis_client.ping() is True
                stats['redis_keys'] = len(self.redis_client.keys('*'))
                try:
                    info = self.redis_client.info('memory')
                    stats['memory_used'] = info.get('used_memory_human', 'N/A')
                except:
                    pass
            except Exception as e:
                stats['redis_connected'] = False
                stats['redis_error'] = str(e)
        return stats


# ==================== Lazy Loader ====================
class LazyLoader:
    """Loads a heavy component on first access."""
    def __init__(self, loader_func, name):
        self._loader = loader_func
        self._name = name
        self._instance = None

    def _load(self):
        if self._instance is None:
            print(f"⏳ Loading {self._name}...")
            t0 = time.time()
            self._instance = self._loader()
            print(f"✅ {self._name} loaded in {time.time()-t0:.2f}s")
        return self._instance

    def __getattr__(self, name):
        return getattr(self._load(), name)

    def __call__(self, *args, **kwargs):
        return self._load()(*args, **kwargs)

    def __bool__(self):
        return self._instance is not None


# ==================== Extensions ====================
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'
mail = Mail()
socketio = SocketIO()
migrate = Migrate()
scheduler = APScheduler()
celery = Celery(__name__)
redis_cache = RedisCache()


def create_app(config_class=Config):
    """Application factory function."""
    print("🚀 Starting ScorePulse AI app...")
    app_start = time.time()

    app_dir = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(app_dir, 'templates')
    static_folder = os.path.join(app_dir, 'static')
    load_dotenv()

    app = Flask(__name__, template_folder=template_folder, static_folder=static_folder)
    if config_class:
        app.config.from_object(config_class)

    # Instance folder
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # --- Initialize extensions (fast) ---
    t = time.time()
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)
    migrate.init_app(app, db)
    socketio.init_app(app, cors_allowed_origins="*")
    scheduler.init_app(app)
    print(f"✅ Extensions initialized in {time.time()-t:.2f}s")

    # --- Redis Cache ---
    t = time.time()
    redis_cache.init_app(app)
    app.cache = redis_cache
    print(f"✅ Redis cache initialized in {time.time()-t:.2f}s")

    # --- Celery ---
    def init_celery(celery_app):
        class FlaskTask(Task):
            def __call__(self, *args, **kwargs):
                with app.app_context():
                    return self.run(*args, **kwargs)

        celery_app.conf.update(
            broker_url=app.config.get('CELERY_BROKER_URL'),
            result_backend=app.config.get('CELERY_RESULT_BACKEND'),
            task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
            result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
            accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
            timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
            enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
            task_always_eager=app.config.get('CELERY_TASK_ALWAYS_EAGER', False),
            task_track_started=True,
            task_time_limit=30 * 60,
            task_soft_time_limit=25 * 60,
            worker_pool=app.config.get('CELERY_WORKER_POOL', 'solo'),
            worker_concurrency=4,
            broker_connection_retry_on_startup=True,
            broker_connection_max_retries=None,
        )
        celery_app.conf.task_routes = {
            'app.tasks.send_*': {'queue': 'email'},
            'app.tasks.process_*': {'queue': 'predictions'},
            'app.tasks.generate_*': {'queue': 'reports'},
            'app.tasks.cleanup_*': {'queue': 'maintenance'},
            'app.tasks.update_*': {'queue': 'maintenance'},
        }
        celery_app.conf.task_queues = {
            'default': {'exchange': 'default', 'routing_key': 'default'},
            'email': {'exchange': 'email', 'routing_key': 'email'},
            'predictions': {'exchange': 'predictions', 'routing_key': 'predictions'},
            'reports': {'exchange': 'reports', 'routing_key': 'reports'},
            'maintenance': {'exchange': 'maintenance', 'routing_key': 'maintenance'},
        }
        celery_app.Task = FlaskTask
        celery_app.set_default()
        celery_app.conf.beat_schedule = {
            'update-leaderboard-every-hour': {
                'task': 'app.tasks.update_leaderboard_task',
                'schedule': 3600.0,
                'args': (),
                'options': {'queue': 'maintenance'}
            },
            'send-daily-reports': {
                'task': 'app.tasks.send_daily_reports_task',
                'schedule': crontab(hour=9, minute=0),
                'options': {'queue': 'email'}
            },
            'cleanup-old-tasks': {
                'task': 'app.tasks.cleanup_old_tasks',
                'schedule': 86400.0,
                'options': {'queue': 'maintenance'}
            },
            'refresh-learning-every-6h': {
                'task': 'app.tasks.periodic_learning_refresh',
                'schedule': crontab(minute=0, hour='*/6'),
                'options': {'queue': 'maintenance'}
            }
        }
        return celery_app

    t = time.time()
    celery_app = init_celery(celery)
    app.celery = celery_app
    print(f"✅ Celery configured in {time.time()-t:.2f}s")

    # --- Lazy loaders for heavy AI components ---
    def load_match_predictor():
        from main import MatchPredictor
        return MatchPredictor()

    def load_value_bet_finder():
        from soccer_match_prediction.scripts.value_bet_finder import ValueBetFinder
        return ValueBetFinder()

    def load_live_tracker():
        from soccer_match_prediction.scripts.live_tracker import LiveMatchTracker
        return LiveMatchTracker()

    def load_performance_analyzer():
        from soccer_match_prediction.scripts.performance_analyzer import PerformanceAnalyzer
        return PerformanceAnalyzer()

    def load_pitch_commander():
        from ..pitch_commander import PitchCommander
        return PitchCommander()

    # Store lazy loaders as app attributes (first access triggers load)
    app.ai_engine = LazyLoader(load_match_predictor, "MatchPredictor")
    app.value_bet_finder = LazyLoader(load_value_bet_finder, "ValueBetFinder")
    app.live_tracker = LazyLoader(load_live_tracker, "LiveMatchTracker")
    app.performance_analyzer = LazyLoader(load_performance_analyzer, "PerformanceAnalyzer")
    app.pitch_commander = LazyLoader(load_pitch_commander, "PitchCommander")

    # --- Monitoring components (lightweight) ---
    try:
        from monitoring.alert_system import AlertSystem
        from monitoring.health_checker import HealthChecker
        from monitoring.metrics_collector import MetricsCollector
        from monitoring.dashboard import Dashboard
        from monitoring.logger import get_logger

        app.health_checker = HealthChecker(app)
        app.alert_manager = AlertSystem()
        app.metrics_collector = MetricsCollector(app)
        app.metrics_collector.start()
        app.training_logger = get_logger("INFO")
        app.dashboard_builder = Dashboard()
        print("✅ Monitoring components initialized")
    except ImportError as e:
        print(f"⚠️ Could not import monitoring components: {e}")
        # Dummies (optional, but kept to avoid AttributeError)
        class DummyHealthChecker:
            def __init__(self, app): pass
            def run_all_checks(self): return {'status': 'warning', 'message': 'Not available'}
        class DummyAlertSystem:
            def __init__(self): pass
            def get_active_alerts(self): return []
        class DummyMetricsCollector:
            def __init__(self, app): pass
            def start(self): pass
        class DummyDashboard:
            def __init__(self): pass
        app.health_checker = DummyHealthChecker(app)
        app.alert_manager = DummyAlertSystem()
        app.metrics_collector = DummyMetricsCollector(app)
        app.training_logger = None
        app.dashboard_builder = DummyDashboard()

    # --- Scheduler ---
    scheduler.start()

    # --- Request timing middleware ---
    @app.before_request
    def before_request():
        g.start_time = time.time()
        request.start_time = time.time()

    @app.after_request
    def after_request(response):
        if hasattr(g, 'start_time'):
            elapsed = time.time() - g.start_time
            if elapsed > 1.0:
                app.logger.warning(f"Slow request: {request.path} took {elapsed:.2f}s")
        # Record metrics (if metrics_collector exists)
        if hasattr(app, 'metrics_collector') and app.metrics_collector:
            try:
                if hasattr(request, 'start_time'):
                    response_time = (time.time() - request.start_time) * 1000
                    app.metrics_collector.record_response_time(
                        request.path,
                        response_time,
                        response.status_code
                    )
                    if response.status_code >= 500:
                        app.metrics_collector.record_error(
                            'http_error',
                            f'{request.path} returned {response.status_code}',
                            'error'
                        )
            except Exception as e:
                app.logger.error(f"Metrics recording failed: {e}")
        return response

    # --- Cache endpoints (kept) ---
    @app.route('/cache/stats')
    def cache_stats():
        stats = app.cache.get_stats()
        return {'status': 'success', 'timestamp': datetime.now().isoformat(), 'stats': stats}

    @app.route('/cache/clear', methods=['POST'])
    def clear_cache():
        pattern = request.json.get('pattern', '*')
        app.cache.clear(pattern)
        return {'status': 'success', 'message': f'Cache cleared for pattern: {pattern}'}

    # --- Celery task endpoints ---
    @app.route('/tasks/stats')
    def task_stats():
        try:
            from celery import current_app
            inspect = current_app.control.inspect()
            stats = {
                'active': inspect.active() or {},
                'reserved': inspect.reserved() or {},
                'scheduled': inspect.scheduled() or {},
                'stats': inspect.stats() or {},
                'registered': inspect.registered() or {},
                'timestamp': datetime.now().isoformat()
            }
            return {'status': 'success', 'stats': stats}
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500

    @app.route('/tasks/<task_id>/status')
    def task_status(task_id):
        try:
            from celery.result import AsyncResult
            task = AsyncResult(task_id, app=app.celery)
            response = {
                'task_id': task_id,
                'status': task.status,
                'ready': task.ready(),
                'successful': task.successful(),
                'failed': task.failed(),
                'result': task.result if task.ready() else None,
                'date_done': task.date_done.isoformat() if task.date_done else None
            }
            if task.failed():
                response['error'] = str(task.result)
                response['traceback'] = task.traceback
            return response
        except Exception as e:
            return {'status': 'error', 'message': str(e)}, 500

    # --- Teardown handlers (kept) ---
    @app.teardown_appcontext
    def cleanup_pitch_commander(exception=None):
        try:
            if 'pitch_commander' in sys.modules:
                pc_module = sys.modules['pitch_commander']
                if hasattr(pc_module, 'chatbot_instance'):
                    chatbot = pc_module.chatbot_instance
                    if hasattr(chatbot, 'mcp_server') and chatbot.mcp_server:
                        if hasattr(chatbot.mcp_server, 'stop_server'):
                            try:
                                chatbot.mcp_server.stop_server()
                                print("✅ [CLEANUP] Stopped MCP server")
                            except Exception as e:
                                print(f"⚠️ [CLEANUP] Error stopping MCP server: {e}")
                if hasattr(pc_module, 'pitch_commander_instances'):
                    for instance in pc_module.pitch_commander_instances:
                        if hasattr(instance, '__del__'):
                            try:
                                instance.__del__()
                            except:
                                pass
                    pc_module.pitch_commander_instances = []
        except Exception as e:
            print(f"⚠️ [CLEANUP] Error cleaning up pitch_commander: {e}")

    @app.teardown_request
    def teardown_request(exception=None):
        pass

    # --- Register routes and models (this imports routes.py) ---
    t = time.time()
    with app.app_context():
        # Error blueprint
        from .errors import errors as errors_blueprint
        app.register_blueprint(errors_blueprint)

        # Routes (this registers all views, but lazy loaders mean heavy code runs only when needed)
        from .routes import register_routes
        register_routes(app)

        # Ensure models are known to SQLAlchemy
        from . import models

        # Import tasks to register with Celery
        try:
            from . import tasks
            print("✅ Celery tasks imported")
        except ImportError as e:
            print(f"⚠️ Could not import tasks module: {e}")

        # Create database tables (should be quick if schema exists)
        try:
            db.create_all()
            print("✅ Database tables verified/created")
        except Exception as e:
            print(f"⚠️ Database initialization error: {e}")

    print(f"✅ Routes and database registered in {time.time()-t:.2f}s")

    # --- Chatbot initialisation (unchanged – may be heavy) ---
    # You can later apply lazy loading to chatbot as well
    chatbot_initialized = False
    try:
        from app.pitch_wrapper import import_pitch_commander_safely
        chatbot_bp, init_chatbot = import_pitch_commander_safely()
        if chatbot_bp:
            app.register_blueprint(chatbot_bp)
            with app.app_context():
                init_chatbot(app)   # <-- this may load models; if heavy, move to lazy loader
            chatbot_initialized = True
            print("✅ Chatbot System initialized successfully")
        else:
            raise ImportError("Chatbot components returned as None")
    except Exception as e:
        print(f"⚠️ Chatbot initialization error: {e}")
        if app.debug:
            traceback.print_exc()

    # Fallback context processor if chatbot failed
    if not chatbot_initialized:
        @app.context_processor
        def inject_chatbot_status():
            return {'chatbot_enabled': False, 'chatbot_available': False, 'chatbot_error': 'Initialization failed'}

    # --- Error handlers ---
    @app.errorhandler(404)
    def not_found_error(error):
        return render_template('errors/404.html', error=error), 404

    @app.errorhandler(500)
    def internal_error(error):
        db.session.rollback()
        return render_template('errors/500.html', error=error), 500

    # --- Context processor ---
    @app.context_processor
    def inject_global_variables():
        return dict(
            google_oauth_enabled=app.config.get('GOOGLE_OAUTH_ENABLED', True),
            current_year=datetime.now().year,
            app_name=app.config.get('APP_NAME', 'ScorePulse AI'),
            current_user=current_user,
            now=lambda: datetime.now(),
            is_development=app.debug,
            version="1.0.0",
            cache_enabled=app.config.get('CACHE_ENABLED', True),
            celery_enabled=not app.config.get('CELERY_TASK_ALWAYS_EAGER', False)
        )

    # --- User loader (must be after app context, but we already have it) ---
    from .routes import load_user
    login_manager.user_loader(load_user)

    # --- Final startup message ---
    elapsed = time.time() - app_start
    print(f"✅ ScorePulse AI App initialized in {elapsed:.2f}s")
    print(f"   Debug mode: {app.debug}")
    print(f"   Chatbot available: {chatbot_initialized}")
    print(f"   Redis Cache: {'Enabled' if app.config.get('CACHE_ENABLED', True) else 'Disabled'}")
    print(f"   Celery: {'Enabled (Async)' if not app.config.get('CELERY_TASK_ALWAYS_EAGER', False) else 'Disabled (Eager mode)'}")

    return app


__all__ = ['create_app', 'db', 'bcrypt', 'login_manager', 'mail', 'socketio', 'redis_cache', 'celery']