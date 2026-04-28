# celery_app.py
from soccer_match_prediction.app import create_app
from soccer_match_prediction.app.celery_factory import make_celery

app = create_app()
celery = make_celery(app)

