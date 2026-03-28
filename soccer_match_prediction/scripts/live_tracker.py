# scripts/live_tracker.py
"""
Live Match Tracker with Advanced In-Play Adjustments
Adjusts predictions based on live match events with time-weighted scoring.
"""

import time
from datetime import datetime, timedelta
import numpy as np
from collections import deque

class LiveMatchTracker:
    def __init__(self, predictor=None, socketio=None):
        self.predictor = predictor
        self.socketio = socketio
        self.live_matches = {}
        self.event_weights = {
            'goal': 1.0,
            'penalty_awarded': 0.8,
            'red_card': 0.7,
            'yellow_card': 0.1,
            'shot_on_target': 0.05,
            'corner': 0.02,
            'possession_swing': 0.03,
            'substitution': 0.01,
            'injury': 0.02
        }
        print(f"✅ Live Match Tracker initialized. WebSocket: {'Enabled' if socketio else 'Disabled'}")
    
    def start_tracking(self, match_id, home, away):
        """Start tracking a live match."""
        try:
            initial_prediction = self.predictor.predict_for_web(home, away)
        except:
            initial_prediction = {
                'win_prob': {'home': 33.3, 'draw': 33.3, 'away': 33.3},
                'score': {'home': 0, 'away': 0},
                'confidence': {'label': 'MEDIUM', 'color': 'text-yellow-400'}
            }
        
        self.live_matches[match_id] = {
            'home': home,
            'away': away,
            'start_time': datetime.now(),
            'current_score': {'home': 0, 'away': 0},
            'minute': 0,
            'possession': {'home': 50, 'away': 50},
            'shots_on_target': {'home': 0, 'away': 0},
            'corners': {'home': 0, 'away': 0},
            'cards': {'home': {'yellow': 0, 'red': 0}, 'away': {'yellow': 0, 'red': 0}},
            'initial_prediction': initial_prediction,
            'current_prediction': initial_prediction.copy(),
            'events': deque(maxlen=50),  # Keep last 50 events
            'momentum_history': [],
            'adjustments': []
        }
        
        # Emit via WebSocket if available
        if self.socketio:
            self.socketio.emit('match_started', {
                'match_id': match_id,
                'home': home,
                'away': away,
                'prediction': initial_prediction
            }, room=f'match_{match_id}')
        
        return self.live_matches[match_id]
    
    def update_match_state(self, match_id, score, minute, possession=None, events=None):
        """Update match state and recalculate probabilities with time-decay."""
        if match_id not in self.live_matches:
            return None
        
        match = self.live_matches[match_id]
        old_score = match['current_score']
        match['current_score'] = score
        match['minute'] = minute
        
        if possession:
            match['possession'] = possession
        
        # Process events
        if events:
            for event in events:
                self._process_event(match, event)
        
        # Calculate momentum
        momentum = self._calculate_momentum(match)
        match['momentum_history'].append({
            'minute': minute,
            'momentum': momentum,
            'score_difference': score['home'] - score['away']
        })
        
        # Adjust prediction with time-decay weighting
        adjusted_prediction = self._adjust_prediction_with_time_decay(match)
        match['current_prediction'] = adjusted_prediction
        
        # Track adjustments
        adjustment = {
            'minute': minute,
            'score': score.copy(),
            'prediction': adjusted_prediction.copy(),
            'momentum': momentum
        }
        match['adjustments'].append(adjustment)
        
        # Emit real-time update via WebSocket
        if self.socketio:
            self.socketio.emit('match_update', {
                'match_id': match_id,
                'minute': minute,
                'score': score,
                'possession': match['possession'],
                'prediction': adjusted_prediction,
                'momentum': momentum,
                'has_goal_changed': score['home'] != old_score['home'] or score['away'] != old_score['away']
            }, room=f'match_{match_id}')
        
        return adjusted_prediction
    
    def _process_event(self, match, event):
        """Process a match event and update statistics."""
        event_type = event.get('type')
        team = event.get('team')  # 'home' or 'away'
        
        match['events'].append({
            'minute': match['minute'],
            'type': event_type,
            'team': team,
            'timestamp': datetime.now()
        })
        
        # Update statistics based on event type
        if event_type == 'goal':
            pass  # Score already updated in update_match_state
        elif event_type == 'shot_on_target' and team:
            match['shots_on_target'][team] += 1
        elif event_type == 'corner' and team:
            match['corners'][team] += 1
        elif event_type == 'yellow_card' and team:
            match['cards'][team]['yellow'] += 1
        elif event_type == 'red_card' and team:
            match['cards'][team]['red'] += 1
            # Apply significant penalty for red card
            self._apply_red_card_penalty(match, team)
    
    def _apply_red_card_penalty(self, match, team_with_red):
        """Apply win probability penalty for red card."""
        # Team with red card gets -25% win probability
        penalty = 25
        
        if team_with_red == 'home':
            # Reduce home win probability, increase away
            match['current_prediction']['win_prob']['home'] = max(
                5, match['current_prediction']['win_prob']['home'] - penalty
            )
            match['current_prediction']['win_prob']['away'] = min(
                95, match['current_prediction']['win_prob']['away'] + penalty * 0.7
            )
        else:
            # Reduce away win probability, increase home
            match['current_prediction']['win_prob']['away'] = max(
                5, match['current_prediction']['win_prob']['away'] - penalty
            )
            match['current_prediction']['win_prob']['home'] = min(
                95, match['current_prediction']['win_prob']['home'] + penalty * 0.7
            )
        
        # Adjust draw probability
        remaining = 100 - (match['current_prediction']['win_prob']['home'] + match['current_prediction']['win_prob']['away'])
        match['current_prediction']['win_prob']['draw'] = max(0, remaining)
    
    def _calculate_momentum(self, match):
        """Calculate current match momentum (-1 to 1, where -1 = all away, 1 = all home)."""
        score_diff = match['current_score']['home'] - match['current_score']['away']
        possession_diff = match['possession']['home'] - match['possession']['away']
        shots_diff = match['shots_on_target']['home'] - match['shots_on_target']['away']
        
        # Weighted momentum calculation
        momentum = (
            (score_diff * 0.5) +           # Goals are most important
            (possession_diff * 0.001) +    # Possession difference (per percentage)
            (shots_diff * 0.1)             # Shots on target
        )
        
        # Normalize to -1 to 1 range
        momentum = max(-1, min(1, momentum / 3))
        return round(momentum, 2)
    
    def _adjust_prediction_with_time_decay(self, match):
        """
        Adjust predictions based on live match state with time-decay weighting.
        
        Time decay logic: Later in the match, current score matters more.
        Uses logistic function for smooth transition.
        """
        initial = match['initial_prediction']
        current = match['current_score']
        minute = match['minute']
        momentum = match['momentum_history'][-1]['momentum'] if match['momentum_history'] else 0
        
        # Time-decay factor: logistic function centered at 75th minute
        # This gives more weight to current score as match progresses
        time_weight = 1 / (1 + np.exp(-0.1 * (minute - 75)))
        
        # Score difference effect
        score_diff = current['home'] - current['away']
        
        # Base adjustments from score difference
        if score_diff > 0:
            # Home leading - boost home, reduce away
            home_boost = min(30, score_diff * 8 * time_weight)  # Max 30% boost
            away_penalty = min(20, score_diff * 6 * time_weight)  # Max 20% penalty
        elif score_diff < 0:
            # Away leading
            home_penalty = min(20, abs(score_diff) * 6 * time_weight)
            away_boost = min(30, abs(score_diff) * 8 * time_weight)
        else:
            # Draw
            home_boost = home_penalty = away_boost = away_penalty = 0
        
        # Momentum adjustment
        momentum_adjustment = momentum * 10  # Convert momentum (-1 to 1) to percentage adjustment
        
        # Start with initial probabilities
        adjusted = {
            'home': initial['win_prob']['home'],
            'draw': initial['win_prob']['draw'],
            'away': initial['win_prob']['away']
        }
        
        # Apply time-weighted score adjustments
        adjusted['home'] += home_boost - home_penalty + momentum_adjustment
        adjusted['away'] += away_boost - away_penalty - momentum_adjustment
        
        # Apply red card penalties if any
        red_card_effect = self._calculate_red_card_effect(match)
        adjusted['home'] += red_card_effect['home']
        adjusted['away'] += red_card_effect['away']
        
        # Ensure bounds
        for outcome in adjusted:
            adjusted[outcome] = max(1, min(99, adjusted[outcome]))
        
        # Normalize to 100%
        total = sum(adjusted.values())
        if total > 0:
            adjusted = {k: round((v / total) * 100, 1) for k, v in adjusted.items()}
        
        # Build response
        result = match['current_prediction'].copy()
        result['win_prob'] = adjusted
        result['momentum'] = momentum
        result['time_weight'] = round(time_weight, 2)
        result['minute'] = minute
        
        # Adjust score prediction based on current score
        if 'score' in result:
            # If current score is higher than predicted, adjust upwards
            current_goals = current['home'] + current['away']
            predicted_goals = result['score']['home'] + result['score']['away']
            
            if current_goals > predicted_goals and minute > 60:
                # Game is more high-scoring than predicted
                result['score']['home'] = max(current['home'], result['score']['home'])
                result['score']['away'] = max(current['away'], result['score']['away'])
        
        return result
    
    def _calculate_red_card_effect(self, match):
        """Calculate ongoing effect of red cards."""
        effect = {'home': 0, 'away': 0}
        
        # Home team red cards
        if match['cards']['home']['red'] > 0:
            effect['home'] -= 10 * match['cards']['home']['red']  # -10% per red card
            effect['away'] += 7 * match['cards']['home']['red']   # +7% for opponent
        
        # Away team red cards
        if match['cards']['away']['red'] > 0:
            effect['away'] -= 10 * match['cards']['away']['red']
            effect['home'] += 7 * match['cards']['away']['red']
        
        return effect
    
    def get_match_summary(self, match_id):
        """Get comprehensive match summary."""
        if match_id not in self.live_matches:
            return None
        
        match = self.live_matches[match_id]
        
        return {
            'match_id': match_id,
            'home': match['home'],
            'away': match['away'],
            'current_score': match['current_score'],
            'minute': match['minute'],
            'possession': match['possession'],
            'shots_on_target': match['shots_on_target'],
            'corners': match['corners'],
            'cards': match['cards'],
            'current_prediction': match['current_prediction'],
            'momentum_trend': match['momentum_history'][-5:] if len(match['momentum_history']) >= 5 else match['momentum_history'],
            'recent_events': list(match['events'])[-10:],
            'time_elapsed': str(datetime.now() - match['start_time']).split('.')[0]
        }
    
    def stop_tracking(self, match_id):
        """Stop tracking a match."""
        if match_id in self.live_matches:
            del self.live_matches[match_id]
            
            if self.socketio:
                self.socketio.emit('match_ended', {
                    'match_id': match_id
                }, room=f'match_{match_id}')
            
            return True
        return False
    
    def __repr__(self):
        return f"LiveMatchTracker(tracking={len(self.live_matches)} matches, websocket={'Yes' if self.socketio else 'No'})"