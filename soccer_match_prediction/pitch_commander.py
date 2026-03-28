"""
ScorePulse AI Chatbot & MCP Integration System
Comprehensive AI Assistant with Multi-Modal Capabilities
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
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional, Union, Callable, Tuple
from dataclasses import dataclass, field
from enum import Enum
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor
import pandas as pd
from flask import render_template, url_for, flash, redirect, request, jsonify, session, current_app, Blueprint
from flask_login import login_required, current_user
from sqlalchemy import func, desc, and_, or_
from flask import Blueprint

# ============================================================================
# CRITICAL: PATH CONFIGURATION FOR AGENTS
# ============================================================================

# Get absolute paths
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # SCORE_PULSEAIv2
agents_dir = os.path.join(project_root, 'agents')

print(f"🔧 [PITCH COMMANDER INIT]")
print(f"   Current dir (pitch_commander.py): {current_dir}")
print(f"   Project root: {project_root}")
print(f"   Agents dir: {agents_dir}")
print(f"   Agents dir exists: {os.path.exists(agents_dir)}")

# Clear and set up sys.path properly
# We need to ensure the agents directory is in the path before importing
sys.path = [p for p in sys.path if 'agents' not in p]  # Remove any existing agents paths

# Add in correct order:
# 1. Project root (for package-style imports: agents.data_agent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)
    print(f"   ✅ Added project root to sys.path")

# 2. Agents directory (for direct imports: data_agent)
if os.path.exists(agents_dir) and agents_dir not in sys.path:
    sys.path.insert(0, agents_dir)
    print(f"   ✅ Added agents directory to sys.path")

# 3. Current directory
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
    print(f"   ✅ Added current directory to sys.path")

print(f"   First 5 entries in sys.path:")
for i, path in enumerate(sys.path[:5]):
    print(f"     [{i}] {path}")

# ============================================================================
# AGENT IMPORTS WITH FALLBACKS
# ============================================================================

# Initialize agent references as None (will be set later)
FootballDataProcessor = None
DescriptiveAnalyticsChatbot = None
EvaluationEngine = None
BankrollManager = None
AdminChatbot = None

def import_agents():
    """Import agents with multiple fallback strategies"""
    global FootballDataProcessor, DescriptiveAnalyticsChatbot, EvaluationEngine, BankrollManager, AdminChatbot
    
    print("🔍 [PITCH COMMANDER] Importing agents...")
    
    # Strategy 1: Try direct import from agents directory
    try:
        print("   Trying Strategy 1: Direct import (from agents directory)...")
        from data_agent import FootballDataProcessor as FDP
        from analyst_agent import DescriptiveAnalyticsChatbot as DAC
        from critic_agent import EvaluationEngine as EE
        from bankroll_agent import BankrollManager as BM
        from admin_agent import AdminChatbot as AC
        
        FootballDataProcessor = FDP
        DescriptiveAnalyticsChatbot = DAC
        EvaluationEngine = EE
        BankrollManager = BM
        AdminChatbot = AC
        
        print("   ✅ Strategy 1 successful: Direct imports worked")
        return True
    except ImportError as e:
        print(f"   ❌ Strategy 1 failed: {e}")
    
    # Strategy 2: Try package import (agents.data_agent)
    try:
        print("   Trying Strategy 2: Package import (agents.data_agent)...")
        from agents.data_agent import FootballDataProcessor as FDP
        from agents.analyst_agent import DescriptiveAnalyticsChatbot as DAC
        from agents.critic_agent import EvaluationEngine as EE
        from agents.bankroll_agent import BankrollManager as BM
        from agents.admin_agent import AdminChatbot as AC
        
        FootballDataProcessor = FDP
        DescriptiveAnalyticsChatbot = DAC
        EvaluationEngine = EE
        BankrollManager = BM
        AdminChatbot = AC
        
        print("   ✅ Strategy 2 successful: Package imports worked")
        return True
    except ImportError as e:
        print(f"   ❌ Strategy 2 failed: {e}")
    
    # Strategy 3: Try importing with full module path
    try:
        print("   Trying Strategy 3: Full module path...")
        import importlib
        
        # Try to import agents module first
        agents_module = importlib.import_module('agents')
        print(f"   ✅ Imported agents module: {agents_module.__file__}")
        
        # Now try to import from it
        FootballDataProcessor = getattr(agents_module.data_agent, 'FootballDataProcessor', None)
        DescriptiveAnalyticsChatbot = getattr(agents_module.analyst_agent, 'DescriptiveAnalyticsChatbot', None)
        EvaluationEngine = getattr(agents_module.critic_agent, 'EvaluationEngine', None)
        BankrollManager = getattr(agents_module.bankroll_agent, 'BankrollManager', None)
        AdminChatbot = getattr(agents_module.admin_agent, 'AdminChatbot', None)
        
        if all([FootballDataProcessor, DescriptiveAnalyticsChatbot, EvaluationEngine, BankrollManager, AdminChatbot]):
            print("   ✅ Strategy 3 successful: Full module path worked")
            return True
        else:
            print("   ❌ Strategy 3 failed: Not all agents found")
    except Exception as e:
        print(f"   ❌ Strategy 3 failed: {e}")
    
    # Strategy 4: Last resort - create dummy classes
    print("   ⚠️ All import strategies failed, creating dummy agent classes")
    
    class DummyAgent:
        def __init__(self, *args, **kwargs):
            print(f"      [DUMMY] Initializing {self.__class__.__name__}")
        
        def __getattr__(self, name):
            # Return a dummy method that does nothing
            def dummy_method(*args, **kwargs):
                print(f"      [DUMMY] Called {self.__class__.__name__}.{name}()")
                return None
            return dummy_method
    
    class DummyDataAgent(DummyAgent):
        def load_data(self):
            return {}
        
        def get_team_stats(self, team_name):
            return {"name": team_name, "dummy": True}
    
    class DummyAnalystAgent(DummyAgent):
        def generate_insight(self, insight_type, context):
            return f"Dummy analysis for {insight_type}"
    
    class DummyCriticAgent(DummyAgent):
        def request_evaluation(self, eval_type, context):
            return {"dummy": True, "evaluation": "No critic available"}
    
    class DummyBankrollAgent(DummyAgent):
        def calculate_kelly_criterion(self, probability, odds):
            return 0.01
        
        def get_betting_recommendation(self, home_team, away_team, probabilities, market_odds):
            return "No betting recommendation available"
    
    class DummyAdminAgent(DummyAgent):
        def process_command(self, command):
            return {"success": False, "message": "Admin agent not available"}
    
    FootballDataProcessor = DummyDataAgent
    DescriptiveAnalyticsChatbot = DummyAnalystAgent
    EvaluationEngine = DummyCriticAgent
    BankrollManager = DummyBankrollAgent
    AdminChatbot = DummyAdminAgent
    
    print("   ⚠️ Created dummy agent classes - limited functionality available")
    return False

# Import the agents now
import_agents()

# ============================================================================
# MATCH PREDICTOR IMPORT
# ============================================================================

MATCH_PREDICTOR_AVAILABLE = False

try:
    print("🔍 [PITCH COMMANDER] Importing MatchPredictor...")
    
    # Make sure project root is in path for main import
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
    
    # Try to import
    from main import MatchPredictor
    MATCH_PREDICTOR_AVAILABLE = True
    print("✅ MatchPredictor with online learning imported successfully")
except ImportError as e:
    print(f"⚠️ MatchPredictor not available: {e}")
    MATCH_PREDICTOR_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('chatbot_system.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configure Orchestrator Logging
orchestrator_logger = logging.getLogger('PitchCommander')
orchestrator_logger.setLevel(logging.INFO)
orchestrator_handler = logging.FileHandler('orchestrator.log')
orchestrator_handler.setFormatter(logging.Formatter('%(asctime)s - [PITCH COMMANDER] - %(levelname)s - %(message)s'))
orchestrator_logger.addHandler(orchestrator_handler)
orchestrator_logger.addHandler(logging.StreamHandler())

print("✅ [PITCH COMMANDER] Imports completed successfully")

# ============================================================================
# PITCH COMMANDER - CENTRAL ORCHESTRATOR
# ============================================================================

class PitchCommander:
    """
    The Central Orchestrator for ScorePulse AI.
    Manages data flow between specialized agents with online learning integration.
    """

    def __init__(self, data_path: str = "data/raw"):
        from app import db, create_app 
        from flask import current_app
        
        # Check if we are in a context; if not, use the app instance
        try:
            # Try to get the existing context
            _ = current_app.name 
            self.db = db
            self.app_context = None  # No context to push/pop later
        except RuntimeError:
            # NO CONTEXT: We are likely in a background thread or early init
            # We must manually push a context to allow DB access
            try:
                from run import app  # Import the actual app instance
                self.app_context = app.app_context()
                self.app_context.push()
                self.db = db
                print("✅ [PITCH COMMANDER] Manually pushed app context")
            except ImportError as e:
                print(f"⚠️ [PITCH COMMANDER] Could not import app from run.py: {e}")
                self.app_context = None
                self.db = None
        
        from app.models import ChatSession, ChatMessage
        self.context: Dict[str, Any] = {}
        self.data_path = data_path
        
        print("🔧 [PITCH COMMANDER] Initializing Agent Team...")
        
        # Initialize the Agent Team with safety checks
        try:
            if FootballDataProcessor:
                self.data_agent = FootballDataProcessor(data_path=self.data_path)
                print("✅ [PITCH COMMANDER] Data agent initialized")
            else:
                self.data_agent = None
                print("⚠️ [PITCH COMMANDER] Data agent not available")
        except Exception as e:
            print(f"❌ [PITCH COMMANDER] Error initializing data agent: {e}")
            self.data_agent = None
        
        try:
            if DescriptiveAnalyticsChatbot:
                self.analyst_agent = DescriptiveAnalyticsChatbot()
                print("✅ [PITCH COMMANDER] Analyst agent initialized")
            else:
                self.analyst_agent = None
                print("⚠️ [PITCH COMMANDER] Analyst agent not available")
        except Exception as e:
            print(f"❌ [PITCH COMMANDER] Error initializing analyst agent: {e}")
            self.analyst_agent = None
        
        try:
            if EvaluationEngine:
                self.critic_agent = EvaluationEngine()
                print("✅ [PITCH COMMANDER] Critic agent initialized")
            else:
                self.critic_agent = None
                print("⚠️ [PITCH COMMANDER] Critic agent not available")
        except Exception as e:
            print(f"❌ [PITCH COMMANDER] Error initializing critic agent: {e}")
            self.critic_agent = None
        
        try:
            if BankrollManager:
                self.bankroll_agent = BankrollManager()
                print("✅ [PITCH COMMANDER] Bankroll agent initialized")
            else:
                self.bankroll_agent = None
                print("⚠️ [PITCH COMMANDER] Bankroll agent not available")
        except Exception as e:
            print(f"❌ [PITCH COMMANDER] Error initializing bankroll agent: {e}")
            self.bankroll_agent = None
        
        self.agents = {}  # Dictionary to hold your sister agents
        self._initialize_agents()  # Call the internal setup method
        
        # Try to initialize admin agent if available
        try:
            if AdminChatbot:
                self.admin_agent = AdminChatbot()
                print("✅ [PITCH COMMANDER] Admin agent initialized")
            else:
                self.admin_agent = None
                print("⚠️ [PITCH COMMANDER] Admin agent not available")
        except Exception as e:
            print(f"❌ [PITCH COMMANDER] Error initializing admin agent: {e}")
            self.admin_agent = None
        
        # Initialize MatchPredictor with online learning capabilities
        self.match_predictor = None
        if MATCH_PREDICTOR_AVAILABLE:
            try:
                self.match_predictor = MatchPredictor()
                orchestrator_logger.info("✅ MatchPredictor with online learning initialized")
                
                # Get initial learning insights
                insights = self.match_predictor.get_learning_insights()
                if insights:
                    orchestrator_logger.info(f"📊 Online Learning Insights: {insights.get('system_status', {}).get('status', 'Unknown')}")
            except Exception as e:
                orchestrator_logger.error(f"Failed to initialize MatchPredictor: {str(e)}")
                self.match_predictor = None
                print(f"❌ [PITCH COMMANDER] Error initializing MatchPredictor: {e}")
        else:
            orchestrator_logger.warning("MatchPredictor not available, using fallback MCMC simulation")
            print("⚠️ [PITCH COMMANDER] MatchPredictor not available")
        
        # Check what agents were successfully initialized
        agent_count = sum([1 for agent in [self.data_agent, self.analyst_agent, self.critic_agent, self.bankroll_agent, self.admin_agent] if agent is not None])
        print(f"✅ [PITCH COMMANDER] Initialization complete: {agent_count}/5 agents available")
        
        orchestrator_logger.info("Pitch Commander initialized and agents registered.")
    
    def register_agent(self, agent_name: str, agent_instance: Any):
        """Register a specialized agent with the orchestrator"""
        if agent_instance is not None:
            self.agents[agent_name] = agent_instance
            logger.info(f"✅ Agent registered: {agent_name}")
        else:
            logger.warning(f"⚠️ Skipped registering {agent_name}: agent instance is None")
        
    def _initialize_agents(self):
        """Initializes and registers the sister agents."""
        print("🔧 [PITCH COMMANDER] Registering agents in internal registry...")
        
        if self.data_agent:
            self.register_agent("data", self.data_agent)
        else:
            print("⚠️ [PITCH COMMANDER] Skipping data agent (not available)")
        
        if self.analyst_agent:
            self.register_agent("analyst", self.analyst_agent)
        else:
            print("⚠️ [PITCH COMMANDER] Skipping analyst agent (not available)")
        
        if self.critic_agent:
            self.register_agent("critic", self.critic_agent)
        else:
            print("⚠️ [PITCH COMMANDER] Skipping critic agent (not available)")
        
        if self.bankroll_agent:
            self.register_agent("bankroll", self.bankroll_agent)
        else:
            print("⚠️ [PITCH COMMANDER] Skipping bankroll agent (not available)")
        
        # Don't register admin_agent in the main agents dict (it's special)
        if self.admin_agent:
            print("✅ [PITCH COMMANDER] Admin agent available (not in main registry)")
        
        orchestrator_logger.info(f"✅ Agents registered: {list(self.agents.keys())}")
        print(f"✅ [PITCH COMMANDER] Agent registry: {list(self.agents.keys())}")

    def run_match_pipeline(self, home_team: str, away_team: str, market_odds: Optional[Dict] = None) -> Dict[str, Any]:
        """
        MASTER WORKFLOW: Orchestrates the end-to-end prediction process with online learning.
        """
        orchestrator_logger.info(f"🚀 Starting orchestration for: {home_team} vs {away_team}")
        
        # Reset context for new run
        self.context = {
            "timestamp": datetime.now().isoformat(),
            "match": f"{home_team} vs {away_team}",
            "home_team": home_team,
            "away_team": away_team,
            "pipeline_version": "2.0_with_online_learning"
        }

        try:
            # STEP 1: Admin System Check (if available)
            if self.admin_agent:
                health = self.admin_agent.process_command('system_status')
                if not health.get('success'):
                    orchestrator_logger.warning("Admin Agent reported system issues. Proceeding with caution.")
                self.context["system_health"] = health

            # STEP 2: Data Retrieval - Enhanced with online learning weights
            orchestrator_logger.info("Fetching team performance data with online learning weights...")
            try:
                # Use match_predictor's data if available
                if self.match_predictor:
                    home_stats = self._get_enhanced_team_stats(home_team, True)
                    away_stats = self._get_enhanced_team_stats(away_team, False)
                    self.context["data"] = {
                        "home": home_stats, 
                        "away": away_stats,
                        "data_source": "match_predictor_with_weights"
                    }
                    orchestrator_logger.info(f"Enhanced data retrieved with learning weights")
                else:
                    # Fallback to data agent
                    self.data_agent.load_data()
                    home_stats = self.data_agent.get_team_stats(home_team)
                    away_stats = self.data_agent.get_team_stats(away_team)
                    self.context["data"] = {"home": home_stats, "away": away_stats}
                    
                orchestrator_logger.info(f"Data retrieved: {home_team} stats: {len(home_stats)} items, {away_team} stats: {len(away_stats)} items")
            except Exception as e:
                orchestrator_logger.error(f"Data retrieval failed: {str(e)}")
                # Use mock data as fallback
                home_stats = {"avg_goals_for": 1.5, "avg_goals_against": 1.0}
                away_stats = {"avg_goals_for": 1.2, "avg_goals_against": 1.3}
                self.context["data"] = {"home": home_stats, "away": away_stats, "data_source": "fallback"}

            # STEP 3: Core Prediction with Online Learning
            orchestrator_logger.info("Running prediction with online learning...")
            if self.match_predictor:
                # Use advanced MatchPredictor with online learning
                prediction = self._predict_with_online_learning(home_team, away_team)
            else:
                # Fallback to MCMC simulation
                prediction = self._simulate_mcmc(home_stats, away_stats)
            
            self.context["prediction"] = prediction
            orchestrator_logger.info(f"Prediction complete: {prediction.get('home_win_prob', 0):.2%} win probability")

            # STEP 4: Bankroll Strategy with Enhanced Values
            if market_odds:
                orchestrator_logger.info("Calculating betting strategy with enhanced probabilities...")
                try:
                    # Enhance market odds with learning insights
                    enhanced_odds = self._enhance_odds_with_learning(market_odds, home_team, away_team, prediction)
                    
                    # Try multiple approaches to find the right method
                    bet_advice = None
                    
                    # Approach 1: Direct Kelly calculation
                    if hasattr(self.bankroll_agent, 'calculate_kelly_bet'):
                        bet_advice = self.bankroll_agent.calculate_kelly_bet(
                            prediction['home_win_prob'], 
                            enhanced_odds.get('home_win_odds', market_odds.get('home_win_odds', 2.10))
                        )
                    # Approach 2: Kelly criterion
                    elif hasattr(self.bankroll_agent, 'calculate_kelly_criterion'):
                        kelly_fraction = self.bankroll_agent.calculate_kelly_criterion(
                            prediction['home_win_prob'], 
                            enhanced_odds.get('home_win_odds', market_odds.get('home_win_odds', 2.10))
                        )
                        bet_advice = {
                            "kelly_fraction": kelly_fraction,
                            "recommended_stake": kelly_fraction * 1000,  # Assuming 1000 bankroll
                            "probability": prediction['home_win_prob'],
                            "odds": enhanced_odds.get('home_win_odds', market_odds.get('home_win_odds', 2.10)),
                            "value_adjusted": enhanced_odds.get('value_adjusted', False)
                        }
                    # Approach 3: Get betting recommendation
                    elif hasattr(self.bankroll_agent, 'get_betting_recommendation'):
                        prediction_probabilities = {
                            'home': prediction['home_win_prob'],
                            'draw': prediction.get('draw_prob', (1 - prediction['home_win_prob']) / 2),
                            'away': prediction.get('away_win_prob', (1 - prediction['home_win_prob']) / 2)
                        }
                        bet_advice = self.bankroll_agent.get_betting_recommendation(
                            home_team, away_team, prediction_probabilities, enhanced_odds
                        )
                    
                    if bet_advice:
                        self.context["betting_strategy"] = bet_advice
                        orchestrator_logger.info(f"Betting strategy calculated with enhanced odds")
                    else:
                        orchestrator_logger.warning("No betting strategy available")
                        
                except Exception as e:
                    orchestrator_logger.error(f"Bankroll strategy failed: {str(e)}")

            # STEP 5: Analyst Narrative with Learning Insights
            orchestrator_logger.info("Generating analysis narrative with learning insights...")
            try:
                # Add learning insights to context
                learning_insights = self._get_learning_insights_for_match(home_team, away_team)
                enhanced_context = {**self.context, "learning_insights": learning_insights}
                
                insight = self.analyst_agent.generate_insight("match_preview", enhanced_context)
                self.context["analysis"] = insight
                orchestrator_logger.info("Analysis narrative generated with learning insights")
            except Exception as e:
                orchestrator_logger.error(f"Analysis generation failed: {str(e)}")
                # Create a basic analysis as fallback
                basic_analysis = f"""
                Match Analysis: {home_team} vs {away_team}
                -----------------------------------------
                Prediction: Home win probability: {prediction.get('home_win_prob', 0):.1%}
                Expected Score: {prediction.get('expected_score', 'N/A')}
                Online Learning: {'Active' if self.match_predictor else 'Inactive'}
                
                Based on statistical modeling, {home_team} has a {prediction.get('home_win_prob', 0):.1%} chance of winning.
                """
                self.context["analysis"] = basic_analysis

            # STEP 6: Critic Feedback with Learning Evaluation
            orchestrator_logger.info("Requesting critic evaluation with learning assessment...")
            try:
                if hasattr(self.critic_agent, 'request_evaluation'):
                    # Add learning metrics for critic
                    critic_context = {
                        **self.context,
                        "learning_metrics": self._get_learning_metrics(),
                        "prediction_confidence": prediction.get('confidence', {}),
                        "online_learning_status": self.match_predictor is not None
                    }
                    self.critic_agent.request_evaluation('classification', critic_context)
                    orchestrator_logger.info("Critic evaluation with learning assessment requested")
            except Exception as e:
                orchestrator_logger.warning(f"Critic evaluation failed: {str(e)}")

            # STEP 7: Record for Online Learning (if applicable)
            if self.match_predictor:
                try:
                    self._record_prediction_for_learning(home_team, away_team, prediction, market_odds)
                    orchestrator_logger.info("Prediction recorded for online learning system")
                except Exception as e:
                    orchestrator_logger.warning(f"Failed to record for online learning: {str(e)}")

            orchestrator_logger.info("✅ Orchestration pipeline with online learning completed successfully.")
            return self.context

        except Exception as e:
            orchestrator_logger.error(f"❌ Orchestration failed: {str(e)}")
            return {"success": False, "error": str(e), "context": self.context}

    def _predict_with_online_learning(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Use MatchPredictor with online learning capabilities for prediction"""
        if not self.match_predictor:
            return self._simulate_fallback_mcmc(home_team, away_team)
        
        try:
            # Use the MatchPredictor's advanced prediction
            result = self.match_predictor.predict_for_web(home_team, away_team, 'gold')
            
            if "error" in result:
                orchestrator_logger.warning(f"MatchPredictor error: {result['error']}, using fallback")
                return self._simulate_fallback_mcmc(home_team, away_team)
            
            # Convert MatchPredictor result to our format
            prediction = {
                "home_win_prob": result['win_prob']['home'] / 100.0,
                "draw_prob": result['win_prob']['draw'] / 100.0,
                "away_win_prob": result['win_prob']['away'] / 100.0,
                "expected_score": f"{result['score']['home']}-{result['score']['away']}",
                "simulation_iterations": 10000,  # MatchPredictor uses 10000 simulations
                "home_avg_goals": result.get('home_report', {}).get('attack', 1.5),
                "away_avg_goals": result.get('away_report', {}).get('attack', 1.2),
                "total_goals": result.get('total_goals', 2.5),
                "btts_probability": result.get('btts', 50) / 100.0,
                "over25_probability": result.get('over25', 50) / 100.0,
                "confidence": result.get('confidence', {}),
                "online_learning_applied": result.get('online_learning', {}).get('weights_applied', False) if 'online_learning' in result else False,
                "top_scores": result.get('top_scores', [])
            }
            
            # Add team reports if available
            if 'home_report' in result:
                prediction['home_report'] = result['home_report']
            if 'away_report' in result:
                prediction['away_report'] = result['away_report']
            
            orchestrator_logger.info(f"✅ Online learning prediction complete with confidence: {result.get('confidence', {}).get('label', 'Unknown')}")
            return prediction
            
        except Exception as e:
            orchestrator_logger.error(f"Error in online learning prediction: {str(e)}")
            return self._simulate_fallback_mcmc(home_team, away_team)

    def _simulate_mcmc(self, home_stats, away_stats, iterations=10000):
        """Legacy MCMC simulation (kept for compatibility)"""
        orchestrator_logger.warning("Using legacy MCMC simulation")
        return self._simulate_fallback_mcmc(home_stats, away_stats, iterations)

    def _simulate_fallback_mcmc(self, home_stats, away_stats, iterations=10000):
        """Fallback MCMC simulation when online learning is unavailable"""
        # Extract stats with fallbacks
        home_avg_goals = home_stats.get('avg_goals_for', 1.5) if isinstance(home_stats, dict) else 1.5
        away_avg_goals = away_stats.get('avg_goals_for', 1.2) if isinstance(away_stats, dict) else 1.2
        
        # Simulate using Poisson distribution
        np.random.seed(int(time.time()))  # Seed for reproducibility
        home_goals = np.random.poisson(home_avg_goals, iterations)
        away_goals = np.random.poisson(away_avg_goals, iterations)
        
        home_wins = np.sum(home_goals > away_goals)
        draws = np.sum(home_goals == away_goals)
        away_wins = np.sum(home_goals < away_goals)
        
        return {
            "home_win_prob": float(home_wins / iterations),
            "draw_prob": float(draws / iterations),
            "away_win_prob": float(away_wins / iterations),
            "expected_score": f"{np.mean(home_goals):.1f} - {np.mean(away_goals):.1f}",
            "simulation_iterations": iterations,
            "home_avg_goals": home_avg_goals,
            "away_avg_goals": away_avg_goals,
            "online_learning_applied": False,
            "confidence": {"label": "MEDIUM", "color": "text-yellow-400"}
        }

    def _get_enhanced_team_stats(self, team_name: str, is_home: bool) -> Dict[str, Any]:
        """Get team stats enhanced with online learning weights"""
        if not self.match_predictor:
            # Fallback to basic stats
            return self.data_agent.get_team_stats(team_name) if hasattr(self.data_agent, 'get_team_stats') else {}
        
        try:
            # Get team report card from MatchPredictor
            report = self.match_predictor.get_team_report_card(team_name)
            if report:
                # Enhance with learning weights
                enhanced_stats = {
                    "name": report.get("name", team_name),
                    "rating": report.get("rating", 1000),
                    "ppg": report.get("ppg", 1.0),
                    "attack": report.get("attack", 1.5),
                    "defense": report.get("defense", 1.2),
                    "form": report.get("form", 0),
                    "original_name": report.get("original_name", None),
                    "online_learning_weighted": True
                }
                
                # Apply team-specific weights if available
                team_weights = getattr(self.match_predictor, 'team_weights', {})
                if team_name in team_weights:
                    weight_data = team_weights[team_name]
                    enhanced_stats["learning_weight"] = weight_data.get("weight", 1.0)
                    enhanced_stats["adjustment_factor"] = weight_data.get("adjustment", 1.0)
                
                return enhanced_stats
            else:
                # Fallback if no report available
                return self.data_agent.get_team_stats(team_name) if hasattr(self.data_agent, 'get_team_stats') else {}
                
        except Exception as e:
            orchestrator_logger.warning(f"Error enhancing team stats for {team_name}: {str(e)}")
            return self.data_agent.get_team_stats(team_name) if hasattr(self.data_agent, 'get_team_stats') else {}

    def _enhance_odds_with_learning(self, market_odds: Dict, home_team: str, away_team: str, prediction: Dict) -> Dict:
        """Enhance market odds with online learning insights"""
        enhanced_odds = market_odds.copy()
        
        if not self.match_predictor:
            enhanced_odds["value_adjusted"] = False
            return enhanced_odds
        
        try:
            # Get team weights
            team_weights = getattr(self.match_predictor, 'team_weights', {})
            
            # Apply adjustments based on team weights
            home_weight = team_weights.get(home_team, {}).get("adjustment", 1.0)
            away_weight = team_weights.get(away_team, {}).get("adjustment", 1.0)
            
            # Adjust odds based on weights
            if 'home_win_odds' in enhanced_odds:
                enhanced_odds['home_win_odds'] = enhanced_odds['home_win_odds'] / home_weight
            
            if 'away_win_odds' in enhanced_odds:
                enhanced_odds['away_win_odds'] = enhanced_odds['away_win_odds'] / away_weight
            
            enhanced_odds["value_adjusted"] = True
            enhanced_odds["adjustment_factors"] = {
                "home": home_weight,
                "away": away_weight
            }
            
            orchestrator_logger.info(f"Odds enhanced with learning weights: home={home_weight:.2f}, away={away_weight:.2f}")
            return enhanced_odds
            
        except Exception as e:
            orchestrator_logger.warning(f"Error enhancing odds: {str(e)}")
            enhanced_odds["value_adjusted"] = False
            return enhanced_odds

    def _get_learning_insights_for_match(self, home_team: str, away_team: str) -> Dict[str, Any]:
        """Get learning insights specific to this match"""
        if not self.match_predictor:
            return {"online_learning": "inactive"}
        
        try:
            insights = self.match_predictor.get_learning_insights()
            if not insights:
                return {"online_learning": "active_no_insights"}
            
            # Filter insights for these specific teams
            match_insights = {
                "system_status": insights.get('system_status', {}),
                "prediction_stats": insights.get('prediction_stats', {}),
                "teams_improving": [
                    t for t in insights.get('teams_improving', [])
                    if isinstance(t, dict) and (t.get('name') == home_team or t.get('name') == away_team)
                ],
                "teams_declining": [
                    t for t in insights.get('teams_declining', [])
                    if isinstance(t, dict) and (t.get('name') == home_team or t.get('name') == away_team)
                ]
            }
            
            return match_insights
            
        except Exception as e:
            orchestrator_logger.warning(f"Error getting learning insights: {str(e)}")
            return {"online_learning": "error", "error": str(e)}

    def _get_learning_metrics(self) -> Dict[str, Any]:
        """Get metrics about the online learning system"""
        if not self.match_predictor:
            return {"status": "inactive"}
        
        try:
            insights = self.match_predictor.get_learning_insights()
            if not insights:
                return {"status": "active_no_data"}
            
            return {
                "status": "active",
                "total_predictions": insights.get('prediction_stats', {}).get('total_predictions', 0),
                "accuracy_trend": insights.get('prediction_stats', {}).get('accuracy_trend', 'stable'),
                "teams_tracked": len(getattr(self.match_predictor, 'team_weights', {})),
                "last_update": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {"status": "error", "error": str(e)}

    def _record_prediction_for_learning(self, home_team: str, away_team: str, prediction: Dict, market_odds: Optional[Dict]):
        """Record prediction for future online learning"""
        if not self.match_predictor or not hasattr(self.match_predictor, 'prediction_storage'):
            return
        
        try:
            # Create a match ID
            match_id = f"{home_team}_{away_team}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            
            # Store the prediction
            storage_result = self.match_predictor.prediction_storage.store_prediction(
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                match_date=datetime.now().isoformat(),
                predicted_data={
                    "win_prob": {
                        "home": prediction.get("home_win_prob", 0),
                        "draw": prediction.get("draw_prob", 0),
                        "away": prediction.get("away_win_prob", 0)
                    },
                    "expected_score": prediction.get("expected_score", "N/A"),
                    "market_odds": market_odds,
                    "context": self.context
                }
            )
            
            if storage_result:
                orchestrator_logger.debug(f"Prediction recorded for online learning: {match_id}")
                
        except Exception as e:
            orchestrator_logger.warning(f"Failed to record prediction for learning: {str(e)}")

    def process_completed_match(self, match_data: Dict[str, Any]) -> bool:
        """
        Process a completed match result for online learning.
        
        Args:
            match_data: Dict containing match result data
                - match_id: Unique match identifier
                - home_team: Home team name
                - away_team: Away team name
                - home_goals: Goals scored by home team
                - away_goals: Goals scored by away team
                - result: Match result ('home_win', 'away_win', 'draw')
                - match_date: Date of the match
        
        Returns:
            bool: True if processed successfully, False otherwise
        """
        if not self.match_predictor:
            orchestrator_logger.warning("Online learning not available, cannot process completed match")
            return False
        
        try:
            success = self.match_predictor.process_completed_match(match_data)
            if success:
                orchestrator_logger.info(f"✅ Completed match processed for online learning: {match_data.get('match_id')}")
            else:
                orchestrator_logger.warning(f"Failed to process completed match: {match_data.get('match_id')}")
            
            return success
            
        except Exception as e:
            orchestrator_logger.error(f"Error processing completed match: {str(e)}")
            return False

    def get_learning_system_status(self) -> Dict[str, Any]:
        """Get the status of the online learning system"""
        if not self.match_predictor:
            return {
                "status": "inactive",
                "message": "MatchPredictor not available",
                "timestamp": datetime.now().isoformat()
            }
        
        try:
            insights = self.match_predictor.get_learning_insights()
            system_status = insights.get('system_status', {}) if insights else {}
            
            return {
                "status": "active",
                "match_predictor_available": True,
                "online_learner_available": self.match_predictor.online_learner is not None,
                "prediction_storage_available": self.match_predictor.prediction_storage is not None,
                "teams_tracked": len(getattr(self.match_predictor, 'team_weights', {})),
                "system_status": system_status,
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            return {
                "status": "error",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def orchestrate_prediction_flow(self, home_team, away_team):
        """Legacy method for backward compatibility"""
        result = self.run_match_pipeline(home_team, away_team)
        
        # Format the result for backward compatibility
        return {
            "prediction": {
                "prob": result.get("prediction", {}).get("home_win_prob", 0.5),
                "expected_score": result.get("prediction", {}).get("expected_score", "N/A"),
                "simulation_details": result.get("prediction", {}),
                "online_learning_applied": result.get("prediction", {}).get("online_learning_applied", False)
            },
            "betting_advice": result.get("betting_strategy", {}),
            "narrative": result.get("analysis", "No analysis available"),
            "data": result.get("data", {}),
            "learning_insights": result.get("learning_insights", {}),
            "context": result
        }
        
    def __del__(self):
        """Cleanup method to pop app context if we pushed it"""
        if hasattr(self, 'app_context') and self.app_context:
            try:
                self.app_context.pop()
                print("✅ [PITCH COMMANDER] Cleaned up app context")
            except:
                pass

# ============================================================================
# ENUMS & DATA CLASSES (Keep existing)
# ============================================================================

class ChatbotMode(Enum):
    """Available chatbot modes"""
    ADMIN = "admin"
    USER_SUPPORT = "user_support"
    ML_ASSISTANT = "ml_assistant"
    DATA_ANALYST = "data_analyst"
    SYSTEM_MONITOR = "system_monitor"
    CODE_REVIEWER = "code_reviewer"
    DOCUMENTATION = "documentation"
    
class MessageType(Enum):
    """Types of messages in the chatbot"""
    USER = "user"
    BOT = "bot"
    SYSTEM = "system"
    ERROR = "error"
    WARNING = "warning"
    SUCCESS = "success"
    DATA = "data"
    CODE = "code"
    
class CommandCategory(Enum):
    """Categories of chatbot commands"""
    SYSTEM = "system"
    DATA = "data"
    ML = "ml"
    ANALYSIS = "analysis"
    ADMIN = "admin"
    USER = "user"
    UTILITY = "utility"
    
class MCPCommand(Enum):
    """MCP server commands"""
    START = "start_mcp"
    STOP = "stop_mcp"
    STATUS = "mcp_status"
    BROADCAST = "broadcast"
    EXECUTE = "execute"
    REGISTER = "register_tool"
    
@dataclass
class ChatMessageData:
    """Data structure for chat messages"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    user_id: int = 0
    message_type: MessageType = MessageType.USER
    content: str = ""
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    response_to: str = ""
    processed: bool = False
    
@dataclass
class ChatSessionData:
    """Data structure for chat sessions"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: int = 0
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    mode: ChatbotMode = ChatbotMode.USER_SUPPORT
    context: Dict[str, Any] = field(default_factory=dict)
    is_active: bool = True
    message_count: int = 0
    
@dataclass
class BotCommand:
    """Data structure for bot commands"""
    name: str
    description: str
    category: CommandCategory
    handler: Callable
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    requires_auth: bool = True
    admin_only: bool = False
    usage: str = ""
    
@dataclass
class MCPTool:
    """Data structure for MCP tools"""
    name: str
    version: str
    description: str
    endpoint: str
    methods: List[str]
    auth_required: bool = True
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    
@dataclass
class SystemMetrics:
    """Data structure for system metrics"""
    timestamp: datetime = field(default_factory=datetime.now)
    cpu_usage: float = 0.0
    memory_usage: float = 0.0
    disk_usage: float = 0.0
    active_users: int = 0
    active_sessions: int = 0
    queued_messages: int = 0
    processing_time: float = 0.0
    error_rate: float = 0.0
    predictions_today: int = 0
    revenue_today: float = 0.0

# ============================================================================
# KNOWLEDGE BASE & CONTEXT MANAGER (Keep existing)
# ============================================================================

class KnowledgeBase:
    """Centralized knowledge base for the chatbot"""
    
    def __init__(self, data_dir: str = "data/knowledge"):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Load knowledge files
        self.faqs = self._load_json("faqs.json", [])
        self.system_info = self._load_json("system_info.json", {})
        self.troubleshooting = self._load_json("troubleshooting.json", [])
        self.code_snippets = self._load_json("code_snippets.json", [])
        self.ml_models = self._load_json("ml_models.json", [])
        self.api_reference = self._load_json("api_reference.json", {})
        
        # Initialize vector store for semantic search (simplified)
        self.vector_index = {}
        self._build_vector_index()
        
    def _load_json(self, filename: str, default):
        """Load JSON file or return default"""
        filepath = self.data_dir / filename
        if filepath.exists():
            try:
                with open(filepath, 'r') as f:
                    return json.load(f)
            except:
                pass
        return default
    
    def _save_json(self, filename: str, data):
        """Save data to JSON file"""
        filepath = self.data_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
    
    def _build_vector_index(self):
        """Build a simple vector index for knowledge retrieval"""
        # This is a simplified version. In production, use proper embeddings.
        all_documents = []
        
        # Add FAQs
        for faq in self.faqs:
            doc = {
                "text": f"Q: {faq.get('question', '')}\nA: {faq.get('answer', '')}",
                "source": "faq",
                "metadata": faq
            }
            all_documents.append(doc)
            
        # Add troubleshooting
        for issue in self.troubleshooting:
            doc = {
                "text": f"Issue: {issue.get('issue', '')}\nSolution: {issue.get('solution', '')}",
                "source": "troubleshooting",
                "metadata": issue
            }
            all_documents.append(doc)
            
        # Index by keywords
        self.vector_index = {}
        for doc in all_documents:
            words = re.findall(r'\b\w+\b', doc["text"].lower())
            for word in words:
                if len(word) > 3:  # Ignore short words
                    if word not in self.vector_index:
                        self.vector_index[word] = []
                    self.vector_index[word].append(doc)
    
    def search(self, query: str, max_results: int = 5) -> List[Dict[str, Any]]:
        """Search knowledge base for relevant information"""
        query_words = re.findall(r'\b\w+\b', query.lower())
        results = []
        seen = set()
        
        for word in query_words:
            if word in self.vector_index and len(word) > 3:
                for doc in self.vector_index[word]:
                    doc_id = hash(doc["text"])
                    if doc_id not in seen:
                        # Simple relevance score
                        score = 0
                        for q_word in query_words:
                            if q_word in doc["text"].lower():
                                score += 1
                        
                        results.append({
                            **doc,
                            "relevance_score": score
                        })
                        seen.add(doc_id)
        
        # Sort by relevance and return top results
        results.sort(key=lambda x: x["relevance_score"], reverse=True)
        return results[:max_results]
    
    def add_faq(self, question: str, answer: str, category: str = "general") -> bool:
        """Add a new FAQ to knowledge base"""
        self.faqs.append({
            "id": len(self.faqs) + 1,
            "question": question,
            "answer": answer,
            "category": category,
            "timestamp": datetime.now().isoformat()
        })
        self._save_json("faqs.json", self.faqs)
        self._build_vector_index()  # Rebuild index
        return True
    
    def add_troubleshooting(self, issue: str, solution: str, tags: List[str] = None) -> bool:
        """Add troubleshooting entry"""
        self.troubleshooting.append({
            "id": len(self.troubleshooting) + 1,
            "issue": issue,
            "solution": solution,
            "tags": tags or [],
            "timestamp": datetime.now().isoformat()
        })
        self._save_json("troubleshooting.json", self.troubleshooting)
        self._build_vector_index()
        return True
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information"""
        return {
            "system": self.system_info,
            "faqs_count": len(self.faqs),
            "troubleshooting_count": len(self.troubleshooting),
            "code_snippets_count": len(self.code_snippets),
            "ml_models_count": len(self.ml_models),
            "last_updated": datetime.now().isoformat()
        }

class ContextManager:
    """Manages conversation context and memory"""
    
    def __init__(self, max_context_length: int = 10):
        self.max_context_length = max_context_length
        self.contexts = {}  # session_id -> context list
        self.memories = {}  # user_id -> memory dict
        self.context_lock = threading.Lock()
        
    def get_context(self, session_id: str) -> List[Dict[str, Any]]:
        """Get conversation context for a session"""
        with self.context_lock:
            return self.contexts.get(session_id, [])
    
    def add_to_context(self, session_id: str, role: str, content: str, metadata: Dict = None) -> None:
        """Add a message to context"""
        with self.context_lock:
            if session_id not in self.contexts:
                self.contexts[session_id] = []
            
            self.contexts[session_id].append({
                "role": role,
                "content": content,
                "timestamp": datetime.now().isoformat(),
                "metadata": metadata or {}
            })
            
            # Trim context if too long
            if len(self.contexts[session_id]) > self.max_context_length:
                self.contexts[session_id] = self.contexts[session_id][-self.max_context_length:]
    
    def clear_context(self, session_id: str) -> None:
        """Clear context for a session"""
        with self.context_lock:
            if session_id in self.contexts:
                del self.contexts[session_id]
    
    def get_user_memory(self, user_id: int) -> Dict[str, Any]:
        """Get user memory/context"""
        return self.memories.get(user_id, {})
    
    def update_user_memory(self, user_id: int, key: str, value: Any) -> None:
        """Update user memory"""
        if user_id not in self.memories:
            self.memories[user_id] = {}
        self.memories[user_id][key] = {
            "value": value,
            "timestamp": datetime.now().isoformat()
        }
    
    def summarize_context(self, session_id: str) -> str:
        """Create a summary of the conversation context"""
        context = self.get_context(session_id)
        if not context:
            return "No conversation history."
        
        summary_parts = []
        for i, msg in enumerate(context[-5:]):  # Last 5 messages
            role = "User" if msg["role"] == "user" else "Assistant"
            summary_parts.append(f"{role}: {msg['content'][:100]}...")
        
        return "\n".join(summary_parts)

# ============================================================================
# NATURAL LANGUAGE PROCESSING (NLP) ENGINE (Keep existing)
# ============================================================================

class NLPEngine:
    """Handles natural language understanding and processing"""
    
    def __init__(self):
        # Intent patterns
        self.intent_patterns = {
            "greeting": [
                r"hello", r"hi", r"hey", r"greetings",
                r"good morning", r"good afternoon", r"good evening"
            ],
            "farewell": [
                r"bye", r"goodbye", r"see you", r"exit", r"quit"
            ],
            "help": [
                r"help", r"support", r"assistance", r"what can you do"
            ],
            "prediction": [
                r"predict", r"forecast", r"match", r"game", r"score",
                r"who will win", r"prediction for"
            ],
            "analysis": [
                r"analyze", r"analysis", r"stats", r"statistics",
                r"data", r"insights", r"report"
            ],
            "system": [
                r"system", r"status", r"health", r"metrics",
                r"performance", r"monitor"
            ],
            "error": [
                r"error", r"bug", r"issue", r"problem", r"not working",
                r"failed", r"broken"
            ],
            "user": [
                r"profile", r"account", r"subscription", r"payment",
                r"billing", r"upgrade"
            ],
            "data": [
                r"data", r"csv", r"file", r"upload", r"dataset",
                r"training", r"model"
            ],
            "admin": [
                r"admin", r"users", r"revenue", r"logs", r"dashboard"
            ]
        }
        
        # Entity extraction patterns
        self.entity_patterns = {
            "team": r"\b([A-Z][a-z]+(?:\s[A-Z][a-z]+)*)\b",
            "number": r"\b\d+\b",
            "date": r"\b\d{4}-\d{2}-\d{2}\b|\b\d{2}/\d{2}/\d{4}\b",
            "file": r"\b\w+\.(csv|json|txt|py|html|css|js)\b",
            "command": r"/(\w+)"
        }
        
    def detect_intent(self, text: str) -> Tuple[str, float]:
        """Detect the intent of user input"""
        text_lower = text.lower()
        intent_scores = {}
        
        for intent, patterns in self.intent_patterns.items():
            score = 0
            for pattern in patterns:
                if re.search(pattern, text_lower):
                    score += 1
            if score > 0:
                intent_scores[intent] = score / len(patterns)
        
        if not intent_scores:
            return "unknown", 0.0
        
        best_intent = max(intent_scores.items(), key=lambda x: x[1])
        return best_intent
    
    def extract_entities(self, text: str) -> Dict[str, List[str]]:
        """Extract entities from text"""
        entities = {}
        
        for entity_type, pattern in self.entity_patterns.items():
            matches = re.findall(pattern, text)
            if matches:
                entities[entity_type] = matches
        
        return entities
    
    def parse_command(self, text: str) -> Optional[Dict[str, Any]]:
        """Parse chatbot command from text"""
        # Check for command prefix
        if text.startswith('/'):
            parts = text[1:].split()
            if parts:
                return {
                    "command": parts[0],
                    "args": parts[1:] if len(parts) > 1 else [],
                    "original": text
                }
        return None
    
    def classify_query_type(self, text: str) -> str:
        """Classify the type of user query"""
        intents = self.detect_intent(text)[0]
        entities = self.extract_entities(text)
        
        if intents == "prediction" and "team" in entities:
            return "match_prediction"
        elif intents == "analysis":
            return "data_analysis"
        elif intents == "system":
            return "system_status"
        elif intents == "error":
            return "troubleshooting"
        elif intents == "user":
            return "user_query"
        elif intents == "admin":
            return "admin_query"
        elif intents == "greeting":
            return "greeting"
        elif intents == "help":
            return "help_request"
        else:
            return "general_query"
    
    def generate_response_template(self, query_type: str) -> Dict[str, Any]:
        """Generate response template based on query type"""
        templates = {
            "greeting": {
                "response": "Hello! I'm the ScorePulse AI assistant. How can I help you today?",
                "suggestions": ["Predict a match", "Check system status", "Analyze data", "Get help"]
            },
            "match_prediction": {
                "response": "I can help you predict match outcomes. Which teams are you interested in?",
                "suggestions": ["Enter home team", "Enter away team", "View recent predictions"]
            },
            "data_analysis": {
                "response": "I can analyze your data. What would you like me to analyze?",
                "suggestions": ["CSV files", "ML models", "Performance metrics", "User statistics"]
            },
            "system_status": {
                "response": "Here's the current system status:",
                "suggestions": ["Detailed metrics", "Server health", "Database status"]
            },
            "troubleshooting": {
                "response": "I'll help you troubleshoot the issue. Can you describe what's happening?",
                "suggestions": ["Common solutions", "Check logs", "Contact support"]
            },
            "help_request": {
                "response": "I can help with predictions, data analysis, system monitoring, and more. What do you need?",
                "suggestions": ["Available commands", "User guide", "Contact admin"]
            }
        }
        
        return templates.get(query_type, {
            "response": "I understand. Let me help you with that.",
            "suggestions": []
        })

# ============================================================================
# MAIN CHATBOT SYSTEM - UPDATED TO USE PITCH COMMANDER
# ============================================================================

class ScorePulseChatbot:
    """Main chatbot system for ScorePulse AI"""
    
    def __init__(self, app_root: str = None):
        """Initialize the comprehensive chatbot system"""
        from app import db
        from app.models import ChatSession, ChatMessage
        self.db = db
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.dirname(self.app_root)
        
        # Initialize components
        self.knowledge_base = KnowledgeBase(os.path.join(self.app_root, "data/knowledge"))
        self.context_manager = ContextManager()
        self.nlp_engine = NLPEngine()
        
        # Initialize Pitch Commander as central orchestrator
        self.pitch_commander = PitchCommander(data_path=os.path.join(self.project_root, "data/raw"))
        
        # MCP Server
        self.mcp_server = None
        self.mcp_enabled = False
        
        # Command registry
        self.commands = {}
        self._register_commands()
        
        # Message queue for async processing
        self.message_queue = queue.Queue()
        self.processing_thread = None
        self._start_processing_thread()
        
        # User sessions
        self.user_sessions = {}
        
        # System metrics
        self.metrics = SystemMetrics()
        self._start_metrics_collection()
        
        logger.info(f"ScorePulse Chatbot initialized for project: {self.project_root}")
        logger.info(f"Pitch Commander orchestrator integrated")
    
    def _register_commands(self):
        """Register all available commands"""
        # System commands
        self.register_command(BotCommand(
            name="help",
            description="Show available commands",
            category=CommandCategory.SYSTEM,
            handler=self._handle_help,
            requires_auth=False
        ))
        
        self.register_command(BotCommand(
            name="status",
            description="Get system status",
            category=CommandCategory.SYSTEM,
            handler=self._handle_status
        ))
        
        self.register_command(BotCommand(
            name="metrics",
            description="Get detailed metrics",
            category=CommandCategory.SYSTEM,
            handler=self._handle_metrics,
            admin_only=True
        ))
        
        # Data commands
        self.register_command(BotCommand(
            name="analyze_data",
            description="Analyze CSV data files",
            category=CommandCategory.DATA,
            handler=self._handle_analyze_data,
            parameters=[
                {"name": "filename", "type": "string", "required": True, "description": "CSV filename"}
            ]
        ))
        
        self.register_command(BotCommand(
            name="list_data",
            description="List available data files",
            category=CommandCategory.DATA,
            handler=self._handle_list_data
        ))
        
        # ML commands
        self.register_command(BotCommand(
            name="predict_match",
            description="Predict match outcome using Pitch Commander",
            category=CommandCategory.ML,
            handler=self._handle_predict_match,
            parameters=[
                {"name": "home_team", "type": "string", "required": True},
                {"name": "away_team", "type": "string", "required": True},
                {"name": "odds", "type": "string", "required": False, "description": "Market odds in JSON format"}
            ]
        ))
        
        self.register_command(BotCommand(
            name="ml_status",
            description="Check ML pipeline status",
            category=CommandCategory.ML,
            handler=self._handle_ml_status
        ))
        
        # Admin commands
        self.register_command(BotCommand(
            name="user_stats",
            description="Get user statistics",
            category=CommandCategory.ADMIN,
            handler=self._handle_user_stats,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="revenue_report",
            description="Get revenue report",
            category=CommandCategory.ADMIN,
            handler=self._handle_revenue_report,
            admin_only=True
        ))
        
        # MCP commands
        self.register_command(BotCommand(
            name="start_mcp",
            description="Start MCP server",
            category=CommandCategory.SYSTEM,
            handler=self._handle_start_mcp,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="stop_mcp",
            description="Stop MCP server",
            category=CommandCategory.SYSTEM,
            handler=self._handle_stop_mcp,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="mcp_status",
            description="Check MCP server status",
            category=CommandCategory.SYSTEM,
            handler=self._handle_mcp_status
        ))
        
        # Orchestrator commands
        self.register_command(BotCommand(
            name="orchestrate",
            description="Run full orchestration pipeline for match prediction",
            category=CommandCategory.ML,
            handler=self._handle_orchestrate,
            parameters=[
                {"name": "home_team", "type": "string", "required": True},
                {"name": "away_team", "type": "string", "required": True}
            ]
        ))
        
        logger.info(f"Registered {len(self.commands)} commands")
    
    def _handle_predict_match(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle match prediction command using Pitch Commander"""
        if len(args) < 2:
            return {
                "success": False,
                "message": "Usage: /predict_match <home_team> <away_team> [odds_json]",
                "type": MessageType.ERROR.value
            }
        
        home_team = args[0]
        away_team = args[1]
        market_odds = None
        
        # Parse market odds if provided
        if len(args) >= 3:
            try:
                odds_str = ' '.join(args[2:])
                market_odds = json.loads(odds_str)
            except:
                # Try to parse as simple odds
                try:
                    market_odds = {"home_win_odds": float(args[2])}
                except:
                    pass
        
        try:
            # Use Pitch Commander for orchestration
            result = self.pitch_commander.run_match_pipeline(home_team, away_team, market_odds)
            
            if "error" in result:
                return {
                    "success": False,
                    "message": f"Orchestration error: {result['error']}",
                    "type": MessageType.ERROR.value
                }
            
            # Format response
            prediction_text = f"""
⚽ PITCH COMMANDER ORCHESTRATION
---------------------------------
• Match: {home_team} vs {away_team}
• Home Win Probability: {result.get('prediction', {}).get('home_win_prob', 0):.1%}
• Draw Probability: {result.get('prediction', {}).get('draw_prob', 0):.1%}
• Away Win Probability: {result.get('prediction', {}).get('away_win_prob', 0):.1%}
• Expected Score: {result.get('prediction', {}).get('expected_score', 'N/A')}

Analysis:
{result.get('analysis', 'No analysis available')[:500]}...
"""
            
            # Add betting advice if available
            if "betting_strategy" in result:
                bet_advice = result["betting_strategy"]
                if isinstance(bet_advice, dict):
                    if "kelly_fraction" in bet_advice:
                        prediction_text += f"\n💰 Betting Advice:\n"
                        prediction_text += f"• Kelly Fraction: {bet_advice['kelly_fraction']:.2%}\n"
                        prediction_text += f"• Recommended Stake: ${bet_advice.get('recommended_stake', 0):.2f}\n"
                        prediction_text += f"• Probability: {bet_advice.get('probability', 0):.1%}\n"
                        prediction_text += f"• Odds: {bet_advice.get('odds', 'N/A')}\n"
            
            return {
                "success": True,
                "message": prediction_text,
                "type": MessageType.BOT.value,
                "data": result
            }
            
        except Exception as e:
            logger.error(f"Error in Pitch Commander orchestration: {str(e)}")
            return {
                "success": False,
                "message": f"Error in orchestration: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_orchestrate(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle orchestration command"""
        if len(args) < 2:
            return {
                "success": False,
                "message": "Usage: /orchestrate <home_team> <away_team>",
                "type": MessageType.ERROR.value
            }
        
        home_team = args[0]
        away_team = args[1]
        
        try:
            result = self.pitch_commander.run_match_pipeline(home_team, away_team)
            
            if "error" in result:
                return {
                    "success": False,
                    "message": f"Orchestration failed: {result['error']}",
                    "type": MessageType.ERROR.value
                }
            
            orchestration_text = f"""
🎯 PITCH COMMANDER ORCHESTRATION COMPLETE
------------------------------------------
Match: {home_team} vs {away_team}

📊 Prediction Results:
• Home Win: {result.get('prediction', {}).get('home_win_prob', 0):.1%}
• Draw: {result.get('prediction', {}).get('draw_prob', 0):.1%}
• Away Win: {result.get('prediction', {}).get('away_win_prob', 0):.1%}
• Expected Score: {result.get('prediction', {}).get('expected_score', 'N/A')}

📈 Data Processed: {'Yes' if 'data' in result else 'No'}
💰 Betting Strategy: {'Available' if 'betting_strategy' in result else 'Not available'}
📝 Analysis Generated: {'Yes' if 'analysis' in result else 'No'}
⚖️ Critic Evaluation: {'Requested' if 'critic' in str(result) else 'Not requested'}

Timeline:
{result.get('timestamp', 'N/A')}
"""
            
            return {
                "success": True,
                "message": orchestration_text,
                "type": MessageType.SUCCESS.value,
                "data": {
                    "match": f"{home_team} vs {away_team}",
                    "prediction": result.get('prediction', {}),
                    "has_betting_strategy": 'betting_strategy' in result,
                    "has_analysis": 'analysis' in result,
                    "orchestration_complete": True
                }
            }
            
        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            return {
                "success": False,
                "message": f"Orchestration error: {str(e)}",
                "type": MessageType.ERROR.value
            }

# ============================================================================
# ADVANCED MCP SERVER WITH WEBSOCKETS
# ============================================================================

class AdvancedMCPServer:
    """Advanced MCP Server with WebSocket support and tool registry"""
    
    def __init__(self, chatbot_instance, host: str = 'localhost', port: int = 8080):
        self.chatbot = chatbot_instance
        self.host = host
        self.port = port
        self.server = None
        self.server_thread = None
        self.ws_server = None
        self.ws_thread = None
        self.is_running = False
        self.connections = []
        self.registered_tools = {}
        self.clients = {}
        
        # MCP Protocol Configuration
        self.protocol = {
            "name": "ScorePulse MCP",
            "version": "2.0.0",
            "description": "Model Context Protocol for ScorePulse AI",
            "capabilities": ["execute", "stream", "tool_registry", "auth", "metrics"]
        }
        
        # Tool registry
        self._register_default_tools()
        
        logger.info(f"Advanced MCP Server initialized on {host}:{port}")
    
    def _register_default_tools(self):
        """Register default MCP tools"""
        self.register_tool({
            "name": "system_status",
            "version": "1.0",
            "description": "Get system status and metrics",
            "endpoint": "/api/system/status",
            "methods": ["GET"],
            "auth_required": True
        })
        
        self.register_tool({
            "name": "execute_command",
            "version": "1.0",
            "description": "Execute chatbot command",
            "endpoint": "/api/command/execute",
            "methods": ["POST"],
            "auth_required": True
        })
        
        self.register_tool({
            "name": "data_analysis",
            "version": "1.0",
            "description": "Analyze data files",
            "endpoint": "/api/data/analyze",
            "methods": ["POST"],
            "auth_required": True
        })
        
        self.register_tool({
            "name": "ml_predict",
            "version": "1.0",
            "description": "Make ML predictions",
            "endpoint": "/api/ml/predict",
            "methods": ["POST"],
            "auth_required": True
        })
    
    def register_tool(self, tool_config: Dict[str, Any]) -> bool:
        """Register a new MCP tool"""
        try:
            tool_name = tool_config["name"]
            self.registered_tools[tool_name] = tool_config
            logger.info(f"Registered MCP tool: {tool_name}")
            return True
        except Exception as e:
            logger.error(f"Failed to register tool: {e}")
            return False
    
    def start_server(self) -> bool:
        """Start both HTTP and WebSocket servers"""
        if self.is_running:
            logger.warning("MCP server is already running")
            return False
        
        try:
            # Start HTTP server
            self._start_http_server()
            
            # Start WebSocket server
            self._start_websocket_server()
            
            self.is_running = True
            logger.info(f"MCP Server started successfully on {self.host}:{self.port}")
            logger.info(f"WebSocket server started on {self.host}:{self.port + 1}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to start MCP server: {e}")
            return False
    
    def _start_http_server(self):
        """Start HTTP server"""
        import http.server
        import socketserver
        
        class MCPHTTPHandler(http.server.BaseHTTPRequestHandler):
            """HTTP handler for MCP server"""
            
            def do_GET(self):
                """Handle GET requests"""
                if self.path == '/api/status':
                    self._handle_status()
                elif self.path == '/api/tools':
                    self._handle_tools_list()
                elif self.path.startswith('/api/tool/'):
                    self._handle_tool_info(self.path.replace('/api/tool/', ''))
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def do_POST(self):
                """Handle POST requests"""
                if self.path == '/api/command/execute':
                    self._handle_command_execute()
                elif self.path == '/api/auth/token':
                    self._handle_auth()
                else:
                    self.send_response(404)
                    self.end_headers()
            
            def _handle_status(self):
                """Handle status endpoint"""
                status = {
                    "status": "running",
                    "timestamp": datetime.now().isoformat(),
                    "protocol": self.server.mcp_server.protocol,
                    "tools_count": len(self.server.mcp_server.registered_tools),
                    "clients_connected": len(self.server.mcp_server.clients)
                }
                self._send_json_response(200, status)
            
            def _handle_tools_list(self):
                """Handle tools listing endpoint"""
                tools = list(self.server.mcp_server.registered_tools.values())
                self._send_json_response(200, {"tools": tools})
            
            def _handle_tool_info(self, tool_name):
                """Handle tool info endpoint"""
                tool = self.server.mcp_server.registered_tools.get(tool_name)
                if tool:
                    self._send_json_response(200, tool)
                else:
                    self._send_json_response(404, {"error": "Tool not found"})
            
            def _handle_command_execute(self):
                """Handle command execution"""
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                try:
                    request_data = json.loads(post_data.decode('utf-8'))
                    command = request_data.get('command')
                    args = request_data.get('args', {})
                    
                    # Validate command
                    if not command:
                        self._send_json_response(400, {"error": "Command required"})
                        return
                    
                    # Execute via chatbot
                    response = self.server.mcp_server.chatbot.process_command(command, args)
                    
                    self._send_json_response(200, response)
                    
                except json.JSONDecodeError:
                    self._send_json_response(400, {"error": "Invalid JSON"})
                except Exception as e:
                    self._send_json_response(500, {"error": str(e)})
            
            def _handle_auth(self):
                """Handle authentication"""
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                
                try:
                    auth_data = json.loads(post_data.decode('utf-8'))
                    # Simplified auth - in production, use proper authentication
                    token = str(uuid.uuid4())
                    self.server.mcp_server.clients[token] = {
                        "authenticated": True,
                        "created_at": datetime.now().isoformat()
                    }
                    
                    self._send_json_response(200, {"token": token})
                    
                except Exception as e:
                    self._send_json_response(401, {"error": "Authentication failed"})
            
            def _send_json_response(self, status_code: int, data: Dict):
                """Send JSON response"""
                self.send_response(status_code)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Access-Control-Allow-Origin', '*')
                self.end_headers()
                self.wfile.write(json.dumps(data).encode('utf-8'))
            
            def log_message(self, format, *args):
                """Override logging"""
                logger.info(f"MCP HTTP: {format % args}")
        
        # Create and start HTTP server
        handler = MCPHTTPHandler
        self.http_server = socketserver.TCPServer((self.host, self.port), handler)
        self.http_server.mcp_server = self
        
        def run_http_server():
            logger.info(f"HTTP Server starting on {self.host}:{self.port}")
            self.http_server.serve_forever()
        
        self.http_thread = threading.Thread(target=run_http_server, daemon=True)
        self.http_thread.start()
    
    def _start_websocket_server(self):
        """Start WebSocket server"""
        try:
            import websockets
            import asyncio
            
            async def websocket_handler(websocket, path):
                """Handle WebSocket connections"""
                client_id = str(uuid.uuid4())
                self.clients[client_id] = {
                    "websocket": websocket,
                    "connected_at": datetime.now(),
                    "authenticated": False
                }
                
                logger.info(f"WebSocket client connected: {client_id}")
                
                try:
                    async for message in websocket:
                        await self._handle_websocket_message(client_id, message, websocket)
                except websockets.exceptions.ConnectionClosed:
                    logger.info(f"WebSocket client disconnected: {client_id}")
                finally:
                    if client_id in self.clients:
                        del self.clients[client_id]
            
            async def start_websocket_server():
                """Start WebSocket server"""
                ws_port = self.port + 1
                server = await websockets.serve(websocket_handler, self.host, ws_port)
                logger.info(f"WebSocket server started on {self.host}:{ws_port}")
                await server.wait_closed()
            
            # Run WebSocket server in thread
            def run_ws_server():
                asyncio.run(start_websocket_server())
            
            self.ws_thread = threading.Thread(target=run_ws_server, daemon=True)
            self.ws_thread.start()
            
        except ImportError:
            logger.warning("WebSocket server not started (websockets package not installed)")
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {e}")
    
    async def _handle_websocket_message(self, client_id: str, message: str, websocket):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(message)
            message_type = data.get("type", "message")
            
            if message_type == "auth":
                # Handle authentication
                token = data.get("token")
                if token and token in self.clients:
                    self.clients[client_id]["authenticated"] = True
                    await websocket.send(json.dumps({
                        "type": "auth_success",
                        "message": "Authenticated successfully"
                    }))
            
            elif message_type == "command":
                # Handle command execution
                if not self.clients[client_id]["authenticated"]:
                    await websocket.send(json.dumps({
                        "type": "error",
                        "message": "Authentication required"
                    }))
                    return
                
                command = data.get("command")
                args = data.get("args", {})
                
                response = self.chatbot.process_command(command, args)
                await websocket.send(json.dumps({
                    "type": "command_response",
                    "data": response
                }))
            
            elif message_type == "subscribe":
                # Handle subscription to updates
                channel = data.get("channel")
                if channel in ["system_metrics", "predictions", "alerts"]:
                    self.clients[client_id]["subscriptions"] = self.clients[client_id].get("subscriptions", [])
                    self.clients[client_id]["subscriptions"].append(channel)
                    await websocket.send(json.dumps({
                        "type": "subscribed",
                        "channel": channel
                    }))
            
            elif message_type == "ping":
                # Handle ping/pong
                await websocket.send(json.dumps({
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                }))
                
        except json.JSONDecodeError:
            await websocket.send(json.dumps({
                "type": "error",
                "message": "Invalid JSON"
            }))
        except Exception as e:
            logger.error(f"WebSocket error: {e}")
            await websocket.send(json.dumps({
                "type": "error",
                "message": str(e)
            }))
    
    async def broadcast_message(self, channel: str, data: Dict):
        """Broadcast message to subscribed clients"""
        message = {
            "type": "broadcast",
            "channel": channel,
            "data": data,
            "timestamp": datetime.now().isoformat()
        }
        
        message_json = json.dumps(message)
        
        for client_id, client_info in self.clients.items():
            if client_info.get("authenticated") and channel in client_info.get("subscriptions", []):
                try:
                    await client_info["websocket"].send(message_json)
                except:
                    pass  # Client disconnected
    
    def stop_server(self) -> bool:
        """Stop MCP servers"""
        if not self.is_running:
            return True
        
        try:
            # Stop HTTP server
            if self.http_server:
                self.http_server.shutdown()
                self.http_server.server_close()
            
            # Stop WebSocket server
            self.is_running = False
            
            logger.info("MCP Server stopped")
            return True
            
        except Exception as e:
            logger.error(f"Error stopping MCP server: {e}")
            return False
    
    def get_server_info(self) -> Dict[str, Any]:
        """Get server information"""
        return {
            "is_running": self.is_running,
            "host": self.host,
            "http_port": self.port,
            "websocket_port": self.port + 1 if self.is_running else None,
            "protocol": self.protocol,
            "registered_tools": len(self.registered_tools),
            "connected_clients": len(self.clients),
            "health": self._check_health()
        }
    
    def _check_health(self) -> Dict[str, Any]:
        """Check server health"""
        return {
            "http": self.is_running,
            "websocket": self.ws_thread is not None and self.ws_thread.is_alive(),
            "timestamp": datetime.now().isoformat()
        }

# ============================================================================
# MAIN CHATBOT SYSTEM
# ============================================================================

class ScorePulseChatbot:
    """Main chatbot system for ScorePulse AI"""
    
    def __init__(self, app_root: str = None):
        """Initialize the comprehensive chatbot system"""
        from app import db
        from app.models import ChatSession, ChatMessage
        self.db = db
        
        self.app_root = app_root or os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self.project_root = os.path.dirname(self.app_root)
        
        # Initialize components
        self.knowledge_base = KnowledgeBase(os.path.join(self.app_root, "data/knowledge"))
        self.context_manager = ContextManager()
        self.nlp_engine = NLPEngine()
        
        # MCP Server
        self.mcp_server = None
        self.mcp_enabled = False
        
        # Command registry
        self.commands = {}
        self._register_commands()
        
        # Message queue for async processing
        self.message_queue = queue.Queue()
        self.processing_thread = None
        self._start_processing_thread()
        
        # User sessions
        self.user_sessions = {}
        
        # System metrics
        self.metrics = SystemMetrics()
        self._start_metrics_collection()
        
        # Mark as ready
        self._ready = True
        
        logger.info(f"ScorePulse Chatbot initialized for project: {self.project_root}")
        print(f"✅ [CHATBOT] Initialized with message_queue: {self.message_queue}")
    
    def _register_commands(self):
        """Register all available commands"""
        # System commands
        self.register_command(BotCommand(
            name="help",
            description="Show available commands",
            category=CommandCategory.SYSTEM,
            handler=self._handle_help,
            requires_auth=False
        ))
        
        self.register_command(BotCommand(
            name="status",
            description="Get system status",
            category=CommandCategory.SYSTEM,
            handler=self._handle_status
        ))
        
        self.register_command(BotCommand(
            name="metrics",
            description="Get detailed metrics",
            category=CommandCategory.SYSTEM,
            handler=self._handle_metrics,
            admin_only=True
        ))
        
        # Data commands
        self.register_command(BotCommand(
            name="analyze_data",
            description="Analyze CSV data files",
            category=CommandCategory.DATA,
            handler=self._handle_analyze_data,
            parameters=[
                {"name": "filename", "type": "string", "required": True, "description": "CSV filename"}
            ]
        ))
        
        self.register_command(BotCommand(
            name="list_data",
            description="List available data files",
            category=CommandCategory.DATA,
            handler=self._handle_list_data
        ))
        
        # ML commands
        self.register_command(BotCommand(
            name="predict_match",
            description="Predict match outcome",
            category=CommandCategory.ML,
            handler=self._handle_predict_match,
            parameters=[
                {"name": "home_team", "type": "string", "required": True},
                {"name": "away_team", "type": "string", "required": True}
            ]
        ))
        
        self.register_command(BotCommand(
            name="ml_status",
            description="Check ML pipeline status",
            category=CommandCategory.ML,
            handler=self._handle_ml_status
        ))
        
        # Admin commands
        self.register_command(BotCommand(
            name="user_stats",
            description="Get user statistics",
            category=CommandCategory.ADMIN,
            handler=self._handle_user_stats,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="revenue_report",
            description="Get revenue report",
            category=CommandCategory.ADMIN,
            handler=self._handle_revenue_report,
            admin_only=True
        ))
        
        # MCP commands
        self.register_command(BotCommand(
            name="start_mcp",
            description="Start MCP server",
            category=CommandCategory.SYSTEM,
            handler=self._handle_start_mcp,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="stop_mcp",
            description="Stop MCP server",
            category=CommandCategory.SYSTEM,
            handler=self._handle_stop_mcp,
            admin_only=True
        ))
        
        self.register_command(BotCommand(
            name="mcp_status",
            description="Check MCP server status",
            category=CommandCategory.SYSTEM,
            handler=self._handle_mcp_status
        ))
        
        logger.info(f"Registered {len(self.commands)} commands")
    
    def register_command(self, command: BotCommand):
        """Register a new command"""
        self.commands[command.name] = command
    
    def _start_processing_thread(self):
        """Start background thread for message processing"""
        def process_messages():
            while True:
                try:
                    message_data = self.message_queue.get()
                    if message_data is None:  # Poison pill
                        break
                    
                    self._process_message_async(message_data)
                    self.message_queue.task_done()
                    
                except Exception as e:
                    logger.error(f"Error in message processing thread: {e}")
        
        self.processing_thread = threading.Thread(target=process_messages, daemon=True)
        self.processing_thread.start()
    
    def _start_metrics_collection(self):
        """Start periodic metrics collection"""
        def collect_metrics():
            while True:
                try:
                    self._update_metrics()
                    time.sleep(60)  # Update every minute
                except Exception as e:
                    logger.error(f"Error collecting metrics: {e}")
                    time.sleep(10)
        
        metrics_thread = threading.Thread(target=collect_metrics, daemon=True)
        metrics_thread.start()
    
    def _update_metrics(self):
        """Update system metrics WITHOUT database access (safe for background threads)"""
        try:
            # Update timestamp
            self.metrics.timestamp = datetime.now()
            
            # Safely get queue size
            if hasattr(self, 'message_queue') and self.message_queue is not None:
                try:
                    self.metrics.queued_messages = self.message_queue.qsize()
                except:
                    self.metrics.queued_messages = 0
            else:
                self.metrics.queued_messages = 0
            
            # Get session count
            if hasattr(self, 'user_sessions'):
                self.metrics.active_sessions = len(self.user_sessions)
            else:
                self.metrics.active_sessions = 0
            
            # Don't try to get database metrics in background thread
            # These would require Flask app context and database access
            self.metrics.active_users = 0  # Placeholder
            self.metrics.predictions_today = 0  # Placeholder
            self.metrics.revenue_today = 0.0  # Placeholder
            
            # System resource usage
            try:
                import psutil
                self.metrics.cpu_usage = psutil.cpu_percent()
                self.metrics.memory_usage = psutil.virtual_memory().percent
                self.metrics.disk_usage = psutil.disk_usage('/').percent
            except ImportError:
                self.metrics.cpu_usage = 0.0
                self.metrics.memory_usage = 0.0
                self.metrics.disk_usage = 0.0
            
            # Don't save to database - just log
            logger.debug(f"Metrics updated: CPU={self.metrics.cpu_usage}%, Memory={self.metrics.memory_usage}%, Queue={self.metrics.queued_messages}")
            
        except Exception as e:
            logger.error(f"❌ Error updating metrics: {e}")
    
    def _save_metrics(self):
        """Save metrics to database"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                log_entry = SystemLog(
                    log_type='metrics',
                    message='System metrics update',
                    data=json.dumps({
                        'cpu_usage': self.metrics.cpu_usage,
                        'memory_usage': self.metrics.memory_usage,
                        'active_users': self.metrics.active_users,
                        'predictions_today': self.metrics.predictions_today,
                        'revenue_today': float(self.metrics.revenue_today)
                    }, default=str)
                )
                db.session.add(log_entry)
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error saving metrics: {e}")
    
    # ==========================================================================
    # MESSAGE HANDLING
    # ==========================================================================
    
    def process_message(self, message: str, user_id: int = None, session_id: str = None) -> Dict[str, Any]:
        """Process a user message"""
        from app.models import ChatMessage, ChatSession
        start_time = time.time()
        
        try:
            # Create session if not exists
            if not session_id:
                session_id = str(uuid.uuid4())
            
            if session_id not in self.user_sessions:
                self.user_sessions[session_id] = ChatSessionData(
                    id=session_id,
                    user_id=user_id or 0,
                    mode=ChatbotMode.USER_SUPPORT if not user_id else ChatbotMode.USER_SUPPORT
                )
            
            # Update session activity
            self.user_sessions[session_id].last_activity = datetime.now()
            self.user_sessions[session_id].message_count += 1
            
            # Add to context
            self.context_manager.add_to_context(session_id, "user", message)
            
            # Check for command
            command_parsed = self.nlp_engine.parse_command(message)
            if command_parsed:
                response = self._handle_command(command_parsed, user_id, session_id)
            else:
                # Natural language processing
                response = self._handle_natural_language(message, user_id, session_id)
            
            # Add response to context
            if response.get("message"):
                self.context_manager.add_to_context(session_id, "assistant", response["message"])
            
            # Update processing time
            processing_time = time.time() - start_time
            response["processing_time"] = round(processing_time, 3)
            response["session_id"] = session_id
            
            # Log interaction
            self._log_interaction(user_id, session_id, message, response)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return {
                "success": False,
                "message": f"Error processing your message: {str(e)}",
                "type": MessageType.ERROR.value,
                "session_id": session_id
            }
    
    def _handle_natural_language(self, message: str, user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle natural language messages"""
        # Detect intent and entities
        intent, confidence = self.nlp_engine.detect_intent(message)
        entities = self.nlp_engine.extract_entities(message)
        query_type = self.nlp_engine.classify_query_type(message)
        
        # Get context
        context = self.context_manager.get_context(session_id)
        context_summary = self.context_manager.summarize_context(session_id)
        
        # Search knowledge base
        kb_results = self.knowledge_base.search(message)
        
        # Generate response based on query type
        template = self.nlp_engine.generate_response_template(query_type)
        
        # Customize response based on intent
        response_data = {
            "success": True,
            "message": template["response"],
            "type": MessageType.BOT.value,
            "intent": intent,
            "confidence": confidence,
            "query_type": query_type,
            "entities": entities,
            "suggestions": template["suggestions"],
            "knowledge_results": kb_results[:3] if kb_results else [],
            "context_summary": context_summary
        }
        
        # Add specific responses based on intent
        if intent == "prediction" and "team" in entities:
            teams = entities["team"]
            if len(teams) >= 2:
                response_data["message"] = f"I'll help predict the match between {teams[0]} and {teams[1]}. Would you like me to make a prediction?"
                response_data["suggestions"] = ["Yes, predict", "View team stats", "Recent matches"]
        
        elif intent == "system":
            system_status = self._get_system_status()
            response_data["message"] = f"System Status:\n- CPU: {system_status['cpu_usage']}%\n- Memory: {system_status['memory_usage']}%\n- Active Users: {system_status['active_users']}"
            response_data["data"] = system_status
        
        elif intent == "error":
            # Search troubleshooting
            if kb_results:
                best_solution = kb_results[0]
                response_data["message"] = f"I found a potential solution:\n\n{best_solution.get('text', '')}"
            else:
                response_data["message"] = "I'll help you troubleshoot. Can you provide more details about the error?"
        
        return response_data
    
    def _handle_command(self, command_data: Dict[str, Any], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle command execution"""
        command_name = command_data["command"]
        args = command_data["args"]
        
        # Check if command exists
        if command_name not in self.commands:
            return {
                "success": False,
                "message": f"Unknown command: {command_name}. Type /help for available commands.",
                "type": MessageType.ERROR.value
            }
        
        command = self.commands[command_name]
        
        # Check authentication
        if command.requires_auth and not user_id:
            return {
                "success": False,
                "message": "Authentication required for this command.",
                "type": MessageType.ERROR.value
            }
        
        # Check admin privileges
        if command.admin_only:
            # Check if user is admin (user_id 1 or has admin role)
            if user_id != 1:  # Simplified - expand with proper role checking
                return {
                    "success": False,
                    "message": "Admin privileges required.",
                    "type": MessageType.ERROR.value
                }
        
        # Execute command
        try:
            result = command.handler(args, user_id, session_id)
            result["command"] = command_name
            return result
            
        except Exception as e:
            logger.error(f"Error executing command {command_name}: {e}")
            return {
                "success": False,
                "message": f"Error executing command: {str(e)}",
                "type": MessageType.ERROR.value,
                "command": command_name
            }
    
    def _process_message_async(self, message_data: Dict[str, Any]):
        """Process message asynchronously (for heavy operations)"""
        try:
            # This is where you would process heavy operations
            # For now, just log it
            logger.debug(f"Async processing: {message_data.get('session_id')}")
        except Exception as e:
            logger.error(f"Async processing error: {e}")
    
    def _log_interaction(self, user_id: int, session_id: str, message: str, response: Dict[str, Any]):
        """Log user interaction to database"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                chat_message = ChatMessage(
                    session_id=session_id,
                    user_id=user_id,
                    message_type="user",
                    content=message,
                    metadata=json.dumps({
                        "processing_time": response.get("processing_time"),
                        "intent": response.get("intent"),
                        "confidence": response.get("confidence")
                    })
                )
                db.session.add(chat_message)
                
                bot_message = ChatMessage(
                    session_id=session_id,
                    user_id=user_id,
                    message_type="bot",
                    content=response.get("message", ""),
                    metadata=json.dumps({
                        "success": response.get("success"),
                        "type": response.get("type")
                    })
                )
                db.session.add(bot_message)
                
                db.session.commit()
                
        except Exception as e:
            logger.error(f"Error logging interaction: {e}")
    
    # ==========================================================================
    # COMMAND HANDLERS
    # ==========================================================================
    
    def _handle_help(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle help command"""
        user_commands = []
        admin_commands = []
        
        for name, cmd in self.commands.items():
            if cmd.admin_only and user_id != 1:
                continue
            
            if cmd.admin_only:
                admin_commands.append(f"/{name}: {cmd.description}")
            else:
                user_commands.append(f"/{name}: {cmd.description}")
        
        help_text = "Available Commands:\n\n"
        if user_commands:
            help_text += "User Commands:\n" + "\n".join(user_commands) + "\n\n"
        
        if admin_commands and user_id == 1:
            help_text += "Admin Commands:\n" + "\n".join(admin_commands)
        
        return {
            "success": True,
            "message": help_text,
            "type": MessageType.BOT.value,
            "commands_count": len(user_commands) + (len(admin_commands) if user_id == 1 else 0)
        }
    
    def _handle_status(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle status command"""
        system_status = self._get_system_status()
        
        status_text = f"""
🏥 SYSTEM STATUS
----------------
• Uptime: {system_status['uptime']}
• CPU Usage: {system_status['cpu_usage']}%
• Memory Usage: {system_status['memory_usage']}%
• Disk Usage: {system_status['disk_usage']}%
• Active Users: {system_status['active_users']}
• Active Sessions: {system_status['active_sessions']}
• Predictions Today: {system_status['predictions_today']}
• Revenue Today: ${system_status['revenue_today']:.2f}
• MCP Server: {'🟢 Online' if system_status['mcp_status'] else '🔴 Offline'}
"""
        
        return {
            "success": True,
            "message": status_text,
            "type": MessageType.SYSTEM.value,
            "data": system_status
        }
    
    def _handle_metrics(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle metrics command"""
        metrics_data = {
            "cpu_usage": self.metrics.cpu_usage,
            "memory_usage": self.metrics.memory_usage,
            "disk_usage": self.metrics.disk_usage,
            "active_users": self.metrics.active_users,
            "active_sessions": self.metrics.active_sessions,
            "queued_messages": self.metrics.queued_messages,
            "predictions_today": self.metrics.predictions_today,
            "revenue_today": self.metrics.revenue_today,
            "timestamp": self.metrics.timestamp.isoformat()
        }
        
        metrics_text = f"""
📊 DETAILED METRICS
-------------------
• CPU Usage: {metrics_data['cpu_usage']}%
• Memory Usage: {metrics_data['memory_usage']}%
• Disk Usage: {metrics_data['disk_usage']}%
• Active Users: {metrics_data['active_users']}
• Active Sessions: {metrics_data['active_sessions']}
• Queued Messages: {metrics_data['queued_messages']}
• Predictions Today: {metrics_data['predictions_today']}
• Revenue Today: ${metrics_data['revenue_today']:.2f}
• Last Updated: {metrics_data['timestamp']}
"""
        
        return {
            "success": True,
            "message": metrics_text,
            "type": MessageType.DATA.value,
            "data": metrics_data
        }
    
    def _handle_analyze_data(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle data analysis command"""
        if not args:
            return {
                "success": False,
                "message": "Please provide a filename. Usage: /analyze_data <filename.csv>",
                "type": MessageType.ERROR.value
            }
        
        filename = args[0]
        data_dir = os.path.join(self.project_root, "data")
        filepath = os.path.join(data_dir, filename)
        
        if not os.path.exists(filepath):
            return {
                "success": False,
                "message": f"File not found: {filename}",
                "type": MessageType.ERROR.value
            }
        
        try:
            # Read CSV file
            df = pd.read_csv(filepath)
            
            # Basic analysis
            analysis = {
                "filename": filename,
                "rows": len(df),
                "columns": len(df.columns),
                "column_names": list(df.columns),
                "data_types": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "missing_values": df.isnull().sum().to_dict(),
                "summary_stats": df.describe().to_dict() if df.select_dtypes(include=[np.number]).shape[1] > 0 else {}
            }
            
            analysis_text = f"""
📈 DATA ANALYSIS: {filename}
----------------------------
• Rows: {analysis['rows']:,}
• Columns: {analysis['columns']}
• Columns: {', '.join(analysis['column_names'][:5])}{'...' if len(analysis['column_names']) > 5 else ''}

Missing Values:
{json.dumps(analysis['missing_values'], indent=2)}
"""
            
            return {
                "success": True,
                "message": analysis_text,
                "type": MessageType.DATA.value,
                "data": analysis
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error analyzing file: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_predict_match(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle match prediction command"""
        if len(args) < 2:
            return {
                "success": False,
                "message": "Usage: /predict_match <home_team> <away_team>",
                "type": MessageType.ERROR.value
            }
        
        home_team = args[0]
        away_team = args[1]
        
        try:
            # Import the AI engine
            import main
            
            ai_engine = main.MatchPredictor()
            
            # Get user tier
            from flask import current_app
            with current_app.app_context():
                user = User.query.get(user_id) if user_id else None
                tier = user.subscription_tier if user and hasattr(user, 'subscription_tier') else 'free'
            
            # Make prediction
            result = ai_engine.predict_for_web(home_team, away_team, tier)
            
            if "error" in result:
                return {
                    "success": False,
                    "message": f"Prediction error: {result['error']}",
                    "type": MessageType.ERROR.value
                }
            
            # Format response
            prediction_text = f"""
⚽ MATCH PREDICTION
-------------------
• Match: {home_team} vs {away_team}
• Predicted Winner: {result.get('predicted_winner', 'N/A')}
• Confidence: {result.get('confidence', 0):.1%}
• Recommended Bet: {result.get('recommended_bet', 'N/A')}
• Odds: {result.get('odds', 'N/A')}
• Value: {result.get('value', 'N/A')}

Analysis:
{result.get('analysis', 'No analysis available')}
"""
            
            return {
                "success": True,
                "message": prediction_text,
                "type": MessageType.BOT.value,
                "data": result
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error making prediction: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_user_stats(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle user statistics command"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                # User statistics
                total_users = User.query.count()
                active_users = User.query.filter(User.last_seen >= datetime.now() - timedelta(days=7)).count()
                premium_users = User.query.filter(User.subscription_tier == 'premium').count()
                
                # Recent registrations
                recent_users = User.query.order_by(User.date_joined.desc()).limit(5).all()
                recent_list = [f"{u.username} ({u.date_joined.strftime('%Y-%m-%d')})" for u in recent_users]
                
                stats_text = f"""
👥 USER STATISTICS
------------------
• Total Users: {total_users}
• Active (7 days): {active_users}
• Premium Users: {premium_users}
• Free Users: {total_users - premium_users}

Recent Registrations:
{chr(10).join(recent_list)}
"""
                
                return {
                    "success": True,
                    "message": stats_text,
                    "type": MessageType.DATA.value,
                    "data": {
                        "total_users": total_users,
                        "active_users": active_users,
                        "premium_users": premium_users,
                        "free_users": total_users - premium_users
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting user stats: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_revenue_report(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle revenue report command"""
        try:
            from flask import current_app
            
            with current_app.app_context():
                # Today's revenue
                today = datetime.now().date()
                revenue_today = db.session.query(func.sum(Payment.amount)).filter(
                    func.date(Payment.timestamp) == today,
                    Payment.status == 'COMPLETED'
                ).scalar() or 0.0
                
                # This week's revenue
                week_ago = datetime.now() - timedelta(days=7)
                revenue_week = db.session.query(func.sum(Payment.amount)).filter(
                    Payment.timestamp >= week_ago,
                    Payment.status == 'COMPLETED'
                ).scalar() or 0.0
                
                # This month's revenue
                month_ago = datetime.now() - timedelta(days=30)
                revenue_month = db.session.query(func.sum(Payment.amount)).filter(
                    Payment.timestamp >= month_ago,
                    Payment.status == 'COMPLETED'
                ).scalar() or 0.0
                
                # Total revenue
                total_revenue = db.session.query(func.sum(Payment.amount)).filter(
                    Payment.status == 'COMPLETED'
                ).scalar() or 0.0
                
                # Recent transactions
                recent_payments = Payment.query.filter(
                    Payment.status == 'COMPLETED'
                ).order_by(Payment.timestamp.desc()).limit(5).all()
                
                recent_list = []
                for payment in recent_payments:
                    user = User.query.get(payment.user_id)
                    username = user.username if user else "Unknown"
                    recent_list.append(f"${payment.amount:.2f} - {username} ({payment.timestamp.strftime('%Y-%m-%d')})")
                
                report_text = f"""
💰 REVENUE REPORT
-----------------
• Today: ${revenue_today:.2f}
• This Week: ${revenue_week:.2f}
• This Month: ${revenue_month:.2f}
• Total: ${total_revenue:.2f}

Recent Transactions:
{chr(10).join(recent_list)}
"""
                
                return {
                    "success": True,
                    "message": report_text,
                    "type": MessageType.DATA.value,
                    "data": {
                        "today": float(revenue_today),
                        "this_week": float(revenue_week),
                        "this_month": float(revenue_month),
                        "total": float(total_revenue)
                    }
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error getting revenue report: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_start_mcp(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle MCP server start command"""
        port = int(args[0]) if args and args[0].isdigit() else 8080
        
        if self.mcp_server and self.mcp_server.is_running:
            return {
                "success": True,
                "message": f"MCP server is already running on port {self.mcp_server.port}",
                "type": MessageType.SUCCESS.value,
                "data": self.mcp_server.get_server_info()
            }
        
        try:
            self.mcp_server = AdvancedMCPServer(self, port=port)
            success = self.mcp_server.start_server()
            
            if success:
                self.mcp_enabled = True
                
                # Add to knowledge base
                self.knowledge_base.add_faq(
                    question="MCP Server",
                    answer=f"MCP Server started on port {port}. External tools can connect via HTTP and WebSocket.",
                    category="system"
                )
                
                return {
                    "success": True,
                    "message": f"MCP server started successfully on port {port}",
                    "type": MessageType.SUCCESS.value,
                    "data": self.mcp_server.get_server_info()
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to start MCP server",
                    "type": MessageType.ERROR.value
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error starting MCP server: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_stop_mcp(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle MCP server stop command"""
        if not self.mcp_server or not self.mcp_server.is_running:
            return {
                "success": True,
                "message": "MCP server is not running",
                "type": MessageType.WARNING.value
            }
        
        try:
            success = self.mcp_server.stop_server()
            
            if success:
                self.mcp_enabled = False
                
                return {
                    "success": True,
                    "message": "MCP server stopped successfully",
                    "type": MessageType.SUCCESS.value
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to stop MCP server",
                    "type": MessageType.ERROR.value
                }
                
        except Exception as e:
            return {
                "success": False,
                "message": f"Error stopping MCP server: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_mcp_status(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle MCP server status command"""
        if self.mcp_server:
            server_info = self.mcp_server.get_server_info()
            
            status_text = f"""
🔌 MCP SERVER STATUS
--------------------
• Status: {'🟢 Running' if server_info['is_running'] else '🔴 Stopped'}
• Host: {server_info['host']}
• HTTP Port: {server_info['http_port']}
• WebSocket Port: {server_info['websocket_port'] or 'N/A'}
• Protocol: {server_info['protocol']['version']}
• Registered Tools: {server_info['registered_tools']}
• Connected Clients: {server_info['connected_clients']}
"""
            
            return {
                "success": True,
                "message": status_text,
                "type": MessageType.SYSTEM.value,
                "data": server_info
            }
        else:
            return {
                "success": True,
                "message": "MCP server is not initialized",
                "type": MessageType.WARNING.value
            }
    
    def _handle_list_data(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle list data command"""
        data_dir = os.path.join(self.project_root, "data")
        
        if not os.path.exists(data_dir):
            return {
                "success": False,
                "message": "Data directory not found",
                "type": MessageType.ERROR.value
            }
        
        try:
            csv_files = []
            for file in os.listdir(data_dir):
                if file.endswith('.csv'):
                    filepath = os.path.join(data_dir, file)
                    size = os.path.getsize(filepath)
                    csv_files.append({
                        "filename": file,
                        "size": size,
                        "size_human": self._human_readable_size(size)
                    })
            
            if not csv_files:
                return {
                    "success": True,
                    "message": "No CSV files found in data directory",
                    "type": MessageType.WARNING.value
                }
            
            # Sort by size
            csv_files.sort(key=lambda x: x["size"], reverse=True)
            
            file_list = "\n".join([f"• {f['filename']} ({f['size_human']})" for f in csv_files[:10]])
            
            list_text = f"""
📁 DATA FILES ({len(csv_files)} found)
----------------------
{file_list}
"""
            
            if len(csv_files) > 10:
                list_text += f"\n... and {len(csv_files) - 10} more files"
            
            return {
                "success": True,
                "message": list_text,
                "type": MessageType.DATA.value,
                "data": {
                    "total_files": len(csv_files),
                    "files": csv_files[:10]
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error listing data files: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    def _handle_ml_status(self, args: List[str], user_id: int, session_id: str) -> Dict[str, Any]:
        """Handle ML pipeline status command"""
        try:
            # Check ML engine
            import main
            
            ai_engine = main.MatchPredictor()
            
            # Get model info
            model_info = {
                "status": "online",
                "model_version": getattr(ai_engine, 'model_version', 'unknown'),
                "trained_date": getattr(ai_engine, 'trained_date', 'unknown'),
                "accuracy": getattr(ai_engine, 'accuracy', 0.0)
            }
            
            # Check data directory
            data_dir = os.path.join(self.project_root, "data")
            csv_files = [f for f in os.listdir(data_dir) if f.endswith('.csv')] if os.path.exists(data_dir) else []
            
            status_text = f"""
🤖 ML PIPELINE STATUS
---------------------
• Engine: {'🟢 Online' if ai_engine else '🔴 Offline'}
• Model Version: {model_info['model_version']}
• Trained: {model_info['trained_date']}
• Accuracy: {model_info['accuracy']:.1%}
• Data Files: {len(csv_files)}
"""
            
            return {
                "success": True,
                "message": status_text,
                "type": MessageType.SYSTEM.value,
                "data": {
                    "engine_status": "online" if ai_engine else "offline",
                    "model_info": model_info,
                    "data_files": csv_files[:5]
                }
            }
            
        except Exception as e:
            return {
                "success": False,
                "message": f"Error checking ML status: {str(e)}",
                "type": MessageType.ERROR.value
            }
    
    # ==========================================================================
    # UTILITY METHODS
    # ==========================================================================
    
    def _get_system_status(self) -> Dict[str, Any]:
        """Get comprehensive system status"""
        return {
            "uptime": self._get_uptime(),
            "cpu_usage": self.metrics.cpu_usage,
            "memory_usage": self.metrics.memory_usage,
            "disk_usage": self.metrics.disk_usage,
            "active_users": self.metrics.active_users,
            "active_sessions": self.metrics.active_sessions,
            "queued_messages": self.message_queue.qsize(),
            "predictions_today": self.metrics.predictions_today,
            "revenue_today": float(self.metrics.revenue_today),
            "mcp_status": self.mcp_enabled,
            "chatbot_version": "2.0.0",
            "timestamp": datetime.now().isoformat()
        }
    
    def _get_uptime(self) -> str:
        """Get system uptime (simplified)"""
        # In a real system, you'd track start time
        return "24h"  # Placeholder
    
    def _human_readable_size(self, size: int) -> str:
        """Convert bytes to human readable size"""
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"
    
    def process_command(self, command: str, args: Dict[str, Any] = None) -> Dict[str, Any]:
        """Process a command (for MCP server integration)"""
        args = args or {}
        
        # Convert args dict to list if needed
        if isinstance(args, dict):
            arg_list = []
            for key, value in args.items():
                if value:
                    arg_list.append(str(value))
            args = arg_list
        elif isinstance(args, list):
            pass
        else:
            args = []
        
        # Execute command
        command_data = {
            "command": command,
            "args": args
        }
        
        return self._handle_command(command_data, user_id=1, session_id="mcp_integration")

# ============================================================================
# FLASK ROUTES & BLUEPRINT
# ============================================================================

# Create blueprint for chatbot routes
chatbot_bp = Blueprint('chatbot', __name__, url_prefix='/chatbot')

# Global chatbot instance
chatbot_instance = None

def init_chatbot(app):
    """Initialize chatbot with Flask app"""
    global chatbot_instance
    chatbot_instance = ScorePulseChatbot(app.root_path)
    
    # Register chatbot cleanup on app teardown
    @app.teardown_appcontext
    def cleanup_chatbot(exception=None):
        if chatbot_instance and chatbot_instance.mcp_server:
            chatbot_instance.mcp_server.stop_server()

@chatbot_bp.route('/chat', methods=['POST'])
@login_required
def chat():
    """Handle chat messages"""
    try:
        data = request.get_json()
        message = data.get('message', '').strip()
        
        if not message:
            return jsonify({
                'success': False,
                'message': 'Message is required'
            }), 400
        
        # Process message
        response = chatbot_instance.process_message(
            message=message,
            user_id=current_user.id,
            session_id=data.get('session_id')
        )
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            'success': False,
            'message': f'Error processing message: {str(e)}'
        }), 500

@chatbot_bp.route('/command', methods=['POST'])
@login_required
def command():
    """Execute chatbot command"""
    try:
        data = request.get_json()
        command = data.get('command', '').strip()
        
        if not command:
            return jsonify({
                'success': False,
                'message': 'Command is required'
            }), 400
        
        # Check if command exists
        if not command.startswith('/'):
            command = '/' + command
        
        # Process command
        response = chatbot_instance.process_message(
            message=command,
            user_id=current_user.id,
            session_id=data.get('session_id')
        )
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error in command endpoint: {e}")
        return jsonify({
            'success': False,
            'message': f'Error executing command: {str(e)}'
        }), 500

@chatbot_bp.route('/sessions', methods=['GET'])
@login_required
def get_sessions():
    """Get user's chat sessions"""
    try:
        # Get sessions from database
        sessions = ChatSession.query.filter_by(
            user_id=current_user.id
        ).order_by(desc(ChatSession.last_activity)).limit(10).all()
        
        session_list = []
        for session in sessions:
            session_list.append({
                'id': session.id,
                'created_at': session.created_at.isoformat(),
                'last_activity': session.last_activity.isoformat(),
                'message_count': session.message_count
            })
        
        return jsonify({
            'success': True,
            'sessions': session_list
        })
        
    except Exception as e:
        logger.error(f"Error getting sessions: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting sessions: {str(e)}'
        }), 500

@chatbot_bp.route('/session/<session_id>', methods=['GET'])
@login_required
def get_session_history(session_id):
    """Get chat history for a session"""
    try:
        # Verify session belongs to user
        session = ChatSession.query.filter_by(
            id=session_id,
            user_id=current_user.id
        ).first()
        
        if not session:
            return jsonify({
                'success': False,
                'message': 'Session not found'
            }), 404
        
        # Get messages
        messages = ChatMessage.query.filter_by(
            session_id=session_id
        ).order_by(ChatMessage.timestamp).limit(100).all()
        
        message_list = []
        for msg in messages:
            message_list.append({
                'id': msg.id,
                'type': msg.message_type,
                'content': msg.content,
                'timestamp': msg.timestamp.isoformat(),
                'metadata': json.loads(msg.metadata) if msg.metadata else {}
            })
        
        return jsonify({
            'success': True,
            'session': {
                'id': session.id,
                'created_at': session.created_at.isoformat()
            },
            'messages': message_list
        })
        
    except Exception as e:
        logger.error(f"Error getting session history: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting history: {str(e)}'
        }), 500

@chatbot_bp.route('/mcp/status', methods=['GET'])
@login_required
def mcp_status():
    """Get MCP server status"""
    try:
        if current_user.id != 1:
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        if not chatbot_instance or not chatbot_instance.mcp_server:
            return jsonify({
                'success': True,
                'message': 'MCP server not initialized',
                'status': 'not_initialized'
            })
        
        status = chatbot_instance.mcp_server.get_server_info()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting MCP status: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting MCP status: {str(e)}'
        }), 500

@chatbot_bp.route('/mcp/start', methods=['POST'])
@login_required
def mcp_start():
    """Start MCP server"""
    try:
        if current_user.id != 1:
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        data = request.get_json()
        port = data.get('port', 8080)
        
        response = chatbot_instance._handle_start_mcp([str(port)], current_user.id, 'admin_session')
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error starting MCP server: {e}")
        return jsonify({
            'success': False,
            'message': f'Error starting MCP server: {str(e)}'
        }), 500

@chatbot_bp.route('/mcp/stop', methods=['POST'])
@login_required
def mcp_stop():
    """Stop MCP server"""
    try:
        if current_user.id != 1:
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        response = chatbot_instance._handle_stop_mcp([], current_user.id, 'admin_session')
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error stopping MCP server: {e}")
        return jsonify({
            'success': False,
            'message': f'Error stopping MCP server: {str(e)}'
        }), 500

@chatbot_bp.route('/system/status', methods=['GET'])
@login_required
def system_status():
    """Get system status"""
    try:
        if current_user.id != 1:
            return jsonify({
                'success': False,
                'message': 'Admin access required'
            }), 403
        
        status = chatbot_instance._get_system_status()
        return jsonify({
            'success': True,
            'status': status
        })
        
    except Exception as e:
        logger.error(f"Error getting system status: {e}")
        return jsonify({
            'success': False,
            'message': f'Error getting system status: {str(e)}'
        }), 500

@chatbot_bp.route('/admin/chatbot', methods=['GET'])
@login_required
def admin_chatbot_interface():
    """Admin chatbot interface page"""
    if current_user.id != 1:
        return redirect(url_for('home'))
    
    return render_template('admin_chatbot.html', title='AI Chatbot Admin')

# ============================================================================
# INTEGRATION WITH MAIN ROUTES
# ============================================================================

def integrate_with_routes(app):
    """Integrate chatbot with main Flask routes"""
    
    # Add chatbot status to admin dashboard
    original_admin_dashboard = app.view_functions['admin_dashboard']
    
    @app.route("/admin")
    @login_required
    def enhanced_admin_dashboard():
        if current_user.id != 1:
            return redirect(url_for('home'))
        
        # Get original stats
        stats = {
            "total_users": User.query.count(),
            "total_revenue": db.session.query(db.func.sum(Payment.amount)).filter(Payment.status=='COMPLETED').scalar() or 0
        }
        
        # Get health info
        health = {"status": "UNKNOWN", "active_alerts": []}
        status_path = os.path.join(app.root_path, '..', 'logs', 'system_status.json')
        if os.path.exists(status_path):
            try:
                with open(status_path, 'r') as f:
                    health = json.load(f)
            except:
                pass
        
        # Add chatbot status
        chatbot_status = "offline"
        if chatbot_instance:
            chatbot_status = "online"
            if chatbot_instance.mcp_enabled:
                chatbot_status = "online_with_mcp"
        
        health["chatbot"] = {
            "status": chatbot_status,
            "active_sessions": len(chatbot_instance.user_sessions) if chatbot_instance else 0,
            "queued_messages": chatbot_instance.message_queue.qsize() if chatbot_instance else 0
        }
        
        return render_template('admin.html', title='Admin', stats=stats, health=health)
    
    # Replace the original admin dashboard
    app.view_functions['admin_dashboard'] = enhanced_admin_dashboard
# ============================================================================
# MAIN EXECUTION & TESTING
# ============================================================================

if __name__ == "__main__":
    """Test the chatbot system"""
    print("=" * 60)
    print("SCOREPULSE AI CHATBOT & MCP INTEGRATION SYSTEM")
    print("=" * 60)
    
    # 1. Create test chatbot
    test_chatbot = ScorePulseChatbot()

    # 2. API DOCUMENTATION (MUST BE COMMENTED OUT OR IN A STRING)
    """
    API Documentation Examples:

    # Request evaluation
    POST /chatbot/evaluate/request
    {
        "type": "classification",
        "parameters": {
            "model_name": "MatchPredictor",
            "y_true": [...],
            "y_pred": [...]
        }
    }

    # Get results
    GET /chatbot/evaluate/results/{evaluation_id}

    # Quick evaluation
    POST /chatbot/evaluate/quick/classification
    {
        "y_true": [...],
        "y_pred": [...],
        "model_name": "QuickTest"
    }
    """

    # 3. Add actual testing logic if needed
    print("Chatbot instance created successfully.")
    
    # Test basic functionality
    print("\n1. Testing Basic Commands:")
    print("-" * 40)
    
    # Test help command
    response = test_chatbot.process_message("/help", user_id=1, session_id="test_session")
    print(f"Help Command: {response.get('success')}")
    print(f"Commands Count: {response.get('commands_count', 0)}")
    
    # Test status command
    response = test_chatbot.process_message("/status", user_id=1, session_id="test_session")
    print(f"\nStatus Command: {response.get('success')}")
    
    # Test natural language
    print("\n2. Testing Natural Language Processing:")
    print("-" * 40)
    
    test_messages = [
        "Hello!",
        "What's the system status?",
        "Predict match between Liverpool and Manchester City",
        "I have an error with my prediction"
    ]
    
    for msg in test_messages:
        response = test_chatbot.process_message(msg, user_id=1, session_id="test_session")
        print(f"\nQuery: {msg}")
        print(f"Intent: {response.get('intent')}")
        print(f"Response: {response.get('message', '')[:50]}...")
    
    # Test MCP server
    print("\n3. Testing MCP Server Integration:")
    print("-" * 40)
    
    # Start MCP server
    response = test_chatbot._handle_start_mcp(["8080"], user_id=1, session_id="test_session")
    print(f"Start MCP: {response.get('success')}")
    print(f"Message: {response.get('message')}")
    
    if response.get('success'):
        # Check MCP status
        time.sleep(1)  # Give server time to start
        response = test_chatbot._handle_mcp_status([], user_id=1, session_id="test_session")
        print(f"\nMCP Status: {response.get('message', '')[:100]}...")
        
        # Stop MCP server
        response = test_chatbot._handle_stop_mcp([], user_id=1, session_id="test_session")
        print(f"\nStop MCP: {response.get('success')}")
        print(f"Message: {response.get('message')}")
    
    print("\n" + "=" * 60)
    print("TEST COMPLETE")
    print("=" * 60)
    
    
# ============================================================================
# BANKROLL STRATEGY AGENT (SISTER AGENT)
# ============================================================================

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
        import random
        
        # Base odds with some randomness
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