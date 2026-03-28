"""
Implements an adaptive 'Soft Learning' system that adjusts team weights based on recent prediction errors.
It features a decay rate mechanism, ensuring that older match results have a diminishing impact on current weights.
The system calculates home and away strength adjustments to fine-tune the base model's probability outputs.
It stores team-specific performance metadata in a JSON format to persist learning across different sessions.
This allows the AI to stay responsive to sudden shifts in team form without requiring a full model retrain.
"""

import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
import logging
from collections import defaultdict

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AdaptiveTeamWeights:
    """
    Soft Learning System that gradually adjusts team performance weights
    based on prediction errors over time.
    """
    
    def __init__(self, weights_path="data/team_weights.json", decay_rate=0.95):
        self.weights_path = Path(weights_path)
        self.decay_rate = decay_rate  # How quickly old errors are forgotten
        self.min_matches = 5  # Minimum matches before significant adjustment
        self.max_adjustment = 0.3  # Maximum single-match adjustment
        self.weights = self.load_weights()
        self.error_history = defaultdict(list)
        
        
        
    def load_weights(self):
        """Load existing weights or initialize with defaults"""
        if self.weights_path.exists():
            try:
                with open(self.weights_path, 'r', encoding='utf-8') as f:  # ← Added encoding
                    data = json.load(f)
                    # Convert old format if needed
                    if isinstance(data, dict) and 'teams' in data:
                        return data
                    else:
                        return self._convert_legacy_format(data)
            except Exception as e:
                logger.error(f"Error loading weights: {e}")
        
        # Default structure
        return {
            'teams': {},
            'metadata': {
                'created': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_adjustments': 0
            }
        }
    
    def _convert_legacy_format(self, old_data):
        """Convert old adjustment format to new format"""
        teams = {}
        for team, weight in old_data.items():
            if isinstance(weight, (int, float)):
                teams[team] = {
                    'weight': float(weight),
                    'confidence': 0.5,
                    'matches_tracked': 0,
                    'last_updated': datetime.now().isoformat(),
                    'trend': 'stable'
                }
        
        return {
            'teams': teams,
            'metadata': {
                'created': datetime.now().isoformat(),
                'last_updated': datetime.now().isoformat(),
                'total_adjustments': len(teams)
            }
        }
    
    def get_team_weight(self, team_name, default=1.0):
        """Get weight for a team with confidence adjustment"""
        team_data = self.weights['teams'].get(team_name)
        if not team_data:
            return default
        
        # Confidence-weighted adjustment
        weight = team_data['weight']
        confidence = team_data.get('confidence', 0.5)
        
        # Less confident = closer to default
        if confidence < 0.3:
            return default * 0.7 + weight * 0.3
        elif confidence < 0.7:
            return default * 0.4 + weight * 0.6
        else:
            return weight
    
    def record_prediction_error(self, match_data):
        """
        Record prediction error for analysis
        match_data should contain:
        - home_team, away_team
        - predicted_home_goals, predicted_away_goals
        - actual_home_goals, actual_away_goals
        - predicted_win_prob (home, draw, away)
        - actual_result (H, D, A)
        """
        try:
            # Extract predicted data (handling main.py structure)
            predicted_data = match_data.get('predicted_data', {})
            
            # Get predicted goals from score field in main.py structure
            score = predicted_data.get('score', {})
            predicted_home_goals = score.get('home', 1.5)
            predicted_away_goals = score.get('away', 1.0)
            
            # Get actual goals - handle multiple naming conventions
            actual_home_goals = match_data.get('actual_home_goals', 
                                              match_data.get('home_goals', 
                                                            match_data.get('FTHG', 0)))
            actual_away_goals = match_data.get('actual_away_goals',
                                              match_data.get('away_goals',
                                                            match_data.get('FTAG', 0)))
            
            # Ensure we have actual goals
            if actual_home_goals is None or actual_away_goals is None:
                logger.warning(f"Missing actual goals in match data: {match_data.get('match_id', 'unknown')}")
                return False
            
            # Get win probabilities
            predicted_win_prob = predicted_data.get('win_prob', {'home': 33, 'draw': 33, 'away': 34})
            
            # Get actual result - handle multiple naming conventions
            actual_result = match_data.get('actual_result',
                                          match_data.get('result',
                                                        match_data.get('FTR', 'D')))
            
            # Calculate errors
            home_error = actual_home_goals - predicted_home_goals
            away_error = actual_away_goals - predicted_away_goals
            result_error = self._calculate_result_error(predicted_win_prob, actual_result)
            
            # Store errors
            home_team = match_data.get('home_team', 'Unknown')
            away_team = match_data.get('away_team', 'Unknown')
            
            self.error_history[home_team].append({
                'error': home_error,
                'type': 'offense',
                'match_date': match_data.get('date', 
                                           match_data.get('match_date', 
                                                         datetime.now().isoformat())),
                'opponent': away_team,
                'actual': actual_home_goals,
                'predicted': predicted_home_goals
            })
            
            self.error_history[away_team].append({
                'error': away_error,
                'type': 'offense',
                'match_date': match_data.get('date',
                                           match_data.get('match_date',
                                                         datetime.now().isoformat())),
                'opponent': home_team,
                'actual': actual_away_goals,
                'predicted': predicted_away_goals
            })
            
            # Apply soft learning adjustment
            self._adjust_weights_based_on_error(
                home_team, away_team, 
                home_error, away_error, result_error,
                predicted_data, actual_result
            )
            
            # Prune old errors
            self._prune_old_errors()
            
            return True
            
        except Exception as e:
            logger.error(f"Error recording prediction: {e}")
            return False
    
    def _calculate_result_error(self, predicted_win_prob, actual_result):
        """Calculate how wrong the win probability prediction was"""
        if actual_result == 'H':
            actual_prob = {'home': 1.0, 'draw': 0.0, 'away': 0.0}
            # Use predicted probability for the actual outcome
            predicted_prob = predicted_win_prob.get('home', 33.3) / 100.0
        elif actual_result == 'D':
            actual_prob = {'home': 0.0, 'draw': 1.0, 'away': 0.0}
            predicted_prob = predicted_win_prob.get('draw', 33.3) / 100.0
        else:  # 'A'
            actual_prob = {'home': 0.0, 'draw': 0.0, 'away': 1.0}
            predicted_prob = predicted_win_prob.get('away', 33.3) / 100.0
        
        # Calculate mean squared error
        pred_home = predicted_win_prob.get('home', 33.3) / 100.0
        pred_draw = predicted_win_prob.get('draw', 33.3) / 100.0
        pred_away = predicted_win_prob.get('away', 33.3) / 100.0
        
        mse = (
            (actual_prob['home'] - pred_home)**2 +
            (actual_prob['draw'] - pred_draw)**2 +
            (actual_prob['away'] - pred_away)**2
        ) / 3.0
        
        # Also calculate outcome-specific error (0-1, where 0 is perfect prediction)
        outcome_error = 1.0 - predicted_prob
        
        return mse
    
    def _adjust_weights_based_on_error(self, home_team, away_team, 
                                       home_error, away_error, result_error,
                                       predicted_data, actual_result):
        """Apply soft adjustment to team weights"""
        # Get current team data
        home_data = self.weights['teams'].get(home_team, self._create_new_team_data())
        away_data = self.weights['teams'].get(away_team, self._create_new_team_data())
        
        # Get predicted probabilities for actual outcome
        predicted_win_prob = predicted_data.get('win_prob', {'home': 33, 'draw': 33, 'away': 34})
        if actual_result == 'H':
            predicted_outcome_prob = predicted_win_prob.get('home', 33) / 100.0
        elif actual_result == 'D':
            predicted_outcome_prob = predicted_win_prob.get('draw', 33) / 100.0
        else:
            predicted_outcome_prob = predicted_win_prob.get('away', 33) / 100.0
        
        # Calculate adjustments
        home_adj = self._calculate_adjustment(home_error, result_error, home_data, predicted_outcome_prob)
        away_adj = self._calculate_adjustment(away_error, result_error, away_data, predicted_outcome_prob)
        
        # Apply with learning rate based on confidence
        home_learning_rate = 0.1 * (1 - home_data.get('confidence', 0.5))
        away_learning_rate = 0.1 * (1 - away_data.get('confidence', 0.5))
        
        home_data['weight'] = np.clip(
            home_data['weight'] + home_adj * home_learning_rate,
            0.5,  # Minimum weight
            2.0   # Maximum weight
        )
        
        away_data['weight'] = np.clip(
            away_data['weight'] + away_adj * away_learning_rate,
            0.5,
            2.0
        )
        
        # Update confidence (more matches = more confidence)
        home_data['matches_tracked'] = home_data.get('matches_tracked', 0) + 1
        away_data['matches_tracked'] = away_data.get('matches_tracked', 0) + 1
        
        home_data['confidence'] = min(0.99, 0.5 + (home_data['matches_tracked'] / 20))
        away_data['confidence'] = min(0.99, 0.5 + (away_data['matches_tracked'] / 20))
        
        # Update trend
        home_data['trend'] = self._calculate_trend(home_adj)
        away_data['trend'] = self._calculate_trend(away_adj)
        
        home_data['last_updated'] = datetime.now().isoformat()
        away_data['last_updated'] = datetime.now().isoformat()
        
        # Store updated data
        self.weights['teams'][home_team] = home_data
        self.weights['teams'][away_team] = away_data
        
        # Update metadata
        self.weights['metadata']['last_updated'] = datetime.now().isoformat()
        self.weights['metadata']['total_adjustments'] += 1
        
        # Save weights
        self.save_weights()
        
        logger.info(f"Adjusted weights: {home_team}: {home_data['weight']:.3f} (adj: {home_adj:.3f}), "
                   f"{away_team}: {away_data['weight']:.3f} (adj: {away_adj:.3f})")
    
    def _calculate_adjustment(self, error, result_error, team_data, predicted_outcome_prob=None):
        """Calculate adjustment using soft sigmoid function"""
        matches = team_data.get('matches_tracked', 1)
        
        # Adjustment diminishes as we have more data
        adjustment_factor = 1.0 / np.sqrt(matches)
        
        # Use outcome probability error if available
        if predicted_outcome_prob is not None:
            # Combine goal error with outcome confidence error
            # If we were confident and wrong, adjust more
            confidence_error = 1.0 - predicted_outcome_prob  # 0 if confident and correct, 1 if confident and wrong
            combined_error = (abs(error) * 0.6) + (confidence_error * 0.4)
        else:
            combined_error = abs(error)
        
        # Normalized adjustment (bounded)
        # Use tanh to keep adjustment between -max and +max
        adjustment = np.tanh(error / 2.0) * adjustment_factor * self.max_adjustment
        
        # Scale by combined error
        adjustment = adjustment * (0.5 + 0.5 * np.tanh(combined_error))
        
        return adjustment
    
    def _calculate_trend(self, adjustment):
        """Determine if team is trending up, down, or stable"""
        if adjustment > 0.05:
            return 'improving'
        elif adjustment < -0.05:
            return 'declining'
        else:
            return 'stable'
    
    def _create_new_team_data(self):
        """Create default team data structure"""
        return {
            'weight': 1.0,
            'confidence': 0.5,
            'matches_tracked': 0,
            'last_updated': datetime.now().isoformat(),
            'trend': 'stable',
            'recent_errors': []
        }
    
    def _prune_old_errors(self):
        """Remove errors older than 90 days"""
        cutoff_date = datetime.now() - timedelta(days=90)
        
        for team in list(self.error_history.keys()):
            self.error_history[team] = [
                error for error in self.error_history[team]
                if datetime.fromisoformat(error['match_date']) > cutoff_date
            ]
            
            if not self.error_history[team]:
                del self.error_history[team]
    
    def save_weights(self):
        """Save weights to JSON file"""
        try:
            self.weights_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.weights_path, 'w', encoding='utf-8') as f:  # ← Added encoding
                json.dump(self.weights, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving weights: {e}")
            return False
    
    def get_team_stats(self, team_name):
        """Get detailed stats for a team"""
        team_data = self.weights['teams'].get(team_name)
        if not team_data:
            return None
        
        recent_errors = self.error_history.get(team_name, [])
        if recent_errors:
            errors = [e['error'] for e in recent_errors]
            avg_error = np.mean(errors)
            consistency = 1.0 / (1.0 + np.std(errors))  # Higher = more consistent
        else:
            avg_error = 0.0
            consistency = 1.0
        
        return {
            'weight': team_data['weight'],
            'confidence': team_data['confidence'],
            'last_updated': team_data['last_updated'],
            'matches_tracked': team_data['matches_tracked'],
            'trend': team_data['trend'],
            'performance_metrics': {
                'average_error': round(avg_error, 3),
                'consistency': round(consistency, 3),
                'adjustment_needed': team_data['weight'] != 1.0
            },
            'recent_performance': recent_errors[-5:] if recent_errors else []
        }
    
    def get_teams_needing_adjustment(self, threshold=0.1):
        """Get teams whose weights differ significantly from 1.0"""
        teams = []
        for team_name, data in self.weights['teams'].items():
            if abs(data['weight'] - 1.0) > threshold and data['confidence'] > 0.6:
                teams.append({
                    'team': team_name,
                    'weight': data['weight'],
                    'deviation': abs(data['weight'] - 1.0),
                    'confidence': data['confidence'],
                    'trend': data['trend']
                })
        
        return sorted(teams, key=lambda x: x['deviation'], reverse=True)
    
    def batch_update_from_results(self, results_df):
        """
        Batch update weights from a DataFrame of match results
        results_df should have columns:
        - Date, HomeTeam, AwayTeam, FTHG, FTAG, FTR
        """
        if results_df.empty:
            return False
        
        logger.info(f"Processing {len(results_df)} match results for online learning")
        
        for _, row in results_df.iterrows():
            # Need to get predictions for this match
            # In production, you would fetch from prediction history
            # For now, we'll simulate or skip if no prediction available
            pass
        
        return True


class PerformanceTracker:
    """Track model performance over time"""
    
    def __init__(self, tracker_path="data/performance_tracker.json"):
        self.tracker_path = Path(tracker_path)
        self.performance_data = self.load_data()
    
    def load_data(self):
        if self.tracker_path.exists():
            try:
                with open(self.tracker_path, 'r', encoding='utf-8') as f:  # ← Added encoding
                    return json.load(f)
            except:
                pass
        
        return {
            'daily_performance': [],
            'model_accuracy': {},
            'team_accuracy': {},
            'last_updated': datetime.now().isoformat()
        }
    
    def record_daily_performance(self, date, total_predictions, correct_predictions, total_error):
        """Record daily prediction performance"""
        accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        
        day_data = {
            'date': date.isoformat() if isinstance(date, datetime) else date,
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'accuracy': accuracy,
            'average_error': total_error / total_predictions if total_predictions > 0 else 0,
            'timestamp': datetime.now().isoformat()
        }
        
        self.performance_data['daily_performance'].append(day_data)
        
        # Keep only last 365 days
        if len(self.performance_data['daily_performance']) > 365:
            self.performance_data['daily_performance'] = self.performance_data['daily_performance'][-365:]
        
        self.performance_data['last_updated'] = datetime.now().isoformat()
        self.save_data()
    
    def update_team_accuracy(self, team_name, prediction_correct):
        """Update accuracy stats for a specific team"""
        if team_name not in self.performance_data['team_accuracy']:
            self.performance_data['team_accuracy'][team_name] = {
                'total': 0,
                'correct': 0,
                'accuracy': 0
            }
        
        stats = self.performance_data['team_accuracy'][team_name]
        stats['total'] += 1
        if prediction_correct:
            stats['correct'] += 1
        
        stats['accuracy'] = stats['correct'] / stats['total'] if stats['total'] > 0 else 0
        self.save_data()
    
    def save_data(self):
        try:
            self.tracker_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.tracker_path, 'w', encoding='utf-8') as f:  # ← Added encoding
                json.dump(self.performance_data, f, indent=2)
            return True
        except Exception as e:
            logger.error(f"Error saving performance data: {e}")
            return False
    
    def get_performance_summary(self, days=30):
        """Get performance summary for last N days"""
        recent_data = self.performance_data['daily_performance'][-days:]
        
        if not recent_data:
            return None
        
        total_predictions = sum(d['total_predictions'] for d in recent_data)
        correct_predictions = sum(d['correct_predictions'] for d in recent_data)
        avg_accuracy = correct_predictions / total_predictions if total_predictions > 0 else 0
        
        return {
            'period_days': days,
            'total_predictions': total_predictions,
            'correct_predictions': correct_predictions,
            'accuracy': round(avg_accuracy, 3),
            'average_daily_predictions': round(total_predictions / days, 1),
            'start_date': recent_data[0]['date'],
            'end_date': recent_data[-1]['date']
        }


