"""
Seed initial data for new features
"""

from app import db, create_app
from app.models import UserSettings, Leaderboard
from datetime import datetime

def seed_initial_data():
    """Seed initial data for new features"""
    app = create_app()
    
    with app.app_context():
        # Create default user settings for existing users
        users = db.session.query(User).all()
        
        for user in users:
            # Check if settings already exist
            existing_settings = UserSettings.query.filter_by(user_id=user.id).first()
            if not existing_settings:
                settings = UserSettings(
                    user_id=user.id,
                    email_notifications=True,
                    push_notifications=True,
                    bet_alert_threshold=0.65,
                    favorite_leagues='["Premier League", "La Liga", "Serie A"]',
                    theme='auto'
                )
                db.session.add(settings)
        
        # Initialize leaderboard
        update_leaderboard()  # Call your update_leaderboard function
        
        try:
            db.session.commit()
            print("✅ Initial data seeded successfully")
        except Exception as e:
            db.session.rollback()
            print(f"❌ Error seeding data: {e}")

if __name__ == '__main__':
    seed_initial_data()