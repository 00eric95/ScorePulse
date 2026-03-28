#!/usr/bin/env python
"""
Improved run.py for ScorePulse AI - Flask + SocketIO application
Compatible with Windows, avoids eventlet deprecation issues
"""

import os
import sys
import time
from datetime import datetime

# Add project paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, current_dir)
sys.path.insert(0, project_root)

# Try to load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ .env file loaded")
except ImportError:
    print("⚠️ python-dotenv not installed - skipping .env loading")

# Import Flask & SocketIO
from flask import Flask
from flask_socketio import SocketIO

# Try to import your app factory
try:
    from app import create_app, socketio
    print("✓ Successfully imported create_app and socketio")
except ImportError as e:
    print(f"✗ Failed to import app: {e}")
    print("Make sure you're running from the correct directory")
    sys.exit(1)

def get_socketio_mode():
    """Determine best SocketIO async mode for this environment"""
    mode = os.getenv('SOCKETIO_ASYNC_MODE', 'threading').lower()
    
    if mode not in ['threading', 'gevent', 'eventlet']:
        # Auto-detect best mode
        try:
            import gevent
            print("→ Detected gevent → using gevent mode")
            return 'gevent'
        except ImportError:
            try:
                import eventlet
                print("→ Detected eventlet → using eventlet mode (deprecated warning expected)")
                return 'eventlet'
            except ImportError:
                print("→ Using threading mode (safest fallback)")
                return 'threading'
    
    print(f"→ Using explicit mode from env: {mode}")
    return mode

if __name__ == '__main__':
    print("=" * 60)
    print(f"  ScorePulse AI Server Startup - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Working directory: {os.getcwd()}")
    print(f"  Python: {sys.version.split()[0]}")
    print("=" * 60)

    start_time = time.time()

    # Create Flask app
    try:
        app = create_app()
        print(f"✓ Flask app created in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"✗ Failed to create Flask app: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    # Determine SocketIO async mode
    async_mode = get_socketio_mode()

    # Apply monkey patching only when needed
    if async_mode == 'gevent':
        try:
            from gevent import monkey
            monkey.patch_all(thread=False)  # Avoid thread patching issues on Windows
            print("✓ gevent monkey patching applied (thread=False)")
        except Exception as e:
            print(f"⚠️ gevent patching failed: {e} → falling back to threading")
            async_mode = 'threading'
    elif async_mode == 'eventlet':
        try:
            import eventlet
            eventlet.monkey_patch(thread=False)
            print("✓ eventlet monkey patching applied (thread=False)")
        except Exception as e:
            print(f"⚠️ eventlet patching failed: {e} → falling back to threading")
            async_mode = 'threading'

    # Override socketio async_mode if needed
    if hasattr(socketio, 'async_mode'):
        socketio.async_mode = async_mode
        print(f"SocketIO async mode set to: {async_mode}")

    # Print final startup info
    print("\n" + "=" * 60)
    print("  Server ready to start")
    print("  Debug mode: ON")
    print("  Access URLs:")
    print("    • Local:     http://127.0.0.1:5000")
    print("    • Network:   http://192.168.0.116:5000  (if allowed by firewall)")
    print("=" * 60 + "\n")

    try:
        # Run the server (Flask only, SocketIO commented out)
        # socketio.run(
        #     app,
        #     debug=True,
        #     host='0.0.0.0',
        #     port=5000,
        #     use_reloader=False,           # Avoid double startup issues
        #     allow_unsafe_werkzeug=True,   # Needed in newer Flask
        #     log_output=True
        # )
        app.run(debug=True, host='0.0.0.0', port=5000)
    except KeyboardInterrupt:
        print("\nServer stopped by user (Ctrl+C)")
    except Exception as e:
        print(f"Server crashed: {e}")
        import traceback
        traceback.print_exc()