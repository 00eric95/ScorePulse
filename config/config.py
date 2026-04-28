import os
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Config:
    # ============================================
    # 🛡️ SECURITY: All sensitive data loaded from .env
    # ============================================
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-scorepulse-ai-v2-secure-change-in-production')

    # ============================================
    # 🔵 GOOGLE OAUTH CONFIGURATION (from .env)
    # ============================================
    GOOGLE_OAUTH_ENABLED = os.getenv('GOOGLE_OAUTH_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    GOOGLE_OAUTH_SCOPES = 'openid email profile'
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"

    # ============================================
    # DATABASE CONFIGURATION (from .env)
    # ============================================
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/scorepulse.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # ============================================
    # APPLICATION CONFIGURATION (from .env)
    # ============================================
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', '1' if FLASK_ENV == 'development' else '0') == '1'
    APP_NAME = "ScorePulse AI"
    APP_VERSION = "2.0.0"

    # ============================================
    # PATHS & DIRECTORIES
    # ============================================
    BASE_DIR = Path(__file__).parent.parent
    RAW_DATA_DIR = BASE_DIR / "data" / "raw"
    RAW_DATA_PATH = RAW_DATA_DIR / "matches.csv"
    UPCOMING_DATA_PATH = BASE_DIR / "data" / "upcoming.csv"
    PROCESSED_DATA_DIR = BASE_DIR / "data" / "processed"
    PROCESSED_TEST_PATH = PROCESSED_DATA_DIR / "test.csv"
    MODELS_DIR = BASE_DIR / "models"
    SCALER_PATH = MODELS_DIR / "scaler.pkl"
    BEST_PARAMS_PATH = MODELS_DIR / "best_hyperparameters.json"
    ML_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', 'SCORE_PULSEv2'))

    # ============================================
    # TARGET MAPPINGS
    # ============================================
    TARGETS = {
        'WLD': 'FTR',
        'TotalGoals': 'TotalGoals',
        'BTTS': 'BTTS',
        'Over25': 'Over25'
    }
    RESULT_MAP = {'H': 2, 'D': 1, 'A': 0}

    # ============================================
    # FEATURES
    # ============================================
    FEATURES_NUMERIC = [
        'Home_Elo', 'Away_Elo',
        'Home_Avg_Goals', 'Away_Avg_Goals',
        'Home_Avg_Conceded', 'Away_Avg_Conceded',
        'Home_Form', 'Away_Form',
        'Home_Streak', 'Away_Streak',
        'H_Attack', 'A_Attack',
        'H_Defense', 'A_Defense'
    ]

    # ============================================
    # FLASK-LOGIN & SESSION CONFIGURATION
    # ============================================
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    SESSION_COOKIE_SECURE = os.getenv('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
    SESSION_PROTECTION = 'strong'

    # Monitoring Configuration
    MONITORING_ENABLED = True
    HEALTH_CHECK_INTERVAL = 60
    METRICS_RETENTION_DAYS = 30

    # Alert Configuration
    ADMIN_EMAILS = ['admin@scorepulse.ai']
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
    ALERT_WEBHOOK_URL = os.environ.get('ALERT_WEBHOOK_URL')
    ALERT_RULES = []

    # External Services to Monitor
    EXTERNAL_SERVICES = [
        {'name': 'Google OAuth', 'url': 'https://accounts.google.com', 'timeout': 5},
        {'name': 'Football Data API', 'url': 'https://api.football-data.org', 'timeout': 5}
    ]

    # ============================================
    # EMAIL CONFIGURATION (from .env)
    # ============================================
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@scorepulse.ai')
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'

    # ============================================
    # FILE UPLOAD CONFIGURATION
    # ============================================
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'csv', 'json'}

    # ============================================
    # RATE LIMITING (from .env)
    # ============================================
    RATELIMIT_ENABLED = os.getenv('RATELIMIT_ENABLED', 'false').lower() == 'true'
    RATELIMIT_DEFAULT = os.getenv('RATELIMIT_DEFAULT', '200 per day')

    # ============================================
    # LOGGING CONFIGURATION (from .env)
    # ============================================
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.getenv('LOG_FILE', os.path.join(BASE_DIR, 'logs', 'app.log'))

    # Redis Configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
    REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
    CACHE_ENABLED = os.environ.get('CACHE_ENABLED', 'true').lower() == 'true'

    # Cache Configuration (will be refined per environment)
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    CACHE_KEY_PREFIX = 'scorepulse_'
    CACHE_OPTIONS = {
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'retry_on_timeout': True,
        'health_check_interval': 30
    }

    # Celery Configuration (single definition with env fallback)
    CELERY_BROKER_URL = os.getenv(
        'CELERY_BROKER_URL',
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    CELERY_RESULT_BACKEND = os.getenv(
        'CELERY_RESULT_BACKEND',
        f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    )
    CELERY_ACCEPT_CONTENT = ['json', 'pickle']
    CELERY_TASK_SERIALIZER = 'pickle'
    CELERY_RESULT_SERIALIZER = 'pickle'
    CELERY_TIMEZONE = 'Africa/Nairobi'
    CELERY_ENABLE_UTC = True
    CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'false').lower() == 'true'
    CELERY_TASK_CREATE_MISSING_QUEUES = True
    CELERY_TASK_DEFAULT_QUEUE = 'default'
    CELERY_TASK_DEFAULT_EXCHANGE = 'default'
    CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'
    CELERY_TASK_TIME_LIMIT = 30 * 60
    CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60
    CELERY_RESULT_EXPIRES = 24 * 3600
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
    CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000
    CELERY_WORKER_PREFETCH_MULTIPLIER = 4

    # Beat Schedule (Periodic Tasks)
    CELERY_BEAT_SCHEDULE = {
        'update-leaderboard-hourly': {
            'task': 'app.tasks.update_leaderboard_task',
            'schedule': crontab(minute=0) if 'crontab' in globals() else 3600.0,
        },
        'send-daily-reports': {
            'task': 'app.tasks.send_daily_reports_task',
            'schedule': crontab(hour=9, minute=0),
        },
        'cleanup-old-tasks': {
            'task': 'app.tasks.cleanup_old_tasks',
            'schedule': crontab(hour=0, minute=0),
        },
        'update-platform-stats': {
            'task': 'app.tasks.update_platform_stats',
            'schedule': timedelta(minutes=30),
        },
        'refresh-ai-models': {
            'task': 'app.tasks.refresh_ai_models',
            'schedule': crontab(day_of_week=0, hour=2, minute=0),
        },
    }

    # Queue configuration
    CELERY_TASK_QUEUES = {
        'default': {'exchange': 'default', 'routing_key': 'default'},
        'email': {'exchange': 'email', 'routing_key': 'email'},
        'predictions': {'exchange': 'predictions', 'routing_key': 'predictions'},
        'reports': {'exchange': 'reports', 'routing_key': 'reports'},
        'maintenance': {'exchange': 'maintenance', 'routing_key': 'maintenance'},
    }

    CELERY_TASK_ROUTES = {
        'app.tasks.send_*': {'queue': 'email'},
        'app.tasks.process_prediction_*': {'queue': 'predictions'},
        'app.tasks.generate_*_report': {'queue': 'reports'},
        'app.tasks.cleanup_*': {'queue': 'maintenance'},
        'app.tasks.update_*': {'queue': 'maintenance'},
    }

    # ============================================
    # FEATURE FLAGS (from .env)
    # ============================================
    FEATURE_EMAIL_VERIFICATION = os.getenv('FEATURE_EMAIL_VERIFICATION', 'true').lower() == 'true'
    FEATURE_PAYMENTS = os.getenv('FEATURE_PAYMENTS', 'false').lower() == 'true'
    FEATURE_PREDICTIONS = os.getenv('FEATURE_PREDICTIONS', 'true').lower() == 'true'
    SOCKETIO_ENABLED = os.getenv('SOCKETIO_ENABLED', 'true').lower() == 'true'

    # ============================================
    # ADMIN CONFIGURATION (from .env)
    # ============================================
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@scorepulse.ai')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')

    # ============================================
    # TIMEZONE (from .env)
    # ============================================
    TIMEZONE = os.getenv('TIMEZONE', 'UTC')

    # ============================================
    # CHATBOT CONFIGURATION
    # ============================================
    CHATBOT_ENABLED = True
    CHATBOT_MAX_MESSAGES = 100
    CHATBOT_SESSION_TIMEOUT = 3600

    # ============================================
    # ONLINE LEARNING CONFIGURATION
    # ============================================
    ONLINE_LEARNING_ENABLED = True
    LEARNING_DATA_RETENTION_DAYS = 365

    # ============================================
    # MCP SERVER CONFIGURATION (from .env)
    # ============================================
    MCP_SERVER_ENABLED = os.getenv('MCP_SERVER_ENABLED', 'false').lower() == 'true'
    MCP_SERVER_HOST = os.getenv('MCP_SERVER_HOST', 'localhost')
    MCP_SERVER_PORT = int(os.getenv('MCP_SERVER_PORT', '8080'))

    # ============================================
    # PREDICTION API CONFIGURATION (from .env)
    # ============================================
    PREDICTION_API_URL = os.getenv('PREDICTION_API_URL', 'http://localhost:5001/predict')
    PREDICTION_API_KEY = os.getenv('PREDICTION_API_KEY', '')

    # ============================================
    # APPLICATION BASE URL (from .env)
    # ============================================
    BASE_URL = os.getenv('BASE_URL', 'http://YOUR_LOCAL_IP:5000')

    # ============================================
    # CONFIGURATION VALIDATION
    # ============================================
    @property
    def GOOGLE_OAUTH_ACTIVE(self):
        if not self.GOOGLE_OAUTH_ENABLED:
            return False
        if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
            return False
        if 'your-' in self.GOOGLE_CLIENT_ID or 'your-' in self.GOOGLE_CLIENT_SECRET:
            return False
        if self.GOOGLE_CLIENT_ID == '' or self.GOOGLE_CLIENT_SECRET == '':
            return False
        return True

    def validate_config(self):
        print("=" * 60)
        print(f"🚀 {self.APP_NAME} v{self.APP_VERSION}")
        print(f"📁 Environment: {self.FLASK_ENV}")
        print(f"🔍 Debug Mode: {self.DEBUG}")
        print("=" * 60)

        env_path = Path('.env')
        if env_path.exists():
            print(f"📄 .env file: Loaded from {env_path.absolute()}")
        else:
            print(f"⚠️  .env file: Not found! Create one in project root")

        print(f"🗄️  Database: {self.SQLALCHEMY_DATABASE_URI}")
        if os.path.exists(self.ML_ROOT):
            print(f"🤖 ML Engine: Found at {self.ML_ROOT}")
        else:
            print(f"⚠️  ML Engine: Not found at {self.ML_ROOT}")

        if self.GOOGLE_OAUTH_ENABLED:
            if self.GOOGLE_OAUTH_ACTIVE:
                print(f"✅ Google OAuth: ACTIVE")
                print(f"   Client ID: {self.GOOGLE_CLIENT_ID[:20]}...")
                print(f"   🔗 Add these redirect URIs to Google Cloud Console:")
                print(f"   {self.BASE_URL}/auth/google/callback")
            else:
                print(f"⚠️  Google OAuth: ENABLED but NOT CONFIGURED")
        else:
            print(f"📧 Google OAuth: DISABLED")

        if self.MAIL_USERNAME and self.MAIL_PASSWORD:
            print(f"📧 Email: Configured ({self.MAIL_USERNAME})")
        else:
            print(f"📧 Email: Not configured (add MAIL_USERNAME & MAIL_PASSWORD to .env)")

        if self.FLASK_ENV == 'production':
            if self.SECRET_KEY.startswith('dev-key-'):
                print(f"⚠️  SECURITY WARNING: Using default secret key in production!")
            if not self.SESSION_COOKIE_SECURE:
                print(f"⚠️  SECURITY WARNING: SESSION_COOKIE_SECURE should be True in production!")
            if not self.ADMIN_PASSWORD or self.ADMIN_PASSWORD == 'ChangeMe123!':
                print(f"⚠️  SECURITY WARNING: Default admin password detected!")

        missing_configs = []
        if self.FLASK_ENV == 'production':
            if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
                missing_configs.append('GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET')
            if not self.MAIL_PASSWORD:
                missing_configs.append('MAIL_PASSWORD')
            if not self.ADMIN_PASSWORD:
                missing_configs.append('ADMIN_PASSWORD')

        if missing_configs:
            print(f"⚠️  Missing in .env: {', '.join(missing_configs)}")

        print("=" * 60)
        return True

    @staticmethod
    def setup_directories():
        base_dir = Path(__file__).parent
        directories = [
            base_dir / 'instance',
            base_dir / 'logs',
            base_dir / 'static' / 'uploads',
            base_dir / 'static' / 'plots',
            base_dir / 'data' / 'raw',
            base_dir / 'data' / 'processed',
            base_dir / 'models',
        ]
        for directory in directories:
            directory.mkdir(parents=True, exist_ok=True)
            print(f"📁 Created/verified: {directory}")

    def ensure_dirs(self):
        self.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration - loads from .env"""
    DEBUG = True
    TESTING = False
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
    SESSION_COOKIE_SECURE = False

    # DATA AGENT CONFIGURATION (fixed: use Config. prefix)
    DATA_SOURCES = {
        'primary': Config.RAW_DATA_DIR,
        'fallback': Config.BASE_DIR / "data" / "backup",
    }
    COLUMN_MAPPING_FILE = Config.BASE_DIR / "config" / "column_mapping.json"
    ENABLE_ADVANCED_FEATURES = os.getenv('ENABLE_ADVANCED_FEATURES', 'true').lower() == 'true'
    ROLLING_WINDOWS = [3, 5, 10]
    TEAM_STATS_CACHE_TTL = int(os.getenv('TEAM_STATS_CACHE_TTL', 3600))

    # ANALYST AGENT CONFIGURATION (fixed: use Config.BASE_DIR)
    REPORTS_DIR = Config.BASE_DIR / "reports" / "descriptive"
    VISUALIZATIONS_DIR = Config.BASE_DIR / "static" / "descriptive_visualizations"
    DEFAULT_REPORT_FORMAT = os.getenv('DEFAULT_REPORT_FORMAT', 'html')
    MAX_INSIGHTS_PER_REQUEST = 10
    MAX_TEAMS_IN_REPORT = 20
    ENABLE_TREND_ANALYSIS = os.getenv('ENABLE_TREND_ANALYSIS', 'true').lower() == 'true'
    ENABLE_PATTERN_ANALYSIS = os.getenv('ENABLE_PATTERN_ANALYSIS', 'true').lower() == 'true'

    # CRITIC AGENT (EVALUATION) CONFIGURATION
    EVALUATION_RESULTS_DIR = Config.BASE_DIR / "data" / "evaluations"
    EVALUATION_RESULTS_RETENTION_DAYS = 30
    CLASSIFICATION_BENCHMARKS = {
        'excellent': {'accuracy': 0.85, 'f1': 0.80},
        'good': {'accuracy': 0.75, 'f1': 0.70},
        'fair': {'accuracy': 0.65, 'f1': 0.60},
        'poor': {'accuracy': 0.55, 'f1': 0.50}
    }
    REGRESSION_BENCHMARKS = {
        'excellent': {'r2': 0.85, 'mae': 0.25},
        'good': {'r2': 0.70, 'mae': 0.40},
        'fair': {'r2': 0.55, 'mae': 0.60},
        'poor': {'r2': 0.40, 'mae': 0.80}
    }
    ASYNC_EVALUATION_ENABLED = os.getenv('ASYNC_EVALUATION_ENABLED', 'false').lower() == 'true'

    # BANKROLL AGENT CONFIGURATION
    DEFAULT_BANKROLL = float(os.getenv('DEFAULT_BANKROLL', '1000.0'))
    DEFAULT_RISK_APPETITE = os.getenv('DEFAULT_RISK_APPETITE', 'half')
    DEFAULT_BASE_STAKE = float(os.getenv('DEFAULT_BASE_STAKE', '10.0'))
    MAX_KELLY_FRACTION = float(os.getenv('MAX_KELLY_FRACTION', '0.25'))
    ODDS_PROVIDER = os.getenv('ODDS_PROVIDER', 'mock')
    ODDS_API_KEY = os.getenv('ODDS_API_KEY', '')
    ODDS_API_URL = os.getenv('ODDS_API_URL', 'https://api.the-odds-api.com/v4')
    BANKROLL_HISTORY_FILE = Config.BASE_DIR / "data" / "bankroll_history.json"

    # ADMIN AGENT CONFIGURATION
    MCP_AUTH_TOKEN = os.getenv('MCP_AUTH_TOKEN', '')
    MCP_ALLOWED_ORIGINS = os.getenv('MCP_ALLOWED_ORIGINS', '*').split(',')
    NOTES_FILE = Config.BASE_DIR / "data" / "admin_notes.json"
    CSV_TRACKER_FILE = Config.BASE_DIR / "data" / "csv_tracker.json"
    SYSTEM_LOG_FILE = Config.BASE_DIR / "logs" / "system_monitor.log"
    HEALTH_CHECK_CRON = "*/5 * * * *"

    # ORCHESTRATOR (PITCH COMMANDER) CONFIGURATION
    PIPELINE_TIMEOUT_SECONDS = int(os.getenv('PIPELINE_TIMEOUT_SECONDS', '60'))
    PIPELINE_ASYNC_MODE = os.getenv('PIPELINE_ASYNC_MODE', 'sync')
    ENABLE_DATA_STEP = True
    ENABLE_PREDICTION_STEP = True
    ENABLE_ANALYSIS_STEP = True
    ENABLE_BETTING_STEP = True
    ENABLE_CRITIC_STEP = True
    EVENT_BUS_ENABLED = os.getenv('EVENT_BUS_ENABLED', 'false').lower() == 'true'

    # Cache backend: use simple for development unless Redis forced
    CACHE_TYPE = 'simple' if not os.getenv('FORCE_REDIS') else 'redis'


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    GOOGLE_OAUTH_ENABLED = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None


def get_redis_url():
    redis_host = os.environ.get('REDIS_HOST', 'localhost')
    redis_port = int(os.environ.get('REDIS_PORT', 6379))
    redis_db = int(os.environ.get('REDIS_DB', 0))
    redis_password = os.environ.get('REDIS_PASSWORD', None)
    if redis_password:
        return f"redis://:{redis_password}@{redis_host}:{redis_port}/{redis_db}"
    else:
        return f"redis://{redis_host}:{redis_port}/{redis_db}"


class ProductionConfig(Config):
    """Production configuration - STRICTLY from .env"""
    DEBUG = False
    TESTING = False
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    RATELIMIT_ENABLED = True
    LOG_LEVEL = 'WARNING'
    CELERY_TASK_ALWAYS_EAGER = False

    REDIS_URL = get_redis_url()
    if REDIS_URL:
        CACHE_TYPE = 'redis'
        CACHE_REDIS_URL = REDIS_URL
        CACHE_OPTIONS = {'ssl_cert_reqs': None}
    else:
        CACHE_TYPE = 'redis'  # fallback to default Redis settings

    def __init__(self):
        super().__init__()
        self._validate_production_config()

    def _validate_production_config(self):
        required_vars = [
            'SECRET_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
            'MAIL_PASSWORD',
            'ADMIN_PASSWORD',
        ]
        missing = [v for v in required_vars if not os.getenv(v)]
        if missing:
            raise ValueError(
                f"Missing required environment variables in .env for production: {', '.join(missing)}\n"
                f"Create a .env file with these variables."
            )


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])


# Initialize directories when this module is imported
Config.setup_directories()