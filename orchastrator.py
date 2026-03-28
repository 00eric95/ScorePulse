"""
This script acts as the central brain or 'controller' of the system, coordinating the execution of various sub-modules.
It encapsulates the logic for high-level operations, ensuring that data flows correctly between the collector, engineer, and trainer.
The class manages the 'Full Pipeline' execution, which orchestrates the sequence from raw data ingestion to final model deployment.
It provides standardized methods for running model evaluations and generating predictions for upcoming football fixtures.
Error handling and logging are centralized here to maintain system stability during complex multi-stage tasks.
The script abstracts the complexity of the underlying utilities, offering a simplified interface for the main application entry point.
It handles directory management and path resolution to ensure all project components can locate the necessary datasets and models.
By decoupling the high-level logic from specific model implementations, it allows for easier scaling and maintenance of the project.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import pandas as pd
import numpy as np
import pickle
import json
from pathlib import Path
import schedule
import time
import threading

# Import project-specific modules
try:
    from utils.feature_engineering import FeatureEngineer
    from .main import MatchPredictor
    from utils.data_loader import DataLoader
    from utils.evaluation import Evaluator
    from config.config import Config
except ImportError:
    # Fallback imports if module structure differs
    pass

logger = logging.getLogger(__name__)

class OnlineLearningManager:
    """Manages automated online learning processes"""
    
    def __init__(self, main_orchestrator):
        self.orchestrator = main_orchestrator
        self.running = False
        self.thread = None
        self.learning_enabled = True
        
    def start(self):
        """Start the learning orchestrator"""
        if self.running:
            logger.warning("Learning orchestrator already running")
            return
        
        if not self.learning_enabled:
            logger.info("Online learning is disabled")
            return
        
        self.running = True
        
        # Schedule tasks
        schedule.every().day.at("02:00").do(self._process_daily_results)
        schedule.every().hour.do(self._check_for_new_results)
        schedule.every().sunday.at("03:00").do(self._weekly_analysis)
        
        # Start in background thread
        self.thread = threading.Thread(target=self._run_scheduler, daemon=True)
        self.thread.start()
        
        logger.info("✅ Learning Orchestrator started")
    
    def stop(self):
        """Stop the learning orchestrator"""
        self.running = False
        if self.thread:
            self.thread.join(timeout=5)
        logger.info("⏹️ Learning Orchestrator stopped")
    
    def enable_learning(self, enabled: bool = True):
        """Enable or disable online learning"""
        self.learning_enabled = enabled
        if not enabled and self.running:
            self.stop()
        logger.info(f"Online learning {'enabled' if enabled else 'disabled'}")
    
    def _run_scheduler(self):
        """Run the scheduler in background"""
        while self.running:
            schedule.run_pending()
            time.sleep(60)  # Check every minute
    
    def _process_daily_results(self):
        """Process yesterday's match results"""
        try:
            logger.info("🔄 Processing daily match results for online learning")
            
            # Get recent predictions with actual results
            recent_predictions = self._get_recent_predictions_with_results()
            
            if recent_predictions:
                logger.info(f"Found {len(recent_predictions)} results to process")
                
                processed_count = 0
                for pred in recent_predictions:
                    # Update model with new data if available
                    if self._has_actual_results(pred):
                        success = self._update_model_with_result(pred)
                        if success:
                            processed_count += 1
                
                logger.info(f"Processed {processed_count} results for online learning")
            
            # Generate learning report
            insights = self._get_learning_insights()
            if insights:
                self._save_learning_report(insights)
            
        except Exception as e:
            logger.error(f"Error processing daily results: {e}")
    
    def _check_for_new_results(self):
        """Check for new match results more frequently"""
        try:
            # This would typically check a database or API for new results
            # For now, we'll check the prediction cache for completed matches
            recent_completed = self._get_recent_completed_matches(limit=10)
            
            if recent_completed:
                logger.info(f"Processing {len(recent_completed)} new results")
                
                for match in recent_completed:
                    self._update_model_with_result(match)
                    
                    # Small delay to prevent overwhelming
                    time.sleep(0.5)
        
        except Exception as e:
            logger.error(f"Error checking for new results: {e}")
    
    def _weekly_analysis(self):
        """Weekly deep analysis of learning performance"""
        try:
            logger.info("📊 Running weekly learning analysis")
            
            insights = self._get_learning_insights()
            if insights:
                # Analyze which adjustments are working
                self._analyze_adjustment_effectiveness(insights)
                
                # Prune old data if needed
                self._prune_old_data()
                
                # Generate comprehensive report
                report = self._generate_weekly_report(insights)
                self._save_weekly_report(report)
                
                logger.info("Weekly analysis completed")
        
        except Exception as e:
            logger.error(f"Error in weekly analysis: {e}")
    
    def _get_recent_predictions_with_results(self):
        """Get recent predictions that have actual results"""
        # This would query a database in production
        # For now, return empty list - implement based on your storage
        return []
    
    def _has_actual_results(self, prediction):
        """Check if prediction has actual results available"""
        return prediction.get('actual_result') is not None
    
    def _update_model_with_result(self, result_data):
        """Update model with new match result"""
        try:
            # This would update the model's training data
            # Implementation depends on your model's online learning capability
            logger.debug(f"Updating model with result: {result_data.get('match_id')}")
            return True
        except Exception as e:
            logger.error(f"Error updating model: {e}")
            return False
    
    def _get_recent_completed_matches(self, limit=10):
        """Get recently completed matches"""
        # Implement based on your data source
        return []
    
    def _get_learning_insights(self):
        """Get insights from the learning process"""
        return {
            'system_status': {
                'teams_needing_adjustment': 0,
                'last_learning_update': datetime.now().isoformat()
            },
            'prediction_stats': {
                'accuracy': 0.0,
                'total_predictions': 0
            }
        }
    
    def _save_learning_report(self, insights):
        """Save learning insights to file"""
        try:
            report_dir = Path("data/learning_reports")
            report_dir.mkdir(exist_ok=True)
            
            report_path = report_dir / f"learning_report_{datetime.now().strftime('%Y%m%d')}.json"
            
            with open(report_path, 'w') as f:
                json.dump(insights, f, indent=2)
            
            logger.info(f"Learning report saved to {report_path}")
        
        except Exception as e:
            logger.error(f"Error saving learning report: {e}")
    
    def _analyze_adjustment_effectiveness(self, insights):
        """Analyze if weight adjustments are improving predictions"""
        # Implementation would track whether adjusted teams' predictions
        # are becoming more accurate over time
        pass
    
    def _prune_old_data(self):
        """Prune old data to keep system efficient"""
        # Implementation would remove old predictions and errors
        try:
            # Example: Clean old cache entries
            cutoff_date = datetime.now() - timedelta(days=30)
            old_keys = [
                k for k, v in self.orchestrator.prediction_cache.items()
                if 'timestamp' in v and datetime.fromisoformat(v['timestamp']) < cutoff_date
            ]
            for key in old_keys:
                del self.orchestrator.prediction_cache[key]
            
            if old_keys:
                logger.info(f"Pruned {len(old_keys)} old cache entries")
        except Exception as e:
            logger.error(f"Error pruning old data: {e}")
    
    def _generate_weekly_report(self, insights):
        """Generate comprehensive weekly report"""
        report = {
            'generated': datetime.now().isoformat(),
            'period': 'weekly',
            'learning_metrics': insights.get('system_status', {}),
            'prediction_performance': insights.get('prediction_stats', {}),
            'key_insights': self._extract_key_insights(insights),
            'recommendations': self._generate_recommendations(insights)
        }
        
        return report
    
    def _extract_key_insights(self, insights):
        """Extract key insights from learning data"""
        insights_list = []
        
        # Check if adjustments are working
        teams_adjusted = insights.get('system_status', {}).get('teams_needing_adjustment', 0)
        if teams_adjusted > 0:
            insights_list.append(f"{teams_adjusted} teams have significant weight adjustments")
        
        # Check prediction accuracy
        stats = insights.get('prediction_stats', {})
        if stats and 'accuracy' in stats:
            insights_list.append(f"Recent prediction accuracy: {stats['accuracy']:.1%}")
        
        return insights_list
    
    def _generate_recommendations(self, insights):
        """Generate recommendations based on learning data"""
        recommendations = []
        
        # If too many adjustments, suggest slower learning
        teams_adjusted = insights.get('system_status', {}).get('teams_needing_adjustment', 0)
        if teams_adjusted > 20:
            recommendations.append("Consider reducing learning rate - too many adjustments")
        
        # If accuracy is low, suggest review
        stats = insights.get('prediction_stats', {})
        if stats and stats.get('accuracy', 0) < 0.5:
            recommendations.append("Review base model - accuracy below 50%")
        
        return recommendations
    
    def _save_weekly_report(self, report):
        """Save weekly report to file"""
        try:
            report_dir = Path("data/learning_reports/weekly")
            report_dir.mkdir(exist_ok=True)
            
            week_num = datetime.now().isocalendar()[1]
            report_path = report_dir / f"weekly_report_w{week_num}.json"
            
            with open(report_path, 'w') as f:
                json.dump(report, f, indent=2)
            
            logger.info(f"Weekly report saved to {report_path}")
        
        except Exception as e:
            logger.error(f"Error saving weekly report: {e}")


