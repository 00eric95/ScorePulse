from app import create_app, db
from sqlalchemy import text

app = create_app()

def repair():
    with app.app_context():
        # Get the actual path being used by the app
        print(f"📡 App is currently using: {db.engine.url}")
        
        with db.engine.connect() as conn:
            # List of missing columns from your traceback
            columns = [
                ("last_seen", "DATETIME"),
                ("telegram_id", "VARCHAR(100)"),
                ("telegram_username", "VARCHAR(100)"),
                ("telegram_first_name", "VARCHAR(100)"),
                ("telegram_last_name", "VARCHAR(100)"),
                ("daily_prediction_limit", "INTEGER DEFAULT 5"),
                ("predictions_today", "INTEGER DEFAULT 0"),
                ("last_prediction_reset", "DATETIME"),
                ("credits", "INTEGER DEFAULT 0"),
                ("total_spent", "FLOAT DEFAULT 0.0"),
                ("referral_code", "VARCHAR(50)"),
                ("referred_by", "INTEGER"),
                ("referral_count", "INTEGER DEFAULT 0"),
                ("referral_bonus", "FLOAT DEFAULT 0.0"),
                ("newsletter_subscribed", "BOOLEAN DEFAULT 0"),
                ("newsletter_frequency", "VARCHAR(20)"),
                ("newsletter_interests", "VARCHAR(200)")
            ]
            
            for col, col_type in columns:
                try:
                    conn.execute(text(f"ALTER TABLE user ADD COLUMN {col} {col_type}"))
                    conn.commit()
                    print(f"✅ Added: {col}")
                except Exception as e:
                    if "duplicate" in str(e).lower():
                        print(f"ℹ️ {col} already exists.")
                    else:
                        print(f"⚠️ Error adding {col}: {e}")

if __name__ == "__main__":
    repair()