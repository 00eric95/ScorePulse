import os

class Config:
    # Security Key
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-key-scorepulse-ai-v2-secure'
    
    # Database Configuration
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL') or \
        'sqlite:///' + os.path.join(BASE_DIR, 'instance', 'site.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Link to ML Engine (One level up)
    ML_ROOT = os.path.abspath(os.path.join(BASE_DIR, '..', 'SCORE_PULSEv2'))