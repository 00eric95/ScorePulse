"""
Admin Chatbot - AI Assistant for ScorePulse AI Administration with MCP Server
"""

import os
import sys
import json
import logging
import subprocess
import threading
import time
import socket
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Callable
import pandas as pd
import numpy as np

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MCPServer:
    """Simple MCP (Model Context Protocol) Server for Chatbot Integration"""
    
    def __init__(self, chatbot_instance, host: str = 'localhost', port: int = 8000):
        """Initialize MCP server"""
        self.chatbot = chatbot_instance
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.is_running = False
        self.connections = []
        self.server_lock = threading.Lock()
        
        # MCP protocol version
        self.protocol_version = "2024-11-30"
        
        # Available tools/commands
        self.available_tools = [
            "analyze_codebase",
            "check_file", 
            "ml_status",
            "add_note",
            "get_notes",
            "track_csv",
            "get_csv_tracker",
            "analyze_error",
            "project_structure",
            "system_status",
            "help"
        ]
        
        
        logger.info(f"MCP Server initialized (host: {host}, port: {port})")
        
        self.predictor = None  # Placeholder for Orchestrator injection
        
    def set_predictor(self, predictor):
        """This is called by the Pitch Commander during register_agent"""
        self.predictor = predictor   
    
    def start_server(self) -> bool:
        """Start the MCP server in a separate thread"""
        if self.is_running:
            logger.warning("MCP server is already running")
            return False
        
        try:
            import http.server
            import socketserver
            
            class MCPRequestHandler(http.server.BaseHTTPRequestHandler):
                """Custom HTTP handler for MCP requests"""
                
                def do_GET(self):
                    """Handle GET requests"""
                    if self.path == '/status':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        
                        status_info = {
                            'status': 'running',
                            'protocol_version': self.server.mcp_server.protocol_version,
                            'available_tools': self.server.mcp_server.available_tools,
                            'chatbot': 'AdminChatbot',
                            'timestamp': datetime.now().isoformat()
                        }
                        self.wfile.write(json.dumps(status_info).encode('utf-8'))
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def do_POST(self):
                    """Handle POST requests for command execution"""
                    if self.path == '/execute':
                        content_length = int(self.headers['Content-Length'])
                        post_data = self.rfile.read(content_length)
                        
                        try:
                            request_data = json.loads(post_data.decode('utf-8'))
                            command = request_data.get('command', '')
                            args = request_data.get('args', {})
                            
                            # Execute command through chatbot
                            response = self.server.mcp_server.chatbot.process_command(command, args)
                            
                            self.send_response(200)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            self.wfile.write(json.dumps(response).encode('utf-8'))
                            
                        except Exception as e:
                            self.send_response(500)
                            self.send_header('Content-Type', 'application/json')
                            self.end_headers()
                            error_response = {
                                'error': str(e),
                                'command': command if 'command' in locals() else 'unknown'
                            }
                            self.wfile.write(json.dumps(error_response).encode('utf-8'))
                    
                    elif self.path == '/health':
                        self.send_response(200)
                        self.send_header('Content-Type', 'application/json')
                        self.end_headers()
                        health_status = {
                            'status': 'healthy',
                            'timestamp': datetime.now().isoformat(),
                            'chatbot_status': 'connected'
                        }
                        self.wfile.write(json.dumps(health_status).encode('utf-8'))
                    
                    else:
                        self.send_response(404)
                        self.end_headers()
                
                def log_message(self, format, *args):
                    """Override to use our logger"""
                    logger.info(f"MCP Server: {format % args}")
            
            # Create custom handler with reference to MCP server
            handler = MCPRequestHandler
            
            # Create server
            self.server = socketserver.TCPServer((self.host, self.port), handler)
            self.server.mcp_server = self  # Pass reference to handler
            
            # Start server in background thread
            def run_server():
                try:
                    with self.server_lock:
                        self.is_running = True
                    logger.info(f"MCP Server started on {self.host}:{self.port}")
                    self.server.serve_forever()
                except Exception as e:
                    logger.error(f"MCP Server error: {e}")
                finally:
                    with self.server_lock:
                        self.is_running = False
                    logger.info("MCP Server stopped")
            
            self.server_thread = threading.Thread(target=run_server, daemon=True)
            self.server_thread.start()
            
            # Wait a moment for server to start
            time.sleep(0.5)
            
            # Verify server is running
            if self.check_server_health():
                logger.info("MCP Server started successfully")
                return True
            else:
                logger.error("MCP Server failed to start")
                return False
                
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def stop_server(self) -> bool:
        """Stop the MCP server"""
        if not self.is_running or self.server is None:
            logger.warning("MCP server is not running")
            return False
        
        try:
            self.server.shutdown()
            self.server.server_close()
            
            with self.server_lock:
                self.is_running = False
            
            logger.info("MCP Server stopped successfully")
            return True
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
            return False
    
    def check_server_health(self) -> bool:
        """Check if server is healthy and responding"""
        try:
            import requests
            
            response = requests.get(f"http://{self.host}:{self.port}/health", timeout=2)
            return response.status_code == 200
        except:
            return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get MCP server information"""
        return {
            'is_running': self.is_running,
            'host': self.host,
            'port': self.port,
            'protocol_version': self.protocol_version,
            'available_tools': self.available_tools,
            'health': self.check_server_health() if self.is_running else False
        }
    
    def execute_remote_command(self, command: str, args: Dict = None) -> Dict[str, Any]:
        """Execute a command via the MCP server (self-call)"""
        args = args or {}
        
        if not self.is_running:
            return {
                'success': False,
                'error': 'MCP server not running',
                'command': command
            }
        
        try:
            import requests
            
            payload = {
                'command': command,
                'args': args
            }
            
            response = requests.post(
                f"http://{self.host}:{self.port}/execute",
                json=payload,
                timeout=10
            )
            
            return response.json()
        except Exception as e:
            return {
                'success': False,
                'error': str(e),
                'command': command
            }


class AdminChatbot:
    """AI-powered admin assistant for ScorePulse AI with MCP Server capabilities"""
    
    def __init__(self, app_root: str = None):
        """Initialize the admin chatbot"""
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.dirname(self.app_root)
        self.log_file = os.path.join(self.app_root, 'logs', 'admin_chat.log')
        
        # Ensure logs directory exists
        os.makedirs(os.path.join(self.app_root, 'logs'), exist_ok=True)
        
        # Knowledge base about the application
        self.knowledge_base = self._build_knowledge_base()
        self.notes_file = os.path.join(self.app_root, 'data', 'admin_notes.json')
        self.csv_tracker_file = os.path.join(self.app_root, 'data', 'csv_tracker.json')
        
        # Ensure data directory exists
        os.makedirs(os.path.join(self.app_root, 'data'), exist_ok=True)
        
        # MCP Server instance (not started by default)
        self.mcp_server = None
        self.mcp_enabled = False
        
        logger.info(f"Admin Chatbot initialized for project: {self.project_root}")
    
    def _build_knowledge_base(self) -> Dict[str, Any]:
        """Build knowledge base about the application structure"""
        return {
            'app_structure': {
                'routes': 'app/routes.py - All Flask route definitions',
                'models': 'app/models.py - Database models (User, Prediction, etc.)',
                'forms': 'app/forms.py - Flask-WTF forms',
                'templates': 'app/templates/ - HTML templates',
                'static': 'app/static/ - CSS, JS, images',
                'admin_chatbot': 'app/admin_chatbot.py - This chatbot',
                'config': 'config.py - Application configuration',
                'run': 'run.py - Application entry point'
            },
            'ml_pipeline': {
                'main_ml': 'main.py - Main ML engine (MatchPredictor)',
                'scripts': 'scripts/ - Additional ML scripts',
                'data': 'data/ - Training data and CSVs',
                'models': 'models/ - Trained ML models'
            },
            'common_issues': {
                'database_errors': 'Check app/__init__.py db initialization',
                'route_errors': 'Check Flask route definitions and templates',
                'import_errors': 'Check sys.path and relative imports',
                'template_errors': 'Check template inheritance and variable passing',
                'form_errors': 'Check form validation and field names'
            },
            'dependencies': {
                'flask': 'Web framework',
                'sqlalchemy': 'ORM for database',
                'flask_login': 'User authentication',
                'flask_mail': 'Email sending',
                'flask_socketio': 'WebSocket support',
                'pandas': 'Data manipulation',
                'numpy': 'Numerical computing',
                'scikit-learn': 'Machine learning',
                'werkzeug': 'WSGI utilities'
            },
            'mcp_server': {
                'description': 'Model Context Protocol Server for external integration',
                'commands': 'start_mcp_server, stop_mcp_server, mcp_status',
                'default_port': 8000,
                'protocol': 'HTTP/REST'
            }
        }
    
    def start_mcp_server(self, port: int = 8000) -> Dict[str, Any]:
        """Start the MCP server"""
        response = {
            'command': 'start_mcp_server',
            'success': False,
            'message': '',
            'data': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if self.mcp_server and self.mcp_server.is_running:
                response['message'] = 'MCP server is already running'
                response['data'] = self.mcp_server.get_server_info()
                return response
            
            # Create and start MCP server
            self.mcp_server = MCPServer(self, port=port)
            success = self.mcp_server.start_server()
            
            if success:
                self.mcp_enabled = True
                response['success'] = True
                response['message'] = f'MCP server started on port {port}'
                response['data'] = self.mcp_server.get_server_info()
                
                # Add note about server start
                self.add_note(f"MCP server started on port {port}", category='system')
            else:
                response['message'] = 'Failed to start MCP server'
                
        except Exception as e:
            response['message'] = f'Error starting MCP server: {str(e)}'
            logger.error(f"MCP server start error: {e}")
        
        return response
    
    def stop_mcp_server(self) -> Dict[str, Any]:
        """Stop the MCP server"""
        response = {
            'command': 'stop_mcp_server',
            'success': False,
            'message': '',
            'data': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if not self.mcp_server or not self.mcp_server.is_running:
                response['message'] = 'MCP server is not running'
                response['success'] = True  # Consider this success since desired state achieved
                return response
            
            success = self.mcp_server.stop_server()
            
            if success:
                self.mcp_enabled = False
                response['success'] = True
                response['message'] = 'MCP server stopped successfully'
                response['data'] = {'was_running': True}
                
                # Add note about server stop
                self.add_note("MCP server stopped", category='system')
            else:
                response['message'] = 'Failed to stop MCP server'
                
        except Exception as e:
            response['message'] = f'Error stopping MCP server: {str(e)}'
            logger.error(f"MCP server stop error: {e}")
        
        return response
    
    def get_mcp_status(self) -> Dict[str, Any]:
        """Get MCP server status"""
        response = {
            'command': 'mcp_status',
            'success': True,
            'message': '',
            'data': None,
            'timestamp': datetime.now().isoformat()
        }
        
        if self.mcp_server:
            response['data'] = self.mcp_server.get_server_info()
            response['message'] = 'MCP server is running' if self.mcp_server.is_running else 'MCP server is not running'
        else:
            response['data'] = {
                'is_running': False,
                'mcp_server': 'not_initialized',
                'mcp_enabled': self.mcp_enabled
            }
            response['message'] = 'MCP server not initialized'
        
        return response
    
    def analyze_codebase(self) -> Dict[str, Any]:
        """Analyze the codebase structure and health"""
        analysis = {
            'timestamp': datetime.now().isoformat(),
            'files_found': {},
            'issues': [],
            'warnings': [],
            'recommendations': [],
            'mcp_status': self.mcp_enabled
        }
        
        # Check app structure
        app_dirs = ['app', 'templates', 'static', 'scripts', 'data', 'models']
        for dir_name in app_dirs:
            dir_path = os.path.join(self.project_root, dir_name)
            if os.path.exists(dir_path):
                if dir_name == 'app':
                    # Count Python files in app
                    py_files = [f for f in os.listdir(dir_path) if f.endswith('.py')]
                    analysis['files_found'][dir_name] = {
                        'exists': True,
                        'files': len(py_files),
                        'file_list': py_files[:10]  # First 10 files
                    }
                else:
                    analysis['files_found'][dir_name] = {
                        'exists': True,
                        'files': len(os.listdir(dir_path))
                    }
            else:
                analysis['files_found'][dir_name] = {'exists': False}
                if dir_name in ['app', 'templates']:
                    analysis['issues'].append(f"Missing directory: {dir_name}")
        
        # Check for common issues
        self._check_for_issues(analysis)
        
        return analysis
    
    def _check_for_issues(self, analysis: Dict[str, Any]):
        """Check for common issues in the codebase"""
        # Check for routes.py
        routes_path = os.path.join(self.project_root, 'app', 'routes.py')
        if os.path.exists(routes_path):
            with open(routes_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if '@app.route' not in content:
                    analysis['issues'].append("No Flask routes found in routes.py")
                if 'current_user' in content and 'flask_login' not in content:
                    analysis['warnings'].append("Flask-Login imports might be missing")
        
        # Check for models.py
        models_path = os.path.join(self.project_root, 'app', 'models.py')
        if os.path.exists(models_path):
            with open(models_path, 'r', encoding='utf-8') as f:
                content = f.read()
                if 'db.Column' not in content:
                    analysis['issues'].append("No SQLAlchemy models found in models.py")
        
        # Check for main ML engine
        main_ml_path = os.path.join(self.project_root, 'main.py')
        if not os.path.exists(main_ml_path):
            analysis['warnings'].append("Main ML engine (main.py) not found")
        
        # Check for required CSV files
        data_dir = os.path.join(self.project_root, 'data')
        if os.path.exists(data_dir):
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            if not csv_files:
                analysis['warnings'].append("No CSV data files found in data/ directory")
            else:
                analysis['files_found']['csv_files'] = csv_files
    
    def check_file_for_errors(self, file_path: str) -> Dict[str, Any]:
        """Check a specific file for errors"""
        result = {
            'file': file_path,
            'exists': False,
            'errors': [],
            'warnings': [],
            'line_count': 0,
            'imports': []
        }
        
        if not os.path.exists(file_path):
            result['errors'].append(f"File does not exist: {file_path}")
            return result
        
        result['exists'] = True
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                result['line_count'] = len(lines)
                
                # Basic syntax and error checking
                for i, line in enumerate(lines, 1):
                    line = line.strip()
                    
                    # Check for common issues
                    if 'import' in line:
                        result['imports'].append(line)
                    
                    # Check for potential errors (simple checks)
                    if 'except:' in line and 'except Exception:' not in line:
                        result['warnings'].append(f"Line {i}: Bare except clause")
                    
                    if 'print(' in line and 'logging' not in line:
                        result['warnings'].append(f"Line {i}: Consider using logger instead of print")
                    
                    # Check for syntax issues in Python files
                    if file_path.endswith('.py'):
                        if 'db.Column' in line and 'nullable' not in line:
                            result['warnings'].append(f"Line {i}: Database column missing nullable parameter")
                        
                        if '@app.route' in line and 'methods' not in lines[i] if i < len(lines) else True:
                            # Check next line for methods
                            result['warnings'].append(f"Line {i}: Route might be missing HTTP methods")
        
        except Exception as e:
            result['errors'].append(f"Error reading file: {str(e)}")
        
        return result
    
    def analyze_ml_pipeline(self) -> Dict[str, Any]:
        """Analyze the ML pipeline status"""
        pipeline_status = {
            'timestamp': datetime.now().isoformat(),
            'components': {},
            'status': 'unknown',
            'issues': [],
            'data_sources': [],
            'mcp_available': self.mcp_enabled
        }
        
        # Check ML components
        ml_files = ['main.py', 'scripts/insights_generator.py', 'scripts/value_bet_finder.py']
        
        for ml_file in ml_files:
            file_path = os.path.join(self.project_root, ml_file)
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    pipeline_status['components'][ml_file] = {
                        'exists': True,
                        'size': os.path.getsize(file_path),
                        'has_class_definitions': 'class ' in content
                    }
            else:
                pipeline_status['components'][ml_file] = {'exists': False}
                pipeline_status['issues'].append(f"Missing ML component: {ml_file}")
        
        # Check for data files
        data_dir = os.path.join(self.project_root, 'data')
        if os.path.exists(data_dir):
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')]
            pipeline_status['data_sources'] = csv_files
            
            # Check CSV contents
            for csv_file in csv_files[:3]:  # Check first 3 CSVs
                csv_path = os.path.join(data_dir, csv_file)
                try:
                    df = pd.read_csv(csv_path, nrows=5)  # Read first 5 rows
                    pipeline_status['components'][f'data/{csv_file}'] = {
                        'rows': len(pd.read_csv(csv_path)) if os.path.getsize(csv_path) < 1000000 else 'large',
                        'columns': list(df.columns),
                        'sample': df.head(2).to_dict('records')
                    }
                except Exception as e:
                    pipeline_status['issues'].append(f"Error reading {csv_file}: {str(e)}")
        
        # Determine overall status
        if pipeline_status['issues']:
            pipeline_status['status'] = 'needs_attention'
        elif all(comp.get('exists', False) for comp in pipeline_status['components'].values()):
            pipeline_status['status'] = 'healthy'
        else:
            pipeline_status['status'] = 'partial'
        
        return pipeline_status
    
    def add_note(self, note: str, category: str = 'general') -> bool:
        """Add a note to the admin notes"""
        try:
            notes = self.get_notes()
            notes.append({
                'timestamp': datetime.now().isoformat(),
                'note': note,
                'category': category
            })
            
            with open(self.notes_file, 'w') as f:
                json.dump(notes, f, indent=2)
            
            self._log_action(f"Added note: {note[:50]}...")
            return True
        except Exception as e:
            logger.error(f"Error adding note: {e}")
            return False
    
    def get_notes(self) -> List[Dict[str, Any]]:
        """Get all admin notes"""
        try:
            if os.path.exists(self.notes_file):
                with open(self.notes_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return []
    
    def track_csv_file(self, filename: str, description: str, status: str = 'pending') -> bool:
        """Track a CSV file that needs to be processed"""
        try:
            tracker = self.get_csv_tracker()
            tracker[filename] = {
                'description': description,
                'status': status,
                'added': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.csv_tracker_file, 'w') as f:
                json.dump(tracker, f, indent=2)
            
            self._log_action(f"Tracked CSV: {filename}")
            return True
        except Exception as e:
            logger.error(f"Error tracking CSV: {e}")
            return False
    
    def get_csv_tracker(self) -> Dict[str, Any]:
        """Get CSV file tracker"""
        try:
            if os.path.exists(self.csv_tracker_file):
                with open(self.csv_tracker_file, 'r') as f:
                    return json.load(f)
        except:
            pass
        return {}
    
    def update_csv_status(self, filename: str, status: str, notes: str = '') -> bool:
        """Update CSV file status"""
        try:
            tracker = self.get_csv_tracker()
            if filename in tracker:
                tracker[filename]['status'] = status
                tracker[filename]['last_updated'] = datetime.now().isoformat()
                if notes:
                    tracker[filename]['notes'] = notes
                
                with open(self.csv_tracker_file, 'w') as f:
                    json.dump(tracker, f, indent=2)
                
                self._log_action(f"Updated CSV {filename} to status: {status}")
                return True
        except Exception as e:
            logger.error(f"Error updating CSV status: {e}")
        return False
    
    def analyze_error(self, error_message: str, context: str = '') -> Dict[str, Any]:
        """Analyze an error message and suggest fixes"""
        analysis = {
            'error_type': 'unknown',
            'likely_cause': '',
            'suggested_fixes': [],
            'relevant_files': [],
            'mcp_help': 'Use analyze_error command via MCP if server is running'
        }
        
        error_lower = error_message.lower()
        
        # Common error patterns
        if 'builderror' in error_lower or 'url_for' in error_lower:
            analysis['error_type'] = 'route_error'
            analysis['likely_cause'] = 'Missing Flask route or incorrect endpoint name'
            analysis['suggested_fixes'] = [
                'Check if the route exists in routes.py',
                'Verify the endpoint name matches the function name',
                'Check for typos in url_for() calls'
            ]
            analysis['relevant_files'] = ['app/routes.py', 'app/templates/base.html']
        
        elif 'import' in error_lower and 'no module' in error_lower:
            analysis['error_type'] = 'import_error'
            analysis['likely_cause'] = 'Missing dependency or incorrect import path'
            analysis['suggested_fixes'] = [
                'Check if the module is installed (pip install)',
                'Verify import statements in the file',
                'Check sys.path or Python path configuration'
            ]
        
        elif 'attributeerror' in error_lower and "'nonetype'" in error_lower:
            analysis['error_type'] = 'null_reference'
            analysis['likely_cause'] = 'Accessing attribute/method on None object'
            analysis['suggested_fixes'] = [
                'Add null checks before accessing attributes',
                'Check database queries return results',
                'Verify object initialization'
            ]
        
        elif 'operationalerror' in error_lower or 'sqlite' in error_lower:
            analysis['error_type'] = 'database_error'
            analysis['likely_cause'] = 'Database connection or query issue'
            analysis['suggested_fixes'] = [
                'Check database file exists and is accessible',
                'Verify database schema matches models',
                'Check SQLAlchemy configuration'
            ]
            analysis['relevant_files'] = ['app/__init__.py', 'app/models.py']
        
        elif 'jinja2' in error_lower or 'template' in error_lower:
            analysis['error_type'] = 'template_error'
            analysis['likely_cause'] = 'Template rendering issue'
            analysis['suggested_fixes'] = [
                'Check template file exists',
                'Verify variable names match between route and template',
                'Check for syntax errors in template'
            ]
        
        # Add context-specific suggestions
        if context:
            analysis['context'] = context
        
        return analysis
    
    def get_project_structure(self, depth: int = 2) -> Dict[str, Any]:
        """Get project structure tree"""
        def build_tree(path: str, current_depth: int = 0) -> Dict:
            if current_depth > depth:
                return {}
            
            name = os.path.basename(path)
            result = {'name': name, 'type': 'directory' if os.path.isdir(path) else 'file'}
            
            if os.path.isdir(path):
                result['children'] = []
                try:
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        # Skip hidden files and some directories
                        if not item.startswith('.') and item not in ['__pycache__', 'node_modules', '.git']:
                            child = build_tree(item_path, current_depth + 1)
                            if child:  # Only add if we got something back
                                result['children'].append(child)
                except PermissionError:
                    pass
            
            elif os.path.isfile(path):
                result['size'] = os.path.getsize(path)
                result['extension'] = os.path.splitext(name)[1]
            
            return result
        
        return build_tree(self.project_root)
    
    def _log_action(self, message: str):
        """Log an action to the chat log"""
        try:
            log_entry = {
                'timestamp': datetime.now().isoformat(),
                'message': message,
                'mcp_enabled': self.mcp_enabled
            }
            
            with open(self.log_file, 'a') as f:
                f.write(json.dumps(log_entry) + '\n')
        except Exception as e:
            logger.error(f"Error logging action: {e}")
    
    def get_system_status(self) -> Dict[str, Any]:
        """Get overall system status"""
        status = {
            'timestamp': datetime.now().isoformat(),
            'app': self.analyze_codebase(),
            'ml_pipeline': self.analyze_ml_pipeline(),
            'notes_count': len(self.get_notes()),
            'csv_tracker_count': len(self.get_csv_tracker()),
            'disk_usage': self._get_disk_usage(),
            'mcp_server': self.get_mcp_status()['data'] if hasattr(self, 'mcp_server') else {'is_running': False},
            'recommendations': []
        }
        
        # Generate recommendations
        if status['app']['issues']:
            status['recommendations'].append("Fix application issues from analysis")
        
        if status['ml_pipeline']['status'] != 'healthy':
            status['recommendations'].append("Check ML pipeline components")
        
        notes = self.get_notes()
        if notes:
            pending_notes = [n for n in notes if n.get('category') == 'todo']
            if pending_notes:
                status['recommendations'].append(f"Address {len(pending_notes)} pending notes")
        
        # MCP recommendation
        if not status['mcp_server'].get('is_running', False):
            status['recommendations'].append("Consider starting MCP server for external integration")
        
        return status
    
    def _get_disk_usage(self) -> Dict[str, Any]:
        """Get disk usage information"""
        try:
            # This is a simple implementation
            # For more detailed disk usage, you might need platform-specific code
            import shutil
            
            total, used, free = shutil.disk_usage(self.project_root)
            return {
                'total_gb': round(total / (1024**3), 2),
                'used_gb': round(used / (1024**3), 2),
                'free_gb': round(free / (1024**3), 2),
                'percent_used': round((used / total) * 100, 2)
            }
        except:
            return {'error': 'Could not get disk usage'}
    
    def process_command(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a chatbot command"""
        args = args or {}
        command = command.lower().strip()
        
        response = {
            'command': command,
            'success': False,
            'message': '',
            'data': None,
            'timestamp': datetime.now().isoformat()
        }
        
        try:
            if command == 'analyze_codebase':
                response['data'] = self.analyze_codebase()
                response['message'] = 'Codebase analysis completed'
                response['success'] = True
            
            elif command == 'check_file':
                file_path = args.get('file_path')
                if file_path:
                    # Convert relative path to absolute
                    if not os.path.isabs(file_path):
                        file_path = os.path.join(self.project_root, file_path)
                    response['data'] = self.check_file_for_errors(file_path)
                    response['message'] = f'File check completed for {file_path}'
                    response['success'] = True
                else:
                    response['message'] = 'Missing file_path parameter'
            
            elif command == 'ml_status':
                response['data'] = self.analyze_ml_pipeline()
                response['message'] = 'ML pipeline analysis completed'
                response['success'] = True
            
            elif command == 'add_note':
                note = args.get('note')
                category = args.get('category', 'general')
                if note:
                    success = self.add_note(note, category)
                    response['success'] = success
                    response['message'] = 'Note added successfully' if success else 'Failed to add note'
                else:
                    response['message'] = 'Missing note parameter'
            
            elif command == 'get_notes':
                response['data'] = self.get_notes()
                response['message'] = f'Retrieved {len(response["data"])} notes'
                response['success'] = True
            
            elif command == 'track_csv':
                filename = args.get('filename')
                description = args.get('description', '')
                if filename:
                    success = self.track_csv_file(filename, description)
                    response['success'] = success
                    response['message'] = 'CSV tracking added' if success else 'Failed to track CSV'
                else:
                    response['message'] = 'Missing filename parameter'
            
            elif command == 'get_csv_tracker':
                response['data'] = self.get_csv_tracker()
                response['message'] = f'Retrieved {len(response["data"])} CSV tracking entries'
                response['success'] = True
            
            elif command == 'analyze_error':
                error = args.get('error')
                context = args.get('context', '')
                if error:
                    response['data'] = self.analyze_error(error, context)
                    response['message'] = 'Error analysis completed'
                    response['success'] = True
                else:
                    response['message'] = 'Missing error parameter'
            
            elif command == 'project_structure':
                depth = args.get('depth', 2)
                response['data'] = self.get_project_structure(depth)
                response['message'] = 'Project structure retrieved'
                response['success'] = True
            
            elif command == 'system_status':
                response['data'] = self.get_system_status()
                response['message'] = 'System status report generated'
                response['success'] = True
            
            # MCP Server Commands
            elif command == 'start_mcp_server':
                port = args.get('port', 8000)
                return self.start_mcp_server(port)
            
            elif command == 'stop_mcp_server':
                return self.stop_mcp_server()
            
            elif command == 'mcp_status':
                return self.get_mcp_status()
            
            elif command == 'help':
                response['data'] = {
                    'available_commands': [
                        'analyze_codebase - Analyze the entire codebase',
                        'check_file - Check a specific file for errors',
                        'ml_status - Check ML pipeline status',
                        'add_note - Add an admin note',
                        'get_notes - Get all admin notes',
                        'track_csv - Track a CSV file',
                        'get_csv_tracker - Get CSV tracking list',
                        'analyze_error - Analyze an error message',
                        'project_structure - Get project structure',
                        'system_status - Get overall system status',
                        'start_mcp_server - Start MCP server for external access',
                        'stop_mcp_server - Stop MCP server',
                        'mcp_status - Check MCP server status',
                        'help - Show this help message'
                    ],
                    'mcp_server': {
                        'description': 'Model Context Protocol server for external tool integration',
                        'default_port': 8000,
                        'endpoints': ['/status', '/execute', '/health']
                    }
                }
                response['message'] = 'Available commands (including MCP server commands)'
                response['success'] = True
            
            else:
                response['message'] = f'Unknown command: {command}. Type "help" for available commands.'
        
        except Exception as e:
            response['message'] = f'Error processing command: {str(e)}'
            logger.error(f"Command processing error: {e}")
        
        return response


# Example usage
if __name__ == "__main__":
    chatbot = AdminChatbot()
    
    # Test basic commands
    print("Testing Admin Chatbot...")
    
    # Get system status
    result = chatbot.process_command('system_status')
    print(f"System Status: {result['success']}")
    
    # Start MCP server
    result = chatbot.process_command('start_mcp_server', {'port': 8000})
    print(f"Start MCP Server: {result['message']}")
    
    # Check MCP status
    result = chatbot.process_command('mcp_status')
    print(f"MCP Status: {result['data']}")
    
    # Get help
    result = chatbot.process_command('help')
    print(f"Help available: {len(result['data']['available_commands'])} commands")