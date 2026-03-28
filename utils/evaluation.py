"""
An advanced analytical engine that generates detailed performance reports for both classification and regression models.
It calculates professional-grade metrics including ROC-AUC, F1-Score, and Mean Absolute Error for predictive accuracy.
The module uses the 'Agg' backend to generate complex visualizations (like Confusion Matrices) without requiring a GUI.
It produces interactive Plotly subplots and HTML reports that provide a deep-dive into model strengths and weaknesses.
This acts as the 'Scientific Auditor,' ensuring every model update meets the required statistical benchmarks.
"""


import pandas as pd
import numpy as np
import matplotlib
# 'Agg' backend prevents crashes on servers/web apps (runs without a monitor)
matplotlib.use('Agg') 
import matplotlib.pyplot as plt
import seaborn as sns
from sklearn.metrics import (accuracy_score, classification_report, confusion_matrix, 
                           mean_absolute_error, mean_squared_error, r2_score,
                           precision_score, recall_score, f1_score, roc_auc_score, 
                           roc_curve, auc, precision_recall_curve, average_precision_score,
                           mean_absolute_percentage_error, explained_variance_score)
import os
import sys
import json
import warnings
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any, Union
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots
warnings.filterwarnings('ignore')

# Allow importing config from parent directory
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
try:
    from config.config import Config
    config = Config()
except ImportError:
    config = None