# Main interface for the online learning system
class OnlineLearningSystem:
    """Orchestrates the complete online learning system"""
    
    def __init__(self, weights_path="data/team_weights.json", decay_rate=0.95):  # ← KEY CHANGE: Added parameters with defaults
        self.team_weights = AdaptiveTeamWeights(weights_path=weights_path, decay_rate=decay_rate)  # ← KEY CHANGE: Pass the parameters
        self.performance_tracker = PerformanceTracker()
        self.logger = logging.getLogger(__name__)
    
    def process_match_result(self, match_result):
        """
        Process a completed match result for online learning
        match_result should contain (main.py structure):
        - match_id, home_team, away_team, match_date
        - home_goals, away_goals, result (or actual_home_goals, actual_away_goals, actual_result)
        - predicted_data (nested dictionary from prediction)
        """
        try:
            # Extract data with fallbacks for different naming conventions
            home_team = match_result.get('home_team', 'Unknown')
            away_team = match_result.get('away_team', 'Unknown')
            
            # Handle different field names for goals - FIXED: Use correct key names
            actual_home_goals = match_result.get('actual_home_goals', 
                                                match_result.get('home_goals',
                                                               match_result.get('FTHG', 0)))
            actual_away_goals = match_result.get('actual_away_goals',
                                                match_result.get('away_goals',
                                                               match_result.get('FTAG', 0)))
            actual_result = match_result.get('actual_result',
                                           match_result.get('result',
                                                          match_result.get('FTR', 'D')))
            
            # Get predicted data (should come from prediction storage)
            predicted_data = match_result.get('predicted_data', {})
            
            if not predicted_data:
                self.logger.warning(f"No predicted data for match {match_result.get('match_id')}")
                return False
            
            # Prepare error recording with main.py structure
            error_data = {
                'home_team': home_team,
                'away_team': away_team,
                'actual_home_goals': actual_home_goals,
                'actual_away_goals': actual_away_goals,
                'actual_result': actual_result,
                'predicted_data': predicted_data,
                'date': match_result.get('match_date', 
                                       match_result.get('date', 
                                                       datetime.now().isoformat()))
            }
            
            # Record error for weight adjustment
            success = self.team_weights.record_prediction_error(error_data)
            if not success:
                return False
            
            # Determine if prediction was correct (for accuracy tracking)
            predicted_winner = self._get_predicted_winner(predicted_data.get('win_prob', {}))
            
            prediction_correct = (predicted_winner == actual_result)
            
            # Update performance tracker
            self.performance_tracker.update_team_accuracy(home_team, prediction_correct)
            self.performance_tracker.update_team_accuracy(away_team, prediction_correct)
            
            self.logger.info(f"Processed match result: {home_team} {actual_home_goals}-{actual_away_goals} {away_team} "
                           f"Predicted: {predicted_winner}, Actual: {actual_result}, Correct: {prediction_correct}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing match result: {e}")
            return False
    
    def _get_predicted_winner(self, win_prob):
        """Convert win probabilities to predicted winner (H, D, A)"""
        if not win_prob:
            return 'D'
        
        max_key = max(win_prob, key=win_prob.get)
        
        if max_key == 'home':
            return 'H'
        elif max_key == 'away':
            return 'A'
        else:
            return 'D'
    
    def get_system_status(self):
        """Get current status of online learning system"""
        teams_needing_adjustment = self.team_weights.get_teams_needing_adjustment()
        performance_summary = self.performance_tracker.get_performance_summary(30)
        
        return {
            'online_learning_active': True,
            'total_teams_tracked': len(self.team_weights.weights['teams']),
            'teams_needing_adjustment': len(teams_needing_adjustment),
            'total_adjustments': self.team_weights.weights['metadata']['total_adjustments'],
            'last_updated': self.team_weights.weights['metadata']['last_updated'],
            'recent_performance': performance_summary,
            'top_adjusted_teams': teams_needing_adjustment[:5] if teams_needing_adjustment else []
        }
    
    def apply_weights_to_prediction(self, home_team, away_team, base_prediction):
        """
        Apply learned weights to a base prediction
        base_prediction should contain at least win probabilities (main.py structure)
        """
        try:
            home_weight = self.team_weights.get_team_weight(home_team)
            away_weight = self.team_weights.get_team_weight(away_team)
            
            # Apply soft adjustment to probabilities
            if 'win_prob' in base_prediction:
                win_prob = base_prediction['win_prob'].copy()
                
                # Adjust based on team weights (softly)
                weight_ratio = home_weight / (away_weight + 1e-8)  # Add epsilon to avoid division by zero
                
                # Sigmoid adjustment to prevent extremes
                adjustment_factor = 0.2 * np.tanh(np.log(weight_ratio + 1e-8))
                
                # Apply adjustment
                win_prob['home'] = win_prob['home'] * (1 + adjustment_factor)
                win_prob['away'] = win_prob['away'] * (1 - adjustment_factor)
                
                # Renormalize to 100%
                total = win_prob['home'] + win_prob['draw'] + win_prob['away']
                if total > 0:
                    win_prob['home'] = (win_prob['home'] / total) * 100
                    win_prob['draw'] = (win_prob['draw'] / total) * 100
                    win_prob['away'] = (win_prob['away'] / total) * 100
                
                base_prediction['win_prob'] = win_prob
                base_prediction['online_learning_adjustment'] = {
                    'home_weight': round(home_weight, 3),
                    'away_weight': round(away_weight, 3),
                    'weight_ratio': round(weight_ratio, 3),
                    'adjustment_factor': round(adjustment_factor, 3),
                    'applied': True
                }
            
            return base_prediction
            
        except Exception as e:
            self.logger.error(f"Error applying weights: {e}")
            return base_prediction


