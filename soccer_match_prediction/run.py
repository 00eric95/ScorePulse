#!/usr/bin/env python
"""
ScorePulse AI - Main Entry Point (Fixed for Windows + SocketIO)
"""

import os
import sys
import time
from datetime import datetime

# ====================== PATH SETUP ======================
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)

sys.path.insert(0, current_dir)
sys.path.insert(0, project_root)

# ====================== ENVIRONMENT ======================
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ .env file loaded")
except ImportError:
    print("⚠️ python-dotenv not installed")

# ====================== IMPORTS ======================
try:
    from app import create_app, socketio
    print("✓ Imported create_app and socketio")
except ImportError as e:
    print(f"✗ Import failed: {e}")
    sys.exit(1)


if __name__ == '__main__':
    print("=" * 90)
    print("🚀 SCORE PULSE AI SERVER STARTING")
    print(f"   Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"   Directory: {os.getcwd()}")
    print("=" * 90)

    start_time = time.time()

    try:
        # Create the Flask app (this is where all heavy loading happens)
        app = create_app()
        print(f"✅ Flask app created in {time.time() - start_time:.2f} seconds")

        print("\n🌐 Starting SocketIO Server...")
        print("   → http://127.0.0.1:5000")
        print("   → Press Ctrl + C to stop")
        print("-" * 90)

        # FIXED: Do NOT pass async_mode to socketio.run()
        # Set it on the socketio instance if needed (we let it auto-detect)
        socketio.run(
            app,
            host='0.0.0.0',
            port=5000,
            debug=True,
            use_reloader=False,           # Critical on Windows
            allow_unsafe_werkzeug=True,
            log_output=True
        )

    except KeyboardInterrupt:
        print("\n\n👋 Server stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Server failed to start: {e}")
        import traceback
        traceback.print_exc()