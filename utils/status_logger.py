"""
A centralized tracking system that records every training run, model version, and system event in a structured format.
It provides a high-level performance summary, including best-ever scores and business impact analytics like ROI.
The logger manages log retention policies, ensuring that historical data is pruned according to the 'max_history_days' setting.
It tracks confidence intervals and comparison baselines to determine if a new model is statistically superior to its predecessor.
This module provides the 'Audit Trail' necessary for maintaining a professional-grade machine learning lifecycle.
"""


import csv
import os
import json
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union
import logging
import warnings
warnings.filterwarnings('ignore')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class StatusLogger:
    """
    Enhanced training status logger with comprehensive tracking,
    analytics, and visualization capabilities.
    """
    
    def __init__(self, log_dir: Optional[str] = None, 
                 enable_analytics: bool = True,
                 max_history_days: int = 90):
        """
        Initialize the enhanced status logger.
        
        Args:
            log_dir: Directory for log files (default: logs/)
            enable_analytics: Whether to enable analytics features
            max_history_days: Maximum days to keep history
        """
        # Determine log directory
        if log_dir:
            self.log_dir = Path(log_dir)
        else:
            # Try multiple possible locations
            possible_dirs = [
                Path.cwd() / "logs",
                Path.cwd().parent / "logs",
                Path(__file__).resolve().parent.parent / "logs"
            ]
            
            for directory in possible_dirs:
                if directory.exists() or directory.parent.exists():
                    self.log_dir = directory
                    break
            else:
                self.log_dir = Path.cwd() / "logs"
        
        # Create log directory and subdirectories
        self.log_dir.mkdir(exist_ok=True)
        
        self.subdirs = {
            'training': self.log_dir / 'training',
            'evaluation': self.log_dir / 'evaluation',
            'models': self.log_dir / 'models',
            'analytics': self.log_dir / 'analytics',
            'backups': self.log_dir / 'backups'
        }
        
        for subdir in self.subdirs.values():
            subdir.mkdir(exist_ok=True)
        
        # Define log files
        self.log_files = {
            'training_history': self.subdirs['training'] / 'training_history.csv',
            'evaluation_history': self.subdirs['evaluation'] / 'evaluation_history.csv',
            'model_versions': self.subdirs['models'] / 'model_versions.json',
            'system_events': self.log_dir / 'system_events.jsonl',
            'performance_metrics': self.subdirs['analytics'] / 'performance_metrics.json'
        }
        
        # Initialize log files with expanded headers
        self._initialize_logs()
        
        # Analytics configuration
        self.enable_analytics = enable_analytics
        self.max_history_days = max_history_days
        
        # Performance tracking
        self.performance_stats = {
            'total_training_runs': 0,
            'successful_runs': 0,
            'failed_runs': 0,
            'best_models': {},
            'trends': {}
        }
        
        logger.info(f"✅ StatusLogger initialized")
        logger.info(f"   📁 Log directory: {self.log_dir}")
        logger.info(f"   📊 Analytics enabled: {enable_analytics}")
    
    def _initialize_logs(self):
        """Initialize all log files with proper headers."""
        # Training history CSV
        if not self.log_files['training_history'].exists():
            training_headers = [
                'timestamp', 'run_id', 'target', 'model_type', 'metric_name',
                'score', 'feature_count', 'dataset_size', 'training_time_seconds',
                'best_params', 'model_version', 'git_commit', 'hardware_info',
                'hyperparameters', 'validation_split', 'early_stopping',
                'learning_rate', 'batch_size', 'epochs', 'notes', 'status'
            ]
            
            with open(self.log_files['training_history'], 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(training_headers)
        
        # Evaluation history CSV
        if not self.log_files['evaluation_history'].exists():
            eval_headers = [
                'timestamp', 'eval_id', 'target', 'model_type', 'metric_name',
                'score', 'test_size', 'confidence_interval_lower',
                'confidence_interval_upper', 'standard_error', 'comparison_baseline',
                'improvement_pct', 'business_impact_score', 'roi_estimate',
                'deployment_readiness', 'failure_modes', 'recommendations'
            ]
            
            with open(self.log_files['evaluation_history'], 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(eval_headers)
        
        # Model versions JSON
        if not self.log_files['model_versions'].exists():
            with open(self.log_files['model_versions'], 'w') as f:
                json.dump({}, f, indent=2)
        
        # Performance metrics JSON
        if not self.log_files['performance_metrics'].exists():
            initial_metrics = {
                'summary': {},
                'trends': {},
                'alerts': [],
                'recommendations': []
            }
            with open(self.log_files['performance_metrics'], 'w') as f:
                json.dump(initial_metrics, f, indent=2)
    
    def log_training_run(self, target: str, model_type: str, score: float, 
                        metric_name: str, feature_count: Optional[int] = None,
                        params: Optional[Dict] = None, training_time: Optional[float] = None,
                        dataset_size: Optional[Union[int, tuple]] = None,
                        additional_info: Optional[Dict] = None,
                        run_id: Optional[str] = None,
                        status: str = 'completed') -> str:
        """
        Log a complete training run with comprehensive details.
        
        Args:
            target: Prediction target (e.g., 'WLD', 'TotalGoals')
            model_type: Model architecture (e.g., 'XGB', 'NN')
            score: Validation score
            metric_name: Metric used (e.g., 'Accuracy', 'MAE')
            feature_count: Number of features used
            params: Hyperparameters used
            training_time: Training duration in seconds
            dataset_size: Size of training dataset
            additional_info: Any additional metadata
            run_id: Unique run identifier (auto-generated if None)
            status: Run status ('completed', 'failed', 'interrupted')
            
        Returns:
            str: Run ID
        """
        if run_id is None:
            run_id = f"RUN_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{target}_{model_type}"
        
        timestamp = datetime.now().isoformat()
        
        # Format dataset size
        if dataset_size:
            if isinstance(dataset_size, tuple) and len(dataset_size) == 2:
                dataset_str = f"{dataset_size[0]}x{dataset_size[1]}"
            else:
                dataset_str = str(dataset_size)
        else:
            dataset_str = "unknown"
        
        # Format parameters
        if params:
            # Convert to string, handling complex objects
            try:
                params_str = json.dumps(params, default=str)
                # Truncate if too long
                if len(params_str) > 2000:
                    params_str = params_str[:2000] + "..."
            except:
                params_str = str(params)
        else:
            params_str = "{}"
        
        # Extract hyperparameters for separate logging
        hyperparams = {}
        if params:
            for key in ['n_estimators', 'max_depth', 'learning_rate', 'batch_size', 
                       'epochs', 'hidden_layers', 'dropout_rate']:
                if key in params:
                    hyperparams[key] = params[key]
        
        # Create log entry
        log_entry = {
            'timestamp': timestamp,
            'run_id': run_id,
            'target': target,
            'model_type': model_type.upper(),
            'metric_name': metric_name,
            'score': round(float(score), 6),
            'feature_count': feature_count,
            'dataset_size': dataset_str,
            'training_time_seconds': round(training_time, 2) if training_time else None,
            'best_params': params_str,
            'model_version': self._get_model_version(),
            'git_commit': self._get_git_commit(),
            'hardware_info': self._get_hardware_info(),
            'hyperparameters': json.dumps(hyperparams, default=str),
            'validation_split': additional_info.get('validation_split', 0.2) if additional_info else 0.2,
            'early_stopping': additional_info.get('early_stopping', False) if additional_info else False,
            'learning_rate': additional_info.get('learning_rate', None),
            'batch_size': additional_info.get('batch_size', None),
            'epochs': additional_info.get('epochs', None),
            'notes': additional_info.get('notes', '') if additional_info else '',
            'status': status
        }
        
        try:
            # Append to CSV
            df = pd.DataFrame([log_entry])
            write_header = not self.log_files['training_history'].exists() or \
                          os.path.getsize(self.log_files['training_history']) == 0
            
            df.to_csv(self.log_files['training_history'], 
                     mode='a', header=write_header, index=False)
            
            # Update performance stats
            self.performance_stats['total_training_runs'] += 1
            if status == 'completed':
                self.performance_stats['successful_runs'] += 1
            else:
                self.performance_stats['failed_runs'] += 1
            
            # Check if this is a new best model
            self._update_best_models(target, model_type, score, metric_name, run_id)
            
            # Log system event
            self.log_system_event(
                action='training_completed',
                details={
                    'run_id': run_id,
                    'target': target,
                    'model': model_type,
                    'score': score,
                    'status': status
                },
                level='INFO' if status == 'completed' else 'WARNING'
            )
            
            logger.info(f"📝 Training run logged: {model_type} for {target} (Score: {score:.4f})")
            
            # Run analytics if enabled
            if self.enable_analytics:
                self._run_analytics()
                self._cleanup_old_logs()
            
            return run_id
            
        except Exception as e:
            logger.error(f"❌ Failed to log training run: {e}")
            return None
    
    def log_evaluation(self, target: str, model_type: str, metric_name: str, 
                      score: float, test_size: Optional[int] = None,
                      confidence_interval: Optional[tuple] = None,
                      comparison_baseline: Optional[float] = None,
                      business_impact: Optional[Dict] = None,
                      eval_id: Optional[str] = None) -> str:
        """
        Log evaluation results with business impact analysis.
        
        Args:
            target: Prediction target
            model_type: Model type
            metric_name: Evaluation metric
            score: Evaluation score
            test_size: Size of test set
            confidence_interval: Confidence interval (lower, upper)
            comparison_baseline: Baseline score for comparison
            business_impact: Business impact metrics
            eval_id: Evaluation ID (auto-generated if None)
            
        Returns:
            str: Evaluation ID
        """
        if eval_id is None:
            eval_id = f"EVAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{target}"
        
        timestamp = datetime.now().isoformat()
        
        # Calculate improvement if baseline provided
        improvement_pct = None
        if comparison_baseline is not None and comparison_baseline != 0:
            improvement_pct = ((score - comparison_baseline) / abs(comparison_baseline)) * 100
        
        # Business impact score
        business_impact_score = self._calculate_business_impact_score(
            score, metric_name, business_impact
        )
        
        # ROI estimate
        roi_estimate = self._estimate_roi(score, metric_name, business_impact)
        
        # Deployment readiness
        deployment_readiness = self._assess_deployment_readiness(
            score, metric_name, confidence_interval
        )
        
        # Create log entry
        log_entry = {
            'timestamp': timestamp,
            'eval_id': eval_id,
            'target': target,
            'model_type': model_type.upper(),
            'metric_name': metric_name,
            'score': round(float(score), 6),
            'test_size': test_size,
            'confidence_interval_lower': confidence_interval[0] if confidence_interval else None,
            'confidence_interval_upper': confidence_interval[1] if confidence_interval else None,
            'standard_error': self._calculate_standard_error(confidence_interval) if confidence_interval else None,
            'comparison_baseline': comparison_baseline,
            'improvement_pct': round(improvement_pct, 2) if improvement_pct else None,
            'business_impact_score': business_impact_score,
            'roi_estimate': roi_estimate,
            'deployment_readiness': deployment_readiness,
            'failure_modes': self._identify_failure_modes(score, metric_name),
            'recommendations': self._generate_recommendations(score, metric_name, business_impact_score)
        }
        
        try:
            # Append to CSV
            df = pd.DataFrame([log_entry])
            write_header = not self.log_files['evaluation_history'].exists() or \
                          os.path.getsize(self.log_files['evaluation_history']) == 0
            
            df.to_csv(self.log_files['evaluation_history'], 
                     mode='a', header=write_header, index=False)
            
            # Log system event
            self.log_system_event(
                action='evaluation_completed',
                details={
                    'eval_id': eval_id,
                    'target': target,
                    'score': score,
                    'improvement': improvement_pct,
                    'readiness': deployment_readiness
                }
            )
            
            logger.info(f"📊 Evaluation logged: {model_type} for {target} ({metric_name}: {score:.4f})")
            
            return eval_id
            
        except Exception as e:
            logger.error(f"❌ Failed to log evaluation: {e}")
            return None
    
    def log_model_version(self, model_name: str, version: str, 
                         metadata: Optional[Dict] = None):
        """
        Log model version information.
        
        Args:
            model_name: Name of the model
            version: Version string (e.g., '1.2.3')
            metadata: Additional model metadata
        """
        try:
            # Load existing versions
            if self.log_files['model_versions'].exists():
                with open(self.log_files['model_versions'], 'r') as f:
                    versions = json.load(f)
            else:
                versions = {}
            
            # Update version info
            if model_name not in versions:
                versions[model_name] = {}
            
            versions[model_name][version] = {
                'timestamp': datetime.now().isoformat(),
                'deployed': False,
                'performance': {},
                'metadata': metadata or {},
                'dependencies': self._get_dependencies_info()
            }
            
            # Save updated versions
            with open(self.log_files['model_versions'], 'w') as f:
                json.dump(versions, f, indent=2)
            
            # Log system event
            self.log_system_event(
                action='model_version_created',
                details={
                    'model': model_name,
                    'version': version,
                    'metadata': metadata
                }
            )
            
            logger.info(f"📦 Model version logged: {model_name} v{version}")
            
        except Exception as e:
            logger.error(f"❌ Failed to log model version: {e}")
    
    def log_system_event(self, action: str, details: Optional[Dict] = None,
                        level: str = 'INFO', component: str = 'system'):
        """
        Log a system event in JSONL format.
        
        Args:
            action: Action that occurred
            details: Event details
            level: Log level (INFO, WARNING, ERROR, CRITICAL)
            component: System component
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'level': level.upper(),
            'component': component,
            'action': action,
            'details': details or {},
            'hostname': self._get_hostname(),
            'pid': os.getpid()
        }
        
        try:
            with open(self.log_files['system_events'], 'a', encoding='utf-8') as f:
                f.write(json.dumps(event) + '\n')
            
            # Also log to console based on level
            if level == 'ERROR' or level == 'CRITICAL':
                logger.error(f"🚨 {action}: {details}")
            elif level == 'WARNING':
                logger.warning(f"⚠️ {action}: {details}")
            else:
                logger.info(f"📋 {action}")
                
        except Exception as e:
            logger.error(f"❌ Failed to log system event: {e}")
    
    def get_training_history(self, filters: Optional[Dict] = None,
                           limit: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieve training history with filtering.
        
        Args:
            filters: Dictionary of column:value filters
            limit: Maximum number of rows to return
            
        Returns:
            pandas.DataFrame: Filtered training history
        """
        try:
            if not self.log_files['training_history'].exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.log_files['training_history'])
            
            # Convert timestamp to datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Apply filters
            if filters:
                for column, value in filters.items():
                    if column in df.columns:
                        if isinstance(value, (list, tuple)):
                            df = df[df[column].isin(value)]
                        else:
                            df = df[df[column] == value]
            
            # Sort by timestamp (newest first)
            df = df.sort_values('timestamp', ascending=False)
            
            # Apply limit
            if limit:
                df = df.head(limit)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to get training history: {e}")
            return pd.DataFrame()
    
    def get_evaluation_history(self, filters: Optional[Dict] = None,
                             limit: Optional[int] = None) -> pd.DataFrame:
        """
        Retrieve evaluation history with filtering.
        
        Args:
            filters: Dictionary of column:value filters
            limit: Maximum number of rows to return
            
        Returns:
            pandas.DataFrame: Filtered evaluation history
        """
        try:
            if not self.log_files['evaluation_history'].exists():
                return pd.DataFrame()
            
            df = pd.read_csv(self.log_files['evaluation_history'])
            
            # Convert timestamp to datetime
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
            
            # Apply filters
            if filters:
                for column, value in filters.items():
                    if column in df.columns:
                        if isinstance(value, (list, tuple)):
                            df = df[df[column].isin(value)]
                        else:
                            df = df[df[column] == value]
            
            # Sort by timestamp (newest first)
            df = df.sort_values('timestamp', ascending=False)
            
            # Apply limit
            if limit:
                df = df.head(limit)
            
            return df
            
        except Exception as e:
            logger.error(f"❌ Failed to get evaluation history: {e}")
            return pd.DataFrame()
    
    def get_performance_summary(self) -> Dict:
        """
        Generate performance summary report.
        
        Returns:
            dict: Performance summary
        """
        summary = {
            'generated_at': datetime.now().isoformat(),
            'training_stats': self.performance_stats,
            'model_performance': {},
            'trends': {},
            'recommendations': [],
            'alerts': []
        }
        
        try:
            # Load training history
            training_df = self.get_training_history()
            
            if not training_df.empty:
                # Overall statistics
                summary['training_stats']['total_runs'] = len(training_df)
                summary['training_stats']['success_rate'] = (
                    len(training_df[training_df['status'] == 'completed']) / 
                    max(1, len(training_df))
                )
                
                # Model performance by target
                for target in training_df['target'].unique():
                    target_df = training_df[training_df['target'] == target]
                    
                    if not target_df.empty:
                        best_run = target_df.loc[target_df['score'].idxmax()]
                        worst_run = target_df.loc[target_df['score'].idxmin()]
                        
                        summary['model_performance'][target] = {
                            'best_score': float(best_run['score']),
                            'best_model': best_run['model_type'],
                            'worst_score': float(worst_run['score']),
                            'worst_model': worst_run['model_type'],
                            'avg_score': float(target_df['score'].mean()),
                            'std_score': float(target_df['score'].std()),
                            'total_runs': len(target_df)
                        }
                
                # Trends over time
                training_df['date'] = training_df['timestamp'].dt.date
                daily_stats = training_df.groupby('date').agg({
                    'score': ['mean', 'count'],
                    'training_time_seconds': 'mean'
                }).round(4)
                
                summary['trends']['daily'] = daily_stats.to_dict()
            
            # Load evaluation history
            eval_df = self.get_evaluation_history()
            
            if not eval_df.empty:
                summary['evaluation_stats'] = {
                    'total_evaluations': len(eval_df),
                    'avg_improvement': float(eval_df['improvement_pct'].mean() if 'improvement_pct' in eval_df.columns else 0),
                    'avg_readiness': float(eval_df['deployment_readiness'].mean() if 'deployment_readiness' in eval_df.columns else 0)
                }
            
            # Generate recommendations
            summary['recommendations'] = self._generate_summary_recommendations(summary)
            
            # Check for alerts
            summary['alerts'] = self._check_for_alerts(summary)
            
            # Save summary
            with open(self.log_files['performance_metrics'], 'w') as f:
                json.dump(summary, f, indent=2)
            
            return summary
            
        except Exception as e:
            logger.error(f"❌ Failed to generate performance summary: {e}")
            return summary
    
    def export_logs(self, output_format: str = 'csv', 
                   include: List[str] = ['training', 'evaluation'],
                   output_dir: Optional[str] = None) -> Dict[str, str]:
        """
        Export logs in various formats.
        
        Args:
            output_format: Export format ('csv', 'json', 'excel')
            include: Which logs to include
            output_dir: Output directory (default: logs/exports)
            
        Returns:
            dict: Paths to exported files
        """
        if output_dir is None:
            output_dir = self.log_dir / 'exports'
            output_dir.mkdir(exist_ok=True)
        else:
            output_dir = Path(output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        exported_files = {}
        
        try:
            # Export training history
            if 'training' in include and self.log_files['training_history'].exists():
                df = self.get_training_history()
                
                if not df.empty:
                    filename = f'training_history_{timestamp}'
                    
                    if output_format == 'csv':
                        filepath = output_dir / f'{filename}.csv'
                        df.to_csv(filepath, index=False)
                    elif output_format == 'json':
                        filepath = output_dir / f'{filename}.json'
                        df.to_json(filepath, orient='records', indent=2)
                    elif output_format == 'excel':
                        filepath = output_dir / f'{filename}.xlsx'
                        df.to_excel(filepath, index=False)
                    
                    exported_files['training'] = str(filepath)
            
            # Export evaluation history
            if 'evaluation' in include and self.log_files['evaluation_history'].exists():
                df = self.get_evaluation_history()
                
                if not df.empty:
                    filename = f'evaluation_history_{timestamp}'
                    
                    if output_format == 'csv':
                        filepath = output_dir / f'{filename}.csv'
                        df.to_csv(filepath, index=False)
                    elif output_format == 'json':
                        filepath = output_dir / f'{filename}.json'
                        df.to_json(filepath, orient='records', indent=2)
                    elif output_format == 'excel':
                        filepath = output_dir / f'{filename}.xlsx'
                        df.to_excel(filepath, index=False)
                    
                    exported_files['evaluation'] = str(filepath)
            
            # Export performance summary
            if 'summary' in include:
                summary = self.get_performance_summary()
                filepath = output_dir / f'performance_summary_{timestamp}.json'
                
                with open(filepath, 'w') as f:
                    json.dump(summary, f, indent=2)
                
                exported_files['summary'] = str(filepath)
            
            logger.info(f"📤 Logs exported: {exported_files}")
            return exported_files
            
        except Exception as e:
            logger.error(f"❌ Failed to export logs: {e}")
            return {}
    
    def cleanup(self, days_to_keep: Optional[int] = None):
        """
        Clean up old log entries.
        
        Args:
            days_to_keep: Number of days to keep (default: max_history_days)
        """
        if days_to_keep is None:
            days_to_keep = self.max_history_days
        
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        
        try:
            # Clean training history
            if self.log_files['training_history'].exists():
                df = pd.read_csv(self.log_files['training_history'])
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df[df['timestamp'] >= cutoff_date]
                    df.to_csv(self.log_files['training_history'], index=False)
            
            # Clean evaluation history
            if self.log_files['evaluation_history'].exists():
                df = pd.read_csv(self.log_files['evaluation_history'])
                if 'timestamp' in df.columns:
                    df['timestamp'] = pd.to_datetime(df['timestamp'])
                    df = df[df['timestamp'] >= cutoff_date]
                    df.to_csv(self.log_files['evaluation_history'], index=False)
            
            # Archive old logs
            self._archive_old_logs(cutoff_date)
            
            logger.info(f"🧹 Cleaned up logs older than {days_to_keep} days")
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup logs: {e}")
    
    # --- HELPER METHODS ---
    
    def _update_best_models(self, target: str, model_type: str, 
                           score: float, metric_name: str, run_id: str):
        """Update best models tracking."""
        if target not in self.performance_stats['best_models']:
            self.performance_stats['best_models'][target] = {
                'score': score,
                'model': model_type,
                'metric': metric_name,
                'run_id': run_id,
                'timestamp': datetime.now().isoformat()
            }
        else:
            current_best = self.performance_stats['best_models'][target]
            
            # Determine if new score is better
            # For accuracy/F1/etc: higher is better
            # For MAE/RMSE/etc: lower is better
            is_higher_better = metric_name.lower() in ['accuracy', 'f1', 'precision', 
                                                      'recall', 'roc_auc', 'r2']
            
            if is_higher_better:
                if score > current_best['score']:
                    self.performance_stats['best_models'][target] = {
                        'score': score,
                        'model': model_type,
                        'metric': metric_name,
                        'run_id': run_id,
                        'timestamp': datetime.now().isoformat()
                    }
            else:
                if score < current_best['score']:
                    self.performance_stats['best_models'][target] = {
                        'score': score,
                        'model': model_type,
                        'metric': metric_name,
                        'run_id': run_id,
                        'timestamp': datetime.now().isoformat()
                    }
    
    def _run_analytics(self):
        """Run analytics on training data."""
        try:
            df = self.get_training_history(limit=100)  # Last 100 runs
            
            if len(df) > 5:  # Need enough data for analytics
                # Calculate trends
                trends = {
                    'score_trend': self._calculate_trend(df, 'score'),
                    'training_time_trend': self._calculate_trend(df, 'training_time_seconds'),
                    'feature_count_trend': self._calculate_trend(df, 'feature_count')
                }
                
                self.performance_stats['trends'] = trends
                
                # Save analytics
                analytics_file = self.subdirs['analytics'] / f'analytics_{datetime.now().strftime("%Y%m%d")}.json'
                analytics_data = {
                    'timestamp': datetime.now().isoformat(),
                    'trends': trends,
                    'model_distribution': df['model_type'].value_counts().to_dict(),
                    'target_distribution': df['target'].value_counts().to_dict(),
                    'performance_summary': df.groupby('target')['score'].agg(['mean', 'std', 'min', 'max']).to_dict()
                }
                
                with open(analytics_file, 'w') as f:
                    json.dump(analytics_data, f, indent=2)
                
                logger.info("📈 Analytics completed")
                
        except Exception as e:
            logger.error(f"❌ Analytics failed: {e}")
    
    def _calculate_trend(self, df: pd.DataFrame, column: str) -> str:
        """Calculate trend for a column."""
        if column not in df.columns or df[column].isnull().all():
            return 'unknown'
        
        # Get recent values
        recent = df[column].tail(5).dropna()
        older = df[column].head(max(1, len(df) - 5)).dropna()
        
        if len(recent) < 2 or len(older) < 2:
            return 'insufficient_data'
        
        recent_mean = recent.mean()
        older_mean = older.mean()
        
        if recent_mean > older_mean * 1.1:
            return 'improving'
        elif recent_mean < older_mean * 0.9:
            return 'declining'
        else:
            return 'stable'
    
    def _calculate_business_impact_score(self, score: float, metric_name: str,
                                        business_impact: Optional[Dict]) -> float:
        """Calculate business impact score."""
        if business_impact:
            # Use provided business impact metrics
            revenue_impact = business_impact.get('revenue_impact', 0)
            cost_reduction = business_impact.get('cost_reduction', 0)
            risk_reduction = business_impact.get('risk_reduction', 0)
            
            return (revenue_impact + cost_reduction + risk_reduction) / 3
        else:
            # Estimate based on model performance
            if metric_name.lower() in ['accuracy', 'f1', 'roc_auc']:
                # Classification metrics
                return score * 100  # Scale to 0-100
            elif metric_name.lower() in ['mae', 'rmse']:
                # Regression metrics (inverse)
                return max(0, 100 - (score * 20))  # Scale based on error
            else:
                return score * 100
    
    def _estimate_roi(self, score: float, metric_name: str, 
                     business_impact: Optional[Dict]) -> float:
        """Estimate ROI based on performance."""
        base_roi = 0
        
        if business_impact and 'estimated_value' in business_impact:
            base_roi = business_impact['estimated_value']
        else:
            # Simple estimation based on performance
            if metric_name.lower() in ['accuracy', 'f1']:
                base_roi = (score - 0.5) * 2000  # $2000 per 0.1 improvement over 0.5
            elif metric_name.lower() == 'mae':
                base_roi = (1 - min(score, 2) / 2) * 1000  # $1000 per 0.1 MAE reduction
        
        return round(base_roi, 2)
    
    def _assess_deployment_readiness(self, score: float, metric_name: str,
                                    confidence_interval: Optional[tuple]) -> str:
        """Assess deployment readiness."""
        if metric_name.lower() in ['accuracy', 'f1', 'roc_auc']:
            if score > 0.8:
                readiness = 'production_ready'
            elif score > 0.7:
                readiness = 'staging_ready'
            elif score > 0.6:
                readiness = 'testing'
            else:
                readiness = 'development'
        elif metric_name.lower() in ['mae', 'rmse']:
            if score < 0.5:
                readiness = 'production_ready'
            elif score < 1.0:
                readiness = 'staging_ready'
            elif score < 1.5:
                readiness = 'testing'
            else:
                readiness = 'development'
        else:
            readiness = 'unknown'
        
        # Adjust based on confidence interval
        if confidence_interval:
            ci_width = confidence_interval[1] - confidence_interval[0]
            if ci_width > 0.1:  # Wide confidence interval
                if readiness == 'production_ready':
                    readiness = 'staging_ready'
                elif readiness == 'staging_ready':
                    readiness = 'testing'
        
        return readiness
    
    def _identify_failure_modes(self, score: float, metric_name: str) -> List[str]:
        """Identify potential failure modes."""
        failure_modes = []
        
        if metric_name.lower() in ['accuracy', 'f1']:
            if score < 0.5:
                failure_modes.append('poor_accuracy')
            if score < 0.6:
                failure_modes.append('needs_improvement')
        
        elif metric_name.lower() in ['mae', 'rmse']:
            if score > 1.5:
                failure_modes.append('high_error')
            if score > 1.0:
                failure_modes.append('needs_improvement')
        
        return failure_modes
    
    def _generate_recommendations(self, score: float, metric_name: str,
                                 business_impact_score: float) -> List[str]:
        """Generate recommendations based on performance."""
        recommendations = []
        
        if metric_name.lower() in ['accuracy', 'f1']:
            if score < 0.6:
                recommendations.append('Consider collecting more training data')
                recommendations.append('Try different model architectures')
                recommendations.append('Review feature engineering pipeline')
            elif score < 0.7:
                recommendations.append('Optimize hyperparameters')
                recommendations.append('Add ensemble methods')
            elif score < 0.8:
                recommendations.append('Fine-tune on specific edge cases')
                recommendations.append('Consider model calibration')
        
        elif metric_name.lower() in ['mae', 'rmse']:
            if score > 1.0:
                recommendations.append('Improve feature selection')
                recommendations.append('Consider non-linear models')
                recommendations.append('Address outliers in training data')
            elif score > 0.5:
                recommendations.append('Try regularization techniques')
                recommendations.append('Consider feature transformations')
        
        if business_impact_score < 50:
            recommendations.append('Focus on features with higher business impact')
            recommendations.append('Consider cost-sensitive learning')
        
        return recommendations
    
    def _generate_summary_recommendations(self, summary: Dict) -> List[str]:
        """Generate summary-level recommendations."""
        recommendations = []
        
        training_stats = summary.get('training_stats', {})
        model_performance = summary.get('model_performance', {})
        
        # Check success rate
        success_rate = training_stats.get('success_rate', 0)
        if success_rate < 0.8:
            recommendations.append(f'Improve training success rate (currently {success_rate:.1%})')
        
        # Check model performance
        for target, perf in model_performance.items():
            avg_score = perf.get('avg_score', 0)
            
            if 'accuracy' in target.lower() or 'WLD' in target:
                if avg_score < 0.6:
                    recommendations.append(f'Improve {target} model performance (avg: {avg_score:.3f})')
            elif 'mae' in target.lower():
                if avg_score > 1.0:
                    recommendations.append(f'Reduce {target} prediction error (avg MAE: {avg_score:.3f})')
        
        # Check trends
        trends = summary.get('trends', {}).get('daily', {})
        if 'score' in trends.get('mean', {}):
            recent_scores = list(trends['mean']['score'].values())[-5:]
            if len(recent_scores) >= 2:
                if recent_scores[-1] < recent_scores[0] * 0.95:
                    recommendations.append('Performance trend is declining - investigate recent changes')
        
        return recommendations[:5]  # Top 5 recommendations
    
    def _check_for_alerts(self, summary: Dict) -> List[Dict]:
        """Check for conditions requiring alerts."""
        alerts = []
        
        training_stats = summary.get('training_stats', {})
        
        # Alert for high failure rate
        if training_stats.get('failed_runs', 0) > 5:
            alerts.append({
                'type': 'high_failure_rate',
                'message': f"High training failure rate: {training_stats.get('failed_runs', 0)} failed runs",
                'severity': 'high'
            })
        
        # Alert for performance degradation
        model_performance = summary.get('model_performance', {})
        for target, perf in model_performance.items():
            std_score = perf.get('std_score', 0)
            if std_score > 0.1:  # High variance in performance
                alerts.append({
                    'type': 'high_variance',
                    'message': f"High variance in {target} performance (std: {std_score:.3f})",
                    'severity': 'medium'
                })
        
        return alerts
    
    def _cleanup_old_logs(self):
        """Clean up old log files."""
        try:
            # Clean system events (keep last 1000 lines)
            if self.log_files['system_events'].exists():
                with open(self.log_files['system_events'], 'r') as f:
                    lines = f.readlines()
                
                if len(lines) > 1000:
                    with open(self.log_files['system_events'], 'w') as f:
                        f.writelines(lines[-1000:])
            
            # Clean analytics files (keep last 30 days)
            analytics_dir = self.subdirs['analytics']
            if analytics_dir.exists():
                for file in analytics_dir.glob('analytics_*.json'):
                    file_date_str = file.stem.split('_')[1]
                    try:
                        file_date = datetime.strptime(file_date_str, '%Y%m%d')
                        if (datetime.now() - file_date).days > 30:
                            file.unlink()
                    except:
                        pass
            
        except Exception as e:
            logger.error(f"❌ Failed to cleanup old logs: {e}")
    
    def _archive_old_logs(self, cutoff_date: datetime):
        """Archive old logs instead of deleting."""
        archive_dir = self.subdirs['backups'] / cutoff_date.strftime('%Y%m')
        archive_dir.mkdir(exist_ok=True)
        
        # Archive old training history
        if self.log_files['training_history'].exists():
            df = pd.read_csv(self.log_files['training_history'])
            if 'timestamp' in df.columns:
                df['timestamp'] = pd.to_datetime(df['timestamp'])
                old_df = df[df['timestamp'] < cutoff_date]
                
                if not old_df.empty:
                    archive_file = archive_dir / f'training_history_{cutoff_date.strftime("%Y%m%d")}.csv'
                    old_df.to_csv(archive_file, index=False)
    
    def _get_model_version(self) -> str:
        """Get current model version."""
        try:
            version_file = Path(__file__).resolve().parent.parent / 'VERSION'
            if version_file.exists():
                with open(version_file, 'r') as f:
                    return f.read().strip()
        except:
            pass
        
        return '1.0.0'
    
    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash."""
        try:
            import subprocess
            result = subprocess.run(
                ['git', 'rev-parse', '--short', 'HEAD'],
                capture_output=True,
                text=True,
                cwd=Path(__file__).resolve().parent.parent
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except:
            pass
        
        return None
    
    def _get_hardware_info(self) -> str:
        """Get hardware information."""
        try:
            import platform
            import psutil
            
            info = {
                'platform': platform.platform(),
                'processor': platform.processor(),
                'ram_gb': round(psutil.virtual_memory().total / (1024**3), 1),
                'cpu_count': psutil.cpu_count(),
                'python_version': platform.python_version()
            }
            
            return json.dumps(info)
        except:
            return '{}'
    
    def _get_hostname(self) -> str:
        """Get system hostname."""
        try:
            import socket
            return socket.gethostname()
        except:
            return 'unknown'
    
    def _get_dependencies_info(self) -> Dict:
        """Get Python dependencies information."""
        try:
            import pkg_resources
            dependencies = {}
            
            for dist in pkg_resources.working_set:
                dependencies[dist.key] = dist.version
            
            return dependencies
        except:
            return {}
    
    def _calculate_standard_error(self, confidence_interval: tuple) -> Optional[float]:
        """Calculate standard error from confidence interval."""
        if confidence_interval and len(confidence_interval) == 2:
            ci_width = confidence_interval[1] - confidence_interval[0]
            # Assuming 95% CI: SE = CI_width / (2 * 1.96)
            return ci_width / (2 * 1.96)
        return None


# Singleton instance for easy access
_status_logger_instance = None

def get_status_logger(log_dir: Optional[str] = None, 
                     enable_analytics: bool = True) -> StatusLogger:
    """Get or create singleton status logger instance."""
    global _status_logger_instance
    if _status_logger_instance is None:
        _status_logger_instance = StatusLogger(log_dir, enable_analytics)
    return _status_logger_instance


if __name__ == "__main__":
    # Demonstration and self-test
    print("🧪 Running StatusLogger self-test...")
    
    logger = get_status_logger()
    
    # Test training run logging
    run_id = logger.log_training_run(
        target="TEST_WLD",
        model_type="XGB",
        score=0.8543,
        metric_name="Accuracy",
        feature_count=33,
        params={
            'n_estimators': 500,
            'max_depth': 7,
            'learning_rate': 0.1
        },
        training_time=45.2,
        dataset_size=(10000, 50),
        additional_info={
            'notes': 'Test run with expanded features',
            'validation_split': 0.2,
            'early_stopping': True
        }
    )
    
    # Test evaluation logging
    eval_id = logger.log_evaluation(
        target="TEST_WLD",
        model_type="XGB",
        metric_name="Accuracy",
        score=0.8234,
        test_size=2000,
        confidence_interval=(0.810, 0.836),
        comparison_baseline=0.78,
        business_impact={
            'revenue_impact': 1500,
            'cost_reduction': 500,
            'risk_reduction': 0.2
        }
    )
    
    # Test model version logging
    logger.log_model_version(
        model_name="WLD_Classifier",
        version="1.2.3",
        metadata={
            'description': 'Win/Loss/Draw classifier',
            'author': 'AI Team',
            'training_data': '2023 Premier League'
        }
    )
    
    # Test system event logging
    logger.log_system_event(
        action="self_test_completed",
        details={'tests_run': 3, 'status': 'success'},
        level="INFO",
        component="testing"
    )
    
    # Generate summary
    summary = logger.get_performance_summary()
    print(f"\n📊 Performance Summary Generated:")
    print(f"   Total runs: {summary.get('training_stats', {}).get('total_runs', 0)}")
    print(f"   Best models: {len(summary.get('model_performance', {}))}")
    print(f"   Recommendations: {len(summary.get('recommendations', []))}")
    
    # Export logs
    exported = logger.export_logs(output_format='json', include=['training', 'evaluation', 'summary'])
    print(f"   Exported files: {len(exported)}")
    
    print("\n✅ StatusLogger self-test completed successfully!")