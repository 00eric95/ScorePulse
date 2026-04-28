#!/usr/bin/env python
"""Run Celery worker, beat scheduler, and Flower monitoring in one script"""

import os
import sys
import threading
import subprocess
import signal
import time

# Add project root to path (go up 2 levels: soccer_match_prediction -> .. -> project root)
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)  # Go to parent (SCORE_PULSEAIv2)
sys.path.insert(0, current_dir)  # Add soccer_match_prediction
sys.path.insert(0, parent_dir)   # Add parent directory where monitoring module is

def run_worker():
    """Run Celery worker with multiple queues"""
    print("🚀 Starting Celery worker...")
    
    # Start worker for different queues
    worker_cmd = [
        'celery', '-A', 'celery_worker.celery', 'worker',   # ← changed
        '--loglevel=info',
        '--concurrency=4',
        '--pool=gevent',   # or 'solo' on Windows if gevent fails
        '--queues=default,email,predictions,reports,maintenance',
        '--hostname=worker1@%h',
        '--max-tasks-per-child=1000',
        '--autoscale=10,3',
    ]
    
    try:
        subprocess.run(worker_cmd)
    except KeyboardInterrupt:
        print("Worker stopped by user")
    except Exception as e:
        print(f"❌ Worker failed: {e}")

def run_beat():
    """Run Celery beat scheduler"""
    print("⏰ Starting Celery beat scheduler...")
    time.sleep(2)  # Give worker time to start
    
    beat_cmd = [
        'celery', '-A', 'app.celery', 'beat',
        '--loglevel=info',
        '--scheduler=celery.beat.PersistentScheduler',
        '--schedule=celerybeat-schedule.db',
    ]
    
    try:
        subprocess.run(beat_cmd)
    except KeyboardInterrupt:
        print("Beat scheduler stopped by user")
    except Exception as e:
        print(f"❌ Beat scheduler failed: {e}")

def run_flower():
    """Run Flower monitoring dashboard"""
    print("🌸 Starting Flower monitoring...")
    time.sleep(3)  # Give worker and beat time to start
    
    flower_cmd = [
        'celery', '-A', 'app.celery', 'flower',
        '--port=5555',
        '--basic_auth=admin:scorepulse123',
        '--max_tasks=1000',
        '--db=flower.db',
    ]
    
    try:
        subprocess.run(flower_cmd)
    except KeyboardInterrupt:
        print("Flower stopped by user")
    except Exception as e:
        print(f"❌ Flower failed: {e}")

def run_single_worker_with_beat():
    """Alternative: Run worker with embedded beat scheduler"""
    print("⚡ Starting combined worker with beat scheduler...")
    
    cmd = [
        'celery', '-A', 'app.celery', 'worker',
        '--loglevel=info',
        '--concurrency=4',
        '--pool=gevent',  # Changed from eventlet to gevent
        '--beat',  # This flag enables beat scheduler in the worker
        '--queues=default,email,predictions,reports,maintenance',
        '--scheduler=celery.beat.PersistentScheduler',
        '--max-tasks-per-child=1000',
    ]
    
    subprocess.run(cmd)

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print("\n🛑 Shutting down Celery services...")
    sys.exit(0)

if __name__ == '__main__':
    # Register signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 50)
    print("🎯 Celery All-in-One Service Manager")
    print("=" * 50)
    print("Options:")
    print("1. Run worker + beat + Flower (separate processes)")
    print("2. Run combined worker with beat + Flower")
    print("3. Run only worker")
    print("4. Run only beat scheduler")
    print("5. Run only Flower monitoring")
    print("6. Run simple worker (Windows compatible)")
    
    try:
        choice = input("\nSelect option (1-6): ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\n\n🛑 Cancelled by user")
        sys.exit(0)
    
    # Create Flask app context first
    try:
        from app import create_app
        app = create_app()
    except ImportError as e:
        print(f"❌ Failed to import Flask app: {e}")
        print("Make sure you're running this from the correct directory")
        sys.exit(1)
    
    with app.app_context():
        if choice == '1':
            # Option 1: Run all services in separate threads
            print("\n🚀 Starting all services...")
            print("-" * 40)
            
            # Run worker in separate thread
            worker_thread = threading.Thread(target=run_worker, daemon=True)
            worker_thread.start()
            
            # Run beat in separate thread
            beat_thread = threading.Thread(target=run_beat, daemon=True)
            beat_thread.start()
            
            # Run Flower in main thread (blocking)
            run_flower()
            
        elif choice == '2':
            # Option 2: Combined worker with beat, plus Flower
            print("\n⚡ Starting combined worker with beat + Flower...")
            print("-" * 40)
            
            # Run combined worker with beat in thread
            worker_beat_thread = threading.Thread(target=run_single_worker_with_beat, daemon=True)
            worker_beat_thread.start()
            
            # Run Flower in main thread
            run_flower()
            
        elif choice == '3':
            # Option 3: Only worker
            run_worker()
            
        elif choice == '4':
            # Option 4: Only beat
            run_beat()
            
        elif choice == '5':
            # Option 5: Only Flower
            run_flower()
            
        elif choice == '6':
            # Option 6: Simple worker (Windows compatible)
            print("\n🪟 Starting simple worker for Windows...")
            print("-" * 40)
            
            simple_cmd = [
                'celery', '-A', 'celery_worker.celery', 'worker',
                '--loglevel=info',
                '--pool=solo',
                '--concurrency=2',
            ]
            
            try:
                subprocess.run(simple_cmd)
            except KeyboardInterrupt:
                print("Worker stopped by user")
            
        else:
            print("❌ Invalid option. Using default (option 6 - Simple worker)")
            simple_cmd = [
                'celery', '-A', 'app.celery', 'worker',
                '--loglevel=info',
                '--pool=solo',
                '--concurrency=2',
                '--max-tasks-per-child=100',
            ]
            
            try:
                subprocess.run(simple_cmd)
            except KeyboardInterrupt:
                print("Worker stopped by user")