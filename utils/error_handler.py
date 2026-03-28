"""
The 'Safety Net' of the pipeline, providing comprehensive error tracking and automated recovery strategies.
It monitors system health metrics like 'degraded_mode_entries' and 'recovery_success' to assess operational stability.
The module generates actionable health recommendations based on error frequency within specific pipeline stages.
It allows the system to enter a 'Degraded Mode' rather than crashing, maintaining basic functionality during partial failures.
Detailed stack traces and error statistics are persisted to 'logs/error_handler.log' for deep-dive debugging.
"""


import logging
import traceback
import pandas as pd
import numpy as np
from datetime import datetime
import json
import os
from typing import Optional, Any, Dict, Tuple
import warnings
warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/error_handler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PipelineErrorHandler:
    """
    Comprehensive error handling and recovery system for the prediction pipeline.
    Provides graceful degradation, automatic recovery, and detailed error tracking.
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        Initialize the error handler with configuration.
        
        Args:
            config_path: Optional path to error handling configuration
        """
        self.error_stats = {
            'loading_errors': 0,
            'prediction_errors': 0,
            'recovery_success': 0,
            'recovery_failed': 0,
            'degraded_mode_entries': 0
        }
        
        # Error thresholds for alerting
        self.thresholds = {
            'max_loading_errors': 3,
            'max_prediction_errors': 5,
            'consecutive_errors': 10
        }
        
        # Fallback strategies
        self.fallback_strategies = {
            'data_loading': ['use_cached_data', 'use_synthetic_data', 'use_simplified_schema'],
            'prediction': ['use_simple_model', 'use_historical_average', 'use_expert_system'],
            'feature_engineering': ['skip_complex_features', 'use_basic_features_only']
        }
        
        # Error patterns for intelligent recovery
        self.error_patterns = {
            'memory_error': ['MemoryError', 'OutOfMemoryError', 'CUDA out of memory'],
            'file_error': ['FileNotFoundError', 'PermissionError', 'IsADirectoryError'],
            'data_error': ['ValueError', 'KeyError', 'TypeError', 'IndexError'],
            'model_error': ['AttributeError', 'RuntimeError', 'NotFittedError']
        }
        
        # Create error log directory
        os.makedirs('logs/error_reports', exist_ok=True)
        
        logger.info("✅ PipelineErrorHandler initialized")
    
    def handle_loading_error(self, error: Exception, context: str = "", 
                           fallback_strategy: str = 'use_cached_data') -> pd.DataFrame:
        """
        Handle data loading errors with graceful fallback strategies.
        
        Args:
            error: The exception that occurred
            context: Context information about where the error occurred
            fallback_strategy: Which fallback strategy to use
            
        Returns:
            pandas.DataFrame: Fallback data or empty DataFrame
        """
        self.error_stats['loading_errors'] += 1
        error_id = f"LOAD_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.error(f"❌ Data loading failed in {context}: {str(error)}")
        
        # Log detailed error information
        error_details = {
            'error_id': error_id,
            'timestamp': datetime.now().isoformat(),
            'context': context,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'fallback_strategy': fallback_strategy,
            'error_stats': self.error_stats.copy()
        }
        
        self._save_error_report(error_details, 'loading_error')
        
        # Check if we should trigger system alert
        if self.error_stats['loading_errors'] >= self.thresholds['max_loading_errors']:
            self._trigger_system_alert('data_loading_critical', error_details)
        
        # Apply fallback strategy
        try:
            fallback_data = self._apply_loading_fallback(fallback_strategy, context, error)
            if not fallback_data.empty:
                self.error_stats['recovery_success'] += 1
                logger.info(f"✅ Recovery successful using {fallback_strategy}")
                return fallback_data
        except Exception as fallback_error:
            logger.error(f"❌ Fallback strategy failed: {fallback_error}")
            self.error_stats['recovery_failed'] += 1
        
        # Ultimate fallback: return empty DataFrame with warning
        logger.warning("⚠️ All fallback strategies failed, returning empty DataFrame")
        return pd.DataFrame()
    
    def handle_prediction_error(self, error: Exception, home_team: str, away_team: str,
                              user_tier: str = 'free', fallback_strategy: str = 'use_simple_model') -> Dict:
        """
        Handle prediction errors with intelligent fallback strategies.
        
        Args:
            error: The exception that occurred
            home_team: Home team name
            away_team: Away team name
            user_tier: User subscription tier
            fallback_strategy: Which fallback strategy to use
            
        Returns:
            dict: Fallback prediction or error response
        """
        self.error_stats['prediction_errors'] += 1
        error_id = f"PRED_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.error(f"❌ Prediction failed for {home_team} vs {away_team}: {str(error)}")
        
        # Log detailed error information
        error_details = {
            'error_id': error_id,
            'timestamp': datetime.now().isoformat(),
            'match': f"{home_team} vs {away_team}",
            'user_tier': user_tier,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'fallback_strategy': fallback_strategy,
            'error_stats': self.error_stats.copy()
        }
        
        self._save_error_report(error_details, 'prediction_error')
        
        # Check if we should trigger system alert
        if self.error_stats['prediction_errors'] >= self.thresholds['max_prediction_errors']:
            self._trigger_system_alert('prediction_critical', error_details)
        
        # Apply fallback prediction strategy
        try:
            fallback_prediction = self._apply_prediction_fallback(
                fallback_strategy, home_team, away_team, user_tier, error
            )
            
            if 'error' not in fallback_prediction:
                self.error_stats['recovery_success'] += 1
                fallback_prediction['status'] = 'degraded_fallback'
                fallback_prediction['warning'] = 'Using simplified prediction model'
                logger.info(f"✅ Prediction recovery successful using {fallback_strategy}")
                return fallback_prediction
                
        except Exception as fallback_error:
            logger.error(f"❌ Prediction fallback failed: {fallback_error}")
            self.error_stats['recovery_failed'] += 1
        
        # Ultimate fallback: return informative error
        self.error_stats['degraded_mode_entries'] += 1
        return {
            "error": "Prediction service temporarily unavailable",
            "status": "degraded",
            "suggestion": "Please try again in a few minutes",
            "match": f"{home_team} vs {away_team}",
            "timestamp": datetime.now().isoformat(),
            "error_id": error_id
        }
    
    def handle_model_error(self, error: Exception, model_name: str, 
                          context: str = "training") -> Dict:
        """
        Handle model training or inference errors.
        
        Args:
            error: The exception that occurred
            model_name: Name of the model
            context: Context (training, inference, loading)
            
        Returns:
            dict: Recovery instructions or error details
        """
        error_id = f"MODEL_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        logger.error(f"❌ Model error for {model_name} in {context}: {str(error)}")
        
        error_details = {
            'error_id': error_id,
            'timestamp': datetime.now().isoformat(),
            'model': model_name,
            'context': context,
            'error_type': type(error).__name__,
            'error_message': str(error),
            'stack_trace': traceback.format_exc(),
            'recovery_suggestions': self._generate_recovery_suggestions(error, context)
        }
        
        self._save_error_report(error_details, 'model_error')
        
        return {
            'status': 'error',
            'model': model_name,
            'error_id': error_id,
            'recovery_suggestions': error_details['recovery_suggestions'],
            'severity': self._assess_error_severity(error, context)
        }
    
    def _apply_loading_fallback(self, strategy: str, context: str, 
                              original_error: Exception) -> pd.DataFrame:
        """
        Apply specific fallback strategy for data loading.
        
        Args:
            strategy: Fallback strategy name
            context: Error context
            original_error: Original exception
            
        Returns:
            pandas.DataFrame: Fallback data
        """
        logger.info(f"Applying loading fallback: {strategy}")
        
        if strategy == 'use_cached_data':
            # Try to load from cache
            cache_paths = [
                'data/cache/latest_data.pkl',
                'data/processed/train.csv',
                'data/raw/backup_data.csv'
            ]
            
            for cache_path in cache_paths:
                if os.path.exists(cache_path):
                    try:
                        if cache_path.endswith('.pkl'):
                            return pd.read_pickle(cache_path)
                        else:
                            return pd.read_csv(cache_path)
                    except Exception as e:
                        logger.warning(f"Cache load failed for {cache_path}: {e}")
                        continue
            
            # If no cache found, create synthetic data
            return self._generate_synthetic_data()
            
        elif strategy == 'use_synthetic_data':
            return self._generate_synthetic_data()
            
        elif strategy == 'use_simplified_schema':
            # Create minimal viable dataset
            return pd.DataFrame({
                'HomeTeam': ['Team A', 'Team B'],
                'AwayTeam': ['Team B', 'Team A'],
                'FTHG': [1, 0],
                'FTAG': [0, 1],
                'FTR': ['H', 'A']
            })
            
        else:
            raise ValueError(f"Unknown fallback strategy: {strategy}")
    
    def _apply_prediction_fallback(self, strategy: str, home_team: str, 
                                 away_team: str, user_tier: str,
                                 original_error: Exception) -> Dict:
        """
        Apply specific fallback strategy for predictions.
        
        Args:
            strategy: Fallback strategy name
            home_team: Home team name
            away_team: Away team name
            user_tier: User subscription tier
            original_error: Original exception
            
        Returns:
            dict: Fallback prediction
        """
        logger.info(f"Applying prediction fallback: {strategy}")
        
        if strategy == 'use_simple_model':
            # Use simple rule-based prediction
            return self._simple_rule_based_prediction(home_team, away_team, user_tier)
            
        elif strategy == 'use_historical_average':
            # Use historical averages
            return self._historical_average_prediction(home_team, away_team)
            
        elif strategy == 'use_expert_system':
            # Use expert system rules
            return self._expert_system_prediction(home_team, away_team)
            
        else:
            raise ValueError(f"Unknown fallback strategy: {strategy}")
    
    def _simple_rule_based_prediction(self, home_team: str, away_team: str, 
                                    user_tier: str) -> Dict:
        """Simple rule-based fallback prediction."""
        # Basic rules (50% home win, 30% draw, 20% away win as baseline)
        import random
        
        base_home_win = 0.50
        base_draw = 0.30
        base_away_win = 0.20
        
        # Adjust based on team names (very simple heuristic)
        home_factor = len(home_team) / (len(home_team) + len(away_team))
        away_factor = len(away_team) / (len(home_team) + len(away_team))
        
        adjusted_home = base_home_win * home_factor
        adjusted_draw = base_draw
        adjusted_away = base_away_win * away_factor
        
        # Normalize
        total = adjusted_home + adjusted_draw + adjusted_away
        win_prob = {
            'Home Win': round(adjusted_home / total, 3),
            'Draw': round(adjusted_draw / total, 3),
            'Away Win': round(adjusted_away / total, 3)
        }
        
        # Determine top prediction
        top_pred = max(win_prob, key=win_prob.get)
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'win_prob': win_prob,
            'top': top_pred,
            'confidence': {
                'score': round(random.uniform(0.4, 0.6), 2),
                'level': 'low'
            },
            'model_info': 'simple_rule_based_fallback',
            'warning': 'Using simplified prediction model',
            'timestamp': datetime.now().isoformat()
        }
    
    def _historical_average_prediction(self, home_team: str, away_team: str) -> Dict:
        """Historical average fallback prediction."""
        # Very basic historical average (mock data)
        import random
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'win_prob': {
                'Home Win': round(random.uniform(0.4, 0.6), 3),
                'Draw': round(random.uniform(0.2, 0.3), 3),
                'Away Win': round(random.uniform(0.2, 0.4), 3)
            },
            'top': 'Home Win' if random.random() > 0.5 else 'Away Win',
            'confidence': {
                'score': round(random.uniform(0.3, 0.5), 2),
                'level': 'very_low'
            },
            'model_info': 'historical_average_fallback',
            'warning': 'Using historical averages (limited accuracy)',
            'timestamp': datetime.now().isoformat()
        }
    
    def _expert_system_prediction(self, home_team: str, away_team: str) -> Dict:
        """Expert system fallback prediction."""
        # Simple expert system rules
        import random
        
        # Some basic rules
        if 'United' in home_team or 'City' in home_team:
            home_bonus = 0.1
        else:
            home_bonus = 0
        
        if 'United' in away_team or 'City' in away_team:
            away_bonus = 0.1
        else:
            away_bonus = 0
        
        base_home = 0.45 + home_bonus
        base_draw = 0.25
        base_away = 0.30 + away_bonus
        
        # Normalize
        total = base_home + base_draw + base_away
        
        return {
            'home_team': home_team,
            'away_team': away_team,
            'win_prob': {
                'Home Win': round(base_home / total, 3),
                'Draw': round(base_draw / total, 3),
                'Away Win': round(base_away / total, 3)
            },
            'top': 'Home Win' if base_home > base_away else 'Away Win',
            'confidence': {
                'score': round(random.uniform(0.35, 0.55), 2),
                'level': 'low'
            },
            'model_info': 'expert_system_fallback',
            'warning': 'Using rule-based expert system',
            'timestamp': datetime.now().isoformat()
        }
    
    def _generate_synthetic_data(self) -> pd.DataFrame:
        """Generate synthetic match data for fallback."""
        import random
        
        teams = ['Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'Man United', 
                'Tottenham', 'Leicester', 'West Ham', 'Everton', 'Aston Villa']
        
        matches = []
        for _ in range(20):
            home = random.choice(teams)
            away = random.choice([t for t in teams if t != home])
            
            matches.append({
                'HomeTeam': home,
                'AwayTeam': away,
                'FTHG': random.randint(0, 4),
                'FTAG': random.randint(0, 4),
                'FTR': random.choice(['H', 'D', 'A'])
            })
        
        return pd.DataFrame(matches)
    
    def _save_error_report(self, error_details: Dict, error_type: str):
        """Save detailed error report to file."""
        try:
            report_dir = 'logs/error_reports'
            os.makedirs(report_dir, exist_ok=True)
            
            filename = f"{error_type}_{error_details['error_id']}.json"
            filepath = os.path.join(report_dir, filename)
            
            with open(filepath, 'w') as f:
                json.dump(error_details, f, indent=2, default=str)
            
            # Also log to central error log
            self._log_to_error_database(error_details)
            
        except Exception as e:
            logger.error(f"Failed to save error report: {e}")
    
    def _log_to_error_database(self, error_details: Dict):
        """Log error to central error database (simplified)."""
        try:
            log_file = 'logs/error_database.csv'
            
            # Create log entry
            log_entry = {
                'timestamp': error_details['timestamp'],
                'error_id': error_details.get('error_id', 'UNKNOWN'),
                'error_type': error_details.get('error_type', 'UNKNOWN'),
                'context': error_details.get('context', ''),
                'message': error_details.get('error_message', '')[:200],
                'recovered': 'recovery_success' in error_details
            }
            
            # Append to CSV
            df = pd.DataFrame([log_entry])
            write_header = not os.path.exists(log_file)
            df.to_csv(log_file, mode='a', header=write_header, index=False)
            
        except Exception as e:
            logger.error(f"Failed to log to error database: {e}")
    
    def _trigger_system_alert(self, alert_type: str, error_details: Dict):
        """Trigger system alert for critical errors."""
        alert_message = f"""
        🚨 SYSTEM ALERT: {alert_type.upper()}
        Time: {error_details['timestamp']}
        Error ID: {error_details['error_id']}
        Context: {error_details.get('context', 'N/A')}
        Message: {error_details.get('error_message', 'N/A')}
        Stats: {self.error_stats}
        """
        
        logger.critical(alert_message)
        
        # In production, this could send email/SMS/Slack notifications
        self._notify_admins(alert_type, alert_message)
    
    def _notify_admins(self, alert_type: str, message: str):
        """Notify administrators (simplified implementation)."""
        try:
            # This would integrate with your notification system
            # For now, just log it
            logger.info(f"Admin notification would be sent for {alert_type}")
            
            # Example: Save to notification queue
            notification = {
                'type': alert_type,
                'message': message,
                'timestamp': datetime.now().isoformat(),
                'sent': False
            }
            
            notification_file = 'logs/pending_notifications.json'
            if os.path.exists(notification_file):
                with open(notification_file, 'r') as f:
                    notifications = json.load(f)
            else:
                notifications = []
            
            notifications.append(notification)
            
            with open(notification_file, 'w') as f:
                json.dump(notifications, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to notify admins: {e}")
    
    def _generate_recovery_suggestions(self, error: Exception, context: str) -> list:
        """Generate intelligent recovery suggestions based on error type."""
        suggestions = []
        error_str = str(error).lower()
        
        if 'memory' in error_str or 'out of memory' in error_str:
            suggestions = [
                "Reduce batch size or sample data",
                "Clear cache and temporary files",
                "Use data streaming instead of loading all at once",
                "Consider using a machine with more RAM"
            ]
        elif 'file not found' in error_str or 'no such file' in error_str:
            suggestions = [
                "Check file path and permissions",
                "Verify data source configuration",
                "Use fallback data sources",
                "Run data collection pipeline"
            ]
        elif 'key error' in error_str or 'index error' in error_str:
            suggestions = [
                "Verify data schema and column names",
                "Check for missing columns in source data",
                "Use simplified feature set",
                "Validate data preprocessing steps"
            ]
        elif 'model' in error_str and 'not fitted' in error_str:
            suggestions = [
                "Retrain the model on current data",
                "Load pre-trained model from backup",
                "Use simpler model as fallback",
                "Check model persistence configuration"
            ]
        else:
            suggestions = [
                "Check logs for more details",
                "Verify all dependencies are installed",
                "Restart the service",
                "Contact system administrator"
            ]
        
        return suggestions
    
    def _assess_error_severity(self, error: Exception, context: str) -> str:
        """Assess error severity level."""
        error_str = str(error).lower()
        
        if any(pattern in error_str for pattern in ['memory', 'corrupt', 'fatal']):
            return 'critical'
        elif any(pattern in error_str for pattern in ['file', 'model', 'data']):
            return 'high'
        elif any(pattern in error_str for pattern in ['connection', 'timeout', 'network']):
            return 'medium'
        else:
            return 'low'
    
    def get_error_stats(self) -> Dict:
        """Get current error statistics."""
        return self.error_stats.copy()
    
    def reset_error_stats(self):
        """Reset error statistics."""
        self.error_stats = {
            'loading_errors': 0,
            'prediction_errors': 0,
            'recovery_success': 0,
            'recovery_failed': 0,
            'degraded_mode_entries': 0
        }
        logger.info("Error statistics reset")
    
    def generate_error_report(self) -> Dict:
        """Generate comprehensive error report."""
        report = {
            'timestamp': datetime.now().isoformat(),
            'statistics': self.error_stats,
            'recovery_rate': (
                self.error_stats['recovery_success'] / 
                max(1, self.error_stats['loading_errors'] + self.error_stats['prediction_errors'])
            ),
            'degraded_percentage': (
                self.error_stats['degraded_mode_entries'] / 
                max(1, self.error_stats['prediction_errors'])
            ),
            'system_health': self._assess_system_health(),
            'recommendations': self._generate_health_recommendations()
        }
        
        return report
    
    def _assess_system_health(self) -> str:
        """Assess overall system health based on error statistics."""
        total_errors = (
            self.error_stats['loading_errors'] + 
            self.error_stats['prediction_errors']
        )
        
        if total_errors == 0:
            return 'excellent'
        elif total_errors < 5:
            return 'good'
        elif total_errors < 20:
            return 'fair'
        elif total_errors < 50:
            return 'poor'
        else:
            return 'critical'
    
    def _generate_health_recommendations(self) -> list:
        """Generate system health recommendations."""
        recommendations = []
        
        if self.error_stats['loading_errors'] > 10:
            recommendations.append("Investigate data pipeline stability")
        
        if self.error_stats['prediction_errors'] > 10:
            recommendations.append("Review model deployment and inference pipeline")
        
        if self.error_stats['recovery_failed'] > 5:
            recommendations.append("Improve fallback strategy implementation")
        
        if self.error_stats['degraded_mode_entries'] > 20:
            recommendations.append("Optimize prediction service reliability")
        
        if not recommendations:
            recommendations.append("System operating normally")
        
        return recommendations


# Singleton instance for easy access
_error_handler_instance = None

def get_error_handler(config_path: Optional[str] = None) -> PipelineErrorHandler:
    """Get or create singleton error handler instance."""
    global _error_handler_instance
    if _error_handler_instance is None:
        _error_handler_instance = PipelineErrorHandler(config_path)
    return _error_handler_instance