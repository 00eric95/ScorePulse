import sqlite3

DB_PATH = "data/predictions.db"

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check if column already exists
cursor.execute("PRAGMA table_info(predictions)")
columns = [col[1] for col in cursor.fetchall()]

if 'match_id' not in columns:
    print("Adding 'match_id' column to 'predictions' table...")
    cursor.execute("ALTER TABLE predictions ADD COLUMN match_id INTEGER")
    print("✓ Column added.")
else:
    print("Column 'match_id' already exists.")

conn.commit()
conn.close()