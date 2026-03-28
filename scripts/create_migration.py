"""
Migration script to add new tables for enhanced features
Run: python create_migrations.py
"""

from app import db, create_app
from app.models import (
    Feedback, Leaderboard, Notification, 
    CustomPrediction, UserSettings, TeamStats
)

def create_tables():
    """Create new tables if they don't exist"""
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        print("✅ All tables created successfully")
        
        # Check which tables were created
        from sqlalchemy import inspect
        inspector = inspect(db.engine)
        
        existing_tables = inspector.get_table_names()
        expected_tables = [
            'feedback',
            'leaderboard', 
            'notifications',
            'custom_predictions',
            'user_settings',
            'team_stats'
        ]
        
        print("\n📊 Database Status:")
        for table in expected_tables:
            if table in existing_tables:
                print(f"  ✅ {table}")
            else:
                print(f"  ❌ {table} (missing)")
        
        print(f"\nTotal tables in database: {len(existing_tables)}")

if __name__ == '__main__':
    create_tables()