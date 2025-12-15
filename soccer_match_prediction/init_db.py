import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

# --- UPDATED IMPORTS ---
# We don't strictly need to import Config here, but create_app uses it internally.
# Just ensure create_app is imported correctly.
from app import create_app, db
from app import models 

def init_database():
    print("🔄 Initializing Database...")
    app = create_app()
    with app.app_context():
        db_path = os.path.join(os.path.dirname(__file__), 'instance')
        os.makedirs(db_path, exist_ok=True)
        db.create_all()
        print(f"✅ Database created at: {os.path.join(db_path, 'site.db')}")

if __name__ == "__main__":
    init_database()