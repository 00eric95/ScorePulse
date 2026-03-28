"""
ScorePulse AI Chatbot with Integrated Model Evaluation System
Enhanced with Advanced ML Evaluation Capabilities
"""

import os
import sys
import json
import logging
import threading
import asyncio
import time
import queue
import sqlite3
import hashlib
import uuid
import re
import inspect
import traceback
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')  # For server use
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix,
                           mean_absolute_error, mean_squared_error, r2_score,
                           precision_score, recall_score, f1_score, roc_auc_score,
                           roc_curve, auc, precision_recall_curve, average_precision_score,
                           mean_absolute_percentage_error, explained_variance_score)
import warnings
warnings.filterwarnings('ignore')

# Import project modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models import User, Prediction, Payment, ChatMessage, ChatSession, SystemLog, ModelEvaluation
from app import db

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot_evaluation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# ENHANCED ENUMS & DATA CLASSES WITH EVALUATION
# ============================================================================

class EvaluationType(Enum):
    """Types of model evaluations"""
    CLASSIFICATION = "classification"
    REGRESSION = "regression"
    ROI_ANALYSIS = "roi_analysis"
    MODEL_COMPARISON = "model_comparison"
    FEATURE_IMPORTANCE = "feature_importance"
    CONFUSION_MATRIX = "confusion_matrix"
    ROC_CURVE = "roc_curve"
    RESIDUAL_ANALYSIS = "residual_analysis"
    
class EvaluationStatus(Enum):
    """Status of evaluations"""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    INTERPRETING = "interpreting"
    
