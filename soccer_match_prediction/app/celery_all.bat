@echo off
title ScorePulse AI - Complete Startup
echo ========================================
echo     SCORE PULSE AI - COMPLETE STARTUP
echo ========================================
echo.

echo Step 1: Starting Flask Application...
start cmd /k "python run.py"

timeout /t 5 /nobreak >nul

echo Step 2: Starting Redis (Docker)...
start cmd /k "docker start redis || docker run -d --name redis -p 6379:6379 redis"

timeout /t 10 /nobreak >nul

echo Step 3: Starting Celery Worker...
start cmd /k "celery -A app.celery worker --loglevel=info --pool=gevent --concurrency=4"

timeout /t 5 /nobreak >nul

echo Step 4: Starting Celery Beat Scheduler...
start cmd /k "celery -A app.celery beat --loglevel=info"

timeout /t 5 /nobreak >nul

echo Step 5: Starting Flower Monitoring...
start cmd /k "celery -A app.celery flower --port=5555 --basic_auth=admin:scorepulse123"

echo.
echo ========================================
echo     ALL SERVICES STARTED SUCCESSFULLY!
echo ========================================
echo.
echo Application URLs:
echo - Flask App:    http://localhost:5000
echo - Flower:       http://localhost:5555 (admin:Eric_Ombogo)
echo - Redis:        localhost:6379
echo.
echo Press Ctrl+C in each terminal to stop services
echo.
pause