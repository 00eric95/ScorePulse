# fix_schema_corrected.py
import os
import sys
import sqlite3
from datetime import datetime

def find_database():
    """Find the database file in various locations"""
    possible_paths = [
        # Current directory structure
        os.path.join('instance', 'scorepulse.db'),
        # One level up (based on your logs)
        os.path.join('..', 'instance', 'scorepulse.db'),
        # Parent directory of parent
        os.path.join('..', '..', 'instance', 'scorepulse.db'),
        # Absolute path from logs
        r'C:\Users\LENOVO\OneDrive\Desktop\SCORE_PULSEAIv2\instance\scorepulse.db',
        # Another possible location
        os.path.join('data', 'predictions.db'),
    ]
    
    for path in possible_paths:
        if os.path.exists(path):
            print(f"✅ Found database at: {path}")
            return os.path.abspath(path)
    
    # Search in common locations
    print("🔍 Searching for database...")
    
    # Check current directory and subdirectories
    for root, dirs, files in os.walk('.'):
        for file in files:
            if file.endswith('.db'):
                full_path = os.path.join(root, file)
                print(f"Found DB file: {full_path}")
                return os.path.abspath(full_path)
    
    # Check parent directory
    for root, dirs, files in os.walk('..'):
        for file in files:
            if file.endswith('.db'):
                full_path = os.path.join(root, file)
                print(f"Found DB file: {full_path}")
                return os.path.abspath(full_path)
    
    return None

def check_schema(db_path):
    """Check current database schema and fix issues"""
    
    if not db_path or not os.path.exists(db_path):
        print(f"❌ Database not found at: {db_path}")
        return False
    
    backup_path = f"{db_path}.backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    
    print(f"🔍 Checking database schema...")
    print(f"📊 Database: {db_path}")
    
    # Backup database
    try:
        import shutil
        shutil.copy2(db_path, backup_path)
        print(f"✅ Database backed up to: {backup_path}")
    except Exception as e:
        print(f"⚠️ Could not backup: {e}")
    
    # Connect to database
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Get current columns in users table
        cursor.execute("PRAGMA table_info(users)")
        current_columns = cursor.fetchall()
        current_column_names = [col[1] for col in current_columns]
        
        print(f"\n📋 Current columns in 'users' table ({len(current_column_names)}):")
        for col in current_columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Check if is_premium exists
        if 'is_premium' in current_column_names:
            print(f"\n✅ 'is_premium' column already exists!")
            print(f"🔍 Checking for other missing columns...")
        else:
            print(f"\n❌ 'is_premium' column is MISSING!")
        
        # Columns that should exist based on your models.py
        expected_columns = [
            ('is_premium', 'BOOLEAN DEFAULT 0'),
            ('premium_expiry', 'DATETIME'),
            ('daily_prediction_limit', 'INTEGER DEFAULT 3'),
            ('predictions_today', 'INTEGER DEFAULT 0'),
            ('last_prediction_reset', 'DATETIME'),
            ('credits', 'INTEGER DEFAULT 0'),
            ('total_spent', 'FLOAT DEFAULT 0.0'),
            ('telegram_id', 'VARCHAR(100)'),
            ('telegram_username', 'VARCHAR(100)'),
            ('telegram_first_name', 'VARCHAR(100)'),
            ('telegram_last_name', 'VARCHAR(100)'),
            ('referral_code', 'VARCHAR(20)'),
            ('referred_by', 'INTEGER'),
            ('referral_count', 'INTEGER DEFAULT 0'),
            ('referral_bonus', 'INTEGER DEFAULT 0'),
            ('newsletter_subscribed', 'BOOLEAN DEFAULT 1'),
            ('newsletter_frequency', 'VARCHAR(20) DEFAULT "weekly"'),
            ('last_seen', 'DATETIME'),
            ('login_count', 'INTEGER DEFAULT 0'),
            ('subscription_tier', 'VARCHAR(20) DEFAULT "free"')
        ]
        
        print(f"\n➕ Adding missing columns...")
        added_count = 0
        
        for column_name, column_def in expected_columns:
            if column_name not in current_column_names:
                try:
                    # Extract just the type for ALTER TABLE
                    col_type = column_def.split()[0]  # Get the type part
                    default_part = ""
                    if "DEFAULT" in column_def:
                        default_part = " " + " ".join(column_def.split()[column_def.split().index("DEFAULT"):])
                    
                    sql = f"ALTER TABLE users ADD COLUMN {column_name} {col_type}{default_part}"
                    cursor.execute(sql)
                    print(f"  ✅ Added: {column_name} ({col_type})")
                    added_count += 1
                except Exception as e:
                    if "duplicate column name" in str(e):
                        print(f"  ⚠️  Column already exists (duplicate check failed): {column_name}")
                    else:
                        print(f"  ❌ Failed to add {column_name}: {e}")
            else:
                print(f"  ✓ Already exists: {column_name}")
        
        conn.commit()
        
        # Verify the fix
        print(f"\n✅ Verification:")
        cursor.execute("PRAGMA table_info(users)")
        final_columns = cursor.fetchall()
        
        # Check if is_premium is now present
        has_is_premium = any(col[1] == 'is_premium' for col in final_columns)
        
        if has_is_premium:
            print(f"🎉 SUCCESS: 'is_premium' column is now in the database!")
        else:
            print(f"❌ ERROR: 'is_premium' column still missing!")
        
        print(f"\n📊 Summary:")
        print(f"   - Database: {db_path}")
        print(f"   - Backup: {backup_path}")
        print(f"   - Columns added: {added_count}")
        print(f"   - Total columns: {len(final_columns)}")
        
        # Show final column list
        print(f"\n📋 Final columns in 'users' table:")
        for col in final_columns:
            print(f"  - {col[1]} ({col[2]})")
        
        return has_is_premium
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        conn.close()

