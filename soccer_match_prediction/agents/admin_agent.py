"""
Admin Chatbot - Comprehensive AI Assistant for ScorePulse AI Administration
Features:
- User management (list, promote, demote, ban, delete, view stats)
- Prediction management (list, delete, force update outcomes)
- Model management (list, reload, evaluate, retrain)
- System operations (clear cache, restart services, health checks, logs)
- Data management (export/import CSV, validate)
- Monitoring (metrics, alerts, Celery status)
- MCP server with authentication and configurable
- Caching with Redis / in‑memory fallback
"""

import os
import sys
import json
import logging
import threading
import time
import socket
import secrets
import shutil
import subprocess
import re
import csv
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass, field

import pandas as pd
import numpy as np

# Flask and app imports (lazy where possible)
try:
    from flask import current_app, url_for
    from flask_login import current_user
    from app import db
    from app.models import (
        User, Prediction, Payment, Notification, Leaderboard,
        UserActivity, Feedback, SystemLog, ModelEvaluation,
        LearningReport, OrchestrationLog, Team, Match, League,
        ChatSession, ChatMessage
    )
    HAS_FLASK = True
except ImportError:
    HAS_FLASK = False

# Config import
try:
    from config import Config, get_config
    HAS_CONFIG = True
except ImportError:
    HAS_CONFIG = False

# Celery
try:
    from app.tasks import (
        update_leaderboard_task, cleanup_old_tasks, update_platform_stats,
        refresh_ai_models, send_daily_reports_task, process_unprocessed_learning
    )
    from celery import current_app as celery_app
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False

# Monitoring
try:
    from monitoring.health_checker import HealthChecker
    from monitoring.metrics_collector import MetricsCollector
    from monitoring.alert_system import AlertSystem
    HAS_MONITORING = True
except ImportError:
    HAS_MONITORING = False

# Set up logging
logger = logging.getLogger(__name__)


class MCPServer:
    """MCP Server with authentication and configuration."""

    def __init__(self, admin_agent, config: Dict[str, Any]):
        self.admin = admin_agent
        self.config = config
        self.host = config.get('MCP_SERVER_HOST', 'localhost')
        self.port = int(config.get('MCP_SERVER_PORT', 8080))
        self.auth_token = config.get('MCP_AUTH_TOKEN', '')
        self.enabled = config.get('MCP_SERVER_ENABLED', False)
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.server_lock = threading.Lock()

    def _check_auth(self, headers) -> bool:
        if not self.auth_token:
            return True
        auth_header = headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            return auth_header[7:] == self.auth_token
        return headers.get('X-API-Key', '') == self.auth_token

    def start_server(self) -> bool:
        if not self.enabled:
            logger.info("MCP server disabled by config")
            return False
        if self.is_running:
            return False
        try:
            import http.server
            import socketserver

            class Handler(http.server.BaseHTTPRequestHandler):
                def do_GET(self):
                    if not self.server.mcp_server._check_auth(self.headers):
                        self.send_response(401)
                        self.send_header('WWW-Authenticate', 'Bearer')
                        self.end_headers()
                        return
                    if self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps({
                            'status': 'running',
                            'version': '1.0',
                            'tools': self.server.mcp_server.admin.get_command_list()
                        }).encode())
                    else:
                        self.send_response(404)

                def do_POST(self):
                    if not self.server.mcp_server._check_auth(self.headers):
                        self.send_response(401)
                        self.end_headers()
                        return
                    if self.path == '/execute':
                        length = int(self.headers.get('Content-Length', 0))
                        data = json.loads(self.rfile.read(length))
                        cmd = data.get('command')
                        args = data.get('args', {})
                        result = self.server.mcp_server.admin.process_command(cmd, args)
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        self.wfile.write(json.dumps(result).encode())
                    else:
                        self.send_response(404)

            self.server = socketserver.TCPServer((self.host, self.port), Handler)
            self.server.mcp_server = self
            self.is_running = True
            self.server_thread = threading.Thread(target=self.server.serve_forever, daemon=True)
            self.server_thread.start()
            logger.info(f"MCP server started on {self.host}:{self.port}")
            return True
        except Exception as e:
            logger.error(f"MCP server start failed: {e}")
            return False

    def stop_server(self) -> bool:
        if self.server and self.is_running:
            self.server.shutdown()
            self.server.server_close()
            self.is_running = False
            logger.info("MCP server stopped")
            return True
        return False


