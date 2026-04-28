import os
import sys
import io
from datetime import timedelta

# --- UNICODE ENCODING FIX FOR WINDOWS ---
# Enable UTF-8 output on Windows to support emojis
if sys.platform == 'win32':
    # Force UTF-8 encoding for stdout and stderr on Windows
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

class Config:
    # Security Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-scorepulse-ai-v2-secure'
    
    # Database Configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, '..', 'instance', 'scorepulse.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    DEBUG = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    # Link to ML Engine (One level up)
    ML_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', 'SCORE_PULSEv2'))
    
    BASE_URL = 'http://127.0.0.1:5000'
    
    # Flask-Login Configuration
    REMEMBER_COOKIE_DURATION = timedelta(days=30)
    REMEMBER_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_PROTECTION = 'basic'    # Options: 'basic', 'strong', or None
    
    # Google OAuth 2.0 Configuration (Optional - Can be disabled)
    # Set GOOGLE_OAUTH_ENABLED=true in .env to enable
    GOOGLE_OAUTH_ENABLED = os.environ.get('GOOGLE_OAUTH_ENABLED', 'true').lower() in ('true', '1', 'yes')
    
    # Google Client ID and Secret (Required only if GOOGLE_OAUTH_ENABLED=true)
    GOOGLE_CLIENT_ID = os.environ.get('GOOGLE_CLIENT_ID', '')
    GOOGLE_CLIENT_SECRET = os.environ.get('GOOGLE_CLIENT_SECRET', '')
    
    # OAuth Configuration
    GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
    GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
    GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/auth"
    
    # OAuth Scopes (what we want to access from Google)
    GOOGLE_OAUTH_SCOPES = [
        'openid',
        'https://www.googleapis.com/auth/userinfo.email',
        'https://www.googleapis.com/auth/userinfo.profile'
    ]
    
    # Session Configuration
    SESSION_COOKIE_SECURE = False  # Set to True in production with HTTPS
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'  # Options: 'Lax', 'Strict', 'None'
    
    # Security Headers (for production)
    SECURITY_HEADERS = {
        'Strict-Transport-Security': 'max-age=31536000; includeSubDomains',
        'X-Content-Type-Options': 'nosniff',
        'X-Frame-Options': 'SAMEORIGIN',
        'X-XSS-Protection': '1; mode=block'
    }
    
    # File Upload Configuration
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'static', 'uploads')
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
    
    # Email Configuration (Optional - for password reset, etc.)
    MAIL_SERVER = os.environ.get('MAIL_SERVER', 'smtp.gmail.com')
    MAIL_PORT = int(os.environ.get('MAIL_PORT', 587))
    MAIL_USE_TLS = os.environ.get('MAIL_USE_TLS', 'true').lower() == 'true'
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME', 'wemba12321@gmail.com')
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD')
    MAIL_DEFAULT_SENDER = os.environ.get('MAIL_DEFAULT_SENDER', 'wemba12321@gmail.com')
    MAIL_MAX_EMAILS = None
    MAIL_ASCII_ATTACHMENTS = False
    MAIL_USE_SSL = False
    
    # Prediction/AI Configuration
    PREDICTION_API_URL = os.environ.get('PREDICTION_API_URL', 'http://localhost:5001/predict')
    PREDICTION_API_KEY = os.environ.get('PREDICTION_API_KEY', '')
    
    # Rate Limiting
    RATELIMIT_ENABLED = os.environ.get('RATELIMIT_ENABLED', 'false').lower() == 'true'
    RATELIMIT_DEFAULT = os.environ.get('RATELIMIT_DEFAULT', '200 per day')
    RATELIMIT_STRATEGY = 'fixed-window'
    
    # Logging Configuration
    LOG_LEVEL = os.environ.get('LOG_LEVEL', 'INFO').upper()
    LOG_FILE = os.environ.get('LOG_FILE', os.path.join(BASE_DIR, '..', 'logs', 'app.log'))
    
    # Feature Flags
    FEATURE_GOOGLE_OAUTH = GOOGLE_OAUTH_ENABLED and GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET
    FEATURE_EMAIL_VERIFICATION = os.environ.get('FEATURE_EMAIL_VERIFICATION', 'false').lower() == 'true'
    FEATURE_PAYMENTS = os.environ.get('FEATURE_PAYMENTS', 'false').lower() == 'true'
    FEATURE_PREDICTIONS = os.environ.get('FEATURE_PREDICTIONS', 'true').lower() == 'true'
    
    # Application Settings
    APP_NAME = "ScorePulse AI"
    APP_VERSION = "2.0.0"
    APP_ENV = os.environ.get('FLASK_ENV', 'development')
    DEBUG = APP_ENV == 'development'
    
    # Admin Configuration
    ADMIN_USERNAME = os.environ.get('ADMIN_USERNAME', 'admin')
    ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', 'wemba12321@gmail.com')
    
    # Static files configuration
    STATIC_FOLDER = 'static'
    TEMPLATES_FOLDER = 'templates'
    
    # Timezone
    TIMEZONE = os.environ.get('TIMEZONE', 'UTC')
    
    #Chatbot-specific configurations
    CHATBOT_ENABLED = True
    CHATBOT_MAX_MESSAGES = 100
    CHATBOT_SESSION_TIMEOUT = 3600  # 1 hour
    CHATBOT_DEFAULT_MODE = 'assistant'
    CHATBOT_ALLOW_COMMANDS = True
    CHATBOT_LOG_LEVEL = 'INFO'
    
    # MCP Server Configuration
    MCP_SERVER_ENABLED = False
    MCP_SERVER_HOST = 'localhost'
    MCP_SERVER_PORT = 8080
    
    # Online Learning Configuration
    ONLINE_LEARNING_ENABLED = True
    LEARNING_DATA_RETENTION_DAYS = 365
    LEARNING_UPDATE_INTERVAL = 3600  # 1 hour
    
       # Redis Configuration
    REDIS_HOST = os.environ.get('REDIS_HOST', 'localhost')
    REDIS_PORT = int(os.environ.get('REDIS_PORT', 6379))
    REDIS_DB = int(os.environ.get('REDIS_DB', 0))
    REDIS_PASSWORD = os.environ.get('REDIS_PASSWORD', None)
    REDIS_SSL = os.environ.get('REDIS_SSL', 'false').lower() == 'true'
    
    CELERY_BROKER_URL = os.environ.get('CELERY_BROKER_URL', f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
    CELERY_RESULT_BACKEND = os.environ.get('CELERY_RESULT_BACKEND', f"redis://{REDIS_HOST}:{REDIS_PORT}/0")
    CELERY_TASK_ALWAYS_EAGER = os.environ.get('CELERY_TASK_ALWAYS_EAGER', 'false').lower() == 'true'
    CELERY_TASK_SERIALIZER = 'json'
    CELERY_RESULT_SERIALIZER = 'json'
    CELERY_ACCEPT_CONTENT = ['json']
    CELERY_TIMEZONE = 'Africa/Nairobi'
    CELERY_ENABLE_UTC = True
    CELERY_WORKER_POOL = 'solo'
    
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
    
    # Check if Google OAuth is properly configured
    @property
    def is_google_oauth_configured(self):
        """Check if Google OAuth is properly configured"""
        if not self.GOOGLE_OAUTH_ENABLED:
            return False
        
        # Check if required credentials are provided
        if not self.GOOGLE_CLIENT_ID or not self.GOOGLE_CLIENT_SECRET:
            print("⚠️  WARNING: Google OAuth is enabled but credentials are missing.")
            print("   Set GOOGLE_CLIENT_ID and GOOGLE_CLIENT_SECRET environment variables.")
            return False
        
        return True
    
    def validate_config(self):
        """Validate configuration and print warnings"""
        print(f"🚀 Starting {self.APP_NAME} v{self.APP_VERSION}")
        print(f"📁 Environment: {self.APP_ENV}")
        print(f"📁 Base Directory: {self.BASE_DIR}")
        print(f"🔗 Database: {self.SQLALCHEMY_DATABASE_URI}")
        print(f"🤖 ML Root: {self.ML_ROOT}")
        print(f"📁 Working Directory: {os.getcwd()}")
        
        # Check Google OAuth
        if self.GOOGLE_OAUTH_ENABLED:
            if self.is_google_oauth_configured:
                print("✅ Google OAuth: Enabled and configured")
            else:
                print("⚠️  Google OAuth: Enabled but not properly configured")
                print("   Google Sign-In buttons will not appear")
        else:
            print("📧 Google OAuth: Disabled (Email/Password only)")
        
        # Check secret key in production
        if self.APP_ENV == 'production' and self.SECRET_KEY.startswith('dev-key-'):
            print("⚠️  WARNING: Using default secret key in production!")
            print("   Set a strong SECRET_KEY environment variable")
        
        # Check email configuration
        if self.MAIL_USERNAME and self.MAIL_PASSWORD:
            print("✅ Email: Configured")
        else:
            print("📧 Email: Not configured (password reset will not work)")
        
        print("-" * 50)
        
        return True


class DevelopmentConfig(Config):
    """Development configuration"""
    DEBUG = True
    TESTING = False
    ENV = 'development'


class TestingConfig(Config):
    """Testing configuration"""
    DEBUG = False
    TESTING = True
    ENV = 'testing'
    SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
    
    # Disable Google OAuth in testing unless explicitly enabled
    GOOGLE_OAUTH_ENABLED = True


class ProductionConfig(Config):
    """Production configuration"""
    DEBUG = False
    TESTING = False
    ENV = 'production'
    
    # Production security settings
    SESSION_COOKIE_SECURE = True
    REMEMBER_COOKIE_SECURE = True


# Configuration dictionary
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    """Get the configuration based on environment"""
    env = os.environ.get('FLASK_ENV', 'development').lower()
    return config.get(env, config['default'])


# Helper function to setup directories
def setup_directories():
    """Create necessary directories for the application"""
    base_dir = os.path.abspath(os.path.dirname(__file__))
    
    directories = [
        os.path.join(base_dir, '..', 'instance'),
        os.path.join(base_dir, '..', 'logs'),
        os.path.join(base_dir, 'static', 'uploads'),
    ]
    
    for directory in directories:
        os.makedirs(directory, exist_ok=True)
        print(f"📁 Created/verified directory: {directory}")


# Initialize directories when this module is imported
setup_directories()