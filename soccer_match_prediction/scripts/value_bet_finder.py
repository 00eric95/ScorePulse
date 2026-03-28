# scripts/value_bet_finder.py
"""
Value Bet Finder with Kelly Criterion
Identifies profitable betting opportunities and calculates optimal stakes.
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math

class ValueBetFinder:
    def __init__(self, predictor=None):
        self.predictor = predictor
        self.bookmaker_odds = self.load_bookmaker_odds()
        print(f"✅ Value Bet Finder initialized with {len(self.bookmaker_odds)} odds records")
    
    def load_bookmaker_odds(self):
        """Load and validate betting odds with timestamps."""
        try:
            odds_df = pd.read_csv('../../data/betting_odds.csv', parse_dates=['timestamp'])
            
            # Filter out stale odds (older than 6 hours by default)
            six_hours_ago = datetime.now() - timedelta(hours=6)
            fresh_odds = odds_df[odds_df['timestamp'] >= six_hours_ago]
            
            stale_count = len(odds_df) - len(fresh_odds)
            if stale_count > 0:
                print(f"   ⚠️ Filtered out {stale_count} stale odds records (>6 hours old)")
            
            return fresh_odds
        except FileNotFoundError:
            print("   ⚠️ Betting odds file not found. Using empty DataFrame.")
            return pd.DataFrame()
        except Exception as e:
            print(f"   ⚠️ Error loading odds: {e}")
            return pd.DataFrame()
    
    def odds_to_implied_probability(self, odds_dict):
        """Convert decimal odds to implied probability (adjusted for margin)."""
        # Remove bookmaker margin using normalized probabilities
        implied_probs = {}
        margin_removed = {}
        
        for outcome, odds in odds_dict.items():
            if odds > 0:
                implied_probs[outcome] = 1 / odds
            else:
                implied_probs[outcome] = 0
        
        # Calculate total probability (should be >1 due to bookmaker margin)
        total_prob = sum(implied_probs.values())
        
        # Remove margin by normalizing to 1
        if total_prob > 0:
            for outcome, prob in implied_probs.items():
                margin_removed[outcome] = prob / total_prob
        
        return margin_removed
    
    def calculate_kelly_stake(self, predicted_prob, bookmaker_odds, bankroll=100, kelly_fraction=0.25):
        """
        Calculate optimal stake using Kelly Criterion.
        
        Args:
            predicted_prob: Our model's probability (0-1)
            bookmaker_odds: Decimal odds offered
            bankroll: Current bankroll
            kelly_fraction: Fraction of Kelly to use (0.25 = quarter Kelly, conservative)
        
        Returns: Recommended stake as percentage of bankroll
        """
        b = bookmaker_odds - 1  # Net odds
        p = predicted_prob      # Probability of winning
        q = 1 - p               # Probability of losing
        
        if b <= 0 or p <= 0 or q <= 0:
            return 0
        
        # Kelly formula: f* = (bp - q) / b
        kelly_percentage = (b * p - q) / b
        
        # Apply fractional Kelly for risk management
        kelly_percentage = kelly_percentage * kelly_fraction
        
        # Ensure non-negative and cap at 5% of bankroll
        kelly_percentage = max(0, min(kelly_percentage, 0.05))
        
        return kelly_percentage * 100  # Return as percentage
    
    def calculate_expected_value(self, predicted_prob, bookmaker_odds, stake=1):
        """Calculate expected value of a bet."""
        b = bookmaker_odds - 1
        p = predicted_prob
        q = 1 - p
        
        ev = (p * b - q) * stake
        return ev
    
    def find_value_bets(self, matches, threshold=0.05, max_odds_age_hours=6, min_odds=1.50):
        """
        Find value betting opportunities.
        
        Args:
            matches: List of upcoming matches
            threshold: Minimum value threshold (0.05 = 5%)
            max_odds_age_hours: Maximum age of odds data
            min_odds: Minimum acceptable odds
        
        Returns: Sorted list of value bets
        """
        value_bets = []
        cutoff_time = datetime.now() - timedelta(hours=max_odds_age_hours)
        
        for match in matches:
            home = match.get('home')
            away = match.get('away')
            
            if not home or not away:
                continue
            
            # Get prediction from model
            try:
                prediction = self.predictor.predict_for_web(home, away)
                if "error" in prediction:
                    continue
            except:
                continue
            
            # Find matching odds
            odds_record = self.get_fresh_odds(home, away, cutoff_time)
            if odds_record is None:
                continue
            
            # Get odds as dictionary
            odds_dict = {
                'home': odds_record.get('odds_home', 2.5),
                'draw': odds_record.get('odds_draw', 3.2),
                'away': odds_record.get('odds_away', 2.8)
            }
            
            # Skip if any odds are too low
            if min(odds_dict.values()) < min_odds:
                continue
            
            # Convert odds to implied probabilities
            implied_probs = self.odds_to_implied_probability(odds_dict)
            
            # Our model's probabilities (convert from percentage to 0-1)
            model_probs = {
                'home': prediction['win_prob']['home'] / 100,
                'draw': prediction['win_prob']['draw'] / 100,
                'away': prediction['win_prob']['away'] / 100
            }
            
            # Calculate value for each outcome
            for outcome in ['home', 'draw', 'away']:
                model_prob = model_probs[outcome]
                implied_prob = implied_probs[outcome]
                odds = odds_dict[outcome]
                
                # Value = (model probability / implied probability) - 1
                if implied_prob > 0:
                    value = (model_prob / implied_prob) - 1
                else:
                    value = 0
                
                # Calculate Kelly stake
                kelly_stake = self.calculate_kelly_stake(
                    predicted_prob=model_prob,
                    bookmaker_odds=odds,
                    bankroll=100,
                    kelly_fraction=0.25  # Conservative quarter-Kelly
                )
                
                # Calculate expected value
                ev = self.calculate_expected_value(model_prob, odds)
                
                # Check if this is a value bet
                if value >= threshold and ev > 0 and kelly_stake > 0:
                    value_bet = {
                        'match': f"{home} vs {away}",
                        'outcome': outcome,
                        'model_prob': round(model_prob * 100, 1),
                        'implied_prob': round(implied_prob * 100, 1),
                        'value_percent': round(value * 100, 1),
                        'odds': round(odds, 2),
                        'kelly_stake_percent': round(kelly_stake, 2),
                        'expected_value': round(ev, 3),
                        'confidence': prediction.get('confidence', {}).get('label', 'MEDIUM'),
                        'timestamp': odds_record.get('timestamp'),
                        'data_freshness_minutes': round((datetime.now() - odds_record['timestamp']).total_seconds() / 60, 1)
                    }
                    
                    # Add score prediction for context
                    if 'score' in prediction:
                        value_bet['predicted_score'] = f"{prediction['score']['home']}-{prediction['score']['away']}"
                    
                    value_bets.append(value_bet)
        
        # Sort by value percentage (highest first)
        return sorted(value_bets, key=lambda x: x['value_percent'], reverse=True)
    
    def get_fresh_odds(self, home_team, away_team, cutoff_time):
        """Get fresh odds for a specific match."""
        if self.bookmaker_odds.empty:
            return None
        
        # Find matching match
        mask = (
            (self.bookmaker_odds['home_team'].str.contains(home_team, case=False, na=False)) |
            (self.bookmaker_odds['away_team'].str.contains(away_team, case=False, na=False))
        )
        
        matches = self.bookmaker_odds[mask]
        if matches.empty:
            return None
        
        # Get the most recent record
        latest = matches.iloc[-1]
        
        # Check if odds are fresh enough
        if latest['timestamp'] < cutoff_time:
            return None
        
        return latest
    
    def generate_value_report(self, value_bets, bankroll=1000):
        """Generate a comprehensive value betting report."""
        if not value_bets:
            return {"message": "No value bets found at current thresholds"}
        
        report = {
            'generated_at': datetime.now().isoformat(),
            'bankroll': bankroll,
            'total_value_bets': len(value_bets),
            'bets': []
        }
        
        total_kelly_stake = 0
        total_ev = 0
        
        for bet in value_bets:
            stake_amount = bankroll * (bet['kelly_stake_percent'] / 100)
            potential_return = stake_amount * bet['odds']
            potential_profit = potential_return - stake_amount
            
            bet_detail = {
                **bet,
                'stake_amount': round(stake_amount, 2),
                'potential_return': round(potential_return, 2),
                'potential_profit': round(potential_profit, 2),
                'risk_level': self.assess_risk_level(bet['value_percent'], bet['confidence'])
            }
            
            report['bets'].append(bet_detail)
            total_kelly_stake += stake_amount
            total_ev += bet['expected_value'] * stake_amount
        
        report['total_stake'] = round(total_kelly_stake, 2)
        report['portfolio_ev'] = round(total_ev, 2)
        report['bankroll_after'] = round(bankroll + total_ev, 2)
        
        return report
    
    def assess_risk_level(self, value_percent, confidence):
        """Assess risk level of a value bet."""
        if value_percent > 20 and confidence == 'HIGH':
            return 'LOW'
        elif value_percent > 10 and confidence in ['HIGH', 'MEDIUM']:
            return 'MEDIUM'
        else:
            return 'HIGH'
    
    def __repr__(self):
        return f"ValueBetFinder(odds_records={len(self.bookmaker_odds)}, predictor={'Yes' if self.predictor else 'No'})"