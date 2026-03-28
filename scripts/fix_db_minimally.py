"""
Minimal database fix - no new data, no new features
"""
import sqlite3
import os
from pathlib import Path
import sys

def fix_missing_columns():
    """Add only the missing subscription_tier column to user table"""
    db_path = Path("instance/site.db")
    
    if not db_path.exists():
        print("[ERR] Database not found")
        return False
    
    print("[INFO] Fixing database schema...")
    
    conn = sqlite3.connect(str(db_path))
    cursor = conn.cursor()
    
    try:
        # Check if subscription_tier column exists
        cursor.execute("PRAGMA table_info(user)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'subscription_tier' not in columns:
            print("[INFO] Adding subscription_tier column...")
            cursor.execute("ALTER TABLE user ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free'")
            
            # Set first user as gold, others as free
            cursor.execute("UPDATE user SET subscription_tier = 'gold' WHERE id = 1")
            cursor.execute("UPDATE user SET subscription_tier = 'free' WHERE id > 1 OR subscription_tier IS NULL")
            print("[OK] Added subscription_tier column")
        
        # Add credits column if missing
        if 'credits' not in columns:
            print("[INFO] Adding credits column...")
            cursor.execute("ALTER TABLE user ADD COLUMN credits INTEGER DEFAULT 3")
            cursor.execute("UPDATE user SET credits = 999 WHERE id = 1")  # Admin gets more
            print("[OK] Added credits column")
        
        conn.commit()
        print("[OK] Database schema fixed")
        return True
        
    except Exception as e:
        print(f"[ERR] Failed to fix database: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

if __name__ == "__main__":
    # Check if we're on Windows and fix encoding
    if sys.platform == 'win32':
        import io
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    
    print("=" * 50)
    print("MINIMAL DATABASE FIX")
    print("=" * 50)
    
    if fix_missing_columns():
        print("\n[DONE] Fix completed successfully")
    else:
        print("\n[FAIL] Fix failed")