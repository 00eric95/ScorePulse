#!/usr/bin/env python3
"""
Database Initialization & Management Script
ScorePulse AI - Football Analytics Platform
Automates database setup, migrations, and management tasks.
"""

import os
import sys
import json
import argparse
import inspect
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum

# ============================================================================
# LOGGING SYSTEM
# ============================================================================

class LogLevel(Enum):
    """Log levels with ANSI color codes"""
    DEBUG = ("🔍", "\033[36m")  # Cyan
    INFO = ("ℹ️ ", "\033[32m")   # Green
    WARNING = ("⚠️ ", "\033[33m") # Yellow
    ERROR = ("❌", "\033[31m")   # Red
    SUCCESS = ("✅", "\033[32m")  # Green
    CRITICAL = ("💥", "\033[41m\033[37m")  # White on Red
    
    def __init__(self, icon: str, color: str):
        self.icon = icon
        self.color = color
        self.reset = "\033[0m"

@dataclass
class LogEntry:
    """Structured log entry"""
    timestamp: datetime
    level: str
    module: str
    function: str
    line: int
    message: str
    data: Optional[Dict] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary"""
        result = asdict(self)
        result['timestamp'] = self.timestamp.isoformat()
        return result
    
    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict(), default=str)

class Logger:
    """Modern, structured logger with file and console output"""
    
    _instance = None
    _log_file = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance
    
    def __init__(self):
        if not self._initialized:
            self.log_level = LogLevel.INFO
            self.log_file_path = None
            self.console_enabled = True
            self.file_enabled = True
            self._log_buffer = []
            self._initialized = True
    
    def setup(self, 
              log_file: str = "logs/database.log",
              level: LogLevel = LogLevel.INFO,
              console: bool = True,
              file: bool = True):
        """Setup logger configuration"""
        self.log_file_path = Path(log_file)
        self.log_level = level
        self.console_enabled = console
        self.file_enabled = file
        
        # Create log directory
        self.log_file_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Create log file if it doesn't exist
        if not self.log_file_path.exists():
            self.log_file_path.touch()
        
        self.info("Logger initialized", {
            "log_file": str(self.log_file_path),
            "level": level.name,
            "console": console,
            "file": file
        })
    
    def _get_caller_info(self) -> Dict[str, Any]:
        """Get information about the calling function"""
        frame = inspect.currentframe()
        # Go back 2 frames: 1 for this method, 1 for the logging method
        for _ in range(3):
            if frame:
                frame = frame.f_back
        
        if frame:
            return {
                "module": frame.f_globals.get('__name__', 'unknown'),
                "function": frame.f_code.co_name,
                "line": frame.f_lineno,
                "file": frame.f_code.co_filename
            }
        return {"module": "unknown", "function": "unknown", "line": 0}
    
    def _write_to_file(self, entry: LogEntry):
        """Write log entry to file"""
        try:
            with open(self.log_file_path, 'a', encoding='utf-8') as f:
                f.write(entry.to_json() + "\n")
        except Exception as e:
            # Fallback to stderr if file writing fails
            print(f"Failed to write to log file: {e}", file=sys.stderr)
    
    def _write_to_console(self, entry: LogEntry):
        """Write log entry to console with colors"""
        level_info = LogLevel[entry.level]
        timestamp = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        
        # Format message
        if entry.data:
            data_str = json.dumps(entry.data, indent=2, default=str)
            message = f"{entry.message}\n{data_str}"
        else:
            message = entry.message
        
        # Create colored output
        colored_output = (
            f"{level_info.color}{level_info.icon} [{timestamp}] "
            f"{entry.level:<8} {entry.module}.{entry.function}:{entry.line} "
            f"- {message}{level_info.reset}"
        )
        
        print(colored_output)
    
    def log(self, level: LogLevel, message: str, data: Optional[Dict] = None):
        """Main logging method"""
        # Check if we should log at this level
        if not self._should_log(level):
            return
        
        # Get caller info
        caller = self._get_caller_info()
        
        # Create log entry
        entry = LogEntry(
            timestamp=datetime.now(),
            level=level.name,
            module=caller["module"],
            function=caller["function"],
            line=caller["line"],
            message=message,
            data=data
        )
        
        # Buffer entry (for potential batch processing)
        self._log_buffer.append(entry)
        
        # Write to outputs
        if self.console_enabled:
            self._write_to_console(entry)
        
        if self.file_enabled:
            self._write_to_file(entry)
        
        # Clear buffer if too large
        if len(self._log_buffer) > 1000:
            self._log_buffer = self._log_buffer[-500:]
    
    def _should_log(self, level: LogLevel) -> bool:
        """Check if we should log at given level"""
        level_order = {
            LogLevel.DEBUG: 0,
            LogLevel.INFO: 1,
            LogLevel.WARNING: 2,
            LogLevel.ERROR: 3,
            LogLevel.CRITICAL: 4,
            LogLevel.SUCCESS: 5
        }
        return level_order[level] >= level_order[self.log_level]
    
    # Convenience methods
    def debug(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.DEBUG, message, data)
    
    def info(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.INFO, message, data)
    
    def warning(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.WARNING, message, data)
    
    def error(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.ERROR, message, data)
    
    def critical(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.CRITICAL, message, data)
    
    def success(self, message: str, data: Optional[Dict] = None):
        self.log(LogLevel.SUCCESS, message, data)
    
    def get_recent_logs(self, count: int = 50) -> List[Dict]:
        """Get recent log entries"""
        recent = self._log_buffer[-count:] if self._log_buffer else []
        return [entry.to_dict() for entry in recent]
    
    def flush(self):
        """Force flush any buffered logs"""
        if self.file_enabled and self._log_buffer:
            try:
                with open(self.log_file_path, 'a', encoding='utf-8') as f:
                    for entry in self._log_buffer:
                        f.write(entry.to_json() + "\n")
                self._log_buffer.clear()
            except Exception as e:
                print(f"Failed to flush logs: {e}", file=sys.stderr)

# Global logger instance
logger = Logger()

# ============================================================================
# DATABASE MANAGEMENT FUNCTIONS
# ============================================================================

def setup_environment() -> Path:
    """Setup Python environment and paths"""
    try:
        # Get project root
        project_root = Path(__file__).parent.parent.absolute()
        sys.path.insert(0, str(project_root))
        os.chdir(project_root)
        
        logger.debug("Environment setup", {
            "project_root": str(project_root),
            "python_path": sys.path,
            "current_dir": os.getcwd()
        })
        
        # Create necessary directories
        directories = [
            'instance',
            'logs',
            'migrations',
            'backups',
            'data/exports',
            'data/imports',
            'data/backups'
        ]
        
        created_dirs = []
        for directory in directories:
            dir_path = Path(directory)
            dir_path.mkdir(parents=True, exist_ok=True)
            created_dirs.append(str(dir_path))
        
        logger.info("Directories verified/created", {"directories": created_dirs})
        
        # Windows encoding fix
        if sys.platform == 'win32':
            import io
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
            sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')
            logger.debug("Applied Windows UTF-8 encoding fix")
        
        return project_root
        
    except Exception as e:
        logger.critical("Failed to setup environment", {"error": str(e)})
        raise

def create_app_instance():
    """Create Flask application instance with proper context"""
    try:
        logger.debug("Creating Flask application instance")
        
        # Try to import from app
        from app import db, create_app
        
        # Create the app instance
        app = create_app()
        
        # Initialize db with the app
        with app.app_context():
            if hasattr(db, 'init_app') and not hasattr(db, 'get_engine'):
                db.init_app(app)
        
        logger.success("Flask application created", {
            "app_name": app.name,
            "debug_mode": app.debug,
            "env": app.config.get('ENV', 'production')
        })
        
        return app, db
        
    except ImportError as e:
        logger.error("Failed to import application modules", {"error": str(e)})
        logger.info("Trying alternative import method")
        
        # Alternative approach
        try:
            import app as app_module
            
            if hasattr(app_module, 'create_app'):
                from app import create_app
                app = create_app()
                
                if hasattr(app_module, 'db'):
                    db = app_module.db
                else:
                    from flask_sqlalchemy import SQLAlchemy
                    db = SQLAlchemy(app)
                
                logger.success("Alternative import successful")
                return app, db
                
        except Exception as e2:
            logger.critical("All import methods failed", {"error": str(e2)})
            sys.exit(1)
            
    except Exception as e:
        logger.critical("Failed to create app instance", {"error": str(e)})
        sys.exit(1)

def check_database_status(db_path: str) -> Dict[str, Any]:
    """Check if database exists and is accessible"""
    try:
        db_path_obj = Path(db_path)
        
        if db_path_obj.exists():
            file_size = db_path_obj.stat().st_size
            modified_time = datetime.fromtimestamp(db_path_obj.stat().st_mtime)
            
            status = {
                "exists": True,
                "path": str(db_path_obj),
                "size_kb": round(file_size / 1024, 2),
                "size_mb": round(file_size / (1024 * 1024), 2),
                "modified": modified_time.isoformat(),
                "age_days": (datetime.now() - modified_time).days
            }
            
            logger.info("Database found", status)
            return status
        else:
            logger.warning("Database file does not exist", {"path": str(db_path_obj)})
            return {"exists": False, "path": str(db_path_obj)}
            
    except Exception as e:
        logger.error("Error checking database status", {"error": str(e)})
        return {"exists": False, "error": str(e)}

def create_database(app, db, reset: bool = False) -> bool:
    """Create or reset database tables"""
    with app.app_context():
        try:
            # Get database configuration
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/scorepulse.db')
            
            # Parse database path
            if db_uri.startswith('sqlite:///'):
                db_path = db_uri.replace('sqlite:///', '')
                if not db_path.startswith('/'):
                    db_path = os.path.join(app.root_path, db_path)
            elif db_uri.startswith('sqlite://'):
                db_path = db_uri.replace('sqlite://', '')
                if not db_path.startswith('/'):
                    db_path = os.path.join(app.root_path, db_path)
            else:
                db_path = db_uri  # For non-SQLite databases
            
            logger.info("Database configuration", {
                "uri": db_uri,
                "path": db_path,
                "reset_requested": reset
            })
            
            # Backup existing database if resetting
            if reset and Path(db_path).exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"data/backups/db_backup_{timestamp}.db"
                
                try:
                    import shutil
                    shutil.copy2(db_path, backup_path)
                    logger.success("Database backup created", {
                        "original": db_path,
                        "backup": backup_path
                    })
                except Exception as e:
                    logger.warning("Could not create backup", {"error": str(e)})
            
            # Create tables
            logger.info("Creating database tables")
            start_time = datetime.now()
            db.create_all()
            elapsed = (datetime.now() - start_time).total_seconds()
            
            # Verify creation
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            # Log table details
            table_details = []
            for table in sorted(tables):
                columns = inspector.get_columns(table)
                table_details.append({
                    "name": table,
                    "columns": len(columns),
                    "column_names": [col['name'] for col in columns[:5]] + 
                                   (["..."] if len(columns) > 5 else [])
                })
            
            logger.success("Database initialized", {
                "location": db_path,
                "tables_created": len(tables),
                "creation_time_seconds": round(elapsed, 2),
                "tables": table_details
            })
            
            # Create initial data if needed
            if app.config.get('CREATE_INITIAL_DATA', False):
                create_initial_data(app, db)
            
            return True
            
        except Exception as e:
            logger.error("Failed to create database", {"error": str(e), "traceback": True})
            return False

def create_initial_data(app, db) -> bool:
    """Create initial data for the application"""
    try:
        logger.info("Creating initial data")
        
        from app.models import User, Team, League, Season
        
        with app.app_context():
            created_items = {}
            
            # Create default admin user
            admin_exists = User.query.filter_by(username='admin').first()
            if not admin_exists and app.config.get('CREATE_ADMIN_USER', True):
                admin = User(
                    username='admin',
                    email='admin@scorepulse.ai',
                    subscription_tier='platinum',
                    email_verified=True,
                    is_active=True
                )
                admin.set_password('Admin@123')  # Strong default password
                db.session.add(admin)
                created_items['admin_user'] = True
                logger.debug("Created admin user")
            
            # Create sample leagues
            if League.query.count() == 0:
                sample_leagues = [
                    League(name='English Premier League', country='England', tier=1, type='Club'),
                    League(name='La Liga', country='Spain', tier=1, type='Club'),
                    League(name='Serie A', country='Italy', tier=1, type='Club'),
                    League(name='Bundesliga', country='Germany', tier=1, type='Club'),
                    League(name='Ligue 1', country='France', tier=1, type='Club'),
                    League(name='UEFA Champions League', country='Europe', tier=1, type='International'),
                ]
                db.session.add_all(sample_leagues)
                created_items['leagues'] = len(sample_leagues)
                logger.debug(f"Created {len(sample_leagues)} sample leagues")
            
            # Create current season
            if Season.query.count() == 0:
                current_year = datetime.now().year
                season = Season(
                    name=f"{current_year}/{current_year + 1}",
                    start_date=datetime(current_year, 8, 1),
                    end_date=datetime(current_year + 1, 5, 31),
                    is_current=True
                )
                db.session.add(season)
                created_items['season'] = True
                logger.debug("Created current season")
            
            db.session.commit()
            
            logger.success("Initial data created", {"items": created_items})
            return True
            
    except ImportError as e:
        logger.warning("Could not create initial data - models not available", {"error": str(e)})
        return False
    except Exception as e:
        logger.error("Failed to create initial data", {"error": str(e)})
        db.session.rollback()
        return False

def run_migrations(app) -> bool:
    """Run database migrations if Alembic is configured"""
    try:
        logger.info("Running database migrations")
        
        with app.app_context():
            from flask_migrate import upgrade, migrate
            
            # Generate migration
            migrate()
            
            # Apply migration
            upgrade()
            
            logger.success("Migrations completed")
            return True
            
    except ImportError:
        logger.info("Alembic migrations not configured")
        return True  # Not an error, just not configured
    except Exception as e:
        logger.error("Migration failed", {"error": str(e)})
        return False

def export_database_schema(db) -> Optional[str]:
    """Export database schema to SQL file"""
    try:
        logger.info("Exporting database schema")
        
        from sqlalchemy.schema import CreateTable, MetaData
        import sqlalchemy as sa
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        export_path = f"data/exports/schema_export_{timestamp}.sql"
        
        metadata = MetaData()
        metadata.reflect(bind=db.engine)
        
        with open(export_path, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"""-- =============================================
