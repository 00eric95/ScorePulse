"""
Risk & Bankroll Strategy Agent for Football Predictions
Integrated into ScorePulse AI Chatbot System
Implements Kelly Criterion and betting strategy recommendations
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime
import json
import math
import statistics
import random
import logging

logger = logging.getLogger(__name__)

@dataclass
class BettingOpportunity:
    """Data structure for a betting opportunity"""
    match_id: str
    home_team: str
    away_team: str
    prediction_probability: float  # Our model's probability (0-1)
    market_odds: float  # Decimal odds from bookmaker
    market_implied_probability: float  # 1 / odds
    value: float  # Edge = prediction_prob - implied_prob
    kelly_fraction: float  # Recommended stake fraction
    recommended_stake_units: float
    confidence: float
    bet_type: str = "1X2"  # 1X2, Over/Under, etc.
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class BankrollHistory:
    """Track bankroll performance over time"""
    date: datetime
    balance: float
    total_staked: float
    total_won: float
    roi: float
    risk_appetite: str

class BankrollManager:
    """Manages betting bankroll using Kelly Criterion - Integrated into ScorePulse"""
    
    def __init__(self, initial_balance: float = 1000.0, risk_appetite: str = "half"):
        """
        Args:
            initial_balance: Starting bankroll
            risk_appetite: "full", "half", "quarter", or "fixed"
        """
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.risk_appetite = risk_appetite
        self.history: List[BankrollHistory] = []
        self.open_bets: List[BettingOpportunity] = []
        self.closed_bets: List[Dict] = []
        
        # Risk profiles
        self.risk_profiles = {
            "full": 1.0,      # Full Kelly
            "half": 0.5,      # Half Kelly (more conservative)
            "quarter": 0.25,  # Quarter Kelly (very conservative)
            "fixed": 0.02     # Fixed 2% of bankroll
        }
        # Placeholder for main predictor
        self.predictor = None
    
    def set_predictor(self, predictor):
        """This is called by the Pitch Commander during register_agent"""
        self.predictor = predictor
    
    def calculate_kelly_criterion(self, probability: float, odds: float) -> float:
        """
        Calculate Kelly Criterion fraction
        
        Formula: f* = (bp - q) / b
        Where:
          b = odds - 1
          p = probability of winning
          q = 1 - p
        
        Returns fraction of bankroll to bet (0-1)
        """
        if odds <= 1.0:
            return 0.0  # Invalid odds
        
        b = odds - 1
        p = probability
        q = 1 - p
        
        # Kelly formula
        kelly = (b * p - q) / b
        
        # Ensure within bounds
        kelly = max(0.0, min(kelly, 0.25))  # Cap at 25% of bankroll
        
        # Apply risk profile
        risk_multiplier = self.risk_profiles.get(self.risk_appetite, 0.5)
        
        return kelly * risk_multiplier
    
    def calculate_value(self, probability: float, odds: float) -> float:
        """Calculate expected value of a bet"""
        implied_probability = 1.0 / odds
        return probability - implied_probability
    
    def analyze_betting_opportunity(
        self, 
        match_id: str,
        home_team: str,
        away_team: str,
        prediction_probabilities: Dict[str, float],  # {'home': 0.45, 'draw': 0.25, 'away': 0.30}
        market_odds: Dict[str, float]  # {'home': 2.10, 'draw': 3.40, 'away': 3.20}
    ) -> Dict[str, Any]:
        """Analyze all betting opportunities for a match"""
        
        opportunities = []
        best_opportunity = None
        best_value = -999
        
        for outcome in ['home', 'draw', 'away']:
            if outcome in prediction_probabilities and outcome in market_odds:
                prob = prediction_probabilities[outcome]
                odds = market_odds[outcome]
                
                value = self.calculate_value(prob, odds)
                kelly_fraction = self.calculate_kelly_criterion(prob, odds)
                stake_units = kelly_fraction * self.current_balance
                
                # Calculate confidence score
                confidence = self._calculate_confidence(prob, value, kelly_fraction)
                
                opportunity = BettingOpportunity(
                    match_id=match_id,
                    home_team=home_team,
                    away_team=away_team,
                    prediction_probability=prob,
                    market_odds=odds,
                    market_implied_probability=1.0/odds,
                    value=value,
                    kelly_fraction=kelly_fraction,
                    recommended_stake_units=stake_units,
                    confidence=confidence,
                    bet_type=outcome
                )
                
                opportunities.append(opportunity)
                
                # Track best opportunity
                if value > best_value and kelly_fraction > 0:
                    best_value = value
                    best_opportunity = opportunity
        
        return {
            "match_id": match_id,
            "home_team": home_team,
            "away_team": away_team,
            "all_opportunities": opportunities,
            "best_opportunity": best_opportunity,
            "analysis": self._generate_analysis_report(opportunities)
        }
    
    def _calculate_confidence(self, probability: float, value: float, kelly_fraction: float) -> float:
        """Calculate confidence score (0-100)"""
        
        # Base confidence on probability
        prob_score = probability * 40  # Max 40 points
        
        # Value adds to confidence
        value_score = min(value * 100, 30)  # Max 30 points
        
        # Kelly fraction indicates strength
        kelly_score = min(kelly_fraction * 200, 30)  # Max 30 points
        
        confidence = prob_score + value_score + kelly_score
        return min(100, max(0, confidence))
    
    def _generate_analysis_report(self, opportunities: List[BettingOpportunity]) -> str:
        """Generate human-readable analysis report"""
        
        if not opportunities:
            return "No positive value betting opportunities found."
        
        report_lines = ["📊 BETTING OPPORTUNITY ANALYSIS", "=" * 40]
        
        # Sort by value
        sorted_opps = sorted(opportunities, key=lambda x: x.value, reverse=True)
        
        for opp in sorted_opps:
            if opp.value > 0 and opp.kelly_fraction > 0:
                bet_type_map = {'home': f'{opp.home_team} Win', 
                              'draw': 'Draw', 
                              'away': f'{opp.away_team} Win'}
                
                report_lines.append(f"\n🎯 {bet_type_map[opp.bet_type]}:")
                report_lines.append(f"   Our Probability: {opp.prediction_probability:.1%}")
                report_lines.append(f"   Market Odds: {opp.market_odds:.2f}")
                report_lines.append(f"   Market Implied: {opp.market_implied_probability:.1%}")
                report_lines.append(f"   Value (Edge): +{opp.value:.1%}")
                report_lines.append(f"   Kelly Stake: {opp.kelly_fraction:.1%} of bankroll")
                report_lines.append(f"   Recommended: ${opp.recommended_stake_units:.2f}")
                report_lines.append(f"   Confidence: {opp.confidence:.0f}/100")
        
        # Summary
        positive_value_opps = [o for o in opportunities if o.value > 0]
        if positive_value_opps:
            avg_value = statistics.mean([o.value for o in positive_value_opps])
            report_lines.append(f"\n📈 SUMMARY: Found {len(positive_value_opps)} positive-value opportunities")
            report_lines.append(f"   Average Edge: +{avg_value:.1%}")
        else:
            report_lines.append("\n⚠️ No positive value bets found. Consider passing.")
        
        return "\n".join(report_lines)
    
    def place_bet(self, opportunity: BettingOpportunity, stake: Optional[float] = None) -> bool:
        """Register a placed bet"""
        
        if stake is None:
            stake = opportunity.recommended_stake_units
        
        if stake > self.current_balance:
            return False  # Insufficient funds
        
        self.current_balance -= stake
        self.open_bets.append(opportunity)
        
        # Record transaction
        bet_record = {
            'match_id': opportunity.match_id,
            'bet_type': opportunity.bet_type,
            'stake': stake,
            'odds': opportunity.market_odds,
            'placed_at': datetime.now(),
            'status': 'OPEN'
        }
        self.closed_bets.append(bet_record)
        
        return True
    
    def settle_bet(self, match_id: str, bet_type: str, won: bool) -> None:
        """Settle a completed bet"""
        
        # Find and remove from open bets
        for i, bet in enumerate(self.open_bets):
            if bet.match_id == match_id and bet.bet_type == bet_type:
                self.open_bets.pop(i)
                
                # Update closed bet record
                for record in self.closed_bets:
                    if record['match_id'] == match_id and record['bet_type'] == bet_type:
                        record['settled_at'] = datetime.now()
                        record['status'] = 'WON' if won else 'LOST'
                        
                        if won:
                            winnings = record['stake'] * record['odds']
                            self.current_balance += winnings
                            record['winnings'] = winnings
                        else:
                            record['winnings'] = 0
                        break
                break
        
        # Update history
        self._update_history()
    
    def _update_history(self):
        """Update bankroll history"""
        
        total_staked = sum(r['stake'] for r in self.closed_bets)
        total_won = sum(r.get('winnings', 0) for r in self.closed_bets)
        roi = (total_won - total_staked) / total_staked if total_staked > 0 else 0
        
        history_entry = BankrollHistory(
            date=datetime.now(),
            balance=self.current_balance,
            total_staked=total_staked,
            total_won=total_won,
            roi=roi,
            risk_appetite=self.risk_appetite
        )
        self.history.append(history_entry)
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Generate performance report"""
        
        if not self.closed_bets:
            return {"status": "no_bets_placed"}
        
        settled_bets = [b for b in self.closed_bets if b['status'] in ['WON', 'LOST']]
        
        if not settled_bets:
            return {"status": "no_settled_bets"}
        
        won_bets = [b for b in settled_bets if b['status'] == 'WON']
        lost_bets = [b for b in settled_bets if b['status'] == 'LOST']
        
        total_bets = len(settled_bets)
        win_rate = len(won_bets) / total_bets if total_bets > 0 else 0
        
        total_staked = sum(b['stake'] for b in settled_bets)
        total_return = sum(b.get('winnings', 0) for b in settled_bets)
        total_profit = total_return - total_staked
        roi = (total_profit / total_staked) if total_staked > 0 else 0
        
        return {
            "total_bets": total_bets,
            "won": len(won_bets),
            "lost": len(lost_bets),
            "win_rate": win_rate,
            "total_staked": total_staked,
            "total_return": total_return,
            "total_profit": total_profit,
            "roi": roi,
            "current_balance": self.current_balance,
            "peak_balance": max([h.balance for h in self.history] + [self.current_balance])
        }
    
    def get_betting_recommendation(
        self, 
        home_team: str, 
        away_team: str, 
        prediction_probabilities: Dict[str, float],
        market_odds: Optional[Dict[str, float]] = None
    ) -> str:
        """Get a formatted betting recommendation string"""
        
        # If no market odds provided, use default fair odds
        if market_odds is None:
            market_odds = {
                'home': 1.0 / prediction_probabilities.get('home', 0.33),
                'draw': 1.0 / prediction_probabilities.get('draw', 0.33),
                'away': 1.0 / prediction_probabilities.get('away', 0.34)
            }
        
        analysis = self.analyze_betting_opportunity(
            match_id=f"{home_team}_{away_team}_{datetime.now().strftime('%Y%m%d')}",
            home_team=home_team,
            away_team=away_team,
            prediction_probabilities=prediction_probabilities,
            market_odds=market_odds
        )
        
        return analysis["analysis"]