@dataclass
class EvaluationRequest:
    """Data structure for evaluation requests"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    evaluation_type: EvaluationType = EvaluationType.CLASSIFICATION
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: EvaluationStatus = EvaluationStatus.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    completed_at: Optional[datetime] = None
    results: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    plot_paths: List[str] = field(default_factory=list)
    interpretation: Optional[str] = None
    
@dataclass
class ModelComparisonResult:
    """Data structure for model comparison results"""
    model_name: str
    metrics: Dict[str, float]
    ranking: int
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    
@dataclass
class ROIAnalysisResult:
    """Data structure for ROI analysis results"""
    strategy: str
    total_bets: int
    wins: int
    losses: int
    win_rate: float
    total_profit: float
    roi_percent: float
    final_bankroll: float
    max_drawdown: float
    sharpe_ratio: float
    profit_factor: float
    risk_assessment: str  # low, medium, high
    sustainability_score: float  # 0-100
    
@dataclass
class ClassificationInterpretation:
    """Data structure for classification model interpretation"""
    overall_performance: str  # excellent, good, fair, poor
    key_strengths: List[str]
    key_weaknesses: List[str]
    business_impact: str
    deployment_recommendation: str  # production, staging, rework
    confidence_level: str  # high, medium, low
    actionable_insights: List[str]
    next_steps: List[str]

# ============================================================================
# ENHANCED EVALUATION ENGINE
# ============================================================================

class EvaluationEngine:
    """Comprehensive model evaluation and interpretation engine"""
    
    def __init__(self, plots_dir: str = None):
        """Initialize evaluation engine"""
        self.plots_dir = plots_dir or os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'static', 'evaluation_plots'
        )
        
        # Create plots directory
        os.makedirs(self.plots_dir, exist_ok=True)
        
        # Subdirectories for different plot types
        self.subdirs = {
            'confusion_matrices': os.path.join(self.plots_dir, 'confusion_matrices'),
            'roc_curves': os.path.join(self.plots_dir, 'roc_curves'),
            'regression_analysis': os.path.join(self.plots_dir, 'regression_analysis'),
            'roi_analysis': os.path.join(self.plots_dir, 'roi_analysis'),
            'comparative': os.path.join(self.plots_dir, 'comparative'),
            'feature_importance': os.path.join(self.plots_dir, 'feature_importance')
        }
        
        for subdir in self.subdirs.values():
            os.makedirs(subdir, exist_ok=True)
            
        self.predictor = None # Placeholder for Orchestrator injection
        
        def set_predictor(self, predictor):
            """This is called by the Pitch Commander during register_agent"""
            self.predictor = predictor
        
        
        # Performance benchmarks
        self.benchmarks = {
            'classification': {
                'excellent': {'accuracy': 0.85, 'f1_score': 0.80, 'roc_auc': 0.85},
                'good': {'accuracy': 0.75, 'f1_score': 0.70, 'roc_auc': 0.75},
                'fair': {'accuracy': 0.65, 'f1_score': 0.60, 'roc_auc': 0.65},
                'poor': {'accuracy': 0.55, 'f1_score': 0.50, 'roc_auc': 0.55}
            },
            'regression': {
                'excellent': {'r2': 0.85, 'mae': 0.25, 'rmse': 0.30},
                'good': {'r2': 0.70, 'mae': 0.40, 'rmse': 0.50},
                'fair': {'r2': 0.55, 'mae': 0.60, 'rmse': 0.75},
                'poor': {'r2': 0.40, 'mae': 0.80, 'rmse': 1.00}
            }
        }
        
        logger.info(f"Evaluation Engine initialized. Plots directory: {self.plots_dir}")
    
    def evaluate_classification(self, y_true: np.ndarray, y_pred: np.ndarray,
                              y_prob: Optional[np.ndarray] = None,
                              class_names: Optional[List[str]] = None,
                              model_name: str = "Unknown") -> Dict[str, Any]:
        """Comprehensive classification evaluation with interpretation"""
        try:
            start_time = time.time()
            
            if class_names is None:
                unique_classes = np.unique(y_true)
                class_names = [f'Class {i}' for i in unique_classes]
            
            # Calculate metrics
            metrics = {}
            metrics['accuracy'] = accuracy_score(y_true, y_pred)
            metrics['precision'] = precision_score(y_true, y_pred, average='weighted', zero_division=0)
            metrics['recall'] = recall_score(y_true, y_pred, average='weighted', zero_division=0)
            metrics['f1_score'] = f1_score(y_true, y_pred, average='weighted', zero_division=0)
            
            # Per-class metrics
            report = classification_report(y_true, y_pred, target_names=class_names, output_dict=True)
            metrics['per_class'] = report
            
            # Confusion matrix
            cm = confusion_matrix(y_true, y_pred)
            metrics['confusion_matrix'] = cm.tolist()
            
            # ROC and PR metrics if probabilities available
            if y_prob is not None:
                try:
                    if len(np.unique(y_true)) == 2:
                        metrics['roc_auc'] = roc_auc_score(y_true, y_prob[:, 1])
                        metrics['average_precision'] = average_precision_score(y_true, y_prob[:, 1])
                    else:
                        metrics['roc_auc'] = roc_auc_score(y_true, y_prob, multi_class='ovr')
                        metrics['average_precision'] = average_precision_score(y_true, y_prob)
                except Exception as e:
                    logger.warning(f"ROC/AUC calculation failed: {e}")
                    metrics['roc_auc'] = None
                    metrics['average_precision'] = None
            
            # Generate plots
            plot_paths = self._generate_classification_plots(
                y_true, y_pred, y_prob, class_names, model_name
            )
            
            # Generate interpretation
            interpretation = self._interpret_classification_results(metrics, model_name)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            result = {
                'metrics': metrics,
                'interpretation': interpretation,
                'plot_paths': plot_paths,
                'execution_time': execution_time,
                'model_name': model_name,
                'evaluation_type': 'classification',
                'timestamp': datetime.now().isoformat(),
                'sample_size': len(y_true),
                'class_distribution': dict(zip(*np.unique(y_true, return_counts=True)))
            }
            
            logger.info(f"Classification evaluation completed for {model_name}. "
                       f"Accuracy: {metrics['accuracy']:.3f}, F1: {metrics['f1_score']:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Classification evaluation failed: {e}")
            raise
    
    def evaluate_regression(self, y_true: np.ndarray, y_pred: np.ndarray,
                          model_name: str = "Unknown") -> Dict[str, Any]:
        """Comprehensive regression evaluation with interpretation"""
        try:
            start_time = time.time()
            
            # Remove NaN values
            mask = ~(np.isnan(y_true) | np.isnan(y_pred))
            y_true = y_true[mask]
            y_pred = y_pred[mask]
            
            if len(y_true) == 0:
                raise ValueError("No valid data points after NaN removal")
            
            # Calculate metrics
            metrics = {}
            metrics['mae'] = mean_absolute_error(y_true, y_pred)
            metrics['mse'] = mean_squared_error(y_true, y_pred)
            metrics['rmse'] = np.sqrt(metrics['mse'])
            metrics['r2'] = r2_score(y_true, y_pred)
            metrics['mape'] = mean_absolute_percentage_error(y_true, y_pred)
            metrics['explained_variance'] = explained_variance_score(y_true, y_pred)
            
            # Additional metrics
            metrics['max_error'] = np.max(np.abs(y_true - y_pred))
            metrics['mean_error'] = np.mean(y_true - y_pred)
            metrics['std_error'] = np.std(y_true - y_pred)
            metrics['median_error'] = np.median(np.abs(y_true - y_pred))
            
            # Percentage within thresholds
            thresholds = [0.5, 1.0, 1.5, 2.0]
            for threshold in thresholds:
                within = np.sum(np.abs(y_true - y_pred) <= threshold) / len(y_true)
                metrics[f'within_{threshold}'] = within
            
            # Generate plots
            plot_paths = self._generate_regression_plots(y_true, y_pred, model_name)
            
            # Generate interpretation
            interpretation = self._interpret_regression_results(metrics, model_name)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            result = {
                'metrics': metrics,
                'interpretation': interpretation,
                'plot_paths': plot_paths,
                'execution_time': execution_time,
                'model_name': model_name,
                'evaluation_type': 'regression',
                'timestamp': datetime.now().isoformat(),
                'sample_size': len(y_true),
                'target_statistics': {
                    'mean': float(np.mean(y_true)),
                    'std': float(np.std(y_true)),
                    'min': float(np.min(y_true)),
                    'max': float(np.max(y_true))
                }
            }
            
            logger.info(f"Regression evaluation completed for {model_name}. "
                       f"R²: {metrics['r2']:.3f}, MAE: {metrics['mae']:.3f}")
            
            return result
            
        except Exception as e:
            logger.error(f"Regression evaluation failed: {e}")
            raise
    
    def analyze_roi(self, df: pd.DataFrame, predictions: np.ndarray,
                   target_col: str = "target", stake: float = 10.0,
                   strategy: str = 'fixed', bankroll: float = 1000.0) -> Dict[str, Any]:
        """Advanced ROI analysis with multiple betting strategies"""
        try:
            start_time = time.time()
            
            # Validate required columns
            required_cols = ['OddHome', 'OddDraw', 'OddAway']
            if not all(col in df.columns for col in required_cols):
                raise ValueError(f"Missing required columns: {required_cols}")
            
            df_reset = df.reset_index(drop=True)
            predictions = np.array(predictions)
            
            # Result mapping
            result_map = {'H': 2, 'D': 1, 'A': 0}
            
            # Initialize tracking for different strategies
            strategies = ['fixed', 'kelly', 'proportional']
            results = {s: {'bankroll': bankroll, 'equity': [bankroll], 'bets': 0, 'wins': 0}
                      for s in strategies}
            
            detailed_results = []
            
            for i, row in df_reset.iterrows():
                if i >= len(predictions):
                    break
                
                actual = self._map_outcome(row[target_col], result_map)
                prediction = self._map_outcome(predictions[i], result_map)
                
                if actual is None or prediction is None:
                    continue
                
                odds = self._get_odds(row, prediction, result_map)
                if odds < 1.01:
                    continue
                
                for strategy_type in strategies:
                    stake_amount = self._calculate_stake(strategy_type, results[strategy_type]['bankroll'],
                                                       stake, odds)
                    
                    # Ensure reasonable stake
                    stake_amount = min(stake_amount, results[strategy_type]['bankroll'] * 0.1)
                    stake_amount = max(stake_amount, 1.0)
                    
                    results[strategy_type]['bets'] += 1
                    
                    if prediction == actual:
                        profit = stake_amount * (odds - 1)
                        results[strategy_type]['bankroll'] += profit
                        results[strategy_type]['wins'] += 1
                        outcome = 'win'
                    else:
                        results[strategy_type]['bankroll'] -= stake_amount
                        outcome = 'loss'
                    
                    results[strategy_type]['equity'].append(results[strategy_type]['bankroll'])
                    
                    detailed_results.append({
                        'match_id': i,
                        'strategy': strategy_type,
                        'prediction': prediction,
                        'actual': actual,
                        'odds': odds,
                        'stake': stake_amount,
                        'outcome': outcome,
                        'profit': profit if outcome == 'win' else -stake_amount,
                        'bankroll': results[strategy_type]['bankroll']
                    })
            
            # Calculate final metrics for each strategy
            roi_analysis = {}
            for strategy_type in strategies:
                if results[strategy_type]['bets'] > 0:
                    roi_data = self._calculate_roi_metrics(results[strategy_type],
                                                         bankroll, stake, detailed_results,
                                                         strategy_type)
                    roi_analysis[strategy_type] = roi_data
            
            # Generate plots
            plot_paths = self._generate_roi_plots(results, detailed_results)
            
            # Generate interpretation
            interpretation = self._interpret_roi_results(roi_analysis)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            result = {
                'roi_analysis': roi_analysis,
                'interpretation': interpretation,
                'plot_paths': plot_paths,
                'execution_time': execution_time,
                'timestamp': datetime.now().isoformat(),
                'total_matches': len(detailed_results),
                'strategies_evaluated': list(roi_analysis.keys())
            }
            
            # Find best strategy
            best_strategy = max(roi_analysis.items(), key=lambda x: x[1]['roi_percent'])
            logger.info(f"ROI analysis completed. Best strategy: {best_strategy[0]} "
                       f"with ROI: {best_strategy[1]['roi_percent']:.1f}%")
            
            return result
            
        except Exception as e:
            logger.error(f"ROI analysis failed: {e}")
            raise
    
    def compare_models(self, models: Dict[str, Any], X_test: np.ndarray,
                      y_test: np.ndarray, task: str = 'classification') -> Dict[str, Any]:
        """Compare multiple models and provide recommendations"""
        try:
            start_time = time.time()
            
            comparison = {}
            
            for name, model in models.items():
                logger.info(f"Evaluating model: {name}")
                
                try:
                    if task == 'classification':
                        y_pred = model.predict(X_test)
                        # Try to get probabilities if available
                        try:
                            y_prob = model.predict_proba(X_test)
                        except:
                            y_prob = None
                        
                        result = self.evaluate_classification(y_test, y_pred, y_prob, model_name=name)
                        comparison[name] = {
                            'accuracy': result['metrics']['accuracy'],
                            'f1_score': result['metrics']['f1_score'],
                            'precision': result['metrics']['precision'],
                            'recall': result['metrics']['recall'],
                            'roc_auc': result['metrics'].get('roc_auc', None),
                            'full_result': result
                        }
                    else:  # regression
                        y_pred = model.predict(X_test)
                        result = self.evaluate_regression(y_test, y_pred, model_name=name)
                        comparison[name] = {
                            'mae': result['metrics']['mae'],
                            'rmse': result['metrics']['rmse'],
                            'r2': result['metrics']['r2'],
                            'mape': result['metrics']['mape'],
                            'full_result': result
                        }
                        
                except Exception as e:
                    logger.error(f"Error evaluating model {name}: {e}")
                    comparison[name] = {'error': str(e)}
            
            # Rank models
            ranked_models = self._rank_models(comparison, task)
            
            # Generate comparison plots
            plot_paths = self._generate_comparison_plots(comparison, task)
            
            # Generate interpretation
            interpretation = self._interpret_comparison_results(ranked_models, task)
            
            # Calculate execution time
            execution_time = time.time() - start_time
            
            result = {
                'comparison': comparison,
                'ranked_models': ranked_models,
                'interpretation': interpretation,
                'plot_paths': plot_paths,
                'execution_time': execution_time,
                'task': task,
                'timestamp': datetime.now().isoformat(),
                'models_evaluated': len(models),
                'best_model': ranked_models[0]['model_name'] if ranked_models else None
            }
            
            logger.info(f"Model comparison completed. Best model: {result['best_model']}")
            
            return result
            
        except Exception as e:
            logger.error(f"Model comparison failed: {e}")
            raise
    
    # ==========================================================================
    # INTERPRETATION METHODS
    # ==========================================================================
    
    def _interpret_classification_results(self, metrics: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Interpret classification model results"""
        interpretation = {
            'model_name': model_name,
            'overall_performance': 'unknown',
            'performance_level': 'unknown',
            'key_strengths': [],
            'key_weaknesses': [],
            'business_impact': 'unknown',
            'deployment_recommendation': 'unknown',
            'confidence_level': 'unknown',
            'actionable_insights': [],
            'next_steps': []
        }
        
        accuracy = metrics.get('accuracy', 0)
        f1_score_val = metrics.get('f1_score', 0)
        roc_auc = metrics.get('roc_auc', 0)
        
        # Determine overall performance
        if accuracy >= 0.85 and f1_score_val >= 0.80 and (roc_auc is None or roc_auc >= 0.85):
            interpretation['overall_performance'] = 'Excellent'
            interpretation['performance_level'] = 'excellent'
            interpretation['deployment_recommendation'] = 'Production Ready'
            interpretation['confidence_level'] = 'High'
            interpretation['business_impact'] = 'High - Can be deployed with high confidence'
        elif accuracy >= 0.75 and f1_score_val >= 0.70 and (roc_auc is None or roc_auc >= 0.75):
            interpretation['overall_performance'] = 'Good'
            interpretation['performance_level'] = 'good'
            interpretation['deployment_recommendation'] = 'Staging - Monitor Closely'
            interpretation['confidence_level'] = 'Medium'
            interpretation['business_impact'] = 'Moderate - May need some monitoring'
        elif accuracy >= 0.65 and f1_score_val >= 0.60 and (roc_auc is None or roc_auc >= 0.65):
            interpretation['overall_performance'] = 'Fair'
            interpretation['performance_level'] = 'fair'
            interpretation['deployment_recommendation'] = 'Further Optimization Needed'
            interpretation['confidence_level'] = 'Low'
            interpretation['business_impact'] = 'Low - Needs improvement before deployment'
        else:
            interpretation['overall_performance'] = 'Poor'
            interpretation['performance_level'] = 'poor'
            interpretation['deployment_recommendation'] = 'Rework Required'
            interpretation['confidence_level'] = 'Very Low'
            interpretation['business_impact'] = 'Very Low - Not ready for deployment'
        
        # Identify strengths
        if accuracy > 0.8:
            interpretation['key_strengths'].append(f"High accuracy ({accuracy:.1%})")
        if f1_score_val > 0.75:
            interpretation['key_strengths'].append(f"Good F1-score balance ({f1_score_val:.1%})")
        if roc_auc and roc_auc > 0.8:
            interpretation['key_strengths'].append(f"Strong ROC-AUC ({roc_auc:.3f})")
        
        # Identify weaknesses
        if accuracy < 0.7:
            interpretation['key_weaknesses'].append(f"Low accuracy ({accuracy:.1%})")
        if 'per_class' in metrics:
            class_report = metrics['per_class']
            for class_name, metrics_dict in class_report.items():
                if isinstance(metrics_dict, dict) and metrics_dict.get('f1-score', 1) < 0.6:
                    interpretation['key_weaknesses'].append(f"Poor performance on {class_name}")
        
        # Actionable insights
        if interpretation['performance_level'] in ['fair', 'poor']:
            interpretation['actionable_insights'].append("Consider collecting more training data")
            interpretation['actionable_insights'].append("Try different model architectures")
            interpretation['actionable_insights'].append("Review feature engineering process")
        else:
            interpretation['actionable_insights'].append("Model is performing well")
            interpretation['actionable_insights'].append("Consider A/B testing in production")
            interpretation['actionable_insights'].append("Monitor for concept drift")
        
        # Next steps
        interpretation['next_steps'] = [
            "Review confusion matrix for specific error patterns",
            "Analyze feature importance if available",
            "Test on new, unseen data",
            "Document model performance metrics"
        ]
        
        return interpretation
    
    def _interpret_regression_results(self, metrics: Dict[str, Any], model_name: str) -> Dict[str, Any]:
        """Interpret regression model results"""
        interpretation = {
            'model_name': model_name,
            'overall_performance': 'unknown',
            'performance_level': 'unknown',
            'key_strengths': [],
            'key_weaknesses': [],
            'business_impact': 'unknown',
            'deployment_recommendation': 'unknown',
            'confidence_level': 'unknown',
            'actionable_insights': [],
            'next_steps': []
        }
        
        r2 = metrics.get('r2', 0)
        mae = metrics.get('mae', float('inf'))
        rmse = metrics.get('rmse', float('inf'))
        
        # Determine overall performance
        if r2 >= 0.85 and mae <= 0.25 and rmse <= 0.30:
            interpretation['overall_performance'] = 'Excellent'
            interpretation['performance_level'] = 'excellent'
            interpretation['deployment_recommendation'] = 'Production Ready'
            interpretation['confidence_level'] = 'High'
            interpretation['business_impact'] = 'High - Very accurate predictions'
        elif r2 >= 0.70 and mae <= 0.40 and rmse <= 0.50:
            interpretation['overall_performance'] = 'Good'
            interpretation['performance_level'] = 'good'
            interpretation['deployment_recommendation'] = 'Staging - Monitor Closely'
            interpretation['confidence_level'] = 'Medium'
            interpretation['business_impact'] = 'Moderate - Useful predictions with some error'
        elif r2 >= 0.55 and mae <= 0.60 and rmse <= 0.75:
            interpretation['overall_performance'] = 'Fair'
            interpretation['performance_level'] = 'fair'
            interpretation['deployment_recommendation'] = 'Further Optimization Needed'
            interpretation['confidence_level'] = 'Low'
            interpretation['business_impact'] = 'Low - Limited predictive power'
        else:
            interpretation['overall_performance'] = 'Poor'
            interpretation['performance_level'] = 'poor'
            interpretation['deployment_recommendation'] = 'Rework Required'
            interpretation['confidence_level'] = 'Very Low'
            interpretation['business_impact'] = 'Very Low - Not reliable for predictions'
        
        # Identify strengths
        if r2 > 0.8:
            interpretation['key_strengths'].append(f"High R² score ({r2:.3f}) - explains most variance")
        if mae < 0.3:
            interpretation['key_strengths'].append(f"Low mean absolute error ({mae:.3f})")
        if metrics.get('within_1.0', 0) > 0.8:
            interpretation['key_strengths'].append(f"High accuracy within 1.0 unit ({metrics['within_1.0']:.1%})")
        
        # Identify weaknesses
        if r2 < 0.6:
            interpretation['key_weaknesses'].append(f"Low R² score ({r2:.3f}) - limited explanatory power")
        if mae > 0.5:
            interpretation['key_weaknesses'].append(f"High mean absolute error ({mae:.3f})")
        if metrics.get('max_error', 0) > 2.0:
            interpretation['key_weaknesses'].append(f"Large maximum error ({metrics['max_error']:.3f})")
        
        # Actionable insights
        interpretation['actionable_insights'] = [
            f"Model explains {r2:.1%} of variance in the target variable",
            f"Average prediction error is {mae:.3f} units",
            f"Predictions are within 1.0 unit for {metrics.get('within_1.0', 0):.1%} of cases"
        ]
        
        # Next steps
        interpretation['next_steps'] = [
            "Review residual plots for patterns",
            "Check for outliers affecting performance",
            "Consider feature engineering improvements",
            "Test with different model architectures"
        ]
        
        return interpretation
    
    def _interpret_roi_results(self, roi_analysis: Dict[str, Any]) -> Dict[str, Any]:
        """Interpret ROI analysis results"""
        interpretation = {
            'best_strategy': None,
            'worst_strategy': None,
            'overall_profitability': 'unknown',
            'risk_assessment': 'unknown',
            'recommended_strategy': None,
            'key_insights': [],
            'risk_factors': [],
            'sustainability_score': 0,
            'actionable_recommendations': []
        }
        
        if not roi_analysis:
            return interpretation
        
        # Find best and worst strategies by ROI
        strategies_by_roi = sorted(roi_analysis.items(), key=lambda x: x[1]['roi_percent'], reverse=True)
        
        if strategies_by_roi:
            best_strategy = strategies_by_roi[0]
            worst_strategy = strategies_by_roi[-1]
            
            interpretation['best_strategy'] = best_strategy[0]
            interpretation['worst_strategy'] = worst_strategy[0]
            
            # Determine overall profitability
            best_roi = best_strategy[1]['roi_percent']
            if best_roi > 20:
                interpretation['overall_profitability'] = 'Highly Profitable'
                interpretation['sustainability_score'] = 85
            elif best_roi > 10:
                interpretation['overall_profitability'] = 'Profitable'
                interpretation['sustainability_score'] = 70
            elif best_roi > 0:
                interpretation['overall_profitability'] = 'Marginally Profitable'
                interpretation['sustainability_score'] = 50
            else:
                interpretation['overall_profitability'] = 'Not Profitable'
                interpretation['sustainability_score'] = 30
            
            # Risk assessment based on max drawdown and Sharpe ratio
            max_drawdown = best_strategy[1]['max_drawdown']
            sharpe_ratio = best_strategy[1]['sharpe_ratio']
            
            if max_drawdown < 0.2 and sharpe_ratio > 1.0:
                interpretation['risk_assessment'] = 'Low Risk'
            elif max_drawdown < 0.4 and sharpe_ratio > 0.5:
                interpretation['risk_assessment'] = 'Moderate Risk'
            else:
                interpretation['risk_assessment'] = 'High Risk'
            
            # Key insights
            interpretation['key_insights'] = [
                f"Best strategy ({best_strategy[0]}) achieved {best_roi:.1f}% ROI",
                f"Win rate: {best_strategy[1]['win_rate']:.1%}",
                f"Maximum drawdown: {max_drawdown:.1%}",
                f"Sharpe ratio: {sharpe_ratio:.2f}"
            ]
            
            # Risk factors
            if max_drawdown > 0.3:
                interpretation['risk_factors'].append(f"High maximum drawdown ({max_drawdown:.1%})")
            if sharpe_ratio < 0.5:
                interpretation['risk_factors'].append(f"Low Sharpe ratio ({sharpe_ratio:.2f})")
            if best_strategy[1]['profit_factor'] < 1.2:
                interpretation['risk_factors'].append(f"Low profit factor ({best_strategy[1]['profit_factor']:.2f})")
            
            # Recommended strategy
            if best_strategy[1]['roi_percent'] > 10 and max_drawdown < 0.3:
                interpretation['recommended_strategy'] = best_strategy[0]
                interpretation['actionable_recommendations'] = [
                    f"Implement {best_strategy[0]} strategy with caution",
                    "Start with small stakes to validate",
                    "Monitor performance weekly",
                    "Consider half-Kelly for risk management"
                ]
            else:
                interpretation['actionable_recommendations'] = [
                    "Strategy needs further refinement",
                    "Consider reducing stake sizes",
                    "Review match selection criteria",
                    "Test on larger dataset"
                ]
        
        return interpretation
    
    def _interpret_comparison_results(self, ranked_models: List[Dict], task: str) -> Dict[str, Any]:
        """Interpret model comparison results"""
        interpretation = {
            'best_model': None,
            'top_performers': [],
            'worst_performers': [],
            'performance_gap': 0.0,
            'recommendations': [],
            'tradeoffs': [],
            'selection_criteria': []
        }
        
        if not ranked_models:
            return interpretation
        
        interpretation['best_model'] = ranked_models[0]['model_name']
        interpretation['top_performers'] = [m['model_name'] for m in ranked_models[:3]]
        interpretation['worst_performers'] = [m['model_name'] for m in ranked_models[-3:]]
        
        # Calculate performance gap
        if task == 'classification':
            best_accuracy = ranked_models[0].get('accuracy', 0)
            worst_accuracy = ranked_models[-1].get('accuracy', 0)
            interpretation['performance_gap'] = best_accuracy - worst_accuracy
        else:  # regression
            best_rmse = ranked_models[0].get('rmse', float('inf'))
            worst_rmse = ranked_models[-1].get('rmse', float('inf'))
            interpretation['performance_gap'] = worst_rmse - best_rmse
        
        # Recommendations
        interpretation['recommendations'] = [
            f"Select {ranked_models[0]['model_name']} as primary model",
            f"Consider {ranked_models[1]['model_name']} as backup for ensemble",
            "Test top 3 models on validation set",
            "Consider computational requirements for deployment"
        ]
        
        # Tradeoffs
        if len(ranked_models) > 1:
            interpretation['tradeoffs'] = [
                f"{ranked_models[0]['model_name']} has best performance",
                f"{ranked_models[-1]['model_name']} may be simpler/faster"
            ]
        
        # Selection criteria
        interpretation['selection_criteria'] = [
            "Performance metrics (primary)",
            "Model complexity",
            "Training/inference speed",
            "Interpretability",
            "Resource requirements"
        ]
        
        return interpretation
    
    # ==========================================================================
    # HELPER METHODS
    # ==========================================================================
    
    def _map_outcome(self, outcome, result_map):
        """Map outcome to numeric code"""
        if outcome is None or pd.isna(outcome):
            return None
        
        if isinstance(outcome, (int, float)):
            return int(outcome)
        
        if str(outcome).upper() == 'H':
            return 2
        elif str(outcome).upper() == 'D':
            return 1
        elif str(outcome).upper() == 'A':
            return 0
        
        return None
    
    def _get_odds(self, row, prediction, result_map):
        """Get odds for prediction"""
        if prediction == 2:  # Home win
            return row.get('OddHome', 0)
        elif prediction == 1:  # Draw
            return row.get('OddDraw', 0)
        elif prediction == 0:  # Away win
            return row.get('OddAway', 0)
        return 0
    
    def _calculate_stake(self, strategy_type, current_bankroll, base_stake, odds):
        """Calculate stake based on strategy"""
        if strategy_type == 'fixed':
            return base_stake
        elif strategy_type == 'kelly':
            # Kelly Criterion
            b = odds - 1
            p = 0.5  # Estimated probability
            q = 1 - p
            kelly_fraction = max(0, (b * p - q) / b)
            return current_bankroll * kelly_fraction * 0.5  # Half-kelly
        else:  # proportional
            return current_bankroll * 0.02  # 2% of bankroll
    
    def _calculate_roi_metrics(self, strategy_results, initial_bankroll, base_stake, detailed_results, strategy_type):
        """Calculate ROI metrics for a strategy"""
        total_profit = strategy_results['bankroll'] - initial_bankroll
        roi_percent = (total_profit / (strategy_results['bets'] * base_stake)) * 100 if strategy_results['bets'] > 0 else 0
        win_rate = strategy_results['wins'] / strategy_results['bets'] if strategy_results['bets'] > 0 else 0
        
        # Calculate max drawdown
        equity_curve = strategy_results['equity']
        max_drawdown = self._calculate_max_drawdown(equity_curve)
        
        # Calculate Sharpe ratio
        sharpe_ratio = self._calculate_sharpe_ratio(equity_curve)
        
        # Calculate profit factor
        profit_factor = self._calculate_profit_factor(detailed_results, strategy_type)
        
        return {
            'total_bets': strategy_results['bets'],
            'wins': strategy_results['wins'],
            'losses': strategy_results['bets'] - strategy_results['wins'],
            'win_rate': win_rate,
            'total_profit': total_profit,
            'roi_percent': roi_percent,
            'final_bankroll': strategy_results['bankroll'],
            'max_drawdown': max_drawdown,
            'sharpe_ratio': sharpe_ratio,
            'profit_factor': profit_factor
        }
    
    def _calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown"""
        if len(equity_curve) < 2:
            return 0
        
        peak = equity_curve[0]
        max_dd = 0
        
        for value in equity_curve:
            if value > peak:
                peak = value
            
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return max_dd
    
    def _calculate_sharpe_ratio(self, equity_curve):
        """Calculate Sharpe ratio"""
        if len(equity_curve) < 2:
            return 0
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0
        
        return np.mean(returns) / np.std(returns) * np.sqrt(252)
    
    def _calculate_profit_factor(self, detailed_results, strategy_type):
        """Calculate profit factor"""
        strategy_results = [r for r in detailed_results if r['strategy'] == strategy_type]
        
        gross_wins = sum(r['profit'] for r in strategy_results if r['profit'] > 0)
        gross_losses = abs(sum(r['profit'] for r in strategy_results if r['profit'] < 0))
        
        if gross_losses == 0:
            return float('inf')
        
        return gross_wins / gross_losses
    
    def _rank_models(self, comparison, task):
        """Rank models based on performance"""
        ranked = []
        
        for name, metrics in comparison.items():
            if 'error' in metrics:
                continue
            
            score = 0
            if task == 'classification':
                score = (metrics.get('accuracy', 0) * 0.4 +
                        metrics.get('f1_score', 0) * 0.3 +
                        metrics.get('roc_auc', 0) * 0.3 if metrics.get('roc_auc') else 0)
            else:  # regression
                r2 = metrics.get('r2', 0)
                mae = metrics.get('mae', float('inf'))
                # Normalize MAE (lower is better)
                mae_score = 1.0 / (1.0 + mae) if mae > 0 else 1.0
                score = (r2 * 0.5 + mae_score * 0.5)
            
            ranked.append({
                'model_name': name,
                'score': score,
                'metrics': metrics
            })
        
        # Sort by score descending
        ranked.sort(key=lambda x: x['score'], reverse=True)
        
        # Add ranking position
        for i, model in enumerate(ranked):
            model['ranking'] = i + 1
        
        return ranked
    
    # ==========================================================================
    # PLOTTING METHODS
    # ==========================================================================
    
    def _generate_classification_plots(self, y_true, y_pred, y_prob, class_names, model_name):
        """Generate classification evaluation plots"""
        plot_paths = []
        
        try:
            # Confusion matrix
            plt.figure(figsize=(10, 8))
            cm = confusion_matrix(y_true, y_pred)
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues',
                       xticklabels=class_names, yticklabels=class_names)
            plt.title(f'Confusion Matrix: {model_name}')
            plt.ylabel('Actual')
            plt.xlabel('Predicted')
            cm_path = os.path.join(self.subdirs['confusion_matrices'],
                                  f'cm_{model_name}_{int(time.time())}.png')
            plt.tight_layout()
            plt.savefig(cm_path, dpi=150)
            plt.close()
            plot_paths.append(cm_path)
            
            # ROC curve if probabilities available
            if y_prob is not None and len(np.unique(y_true)) == 2:
                plt.figure(figsize=(10, 8))
                fpr, tpr, _ = roc_curve(y_true, y_prob[:, 1])
                roc_auc = auc(fpr, tpr)
                
                plt.plot(fpr, tpr, color='darkorange', lw=2,
                        label=f'ROC curve (AUC = {roc_auc:.2f})')
                plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
                plt.xlim([0.0, 1.0])
                plt.ylim([0.0, 1.05])
                plt.xlabel('False Positive Rate')
                plt.ylabel('True Positive Rate')
                plt.title(f'ROC Curve: {model_name}')
                plt.legend(loc="lower right")
                
                roc_path = os.path.join(self.subdirs['roc_curves'],
                                       f'roc_{model_name}_{int(time.time())}.png')
                plt.savefig(roc_path, dpi=150)
                plt.close()
                plot_paths.append(roc_path)
            
            # Class distribution
            plt.figure(figsize=(12, 5))
            
            plt.subplot(1, 2, 1)
            unique, counts = np.unique(y_true, return_counts=True)
            plt.bar(range(len(unique)), counts, color='skyblue', alpha=0.7)
            plt.xticks(range(len(unique)), [class_names[i] for i in unique])
            plt.title('Actual Class Distribution')
            plt.ylabel('Count')
            
            plt.subplot(1, 2, 2)
            unique_pred, counts_pred = np.unique(y_pred, return_counts=True)
            plt.bar(range(len(unique_pred)), counts_pred, color='lightcoral', alpha=0.7)
            plt.xticks(range(len(unique_pred)), [class_names[i] for i in unique_pred])
            plt.title('Predicted Class Distribution')
            plt.ylabel('Count')
            
            plt.suptitle(f'Class Distribution: {model_name}')
            plt.tight_layout()
            
            dist_path = os.path.join(self.plots_dir,
                                    f'class_dist_{model_name}_{int(time.time())}.png')
            plt.savefig(dist_path, dpi=150)
            plt.close()
            plot_paths.append(dist_path)
            
        except Exception as e:
            logger.error(f"Error generating classification plots: {e}")
        
        return plot_paths
    
    def _generate_regression_plots(self, y_true, y_pred, model_name):
        """Generate regression evaluation plots"""
        plot_paths = []
        
        try:
            # Scatter plot with regression line
            plt.figure(figsize=(10, 8))
            plt.scatter(y_true, y_pred, alpha=0.6, color='blue', edgecolor='white', s=50)
            
            # Perfect prediction line
            lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
            plt.plot(lims, lims, 'k--', alpha=0.75, label='Perfect Prediction')
            
            # Regression line
            m, b = np.polyfit(y_true, y_pred, 1)
            plt.plot(y_true, m*y_true + b, color='red', alpha=0.8, label=f'Fit: y={m:.2f}x+{b:.2f}')
            
            plt.xlabel('Actual')
            plt.ylabel('Predicted')
            plt.title(f'Actual vs Predicted: {model_name}')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            scatter_path = os.path.join(self.subdirs['regression_analysis'],
                                       f'scatter_{model_name}_{int(time.time())}.png')
            plt.savefig(scatter_path, dpi=150)
            plt.close()
            plot_paths.append(scatter_path)
            
            # Error distribution
            plt.figure(figsize=(10, 6))
            errors = y_pred - y_true
            plt.hist(errors, bins=30, alpha=0.7, color='green', edgecolor='black')
            plt.axvline(x=0, color='red', linestyle='--', linewidth=2)
            plt.xlabel('Prediction Error')
            plt.ylabel('Frequency')
            plt.title(f'Error Distribution: {model_name}')
            plt.grid(True, alpha=0.3)
            
            error_path = os.path.join(self.subdirs['regression_analysis'],
                                     f'error_{model_name}_{int(time.time())}.png')
            plt.savefig(error_path, dpi=150)
            plt.close()
            plot_paths.append(error_path)
            
            # Residuals plot
            plt.figure(figsize=(10, 6))
            residuals = y_pred - y_true
            plt.scatter(y_pred, residuals, alpha=0.6, color='orange', s=50)
            plt.axhline(y=0, color='red', linestyle='--', linewidth=2)
            plt.xlabel('Predicted Values')
            plt.ylabel('Residuals')
            plt.title(f'Residuals Plot: {model_name}')
            plt.grid(True, alpha=0.3)
            
            residual_path = os.path.join(self.subdirs['regression_analysis'],
                                        f'residuals_{model_name}_{int(time.time())}.png')
            plt.savefig(residual_path, dpi=150)
            plt.close()
            plot_paths.append(residual_path)
            
        except Exception as e:
            logger.error(f"Error generating regression plots: {e}")
        
        return plot_paths
    
    def _generate_roi_plots(self, results, detailed_results):
        """Generate ROI analysis plots"""
        plot_paths = []
        
        try:
            # Equity curves
            plt.figure(figsize=(12, 8))
            colors = {'fixed': 'blue', 'kelly': 'green', 'proportional': 'orange'}
            
            for strategy, data in results.items():
                if len(data['equity']) > 1:
                    plt.plot(data['equity'], label=f'{strategy.capitalize()} Strategy',
                            color=colors.get(strategy, 'gray'), linewidth=2.5)
            
            plt.xlabel('Number of Bets')
            plt.ylabel('Bankroll ($)')
            plt.title('Betting Strategy Performance')
            plt.legend(loc='best')
            plt.grid(True, alpha=0.2)
            
            equity_path = os.path.join(self.subdirs['roi_analysis'],
                                      f'equity_curves_{int(time.time())}.png')
            plt.savefig(equity_path, dpi=150)
            plt.close()
            plot_paths.append(equity_path)
            
            # ROI comparison bar chart
            if results:
                strategies = []
                roi_values = []
                
                for strategy, data in results.items():
                    if data['bets'] > 0:
                        total_profit = data['bankroll'] - 1000  # Assuming initial 1000
                        roi_percent = (total_profit / (data['bets'] * 10)) * 100
                        strategies.append(strategy.capitalize())
                        roi_values.append(roi_percent)
                
                if strategies:
                    plt.figure(figsize=(10, 6))
                    bars = plt.bar(strategies, roi_values, color=['blue', 'green', 'orange'])
                    plt.xlabel('Strategy')
                    plt.ylabel('ROI (%)')
                    plt.title('ROI by Betting Strategy')
                    
                    # Add value labels
                    for bar, value in zip(bars, roi_values):
                        plt.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.5,
                                f'{value:.1f}%', ha='center', va='bottom')
                    
                    roi_bar_path = os.path.join(self.subdirs['roi_analysis'],
                                              f'roi_comparison_{int(time.time())}.png')
                    plt.savefig(roi_bar_path, dpi=150)
                    plt.close()
                    plot_paths.append(roi_bar_path)
            
        except Exception as e:
            logger.error(f"Error generating ROI plots: {e}")
        
        return plot_paths
    
    def _generate_comparison_plots(self, comparison, task):
        """Generate model comparison plots"""
        plot_paths = []
        
        try:
            # Prepare data for plotting
            model_names = []
            metric_values = []
            
            if task == 'classification':
                metric_name = 'accuracy'
                for name, metrics in comparison.items():
                    if 'error' not in metrics:
                        model_names.append(name)
                        metric_values.append(metrics.get('accuracy', 0))
            else:  # regression
                metric_name = 'r2'
                for name, metrics in comparison.items():
                    if 'error' not in metrics:
                        model_names.append(name)
                        metric_values.append(metrics.get('r2', 0))
            
            if not model_names:
                return plot_paths
            
            # Bar chart comparison
            plt.figure(figsize=(12, 6))
            colors = plt.cm.Set3(np.linspace(0, 1, len(model_names)))
            bars = plt.bar(range(len(model_names)), metric_values, color=colors)
            plt.xticks(range(len(model_names)), model_names, rotation=45, ha='right')
            plt.ylabel(metric_name.upper())
            plt.title(f'Model Comparison: {metric_name.upper()}')
            plt.grid(True, alpha=0.3, axis='y')
            
            # Add value labels
            for bar, value in zip(bars, metric_values):
                plt.text(bar.get_x() + bar.get_width()/2., bar.get_height() + 0.01,
                        f'{value:.3f}', ha='center', va='bottom')
            
            comp_path = os.path.join(self.subdirs['comparative'],
                                    f'model_comparison_{task}_{int(time.time())}.png')
            plt.tight_layout()
            plt.savefig(comp_path, dpi=150)
            plt.close()
            plot_paths.append(comp_path)
            
            # Radar chart for multi-metric comparison (for top 3 models)
            if task == 'classification':
                self._create_radar_chart(comparison, model_names, metric_values, task)
            
        except Exception as e:
            logger.error(f"Error generating comparison plots: {e}")
        
        return plot_paths
    
    def _create_radar_chart(self, comparison, model_names, metric_values, task):
        """Create radar chart for multi-metric comparison"""
        try:
            # Select top 3 models
            top_models = sorted(zip(model_names, metric_values), key=lambda x: x[1], reverse=True)[:3]
            
            if len(top_models) < 2:
                return
            
            # Prepare metrics for radar chart
            metrics_to_plot = ['accuracy', 'precision', 'recall', 'f1_score']
            if task == 'regression':
                metrics_to_plot = ['r2', 'mae', 'rmse', 'mape']
            
            fig, ax = plt.subplots(figsize=(10, 10), subplot_kw=dict(projection='polar'))
            
            # Calculate angles
            angles = np.linspace(0, 2*np.pi, len(metrics_to_plot), endpoint=False).tolist()
            angles += angles[:1]  # Close the loop
            
            colors = ['blue', 'green', 'orange']
            
            for idx, (model_name, _) in enumerate(top_models):
                values = []
                for metric in metrics_to_plot:
                    if metric in comparison[model_name]:
                        values.append(comparison[model_name][metric])
                    else:
                        values.append(0)
                
                # Normalize values to 0-1 range
                max_val = max(values)
                if max_val > 0:
                    values = [v/max_val for v in values]
                
                values += values[:1]  # Close the loop
                
                ax.plot(angles, values, 'o-', linewidth=2, label=model_name, color=colors[idx])
                ax.fill(angles, values, alpha=0.1, color=colors[idx])
            
            # Set labels
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics_to_plot])
            ax.set_ylim(0, 1)
            ax.set_title('Model Comparison (Normalized Metrics)', size=16, pad=20)
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
            
            radar_path = os.path.join(self.subdirs['comparative'],
                                     f'radar_chart_{task}_{int(time.time())}.png')
            plt.tight_layout()
            plt.savefig(radar_path, dpi=150)
            plt.close()
            
        except Exception as e:
            logger.error(f"Error creating radar chart: {e}")
    
    def generate_evaluation_summary(self, evaluation_result: Dict[str, Any]) -> str:
        """Generate a human-readable summary of evaluation results"""
        summary_parts = []
        
        eval_type = evaluation_result.get('evaluation_type', 'unknown')
        model_name = evaluation_result.get('model_name', 'Unknown Model')
        interpretation = evaluation_result.get('interpretation', {})
        
        summary_parts.append(f"📊 EVALUATION SUMMARY: {model_name}")
        summary_parts.append("=" * 50)
        summary_parts.append(f"Type: {eval_type.upper()}")
        summary_parts.append(f"Timestamp: {evaluation_result.get('timestamp', 'N/A')}")
        summary_parts.append(f"Sample Size: {evaluation_result.get('sample_size', 'N/A')}")
        
        if eval_type == 'classification':
            metrics = evaluation_result.get('metrics', {})
            summary_parts.append(f"\n🎯 PERFORMANCE METRICS:")
            summary_parts.append(f"  • Accuracy: {metrics.get('accuracy', 0):.1%}")
            summary_parts.append(f"  • Precision: {metrics.get('precision', 0):.1%}")
            summary_parts.append(f"  • Recall: {metrics.get('recall', 0):.1%}")
            summary_parts.append(f"  • F1-Score: {metrics.get('f1_score', 0):.1%}")
            if 'roc_auc' in metrics and metrics['roc_auc']:
                summary_parts.append(f"  • ROC-AUC: {metrics['roc_auc']:.3f}")
        
        elif eval_type == 'regression':
            metrics = evaluation_result.get('metrics', {})
            summary_parts.append(f"\n📈 PERFORMANCE METRICS:")
            summary_parts.append(f"  • R² Score: {metrics.get('r2', 0):.3f}")
            summary_parts.append(f"  • MAE: {metrics.get('mae', 0):.3f}")
            summary_parts.append(f"  • RMSE: {metrics.get('rmse', 0):.3f}")
            summary_parts.append(f"  • MAPE: {metrics.get('mape', 0):.1%}")
        
        # Add interpretation
        if interpretation:
            summary_parts.append(f"\n🧠 INTERPRETATION:")
            summary_parts.append(f"  • Overall: {interpretation.get('overall_performance', 'N/A')}")
            summary_parts.append(f"  • Confidence: {interpretation.get('confidence_level', 'N/A')}")
            summary_parts.append(f"  • Recommendation: {interpretation.get('deployment_recommendation', 'N/A')}")
            
            if interpretation.get('key_strengths'):
                summary_parts.append(f"\n✅ STRENGTHS:")
                for strength in interpretation['key_strengths'][:3]:
                    summary_parts.append(f"  • {strength}")
            
            if interpretation.get('key_weaknesses'):
                summary_parts.append(f"\n⚠️ WEAKNESSES:")
                for weakness in interpretation['key_weaknesses'][:3]:
                    summary_parts.append(f"  • {weakness}")
        
        # Add next steps
        if interpretation.get('next_steps'):
            summary_parts.append(f"\n🚀 NEXT STEPS:")
            for step in interpretation['next_steps'][:3]:
                summary_parts.append(f"  • {step}")
        
        summary_parts.append(f"\n⏱️ Execution Time: {evaluation_result.get('execution_time', 0):.2f}s")
        
        return "\n".join(summary_parts)

# ============================================================================
# ENHANCED CHATBOT WITH EVALUATION CAPABILITIES
# ============================================================================

class EnhancedChatbot:
    """Enhanced chatbot with integrated evaluation capabilities"""
    
    def __init__(self):
        """Initialize enhanced chatbot with evaluation engine"""
        # Initialize core components
        self.evaluation_engine = EvaluationEngine()
        self.evaluation_queue = queue.Queue()
        self.running_evaluations = {}
        self.evaluation_history = []
        
        # Start evaluation processing thread
        self._start_evaluation_processor()
        
        logger.info("Enhanced Chatbot with Evaluation initialized")
    
    def _start_evaluation_processor(self):
        """Start background thread for processing evaluations"""
        def process_evaluations():
            while True:
                try:
                    eval_request = self.evaluation_queue.get()
                    if eval_request is None:  # Poison pill
                        break
                    
                    self._process_evaluation(eval_request)
                    self.evaluation_queue.task_done()
                    
                except Exception as e:
                    logger.error(f"Error in evaluation processor: {e}")
        
        self.eval_processor = threading.Thread(target=process_evaluations, daemon=True)
        self.eval_processor.start()
    
    def _process_evaluation(self, eval_request: EvaluationRequest):
        """Process an evaluation request"""
        try:
            eval_id = eval_request.id
            self.running_evaluations[eval_id] = {
                'status': EvaluationStatus.RUNNING,
                'started_at': datetime.now()
            }
            
            result = None
            error = None
            
            try:
                # Perform evaluation based on type
                if eval_request.evaluation_type == EvaluationType.CLASSIFICATION:
                    result = self._perform_classification_evaluation(eval_request)
                elif eval_request.evaluation_type == EvaluationType.REGRESSION:
                    result = self._perform_regression_evaluation(eval_request)
                elif eval_request.evaluation_type == EvaluationType.ROI_ANALYSIS:
                    result = self._perform_roi_analysis(eval_request)
                elif eval_request.evaluation_type == EvaluationType.MODEL_COMPARISON:
                    result = self._perform_model_comparison(eval_request)
                
                # Update evaluation request
                eval_request.status = EvaluationStatus.COMPLETED
                eval_request.completed_at = datetime.now()
                eval_request.results = result
                
                # Generate interpretation
                eval_request.interpretation = self._generate_interpretation_summary(result)
                
            except Exception as e:
                error = str(e)
                eval_request.status = EvaluationStatus.FAILED
                eval_request.error_message = error
                logger.error(f"Evaluation {eval_id} failed: {e}")
            
            # Update running evaluations
            self.running_evaluations[eval_id] = {
                'status': eval_request.status,
                'completed_at': eval_request.completed_at,
                'result': result,
                'error': error
            }
            
            # Save to history
            self.evaluation_history.append(eval_request)
            
            # Save to database if needed
            self._save_evaluation_to_db(eval_request)
            
            logger.info(f"Evaluation {eval_id} completed with status: {eval_request.status}")
            
        except Exception as e:
            logger.error(f"Error processing evaluation: {e}")
    
    def _perform_classification_evaluation(self, eval_request: EvaluationRequest) -> Dict[str, Any]:
        """Perform classification evaluation"""
        params = eval_request.parameters
        
        # Load data
        y_true = self._load_data(params.get('true_data'))
        y_pred = self._load_data(params.get('pred_data'))
        y_prob = self._load_data(params.get('prob_data')) if params.get('prob_data') else None
        
        # Get class names
        class_names = params.get('class_names', [f'Class {i}' for i in np.unique(y_true)])
        model_name = params.get('model_name', 'Unknown_Model')
        
        # Perform evaluation
        result = self.evaluation_engine.evaluate_classification(
            y_true, y_pred, y_prob, class_names, model_name
        )
        
        return result
    
    def _perform_regression_evaluation(self, eval_request: EvaluationRequest) -> Dict[str, Any]:
        """Perform regression evaluation"""
        params = eval_request.parameters
        
        # Load data
        y_true = self._load_data(params.get('true_data'))
        y_pred = self._load_data(params.get('pred_data'))
        model_name = params.get('model_name', 'Unknown_Model')
        
        # Perform evaluation
        result = self.evaluation_engine.evaluate_regression(y_true, y_pred, model_name)
        
        return result
    
    def _perform_roi_analysis(self, eval_request: EvaluationRequest) -> Dict[str, Any]:
        """Perform ROI analysis"""
        params = eval_request.parameters
        
        # Load data
        df = self._load_dataframe(params.get('match_data'))
        predictions = self._load_data(params.get('predictions'))
        
        # Get parameters
        target_col = params.get('target_col', 'target')
        stake = float(params.get('stake', 10.0))
        strategy = params.get('strategy', 'fixed')
        bankroll = float(params.get('bankroll', 1000.0))
        
        # Perform analysis
        result = self.evaluation_engine.analyze_roi(df, predictions, target_col, stake, strategy, bankroll)
        
        return result
    
    def _perform_model_comparison(self, eval_request: EvaluationRequest) -> Dict[str, Any]:
        """Perform model comparison"""
        params = eval_request.parameters
        
        # This would typically load models and test data
        # For now, return a placeholder result
        return {
            'comparison': {},
            'interpretation': {'best_model': 'None', 'recommendations': []},
            'task': params.get('task', 'classification')
        }
    
    def _load_data(self, data_source):
        """Load data from various sources"""
        if isinstance(data_source, (list, np.ndarray)):
            return np.array(data_source)
        elif isinstance(data_source, str) and data_source.endswith('.csv'):
            return pd.read_csv(data_source).values.flatten()
        else:
            raise ValueError(f"Unsupported data source: {type(data_source)}")
    
    def _load_dataframe(self, data_source):
        """Load DataFrame from various sources"""
        if isinstance(data_source, pd.DataFrame):
            return data_source
        elif isinstance(data_source, str) and data_source.endswith('.csv'):
            return pd.read_csv(data_source)
        else:
            raise ValueError(f"Unsupported DataFrame source: {type(data_source)}")
    
    def _generate_interpretation_summary(self, result: Dict[str, Any]) -> str:
        """Generate interpretation summary from evaluation results"""
        return self.evaluation_engine.generate_evaluation_summary(result)
    
    def _save_evaluation_to_db(self, eval_request: EvaluationRequest):
        """Save evaluation results to database"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                evaluation = ModelEvaluation(
                    evaluation_id=eval_request.id,
                    user_id=eval_request.user_id,
                    evaluation_type=eval_request.evaluation_type.value,
                    parameters=json.dumps(eval_request.parameters),
                    status=eval_request.status.value,
                    results=json.dumps(eval_request.results) if eval_request.results else None,
                    interpretation=eval_request.interpretation,
                    error_message=eval_request.error_message,
                    created_at=eval_request.created_at,
                    completed_at=eval_request.completed_at
                )
                db.session.add(evaluation)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error saving evaluation to database: {e}")
    
    # ==========================================================================
    # PUBLIC API FOR EVALUATION
    # ==========================================================================
    
    def request_evaluation(self, evaluation_type: str, parameters: Dict[str, Any],
                          user_id: int = 0) -> Dict[str, Any]:
        """Request an evaluation"""
        try:
            # Validate evaluation type
            try:
                eval_type = EvaluationType(evaluation_type)
            except ValueError:
                return {
                    'success': False,
                    'message': f'Invalid evaluation type: {evaluation_type}',
                    'valid_types': [e.value for e in EvaluationType]
                }
            
            # Create evaluation request
            eval_request = EvaluationRequest(
                user_id=user_id,
                evaluation_type=eval_type,
                parameters=parameters,
                status=EvaluationStatus.PENDING
            )
            
            # Add to queue
            self.evaluation_queue.put(eval_request)
            
            return {
                'success': True,
                'message': f'Evaluation requested successfully',
                'evaluation_id': eval_request.id,
                'evaluation_type': evaluation_type,
                'status': EvaluationStatus.PENDING.value,
                'queue_position': self.evaluation_queue.qsize()
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error requesting evaluation: {str(e)}'
            }
    
    def get_evaluation_status(self, evaluation_id: str) -> Dict[str, Any]:
        """Get status of an evaluation"""
        if evaluation_id in self.running_evaluations:
            status_info = self.running_evaluations[evaluation_id]
            return {
                'success': True,
                'evaluation_id': evaluation_id,
                'status': status_info['status'].value if isinstance(status_info['status'], EvaluationStatus) else status_info['status'],
                'started_at': status_info.get('started_at'),
                'completed_at': status_info.get('completed_at'),
                'has_result': 'result' in status_info and status_info['result'] is not None,
                'error': status_info.get('error')
            }
        
        # Check history
        for eval_req in self.evaluation_history:
            if eval_req.id == evaluation_id:
                return {
                    'success': True,
                    'evaluation_id': evaluation_id,
                    'status': eval_req.status.value,
                    'created_at': eval_req.created_at.isoformat(),
                    'completed_at': eval_req.completed_at.isoformat() if eval_req.completed_at else None,
                    'has_result': eval_req.results is not None,
                    'interpretation': eval_req.interpretation,
                    'error_message': eval_req.error_message
                }
        
        return {
            'success': False,
            'message': f'Evaluation not found: {evaluation_id}'
        }
    
    def get_evaluation_results(self, evaluation_id: str) -> Dict[str, Any]:
        """Get results of a completed evaluation"""
        # Check history
        for eval_req in self.evaluation_history:
            if eval_req.id == evaluation_id and eval_req.status == EvaluationStatus.COMPLETED:
                return {
                    'success': True,
                    'evaluation_id': evaluation_id,
                    'status': eval_req.status.value,
                    'results': eval_req.results,
                    'interpretation': eval_req.interpretation,
                    'plot_paths': eval_req.plot_paths,
                    'execution_time': eval_req.results.get('execution_time', 0) if eval_req.results else 0,
                    'summary': self.evaluation_engine.generate_evaluation_summary(eval_req.results) if eval_req.results else None
                }
        
        return {
            'success': False,
            'message': f'Evaluation not found or not completed: {evaluation_id}'
        }
    
    def get_evaluation_history(self, user_id: int = None, limit: int = 10) -> List[Dict[str, Any]]:
        """Get evaluation history"""
        history = []
        
        for eval_req in self.evaluation_history[-limit:]:
            if user_id is None or eval_req.user_id == user_id:
                history.append({
                    'id': eval_req.id,
                    'user_id': eval_req.user_id,
                    'evaluation_type': eval_req.evaluation_type.value,
                    'status': eval_req.status.value,
                    'created_at': eval_req.created_at.isoformat(),
                    'completed_at': eval_req.completed_at.isoformat() if eval_req.completed_at else None,
                    'has_results': eval_req.results is not None,
                    'error_message': eval_req.error_message
                })
        
        return history
    
    def cancel_evaluation(self, evaluation_id: str) -> Dict[str, Any]:
        """Cancel a running evaluation"""
        # Note: This is a simplified implementation
        # In production, you would need thread-safe cancellation
        if evaluation_id in self.running_evaluations:
            self.running_evaluations[evaluation_id]['status'] = 'cancelled'
            return {
                'success': True,
                'message': f'Evaluation {evaluation_id} cancelled'
            }
        
        return {
            'success': False,
            'message': f'Evaluation not found or not running: {evaluation_id}'
        }
    
    def quick_evaluate_classification(self, y_true, y_pred, y_prob=None,
                                     class_names=None, model_name="Quick_Eval") -> Dict[str, Any]:
        """Quick classification evaluation (synchronous)"""
        try:
            result = self.evaluation_engine.evaluate_classification(
                np.array(y_true), np.array(y_pred), y_prob, class_names, model_name
            )
            
            return {
                'success': True,
                'result': result,
                'summary': self.evaluation_engine.generate_evaluation_summary(result)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Quick evaluation failed: {str(e)}'
            }
    
    def quick_evaluate_regression(self, y_true, y_pred, model_name="Quick_Eval") -> Dict[str, Any]:
        """Quick regression evaluation (synchronous)"""
        try:
            result = self.evaluation_engine.evaluate_regression(
                np.array(y_true), np.array(y_pred), model_name
            )
            
            return {
                'success': True,
                'result': result,
                'summary': self.evaluation_engine.generate_evaluation_summary(result)
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Quick evaluation failed: {str(e)}'
            }
    
    def interpret_metrics(self, metrics: Dict[str, Any], eval_type: str) -> Dict[str, Any]:
        """Interpret metrics and provide actionable insights"""
        try:
            if eval_type == 'classification':
                interpretation = self.evaluation_engine._interpret_classification_results(
                    metrics, 'Interpreted_Model'
                )
            elif eval_type == 'regression':
                interpretation = self.evaluation_engine._interpret_regression_results(
                    metrics, 'Interpreted_Model'
                )
            else:
                return {
                    'success': False,
                    'message': f'Unsupported evaluation type: {eval_type}'
                }
            
            return {
                'success': True,
                'interpretation': interpretation,
                'summary': f"Model performance: {interpretation['overall_performance']}. "
                          f"Recommendation: {interpretation['deployment_recommendation']}"
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Interpretation failed: {str(e)}'
            }
    
    def generate_evaluation_report(self, evaluation_id: str) -> Dict[str, Any]:
        """Generate a comprehensive evaluation report"""
        # Get evaluation results
        results = self.get_evaluation_results(evaluation_id)
        
        if not results['success']:
            return results
        
        eval_data = results['results']
        interpretation = results['interpretation']
        
        # Generate HTML report
        report_html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Model Evaluation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .plots {{ display: flex; flex-wrap: wrap; gap: 20px; margin: 20px 0; }}
                .plot-item {{ flex: 1 1 300px; }}
                img {{ max-width: 100%; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                .summary {{ background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Model Evaluation Report</h1>
                    <p><strong>Evaluation ID:</strong> {evaluation_id}</p>
                    <p><strong>Type:</strong> {eval_data.get('evaluation_type', 'Unknown')}</p>
                    <p><strong>Model:</strong> {eval_data.get('model_name', 'Unknown')}</p>
                    <p><strong>Date:</strong> {eval_data.get('timestamp', 'N/A')}</p>
                </div>
                
                <div class="summary">
                    <h2>🎯 Performance Summary</h2>
                    <p><strong>Overall Performance:</strong> {interpretation.get('overall_performance', 'N/A')}</p>
                    <p><strong>Confidence Level:</strong> {interpretation.get('confidence_level', 'N/A')}</p>
                    <p><strong>Deployment Recommendation:</strong> {interpretation.get('deployment_recommendation', 'N/A')}</p>
                </div>
                
                <h2>📈 Key Metrics</h2>
                <div class="metric-card">
        """
        
        # Add metrics based on evaluation type
        if eval_data.get('evaluation_type') == 'classification':
            metrics = eval_data.get('metrics', {})
            report_html += f"""
                    <p><strong>Accuracy:</strong> {metrics.get('accuracy', 0):.2%}</p>
                    <p><strong>Precision:</strong> {metrics.get('precision', 0):.2%}</p>
                    <p><strong>Recall:</strong> {metrics.get('recall', 0):.2%}</p>
                    <p><strong>F1-Score:</strong> {metrics.get('f1_score', 0):.2%}</p>
            """
        else:
            metrics = eval_data.get('metrics', {})
            report_html += f"""
                    <p><strong>R² Score:</strong> {metrics.get('r2', 0):.3f}</p>
                    <p><strong>MAE:</strong> {metrics.get('mae', 0):.3f}</p>
                    <p><strong>RMSE:</strong> {metrics.get('rmse', 0):.3f}</p>
                    <p><strong>Explained Variance:</strong> {metrics.get('explained_variance', 0):.3f}</p>
            """
        
        report_html += """
                </div>
                
                <h2>🔍 Insights & Recommendations</h2>
                <div class="metric-card">
        """
        
        # Add insights
        if interpretation.get('key_strengths'):
            report_html += "<h3>✅ Strengths</h3><ul>"
            for strength in interpretation['key_strengths']:
                report_html += f"<li>{strength}</li>"
            report_html += "</ul>"
        
        if interpretation.get('key_weaknesses'):
            report_html += "<h3>⚠️ Weaknesses</h3><ul>"
            for weakness in interpretation['key_weaknesses']:
                report_html += f"<li>{weakness}</li>"
            report_html += "</ul>"
        
        if interpretation.get('actionable_insights'):
            report_html += "<h3>💡 Actionable Insights</h3><ul>"
            for insight in interpretation['actionable_insights']:
                report_html += f"<li>{insight}</li>"
            report_html += "</ul>"
        
        report_html += """
                </div>
                
                <h2>🚀 Next Steps</h2>
                <div class="metric-card">
                    <ul>
        """
        
        # Add next steps
        if interpretation.get('next_steps'):
            for step in interpretation['next_steps']:
                report_html += f"<li>{step}</li>"
        
        report_html += """
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        # Save report to file
        report_file = f"evaluation_report_{evaluation_id}_{int(time.time())}.html"
        report_path = os.path.join(self.evaluation_engine.plots_dir, report_file)
        
        try:
            with open(report_path, 'w') as f:
                f.write(report_html)
        except Exception as e:
            logger.error(f"Error saving report: {e}")
        
        return {
            'success': True,
            'report_html': report_html,
            'report_path': report_path,
            'evaluation_id': evaluation_id
        }

# ============================================================================
# FLASK ROUTES FOR EVALUATION
# ============================================================================

# Create enhanced chatbot instance
enhanced_chatbot = EnhancedChatbot()

def register_evaluation_routes(bp):
    """Register evaluation routes with Flask blueprint"""
    
    @bp.route('/evaluate/request', methods=['POST'])
    @login_required
    def request_evaluation():
        """Request a new evaluation"""
        try:
            data = request.get_json()
            evaluation_type = data.get('type')
            parameters = data.get('parameters', {})
            
            if not evaluation_type:
                return jsonify({
                    'success': False,
                    'message': 'Evaluation type is required'
                }), 400
            
            result = enhanced_chatbot.request_evaluation(evaluation_type, parameters, current_user.id)
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error requesting evaluation: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/status/<evaluation_id>', methods=['GET'])
    @login_required
    def get_evaluation_status_route(evaluation_id):
        """Get evaluation status"""
        try:
            result = enhanced_chatbot.get_evaluation_status(evaluation_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error getting evaluation status: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/results/<evaluation_id>', methods=['GET'])
    @login_required
    def get_evaluation_results_route(evaluation_id):
        """Get evaluation results"""
        try:
            result = enhanced_chatbot.get_evaluation_results(evaluation_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error getting evaluation results: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/history', methods=['GET'])
    @login_required
    def get_evaluation_history_route():
        """Get evaluation history"""
        try:
            limit = request.args.get('limit', 10, type=int)
            history = enhanced_chatbot.get_evaluation_history(current_user.id, limit)
            return jsonify({
                'success': True,
                'history': history,
                'count': len(history)
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error getting evaluation history: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/quick/classification', methods=['POST'])
    @login_required
    def quick_classification_evaluation():
        """Quick classification evaluation"""
        try:
            data = request.get_json()
            y_true = data.get('y_true')
            y_pred = data.get('y_pred')
            y_prob = data.get('y_prob')
            class_names = data.get('class_names')
            model_name = data.get('model_name', 'Quick_Eval')
            
            if not y_true or not y_pred:
                return jsonify({
                    'success': False,
                    'message': 'y_true and y_pred are required'
                }), 400
            
            result = enhanced_chatbot.quick_evaluate_classification(
                y_true, y_pred, y_prob, class_names, model_name
            )
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error performing quick evaluation: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/quick/regression', methods=['POST'])
    @login_required
    def quick_regression_evaluation():
        """Quick regression evaluation"""
        try:
            data = request.get_json()
            y_true = data.get('y_true')
            y_pred = data.get('y_pred')
            model_name = data.get('model_name', 'Quick_Eval')
            
            if not y_true or not y_pred:
                return jsonify({
                    'success': False,
                    'message': 'y_true and y_pred are required'
                }), 400
            
            result = enhanced_chatbot.quick_evaluate_regression(y_true, y_pred, model_name)
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error performing quick evaluation: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/interpret', methods=['POST'])
    @login_required
    def interpret_metrics_route():
        """Interpret metrics"""
        try:
            data = request.get_json()
            metrics = data.get('metrics')
            eval_type = data.get('type')
            
            if not metrics or not eval_type:
                return jsonify({
                    'success': False,
                    'message': 'Metrics and type are required'
                }), 400
            
            result = enhanced_chatbot.interpret_metrics(metrics, eval_type)
            return jsonify(result)
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error interpreting metrics: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/report/<evaluation_id>', methods=['GET'])
    @login_required
    def generate_evaluation_report_route(evaluation_id):
        """Generate evaluation report"""
        try:
            result = enhanced_chatbot.generate_evaluation_report(evaluation_id)
            return jsonify(result)
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error generating report: {str(e)}'
            }), 500
    
    @bp.route('/evaluate/dashboard', methods=['GET'])
    @login_required
    def evaluation_dashboard():
        """Evaluation dashboard page"""
        return render_template('evaluation_dashboard.html', title='Evaluation Dashboard')
    
    return bp

# ============================================================================
# INTEGRATION WITH MAIN CHATBOT
# ============================================================================

def integrate_evaluation_with_chatbot(main_chatbot):
    """Integrate evaluation capabilities with main chatbot"""
    
    # Add evaluation commands to chatbot
    evaluation_commands = {
        'evaluate_classification': {
            'description': 'Evaluate a classification model',
            'handler': lambda args, user_id, session_id: handle_evaluation_command('classification', args, user_id, session_id),
            'parameters': [
                {'name': 'model_name', 'type': 'string', 'required': True, 'description': 'Name of the model'},
                {'name': 'y_true', 'type': 'array', 'required': True, 'description': 'True labels'},
                {'name': 'y_pred', 'type': 'array', 'required': True, 'description': 'Predicted labels'}
            ]
        },
        'evaluate_regression': {
            'description': 'Evaluate a regression model',
            'handler': lambda args, user_id, session_id: handle_evaluation_command('regression', args, user_id, session_id),
            'parameters': [
                {'name': 'model_name', 'type': 'string', 'required': True, 'description': 'Name of the model'},
                {'name': 'y_true', 'type': 'array', 'required': True, 'description': 'True values'},
                {'name': 'y_pred', 'type': 'array', 'required': True, 'description': 'Predicted values'}
            ]
        },
        'analyze_roi': {
            'description': 'Analyze ROI for betting strategies',
            'handler': lambda args, user_id, session_id: handle_evaluation_command('roi_analysis', args, user_id, session_id),
            'parameters': [
                {'name': 'match_data', 'type': 'file', 'required': True, 'description': 'CSV file with match data'},
                {'name': 'predictions', 'type': 'array', 'required': True, 'description': 'Model predictions'}
            ]
        },
        'get_evaluation_status': {
            'description': 'Get status of an evaluation',
            'handler': lambda args, user_id, session_id: handle_get_evaluation_status(args, user_id, session_id),
            'parameters': [
                {'name': 'evaluation_id', 'type': 'string', 'required': True, 'description': 'Evaluation ID'}
            ]
        },
        'evaluation_history': {
            'description': 'Get evaluation history',
            'handler': lambda args, user_id, session_id: handle_evaluation_history(args, user_id, session_id),
            'parameters': [
                {'name': 'limit', 'type': 'number', 'required': False, 'description': 'Number of results to return'}
            ]
        }
    }
    
    # Add commands to main chatbot
    for cmd_name, cmd_config in evaluation_commands.items():
        main_chatbot.register_command(BotCommand(
            name=cmd_name,
            description=cmd_config['description'],
            category=CommandCategory.ANALYSIS,
            handler=cmd_config['handler'],
            parameters=cmd_config['parameters']
        ))
    
    def handle_evaluation_command(eval_type, args, user_id, session_id):
        """Handle evaluation command"""
        try:
            # Parse arguments
            params = {}
            for param in evaluation_commands[f'evaluate_{eval_type}']['parameters']:
                param_name = param['name']
                if param_name in args:
                    params[param_name] = args[param_name]
            
            # Request evaluation
            result = enhanced_chatbot.request_evaluation(eval_type, params, user_id)
            
            if result['success']:
                return {
                    'success': True,
                    'message': f'✅ {eval_type.title()} evaluation requested successfully!\n'
                              f'Evaluation ID: {result["evaluation_id"]}\n'
                              f'Status: {result["status"]}\n'
                              f'Queue position: {result["queue_position"]}',
                    'data': result,
                    'type': MessageType.SUCCESS.value
                }
            else:
                return {
                    'success': False,
                    'message': f'❌ Failed to request evaluation: {result["message"]}',
                    'type': MessageType.ERROR.value
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error handling evaluation command: {str(e)}',
                'type': MessageType.ERROR.value
            }
    
    def handle_get_evaluation_status(args, user_id, session_id):
        """Handle get evaluation status command"""
        try:
            evaluation_id = args.get('evaluation_id')
            
            if not evaluation_id:
                return {
                    'success': False,
                    'message': 'Evaluation ID is required',
                    'type': MessageType.ERROR.value
                }
            
            result = enhanced_chatbot.get_evaluation_status(evaluation_id)
            
            if result['success']:
                status = result['status']
                status_emoji = '🟢' if status == 'completed' else '🟡' if status == 'running' else '🔴'
                
                message = f'{status_emoji} Evaluation Status: {status.upper()}\n'
                message += f'ID: {evaluation_id}\n'
                
                if 'started_at' in result:
                    message += f'Started: {result["started_at"]}\n'
                if 'completed_at' in result:
                    message += f'Completed: {result["completed_at"]}\n'
                
                if status == 'completed' and result.get('has_result'):
                    message += '\n✅ Evaluation completed successfully!\n'
                    message += 'Use /get_evaluation_results to see the full report.'
                
                return {
                    'success': True,
                    'message': message,
                    'data': result,
                    'type': MessageType.SYSTEM.value
                }
            else:
                return {
                    'success': False,
                    'message': f'❌ {result["message"]}',
                    'type': MessageType.ERROR.value
                }
                
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting evaluation status: {str(e)}',
                'type': MessageType.ERROR.value
            }
    
    def handle_evaluation_history(args, user_id, session_id):
        """Handle evaluation history command"""
        try:
            limit = args.get('limit', 10)
            history = enhanced_chatbot.get_evaluation_history(user_id, limit)
            
            if not history:
                return {
                    'success': True,
                    'message': '📭 No evaluation history found',
                    'type': MessageType.INFO.value
                }
            
            message = f'📊 Evaluation History (Last {len(history)} evaluations):\n\n'
            
            for i, eval_item in enumerate(history, 1):
                status_emoji = '✅' if eval_item['status'] == 'completed' else '⏳' if eval_item['status'] == 'running' else '❌'
                message += f'{i}. {status_emoji} {eval_item["evaluation_type"].upper()}\n'
                message += f'   ID: {eval_item["id"]}\n'
                message += f'   Status: {eval_item["status"]}\n'
                message += f'   Created: {eval_item["created_at"][:10]}\n'
                
                if eval_item['completed_at']:
                    message += f'   Completed: {eval_item["completed_at"][:10]}\n'
                
                message += '\n'
            
            return {
                'success': True,
                'message': message,
                'data': {'history': history, 'count': len(history)},
                'type': MessageType.DATA.value
            }
            
        except Exception as e:
            return {
                'success': False,
                'message': f'Error getting evaluation history: {str(e)}',
                'type': MessageType.ERROR.value
            }
    
    logger.info("Evaluation capabilities integrated with chatbot")
    return main_chatbot

# ============================================================================
# TESTING & DEMONSTRATION
# ============================================================================

if __name__ == "__main__":
    """Test the enhanced evaluation system"""
    print("=" * 60)
    print("ENHANCED EVALUATION SYSTEM TEST")
    print("=" * 60)
    
    # Create enhanced chatbot
    chatbot = EnhancedChatbot()
    
    # Test quick classification evaluation
    print("\n1. Testing Quick Classification Evaluation:")
    print("-" * 40)
    
    y_true_cls = np.random.choice([0, 1, 2], size=100)
    y_pred_cls = np.random.choice([0, 1, 2], size=100)
    
    result = chatbot.quick_evaluate_classification(
        y_true_cls, y_pred_cls, 
        model_name="Test_Classification_Model"
    )
    
    if result['success']:
        print(f"✅ Quick classification evaluation completed")
        summary = result['summary'].split('\n')[:5]
        for line in summary:
            print(f"   {line}")
    else:
        print(f"❌ Failed: {result['message']}")
    
    # Test quick regression evaluation
    print("\n2. Testing Quick Regression Evaluation:")
    print("-" * 40)
    
    y_true_reg = np.random.randn(100) * 2 + 1
    y_pred_reg = y_true_reg + np.random.randn(100) * 0.5
    
    result = chatbot.quick_evaluate_regression(
        y_true_reg, y_pred_reg,
        model_name="Test_Regression_Model"
    )
    
    if result['success']:
        print(f"✅ Quick regression evaluation completed")
        summary = result['summary'].split('\n')[:5]
        for line in summary:
            print(f"   {line}")
    else:
        print(f"❌ Failed: {result['message']}")
    
    # Test interpretation
    print("\n3. Testing Metrics Interpretation:")
    print("-" * 40)
    
    test_metrics = {
        'accuracy': 0.82,
        'precision': 0.79,
        'recall': 0.85,
        'f1_score': 0.82
    }
    
    result = chatbot.interpret_metrics(test_metrics, 'classification')
    
    if result['success']:
        print(f"✅ Metrics interpretation completed")
        print(f"   Summary: {result['summary']}")
    else:
        print(f"❌ Failed: {result['message']}")
    
    # Test async evaluation request
    print("\n4. Testing Async Evaluation Request:")
    print("-" * 40)
    
    eval_params = {
        'model_name': 'Async_Test_Model',
        'y_true': y_true_cls.tolist(),
        'y_pred': y_pred_cls.tolist()
    }
    
    result = chatbot.request_evaluation('classification', eval_params, user_id=1)
    
    if result['success']:
        eval_id = result['evaluation_id']
        print(f"✅ Async evaluation requested")
        print(f"   Evaluation ID: {eval_id}")
        print(f"   Status: {result['status']}")
        
        # Check status after a short delay
        time.sleep(1)
        status_result = chatbot.get_evaluation_status(eval_id)
        print(f"   Current Status: {status_result.get('status')}")
    else:
        print(f"❌ Failed: {result['message']}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)