-- ScorePulse AI Database Schema Export
-- Generated: {datetime.now().isoformat()}
-- Database: {db.engine.url}
-- Tables: {len(metadata.tables)}
-- =============================================\n\n""")
            
            # Tables
            for table_name in sorted(metadata.tables.keys()):
                table = metadata.tables[table_name]
                f.write(f"-- Table: {table_name}\n")
                f.write(str(CreateTable(table).compile(db.engine)) + ";\n\n")
                
                # Indexes
                if table.indexes:
                    f.write(f"-- Indexes for {table_name}\n")
                    for index in table.indexes:
                        f.write(f"--   {index.name}: {[c.name for c in index.columns]}\n")
                    f.write("\n")
            
            # Relationships summary
            f.write("-- =============================================\n")
            f.write("-- TABLE RELATIONSHIPS SUMMARY\n")
            f.write("-- =============================================\n")
            for table_name in sorted(metadata.tables.keys()):
                table = metadata.tables[table_name]
                if table.foreign_keys:
                    f.write(f"-- {table_name} references:\n")
                    for fk in table.foreign_keys:
                        f.write(f"--   -> {fk.column.table.name}.{fk.column.name}\n")
                    f.write("\n")
        
        logger.success("Database schema exported", {"path": export_path, "tables": len(metadata.tables)})
        return export_path
        
    except Exception as e:
        logger.error("Failed to export schema", {"error": str(e)})
        return None

def check_database_integrity(app, db) -> Dict[str, Any]:
    """Check database integrity and consistency"""
    with app.app_context():
        try:
            logger.info("Running database integrity checks")
            
            from sqlalchemy import text, inspect
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            integrity_results = {
                "total_tables": len(tables),
                "tables_checked": 0,
                "errors": [],
                "warnings": [],
                "table_stats": {}
            }
            
            # Check each table
            for table in tables:
                try:
                    # Count records
                    count = db.session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
                    
                    # Get column info
                    columns = inspector.get_columns(table)
                    
                    integrity_results["table_stats"][table] = {
                        "records": count,
                        "columns": len(columns),
                        "column_names": [col['name'] for col in columns]
                    }
                    
                    integrity_results["tables_checked"] += 1
                    
                    # Check for empty tables (warning only)
                    if count == 0:
                        integrity_results["warnings"].append(f"Table '{table}' is empty")
                    
                except Exception as e:
                    integrity_results["errors"].append(f"Failed to check table '{table}': {str(e)}")
            
            # Check foreign key constraints (SQLite specific)
            if 'sqlite' in str(db.engine.url).lower():
                try:
                    fk_check = db.session.execute(text("PRAGMA foreign_key_check;")).fetchall()
                    if fk_check:
                        for row in fk_check:
                            integrity_results["errors"].append(
                                f"Foreign key violation in '{row[0]}'.{row[1]}: {row[2]}"
                            )
                    else:
                        integrity_results["foreign_key_check"] = "passed"
                except:
                    pass  # Not all databases support this
            
            # Log results
            if integrity_results["errors"]:
                logger.error("Database integrity check failed", integrity_results)
            elif integrity_results["warnings"]:
                logger.warning("Database integrity check completed with warnings", integrity_results)
            else:
                logger.success("Database integrity check passed", integrity_results)
            
            return integrity_results
            
        except Exception as e:
            logger.error("Integrity check failed", {"error": str(e)})
            return {"error": str(e), "tables_checked": 0}

def reset_database_full(app, db, force: bool = False) -> bool:
    """Completely reset the database (drop all tables)"""
    with app.app_context():
        try:
            logger.warning("Initiating database reset")
            
            # Get confirmation
            if not force and sys.stdin.isatty():
                logger.warning("⚠️  THIS WILL DELETE ALL DATA IN THE DATABASE!")
                response = input("Type 'RESET' to confirm: ")
                if response != 'RESET':
                    logger.info("Reset cancelled by user")
                    return False
            
            # Backup first
            db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/scorepulse.db')
            db_path = db_uri.replace('sqlite:///', '')
            
            if Path(db_path).exists():
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                backup_path = f"data/backups/pre_reset_{timestamp}.db"
                import shutil
                shutil.copy2(db_path, backup_path)
                logger.info("Created pre-reset backup", {"backup": backup_path})
            
            # Drop all tables
            logger.info("Dropping all tables")
            db.drop_all()
            
            # Recreate tables
            logger.info("Recreating tables")
            db.create_all()
            
            logger.success("Database reset completed")
            return True
            
        except Exception as e:
            logger.critical("Failed to reset database", {"error": str(e)})
            return False

def generate_database_report(app, db) -> Dict[str, Any]:
    """Generate comprehensive database report"""
    try:
        logger.info("Generating database report")
        
        with app.app_context():
            from sqlalchemy import inspect
            
            inspector = inspect(db.engine)
            tables = inspector.get_table_names()
            
            report = {
                "generated_at": datetime.now().isoformat(),
                "database": {
                    "uri": str(db.engine.url),
                    "dialect": db.engine.dialect.name,
                    "tables_count": len(tables),
                    "tables": []
                },
                "statistics": {
                    "total_records": 0,
                    "largest_table": {"name": "", "records": 0},
                    "smallest_table": {"name": "", "records": 0}
                }
            }
            
            # Analyze each table
            for table in sorted(tables):
                try:
                    # Get record count
                    result = db.session.execute(f"SELECT COUNT(*) FROM {table}")
                    count = result.scalar()
                    
                    # Get column info
                    columns = inspector.get_columns(table)
                    
                    table_info = {
                        "name": table,
                        "records": count,
                        "columns": len(columns),
                        "column_types": {col['name']: str(col['type']) for col in columns}
                    }
                    
                    report["database"]["tables"].append(table_info)
                    report["statistics"]["total_records"] += count
                    
                    # Update largest/smallest
                    if count > report["statistics"]["largest_table"]["records"]:
                        report["statistics"]["largest_table"] = {"name": table, "records": count}
                    
                    if count < report["statistics"]["smallest_table"]["records"] or \
                       report["statistics"]["smallest_table"]["name"] == "":
                        report["statistics"]["smallest_table"] = {"name": table, "records": count}
                        
                except Exception as e:
                    logger.warning(f"Could not analyze table {table}", {"error": str(e)})
            
            # Calculate averages
            if tables:
                report["statistics"]["avg_records_per_table"] = round(
                    report["statistics"]["total_records"] / len(tables), 2
                )
            
            # Save report
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            report_path = f"data/exports/db_report_{timestamp}.json"
            
            with open(report_path, 'w', encoding='utf-8') as f:
                json.dump(report, f, indent=2, default=str)
            
            logger.success("Database report generated", {
                "path": report_path,
                "tables": len(tables),
                "total_records": report["statistics"]["total_records"]
            })
            
            return report
            
    except Exception as e:
        logger.error("Failed to generate database report", {"error": str(e)})
        return {"error": str(e)}

def parse_arguments():
    """Parse command line arguments"""
    parser = argparse.ArgumentParser(
        description='ScorePulse AI Database Management System',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""📊 EXAMPLES:
  %(prog)s                        # Initialize database (safe)
  %(prog)s --reset                # Reset database (drops all tables)
  %(prog)s --seed                 # Create initial data
  %(prog)s --migrate              # Run migrations
  %(prog)s --check                # Check database integrity
  %(prog)s --export               # Export database schema
  %(prog)s --report               # Generate database report
  %(prog)s --all                  # Complete setup (reset, migrate, seed)
  %(prog)s -vv                    # Verbose debug output
        """
    )
    
    # Action arguments
    action_group = parser.add_argument_group('Actions')
    action_group.add_argument('--reset', action='store_true',
                           help='Reset database (drop all tables before creating)')
    action_group.add_argument('--seed', action='store_true',
                           help='Seed database with initial data')
    action_group.add_argument('--migrate', action='store_true',
                           help='Run database migrations')
    action_group.add_argument('--check', action='store_true',
                           help='Check database integrity')
    action_group.add_argument('--export', action='store_true',
                           help='Export database schema to SQL file')
    action_group.add_argument('--report', action='store_true',
                           help='Generate comprehensive database report')
    action_group.add_argument('--all', action='store_true',
                           help='Run complete setup (reset, migrate, seed)')
    
    # Output arguments
    output_group = parser.add_argument_group('Output Control')
    output_group.add_argument('--verbose', '-v', action='count', default=0,
                           help='Verbose output (use -v, -vv, -vvv for more detail)')
    output_group.add_argument('--quiet', '-q', action='store_true',
                           help='Suppress console output (logs still saved to file)')
    output_group.add_argument('--force', '-f', action='store_true',
                           help='Force operations without confirmation')
    output_group.add_argument('--log-file', default='logs/database.log',
                           help='Custom log file path')
    
    return parser.parse_args()

