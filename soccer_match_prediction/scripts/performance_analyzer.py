# scripts/performance_analyzer.py
"""
Performance Analyzer with Calibration Curves and Profit/Loss Tracking
Tracks model accuracy, calibration, and betting performance.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from collections import defaultdict, Counter
import json
import os

class PerformanceAnalyzer:
    def __init__(self, predictor=None, data_dir='data/performance'):
        self.predictor = predictor
        self.data_dir = data_dir
        self.history = []
        self.calibration_bins = defaultdict(list)  # Store actual outcomes by confidence bin
        self.profit_loss_tracker = {
            'total_staked': 0.0,
            'total_returned': 0.0,
            'net_profit': 0.0,
            'roi': 0.0,
            'units_track': []  # Time series of unit changes
        }
        self.market_performance = {
            'home_win': {'total': 0, 'correct': 0, 'profit': 0.0},
            'draw': {'total': 0, 'correct': 0, 'profit': 0.0},
            'away_win': {'total': 0, 'correct': 0, 'profit': 0.0},
            'btts_yes': {'total': 0, 'correct': 0, 'profit': 0.0},
            'btts_no': {'total': 0, 'correct': 0, 'profit': 0.0},
            'over25': {'total': 0, 'correct': 0, 'profit': 0.0},
            'under25': {'total': 0, 'correct': 0, 'profit': 0.0}
        }
        
        # Create data directory if it doesn't exist
        os.makedirs(data_dir, exist_ok=True)
        
        # Load existing performance data
        self._load_history()
        
        print(f"✅ Performance Analyzer initialized with {len(self.history)} historical predictions")
    
    def _load_history(self):
        """Load performance history from file."""
        history_path = os.path.join(self.data_dir, 'performance_history.json')
        if os.path.exists(history_path):
            try:
                with open(history_path, 'r') as f:
                    data = json.load(f)
                    self.history = data.get('history', [])
                    self.calibration_bins = defaultdict(list, {k: v for k, v in data.get('calibration_bins', {}).items()})
                    self.profit_loss_tracker = data.get('profit_loss_tracker', self.profit_loss_tracker)
                    self.market_performance = data.get('market_performance', self.market_performance)
                print(f"   📊 Loaded {len(self.history)} historical predictions")
            except Exception as e:
                print(f"   ⚠️ Error loading performance history: {e}")
    
    def _save_history(self):
        """Save performance history to file."""
        history_path = os.path.join(self.data_dir, 'performance_history.json')
        try:
            data = {
                'history': self.history,
                'calibration_bins': dict(self.calibration_bins),
                'profit_loss_tracker': self.profit_loss_tracker,
                'market_performance': self.market_performance,
                'last_updated': datetime.now().isoformat()
            }
            with open(history_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"⚠️ Error saving performance history: {e}")
    
    def log_prediction(self, prediction, actual_result, odds_used=None, stake=1.0, bet_type='match_winner'):
        """
        Log a prediction and its actual outcome.
        
        Args:
            prediction: Model prediction dictionary
            actual_result: Dictionary with actual score {'home': X, 'away': Y}
            odds_used: Dictionary of odds used for betting
            stake: Stake amount (in units)
            bet_type: Type of bet ('match_winner', 'btts', 'over25', etc.)
        """
        # Determine if prediction was correct
        is_correct = self._check_prediction_correctness(prediction, actual_result, bet_type)
        
        # Calculate profit/loss if odds are provided
        pl_entry = {
            'timestamp': datetime.now().isoformat(),
            'stake': stake,
            'profit_loss': 0.0,
            'odds': odds_used,
            'bet_type': bet_type,
            'correct': is_correct
        }
        
        if odds_used and bet_type in odds_used:
            odds = odds_used[bet_type]
            if is_correct:
                profit = (odds - 1) * stake
                pl_entry['profit_loss'] = profit
                self.profit_loss_tracker['total_returned'] += stake + profit
            else:
                profit = -stake
                pl_entry['profit_loss'] = profit
            
            self.profit_loss_tracker['total_staked'] += stake
            self.profit_loss_tracker['net_profit'] += profit
            
            if self.profit_loss_tracker['total_staked'] > 0:
                self.profit_loss_tracker['roi'] = (
                    self.profit_loss_tracker['net_profit'] / self.profit_loss_tracker['total_staked']
                ) * 100
        
        # Update market performance
        self._update_market_performance(bet_type, is_correct, pl_entry['profit_loss'])
        
        # Get confidence for calibration
        confidence = self._get_prediction_confidence(prediction, bet_type)
        
        # Bin confidence for calibration curve
        confidence_bin = round(confidence / 10) * 10  # Bin by 10% increments
        self.calibration_bins[confidence_bin].append(1 if is_correct else 0)
        
        # Create history entry
        entry = {
            'timestamp': datetime.now().isoformat(),
            'prediction': prediction,
            'actual_result': actual_result,
            'is_correct': is_correct,
            'bet_type': bet_type,
            'confidence': confidence,
            'profit_loss': pl_entry,
            'match': f"{prediction.get('home', 'Unknown')} vs {prediction.get('away', 'Unknown')}"
        }
        
        self.history.append(entry)
        
        # Add to unit track
        self.profit_loss_tracker['units_track'].append({
            'timestamp': datetime.now().isoformat(),
            'profit_loss': pl_entry['profit_loss'],
            'cumulative': self.profit_loss_tracker['net_profit'],
            'match': entry['match']
        })
        
        # Keep only last 1000 entries in units track
        if len(self.profit_loss_tracker['units_track']) > 1000:
            self.profit_loss_tracker['units_track'] = self.profit_loss_tracker['units_track'][-1000:]
        
        # Save periodically
        if len(self.history) % 10 == 0:
            self._save_history()
        
        return entry
    
    def _check_prediction_correctness(self, prediction, actual_result, bet_type):
        """Check if prediction was correct for given bet type."""
        if bet_type == 'match_winner':
            # Determine predicted winner
            pred_winner = max(prediction['win_prob'].items(), key=lambda x: x[1])[0]
            
            # Determine actual winner
            if actual_result['home'] > actual_result['away']:
                actual_winner = 'home'
            elif actual_result['home'] < actual_result['away']:
                actual_winner = 'away'
            else:
                actual_winner = 'draw'
            
            return pred_winner == actual_winner
        
        elif bet_type == 'btts':
            pred_btts = prediction.get('btts', 50) > 50  # >50% means BTTS Yes
            actual_btts = actual_result['home'] > 0 and actual_result['away'] > 0
            return pred_btts == actual_btts
        
        elif bet_type == 'over25':
            pred_over = prediction.get('over25', 50) > 50
            actual_total = actual_result['home'] + actual_result['away']
            actual_over = actual_total > 2.5
            return pred_over == actual_over
        
        return False
    
    def _get_prediction_confidence(self, prediction, bet_type):
        """Extract confidence percentage for a specific bet type."""
        if bet_type == 'match_winner':
            # Maximum win probability
            return max(prediction['win_prob'].values())
        elif bet_type == 'btts':
            return prediction.get('btts', 50)
        elif bet_type == 'over25':
            return prediction.get('over25', 50)
        return 50
    
    def _update_market_performance(self, bet_type, is_correct, profit_loss):
        """Update performance statistics for specific market."""
        market_key = None
        
        if bet_type == 'match_winner':
            # Need to determine which market from prediction
            # This is simplified - you'd need to pass more context
            market_key = 'home_win'  # Simplified
        elif bet_type == 'btts':
            market_key = 'btts_yes'  # Simplified - would need prediction direction
        elif bet_type == 'over25':
            market_key = 'over25'  # Simplified
        
        if market_key and market_key in self.market_performance:
            self.market_performance[market_key]['total'] += 1
            if is_correct:
                self.market_performance[market_key]['correct'] += 1
            self.market_performance[market_key]['profit'] += profit_loss
    
    def get_calibration_curve(self):
        """Generate calibration curve data showing predicted vs actual accuracy."""
        calibration_points = []
        
        for confidence_bin, outcomes in sorted(self.calibration_bins.items()):
            if len(outcomes) >= 5:  # Need minimum samples
                predicted_accuracy = confidence_bin
                actual_accuracy = (sum(outcomes) / len(outcomes)) * 100
                calibration_points.append({
                    'confidence_bin': confidence_bin,
                    'predicted_accuracy': predicted_accuracy,
                    'actual_accuracy': round(actual_accuracy, 1),
                    'samples': len(outcomes),
                    'calibration_error': round(abs(predicted_accuracy - actual_accuracy), 1)
                })
        
        # Calculate overall calibration metrics
        if calibration_points:
            total_samples = sum(p['samples'] for p in calibration_points)
            weighted_error = sum(p['calibration_error'] * p['samples'] for p in calibration_points) / total_samples
            
            calibration_summary = {
                'points': calibration_points,
                'total_samples': total_samples,
                'weighted_calibration_error': round(weighted_error, 2),
                'is_overconfident': any(p['actual_accuracy'] < p['predicted_accuracy'] - 10 for p in calibration_points),
                'is_underconfident': any(p['actual_accuracy'] > p['predicted_accuracy'] + 10 for p in calibration_points)
            }
        else:
            calibration_summary = {'points': [], 'message': 'Insufficient data for calibration'}
        
        return calibration_summary
    
    def get_profit_loss_report(self, days=30):
        """Generate comprehensive P/L report."""
        cutoff_date = datetime.now() - timedelta(days=days)
        
        # Filter recent history
        recent_history = [
            h for h in self.history 
            if datetime.fromisoformat(h['timestamp'].replace('Z', '+00:00')) > cutoff_date
        ]
        
        recent_units = [
            u for u in self.profit_loss_tracker['units_track']
            if datetime.fromisoformat(u['timestamp'].replace('Z', '+00:00')) > cutoff_date
        ]
        
        # Calculate metrics
        total_bets = len(recent_history)
        winning_bets = sum(1 for h in recent_history if h.get('profit_loss', {}).get('profit_loss', 0) > 0)
        losing_bets = sum(1 for h in recent_history if h.get('profit_loss', {}).get('profit_loss', 0) < 0)
        
        if total_bets > 0:
            win_rate = (winning_bets / total_bets) * 100
        else:
            win_rate = 0
        
        # Calculate P/L from recent units
        recent_pl = sum(u['profit_loss'] for u in recent_units) if recent_units else 0
        recent_staked = sum(u.get('stake', 0) for u in recent_units) if recent_units else 0
        
        if recent_staked > 0:
            recent_roi = (recent_pl / recent_staked) * 100
        else:
            recent_roi = 0
        
        # Best/worst performing markets
        market_perf = self.get_market_performance_analysis()
        
        return {
            'period_days': days,
            'total_bets': total_bets,
            'winning_bets': winning_bets,
            'losing_bets': losing_bets,
            'win_rate': round(win_rate, 1),
            'recent_profit_loss': round(recent_pl, 2),
            'recent_roi': round(recent_roi, 2),
            'overall_profit_loss': round(self.profit_loss_tracker['net_profit'], 2),
            'overall_roi': round(self.profit_loss_tracker['roi'], 2),
            'total_staked': round(self.profit_loss_tracker['total_staked'], 2),
            'total_returned': round(self.profit_loss_tracker['total_returned'], 2),
            'market_performance': market_perf,
            'units_timeseries': recent_units[-50:],  # Last 50 units
            'performance_trend': self._calculate_performance_trend(recent_units)
        }
    
    def get_market_performance_analysis(self):
        """Analyze performance by market type."""
        analysis = {}
        
        for market, stats in self.market_performance.items():
            if stats['total'] > 0:
                accuracy = (stats['correct'] / stats['total']) * 100
                profit_per_bet = stats['profit'] / stats['total'] if stats['total'] > 0 else 0
                
                analysis[market] = {
                    'total_bets': stats['total'],
                    'correct_bets': stats['correct'],
                    'accuracy': round(accuracy, 1),
                    'total_profit': round(stats['profit'], 2),
                    'profit_per_bet': round(profit_per_bet, 2),
                    'expected_value': self._calculate_market_ev(stats)
                }
        
        # Sort by profitability
        sorted_markets = sorted(
            analysis.items(),
            key=lambda x: x[1]['profit_per_bet'],
            reverse=True
        )
        
        best_market = sorted_markets[0] if sorted_markets else None
        worst_market = sorted_markets[-1] if sorted_markets else None
        
        return {
            'by_market': dict(sorted_markets),
            'best_performing': best_market,
            'worst_performing': worst_market,
            'recommendation': self._generate_market_recommendation(sorted_markets)
        }
    
    def _calculate_market_ev(self, stats):
        """Calculate expected value for a market."""
        if stats['total'] == 0:
            return 0
        
        win_prob = stats['correct'] / stats['total']
        avg_profit_on_win = stats['profit'] / stats['correct'] if stats['correct'] > 0 else 0
        avg_loss_on_loss = -stats['profit'] / (stats['total'] - stats['correct']) if stats['total'] > stats['correct'] else 0
        
        ev = (win_prob * avg_profit_on_win) + ((1 - win_prob) * avg_loss_on_loss)
        return round(ev, 3)
    
    def _calculate_performance_trend(self, units_data):
        """Calculate performance trends (improving/declining)."""
        if len(units_data) < 10:
            return {'trend': 'insufficient_data', 'slope': 0}
        
        # Get cumulative profits over time
        profits = [u['cumulative'] for u in units_data]
        
        # Simple linear regression to determine trend
        x = np.arange(len(profits))
        slope, intercept = np.polyfit(x, profits, 1)
        
        if slope > 0.1:
            trend = 'improving'
        elif slope < -0.1:
            trend = 'declining'
        else:
            trend = 'stable'
        
        return {
            'trend': trend,
            'slope': round(slope, 3),
            'volatility': round(np.std(profits) if len(profits) > 1 else 0, 2)
        }
    
    def _generate_market_recommendation(self, sorted_markets):
        """Generate betting recommendations based on market performance."""
        if not sorted_markets:
            return "No data for recommendations"
        
        best_market, best_stats = sorted_markets[0]
        worst_market, worst_stats = sorted_markets[-1]
        
        recommendations = []
        
        if best_stats['profit_per_bet'] > 0.1:
            recommendations.append(f"✅ Focus on {best_market} (profit per bet: {best_stats['profit_per_bet']} units)")
        
        if worst_stats['profit_per_bet'] < -0.1:
            recommendations.append(f"⚠️ Avoid {worst_market} (losing {abs(worst_stats['profit_per_bet'])} units per bet)")
        
        if best_stats['accuracy'] > 60:
            recommendations.append(f"🎯 {best_market} has high accuracy ({best_stats['accuracy']}%) - consider increasing stakes")
        
        return "; ".join(recommendations) if recommendations else "No clear recommendations - maintain current strategy"
    
    def get_comprehensive_report(self):
        """Generate comprehensive performance report."""
        calibration = self.get_calibration_curve()
        pl_report = self.get_profit_loss_report(days=30)
        market_analysis = self.get_market_performance_analysis()
        
        # Calculate overall metrics
        total_predictions = len(self.history)
        if total_predictions > 0:
            correct_predictions = sum(1 for h in self.history if h['is_correct'])
            overall_accuracy = (correct_predictions / total_predictions) * 100
        else:
            overall_accuracy = 0
        
        return {
            'report_generated': datetime.now().isoformat(),
            'overall_accuracy': round(overall_accuracy, 1),
            'total_predictions': total_predictions,
            'calibration_analysis': calibration,
            'profit_loss_analysis': pl_report,
            'market_analysis': market_analysis,
            'model_health': self._assess_model_health(calibration, pl_report),
            'recommendations': self._generate_model_recommendations(calibration, pl_report, market_analysis)
        }
    
    def _assess_model_health(self, calibration, pl_report):
        """Assess overall model health."""
        health_indicators = []
        
        # Check calibration
        if calibration.get('weighted_calibration_error', 100) < 5:
            health_indicators.append('well_calibrated')
        elif calibration.get('is_overconfident'):
            health_indicators.append('overconfident')
        elif calibration.get('is_underconfident'):
            health_indicators.append('underconfident')
        
        # Check profitability
        if pl_report.get('overall_roi', 0) > 5:
            health_indicators.append('profitable')
        elif pl_report.get('overall_roi', 0) < -5:
            health_indicators.append('unprofitable')
        
        # Check consistency
        trend = pl_report.get('performance_trend', {}).get('trend')
        if trend == 'improving':
            health_indicators.append('improving')
        elif trend == 'declining':
            health_indicators.append('declining')
        
        return {
            'indicators': health_indicators,
            'score': len([i for i in health_indicators if i in ['well_calibrated', 'profitable', 'improving']]),
            'requires_attention': 'overconfident' in health_indicators or 'unprofitable' in health_indicators
        }
    
    def _generate_model_recommendations(self, calibration, pl_report, market_analysis):
        """Generate actionable recommendations for model improvement."""
        recommendations = []
        
        # Calibration recommendations
        if calibration.get('is_overconfident'):
            recommendations.append("Model is overconfident. Consider lowering confidence estimates or increasing prediction thresholds.")
        
        if calibration.get('is_underconfident'):
            recommendations.append("Model is underconfident. High-probability predictions may be too conservative.")
        
        # Profitability recommendations
        if pl_report.get('overall_roi', 0) < 0:
            recommendations.append(f"Current strategy is losing money (ROI: {pl_report.get('overall_roi', 0)}%). Review betting strategy and odds selection.")
        
        # Market-specific recommendations
        best_market = market_analysis.get('best_performing')
        worst_market = market_analysis.get('worst_performing')
        
        if best_market:
            recommendations.append(f"Focus on {best_market[0]} market which shows positive EV of {best_market[1].get('expected_value', 0)}.")
        
        if worst_market and worst_market[1].get('profit_per_bet', 0) < -0.05:
            recommendations.append(f"Avoid {worst_market[0]} market which is losing {abs(worst_market[1].get('profit_per_bet', 0))} units per bet.")
        
        return recommendations
    
    def export_report(self, format='json'):
        """Export comprehensive report in specified format."""
        report = self.get_comprehensive_report()
        
        if format.lower() == 'json':
            return json.dumps(report, indent=2)
        elif format.lower() == 'csv':
            # Simplified CSV export - would need more implementation
            return "CSV export not fully implemented"
        else:
            return report
    
    def __repr__(self):
        return f"PerformanceAnalyzer(history={len(self.history)}, net_profit={self.profit_loss_tracker['net_profit']:.2f}, ROI={self.profit_loss_tracker['roi']:.1f}%)"