def quick_fix_sql(db_path):
    """Run a quick SQL fix"""
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return False
    
    print(f"\n🔧 Running quick SQL fix...")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # SQL commands to add missing columns
    sql_commands = [
        "ALTER TABLE users ADD COLUMN is_premium BOOLEAN DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN premium_expiry DATETIME;",
        "ALTER TABLE users ADD COLUMN daily_prediction_limit INTEGER DEFAULT 3;",
        "ALTER TABLE users ADD COLUMN predictions_today INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN last_prediction_reset DATETIME;",
        "ALTER TABLE users ADD COLUMN credits INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN total_spent FLOAT DEFAULT 0.0;",
        "ALTER TABLE users ADD COLUMN telegram_id VARCHAR(100);",
        "ALTER TABLE users ADD COLUMN telegram_username VARCHAR(100);",
        "ALTER TABLE users ADD COLUMN telegram_first_name VARCHAR(100);",
        "ALTER TABLE users ADD COLUMN telegram_last_name VARCHAR(100);",
        "ALTER TABLE users ADD COLUMN referral_code VARCHAR(20);",
        "ALTER TABLE users ADD COLUMN referred_by INTEGER;",
        "ALTER TABLE users ADD COLUMN referral_count INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN referral_bonus INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN newsletter_subscribed BOOLEAN DEFAULT 1;",
        "ALTER TABLE users ADD COLUMN newsletter_frequency VARCHAR(20) DEFAULT 'weekly';",
        "ALTER TABLE users ADD COLUMN last_seen DATETIME;",
        "ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0;",
        "ALTER TABLE users ADD COLUMN subscription_tier VARCHAR(20) DEFAULT 'free';"
    ]
    
    success_count = 0
    error_count = 0
    
    for sql in sql_commands:
        try:
            cursor.execute(sql)
            success_count += 1
            print(f"  ✅ {sql.split()[2]} {sql.split()[3]}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"  ⚠️  Column already exists: {sql.split()[2]} {sql.split()[3]}")
                success_count += 1  # Not an error, it already exists
            else:
                print(f"  ❌ Error: {e}")
                error_count += 1
    
    conn.commit()
    conn.close()
    
    print(f"\n📊 Quick fix complete:")
    print(f"   - Successful: {success_count}")
    print(f"   - Errors: {error_count}")
    
    return error_count == 0

def run_sqlite_shell(db_path):
    """Run SQLite shell with the database"""
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return
    
    print(f"\n📟 Opening SQLite shell for: {db_path}")
    print("=" * 60)
    print("Useful commands:")
    print("  .tables                         - List all tables")
    print("  .schema users                   - Show users table schema")
    print("  PRAGMA table_info(users);       - Show column info")
    print("  SELECT * FROM users LIMIT 1;    - Show first user")
    print("  .exit                           - Exit shell")
    print("=" * 60)
    print("\nOpening SQLite shell...")
    
    # Run sqlite3 shell
    import subprocess
    subprocess.run(['sqlite3', db_path])

if __name__ == "__main__":
    print("=" * 60)
    print("DATABASE SCHEMA FIXER")
    print("=" * 60)
    
    # Find the database
    db_path = find_database()
    
    if not db_path:
        print("\n❌ Could not find database file!")
        print("\nPlease specify the database path:")
        user_path = input("Enter path to scorepulse.db: ").strip()
        
        if os.path.exists(user_path):
            db_path = user_path
        else:
            print("❌ Path does not exist. Exiting.")
            sys.exit(1)
    
    print(f"\n📊 Using database: {db_path}")
    
    print("\nChoose an option:")
    print("1. Check and fix schema (Recommended)")
    print("2. Quick fix (Add all missing columns)")
    print("3. Open SQLite shell (Manual inspection)")
    
    choice = input("\nEnter choice (1-3): ").strip()
    
    if choice == '1':
        success = check_schema(db_path)
        if success:
            print("\n✅ Schema fixed successfully!")
        else:
            print("\n❌ Schema fix failed. Try option 2.")
    elif choice == '2':
        success = quick_fix_sql(db_path)
        if success:
            print("\n✅ Quick fix completed successfully!")
        else:
            print("\n⚠️  Quick fix had some issues. Check above for details.")
    elif choice == '3':
        run_sqlite_shell(db_path)
    else:
        print("Invalid choice. Running option 1...")
        check_schema(db_path)
    
    print("\n🚀 Done! You can now run 'python run.py' to start the app.")