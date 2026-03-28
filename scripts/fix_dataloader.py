# fix_data_loader.py - Fix categorical data loading issue
import pandas as pd
import numpy as np
from pathlib import Path
import sys
import os

# Add project root to path
current_dir = Path(__file__).parent
project_root = current_dir.parent
sys.path.append(str(project_root))

def fix_categorical_data():
    """Fix categorical data issues in matches.csv"""
    data_path = project_root / 'data' / 'raw' / 'matches.csv'
    
    if not data_path.exists():
        print(f"❌ File not found: {data_path}")
        return False
    
    print(f"📂 Loading data from: {data_path}")
    
    try:
        # Read CSV with proper encoding
        df = pd.read_csv(data_path, encoding='utf-8', low_memory=False)
        print(f"✅ Loaded {len(df)} matches")
        
        # Check for categorical columns
        categorical_cols = df.select_dtypes(include=['category']).columns
        if len(categorical_cols) > 0:
            print(f"⚠️ Found categorical columns: {list(categorical_cols)}")
            
            # Convert problematic categorical columns to string
            for col in categorical_cols:
                if df[col].dtype.name == 'category':
                    # Preserve NaN values
                    df[col] = df[col].astype(str)
                    # Convert 'nan' string back to actual NaN
                    df[col] = df[col].replace('nan', np.nan)
                    print(f"   Converted {col} from category to string")
        
        # Identify columns that should be numeric
        numeric_cols = ['FTHG', 'FTAG', 'HTHG', 'HTAG', 'HS', 'AS', 'HST', 'AST', 
                       'HF', 'AF', 'HC', 'AC', 'HY', 'AY', 'HR', 'AR']
        
        for col in numeric_cols:
            if col in df.columns:
                # Convert to numeric, coerce errors to NaN
                df[col] = pd.to_numeric(df[col], errors='coerce')
                print(f"   Converted {col} to numeric")
        
        # Clean team name columns
        for col in ['HomeTeam', 'AwayTeam']:
            if col in df.columns:
                # Strip whitespace and handle NaN
                df[col] = df[col].astype(str).str.strip()
                df[col] = df[col].replace('nan', np.nan)
        
        # Save cleaned data
        cleaned_path = project_root / 'data' / 'raw' / 'matches_cleaned.csv'
        df.to_csv(cleaned_path, index=False, encoding='utf-8')
        
        print(f"✅ Saved cleaned data to: {cleaned_path}")
        print(f"   Original shape: {df.shape}")
        print(f"   Columns: {len(df.columns)}")
        
        # Create a smaller test dataset if needed
        test_path = project_root / 'data' / 'raw' / 'matches_test.csv'
        if len(df) > 10000:
            test_df = df.sample(10000, random_state=42)
            test_df.to_csv(test_path, index=False, encoding='utf-8')
            print(f"✅ Created test dataset with 10,000 matches")
        
        return True
        
    except Exception as e:
        print(f"❌ Error fixing data: {e}")
        import traceback
        traceback.print_exc()
        return False

def create_test_data():
    """Create a synthetic test dataset for development"""
    print("\n🎯 Creating synthetic test data...")
    
    # Create synthetic matches
    teams = ['Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'Man United', 
             'Tottenham', 'Leicester', 'West Ham', 'Everton', 'Aston Villa']
    
    matches = []
    import random
    from datetime import datetime, timedelta
    
    for i in range(1000):
        home = random.choice(teams)
        away = random.choice([t for t in teams if t != home])
        
        match = {
            'Div': 'E0',
            'Date': (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%d/%m/%Y'),
            'Time': f"{random.randint(14, 22)}:00",
            'HomeTeam': home,
            'AwayTeam': away,
            'FTHG': random.randint(0, 5),
            'FTAG': random.randint(0, 5),
            'FTR': random.choice(['H', 'D', 'A']),
            'HTHG': random.randint(0, 3),
            'HTAG': random.randint(0, 3),
            'HTR': random.choice(['H', 'D', 'A']),
            'Referee': f"Referee_{random.randint(1, 10)}",
            'HS': random.randint(2, 20),
            'AS': random.randint(2, 20),
            'HST': random.randint(0, 10),
            'AST': random.randint(0, 10),
            'HF': random.randint(5, 25),
            'AF': random.randint(5, 25),
            'HC': random.randint(1, 15),
            'AC': random.randint(1, 15),
            'HY': random.randint(0, 5),
            'AY': random.randint(0, 5),
            'HR': random.randint(0, 2),
            'AR': random.randint(0, 2)
        }
        matches.append(match)
    
    df = pd.DataFrame(matches)
    
    # Save synthetic data
    synth_path = project_root / 'data' / 'raw' / 'matches_synthetic.csv'
    df.to_csv(synth_path, index=False, encoding='utf-8')
    
    print(f"✅ Created synthetic dataset with {len(df)} matches")
    print(f"   Saved to: {synth_path}")
    
    return True

if __name__ == "__main__":
    print("🔧 FIXING DATA LOADING ISSUES")
    print("=" * 50)
    
    # Fix categorical data
    if fix_categorical_data():
        print("\n✅ Data cleaning completed successfully!")
    else:
        print("\n❌ Data cleaning failed. Creating synthetic data instead...")
        create_test_data()
    
    print("\n🎯 NEXT STEPS:")
    print("1. Update config.py to use cleaned data:")
    print("   DATA_FILE = 'data/raw/matches_cleaned.csv'")
    print("2. Or use synthetic data for testing:")
    print("   DATA_FILE = 'data/raw/matches_synthetic.csv'")