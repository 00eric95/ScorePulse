# fix_encoding.py - Fix Unicode encoding issues on Windows
import sys
import io

def fix_windows_encoding():
    """Fix Unicode encoding issues on Windows"""
    if sys.platform == 'win32':
        # Set stdout to use UTF-8
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
        sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
        
        # Set environment variable for console encoding
        import os
        os.environ['PYTHONIOENCODING'] = 'utf-8'
        
        print("✅ Fixed Windows console encoding for Unicode characters")
    
    return True

# Apply fix when imported
fix_windows_encoding()