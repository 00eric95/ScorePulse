"""
FILE: validate_predictions.py
DESCRIPTION: Prediction Validation & Financial Performance Auditor.
This script serves as the "Judge" for the ScorePulse AI system. It cross-references 
AI-generated predictions stored in the database with actual match outcomes found in 
the admin-uploaded results.csv. It calculates critical KPIs including ROI (Return on 
Investment), Win/Loss ratios, and bankroll efficiency using the Bankroll class logic.
"""

import pandas as pd
import numpy as np
import json
import os
import time
import warnings
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Any
import logging
from sqlalchemy import create_engine, text, MetaData, Table, select
from sqlalchemy.orm import sessionmaker
import mysql.connector
import sys
from sklearn.metrics import accuracy_score, precision_score, recall_score, f1_score
from sklearn.metrics import confusion_matrix, classification_report, roc_auc_score
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from plotly.subplots import make_subplots

warnings.filterwarnings('ignore')

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/validation.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class DatabasePredictionValidator:
    """Validates user predictions from database against admin-uploaded results.csv."""
    
    def __init__(self, 
                 db_config: Dict = None,
                 results_file: str = 'data/results.csv',
                 validation_output_dir: str = 'validation_reports'):
        """
        Initialize the validator with database connection.
        
        Args:
            db_config: Database configuration dictionary
            results_file: Admin-uploaded results CSV
            validation_output_dir: Directory for output reports
        """
        self.results_file = Path(results_file)
        self.validation_dir = Path(validation_output_dir)
        self.validation_dir.mkdir(exist_ok=True, parents=True)
        
        # Database configuration
        self.db_config = db_config or self.load_default_db_config()
        self.engine = None
        self.Session = None
        
        # Performance tracking
        self.performance_history = []
        self.model_performance = {}
        
        # Betting parameters
        self.betting_parameters = {
            'stake_per_bet': 100.0,
            'bankroll': 10000.0,
            'min_odds': 1.50,
            'max_odds': 10.00,
            'value_threshold': 1.05,
        }
        
        # Thresholds for retraining
        self.retraining_thresholds = {
            'accuracy_drop': 0.10,
            'roi_drop': -5.0,
            'consecutive_losses': 5,
            'min_predictions': 20,
            'confidence_threshold': 0.65,
        }
        
        logger.info(f"DatabasePredictionValidator initialized")
        logger.info(f"Results file: {self.results_file}")
    
    def load_default_db_config(self) -> Dict:
        """Load default database configuration."""
        return {
            'host': 'localhost',
            'database': 'soccer_ai',
            'user': 'root',
            'password': '',
            'port': 3306
        }
    
    def connect_to_database(self) -> bool:
        """Establish database connection."""
        try:
            # Create SQLAlchemy engine
            connection_string = f"mysql+mysqlconnector://{self.db_config['user']}:{self.db_config['password']}@{self.db_config['host']}:{self.db_config['port']}/{self.db_config['database']}"
            self.engine = create_engine(connection_string)
            
            # Test connection
            with self.engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            
            # Create session factory
            self.Session = sessionmaker(bind=self.engine)
            
            logger.info(f"Connected to database: {self.db_config['database']}")
            return True
            
        except Exception as e:
            logger.error(f"Database connection failed: {str(e)}")
            
            # Try direct MySQL connection as fallback
            try:
                self.conn = mysql.connector.connect(
                    host=self.db_config['host'],
                    user=self.db_config['user'],
                    password=self.db_config['password'],
                    database=self.db_config['database']
                )
                logger.info("Connected via mysql.connector")
                return True
            except Exception as e2:
                logger.error(f"Fallback connection also failed: {str(e2)}")
                return False
    
    def get_user_predictions_from_db(self, user_id: Optional[int] = None) -> pd.DataFrame:
        """
        Fetch user predictions from database.
        
        Args:
            user_id: Specific user ID, or None for all users
            
        Returns:
            DataFrame with user predictions
        """
        try:
            if self.engine:
                # Using SQLAlchemy with ORM-style query
                if user_id:
                    query = text("""
                        SELECT 
                            p.id,
                            p.user_id,
                            p.match_date,
                            p.home_team,
                            p.away_team,
                            p.prediction as ai_prediction,
                            p.confidence as ai_confidence,
                            p.pred_outcome,
                            p.created_at,
                            u.username,
                            u.email,
                            m.home_score,
                            m.away_score,
                            m.league,
                            m.country
                        FROM predictions p
                        JOIN users u ON p.user_id = u.id
                        LEFT JOIN matches m ON p.match_id = m.id
                        WHERE p.user_id = :user_id
                        ORDER BY p.match_date DESC
                    """)
                    with self.engine.connect() as conn:
                        result = conn.execute(query, {'user_id': user_id})
                        df = pd.DataFrame(result.fetchall(), columns=result.keys())
                else:
                    # Get all predictions from all users
                    query = text("""
                        SELECT 
                            p.id,
                            p.user_id,
                            p.match_date,
                            p.home_team,
                            p.away_team,
                            p.prediction as ai_prediction,
                            p.confidence as ai_confidence,
                            p.pred_outcome,
                            p.created_at,
                            u.username,
                            u.email,
                            m.home_score,
                            m.away_score,
                            m.league,
                            m.country
                        FROM predictions p
                        JOIN users u ON p.user_id = u.id
                        LEFT JOIN matches m ON p.match_id = m.id
                        WHERE m.match_date IS NOT NULL
                        ORDER BY p.match_date DESC
                    """)
                    with self.engine.connect() as conn:
                        result = conn.execute(query)
                        df = pd.DataFrame(result.fetchall(), columns=result.keys())
            else:
                # Using direct MySQL connection
                if user_id:
                    query = f"""
                        SELECT 
                            p.id,
                            p.user_id,
                            p.match_date,
                            p.home_team,
                            p.away_team,
                            p.prediction as ai_prediction,
                            p.confidence as ai_confidence,
                            p.pred_outcome,
                            p.created_at,
                            u.username,
                            u.email,
                            m.home_score,
                            m.away_score,
                            m.league,
                            m.country
                        FROM predictions p
                        JOIN users u ON p.user_id = u.id
                        LEFT JOIN matches m ON p.match_id = m.id
                        WHERE p.user_id = {user_id}
                        ORDER BY p.match_date DESC
                    """
                else:
                    query = """
                        SELECT 
                            p.id,
                            p.user_id,
                            p.match_date,
                            p.home_team,
                            p.away_team,
                            p.prediction as ai_prediction,
                            p.confidence as ai_confidence,
                            p.pred_outcome,
                            p.created_at,
                            u.username,
                            u.email,
                            m.home_score,
                            m.away_score,
                            m.league,
                            m.country
                        FROM predictions p
                        JOIN users u ON p.user_id = u.id
                        LEFT JOIN matches m ON p.match_id = m.id
                        WHERE m.match_date IS NOT NULL
                        ORDER BY p.match_date DESC
                    """
                
                df = pd.read_sql(query, self.conn)
            
            logger.info(f"Retrieved {len(df)} predictions from database")
            
            # Convert date columns
            if 'match_date' in df.columns:
                df['match_date'] = pd.to_datetime(df['match_date'])
            if 'created_at' in df.columns:
                df['created_at'] = pd.to_datetime(df['created_at'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error fetching predictions from database: {str(e)}")
            import traceback
            logger.error(traceback.format_exc())
            
            # Return empty DataFrame as fallback
            return pd.DataFrame()
    
    def load_admin_results(self) -> pd.DataFrame:
        """Load admin-uploaded results.csv file."""
        try:
            if not self.results_file.exists():
                logger.error(f"Results file not found: {self.results_file}")
                return pd.DataFrame()
            
            df = pd.read_csv(self.results_file)
            logger.info(f"Loaded {len(df)} results from {self.results_file}")
            
            # Standardize column names
            df = self.standardize_results_columns(df)
            
            # Convert date column
            if 'Date' in df.columns:
                df['Date'] = pd.to_datetime(df['Date'], errors='coerce')
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading results file: {str(e)}")
            return pd.DataFrame()
    
    def standardize_results_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Standardize results.csv column names."""
        df = df.copy()
        
        # Column mappings
        column_mappings = {
            # Date columns
            'date': 'Date', 'Date': 'Date', 'MatchDate': 'Date', 'match_date': 'Date',
            
            # Team columns
            'Home': 'HomeTeam', 'home': 'HomeTeam', 'Home Team': 'HomeTeam',
            'Away': 'AwayTeam', 'away': 'AwayTeam', 'Away Team': 'AwayTeam',
            'HomeTeam': 'HomeTeam', 'AwayTeam': 'AwayTeam',
            
            # Score columns
            'FTHG': 'HomeScore', 'HomeGoals': 'HomeScore', 'home_score': 'HomeScore',
            'FTAG': 'AwayScore', 'AwayGoals': 'AwayScore', 'away_score': 'AwayScore',
            'HG': 'HomeScore', 'AG': 'AwayScore',
            
            # Result columns
            'FTR': 'Result', 'Result': 'Result', 'FT Result': 'Result',
            'Outcome': 'Result', 'WDL': 'Result', 'wdl': 'Result',
            
            # Odds columns (if provided)
            'B365H': 'HomeOdds', 'AvgH': 'HomeOdds', 'home_odds': 'HomeOdds',
            'B365D': 'DrawOdds', 'AvgD': 'DrawOdds', 'draw_odds': 'DrawOdds',
            'B365A': 'AwayOdds', 'AvgA': 'AwayOdds', 'away_odds': 'AwayOdds',
            'PSH': 'HomeOdds', 'PSD': 'DrawOdds', 'PSA': 'AwayOdds',
        }
        
        # Rename columns
        for old_col, new_col in column_mappings.items():
            if old_col in df.columns and new_col not in df.columns:
                df[new_col] = df[old_col]
        
        return df
    
    def merge_predictions_with_results(self, predictions_df: pd.DataFrame, results_df: pd.DataFrame) -> pd.DataFrame:
        """Merge user predictions with admin results."""
        if predictions_df.empty or results_df.empty:
            logger.warning("Cannot merge: empty predictions or results")
            return pd.DataFrame()
        
        # Create copies
        pred_df = predictions_df.copy()
        res_df = results_df.copy()
        
        # Standardize team names (remove extra spaces, convert to lowercase for matching)
        for df in [pred_df, res_df]:
            if 'home_team' in df.columns:
                df['home_team_clean'] = df['home_team'].astype(str).str.strip().str.lower()
            if 'away_team' in df.columns:
                df['away_team_clean'] = df['away_team'].astype(str).str.strip().str.lower()
            if 'HomeTeam' in df.columns:
                df['home_team_clean'] = df['HomeTeam'].astype(str).str.strip().str.lower()
            if 'AwayTeam' in df.columns:
                df['away_team_clean'] = df['AwayTeam'].astype(str).str.strip().str.lower()
        
        # Merge on date and teams
        merged_df = pd.merge(
            pred_df,
            res_df,
            left_on=['match_date', 'home_team_clean', 'away_team_clean'],
            right_on=['Date', 'home_team_clean', 'away_team_clean'],
            how='inner',
            suffixes=('_pred', '_result')
        )
        
        if merged_df.empty:
            logger.warning("No matching records found between predictions and results")
            return pd.DataFrame()
        
        logger.info(f"Merged {len(merged_df)} predictions with results")
        return merged_df
    
    def calculate_actual_result(self, home_score: Any, away_score: Any) -> Optional[str]:
        """Calculate actual result from scores."""
        try:
            if pd.isna(home_score) or pd.isna(away_score):
                return None
            
            home = float(home_score)
            away = float(away_score)
            
            if home > away:
                return 'H'
            elif away > home:
                return 'A'
            else:
                return 'D'
        except:
            return None
    
    def clean_prediction(self, pred: Any) -> Optional[str]:
        """Clean prediction to standard format (H, D, A)."""
        if pd.isna(pred):
            return None
        
        pred_str = str(pred).upper().strip()
        
        # Handle various formats
        if pred_str in ['H', 'HOME', '1', 'HW', 'HOME WIN', 'H WIN']:
            return 'H'
        elif pred_str in ['A', 'AWAY', '2', 'AW', 'AWAY WIN', 'A WIN']:
            return 'A'
        elif pred_str in ['D', 'DRAW', 'X', 'DR', 'DRAW WIN']:
            return 'D'
        elif len(pred_str) == 1 and pred_str in ['H', 'D', 'A']:
            return pred_str
        else:
            # Try to extract from text
            if 'HOME' in pred_str or 'H ' in pred_str:
                return 'H'
            elif 'AWAY' in pred_str or 'A ' in pred_str:
                return 'A'
            elif 'DRAW' in pred_str or 'D ' in pred_str:
                return 'D'
        
        return None
    
    def prepare_validation_data(self, merged_df: pd.DataFrame) -> pd.DataFrame:
        """Prepare merged data for validation analysis."""
        df = merged_df.copy()
        
        # Calculate actual result from scores
        if 'HomeScore' in df.columns and 'AwayScore' in df.columns:
            df['Actual_Result'] = df.apply(
                lambda x: self.calculate_actual_result(x['HomeScore'], x['AwayScore']),
                axis=1
            )
        elif 'Result' in df.columns:
            df['Actual_Result'] = df['Result'].apply(self.clean_prediction)
        
        # Clean AI predictions
        if 'ai_prediction' in df.columns:
            df['Clean_AI_Prediction'] = df['ai_prediction'].apply(self.clean_prediction)
        elif 'pred_outcome' in df.columns:
            df['Clean_AI_Prediction'] = df['pred_outcome'].apply(self.clean_prediction)
        
        # Calculate prediction outcome
        if 'Clean_AI_Prediction' in df.columns and 'Actual_Result' in df.columns:
            df['Prediction_Outcome'] = df.apply(
                lambda x: 'Correct' if x['Clean_AI_Prediction'] == x['Actual_Result'] else 'Incorrect',
                axis=1
            )
            df['Prediction_Correct'] = df['Prediction_Outcome'] == 'Correct'
        
        # Calculate confidence if available
        if 'ai_confidence' in df.columns:
            df['Confidence'] = pd.to_numeric(df['ai_confidence'], errors='coerce')
        
        # Add match identifier
        df['Match_ID'] = df.apply(
            lambda x: f"{x['home_team']}_{x['away_team']}_{x['match_date']}", 
            axis=1
        )
        
        logger.info(f"Prepared {len(df)} matches for validation")
        return df
    
    def calculate_user_performance(self, df: pd.DataFrame, user_id: Optional[int] = None) -> Dict:
        """Calculate performance metrics for a specific user or all users."""
        if df.empty:
            return {}
        
        # Filter by user if specified
        if user_id and 'user_id' in df.columns:
            user_df = df[df['user_id'] == user_id].copy()
            user_info = f"user_id={user_id}"
        else:
            user_df = df.copy()
            user_info = "all users"
        
        if user_df.empty:
            logger.warning(f"No data for {user_info}")
            return {}
        
        # Filter to matches with predictions and actual results
        valid_df = user_df[
            user_df['Clean_AI_Prediction'].notna() & 
            user_df['Actual_Result'].notna()
        ].copy()
        
        if valid_df.empty:
            logger.warning(f"No valid predictions for {user_info}")
            return {}
        
        # Basic metrics
        total_matches = len(valid_df)
        correct_predictions = len(valid_df[valid_df['Prediction_Outcome'] == 'Correct'])
        
        metrics = {
            'user_info': user_info,
            'total_matches': total_matches,
            'correct_predictions': correct_predictions,
            'accuracy': round((correct_predictions / total_matches) * 100, 2) if total_matches > 0 else 0,
            'accuracy_raw': correct_predictions / total_matches if total_matches > 0 else 0,
        }
        
        # Detailed metrics by prediction type
        detailed_metrics = {}
        for pred_type in ['H', 'D', 'A']:
            type_df = valid_df[valid_df['Clean_AI_Prediction'] == pred_type]
            if len(type_df) > 0:
                type_correct = len(type_df[type_df['Actual_Result'] == pred_type])
                type_accuracy = (type_correct / len(type_df)) * 100 if len(type_df) > 0 else 0
                
                detailed_metrics[f'{pred_type}_predictions'] = {
                    'count': len(type_df),
                    'correct': type_correct,
                    'accuracy': round(type_accuracy, 2),
                    'frequency': round((len(type_df) / total_matches) * 100, 2) if total_matches > 0 else 0
                }
        
        metrics['detailed'] = detailed_metrics
        
        # Sklearn metrics
        try:
            y_true = valid_df['Actual_Result'].values
            y_pred = valid_df['Clean_AI_Prediction'].values
            
            metrics['precision'] = round(precision_score(y_true, y_pred, average='weighted', zero_division=0), 4)
            metrics['recall'] = round(recall_score(y_true, y_pred, average='weighted', zero_division=0), 4)
            metrics['f1_score'] = round(f1_score(y_true, y_pred, average='weighted', zero_division=0), 4)
            
            # Confusion matrix
            cm = confusion_matrix(y_true, y_pred, labels=['H', 'D', 'A'])
            metrics['confusion_matrix'] = cm.tolist()
            
        except Exception as e:
            logger.warning(f"Could not calculate sklearn metrics: {str(e)}")
            metrics['precision'] = 0
            metrics['recall'] = 0
            metrics['f1_score'] = 0
            metrics['confusion_matrix'] = []
        
        # Betting performance metrics (if odds available)
        if any(col in valid_df.columns for col in ['HomeOdds', 'DrawOdds', 'AwayOdds']):
            betting_metrics = self.calculate_betting_performance(valid_df)
            metrics['betting'] = betting_metrics
        
        # Confidence analysis
        if 'Confidence' in valid_df.columns:
            confidence_metrics = self.analyze_confidence(valid_df)
            metrics['confidence'] = confidence_metrics
        
        # Performance by league
        if 'league' in valid_df.columns:
            league_metrics = {}
            for league in valid_df['league'].unique():
                league_df = valid_df[valid_df['league'] == league]
                if len(league_df) >= 3:
                    league_correct = len(league_df[league_df['Prediction_Outcome'] == 'Correct'])
                    league_accuracy = (league_correct / len(league_df)) * 100 if len(league_df) > 0 else 0
                    league_metrics[league] = {
                        'count': len(league_df),
                        'accuracy': round(league_accuracy, 2),
                        'correct': league_correct
                    }
            metrics['league_performance'] = league_metrics
        
        # Performance over time
        if 'match_date' in valid_df.columns:
            trend_metrics = self.analyze_performance_trends(valid_df)
            metrics['trends'] = trend_metrics
        
        return metrics
    
    def calculate_betting_performance(self, df: pd.DataFrame) -> Dict:
        """Calculate betting performance with various strategies."""
        results = {
            'flat_betting': {'profit': 0, 'roi': 0, 'bets': 0, 'wins': 0, 'win_rate': 0},
            'confidence_betting': {'profit': 0, 'roi': 0, 'bets': 0, 'wins': 0, 'win_rate': 0},
            'value_betting': {'profit': 0, 'roi': 0, 'bets': 0, 'wins': 0, 'win_rate': 0},
            'overall': {'profit': 0, 'roi': 0, 'bets': 0, 'wins': 0, 'win_rate': 0, 'strategy': 'flat_betting'}
        }
        
        stake = self.betting_parameters['stake_per_bet']
        min_odds = self.betting_parameters['min_odds']
        max_odds = self.betting_parameters['max_odds']
        value_threshold = self.betting_parameters['value_threshold']
        
        for _, row in df.iterrows():
            pred = row.get('Clean_AI_Prediction')
            actual = row.get('Actual_Result')
            
            if not pred or not actual:
                continue
            
            # Determine which odds to use based on prediction
            if pred == 'H' and 'HomeOdds' in row:
                odds = row.get('HomeOdds')
            elif pred == 'D' and 'DrawOdds' in row:
                odds = row.get('DrawOdds')
            elif pred == 'A' and 'AwayOdds' in row:
                odds = row.get('AwayOdds')
            else:
                continue
            
            # Skip if odds are invalid
            if pd.isna(odds) or odds < min_odds or odds > max_odds:
                continue
            
            # Convert odds to float
            try:
                odds = float(odds)
            except:
                continue
            
            # Strategy 1: Flat betting (bet on all predictions)
            results['flat_betting']['bets'] += 1
            if pred == actual:
                results['flat_betting']['profit'] += (odds - 1) * stake
                results['flat_betting']['wins'] += 1
            else:
                results['flat_betting']['profit'] -= stake
            
            # Strategy 2: Confidence-based betting
            confidence = row.get('Confidence')
            if confidence is not None and confidence > self.retraining_thresholds['confidence_threshold']:
                results['confidence_betting']['bets'] += 1
                if pred == actual:
                    results['confidence_betting']['profit'] += (odds - 1) * stake
                    results['confidence_betting']['wins'] += 1
                else:
                    results['confidence_betting']['profit'] -= stake
            
            # Strategy 3: Value betting
            if confidence is not None:
                # Convert confidence to probability (assuming 0-100 scale)
                confidence_prob = confidence / 100 if confidence > 1 else confidence
                value = confidence_prob * odds
                
                if value > value_threshold:
                    results['value_betting']['bets'] += 1
                    if pred == actual:
                        results['value_betting']['profit'] += (odds - 1) * stake
                        results['value_betting']['wins'] += 1
                    else:
                        results['value_betting']['profit'] -= stake
        
        # Calculate ROI and win rates
        for strategy in ['flat_betting', 'confidence_betting', 'value_betting']:
            if results[strategy]['bets'] > 0:
                total_staked = results[strategy]['bets'] * stake
                results[strategy]['roi'] = round((results[strategy]['profit'] / total_staked) * 100, 2)
                results[strategy]['profit'] = round(results[strategy]['profit'], 2)
                results[strategy]['win_rate'] = round((results[strategy]['wins'] / results[strategy]['bets']) * 100, 2)
        
        # Determine best strategy
        strategies = ['flat_betting', 'confidence_betting', 'value_betting']
        valid_strategies = [s for s in strategies if results[s]['bets'] > 0]
        
        if valid_strategies:
            best_strategy = max(valid_strategies, key=lambda x: results[x]['profit'])
            results['overall'] = results[best_strategy].copy()
            results['overall']['strategy'] = best_strategy
        
        return results
    
    def analyze_confidence(self, df: pd.DataFrame) -> Dict:
        """Analyze prediction confidence vs accuracy."""
        if 'Confidence' not in df.columns:
            return {}
        
        valid_df = df[df['Confidence'].notna()].copy()
        
        # Bin confidence levels
        bins = [0, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
        labels = ['<50%', '50-60%', '60-70%', '70-80%', '80-90%', '>90%']
        
        valid_df['Confidence_Bin'] = pd.cut(
            valid_df['Confidence'], 
            bins=bins, 
            labels=labels,
            include_lowest=True
        )
        
        # Calculate accuracy per confidence bin
        confidence_analysis = {}
        for bin_label in labels:
            bin_df = valid_df[valid_df['Confidence_Bin'] == bin_label]
            if len(bin_df) > 0:
                accuracy = (len(bin_df[bin_df['Prediction_Correct']]) / len(bin_df)) * 100
                confidence_analysis[bin_label] = {
                    'count': len(bin_df),
                    'accuracy': round(accuracy, 2),
                    'avg_confidence': round(bin_df['Confidence'].mean(), 2)
                }
        
        # Overall calibration
        avg_confidence = valid_df['Confidence'].mean()
        actual_accuracy = (len(valid_df[valid_df['Prediction_Correct']]) / len(valid_df)) * 100
        
        return {
            'bins': confidence_analysis,
            'calibration': {
                'avg_confidence': round(avg_confidence, 2),
                'actual_accuracy': round(actual_accuracy, 2),
                'calibration_error': round(abs(avg_confidence - actual_accuracy), 2)
            }
        }
    
    def analyze_performance_trends(self, df: pd.DataFrame) -> Dict:
        """Analyze performance trends over time."""
        try:
            df['match_date'] = pd.to_datetime(df['match_date'])
            df['Week'] = df['match_date'].dt.isocalendar().week
            df['Month'] = df['match_date'].dt.to_period('M')
            
            # Weekly performance
            weekly_performance = {}
            for week in sorted(df['Week'].unique()):
                week_df = df[df['Week'] == week]
                if len(week_df) >= 3:
                    accuracy = (len(week_df[week_df['Prediction_Correct']]) / len(week_df)) * 100
                    weekly_performance[f'Week_{week}'] = {
                        'accuracy': round(accuracy, 2),
                        'matches': len(week_df)
                    }
            
            # Monthly performance
            monthly_performance = {}
            for month in sorted(df['Month'].unique()):
                month_df = df[df['Month'] == month]
                if len(month_df) >= 5:
                    accuracy = (len(month_df[month_df['Prediction_Correct']]) / len(month_df)) * 100
                    monthly_performance[str(month)] = {
                        'accuracy': round(accuracy, 2),
                        'matches': len(month_df)
                    }
            
            return {
                'weekly': weekly_performance,
                'monthly': monthly_performance
            }
            
        except Exception as e:
            logger.warning(f"Error analyzing trends: {str(e)}")
            return {}
    
    def check_retraining_need(self, metrics: Dict) -> Dict:
        """Check if model retraining is needed."""
        retraining_info = {
            'needed': False,
            'priority': 'low',
            'reasons': [],
            'suggested_actions': []
        }
        
        accuracy = metrics.get('accuracy_raw', 0)
        betting = metrics.get('betting', {}).get('overall', {})
        
        # Check accuracy thresholds
        if accuracy < 0.45:
            retraining_info['needed'] = True
            retraining_info['priority'] = 'high' if accuracy < 0.40 else 'medium'
            retraining_info['reasons'].append(f"Low accuracy: {accuracy:.2%}")
        
        # Check betting performance
        roi = betting.get('roi', 0)
        if roi < -10:
            retraining_info['needed'] = True
            retraining_info['priority'] = 'high'
            retraining_info['reasons'].append(f"Poor ROI: {roi}%")
        
        # Check specific prediction types
        detailed = metrics.get('detailed', {})
        for pred_type in ['H', 'D', 'A']:
            if f'{pred_type}_predictions' in detailed:
                type_data = detailed[f'{pred_type}_predictions']
                if type_data['count'] >= 10 and type_data['accuracy'] < 30:
                    retraining_info['needed'] = True
                    retraining_info['reasons'].append(f"Poor {pred_type} prediction accuracy: {type_data['accuracy']}%")
        
        # Generate actions if retraining needed
        if retraining_info['needed']:
            if retraining_info['priority'] == 'high':
                retraining_info['suggested_actions'] = [
                    "Immediate retraining with latest data",
                    "Review feature engineering",
                    "Add recent match data from past 3 months",
                    "Consider trying different algorithms"
                ]
            else:
                retraining_info['suggested_actions'] = [
                    "Schedule retraining this week",
                    "Collect more recent match data",
                    "Analyze specific failure cases"
                ]
        
        return retraining_info
    
    def generate_visualizations(self, df: pd.DataFrame, metrics: Dict, user_id: Optional[int] = None):
        """Generate interactive charts and graphs."""
        viz_dir = self.validation_dir
        if user_id:
            viz_dir = viz_dir / f"user_{user_id}"
        viz_dir.mkdir(exist_ok=True, parents=True)
        
        timestamp = datetime.now().strftime("%Y%m%d")
        
        try:
            # 1. Accuracy Trend Chart
            if 'match_date' in df.columns:
                df_sorted = df.sort_values('match_date')
                df_sorted['Cumulative_Accuracy'] = df_sorted['Prediction_Correct'].expanding().mean()
                
                fig = go.Figure()
                fig.add_trace(go.Scatter(
                    x=df_sorted['match_date'],
                    y=df_sorted['Cumulative_Accuracy'] * 100,
                    mode='lines+markers',
                    name='Cumulative Accuracy',
                    line=dict(color='#00ff88', width=3)
                ))
                
                fig.update_layout(
                    title='Prediction Accuracy Over Time',
                    xaxis_title='Date',
                    yaxis_title='Accuracy (%)',
                    template='plotly_dark'
                )
                
                fig.write_html(viz_dir / f"accuracy_trend_{timestamp}.html")
            
            # 2. Confusion Matrix Heatmap
            cm = metrics.get('confusion_matrix', [])
            if cm:
                labels = ['Home Win', 'Draw', 'Away Win']
                fig = go.Figure(data=go.Heatmap(
                    z=cm,
                    x=labels,
                    y=labels,
                    colorscale='Viridis'
                ))
                
                fig.update_layout(
                    title='Confusion Matrix',
                    xaxis_title='Predicted',
                    yaxis_title='Actual',
                    template='plotly_dark'
                )
                
                fig.write_html(viz_dir / f"confusion_matrix_{timestamp}.html")
            
            # 3. Prediction Distribution
            pred_counts = df['Clean_AI_Prediction'].value_counts()
            if not pred_counts.empty:
                colors = {'H': '#00ff88', 'D': '#0088ff', 'A': '#ff8800'}
                
                fig = go.Figure(data=[go.Pie(
                    labels=[f'Home ({pred_counts.get("H", 0)})', 
                           f'Draw ({pred_counts.get("D", 0)})', 
                           f'Away ({pred_counts.get("A", 0)})'],
                    values=[pred_counts.get('H', 0), pred_counts.get('D', 0), pred_counts.get('A', 0)],
                    marker=dict(colors=[colors['H'], colors['D'], colors['A']]),
                    hole=0.3
                )])
                
                fig.update_layout(
                    title='Prediction Distribution',
                    template='plotly_dark'
                )
                
                fig.write_html(viz_dir / f"prediction_distribution_{timestamp}.html")
            
            # 4. Performance Dashboard
            self.generate_performance_dashboard(df, metrics, viz_dir, timestamp)
            
            logger.info(f"Visualizations saved to {viz_dir}")
            
        except Exception as e:
            logger.error(f"Error generating visualizations: {str(e)}")
    
    def generate_performance_dashboard(self, df: pd.DataFrame, metrics: Dict, viz_dir: Path, timestamp: str):
        """Generate comprehensive performance dashboard."""
        try:
            fig = make_subplots(
                rows=2, cols=2,
                subplot_titles=('Accuracy by Prediction Type', 'Performance by League',
                              'Confidence Calibration', 'ROI by Strategy'),
                specs=[[{'type': 'bar'}, {'type': 'bar'}],
                       [{'type': 'scatter'}, {'type': 'bar'}]],
                vertical_spacing=0.15
            )
            
            # 1. Accuracy by Prediction Type
            detailed = metrics.get('detailed', {})
            if detailed:
                pred_types = ['H', 'D', 'A']
                accuracies = [detailed.get(f'{pt}_predictions', {}).get('accuracy', 0) for pt in pred_types]
                
                fig.add_trace(
                    go.Bar(
                        x=['Home', 'Draw', 'Away'],
                        y=accuracies,
                        marker_color=['#00ff88', '#0088ff', '#ff8800'],
                        name='Accuracy'
                    ),
                    row=1, col=1
                )
            
            # 2. Performance by League
            league_perf = metrics.get('league_performance', {})
            if league_perf:
                leagues = list(league_perf.keys())
                league_acc = [league_perf[l]['accuracy'] for l in leagues]
                
                fig.add_trace(
                    go.Bar(
                        x=leagues,
                        y=league_acc,
                        name='League Accuracy'
                    ),
                    row=1, col=2
                )
            
            # 3. Confidence Calibration
            confidence = metrics.get('confidence', {}).get('bins', {})
            if confidence:
                bins = list(confidence.keys())
                accuracies = [confidence[b]['accuracy'] for b in bins]
                confidences = [confidence[b]['avg_confidence'] for b in bins]
                
                fig.add_trace(
                    go.Scatter(
                        x=bins,
                        y=accuracies,
                        mode='lines+markers',
                        name='Actual Accuracy',
                        line=dict(color='#00ff88', width=3)
                    ),
                    row=2, col=1
                )
                
                fig.add_trace(
                    go.Scatter(
                        x=bins,
                        y=confidences,
                        mode='lines+markers',
                        name='Average Confidence',
                        line=dict(color='#ff8800', width=3)
                    ),
                    row=2, col=1
                )
            
            # 4. ROI by Strategy
            betting = metrics.get('betting', {})
            if betting:
                strategies = ['Flat', 'Confidence', 'Value']
                roi_values = [
                    betting.get('flat_betting', {}).get('roi', 0),
                    betting.get('confidence_betting', {}).get('roi', 0),
                    betting.get('value_betting', {}).get('roi', 0)
                ]
                
                colors = ['green' if roi >= 0 else 'red' for roi in roi_values]
                
                fig.add_trace(
                    go.Bar(
                        x=strategies,
                        y=roi_values,
                        marker_color=colors,
                        name='ROI'
                    ),
                    row=2, col=2
                )
            
            fig.update_layout(
                title_text='AI Model Performance Dashboard',
                template='plotly_dark',
                height=800
            )
            
            fig.write_html(viz_dir / f"performance_dashboard_{timestamp}.html")
            
        except Exception as e:
            logger.error(f"Error generating dashboard: {str(e)}")
    
    def generate_report(self, df: pd.DataFrame, metrics: Dict, user_id: Optional[int] = None) -> Dict:
        """Generate comprehensive validation report."""
        report = {
            'report_id': f"VAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'timestamp': datetime.now().isoformat(),
            'user_id': user_id,
            'data_summary': {
                'total_predictions': len(df),
                'validated_predictions': len(df[df['Actual_Result'].notna()]),
                'date_range': {
                    'start': df['match_date'].min().strftime('%Y-%m-%d') if 'match_date' in df.columns else 'Unknown',
                    'end': df['match_date'].max().strftime('%Y-%m-%d') if 'match_date' in df.columns else 'Unknown'
                }
            },
            'performance_metrics': metrics,
            'retraining_analysis': self.check_retraining_need(metrics),
            'recommendations': [],
            'visualizations': {}
        }
        
        # Generate recommendations
        accuracy = metrics.get('accuracy', 0)
        if accuracy < 50:
            report['recommendations'].append(f"Accuracy is {accuracy}%. Consider reviewing prediction strategy.")
        elif accuracy > 65:
            report['recommendations'].append(f"Excellent accuracy: {accuracy}%.")
        
        betting = metrics.get('betting', {}).get('overall', {})
        if betting:
            roi = betting.get('roi', 0)
            if roi > 10:
                report['recommendations'].append(f"Strong positive ROI: {roi}%. Consider increasing stakes.")
            elif roi < -5:
                report['recommendations'].append(f"Negative ROI: {roi}%. Review betting strategy.")
        
        return report
    
    def save_report(self, report: Dict, user_id: Optional[int] = None):
        """Save validation report to file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        if user_id:
            user_dir = self.validation_dir / f"user_{user_id}"
            user_dir.mkdir(exist_ok=True, parents=True)
            report_file = user_dir / f"validation_report_{timestamp}.json"
        else:
            report_file = self.validation_dir / f"model_report_{timestamp}.json"
        
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Save as latest report
        if user_id:
            latest_file = user_dir / "latest_validation_report.json"
        else:
            latest_file = self.validation_dir / "latest_model_report.json"
        
        with open(latest_file, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        logger.info(f"Validation report saved: {report_file}")
        
        # Update performance history
        self.performance_history.append(report)
        if len(self.performance_history) > 50:
            self.performance_history = self.performance_history[-50:]
    
    def validate_user_predictions(self, user_id: int):
        """Validate predictions for a specific user."""
        logger.info(f"Validating predictions for user_id: {user_id}")
        
        # Connect to database
        if not self.connect_to_database():
            logger.error("Cannot connect to database")
            return None
        
        # Load user predictions from database
        predictions_df = self.get_user_predictions_from_db(user_id)
        if predictions_df.empty:
            logger.warning(f"No predictions found for user_id: {user_id}")
            return None
        
        # Load admin results
        results_df = self.load_admin_results()
        if results_df.empty:
            logger.error("No results file found or empty results")
            return None
        
        # Merge predictions with results
        merged_df = self.merge_predictions_with_results(predictions_df, results_df)
        if merged_df.empty:
            logger.warning("No matching predictions with results")
            return None
        
        # Prepare validation data
        validation_df = self.prepare_validation_data(merged_df)
        
        # Calculate performance metrics
        metrics = self.calculate_user_performance(validation_df, user_id)
        
        # Generate visualizations
        self.generate_visualizations(validation_df, metrics, user_id)
        
        # Generate report
        report = self.generate_report(validation_df, metrics, user_id)
        
        # Save report
        self.save_report(report, user_id)
        
        # Display summary
        self.display_summary(report, user_id)
        
        return report
    
    def validate_all_users(self):
        """Validate predictions for all users (model evaluation)."""
        logger.info("Validating predictions for all users")
        
        # Connect to database
        if not self.connect_to_database():
            logger.error("Cannot connect to database")
            return None
        
        # Load all predictions
        predictions_df = self.get_user_predictions_from_db()
        if predictions_df.empty:
            logger.warning("No predictions found in database")
            return None
        
        # Load admin results
        results_df = self.load_admin_results()
        if results_df.empty:
            logger.error("No results file found")
            return None
        
        # Merge predictions with results
        merged_df = self.merge_predictions_with_results(predictions_df, results_df)
        if merged_df.empty:
            logger.warning("No matching predictions with results")
            return None
        
        # Prepare validation data
        validation_df = self.prepare_validation_data(merged_df)
        
        # Calculate overall model performance
        metrics = self.calculate_user_performance(validation_df)
        
        # Generate visualizations
        self.generate_visualizations(validation_df, metrics)
        
        # Generate report
        report = self.generate_report(validation_df, metrics)
        
        # Save report
        self.save_report(report)
        
        # Display summary
        self.display_summary(report)
        
        # Check retraining
        retraining = report['retraining_analysis']
        if retraining['needed']:
            logger.warning("⚠️ MODEL RETRAINING REQUIRED!")
            self.create_retraining_flag(report)
        
        return report
    
    def display_summary(self, report: Dict, user_id: Optional[int] = None):
        """Display validation summary."""
        metrics = report.get('performance_metrics', {})
        
        logger.info("\n" + "=" * 60)
        if user_id:
            logger.info(f"VALIDATION SUMMARY - User {user_id}")
        else:
            logger.info("MODEL VALIDATION SUMMARY")
        logger.info("=" * 60)
        logger.info(f"Total Predictions: {report['data_summary']['validated_predictions']}")
        logger.info(f"Model Accuracy: {metrics.get('accuracy', 0)}%")
        
        if 'betting' in metrics:
            betting = metrics['betting']['overall']
            logger.info(f"\nBETTING PERFORMANCE:")
            logger.info(f"  Strategy: {betting.get('strategy', 'N/A')}")
            logger.info(f"  Bets: {betting.get('bets', 0)}")
            logger.info(f"  Win Rate: {betting.get('win_rate', 0)}%")
            logger.info(f"  Profit: £{betting.get('profit', 0)}")
            logger.info(f"  ROI: {betting.get('roi', 0)}%")
        
        logger.info("\n" + "=" * 60)
    
    def create_retraining_flag(self, report: Dict):
        """Create flag file to trigger retraining."""
        flag_content = {
            'timestamp': datetime.now().isoformat(),
            'trigger': 'validation_performance_degradation',
            'metrics': {
                'accuracy': report['performance_metrics'].get('accuracy', 0),
                'roi': report['performance_metrics'].get('betting', {}).get('overall', {}).get('roi', 0)
            },
            'priority': report['retraining_analysis']['priority'],
            'reasons': report['retraining_analysis']['reasons']
        }
        
        flag_file = Path('retraining_flag.json')
        with open(flag_file, 'w') as f:
            json.dump(flag_content, f, indent=2)
        
        logger.info(f"Retraining flag created: {flag_file}")


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Validate user predictions from database against results.csv')
    parser.add_argument('--mode', choices=['user', 'model'], default='model',
                       help='Validate for specific user or entire model')
    parser.add_argument('--user-id', type=int, help='User ID for user validation')
    parser.add_argument('--results', default='data/results.csv',
                       help='Path to admin results CSV')
    parser.add_argument('--output-dir', default='validation_reports',
                       help='Directory for validation reports')
    parser.add_argument('--config', default='config/database.json',
                       help='Path to database config')
    
    args = parser.parse_args()
    
    # Load database config
    db_config = {}
    if Path(args.config).exists():
        try:
            with open(args.config, 'r') as f:
                db_config = json.load(f)
        except:
            logger.warning(f"Could not load config from {args.config}")
    
    # Initialize validator
    validator = DatabasePredictionValidator(
        db_config=db_config,
        results_file=args.results,
        validation_output_dir=args.output_dir
    )
    
    # Run validation
    if args.mode == 'user' and args.user_id:
        report = validator.validate_user_predictions(args.user_id)
    else:
        report = validator.validate_all_users()
    
    if report:
        print(f"\nValidation complete!")
        if args.mode == 'user':
            print(f"User report saved to: {args.output_dir}/user_{args.user_id}/")
        else:
            print(f"Model report saved to: {args.output_dir}/")
    else:
        print("Validation failed!")


if __name__ == "__main__":
    main()