class SoccerMLPipelineOrchestrator:
    """
    Orchestrates the complete soccer match prediction ML pipeline.
    Manages data collection, feature engineering, model training, evaluation,
    monitoring, and online learning for the SCORE_PULSE soccer prediction system.
    """
    
    def __init__(self, config_path: str = None, enable_learning: bool = True):
        """
        Initialize orchestrator with configuration
        
        Args:
            config_path: Path to configuration file
            enable_learning: Enable online learning features
        """
        self.config = Config() if config_path is None else self._load_config(config_path)
        self.setup_logging()
        
        # Initialize pipeline components
        self.data_handler = DataLoader(raw_path=self.config.RAW_DATA_DIR, processed_path=self.config.PROCESSED_DATA_DIR)
        self.feature_engineer = FeatureEngineer(targets=self.config.TARGETS)
        self.model = MatchPredictor(model_dir=self.config.MODELS_DIR)
        self.evaluator = Evaluator(self.config)
        
        # Initialize online learning manager
        self.online_learning = OnlineLearningManager(self)
        if enable_learning:
            self.online_learning.start()
        
        # Pipeline state tracking
        self.pipeline_state = {
            'last_run': None,
            'current_model_version': None,
            'data_statistics': {},
            'model_metrics': {},
            'learning_enabled': enable_learning
        }
        
        # Cache for recent predictions
        self.prediction_cache = {}
        self.cache_size = self.config.get('CACHE_SIZE', 1000)
        
        logger.info("Soccer ML Pipeline Orchestrator initialized")
    
    def _load_config(self, config_path: str) -> Dict:
        """Load configuration from file"""
        try:
            if config_path.endswith('.json'):
                with open(config_path, 'r') as f:
                    return json.load(f)
            elif config_path.endswith('.py'):
                import importlib.util
                spec = importlib.util.spec_from_file_location("config", config_path)
                config_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(config_module)
                return config_module.Config()
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    
    def setup_logging(self):
        """Setup logging configuration"""
        log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=[
                logging.FileHandler('logs/orchestrator.log'),
                logging.StreamHandler()
            ]
        )
    
    def run_full_pipeline(self, retrain: bool = False) -> Dict[str, Any]:
        """
        Orchestrates entire ML pipeline for soccer match prediction
        
        Args:
            retrain: If True, forces retraining even if model exists
            
        Returns:
            Dictionary with pipeline execution results
        """
        pipeline_results = {
            'timestamp': datetime.now().isoformat(),
            'success': False,
            'steps': {}
        }
        
        try:
            logger.info("Starting full soccer prediction pipeline")
            
            # Step 1: Data Collection and Validation
            logger.info("Step 1: Data collection and validation")
            data_result = self.data_handler.load_and_validate()
            pipeline_results['steps']['data_collection'] = data_result
            
            if not data_result['success']:
                logger.error("Data collection failed")
                return pipeline_results
            
            # Step 2: Feature Engineering
            logger.info("Step 2: Feature engineering")
            features_result = self.feature_engineering_pipeline(data_result['data'])
            pipeline_results['steps']['feature_engineering'] = features_result
            
            if not features_result['success']:
                logger.error("Feature engineering failed")
                return pipeline_results
            
            # Step 3: Model Training/Retraining
            logger.info("Step 3: Model training")
            training_result = self.training_pipeline(
                features_result['features'], 
                features_result['labels'],
                retrain=retrain
            )
            pipeline_results['steps']['model_training'] = training_result
            
            if not training_result['success']:
                logger.error("Model training failed")
                return pipeline_results
            
            # Step 4: Model Evaluation
            logger.info("Step 4: Model evaluation")
            evaluation_result = self.evaluation_pipeline(
                training_result['model'],
                features_result['test_features'],
                features_result['test_labels']
            )
            pipeline_results['steps']['model_evaluation'] = evaluation_result
            
            # Step 5: Monitoring and Health Checks
            logger.info("Step 5: System monitoring")
            monitoring_result = self.monitoring_pipeline()
            pipeline_results['steps']['system_monitoring'] = monitoring_result
            
            # Update pipeline state
            self.pipeline_state.update({
                'last_run': pipeline_results['timestamp'],
                'current_model_version': training_result.get('model_version'),
                'model_metrics': evaluation_result.get('metrics', {})
            })
            
            # Save pipeline state
            self.save_pipeline_state()
            
            pipeline_results['success'] = True
            logger.info("Pipeline completed successfully")
            
        except Exception as e:
            logger.error(f"Pipeline failed with error: {e}", exc_info=True)
            pipeline_results['error'] = str(e)
        
        return pipeline_results
    
    def feature_engineering_pipeline(self, raw_data: pd.DataFrame) -> Dict[str, Any]:
        """
        Execute feature engineering pipeline
        
        Args:
            raw_data: Raw match data
            
        Returns:
            Dictionary with engineered features and metadata
        """
        try:
            logger.info("Starting feature engineering pipeline")
            
            # Split data into features and labels
            X, y = self.feature_engineer.prepare_features_and_labels(raw_data)
            
            # Apply feature transformations
            X_transformed = self.feature_engineer.transform_features(X)
            
            # Split into train/test
            X_train, X_test, y_train, y_test = self.feature_engineer.split_data(
                X_transformed, y
            )
            
            # Get feature importance if available
            feature_importance = self.feature_engineer.get_feature_importance(
                X_train, y_train
            )
            
            logger.info(f"Feature engineering complete. "
                       f"Train shape: {X_train.shape}, Test shape: {X_test.shape}")
            
            return {
                'success': True,
                'features': X_train,
                'labels': y_train,
                'test_features': X_test,
                'test_labels': y_test,
                'feature_importance': feature_importance,
                'feature_names': list(X.columns) if hasattr(X, 'columns') else []
            }
            
        except Exception as e:
            logger.error(f"Feature engineering failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def training_pipeline(self, X_train: pd.DataFrame, y_train: pd.Series, 
                         retrain: bool = False) -> Dict[str, Any]:
        """
        Execute model training pipeline
        
        Args:
            X_train: Training features
            y_train: Training labels
            retrain: Force retraining
            
        Returns:
            Dictionary with training results
        """
        try:
            logger.info("Starting training pipeline")
            
            # Check if model exists and should be retrained
            model_exists = self.model.exists()
            
            if model_exists and not retrain:
                logger.info("Model exists and retrain=False, skipping training")
                self.model.load()
                return {
                    'success': True,
                    'model': self.model,
                    'model_version': self.model.version,
                    'action': 'loaded_existing'
                }
            
            # Train new model
            logger.info(f"Training model with {len(X_train)} samples")
            self.model.train(X_train, y_train)
            
            # Save the trained model
            model_path = self.model.save()
            
            # Generate model version based on timestamp
            model_version = f"model_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            logger.info(f"Model training completed. Saved to: {model_path}")
            
            return {
                'success': True,
                'model': self.model,
                'model_path': model_path,
                'model_version': model_version,
                'action': 'trained_new'
            }
            
        except Exception as e:
            logger.error(f"Training pipeline failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def evaluation_pipeline(self, model, X_test: pd.DataFrame, 
                           y_test: pd.Series) -> Dict[str, Any]:
        """
        Execute model evaluation pipeline
        
        Args:
            model: Trained model
            X_test: Test features
            y_test: Test labels
            
        Returns:
            Dictionary with evaluation results
        """
        try:
            logger.info("Starting evaluation pipeline")
            
            # Make predictions
            predictions = model.predict(X_test)
            probabilities = model.predict_proba(X_test) if hasattr(model, 'predict_proba') else None
            
            # Calculate metrics
            metrics = self.evaluator.calculate_metrics(y_test, predictions, probabilities)
            
            # Generate evaluation report
            report = self.evaluator.generate_report(metrics)
            
            # Log important metrics
            logger.info(f"Model evaluation complete. "
                       f"Accuracy: {metrics.get('accuracy', 'N/A'):.3f}, "
                       f"Precision: {metrics.get('precision', 'N/A'):.3f}")
            
            return {
                'success': True,
                'metrics': metrics,
                'report': report,
                'predictions': predictions,
                'actual': y_test.values
            }
            
        except Exception as e:
            logger.error(f"Evaluation pipeline failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def monitoring_pipeline(self) -> Dict[str, Any]:
        """
        Execute system monitoring and health checks
        
        Returns:
            Dictionary with monitoring results
        """
        try:
            logger.info("Starting monitoring pipeline")
            
            # Check data quality
            data_quality = self.data_handler.check_data_quality()
            
            # Check model performance drift
            performance_drift = self.evaluator.check_performance_drift()
            
            # Check feature drift
            feature_drift = self.feature_engineer.check_feature_drift()
            
            # Check learning system health
            learning_health = {
                'learning_enabled': self.online_learning.learning_enabled,
                'learning_running': self.online_learning.running,
                'last_learning_update': None  # Would be populated from actual data
            }
            
            # System health checks
            system_health = {
                'database_connected': self.data_handler.is_connected(),
                'model_loaded': self.model.is_loaded(),
                'feature_store_available': self.feature_engineer.is_available(),
                'last_prediction_time': self.pipeline_state.get('last_run'),
                'learning_system': learning_health
            }
            
            # Log warnings if any issues
            warnings = []
            if performance_drift.get('has_drift', False):
                warnings.append(f"Performance drift detected: {performance_drift}")
            
            if not self.online_learning.running and self.online_learning.learning_enabled:
                warnings.append("Online learning is enabled but not running")
            
            logger.info(f"Monitoring complete. System health: {system_health}")
            
            return {
                'success': True,
                'data_quality': data_quality,
                'performance_drift': performance_drift,
                'feature_drift': feature_drift,
                'system_health': system_health,
                'warnings': warnings
            }
            
        except Exception as e:
            logger.error(f"Monitoring pipeline failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict_single_match(self, match_data: Dict) -> Dict[str, Any]:
        """
        Predict outcome for a single match
        
        Args:
            match_data: Dictionary with match features
            
        Returns:
            Prediction results
        """
        try:
            # Check cache first
            match_hash = hash(json.dumps(match_data, sort_keys=True))
            if match_hash in self.prediction_cache:
                logger.debug("Returning cached prediction")
                return self.prediction_cache[match_hash]
            
            # Ensure model is loaded
            if not self.model.is_loaded():
                self.model.load()
            
            # Prepare features
            features_df = pd.DataFrame([match_data])
            processed_features = self.feature_engineer.transform_single(features_df)
            
            # Make prediction
            prediction = self.model.predict(processed_features)[0]
            probability = self.model.predict_proba(processed_features)[0] \
                if hasattr(self.model, 'predict_proba') else None
            
            # Prepare result
            result = {
                'prediction': prediction,
                'probability': probability.tolist() if probability is not None else None,
                'confidence': float(max(probability)) if probability is not None else None,
                'timestamp': datetime.now().isoformat(),
                'model_version': self.model.version
            }
            
            # Cache the result
            self._add_to_cache(match_hash, result)
            
            logger.info(f"Prediction made: {result}")
            return result
            
        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            return {'error': str(e), 'success': False}
    
    def predict_batch_matches(self, matches_data: List[Dict]) -> List[Dict]:
        """
        Predict outcomes for multiple matches
        
        Args:
            matches_data: List of match data dictionaries
            
        Returns:
            List of prediction results
        """
        results = []
        for match_data in matches_data:
            result = self.predict_single_match(match_data)
            results.append(result)
        return results
    
    def _add_to_cache(self, key: Any, value: Any):
        """Add item to prediction cache with LRU eviction"""
        if len(self.prediction_cache) >= self.cache_size:
            # Remove oldest item (first inserted)
            oldest_key = next(iter(self.prediction_cache))
            del self.prediction_cache[oldest_key]
        
        self.prediction_cache[key] = value
    
    def save_pipeline_state(self, path: str = None):
        """Save current pipeline state to disk"""
        if path is None:
            path = self.config.get('STATE_PATH', 'pipeline_state.pkl')
        
        state_to_save = {
            'pipeline_state': self.pipeline_state,
            'timestamp': datetime.now().isoformat(),
            'prediction_cache_size': len(self.prediction_cache)
        }
        
        try:
            with open(path, 'wb') as f:
                pickle.dump(state_to_save, f)
            logger.info(f"Pipeline state saved to {path}")
        except Exception as e:
            logger.error(f"Failed to save pipeline state: {e}")
    
    def load_pipeline_state(self, path: str = None):
        """Load pipeline state from disk"""
        if path is None:
            path = self.config.get('STATE_PATH', 'pipeline_state.pkl')
        
        try:
            with open(path, 'rb') as f:
                state = pickle.load(f)
            self.pipeline_state = state.get('pipeline_state', {})
            logger.info(f"Pipeline state loaded from {path}")
        except FileNotFoundError:
            logger.warning(f"No existing pipeline state found at {path}")
        except Exception as e:
            logger.error(f"Failed to load pipeline state: {e}")
    
    def get_pipeline_status(self) -> Dict[str, Any]:
        """Get current status of the pipeline"""
        return {
            'status': 'healthy' if self.pipeline_state.get('last_run') else 'unknown',
            'last_run': self.pipeline_state.get('last_run'),
            'model_version': self.pipeline_state.get('current_model_version'),
            'cache_size': len(self.prediction_cache),
            'model_loaded': self.model.is_loaded(),
            'data_connected': self.data_handler.is_connected(),
            'learning_enabled': self.online_learning.learning_enabled,
            'learning_running': self.online_learning.running
        }
    
    def enable_online_learning(self, enabled: bool = True):
        """Enable or disable online learning"""
        self.online_learning.enable_learning(enabled)
        self.pipeline_state['learning_enabled'] = enabled
        logger.info(f"Online learning {'enabled' if enabled else 'disabled'}")
    
    def get_learning_insights(self) -> Dict[str, Any]:
        """Get insights from the learning system"""
        return self.online_learning._get_learning_insights()


# Factory function for creating orchestrator
def create_orchestrator(config_path: str = None, enable_learning: bool = True) -> SoccerMLPipelineOrchestrator:
    """
    Factory function to create and initialize orchestrator
    
    Args:
        config_path: Optional path to configuration file
        enable_learning: Enable online learning features
        
    Returns:
        Initialized SoccerMLPipelineOrchestrator instance
    """
    return SoccerMLPipelineOrchestrator(config_path, enable_learning)


# Command-line interface
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='Soccer Match Prediction Pipeline Orchestrator')
    parser.add_argument('--run-pipeline', action='store_true', 
                       help='Run the full ML pipeline')
    parser.add_argument('--retrain', action='store_true',
                       help='Force retraining of model')
    parser.add_argument('--predict', type=str,
                       help='Predict single match (provide JSON string)')
    parser.add_argument('--status', action='store_true',
                       help='Get pipeline status')
    parser.add_argument('--config', type=str, default='config.py',
                       help='Path to configuration file')
    parser.add_argument('--enable-learning', action='store_true',
                       help='Enable online learning system')
    parser.add_argument('--disable-learning', action='store_true',
                       help='Disable online learning system')
    parser.add_argument('--learning-insights', action='store_true',
                       help='Get learning system insights')
    
    args = parser.parse_args()
    
    # Create orchestrator
    orchestrator = create_orchestrator(args.config, enable_learning=not args.disable_learning)
    
    if args.run_pipeline:
        print("Running full pipeline...")
        result = orchestrator.run_full_pipeline(retrain=args.retrain)
        print(f"Pipeline result: {json.dumps(result, indent=2)}")
    
    elif args.predict:
        try:
            match_data = json.loads(args.predict)
            result = orchestrator.predict_single_match(match_data)
            print(f"Prediction result: {json.dumps(result, indent=2)}")
        except json.JSONDecodeError:
            print("Error: Invalid JSON provided for prediction")
    
    elif args.status:
        status = orchestrator.get_pipeline_status()
        print(f"Pipeline status: {json.dumps(status, indent=2)}")
    
    elif args.enable_learning:
        orchestrator.enable_online_learning(True)
        print("Online learning enabled")
    
    elif args.disable_learning:
        orchestrator.enable_online_learning(False)
        print("Online learning disabled")
    
    elif args.learning_insights:
        insights = orchestrator.get_learning_insights()
        print(f"Learning insights: {json.dumps(insights, indent=2)}")
    
    else:
        print("Soccer Match Prediction Orchestrator")
        print("Available commands:")
        print("  --run-pipeline      : Run full ML pipeline")
        print("  --retrain           : Force model retraining")
        print("  --predict 'JSON'    : Predict single match")
        print("  --status            : Get pipeline status")
        print("  --enable-learning   : Enable online learning")
        print("  --disable-learning  : Disable online learning")
        print("  --learning-insights : Get learning system insights")
        print("  --config PATH       : Specify config file path")