def print_banner():
    """Print application banner"""
    banner = """
    ╔══════════════════════════════════════════════════════════════╗
    ║                    SCOREPULSE AI DATABASE                    ║
    ║                MANAGEMENT & MIGRATION SYSTEM                 ║
    ╚══════════════════════════════════════════════════════════════╝
    """
    print(banner)

def main():
    """Main execution function"""
    print_banner()
    
    # Parse arguments
    args = parse_arguments()
    
    # Setup logging based on verbosity
    if args.verbose == 0:
        log_level = LogLevel.INFO
    elif args.verbose == 1:
        log_level = LogLevel.INFO
    elif args.verbose == 2:
        log_level = LogLevel.DEBUG
    else:
        log_level = LogLevel.DEBUG
    
    # Setup logger
    logger.setup(
        log_file=args.log_file,
        level=log_level,
        console=not args.quiet,
        file=True
    )
    
    logger.info("Starting database management system", {
        "arguments": vars(args),
        "python_version": sys.version,
        "platform": sys.platform
    })
    
    # Setup environment
    project_root = setup_environment()
    
    # Create app instance
    app, db = create_app_instance()
    
    with app.app_context():
        # Determine database path
        db_uri = app.config.get('SQLALCHEMY_DATABASE_URI', 'sqlite:///instance/scorepulse.db')
        db_path = db_uri.replace('sqlite:///', '')
        
        # Check database status
        db_status = check_database_status(db_path)
        
        # Determine if we need to reset
        should_reset = args.reset or args.all
        
        if should_reset and db_status.get('exists', False):
            logger.warning("Database exists and reset requested", db_status)
            if not args.force and sys.stdin.isatty():
                response = input("Reset will delete all data. Type 'YES' to continue: ")
                if response != 'YES':
                    logger.info("Reset cancelled by user")
                    should_reset = False
        
        # Execute requested operations
        results = {
            "database_creation": None,
            "migrations": None,
            "integrity_check": None,
            "schema_export": None,
            "report": None,
            "initial_data": None
        }
        
        # Create/reset database
        if should_reset or not db_status.get('exists', False):
            results["database_creation"] = create_database(app, db, reset=should_reset)
        
        # Run migrations
        if args.migrate or args.all:
            results["migrations"] = run_migrations(app)
        
        # Check integrity
        if args.check:
            results["integrity_check"] = check_database_integrity(app, db)
        
        # Export schema
        if args.export:
            results["schema_export"] = export_database_schema(db)
        
        # Generate report
        if args.report:
            results["report"] = generate_database_report(app, db)
        
        # Seed initial data
        if args.seed or args.all:
            results["initial_data"] = create_initial_data(app, db)
        
        # Flush logs
        logger.flush()
        
        # Summary
        print("\n" + "="*70)
        print("📋 DATABASE OPERATIONS SUMMARY")
        print("="*70)
        
        for operation, result in results.items():
            if result is not None:
                status = "✅ SUCCESS" if result not in [False, None] else "❌ FAILED"
                print(f"  {operation.replace('_', ' ').title():<20} {status}")
        
        print("="*70)
        
        # Final status
        if all(r for r in results.values() if r is not None):
            print("\n🎉 All operations completed successfully!")
            print(f"📁 Database: {db_path}")
            print(f"📊 Logs: {args.log_file}")
            print(f"🚀 Next: Run 'python run.py' to start the application")
        else:
            print("\n⚠️  Some operations may have failed. Check the logs for details.")
        
        return 0 if all(r for r in results.values() if r is not None) else 1

if __name__ == "__main__":
    try:
        exit_code = main()
        sys.exit(exit_code)
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        sys.exit(130)
    except Exception as e:
        logger.critical("Unhandled exception", {"error": str(e), "traceback": True})
        sys.exit(1)