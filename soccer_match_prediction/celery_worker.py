# celery_worker.py
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print("📍 [celery_worker] Initializing Celery worker...", flush=True)

from app import create_app

print("📍 [celery_worker] Creating Flask app...", flush=True)
app = create_app()
print("📍 [celery_worker] Flask app created successfully", flush=True)

# Push an application context so that all tasks can use current_app and db
ctx = app.app_context()
ctx.push()
print("📍 [celery_worker] App context pushed for worker", flush=True)

celery = app.celery
print(f"📍 [celery_worker] Celery instance obtained: {type(celery)}", flush=True)