# app/celery_factory.py
from celery import Celery
from flask import Flask
from celery.schedules import crontab

def make_celery(app: Flask) -> Celery:
    class FlaskTask(Celery.Task):
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
    celery.conf.update(
        task_serializer=app.config.get('CELERY_TASK_SERIALIZER', 'json'),
        result_serializer=app.config.get('CELERY_RESULT_SERIALIZER', 'json'),
        accept_content=app.config.get('CELERY_ACCEPT_CONTENT', ['json']),
        timezone=app.config.get('CELERY_TIMEZONE', 'UTC'),
        enable_utc=app.config.get('CELERY_ENABLE_UTC', True),
        task_always_eager=app.config.get('CELERY_TASK_ALWAYS_EAGER', False),
        worker_pool=app.config.get('CELERY_WORKER_POOL', 'solo'),
        broker_connection_retry_on_startup=True,
    )

    # Task routes
    celery.conf.task_routes = {
        'app.tasks.send_*': {'queue': 'email'},
        'app.tasks.process_*': {'queue': 'predictions'},
        'app.tasks.generate_*': {'queue': 'reports'},
        'app.tasks.cleanup_*': {'queue': 'maintenance'},
        'app.tasks.update_*': {'queue': 'maintenance'},
    }

    # Beat schedule
    celery.conf.beat_schedule = {
        'update-leaderboard-every-hour': {
            'task': 'app.tasks.update_leaderboard_task',
            'schedule': 3600.0,
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

    return celery