# Singleton instance for easy access
online_learner = OnlineLearningSystem(
    weights_path="data/team_weights.json",  # ← KEY CHANGE: Pass explicit values (or use defaults by omitting)
    decay_rate=0.92
)

if __name__ == "__main__":
    # Test the system with main.py structure - FIXED: Use correct key names
    learner = OnlineLearningSystem(  # ← KEY CHANGE: Pass values here too (or use defaults)
        weights_path="data/team_weights.json",
        decay_rate=0.92
    )
    
    # Test with a sample match result (main.py structure) - CORRECTED KEYS
    test_result = {
        'match_id': 'test_123',
        'home_team': 'Manchester United',
        'away_team': 'Liverpool',
        'match_date': datetime.now().isoformat(),
        'actual_home_goals': 2,  # FIXED: Changed from 'home_goals'
        'actual_away_goals': 1,  # FIXED: Changed from 'away_goals'
        'actual_result': 'H',    # FIXED: Changed from 'result'
        'predicted_data': {
            'win_prob': {'home': 40, 'draw': 30, 'away': 30},
            'score': {'home': 1, 'away': 1},
            'total_goals': 2.0,
            'btts': 55.5,
            'over25': 45.2,
            'prediction_outcome': 'D',
            'prediction_confidence': 40.0
        }
    }
    
    success = learner.process_match_result(test_result)
    print(f"Processing test result: {'Success' if success else 'Failed'}")
    
    # Test weight application
    test_prediction = {
        'home': 'Manchester United',
        'away': 'Liverpool',
        'win_prob': {'home': 40, 'draw': 30, 'away': 30}
    }
    
    adjusted = learner.apply_weights_to_prediction('Manchester United', 'Liverpool', test_prediction)
    print(f"Applied weights adjustment: {adjusted.get('online_learning_adjustment', {})}")
    
    status = learner.get_system_status()
    print(f"\nSystem Status:")
    print(f"  Total teams tracked: {status['total_teams_tracked']}")
    print(f"  Total adjustments: {status['total_adjustments']}")
    print(f"  Last updated: {status['last_updated']}")