class OddsAPI:
    """Mock odds API - can be replaced with real odds provider"""
    
    def __init__(self):
        self.providers = ["Bet365", "William Hill", "Pinnacle", "Betfair"]
    
    def get_market_odds(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Get market odds for a match"""
        # Mock implementation - replace with real API call
        
        # Base odds with some randomness
        import random
        
        # Simulate different odds from different bookmakers
        base_odds = {
            'home': random.uniform(1.8, 2.5),
            'draw': random.uniform(3.0, 3.8),
            'away': random.uniform(2.8, 4.0)
        }
        
        # Add some arbitrage opportunities occasionally
        if random.random() < 0.3:  # 30% chance of mispriced odds
            base_odds[random.choice(['home', 'draw', 'away'])] *= 1.15
        
        return base_odds
    
    def get_best_odds(self, home_team: str, away_team: str) -> Dict[str, float]:
        """Get best available odds across all bookmakers"""
        
        all_odds = []
        for _ in range(3):  # Get odds from 3 providers
            all_odds.append(self.get_market_odds(home_team, away_team))
        
        # Take best odds for each outcome
        best_odds = {
            'home': max(od['home'] for od in all_odds),
            'draw': max(od['draw'] for od in all_odds),
            'away': max(od['away'] for od in all_odds)
        }
        
        return best_odds