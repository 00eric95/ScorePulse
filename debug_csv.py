import pandas as pd
import os

# Define path to your file
file_path = "data/raw/matches.csv"

if not os.path.exists(file_path):
    print(f"❌ File not found at: {file_path}")
else:
    try:
        # Try reading with standard comma separator
        df = pd.read_csv(file_path, encoding='latin1', low_memory=False)
        
        print("\n🔍 --- CSV DIAGNOSTIC REPORT ---")
        print(f"File: {file_path}")
        print(f"Total Columns: {len(df.columns)}")
        print(f"Rows: {len(df)}")
        
        print("\n📋 ACTUAL COLUMN NAMES FOUND:")
        print(df.columns.tolist())
        
        print("\n👀 FIRST ROW OF DATA:")
        print(df.iloc[0].to_dict())

    except Exception as e:
        print(f"\n❌ Error reading CSV: {e}")