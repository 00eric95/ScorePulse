import os
from pathlib import Path
from datetime import timedelta
from celery.schedules import crontab
from dotenv import load_dotenv  # Added import for .env file loading

# Load environment variables from .env file
# This loads from .env file in the project root
load_dotenv()


class Config:
    # ============================================
    # 🛡️ SECURITY: All sensitive data loaded from .env
    # ============================================
    
    # SECURITY WARNING: Always use .env for production!
    # Get from .env or use default (for development only)
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-key-scorepulse-ai-v2-secure-change-in-production')
    
    # ============================================
    # 🔵 GOOGLE OAUTH CONFIGURATION (from .env)
    # ============================================
    
    # Enable Google OAuth (set to True to enable)
    GOOGLE_OAUTH_ENABLED = os.getenv('GOOGLE_OAUTH_ENABLED', 'true').lower() in ('true', '1', 'yes', 'on')
    
    # Google OAuth Credentials - MUST be in .env file
    GOOGLE_CLIENT_ID = os.getenv('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.getenv('GOOGLE_CLIENT_SECRET', '')
    
    # OAuth Scopes - what user data we request from Google
    GOOGLE_OAUTH_SCOPES = 'openid email profile'
    
    # OAuth Configuration
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    
    # ============================================
    # DATABASE CONFIGURATION (from .env)
    # ============================================
    
    SQLALCHEMY_DATABASE_URI = os.getenv('DATABASE_URL', 'sqlite:///instance/scorepulse.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # ============================================
    # APPLICATION CONFIGURATION (from .env)
    # ============================================
    
    # Flask Environment
    FLASK_ENV = os.getenv('FLASK_ENV', 'development')
    DEBUG = os.getenv('FLASK_DEBUG', '1' if FLASK_ENV == 'development' else '0') == '1'
    
    
    # Application Details
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
    
    # Files
    SCALER_PATH = MODELS_DIR / "scaler.pkl"
    BEST_PARAMS_PATH = MODELS_DIR / "best_hyperparameters.json"
    
    # Link to ML Engine
    ML_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', 'SCORE_PULSEv2'))
    
    # ============================================
    # TARGET MAPPINGS
    # ============================================
    
    TARGETS = {
        'WLD': 'FTR',         # Win/Loss/Draw
        'TotalGoals': 'TotalGoals',  # Regression Target
        'BTTS': 'BTTS',       # Both Teams To Score
        'Over25': 'Over25'    # Over 2.5 Goals
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
    HEALTH_CHECK_INTERVAL = 60  # seconds
    METRICS_RETENTION_DAYS = 30

    # Alert Configuration
    ADMIN_EMAILS = ['admin@scorepulse.ai']
    SLACK_WEBHOOK_URL = os.environ.get('SLACK_WEBHOOK_URL')
    ALERT_WEBHOOK_URL = os.environ.get('ALERT_WEBHOOK_URL')

    # Alert Rules (optional overrides)
    ALERT_RULES = [
        # Custom rules can be added here
    ]

    # External Services to Monitor
    EXTERNAL_SERVICES = [
        {
            'name': 'Google OAuth',
            'url': 'https://accounts.google.com',
            'timeout': 5
        },
        {
            'name': 'Football Data API',
            'url': 'https://api.football-data.org',
            'timeout': 5
        }
    ]
    
    # ============================================
    # EMAIL CONFIGURATION (from .env)
    # ============================================
    
    MAIL_SERVER = os.getenv('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.getenv('MAIL_PORT', '587'))
    MAIL_USE_TLS = os.getenv('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.getenv('MAIL_USERNAME', '')  # Must be in .env
    MAIL_PASSWORD = os.getenv('MAIL_PASSWORD', '')  # Must be in .env
    MAIL_DEFAULT_SENDER = os.getenv('MAIL_DEFAULT_SENDER', 'noreply@scorepulse.ai')
    MAIL_USE_SSL = os.getenv('MAIL_USE_SSL', 'false').lower() == 'true'
    
    # ============================================
    # FILE UPLOAD CONFIGURATION
    # ============================================
    
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
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
    
    # Cache Configuration
    CACHE_TYPE = 'redis'
    CACHE_REDIS_HOST = REDIS_HOST
    CACHE_REDIS_PORT = REDIS_PORT
    CACHE_REDIS_DB = REDIS_DB
    CACHE_REDIS_PASSWORD = REDIS_PASSWORD
    CACHE_REDIS_SSL = REDIS_SSL
    CACHE_DEFAULT_TIMEOUT = int(os.environ.get('CACHE_DEFAULT_TIMEOUT', 300))
    CACHE_KEY_PREFIX = 'scorepulse_'
    CACHE_OPTIONS = {
        'socket_connect_timeout': 5,
        'socket_timeout': 5,
        'retry_on_timeout': True,
        'health_check_interval': 30
    }
    
    # Optional: Use different cache backends based on environment
    if os.environ.get('FLASK_ENV') == 'development':
        # Use simple cache for development (no Redis required)
        CACHE_TYPE = 'simple'
    else:
        CACHE_TYPE = 'redis'
    
    # ============================================
    # FEATURE FLAGS (from .env)
    # ============================================
    
    @property
    def GOOGLE_OAUTH_ACTIVE(self):
        """Check if Google OAuth is properly configured and active"""
        if not self.GOOGLE_OAUTH_ENABLED:
            return False
        # Check if credentials are provided
        if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
            return False
        # Check if credentials look valid
        if 'your-' in self.GOOGLE_CLIENT_ID or 'your-' in self.GOOGLE_CLIENT_SECRET:
            return False
        if self.GOOGLE_CLIENT_ID == '' or self.GOOGLE_CLIENT_SECRET == '':
            return False
        return True
    
    # Other feature flags from .env
    FEATURE_EMAIL_VERIFICATION = os.getenv('FEATURE_EMAIL_VERIFICATION', 'true').lower() == 'true'
    FEATURE_PAYMENTS = os.getenv('FEATURE_PAYMENTS', 'false').lower() == 'true'
    FEATURE_PREDICTIONS = os.getenv('FEATURE_PREDICTIONS', 'true').lower() == 'true'
    
    SOCKETIO_ENABLED = os.getenv('SOCKETIO_ENABLED', 'true').lower() == 'true'
    CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', f"redis://{REDIS_HOST}:{REDIS_PORT}/1")
    CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', f"redis://{REDIS_HOST}:{REDIS_PORT}/2")
    CELERY_TASK_ALWAYS_EAGER = os.getenv('CELERY_TASK_ALWAYS_EAGER', 'false').lower() == 'true'
    # ============================================
    # ADMIN CONFIGURATION (from .env)
    # ============================================
    
    ADMIN_USERNAME = os.getenv('ADMIN_USERNAME', 'admin')
    ADMIN_EMAIL = os.getenv('ADMIN_EMAIL', 'admin@scorepulse.ai')
    ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', '')  # Must be in .env for production
    
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
    
    # Celery Configuration
    CELERY_BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    CELERY_RESULT_BACKEND = f"redis://{REDIS_HOST}:{REDIS_PORT}/{REDIS_DB}"
    CELERY_ACCEPT_CONTENT = ['json', 'pickle']
    CELERY_TASK_SERIALIZER = 'pickle'
    CELERY_RESULT_SERIALIZER = 'pickle'
    CELERY_TIMEZONE = 'Africa/Nairobi'  # Adjust to your timezone
    CELERY_ENABLE_UTC = True
    
    # Celery Task Settings
    CELERY_TASK_ALWAYS_EAGER = False  # Set to True for testing (sync mode)
    CELERY_TASK_CREATE_MISSING_QUEUES = True
    CELERY_TASK_DEFAULT_QUEUE = 'default'
    CELERY_TASK_DEFAULT_EXCHANGE = 'default'
    CELERY_TASK_DEFAULT_ROUTING_KEY = 'default'
    
    # Task timeouts
    CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes
    CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # 25 minutes
    
    # Result expiration
    CELERY_RESULT_EXPIRES = 24 * 3600  # 24 hours
    
    # Beat Schedule (Periodic Tasks)
    CELERY_BEAT_SCHEDULE = {
        # Update leaderboard every hour
        'update-leaderboard-hourly': {
            'task': 'app.tasks.update_leaderboard_task',
            'schedule': crontab(minute=0) if 'crontab' in globals() else 3600.0,
        },
        # Send daily reports at 9 AM
        'send-daily-reports': {
            'task': 'app.tasks.send_daily_reports_task',
            'schedule': crontab(hour=9, minute=0),
        },
        # Clean up old tasks daily at midnight
        'cleanup-old-tasks': {
            'task': 'app.tasks.cleanup_old_tasks',
            'schedule': crontab(hour=0, minute=0),
        },
        # Update platform stats every 30 minutes
        'update-platform-stats': {
            'task': 'app.tasks.update_platform_stats',
            'schedule': timedelta(minutes=30),
        },
        # Refresh AI models weekly on Sunday at 2 AM
        'refresh-ai-models': {
            'task': 'app.tasks.refresh_ai_models',
            'schedule': crontab(day_of_week=0, hour=2, minute=0),
        },
    }
    
    # Worker settings
    CELERY_WORKER_MAX_TASKS_PER_CHILD = 1000
    CELERY_WORKER_MAX_MEMORY_PER_CHILD = 200000  # 200MB
    CELERY_WORKER_PREFETCH_MULTIPLIER = 4
    
    # Queue configuration
    CELERY_TASK_QUEUES = {
        'default': {
            'exchange': 'default',
            'routing_key': 'default',
        },
        'email': {
            'exchange': 'email',
            'routing_key': 'email',
        },
        'predictions': {
            'exchange': 'predictions',
            'routing_key': 'predictions',
        },
        'reports': {
            'exchange': 'reports',
            'routing_key': 'reports',
        },
        'maintenance': {
            'exchange': 'maintenance',
            'routing_key': 'maintenance',
        },
    }
    
    # Task routes
    CELERY_TASK_ROUTES = {
        'app.tasks.send_*': {'queue': 'email'},
        'app.tasks.process_prediction_*': {'queue': 'predictions'},
        'app.tasks.generate_*_report': {'queue': 'reports'},
        'app.tasks.cleanup_*': {'queue': 'maintenance'},
        'app.tasks.update_*': {'queue': 'maintenance'},
    }

    
    # ============================================
    # CONFIGURATION VALIDATION
    # ============================================
    
    def validate_config(self):
        """Validate configuration and print status"""
        print("=" * 60)
        print(f"🚀 {self.APP_NAME} v{self.APP_VERSION}")
        print(f"📁 Environment: {self.FLASK_ENV}")
        print(f"🔍 Debug Mode: {self.DEBUG}")
        print("=" * 60)
        
        # Check if .env file is loaded
        env_path = Path('.env')
        if env_path.exists():
            print(f"📄 .env file: Loaded from {env_path.absolute()}")
        else:
            print(f"⚠️  .env file: Not found! Create one in project root")
            print(f"   Template: https://github.com/yourrepo/.env.example")
        
        # Database status
        print(f"🗄️  Database: {self.SQLALCHEMY_DATABASE_URI}")
        
        # ML Engine status
        if os.path.exists(self.ML_ROOT):
            print(f"🤖 ML Engine: Found at {self.ML_ROOT}")
        else:
            print(f"⚠️  ML Engine: Not found at {self.ML_ROOT}")
        
        # Google OAuth status
        if self.GOOGLE_OAUTH_ENABLED:
            if self.GOOGLE_OAUTH_ACTIVE:
                print(f"✅ Google OAuth: ACTIVE")
                print(f"   Client ID: {self.GOOGLE_CLIENT_ID[:20]}...")
                print(f"   🔗 Add these redirect URIs to Google Cloud Console:")
                print(f"   {self.BASE_URL}/auth/google/callback")
            else:
                print(f"⚠️  Google OAuth: ENABLED but NOT CONFIGURED")
                print(f"   Add GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET to .env file")
        else:
            print(f"📧 Google OAuth: DISABLED")
        
        # Email configuration
        if self.MAIL_USERNAME and self.MAIL_PASSWORD:
            print(f"📧 Email: Configured ({self.MAIL_USERNAME})")
        else:
            print(f"📧 Email: Not configured (add MAIL_USERNAME & MAIL_PASSWORD to .env)")
        
        # Security warnings
        if self.FLASK_ENV == 'production':
            if self.SECRET_KEY.startswith('dev-key-'):
                print(f"⚠️  SECURITY WARNING: Using default secret key in production!")
                print(f"   Add a strong SECRET_KEY to .env file")
            if not self.SESSION_COOKIE_SECURE:
                print(f"⚠️  SECURITY WARNING: SESSION_COOKIE_SECURE should be True in production!")
            if not self.ADMIN_PASSWORD or self.ADMIN_PASSWORD == 'ChangeMe123!':
                print(f"⚠️  SECURITY WARNING: Default admin password detected!")
                print(f"   Change ADMIN_PASSWORD in .env file")
        
        # Missing sensitive configuration
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
    
    # ============================================
    # DIRECTORIES SETUP
    # ============================================
    
    @staticmethod
    def setup_directories():
        """Create necessary directories for the application"""
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
        """Ensure all required directories exist"""
        self.RAW_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.PROCESSED_DATA_DIR.mkdir(parents=True, exist_ok=True)
        self.MODELS_DIR.mkdir(parents=True, exist_ok=True)


class DevelopmentConfig(Config):
    """Development configuration - loads from .env"""
    DEBUG = True
    TESTING = False
    
    CELERY_TASK_ALWAYS_EAGER = True  # Run tasks synchronously for development
    CELERY_TASK_EAGER_PROPAGATES = True
    
    # Development-specific overrides
    SESSION_COOKIE_SECURE = False
    

class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable external services in testing
    GOOGLE_OAUTH_ENABLED = False
    MAIL_USERNAME = None
    MAIL_PASSWORD = None
    
# In config/config.py, add this function before ProductionConfig
def get_redis_url():
    """Generate Redis URL from configuration"""
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
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True
    SESSION_COOKIE_SAMESITE = 'Lax'
    
    # Production features
    RATELIMIT_ENABLED = True
    LOG_LEVEL = 'WARNING'
    
    CELERY_TASK_ALWAYS_EAGER = False
    
    # Redis from environment variable
    REDIS_URL = get_redis_url()
    
    if REDIS_URL:
        CACHE_TYPE = 'redis'
        CACHE_REDIS_URL = REDIS_URL
        CACHE_OPTIONS = {
            'ssl_cert_reqs': None  # For self-signed certificates
        }
    else:
        # Fallback to local Redis
        REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
        REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
        REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD')
        REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
        
        
    
    # Ensure required production variables are set
    def __init__(self):
        super().__init__()
        self._validate_production_config()
    
    def _validate_production_config(self):
        """Validate that all required production configs are in .env"""
        required_vars = [
            'SECRET_KEY',
            'GOOGLE_CLIENT_ID',
            'GOOGLE_CLIENT_SECRET',
            'MAIL_PASSWORD',
            'ADMIN_PASSWORD',
        ]
        
        missing = []
        for var in required_vars:
            if not os.getenv(var):
                missing.append(var)
        
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
    """Get the configuration based on environment"""
    env = os.getenv('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])


# Initialize directories when this module is imported
Config.setup_directories()