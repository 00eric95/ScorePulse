# app/celery_factory.py

from celery import Celery
from flask import Flask

def make_celery(app: Flask) -> Celery:
    """Create and configure Celery instance"""
    
    class FlaskTask(Celery.Task):
        """Custom task base with Flask app context"""
        def __call__(self, *args, **kwargs):
            with app.app_context():
                return self.run(*args, **kwargs)
    
    celery = Celery(
        app.import_name,
        backend=app.config['CELERY_RESULT_BACKEND'],
        broker=app.config['CELERY_BROKER_URL'],
        task_cls=FlaskTask
    )
    
    # Update Celery config from Flask config
    celery.conf.update(app.config)
    
    # Task base class
    celery.Task = FlaskTask
    
    # Auto-discover tasks
    celery.autodiscover_tasks(['app.tasks'], force=True)
    
    return celery