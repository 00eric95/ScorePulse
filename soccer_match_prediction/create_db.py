#!/usr/bin/env python3
"""
Simple database creation script
"""

import os
import sys

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    from app import create_app
    print("Creating Flask app...")
    app = create_app()

    with app.app_context():
        from app import db
        print("Creating database tables...")
        db.create_all()
        print("✅ Database created successfully!")

except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)