class AdminAgent:
    """
    Comprehensive administrative agent for ScorePulse AI.
    Handles user management, predictions, models, system health, caching,
    Celery tasks, data export/import, and much more.
    """

    def __init__(self, config: Dict[str, Any] = None, cache=None):
        self.config = config or {}
        if not self.config and HAS_CONFIG:
            try:
                cfg = get_config()
                self.config = {k: getattr(cfg, k) for k in dir(cfg) if not k.startswith('_')}
            except:
                pass

        # Paths using pathlib
        self.base_dir = Path(self.config.get('BASE_DIR', Path.cwd()))
        self.data_dir = self.base_dir / 'data'
        self.logs_dir = self.base_dir / 'logs'
        self.models_dir = self.base_dir / 'models'
        for d in [self.data_dir, self.logs_dir, self.models_dir]:
            d.mkdir(parents=True, exist_ok=True)

        # Cache (Redis or in‑memory)
        self.cache = cache
        self._local_cache = {}
        self._cache_ttl = self.config.get('CACHE_DEFAULT_TIMEOUT', 300)

        # MCP server
        self.mcp_server = MCPServer(self, self.config)
        self.mcp_enabled = False

        # Internal storage for quick access
        self._command_registry = self._build_command_registry()

        logger.info(f"AdminAgent initialized. Project root: {self.base_dir}")

    # ------------------------------------------------------------------
    # Caching helpers
    # ------------------------------------------------------------------
    def _get_cache(self, key: str) -> Any:
        if self.cache:
            try:
                return self.cache.get(key)
            except:
                pass
        if key in self._local_cache:
            val, expiry = self._local_cache[key]
            if expiry > time.time():
                return val
            else:
                del self._local_cache[key]
        return None

    def _set_cache(self, key: str, value: Any, ttl: int = None):
        ttl = ttl or self._cache_ttl
        if self.cache:
            try:
                self.cache.set(key, value, timeout=ttl)
                return
            except:
                pass
        self._local_cache[key] = (value, time.time() + ttl)

    def _clear_cache(self, pattern: str = None):
        if self.cache and hasattr(self.cache, 'clear'):
            self.cache.clear(pattern)
        else:
            self._local_cache.clear()

    # ------------------------------------------------------------------
    # Command registry
    # ------------------------------------------------------------------
    def _build_command_registry(self) -> Dict[str, Dict]:
        return {
            # User management
            'list_users': {'func': self._list_users, 'desc': 'List all users with pagination'},
            'get_user': {'func': self._get_user, 'desc': 'Get user details by ID or email'},
            'promote_user': {'func': self._promote_user, 'desc': 'Promote user to admin'},
            'demote_user': {'func': self._demote_user, 'desc': 'Remove admin privileges'},
            'ban_user': {'func': self._ban_user, 'desc': 'Ban a user'},
            'unban_user': {'func': self._unban_user, 'desc': 'Unban a user'},
            'delete_user': {'func': self._delete_user, 'desc': 'Delete a user (careful)'},
            'user_stats': {'func': self._user_stats, 'desc': 'Get user statistics summary'},
            'update_subscription': {'func': self._update_subscription, 'desc': 'Change user subscription tier'},
            'add_credits': {'func': self._add_credits, 'desc': 'Add credits to a user'},

            # Prediction management
            'list_predictions': {'func': self._list_predictions, 'desc': 'List predictions with filters'},
            'delete_prediction': {'func': self._delete_prediction, 'desc': 'Delete a prediction by ID'},
            'force_update_outcomes': {'func': self._force_update_outcomes, 'desc': 'Force update prediction outcomes'},
            'prediction_stats': {'func': self._prediction_stats, 'desc': 'Get prediction platform stats'},
            'recalculate_leaderboard': {'func': self._recalculate_leaderboard, 'desc': 'Force leaderboard recalculation'},

            # Model management
            'list_models': {'func': self._list_models, 'desc': 'List loaded ML models'},
            'reload_models': {'func': self._reload_models, 'desc': 'Reload all ML models'},
            'evaluate_models': {'func': self._evaluate_models, 'desc': 'Run model evaluation on test set'},
            'retrain_model': {'func': self._retrain_model, 'desc': 'Retrain a specific model (WLD/BTTS/Over25/TotalGoals)'},
            'model_health': {'func': self._model_health, 'desc': 'Check model health against thresholds'},

            # System operations
            'health_check': {'func': self._health_check, 'desc': 'Run full system health check'},
            'system_status': {'func': self._system_status, 'desc': 'Get overall system status'},
            'clear_cache': {'func': self._clear_cache_cmd, 'desc': 'Clear application cache'},
            'view_logs': {'func': self._view_logs, 'desc': 'View recent system logs'},
            'run_maintenance': {'func': self._run_maintenance, 'desc': 'Run cleanup tasks (logs, old predictions)'},
            'restart_celery': {'func': self._restart_celery, 'desc': 'Restart Celery workers (requires shell)'},
            'export_system_logs': {'func': self._export_system_logs, 'desc': 'Export logs to CSV/JSON'},

            # Data management
            'export_users': {'func': self._export_users, 'desc': 'Export users to CSV'},
            'export_predictions': {'func': self._export_predictions, 'desc': 'Export predictions to CSV'},
            'import_teams': {'func': self._import_teams, 'desc': 'Import teams from CSV file'},
            'validate_csv': {'func': self._validate_csv, 'desc': 'Validate a CSV file against expected schema'},
            'backup_db': {'func': self._backup_db, 'desc': 'Create database backup'},

            # Monitoring & Celery
            'celery_status': {'func': self._celery_status, 'desc': 'Get Celery worker status'},
            'queue_length': {'func': self._queue_length, 'desc': 'Get Celery queue lengths'},
            'metrics_summary': {'func': self._metrics_summary, 'desc': 'Get metrics collector summary'},
            'active_alerts': {'func': self._active_alerts, 'desc': 'List active alerts'},

            # MCP server control
            'start_mcp': {'func': self._start_mcp, 'desc': 'Start MCP server'},
            'stop_mcp': {'func': self._stop_mcp, 'desc': 'Stop MCP server'},
            'mcp_status': {'func': self._mcp_status, 'desc': 'Get MCP server status'},

            # Help
            'help': {'func': self._help, 'desc': 'Show this help'},
        }

    def get_command_list(self) -> List[str]:
        return list(self._command_registry.keys())

    def process_command(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        args = args or {}
        cmd = command.lower().strip()
        if cmd not in self._command_registry:
            return {'success': False, 'message': f'Unknown command: {cmd}', 'timestamp': datetime.now().isoformat()}
        try:
            result = self._command_registry[cmd]['func'](args)
            result['command'] = cmd
            result['timestamp'] = datetime.now().isoformat()
            return result
        except Exception as e:
            logger.exception(f"Error in command {cmd}: {e}")
            return {'success': False, 'message': str(e), 'command': cmd, 'timestamp': datetime.now().isoformat()}

    # ------------------------------------------------------------------
    # Command implementations
    # ------------------------------------------------------------------

    # ----- User management -----
    def _list_users(self, args: Dict) -> Dict:
        page = args.get('page', 1)
        per_page = min(args.get('per_page', 20), 100)
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        users = User.query.order_by(User.id).paginate(page=page, per_page=per_page, error_out=False)
        data = [{'id': u.id, 'username': u.username, 'email': u.email, 'is_admin': u.is_admin,
                 'is_verified': u.is_verified, 'subscription_tier': u.subscription_tier,
                 'created_at': u.created_at.isoformat() if u.created_at else None}
                for u in users.items]
        return {'success': True, 'users': data, 'total': users.total, 'page': page, 'per_page': per_page}

    def _get_user(self, args: Dict) -> Dict:
        identifier = args.get('identifier')
        if not identifier:
            return {'success': False, 'message': 'Missing identifier (email or id)'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = None
        if identifier.isdigit():
            user = User.query.get(int(identifier))
        else:
            user = User.query.filter_by(email=identifier).first()
        if not user:
            return {'success': False, 'message': 'User not found'}
        return {
            'success': True,
            'user': {
                'id': user.id, 'username': user.username, 'email': user.email,
                'is_admin': user.is_admin, 'is_verified': user.is_verified,
                'subscription_tier': user.subscription_tier, 'credits': user.credits,
                'predictions_today': user.predictions_today, 'daily_limit': user.daily_prediction_limit,
                'created_at': user.created_at.isoformat() if user.created_at else None,
                'last_login': user.last_login.isoformat() if user.last_login else None,
                'total_predictions': user.predictions.count(),
                'wins': sum(1 for p in user.predictions if p.status == 'Won'),
                'losses': sum(1 for p in user.predictions if p.status == 'Lost')
            }
        }

    def _promote_user(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'Missing user_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.is_admin = True
        db.session.commit()
        return {'success': True, 'message': f'User {user.username} promoted to admin'}

    def _demote_user(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'Missing user_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        if user.id == 1:
            return {'success': False, 'message': 'Cannot demote the primary admin'}
        user.is_admin = False
        db.session.commit()
        return {'success': True, 'message': f'User {user.username} demoted'}

    def _ban_user(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'Missing user_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.is_active = False
        db.session.commit()
        return {'success': True, 'message': f'User {user.username} banned'}

    def _unban_user(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'Missing user_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.is_active = True
        db.session.commit()
        return {'success': True, 'message': f'User {user.username} unbanned'}

    def _delete_user(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        if not user_id:
            return {'success': False, 'message': 'Missing user_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        if user.id == 1:
            return {'success': False, 'message': 'Cannot delete primary admin'}
        username = user.username
        db.session.delete(user)
        db.session.commit()
        return {'success': True, 'message': f'User {username} deleted'}

    def _user_stats(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        total = User.query.count()
        active = User.query.filter(User.is_active == True).count()
        verified = User.query.filter(User.is_verified == True).count()
        admins = User.query.filter(User.is_admin == True).count()
        premium = User.query.filter(User.is_premium == True).count()
        return {
            'success': True,
            'stats': {
                'total_users': total,
                'active_users': active,
                'verified_users': verified,
                'admins': admins,
                'premium_users': premium
            }
        }

    def _update_subscription(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        tier = args.get('tier')
        if not user_id or not tier:
            return {'success': False, 'message': 'user_id and tier required'}
        if tier not in ['free', 'silver', 'gold', 'platinum']:
            return {'success': False, 'message': 'Invalid tier'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.subscription_tier = tier
        user.is_premium = (tier != 'free')
        db.session.commit()
        return {'success': True, 'message': f'User {user.username} tier updated to {tier}'}

    def _add_credits(self, args: Dict) -> Dict:
        user_id = args.get('user_id')
        amount = args.get('amount')
        if not user_id or amount is None:
            return {'success': False, 'message': 'user_id and amount required'}
        amount = int(amount)
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        user = User.query.get(user_id)
        if not user:
            return {'success': False, 'message': 'User not found'}
        user.credits += amount
        db.session.commit()
        return {'success': True, 'message': f'Added {amount} credits to {user.username}. New balance: {user.credits}'}

    # ----- Prediction management -----
    def _list_predictions(self, args: Dict) -> Dict:
        page = args.get('page', 1)
        per_page = min(args.get('per_page', 50), 100)
        status = args.get('status')
        user_id = args.get('user_id')
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        query = Prediction.query
        if status:
            query = query.filter(Prediction.status == status)
        if user_id:
            query = query.filter(Prediction.user_id == user_id)
        paginated = query.order_by(Prediction.id.desc()).paginate(page=page, per_page=per_page, error_out=False)
        data = [{
            'id': p.id, 'user_id': p.user_id, 'home_team': p.home_team, 'away_team': p.away_team,
            'pred_outcome': p.pred_outcome, 'status': p.status, 'confidence': p.confidence,
            'match_date': p.match_date.isoformat() if p.match_date else None
        } for p in paginated.items]
        return {'success': True, 'predictions': data, 'total': paginated.total, 'page': page, 'per_page': per_page}

    def _delete_prediction(self, args: Dict) -> Dict:
        pred_id = args.get('prediction_id')
        if not pred_id:
            return {'success': False, 'message': 'Missing prediction_id'}
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        pred = Prediction.query.get(pred_id)
        if not pred:
            return {'success': False, 'message': 'Prediction not found'}
        db.session.delete(pred)
        db.session.commit()
        return {'success': True, 'message': f'Prediction {pred_id} deleted'}

    def _force_update_outcomes(self, args: Dict) -> Dict:
        # This would call the existing update_prediction_outcomes_sync from routes
        # For simplicity, we import and call
        try:
            from app.routes import update_prediction_outcomes_sync
            result = update_prediction_outcomes_sync()
            return {'success': True, 'updated': result.get('updated', 0), 'errors': result.get('errors', 0)}
        except ImportError:
            return {'success': False, 'message': 'Could not import update function'}

    def _prediction_stats(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        total = Prediction.query.count()
        pending = Prediction.query.filter_by(status='Pending').count()
        won = Prediction.query.filter_by(status='Won').count()
        lost = Prediction.query.filter_by(status='Lost').count()
        settled = won + lost
        accuracy = (won / settled * 100) if settled > 0 else 0
        return {
            'success': True,
            'stats': {
                'total': total, 'pending': pending, 'won': won, 'lost': lost,
                'accuracy': round(accuracy, 2), 'settled': settled
            }
        }

    def _recalculate_leaderboard(self, args: Dict) -> Dict:
        if HAS_CELERY:
            update_leaderboard_task.delay()
            return {'success': True, 'message': 'Leaderboard recalculation queued'}
        else:
            # Try to call sync version
            try:
                from app.routes import update_leaderboard_sync
                update_leaderboard_sync()
                return {'success': True, 'message': 'Leaderboard recalculated synchronously'}
            except ImportError:
                return {'success': False, 'message': 'Leaderboard update function not available'}

    # ----- Model management -----
    def _list_models(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        ai = current_app.ai_engine if hasattr(current_app, 'ai_engine') else None
        if not ai or not hasattr(ai, 'models'):
            return {'success': False, 'message': 'AI engine not available or no models'}
        models = list(ai.models.keys()) if hasattr(ai.models, 'keys') else []
        return {'success': True, 'models': models, 'total': len(models)}

    def _reload_models(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        ai = current_app.ai_engine
        if not ai or not hasattr(ai, '_load_models'):
            return {'success': False, 'message': 'AI engine does not support reload'}
        try:
            ai._load_models()
            return {'success': True, 'message': 'Models reloaded successfully'}
        except Exception as e:
            return {'success': False, 'message': f'Reload failed: {e}'}

    def _evaluate_models(self, args: Dict) -> Dict:
        # Placeholder: run model evaluation using critic agent or health_checker
        try:
            from monitoring.alert_system import AlertSystem
            alert = AlertSystem()
            alerts = alert.check_model_health()
            return {'success': True, 'alerts': alerts, 'count': len(alerts)}
        except Exception as e:
            return {'success': False, 'message': f'Evaluation failed: {e}'}

    def _retrain_model(self, args: Dict) -> Dict:
        target = args.get('target')
        if not target:
            return {'success': False, 'message': 'Missing target (WLD/BTTS/Over25/TotalGoals)'}
        # This would need to call training pipeline – for now placeholder
        return {'success': False, 'message': 'Retraining not yet implemented via admin agent'}

    def _model_health(self, args: Dict) -> Dict:
        try:
            from monitoring.alert_system import AlertSystem
            alert = AlertSystem()
            alerts = alert.check_model_health()
            return {'success': True, 'health': alerts}
        except ImportError:
            return {'success': False, 'message': 'Monitoring module not available'}

    # ----- System operations -----
    def _health_check(self, args: Dict) -> Dict:
        try:
            from monitoring.health_checker import HealthChecker
            if not HAS_FLASK:
                return {'success': False, 'message': 'Flask context required'}
            checker = HealthChecker(current_app._get_current_object())
            result = checker.run_all_checks()
            return {'success': True, 'health': result}
        except Exception as e:
            return {'success': False, 'message': f'Health check failed: {e}'}

    def _system_status(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        status = {
            'app_name': current_app.config.get('APP_NAME'),
            'environment': current_app.config.get('FLASK_ENV'),
            'debug': current_app.config.get('DEBUG'),
            'database_uri': current_app.config.get('SQLALCHEMY_DATABASE_URI', '').split('?')[0],
            'cache_enabled': current_app.config.get('CACHE_ENABLED'),
            'celery_available': HAS_CELERY,
            'redis_configured': bool(current_app.config.get('REDIS_HOST')),
            'models_loaded': hasattr(current_app, 'ai_engine') and current_app.ai_engine is not None
        }
        return {'success': True, 'status': status}

    def _clear_cache_cmd(self, args: Dict) -> Dict:
        pattern = args.get('pattern', '*')
        self._clear_cache(pattern)
        return {'success': True, 'message': f'Cache cleared (pattern: {pattern})'}

    def _view_logs(self, args: Dict) -> Dict:
        lines = args.get('lines', 50)
        log_file = self.logs_dir / 'app.log'
        if not log_file.exists():
            return {'success': False, 'message': 'Log file not found'}
        with open(log_file, 'r') as f:
            tail = f.readlines()[-lines:]
        return {'success': True, 'logs': ''.join(tail), 'lines': len(tail)}

    def _run_maintenance(self, args: Dict) -> Dict:
        if HAS_CELERY:
            cleanup_old_tasks.delay()
            return {'success': True, 'message': 'Maintenance tasks queued'}
        else:
            # Fallback: call sync cleanup (if defined)
            try:
                from app.routes import cleanup_old_tasks_sync
                cleanup_old_tasks_sync()
                return {'success': True, 'message': 'Maintenance ran synchronously'}
            except ImportError:
                return {'success': False, 'message': 'Maintenance function not available'}

    def _restart_celery(self, args: Dict) -> Dict:
        # This would require external process control – placeholder
        return {'success': False, 'message': 'Restart Celery manually (supervisor/systemctl)'}

    def _export_system_logs(self, args: Dict) -> Dict:
        fmt = args.get('format', 'csv')
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        logs = SystemLog.query.order_by(SystemLog.timestamp.desc()).limit(5000).all()
        data = [{'timestamp': l.timestamp, 'level': l.level, 'module': l.module, 'message': l.message} for l in logs]
        df = pd.DataFrame(data)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        if fmt == 'csv':
            path = self.data_dir / f'logs_export_{timestamp}.csv'
            df.to_csv(path, index=False)
            return {'success': True, 'file': str(path)}
        else:
            return {'success': True, 'data': data.to_dict(orient='records')}

    # ----- Data management -----
    def _export_users(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        users = User.query.all()
        data = [{'id': u.id, 'username': u.username, 'email': u.email, 'subscription_tier': u.subscription_tier,
                 'is_verified': u.is_verified, 'is_active': u.is_active, 'created_at': u.created_at} for u in users]
        df = pd.DataFrame(data)
        path = self.data_dir / f'users_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(path, index=False)
        return {'success': True, 'file': str(path)}

    def _export_predictions(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        predictions = Prediction.query.all()
        data = [{
            'id': p.id, 'user_id': p.user_id, 'home_team': p.home_team, 'away_team': p.away_team,
            'pred_outcome': p.pred_outcome, 'status': p.status, 'confidence': p.confidence,
            'match_date': p.match_date, 'created_at': p.created_at
        } for p in predictions]
        df = pd.DataFrame(data)
        path = self.data_dir / f'predictions_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        df.to_csv(path, index=False)
        return {'success': True, 'file': str(path)}

    def _import_teams(self, args: Dict) -> Dict:
        file_path = args.get('file')
        if not file_path:
            return {'success': False, 'message': 'Missing file path'}
        file_path = Path(file_path)
        if not file_path.exists():
            return {'success': False, 'message': 'File not found'}
        try:
            df = pd.read_csv(file_path)
            required = ['name', 'league']
            for col in required:
                if col not in df.columns:
                    return {'success': False, 'message': f'Missing column: {col}'}
            if not HAS_FLASK:
                return {'success': False, 'message': 'Flask context not available'}
            imported = 0
            for _, row in df.iterrows():
                team = Team.query.filter_by(name=row['name']).first()
                if not team:
                    team = Team(name=row['name'])
                    db.session.add(team)
                # League association can be more complex – placeholder
                imported += 1
            db.session.commit()
            return {'success': True, 'message': f'Imported {imported} teams'}
        except Exception as e:
            return {'success': False, 'message': f'Import failed: {e}'}

    def _validate_csv(self, args: Dict) -> Dict:
        file_path = args.get('file')
        if not file_path:
            return {'success': False, 'message': 'Missing file path'}
        file_path = Path(file_path)
        if not file_path.exists():
            return {'success': False, 'message': 'File not found'}
        try:
            df = pd.read_csv(file_path)
            report = {
                'rows': len(df),
                'columns': list(df.columns),
                'null_counts': df.isnull().sum().to_dict(),
                'sample': df.head(5).to_dict(orient='records')
            }
            return {'success': True, 'report': report}
        except Exception as e:
            return {'success': False, 'message': f'Validation failed: {e}'}

    def _backup_db(self, args: Dict) -> Dict:
        if not HAS_FLASK:
            return {'success': False, 'message': 'Flask context not available'}
        db_uri = current_app.config.get('SQLALCHEMY_DATABASE_URI')
        if 'sqlite' not in db_uri:
            return {'success': False, 'message': 'Only SQLite backups supported via this command'}
        db_path = db_uri.replace('sqlite:///', '')
        if not os.path.isabs(db_path):
            db_path = self.base_dir / db_path
        if not os.path.exists(db_path):
            return {'success': False, 'message': 'Database file not found'}
        backup_dir = self.data_dir / 'backups'
        backup_dir.mkdir(exist_ok=True)
        backup_file = backup_dir / f'db_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.db'
        shutil.copy2(db_path, backup_file)
        return {'success': True, 'backup_file': str(backup_file)}

    # ----- Monitoring & Celery -----
    def _celery_status(self, args: Dict) -> Dict:
        if not HAS_CELERY:
            return {'success': False, 'message': 'Celery not available'}
        try:
            inspect = celery_app.control.inspect()
            workers = inspect.active() or {}
            stats = inspect.stats() or {}
            return {'success': True, 'workers': list(workers.keys()), 'stats': stats}
        except Exception as e:
            return {'success': False, 'message': f'Celery status error: {e}'}

    def _queue_length(self, args: Dict) -> Dict:
        if not HAS_CELERY:
            return {'success': False, 'message': 'Celery not available'}
        try:
            from celery import current_app as celery_app
            i = celery_app.control.inspect()
            active_queues = i.active_queues() or {}
            lengths = {}
            for worker, queues in active_queues.items():
                for q in queues:
                    lengths[q['name']] = lengths.get(q['name'], 0) + 1
            return {'success': True, 'queues': lengths}
        except Exception as e:
            return {'success': False, 'message': f'Queue check error: {e}'}

    def _metrics_summary(self, args: Dict) -> Dict:
        if not HAS_MONITORING or not HAS_FLASK:
            return {'success': False, 'message': 'Monitoring not available'}
        try:
            collector = current_app.metrics_collector
            summary = collector.get_metrics_summary(hours=24)
            return {'success': True, 'summary': summary}
        except Exception as e:
            return {'success': False, 'message': f'Metrics error: {e}'}

    def _active_alerts(self, args: Dict) -> Dict:
        if not HAS_MONITORING or not HAS_FLASK:
            return {'success': False, 'message': 'Alert system not available'}
        try:
            alerts = current_app.alert_manager.get_active_alerts()
            return {'success': True, 'alerts': alerts, 'count': len(alerts)}
        except Exception as e:
            return {'success': False, 'message': f'Alert error: {e}'}

    # ----- MCP server -----
    def _start_mcp(self, args: Dict) -> Dict:
        port = args.get('port', self.config.get('MCP_SERVER_PORT', 8080))
        self.config['MCP_SERVER_PORT'] = port
        self.mcp_server = MCPServer(self, self.config)
        if self.mcp_server.start_server():
            self.mcp_enabled = True
            return {'success': True, 'message': f'MCP server started on port {port}'}
        return {'success': False, 'message': 'Failed to start MCP server'}

    def _stop_mcp(self, args: Dict) -> Dict:
        if self.mcp_server:
            self.mcp_server.stop_server()
            self.mcp_enabled = False
            return {'success': True, 'message': 'MCP server stopped'}
        return {'success': False, 'message': 'MCP server not running'}

    def _mcp_status(self, args: Dict) -> Dict:
        if self.mcp_server:
            info = self.mcp_server.get_server_info() if hasattr(self.mcp_server, 'get_server_info') else {'is_running': self.mcp_server.is_running}
            return {'success': True, 'status': info}
        return {'success': True, 'status': {'is_running': False, 'enabled': self.mcp_enabled}}

    # ----- Help -----
    def _help(self, args: Dict) -> Dict:
        help_text = {}
        for cmd, info in self._command_registry.items():
            help_text[cmd] = info['desc']
        return {'success': True, 'commands': help_text}


# Singleton for easy import
_admin_agent_instance = None

def get_admin_agent(config: Dict = None, cache=None) -> AdminAgent:
    global _admin_agent_instance
    if _admin_agent_instance is None:
        _admin_agent_instance = AdminAgent(config, cache)
    return _admin_agent_instance


if __name__ == "__main__":
    # Quick self-test
    agent = AdminAgent()
    print("Testing admin agent...")
    result = agent.process_command('help')
    print(f"Help: {len(result.get('commands', {}))} commands")
    result = agent.process_command('system_status')
    print(f"System status: {result.get('status', {})}")