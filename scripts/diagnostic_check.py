import os
import sys
import time

def check_database(app):
    print("\n[Database Check]")
    try:
        from flask_sqlalchemy import SQLAlchemy
        db = SQLAlchemy(app)
        with app.app_context():
            db.session.execute('SELECT 1')
        print("✓ Database connection successful.")
    except Exception as e:
        print(f"✗ Database connection failed: {e}")

def check_redis(app):
    print("\n[Redis Check]")
    try:
        import redis
        redis_url = app.config.get('REDIS_URL') or app.config.get('CACHE_REDIS_URL')
        if not redis_url:
            print("⚠️  No REDIS_URL or CACHE_REDIS_URL found in config.")
            return
        r = redis.from_url(redis_url)
        r.ping()
        print("✓ Redis connection successful.")
    except Exception as e:
        print(f"✗ Redis connection failed: {e}")

def check_celery(app):
    print("\n[Celery Check]")
    try:
        from celery import Celery
        celery_broker = app.config.get('CELERY_BROKER_URL')
        if not celery_broker:
            print("⚠️  No CELERY_BROKER_URL found in config.")
            return
        celery_app = Celery('diagnostic', broker=celery_broker)
        result = celery_app.control.ping(timeout=2)
        if result:
            print(f"✓ Celery broker reachable: {result}")
        else:
            print("✗ Celery broker not responding.")
    except Exception as e:
        print(f"✗ Celery check failed: {e}")

if __name__ == "__main__":
    # Import your Flask app factory
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    sys.path.insert(0, project_root)
    try:
        from soccer_match_prediction.app import create_app
        app = create_app()
    except Exception as e:
        print(f"Failed to import Flask app: {e}")
        sys.exit(1)

    check_database(app)
    check_redis(app)
    check_celery(app)