class Evaluator:
    """
    Comprehensive model evaluation and analysis system.
    Provides detailed metrics, visualizations, and business impact analysis.
    """
    
    def __init__(self, output_dir: Optional[str] = None):
        """
        Initialize the evaluator with output directory configuration.
        
        Args:
            output_dir: Directory to save evaluation outputs
        """
        self.config = Config() if config is None else config
        
        # Set up output directories
        project_root = Path(__file__).resolve().parent.parent
        
        # Try multiple possible plot directories
        possible_dirs = [
            project_root / 'soccer_match_prediction' / 'app' / 'static' / 'plots',
            project_root / 'app' / 'static' / 'plots',
            project_root / 'static' / 'plots',
            Path(output_dir) if output_dir else project_root / 'evaluation_outputs'
        ]
        
        self.plots_dir = None
        for directory in possible_dirs:
            try:
                directory.mkdir(parents=True, exist_ok=True)
                self.plots_dir = directory
                break
            except Exception:
                continue
        
        if self.plots_dir is None:
            # Fallback to current directory
            self.plots_dir = Path.cwd() / 'plots'
            self.plots_dir.mkdir(exist_ok=True)
        
        # Create subdirectories for different plot types
        self.subdirs = {
            'confusion_matrices': self.plots_dir / 'confusion_matrices',
            'roc_curves': self.plots_dir / 'roc_curves',
            'feature_importance': self.plots_dir / 'feature_importance',
            'performance_trends': self.plots_dir / 'performance_trends',
            'roi_analysis': self.plots_dir / 'roi_analysis',
            'comparative': self.plots_dir / 'comparative'
        }
        
        for subdir in self.subdirs.values():
            subdir.mkdir(exist_ok=True)
        
        # Style configuration
        self.styles = {
            'dark': {
                'background': '#1a1a1a',
                'text': '#ffffff',
                'grid': '#333333',
                'primary': '#00F2C3',
                'secondary': '#0088cc',
                'warning': '#ff9900',
                'danger': '#ff3333'
            },
            'light': {
                'background': '#ffffff',
                'text': '#333333',
                'grid': '#e0e0e0',
                'primary': '#0088cc',
                'secondary': '#00F2C3',
                'warning': '#ff9900',
                'danger': '#ff3333'
            }
        }
        
        self.current_style = 'dark'
        self.style = self.styles[self.current_style]
        
        print(f"📊 Evaluator initialized")
        print(f"   📁 Plots directory: {self.plots_dir}")
        print(f"   🎨 Style: {self.current_style}")

    def evaluate_classification(self, y_true: Union[List, np.ndarray], 
                              y_pred: Union[List, np.ndarray], 
                              y_prob: Optional[np.ndarray] = None,
                              target_name: str = "WLD", 
                              class_names: Optional[List[str]] = None,
                              save_plots: bool = True) -> Dict[str, Any]:
        """
        Comprehensive classification model evaluation.
        
        Args:
            y_true: True labels
            y_pred: Predicted labels
            y_prob: Predicted probabilities (optional)
            target_name: Name of target variable
            class_names: Names of classes
            save_plots: Whether to save plots
            
        Returns:
            dict: Comprehensive evaluation metrics
        """
        print(f"\n📊 COMPREHENSIVE CLASSIFICATION EVALUATION: {target_name}")
        print("=" * 60)
        
        y_true = np.array(y_true)
        y_pred = np.array(y_pred)
        
        if class_names is None:
            class_names = [f'Class {i}' for i in np.unique(y_true)]
        
        # Calculate metrics
        metrics = {}
        
        # Basic metrics
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
        
        # Advanced metrics if probabilities available
        if y_prob is not None:
            try:
                # ROC AUC (requires binary or one-vs-rest for multiclass)
                if len(np.unique(y_true)) == 2:
                    metrics['roc_auc'] = roc_auc_score(y_true, y_prob[:, 1])
                else:
                    # Multiclass ROC AUC
                    metrics['roc_auc'] = roc_auc_score(y_true, y_prob, multi_class='ovr')
                
                # Average Precision
                metrics['average_precision'] = average_precision_score(y_true, y_prob[:, 1] if y_prob.shape[1] == 2 else y_prob)
            except Exception as e:
                print(f"⚠️ Advanced metrics calculation failed: {e}")
                metrics['roc_auc'] = None
                metrics['average_precision'] = None
        
        # Display results
        print(f"✅ Accuracy: {metrics['accuracy']:.2%}")
        print(f"📏 Precision: {metrics['precision']:.2%}")
        print(f"🔍 Recall: {metrics['recall']:.2%}")
        print(f"⚖️ F1-Score: {metrics['f1_score']:.2%}")
        
        if metrics.get('roc_auc') is not None:
            print(f"📈 ROC AUC: {metrics['roc_auc']:.3f}")
        
        print("\n📝 Detailed Classification Report:")
        print(classification_report(y_true, y_pred, target_names=class_names))
        
        # Save plots
        if save_plots:
            self._plot_confusion_matrix(y_true, y_pred, class_names, target_name)
            
            if y_prob is not None:
                self._plot_roc_curve(y_true, y_prob, target_name, class_names)
                self._plot_precision_recall_curve(y_true, y_prob, target_name, class_names)
            
            self._plot_class_distribution(y_true, y_pred, target_name, class_names)
        
        # Save metrics to file
        self._save_metrics(metrics, f'classification_{target_name}')
        
        return metrics

    def evaluate_regression(self, y_true: Union[List, np.ndarray], 
                           y_pred: Union[List, np.ndarray],
                           target_name: str = "TotalGoals",
                           save_plots: bool = True) -> Dict[str, Any]:
        """
        Comprehensive regression model evaluation.
        
        Args:
            y_true: True values
            y_pred: Predicted values
            target_name: Name of target variable
            save_plots: Whether to save plots
            
        Returns:
            dict: Comprehensive evaluation metrics
        """
        print(f"\n📊 COMPREHENSIVE REGRESSION EVALUATION: {target_name}")
        print("=" * 60)
        
        y_true = np.array(y_true).astype(float)
        y_pred = np.array(y_pred).astype(float)
        
        # Remove NaN values
        mask = ~(np.isnan(y_true) | np.isnan(y_pred))
        y_true = y_true[mask]
        y_pred = y_pred[mask]
        
        if len(y_true) == 0:
            print("⚠️ No valid data points after NaN removal")
            return {}
        
        # Calculate metrics
        metrics = {}
        
        # Basic metrics
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
        
        # Percentage within thresholds
        thresholds = [0.5, 1.0, 1.5, 2.0]
        for threshold in thresholds:
            within = np.sum(np.abs(y_true - y_pred) <= threshold) / len(y_true)
            metrics[f'within_{threshold}'] = within
        
        # Display results
        print(f"📉 Mean Absolute Error (MAE): {metrics['mae']:.4f}")
        print(f"📉 Root Mean Squared Error (RMSE): {metrics['rmse']:.4f}")
        print(f"📊 R² Score: {metrics['r2']:.3f}")
        print(f"📈 Explained Variance: {metrics['explained_variance']:.3f}")
        print(f"📋 Mean Absolute Percentage Error: {metrics['mape']:.2%}")
        
        print(f"\n📏 Error Statistics:")
        print(f"   Mean Error: {metrics['mean_error']:.4f}")
        print(f"   Std Error: {metrics['std_error']:.4f}")
        print(f"   Max Error: {metrics['max_error']:.4f}")
        
        print(f"\n🎯 Predictions within tolerance:")
        for threshold in thresholds:
            print(f"   ±{threshold}: {metrics[f'within_{threshold}']:.1%}")
        
        # Save plots
        if save_plots:
            self._plot_regression_scatter(y_true, y_pred, target_name)
            self._plot_error_distribution(y_true, y_pred, target_name)
            self._plot_residuals(y_true, y_pred, target_name)
            self._plot_prediction_error(y_true, y_pred, target_name)
        
        # Save metrics to file
        self._save_metrics(metrics, f'regression_{target_name}')
        
        return metrics

    def calculate_roi(self, df: pd.DataFrame, preds: Union[List, np.ndarray], 
                     target_col: str = "Target_WLD", stake: float = 10.0,
                     betting_strategy: str = 'fixed', bankroll: float = 1000.0,
                     save_plots: bool = True) -> Dict[str, Any]:
        """
        Advanced ROI analysis with multiple betting strategies.
        
        Args:
            df: DataFrame with match data and odds
            preds: Model predictions
            target_col: Column name for true outcomes
            stake: Base betting stake
            betting_strategy: Betting strategy ('fixed', 'kelly', 'proportional')
            bankroll: Initial bankroll for bankroll management
            save_plots: Whether to save plots
            
        Returns:
            dict: ROI analysis results
        """
        print(f"\n💰 ADVANCED BETTING ROI ANALYSIS")
        print("=" * 60)
        
        # Reset index for alignment
        df_reset = df.reset_index(drop=True)
        preds = np.array(preds)
        
        # Check required columns
        required_cols = ['OddHome', 'OddDraw', 'OddAway']
        if not all(col in df_reset.columns for col in required_cols):
            print("⚠️ Odds columns missing. Skipping ROI analysis.")
            return {}
        
        # Get result mapping from config
        result_map = getattr(self.config, 'RESULT_MAP', None) or {}
        
        # Initialize tracking
        results = {
            'fixed': {'bankroll': bankroll, 'equity': [bankroll], 'bets': 0, 'wins': 0},
            'kelly': {'bankroll': bankroll, 'equity': [bankroll], 'bets': 0, 'wins': 0},
            'proportional': {'bankroll': bankroll, 'equity': [bankroll], 'bets': 0, 'wins': 0}
        }
        
        detailed_results = []
        
        for i, row in df_reset.iterrows():
            if i >= len(preds):
                break
            
            # Get actual and predicted outcomes
            actual_raw = row[target_col]
            prediction_raw = preds[i]
            
            # Map to numeric codes
            actual = self._map_outcome_to_code(actual_raw, result_map)
            prediction = self._map_outcome_to_code(prediction_raw, result_map)
            
            if actual is None or prediction is None:
                continue
            
            # Get odds for prediction
            odds = self._get_odds_for_prediction(row, prediction, result_map)
            
            if odds < 1.01:  # Skip invalid odds
                continue
            
            # Calculate probability from odds
            implied_prob = 1 / odds
            
            # For each betting strategy
            for strategy in ['fixed', 'kelly', 'proportional']:
                # Calculate stake for this strategy
                if strategy == 'fixed':
                    stake_amount = stake
                elif strategy == 'kelly':
                    # Kelly Criterion: f* = (bp - q) / b
                    b = odds - 1
                    p = 0.5  # Estimated probability (could be model confidence)
                    q = 1 - p
                    kelly_fraction = max(0, (b * p - q) / b)
                    stake_amount = results[strategy]['bankroll'] * kelly_fraction * 0.5  # Half-kelly for safety
                else:  # proportional
                    stake_amount = results[strategy]['bankroll'] * 0.02  # 2% of bankroll
                
                # Ensure stake is reasonable
                stake_amount = min(stake_amount, results[strategy]['bankroll'] * 0.1)  # Max 10%
                stake_amount = max(stake_amount, 1.0)  # Minimum stake
                
                # Place bet
                results[strategy]['bets'] += 1
                
                if prediction == actual:  # Win
                    profit = stake_amount * (odds - 1)
                    results[strategy]['bankroll'] += profit
                    results[strategy]['wins'] += 1
                    outcome = 'win'
                else:  # Loss
                    results[strategy]['bankroll'] -= stake_amount
                    outcome = 'loss'
                
                # Record equity
                results[strategy]['equity'].append(results[strategy]['bankroll'])
                
                # Store detailed result
                detailed_results.append({
                    'match_id': i,
                    'strategy': strategy,
                    'prediction': prediction,
                    'actual': actual,
                    'odds': odds,
                    'stake': stake_amount,
                    'outcome': outcome,
                    'profit': profit if outcome == 'win' else -stake_amount,
                    'bankroll': results[strategy]['bankroll']
                })
        
        # Calculate final metrics
        roi_analysis = {}
        
        for strategy in results.keys():
            if results[strategy]['bets'] > 0:
                total_profit = results[strategy]['bankroll'] - bankroll
                roi_percent = (total_profit / (results[strategy]['bets'] * stake)) * 100
                win_rate = results[strategy]['wins'] / results[strategy]['bets']
                
                roi_analysis[strategy] = {
                    'total_bets': results[strategy]['bets'],
                    'wins': results[strategy]['wins'],
                    'losses': results[strategy]['bets'] - results[strategy]['wins'],
                    'win_rate': win_rate,
                    'total_profit': total_profit,
                    'roi_percent': roi_percent,
                    'final_bankroll': results[strategy]['bankroll'],
                    'max_drawdown': self._calculate_max_drawdown(results[strategy]['equity']),
                    'sharpe_ratio': self._calculate_sharpe_ratio(results[strategy]['equity']),
                    'profit_factor': self._calculate_profit_factor(detailed_results, strategy)
                }
                
                # Display results
                print(f"\n📊 {strategy.upper()} Strategy:")
                print(f"   Bets: {roi_analysis[strategy]['total_bets']}")
                print(f"   Win Rate: {roi_analysis[strategy]['win_rate']:.1%}")
                print(f"   Profit: ${roi_analysis[strategy]['total_profit']:.2f}")
                print(f"   ROI: {roi_analysis[strategy]['roi_percent']:.1f}%")
                print(f"   Final Bankroll: ${roi_analysis[strategy]['final_bankroll']:.2f}")
                print(f"   Max Drawdown: {roi_analysis[strategy]['max_drawdown']:.1%}")
        
        # Save plots
        if save_plots:
            self._plot_roi_curves(results, target_col)
            self._plot_betting_performance(roi_analysis)
            self._plot_strategy_comparison(roi_analysis)
        
        # Save detailed results
        self._save_detailed_results(detailed_results, target_col)
        
        return roi_analysis

    def evaluate_model_comparison(self, models: Dict[str, Any], 
                                X_test: np.ndarray, y_test: np.ndarray,
                                task: str = 'classification',
                                save_plots: bool = True) -> Dict[str, Any]:
        """
        Compare multiple models on the same test set.
        
        Args:
            models: Dictionary of model name -> model object
            X_test: Test features
            y_test: Test labels
            task: 'classification' or 'regression'
            save_plots: Whether to save plots
            
        Returns:
            dict: Comparison results
        """
        print(f"\n🔬 MODEL COMPARISON ANALYSIS")
        print("=" * 60)
        
        comparison = {}
        
        for name, model in models.items():
            print(f"\n📋 Evaluating {name}...")
            
            try:
                if task == 'classification':
                    y_pred = model.predict(X_test)
                    metrics = self.evaluate_classification(y_test, y_pred, 
                                                         target_name=name,
                                                         save_plots=False)
                    comparison[name] = {
                        'accuracy': metrics['accuracy'],
                        'f1_score': metrics['f1_score'],
                        'precision': metrics['precision'],
                        'recall': metrics['recall']
                    }
                else:  # regression
                    y_pred = model.predict(X_test)
                    metrics = self.evaluate_regression(y_test, y_pred,
                                                     target_name=name,
                                                     save_plots=False)
                    comparison[name] = {
                        'mae': metrics['mae'],
                        'rmse': metrics['rmse'],
                        'r2': metrics['r2'],
                        'mape': metrics['mape']
                    }
                    
            except Exception as e:
                print(f"⚠️ Error evaluating {name}: {e}")
                comparison[name] = {'error': str(e)}
        
        # Create comparison table
        comparison_df = pd.DataFrame(comparison).T
        
        print("\n🏆 MODEL COMPARISON RESULTS:")
        print(comparison_df.to_string())
        
        # Save plots
        if save_plots:
            self._plot_model_comparison(comparison, task)
        
        # Save comparison results
        self._save_comparison_results(comparison, task)
        
        return comparison

    # --- HELPER METHODS ---
    
    def _map_outcome_to_code(self, outcome, result_map):
        """Map outcome to numeric code."""
        if outcome is None or pd.isna(outcome):
            return None
        
        # If already numeric
        if isinstance(outcome, (int, float)):
            return int(outcome)
        
        # Map using result_map
        if result_map and str(outcome) in result_map:
            return result_map[str(outcome)]
        
        # Default mapping
        if str(outcome).upper() == 'H':
            return 2  # Home win
        elif str(outcome).upper() == 'D':
            return 1  # Draw
        elif str(outcome).upper() == 'A':
            return 0  # Away win
        
        return None
    
    def _get_odds_for_prediction(self, row, prediction, result_map):
        """Get odds for a given prediction."""
        if prediction == result_map.get('H', 2):
            return row.get('OddHome', 0)
        elif prediction == result_map.get('D', 1):
            return row.get('OddDraw', 0)
        elif prediction == result_map.get('A', 0):
            return row.get('OddAway', 0)
        else:
            return 0
    
    def _calculate_max_drawdown(self, equity_curve):
        """Calculate maximum drawdown from equity curve."""
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
        """Calculate Sharpe ratio from equity curve."""
        if len(equity_curve) < 2:
            return 0
        
        returns = np.diff(equity_curve) / equity_curve[:-1]
        
        if len(returns) == 0 or np.std(returns) == 0:
            return 0
        
        return np.mean(returns) / np.std(returns) * np.sqrt(252)  # Annualized
    
    def _calculate_profit_factor(self, detailed_results, strategy):
        """Calculate profit factor (gross wins / gross losses)."""
        strategy_results = [r for r in detailed_results if r['strategy'] == strategy]
        
        gross_wins = sum(r['profit'] for r in strategy_results if r['profit'] > 0)
        gross_losses = abs(sum(r['profit'] for r in strategy_results if r['profit'] < 0))
        
        if gross_losses == 0:
            return float('inf')
        
        return gross_wins / gross_losses
    
    # --- PLOTTING METHODS ---
    
    def _plot_confusion_matrix(self, y_true, y_pred, class_names, filename_suffix):
        """Plot enhanced confusion matrix."""
        try:
            plt.figure(figsize=(10, 8))
            cm = confusion_matrix(y_true, y_pred)
            
            # Calculate percentages
            cm_percent = cm.astype('float') / cm.sum(axis=1)[:, np.newaxis] * 100
            
            # Create heatmap
            sns.heatmap(cm, annot=True, fmt='d', cmap='Blues', 
                       xticklabels=class_names, yticklabels=class_names,
                       cbar_kws={'label': 'Count'})
            
            # Overlay percentages
            for i in range(len(class_names)):
                for j in range(len(class_names)):
                    if cm[i, j] > 0:
                        plt.text(j + 0.5, i + 0.8, f'{cm_percent[i, j]:.1f}%',
                                ha='center', va='center', color='red', fontsize=9)
            
            plt.title(f'Confusion Matrix: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.ylabel('Actual', fontsize=12)
            plt.xlabel('Predicted', fontsize=12)
            plt.tight_layout()
            
            path = self.subdirs['confusion_matrices'] / f'cm_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            # Also create interactive plotly version
            self._create_interactive_confusion_matrix(cm, class_names, filename_suffix)
            
            print(f"   ✅ Saved confusion matrix: {path}")
            
        except Exception as e:
            print(f"   ⚠️ Confusion matrix plotting failed: {e}")
    
    def _create_interactive_confusion_matrix(self, cm, class_names, filename_suffix):
        """Create interactive confusion matrix using Plotly."""
        try:
            fig = go.Figure(data=go.Heatmap(
                z=cm,
                x=class_names,
                y=class_names,
                text=cm,
                texttemplate='%{text}',
                textfont={"size": 12},
                colorscale='Blues',
                showscale=True
            ))
            
            fig.update_layout(
                title=f'Confusion Matrix: {filename_suffix}',
                xaxis_title='Predicted',
                yaxis_title='Actual',
                width=600,
                height=500
            )
            
            path = self.subdirs['confusion_matrices'] / f'cm_interactive_{filename_suffix}.html'
            fig.write_html(path)
            
        except Exception as e:
            print(f"   ⚠️ Interactive confusion matrix failed: {e}")
    
    def _plot_roc_curve(self, y_true, y_prob, filename_suffix, class_names):
        """Plot ROC curve for classification."""
        try:
            plt.figure(figsize=(10, 8))
            
            if len(np.unique(y_true)) == 2:  # Binary classification
                fpr, tpr, _ = roc_curve(y_true, y_prob[:, 1])
                roc_auc = auc(fpr, tpr)
                
                plt.plot(fpr, tpr, color='darkorange', lw=2,
                        label=f'ROC curve (AUC = {roc_auc:.2f})')
                plt.plot([0, 1], [0, 1], color='navy', lw=2, linestyle='--')
                
            else:  # Multiclass classification
                from sklearn.preprocessing import label_binarize
                
                # Binarize the output
                y_true_bin = label_binarize(y_true, classes=np.unique(y_true))
                n_classes = y_true_bin.shape[1]
                
                # Compute ROC curve and ROC area for each class
                for i in range(n_classes):
                    fpr, tpr, _ = roc_curve(y_true_bin[:, i], y_prob[:, i])
                    roc_auc = auc(fpr, tpr)
                    plt.plot(fpr, tpr, lw=2,
                            label=f'Class {class_names[i]} (AUC = {roc_auc:.2f})')
            
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('False Positive Rate', fontsize=12)
            plt.ylabel('True Positive Rate', fontsize=12)
            plt.title(f'ROC Curve: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.legend(loc="lower right")
            plt.grid(True, alpha=0.3)
            
            path = self.subdirs['roc_curves'] / f'roc_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            print(f"   ✅ Saved ROC curve: {path}")
            
        except Exception as e:
            print(f"   ⚠️ ROC curve plotting failed: {e}")
    
    def _plot_precision_recall_curve(self, y_true, y_prob, filename_suffix, class_names):
        """Plot Precision-Recall curve."""
        try:
            plt.figure(figsize=(10, 8))
            
            if len(np.unique(y_true)) == 2:  # Binary classification
                precision, recall, _ = precision_recall_curve(y_true, y_prob[:, 1])
                avg_precision = average_precision_score(y_true, y_prob[:, 1])
                
                plt.plot(recall, precision, color='blue', lw=2,
                        label=f'Precision-Recall (AP = {avg_precision:.2f})')
                
            else:  # Multiclass classification
                from sklearn.preprocessing import label_binarize
                
                y_true_bin = label_binarize(y_true, classes=np.unique(y_true))
                n_classes = y_true_bin.shape[1]
                
                for i in range(n_classes):
                    precision, recall, _ = precision_recall_curve(y_true_bin[:, i], y_prob[:, i])
                    avg_precision = average_precision_score(y_true_bin[:, i], y_prob[:, i])
                    plt.plot(recall, precision, lw=2,
                            label=f'Class {class_names[i]} (AP = {avg_precision:.2f})')
            
            plt.xlim([0.0, 1.0])
            plt.ylim([0.0, 1.05])
            plt.xlabel('Recall', fontsize=12)
            plt.ylabel('Precision', fontsize=12)
            plt.title(f'Precision-Recall Curve: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.legend(loc="best")
            plt.grid(True, alpha=0.3)
            
            path = self.subdirs['roc_curves'] / f'pr_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            print(f"   ✅ Saved Precision-Recall curve: {path}")
            
        except Exception as e:
            print(f"   ⚠️ Precision-Recall curve plotting failed: {e}")
    
    def _plot_regression_scatter(self, y_true, y_pred, filename_suffix):
        """Enhanced regression scatter plot."""
        try:
            fig, axes = plt.subplots(2, 2, figsize=(15, 12))
            
            # Scatter plot with regression line
            ax = axes[0, 0]
            ax.scatter(y_true, y_pred, alpha=0.6, color=self.style['primary'], edgecolor='white', s=50)
            
            # Add perfect prediction line
            lims = [min(y_true.min(), y_pred.min()), max(y_true.max(), y_pred.max())]
            ax.plot(lims, lims, 'k--', alpha=0.75, zorder=0, label='Perfect Prediction')
            
            # Add regression line
            m, b = np.polyfit(y_true, y_pred, 1)
            ax.plot(y_true, m*y_true + b, color='red', alpha=0.8, label=f'Fit: y={m:.2f}x+{b:.2f}')
            
            ax.set_xlabel('Actual Goals', fontsize=12)
            ax.set_ylabel('Predicted Goals', fontsize=12)
            ax.set_title('Actual vs Predicted', fontsize=14, fontweight='bold')
            ax.legend()
            ax.grid(True, alpha=0.3)
            
            # Error distribution
            ax = axes[0, 1]
            errors = y_pred - y_true
            ax.hist(errors, bins=30, alpha=0.7, color=self.style['secondary'], edgecolor='black')
            ax.axvline(x=0, color='red', linestyle='--', linewidth=2)
            ax.set_xlabel('Prediction Error', fontsize=12)
            ax.set_ylabel('Frequency', fontsize=12)
            ax.set_title('Error Distribution', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # Residuals plot
            ax = axes[1, 0]
            ax.scatter(y_pred, errors, alpha=0.6, color=self.style['warning'], s=50)
            ax.axhline(y=0, color='red', linestyle='--', linewidth=2)
            ax.set_xlabel('Predicted Values', fontsize=12)
            ax.set_ylabel('Residuals', fontsize=12)
            ax.set_title('Residuals Plot', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            # QQ plot
            ax = axes[1, 1]
            from scipy import stats
            stats.probplot(errors, dist="norm", plot=ax)
            ax.get_lines()[0].set_marker('o')
            ax.get_lines()[0].set_markersize(4)
            ax.get_lines()[0].set_markerfacecolor(self.style['primary'])
            ax.get_lines()[0].set_markeredgecolor('white')
            ax.get_lines()[1].set_color('red')
            ax.set_title('Q-Q Plot of Errors', fontsize=14, fontweight='bold')
            ax.grid(True, alpha=0.3)
            
            plt.suptitle(f'Regression Analysis: {filename_suffix}', fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            path = self.plots_dir / f'regression_analysis_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            print(f"   ✅ Saved regression analysis: {path}")
            
        except Exception as e:
            print(f"   ⚠️ Regression plotting failed: {e}")
    
    def _plot_roi_curves(self, results, filename_suffix):
        """Plot ROI curves for different betting strategies."""
        try:
            plt.figure(figsize=(12, 8))
            
            colors = {'fixed': self.style['primary'], 
                     'kelly': self.style['secondary'], 
                     'proportional': self.style['warning']}
            
            for strategy, data in results.items():
                if len(data['equity']) > 1:
                    plt.plot(data['equity'], label=f'{strategy.capitalize()} Strategy', 
                            color=colors[strategy], linewidth=2.5)
            
            plt.axhline(y=1000, color='white', linestyle='--', alpha=0.3, label='Initial Bankroll')
            plt.xlabel('Number of Bets', fontsize=12)
            plt.ylabel('Bankroll ($)', fontsize=12)
            plt.title(f'Betting Strategy Performance: {filename_suffix}', 
                     fontsize=14, fontweight='bold')
            plt.legend(loc='best')
            plt.grid(True, alpha=0.2)
            
            # Dark theme
            plt.gca().set_facecolor(self.style['background'])
            plt.gcf().set_facecolor(self.style['background'])
            plt.tick_params(colors=self.style['text'])
            plt.title(f'Betting Strategy Performance ({filename_suffix})', color=self.style['text'])
            plt.xlabel('Number of Bets', color=self.style['text'])
            plt.ylabel('Profit ($)', color=self.style['text'])
            plt.grid(color=self.style['text'], alpha=0.1)
            
            path = self.subdirs['roi_analysis'] / f'roi_curves_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            print(f"   ✅ Saved ROI curves: {path}")
            
        except Exception as e:
            print(f"   ⚠️ ROI curve plotting failed: {e}")
    
    def _plot_model_comparison(self, comparison, task):
        """Plot model comparison results."""
        try:
            comparison_df = pd.DataFrame(comparison).T
            
            if task == 'classification':
                metrics = ['accuracy', 'f1_score', 'precision', 'recall']
                title = 'Classification Model Comparison'
            else:
                metrics = ['mae', 'rmse', 'r2', 'mape']
                title = 'Regression Model Comparison'
            
            fig, axes = plt.subplots(2, 2, figsize=(15, 10))
            axes = axes.flatten()
            
            for idx, metric in enumerate(metrics):
                if metric in comparison_df.columns:
                    ax = axes[idx]
                    
                    # Sort by metric value
                    sorted_data = comparison_df[metric].sort_values()
                    
                    if metric in ['mae', 'rmse', 'mape']:  # Lower is better
                        colors = plt.cm.RdYlGn_r(np.linspace(0.2, 0.8, len(sorted_data)))
                    else:  # Higher is better
                        colors = plt.cm.RdYlGn(np.linspace(0.2, 0.8, len(sorted_data)))
                    
                    bars = ax.barh(range(len(sorted_data)), sorted_data.values, color=colors)
                    ax.set_yticks(range(len(sorted_data)))
                    ax.set_yticklabels(sorted_data.index)
                    
                    # Add value labels
                    for i, (name, value) in enumerate(sorted_data.items()):
                        ax.text(value, i, f' {value:.3f}', va='center')
                    
                    ax.set_xlabel(metric.replace('_', ' ').title())
                    ax.set_title(f'{metric.replace("_", " ").title()} Comparison')
                    ax.grid(True, alpha=0.3, axis='x')
            
            plt.suptitle(title, fontsize=16, fontweight='bold')
            plt.tight_layout()
            
            path = self.subdirs['comparative'] / f'model_comparison_{task}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
            print(f"   ✅ Saved model comparison: {path}")
            
        except Exception as e:
            print(f"   ⚠️ Model comparison plotting failed: {e}")
    
    def _save_metrics(self, metrics, filename):
        """Save evaluation metrics to JSON file."""
        try:
            metrics_file = self.plots_dir / f'{filename}_metrics.json'
            
            # Convert numpy types to Python types for JSON serialization
            def convert_to_serializable(obj):
                if isinstance(obj, (np.integer, np.floating)):
                    return float(obj)
                elif isinstance(obj, np.ndarray):
                    return obj.tolist()
                elif isinstance(obj, pd.DataFrame):
                    return obj.to_dict()
                else:
                    return obj
            
            serializable_metrics = convert_to_serializable(metrics)
            
            with open(metrics_file, 'w') as f:
                json.dump(serializable_metrics, f, indent=2, default=str)
            
            print(f"   💾 Saved metrics: {metrics_file}")
            
        except Exception as e:
            print(f"   ⚠️ Failed to save metrics: {e}")
    
    def _save_detailed_results(self, results, filename):
        """Save detailed betting results to CSV."""
        try:
            results_file = self.subdirs['roi_analysis'] / f'{filename}_detailed_results.csv'
            results_df = pd.DataFrame(results)
            results_df.to_csv(results_file, index=False)
            
            print(f"   💾 Saved detailed results: {results_file}")
            
        except Exception as e:
            print(f"   ⚠️ Failed to save detailed results: {e}")
    
    def _save_comparison_results(self, comparison, task):
        """Save model comparison results."""
        try:
            comparison_file = self.subdirs['comparative'] / f'model_comparison_{task}.json'
            
            with open(comparison_file, 'w') as f:
                json.dump(comparison, f, indent=2, default=str)
            
            print(f"   💾 Saved comparison results: {comparison_file}")
            
        except Exception as e:
            print(f"   ⚠️ Failed to save comparison results: {e}")
    
    def _plot_class_distribution(self, y_true, y_pred, filename_suffix, class_names):
        """Plot class distribution comparison."""
        try:
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
            
            # Actual distribution
            unique, counts = np.unique(y_true, return_counts=True)
            axes[0].bar(range(len(unique)), counts, color=self.style['primary'], alpha=0.7)
            axes[0].set_xticks(range(len(unique)))
            axes[0].set_xticklabels([class_names[i] for i in unique])
            axes[0].set_title('Actual Class Distribution', fontsize=12)
            axes[0].set_ylabel('Count')
            axes[0].grid(True, alpha=0.3)
            
            # Predicted distribution
            unique_pred, counts_pred = np.unique(y_pred, return_counts=True)
            axes[1].bar(range(len(unique_pred)), counts_pred, color=self.style['secondary'], alpha=0.7)
            axes[1].set_xticks(range(len(unique_pred)))
            axes[1].set_xticklabels([class_names[i] for i in unique_pred])
            axes[1].set_title('Predicted Class Distribution', fontsize=12)
            axes[1].set_ylabel('Count')
            axes[1].grid(True, alpha=0.3)
            
            plt.suptitle(f'Class Distribution: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            path = self.plots_dir / f'class_distribution_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Class distribution plotting failed: {e}")
    
    def _plot_error_distribution(self, y_true, y_pred, filename_suffix):
        """Plot error distribution for regression."""
        try:
            errors = y_pred - y_true
            
            plt.figure(figsize=(10, 6))
            
            plt.hist(errors, bins=30, alpha=0.7, color=self.style['primary'], 
                    edgecolor='black', density=True)
            
            # Add normal distribution overlay
            from scipy.stats import norm
            mu, std = norm.fit(errors)
            xmin, xmax = plt.xlim()
            x = np.linspace(xmin, xmax, 100)
            p = norm.pdf(x, mu, std)
            plt.plot(x, p, 'k', linewidth=2, 
                    label=f'Normal fit: μ={mu:.2f}, σ={std:.2f}')
            
            plt.axvline(x=0, color='red', linestyle='--', linewidth=2, label='Zero Error')
            plt.xlabel('Prediction Error', fontsize=12)
            plt.ylabel('Density', fontsize=12)
            plt.title(f'Error Distribution: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            path = self.plots_dir / f'error_distribution_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Error distribution plotting failed: {e}")
    
    def _plot_residuals(self, y_true, y_pred, filename_suffix):
        """Plot residuals analysis."""
        try:
            residuals = y_pred - y_true
            
            fig, axes = plt.subplots(1, 2, figsize=(12, 5))
            
            # Residuals vs predicted
            axes[0].scatter(y_pred, residuals, alpha=0.6, color=self.style['primary'], s=50)
            axes[0].axhline(y=0, color='red', linestyle='--', linewidth=2)
            axes[0].set_xlabel('Predicted Values', fontsize=12)
            axes[0].set_ylabel('Residuals', fontsize=12)
            axes[0].set_title('Residuals vs Predicted', fontsize=12)
            axes[0].grid(True, alpha=0.3)
            
            # Residuals histogram
            axes[1].hist(residuals, bins=30, alpha=0.7, color=self.style['secondary'], 
                        edgecolor='black')
            axes[1].axvline(x=0, color='red', linestyle='--', linewidth=2)
            axes[1].set_xlabel('Residuals', fontsize=12)
            axes[1].set_ylabel('Frequency', fontsize=12)
            axes[1].set_title('Residuals Distribution', fontsize=12)
            axes[1].grid(True, alpha=0.3)
            
            plt.suptitle(f'Residuals Analysis: {filename_suffix}', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            path = self.plots_dir / f'residuals_analysis_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Residuals plotting failed: {e}")
    
    def _plot_prediction_error(self, y_true, y_pred, filename_suffix):
        """Plot prediction error visualization."""
        try:
            plt.figure(figsize=(10, 6))
            
            # Sort by true values for better visualization
            sort_idx = np.argsort(y_true)
            y_true_sorted = y_true[sort_idx]
            y_pred_sorted = y_pred[sort_idx]
            
            plt.plot(range(len(y_true_sorted)), y_true_sorted, 
                    label='Actual', color=self.style['primary'], linewidth=2, marker='o')
            plt.plot(range(len(y_pred_sorted)), y_pred_sorted, 
                    label='Predicted', color=self.style['secondary'], linewidth=2, marker='s')
            
            # Fill between for error visualization
            plt.fill_between(range(len(y_true_sorted)), 
                           y_true_sorted, y_pred_sorted, 
                           alpha=0.2, color=self.style['warning'], label='Error')
            
            plt.xlabel('Sample Index (Sorted by Actual Value)', fontsize=12)
            plt.ylabel('Value', fontsize=12)
            plt.title(f'Prediction Error Visualization: {filename_suffix}', 
                     fontsize=14, fontweight='bold')
            plt.legend()
            plt.grid(True, alpha=0.3)
            
            path = self.plots_dir / f'prediction_error_{filename_suffix}.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Prediction error plotting failed: {e}")
    
    def _plot_betting_performance(self, roi_analysis):
        """Plot betting performance metrics."""
        try:
            strategies = list(roi_analysis.keys())
            metrics = ['roi_percent', 'win_rate', 'total_profit']
            
            fig, axes = plt.subplots(1, 3, figsize=(15, 5))
            
            for idx, metric in enumerate(metrics):
                ax = axes[idx]
                values = [roi_analysis[s][metric] for s in strategies]
                
                colors = plt.cm.Set3(np.linspace(0, 1, len(strategies)))
                bars = ax.bar(strategies, values, color=colors, edgecolor='black')
                
                # Add value labels
                for bar, value in zip(bars, values):
                    height = bar.get_height()
                    ax.text(bar.get_x() + bar.get_width()/2., height + 0.01*max(values),
                           f'{value:.1f}' if metric != 'total_profit' else f'${value:.0f}',
                           ha='center', va='bottom')
                
                ax.set_ylabel(metric.replace('_', ' ').title())
                ax.set_title(f'{metric.replace("_", " ").title()} by Strategy')
                ax.grid(True, alpha=0.3, axis='y')
            
            plt.suptitle('Betting Strategy Performance Comparison', fontsize=14, fontweight='bold')
            plt.tight_layout()
            
            path = self.subdirs['roi_analysis'] / 'betting_performance_comparison.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'])
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Betting performance plotting failed: {e}")
    
    def _plot_strategy_comparison(self, roi_analysis):
        """Plot radar chart for strategy comparison."""
        try:
            strategies = list(roi_analysis.keys())
            
            # Select key metrics for radar chart
            metrics = ['roi_percent', 'win_rate', 'total_profit', 'max_drawdown']
            
            fig = plt.figure(figsize=(8, 8))
            ax = fig.add_subplot(111, projection='polar')
            
            # Normalize metrics for radar chart
            normalized_data = {}
            for strategy in strategies:
                normalized = []
                for metric in metrics:
                    value = roi_analysis[strategy][metric]
                    if metric == 'max_drawdown':
                        # Invert so higher is better (lower drawdown)
                        normalized.append(1 - value)
                    else:
                        # Normalize to 0-1 range
                        max_val = max(roi_analysis[s][metric] for s in strategies)
                        min_val = min(roi_analysis[s][metric] for s in strategies)
                        if max_val != min_val:
                            normalized.append((value - min_val) / (max_val - min_val))
                        else:
                            normalized.append(0.5)
                normalized_data[strategy] = normalized
            
            # Plot each strategy
            angles = np.linspace(0, 2*np.pi, len(metrics), endpoint=False).tolist()
            angles += angles[:1]  # Close the polygon
            
            colors = plt.cm.Set3(np.linspace(0, 1, len(strategies)))
            
            for idx, strategy in enumerate(strategies):
                values = normalized_data[strategy]
                values += values[:1]  # Close the polygon
                ax.plot(angles, values, 'o-', linewidth=2, label=strategy.capitalize(), 
                       color=colors[idx])
                ax.fill(angles, values, alpha=0.1, color=colors[idx])
            
            ax.set_xticks(angles[:-1])
            ax.set_xticklabels([m.replace('_', ' ').title() for m in metrics])
            ax.set_ylim(0, 1)
            ax.set_title('Strategy Comparison (Normalized Metrics)', fontsize=14, fontweight='bold')
            ax.legend(loc='upper right', bbox_to_anchor=(1.3, 1.0))
            ax.grid(True)
            
            path = self.subdirs['roi_analysis'] / 'strategy_comparison_radar.png'
            plt.savefig(path, dpi=150, facecolor=self.style['background'], bbox_inches='tight')
            plt.close()
            
        except Exception as e:
            print(f"   ⚠️ Strategy comparison radar chart failed: {e}")

    def generate_evaluation_report(self, metrics: Dict, model_name: str, 
                                 task: str = 'classification') -> str:
        """
        Generate a comprehensive HTML evaluation report.
        
        Args:
            metrics: Evaluation metrics dictionary
            model_name: Name of the model
            task: 'classification' or 'regression'
            
        Returns:
            str: HTML report content
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Model Evaluation Report: {model_name}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background-color: #f5f5f5; }}
                .container {{ max-width: 1200px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }}
                .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 30px; }}
                .metric-card {{ background: #f8f9fa; border-left: 4px solid #007bff; padding: 15px; margin: 10px 0; border-radius: 5px; }}
                .good {{ color: #28a745; }}
                .fair {{ color: #ffc107; }}
                .poor {{ color: #dc3545; }}
                .plots {{ display: flex; flex-wrap: wrap; gap: 20px; margin: 20px 0; }}
                .plot-item {{ flex: 1 1 300px; }}
                img {{ max-width: 100%; border-radius: 5px; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }}
                th {{ background-color: #f2f2f2; }}
                .summary {{ background: #e8f4fd; padding: 20px; border-radius: 8px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📊 Model Evaluation Report</h1>
                    <p><strong>Model:</strong> {model_name} | <strong>Task:</strong> {task} | <strong>Date:</strong> {timestamp}</p>
                </div>
                
                <div class="summary">
                    <h2>📈 Performance Summary</h2>
        """
        
        if task == 'classification':
            accuracy = metrics.get('accuracy', 0)
            f1 = metrics.get('f1_score', 0)
            
            html += f"""
                    <p><strong>Accuracy:</strong> <span class="{'good' if accuracy > 0.7 else 'fair' if accuracy > 0.6 else 'poor'}">{accuracy:.2%}</span></p>
                    <p><strong>F1-Score:</strong> <span class="{'good' if f1 > 0.7 else 'fair' if f1 > 0.6 else 'poor'}">{f1:.2%}</span></p>
                    <p><strong>Precision:</strong> {metrics.get('precision', 0):.2%}</p>
                    <p><strong>Recall:</strong> {metrics.get('recall', 0):.2%}</p>
            """
        else:
            mae = metrics.get('mae', 0)
            r2 = metrics.get('r2', 0)
            
            html += f"""
                    <p><strong>MAE:</strong> <span class="{'good' if mae < 0.5 else 'fair' if mae < 1.0 else 'poor'}">{mae:.3f}</span></p>
                    <p><strong>R² Score:</strong> <span class="{'good' if r2 > 0.7 else 'fair' if r2 > 0.5 else 'poor'}">{r2:.3f}</span></p>
                    <p><strong>RMSE:</strong> {metrics.get('rmse', 0):.3f}</p>
                    <p><strong>Explained Variance:</strong> {metrics.get('explained_variance', 0):.3f}</p>
            """
        
        html += """
                </div>
                
                <h2>📋 Detailed Metrics</h2>
                <div class="plots">
        """
        
        # Add plot images (simplified - in reality you'd reference actual plot files)
        html += """
                    <div class="plot-item">
                        <h3>Performance Visualization</h3>
                        <p><em>Plots saved in evaluation directory</em></p>
                    </div>
                </div>
                
                <h2>📝 Recommendations</h2>
                <div class="metric-card">
        """
        
        if task == 'classification':
            accuracy = metrics.get('accuracy', 0)
            if accuracy > 0.8:
                html += "<p>✅ Excellent performance! Model is ready for production deployment.</p>"
            elif accuracy > 0.7:
                html += "<p>⚠️ Good performance. Consider hyperparameter tuning for minor improvements.</p>"
            elif accuracy > 0.6:
                html += "<p>⚠️ Fair performance. Review feature engineering and consider additional data.</p>"
            else:
                html += "<p>❌ Poor performance. Re-evaluate model architecture and feature selection.</p>"
        else:
            r2 = metrics.get('r2', 0)
            if r2 > 0.8:
                html += "<p>✅ Excellent predictive accuracy! Model captures most variance in data.</p>"
            elif r2 > 0.6:
                html += "<p>⚠️ Good predictive accuracy. Some room for improvement in feature engineering.</p>"
            elif r2 > 0.4:
                html += "<p>⚠️ Fair predictive accuracy. Consider more complex models or additional features.</p>"
            else:
                html += "<p>❌ Poor predictive accuracy. Fundamental re-evaluation of approach needed.</p>"
        
        html += """
                </div>
                
                <h2>🔍 Next Steps</h2>
                <ul>
                    <li>Review detailed plots in the evaluation directory</li>
                    <li>Compare with baseline models</li>
                    <li>Consider feature importance analysis</li>
                    <li>Validate on additional test sets</li>
                    <li>Monitor performance in production</li>
                </ul>
            </div>
        </body>
        </html>
        """
        
        # Save HTML report
        report_file = self.plots_dir / f'evaluation_report_{model_name}_{timestamp}.html'
        with open(report_file, 'w') as f:
            f.write(html)
        
        print(f"   📄 Generated evaluation report: {report_file}")
        
        return html


# Singleton instance for easy access
_evaluator_instance = None

def get_evaluator(output_dir: Optional[str] = None) -> Evaluator:
    """Get or create singleton evaluator instance."""
    global _evaluator_instance
    if _evaluator_instance is None:
        _evaluator_instance = Evaluator(output_dir)
    return _evaluator_instance


if __name__ == "__main__":
    # Demonstration and self-test
    print("🧪 Running Evaluator self-test...")
    
    evaluator = get_evaluator()
    
    # Test classification evaluation
    y_true_cls = np.random.choice([0, 1, 2], size=100)
    y_pred_cls = np.random.choice([0, 1, 2], size=100)
    y_prob_cls = np.random.rand(100, 3)
    
    cls_metrics = evaluator.evaluate_classification(
        y_true_cls, y_pred_cls, y_prob_cls, 
        target_name="Test_Classification",
        class_names=["Class A", "Class B", "Class C"]
    )
    
    # Test regression evaluation
    y_true_reg = np.random.randn(100) * 2 + 1
    y_pred_reg = y_true_reg + np.random.randn(100) * 0.5
    
    reg_metrics = evaluator.evaluate_regression(
        y_true_reg, y_pred_reg,
        target_name="Test_Regression"
    )
    
    print("\n✅ Evaluator self-test completed successfully!")