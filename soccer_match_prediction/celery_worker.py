# celery_worker.py
"""Celery worker entry point – builds the Flask app and exposes its celery instance."""

import os
import sys

# Ensure the project root is in path
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from app import create_app

# Build the Flask application (this initializes everything,
# including the fully configured Celery instance)
app = create_app()

# This is the instance the worker will use
celery = app.celery