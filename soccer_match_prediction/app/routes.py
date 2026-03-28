import sys
import os
import threading
import re
import random
import string
import json
import time
import logging
import secrets
import string
import pandas as pd
import numpy as np
from datetime import datetime, date, timedelta
from functools import wraps
from flask import render_template, url_for, flash, redirect, request, jsonify, session, current_app, send_file, send_from_directory, abort
from flask_login import login_user, current_user, logout_user, login_required
from flask_mail import Message
from urllib.parse import urlparse as url_parse
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import func, or_, case
from monitoring.logger import get_logger

# Import custom exceptions from errors.py
from .errors import PaymentRequired, PremiumAccessRequired, RateLimitExceeded, MaintenanceMode

# Use relative imports to avoid Circular Import Error
from . import db, login_manager, mail, socketio
from .forms import (
    RegistrationForm, LoginForm, PredictForm, ResetPasswordRequestForm, 
    ResetPasswordForm, ProfileUpdateForm, PaymentForm, FeedbackForm, 
    CustomPredictionForm, AdvancedSettingsForm, MatchOrchestrationForm,
    TeamAnalysisForm, HeadToHeadForm, MatchPredictionForm,
    DataLoadForm, FeatureGenerationForm,VerificationForm,PasswordChangeForm
)

# Import monitoring components
from monitoring.health_checker import HealthChecker
from monitoring.alert_system import AlertSystem
from monitoring.metrics_collector import MetricsCollector
from monitoring.logger import get_logger
from monitoring.dashboard import Dashboard

from updating.online_learner import OnlineLearningSystem

from .models import (
    User, Prediction, Payment, Match, TeamNameMapping, 
    UserActivity, Feedback, Leaderboard, Notification, 
    CustomPrediction, UserSettings, TeamStats, OrchestrationLog,
    DataValidationLog, FeatureCache, League, PendingRegistration,
    Coupon, CreditTransaction, OrchestrationSession, Team,
    Player, Venue, Season, ChatSession, ChatMessage,
    NewsletterSubscription, SystemLog, AgentPerformance,
    ModelEvaluation, LearningReport, DataAgentState,
    StoredPrediction, PredictionPerformance
)

# Import Celery tasks if available
try:
    from .tasks import (
        send_verification_email, send_welcome_email, send_password_reset_email,
        send_email_task, process_batch_predictions, process_single_prediction,
        update_prediction_outcomes, generate_user_report, generate_platform_report,
        update_leaderboard_task, cleanup_old_tasks, update_platform_stats,
        refresh_ai_models, send_daily_reports_task, send_notification_task,
        process_unprocessed_learning
    )
    CELERY_AVAILABLE = True
except ImportError:
    CELERY_AVAILABLE = False
    logger.warning("Celery tasks not available, running synchronously")

# Import prediction storage
try:
    from updating.prediction_storage import prediction_storage
except ImportError:
    prediction_storage = None
    logger.warning("PredictionStorage not available")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global variables for AI engines (will be initialized in register_routes)
ai_engine = None
value_bet_finder = None
live_tracker = None
performance_analyzer = None
pitch_commander = None  # New orchestration engine
# Global OAuth instance
google_oauth = None
health_checker = None
alert_manager = None      # ← very important — you already use current_app.alert_manager in some places
metrics_collector = None
training_logger = None
dashboard_builder = None
# Create singleton instance
online_learner = OnlineLearningSystem(
    weights_path="data/team_weights.json",   # or use app.config['TEAM_WEIGHTS_PATH']
    decay_rate=0.92                          # you can make tunable later
)

# ==================== CELERY-RELATED FUNCTIONS ====================

def celery_send_verification_email(user, verification_code):
    """Send verification email using Celery if available, otherwise synchronous"""
    if CELERY_AVAILABLE:
        send_verification_email.delay(user.id, verification_code)
        logger.info(f"Verification email queued for {user.email}")
    else:
        # Fallback to synchronous email sending
        from utils.email_service import EmailService
        EmailService.send_verification_email(user, verification_code)
        logger.info(f"Verification email sent synchronously to {user.email}")

def celery_send_welcome_email(user):
    """Send welcome email using Celery if available"""
    if CELERY_AVAILABLE:
        send_welcome_email.delay(user.id)
        logger.info(f"Welcome email queued for {user.email}")
    else:
        # Fallback to synchronous email sending
        from utils.email_service import EmailService
        EmailService.send_welcome_email(user)
        logger.info(f"Welcome email sent synchronously to {user.email}")

def celery_send_password_reset_email(user):
    """Send password reset email using Celery"""
    if CELERY_AVAILABLE:
        token = user.get_reset_token()
        send_password_reset_email.delay(user.id, token)
        logger.info(f"Password reset email queued for {user.email}")
    else:
        # Fallback to existing synchronous function
        send_password_reset_email_sync(user)

def celery_send_notification(user_id, title, message, notification_type='info', send_email=False):
    """Send notification using Celery"""
    if CELERY_AVAILABLE:
        send_notification_task.delay(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            send_email=send_email
        )
        logger.info(f"Notification queued for user {user_id}")
    else:
        # Fallback to synchronous notification
        send_notification_sync(user_id, title, message, notification_type)

def celery_process_prediction(prediction_data):
    """Process prediction asynchronously using Celery"""
    if CELERY_AVAILABLE:
        return process_single_prediction.delay(prediction_data)
    else:
        # Fallback to synchronous processing
        logger.warning("Celery not available, processing prediction synchronously")
        # You would call your synchronous prediction function here
        return None

def celery_update_leaderboard():
    """Update leaderboard using Celery"""
    if CELERY_AVAILABLE:
        update_leaderboard_task.delay()
        logger.info("Leaderboard update queued")
    else:
        # Fallback to synchronous update
        update_leaderboard_sync()

def celery_generate_user_report(user_id, report_type='monthly'):
    """Generate user report using Celery"""
    if CELERY_AVAILABLE:
        return generate_user_report.delay(user_id, report_type)
    else:
        # Fallback to synchronous report generation
        logger.warning("Celery not available, generating report synchronously")
        return None

# ==================== EXISTING SYNC FUNCTIONS (FOR FALLBACK) ====================

def send_password_reset_email_sync(user):
    """Synchronous password reset email sending (fallback)"""
    try:
        token = user.get_reset_token()

        msg = Message(
            subject='Password Reset Request',
            sender=current_app.config.get(
                'MAIL_DEFAULT_SENDER',
                'noreply@scorepulse.ai'
            ),
            recipients=[user.email]
        )

        reset_url = url_for('reset_password', token=token, _external=True)

        msg.body = f"""To reset your password, visit the following link:
{reset_url}

If you did not make this request, please ignore this email."""

        current_app.mail.send(msg)          # ← use current_app.mail (safer in context)

        logger.info(f"Password reset email sent to {user.email}")

    except Exception as e:
        logger.error(f"Failed to send password reset email: {e}")
        
def send_notification_sync(user_id, title, message, notification_type='info'):
    """Synchronous notification sending (fallback)"""
    try:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            is_read=False,
            created_at=datetime.utcnow()
        )
        db.session.add(notification)
        db.session.commit()
        
        # Emit socket event if using SocketIO
        if socketio:
            socketio.emit('new_notification', {
                'title': title,
                'message': message,
                'type': notification_type
            }, room=f'user_{user_id}')
            
    except Exception as e:
        logger.error(f"Failed to send notification: {e}")

def update_leaderboard_sync():
    """Synchronous leaderboard update (fallback)"""
    try:
        # Clear existing leaderboard
        Leaderboard.query.delete()
        
        # Get all users with predictions
        users = User.query.filter(User.login_count > 0).all()
        
        leaderboard_entries = []
        for user in users:
            predictions = Prediction.query.filter_by(user_id=user.id).all()
            if not predictions:
                continue
                
            wins = sum(1 for p in predictions if p.status == 'Won')
            losses = sum(1 for p in predictions if p.status == 'Lost')
            total = wins + losses
            
            if total > 0:
                accuracy = (wins / total) * 100
                profit = sum(p.profit_loss for p in predictions if p.profit_loss)
                
                entry = Leaderboard(
                    user_id=user.id,
                    username=user.username,
                    total_predictions=total,
                    wins=wins,
                    losses=losses,
                    accuracy=accuracy,
                    profit=profit,
                    streak=calculate_streak(user.id),
                    last_updated=datetime.utcnow()
                )
                leaderboard_entries.append(entry)
        
        # Sort by accuracy and profit
        leaderboard_entries.sort(key=lambda x: (x.accuracy, x.profit), reverse=True)
        
        # Add rank
        for i, entry in enumerate(leaderboard_entries):
            entry.rank = i + 1
            
        db.session.add_all(leaderboard_entries)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Failed to update leaderboard: {e}")
        db.session.rollback()

def update_prediction_outcomes_sync(match_id=None, batch_size=50):
    """
    Synchronously update prediction outcomes based on completed match results.
    Now integrates with PredictionPerformance model.
    """
    try:
        logger.info(f"Starting prediction outcome update. Match ID: {match_id}, Batch size: {batch_size}")
        
        if match_id:
            # Single match update
            return _update_single_match_predictions(match_id)
        else:
            # Batch update for all pending predictions
            return _update_batch_predictions(batch_size)
            
    except Exception as e:
        logger.error(f"Error updating prediction outcomes: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Error: {str(e)}',
            'updated': 0,
            'errors': 0
        }

def _update_single_match_predictions(match_id):
    """Update predictions for a single match"""
    try:
        # Get the match
        match = Match.query.get(match_id)
        if not match:
            return {
                'success': False,
                'message': f'Match {match_id} not found',
                'updated': 0,
                'errors': 0
            }
        
        # Check if match has a result
        if not match.home_score or not match.away_score:
            return {
                'success': False,
                'message': f'Match {match_id} has no final score',
                'updated': 0,
                'errors': 0
            }
        
        # Determine match outcome
        if match.home_score > match.away_score:
            actual_outcome = 'H'  # Home win
        elif match.home_score < match.away_score:
            actual_outcome = 'A'  # Away win
        else:
            actual_outcome = 'D'  # Draw
        
        # Get all predictions for this match
        predictions = Prediction.query.filter_by(match_id=match_id).all()
        
        if not predictions:
            return {
                'success': True,
                'message': f'No predictions found for match {match_id}',
                'updated': 0,
                'errors': 0
            }
        
        updated_count = 0
        error_count = 0
        
        for pred in predictions:
            try:
                # Skip already processed predictions
                if pred.status in ['Won', 'Lost']:
                    continue
                
                # Determine if prediction was correct
                if pred.pred_outcome == actual_outcome:
                    pred.status = 'Won'
                    pred.profit_loss = (pred.odds or 1.8) * (pred.stake or 10) - (pred.stake or 10)
                else:
                    pred.status = 'Lost'
                    pred.profit_loss = -(pred.stake or 10)
                
                # Set outcome date
                pred.outcome_date = datetime.utcnow()
                
                # Add result notes
                pred.notes = (pred.notes or '') + f'\nMatch result: {match.home_score}-{match.away_score}. ' \
                                                f'Actual outcome: {actual_outcome}. ' \
                                                f'Updated on: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
                
                updated_count += 1
                
            except Exception as e:
                logger.error(f"Error updating prediction {pred.id}: {e}")
                error_count += 1
                continue
        
        db.session.commit()
        
        # Update user statistics and leaderboard for affected users
        user_ids = set([pred.user_id for pred in predictions])
        for user_id in user_ids:
            _update_user_statistics(user_id)
        
        # Trigger leaderboard update
        celery_update_leaderboard()
        
        # Log activity
        log_activity(None, 'prediction_update', 
                    f'Updated {updated_count} predictions for match {match_id} ({match.home} vs {match.away})')
        
        return {
            'success': True,
            'message': f'Updated {updated_count} predictions for match {match_id}',
            'updated': updated_count,
            'errors': error_count,
            'match': {
                'id': match_id,
                'home': match.home,
                'away': match.away,
                'score': f'{match.home_score}-{match.away_score}',
                'outcome': actual_outcome
            }
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating single match predictions: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Error: {str(e)}',
            'updated': 0,
            'errors': 0
        }

def _update_batch_predictions(batch_size):
    """Update predictions in batch mode"""
    try:
        # Get completed matches with pending predictions
        completed_matches = Match.query.filter(
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
            Match.date <= date.today()  # Past matches only
        ).order_by(Match.date.desc()).limit(batch_size).all()
        
        if not completed_matches:
            return {
                'success': True,
                'message': 'No completed matches found for update',
                'total_updated': 0,
                'total_errors': 0,
                'matches_processed': 0
            }
        
        total_updated = 0
        total_errors = 0
        matches_processed = 0
        
        match_results = []
        
        for match in completed_matches:
            match_updated = 0
            match_errors = 0
            
            # Determine match outcome
            if match.home_score > match.away_score:
                actual_outcome = 'H'
            elif match.home_score < match.away_score:
                actual_outcome = 'A'
            else:
                actual_outcome = 'D'
            
            # Get pending predictions for this match
            predictions = Prediction.query.filter(
                Prediction.match_id == match.id,
                Prediction.status == 'Pending'
            ).all()
            
            for pred in predictions:
                try:
                    if pred.pred_outcome == actual_outcome:
                        pred.status = 'Won'
                        pred.profit_loss = (pred.odds or 1.8) * (pred.stake or 10) - (pred.stake or 10)
                    else:
                        pred.status = 'Lost'
                        pred.profit_loss = -(pred.stake or 10)
                    
                    pred.outcome_date = datetime.utcnow()
                    pred.notes = (pred.notes or '') + f'\nAuto-updated on: {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
                    
                    match_updated += 1
                    total_updated += 1
                    
                except Exception as e:
                    logger.error(f"Error updating prediction {pred.id}: {e}")
                    match_errors += 1
                    total_errors += 1
            
            if match_updated > 0 or match_errors > 0:
                matches_processed += 1
                match_results.append({
                    'match_id': match.id,
                    'match': f'{match.home} vs {match.away}',
                    'score': f'{match.home_score}-{match.away_score}',
                    'outcome': actual_outcome,
                    'updated': match_updated,
                    'errors': match_errors
                })
        
        db.session.commit()
        
        # Update user statistics for all affected users
        if total_updated > 0:
            # Get unique user IDs from updated predictions
            updated_predictions = Prediction.query.filter(
                Prediction.status.in_(['Won', 'Lost']),
                Prediction.outcome_date >= datetime.utcnow() - timedelta(minutes=5)
            ).all()
            
            user_ids = set([pred.user_id for pred in updated_predictions])
            for user_id in user_ids:
                _update_user_statistics(user_id)
            
            # Trigger leaderboard update
            celery_update_leaderboard()
        
        # Log activity
        log_activity(None, 'batch_prediction_update', 
                    f'Batch update completed. Updated {total_updated} predictions across {matches_processed} matches')
        
        return {
            'success': True,
            'message': f'Batch update completed successfully',
            'total_updated': total_updated,
            'total_errors': total_errors,
            'matches_processed': matches_processed,
            'match_results': match_results,
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error in batch prediction update: {e}", exc_info=True)
        return {
            'success': False,
            'message': f'Error: {str(e)}',
            'total_updated': 0,
            'total_errors': 0,
            'matches_processed': 0
        }

def _update_user_statistics(user_id):
    """Update user statistics after prediction outcomes"""
    try:
        user = User.query.get(user_id)
        if not user:
            return
        
        # Calculate new statistics
        predictions = Prediction.query.filter_by(user_id=user_id).all()
        
        total = len(predictions)
        wins = sum(1 for p in predictions if p.status == 'Won')
        losses = sum(1 for p in predictions if p.status == 'Lost')
        pending = sum(1 for p in predictions if p.status == 'Pending')
        
        # Update user fields if they exist
        if hasattr(user, 'total_predictions'):
            user.total_predictions = total
        
        if hasattr(user, 'wins'):
            user.wins = wins
        
        if hasattr(user, 'losses'):
            user.losses = losses
        
        if hasattr(user, 'pending_predictions'):
            user.pending_predictions = pending
        
        # Calculate profit if field exists
        if hasattr(user, 'total_profit'):
            total_profit = sum(p.profit_loss or 0 for p in predictions if p.profit_loss is not None)
            user.total_profit = total_profit
        
        # Update accuracy
        if hasattr(user, 'accuracy'):
            settled = wins + losses
            if settled > 0:
                user.accuracy = (wins / settled) * 100
            else:
                user.accuracy = 0
        
        # Calculate streak
        if hasattr(user, 'current_streak'):
            user.current_streak = calculate_streak(user_id)
        
        db.session.commit()
        
        logger.debug(f"Updated statistics for user {user_id}: {wins}W/{losses}L/{pending}P, Accuracy: {user.accuracy if hasattr(user, 'accuracy') else 'N/A'}")
        
    except Exception as e:
        logger.error(f"Error updating user statistics for {user_id}: {e}")
        db.session.rollback()
        
def update_prediction_performance(prediction_id, actual_outcome):
    """
    Update performance metrics for a specific prediction.
    
    Args:
        prediction_id (int): ID of the prediction
        actual_outcome (str): Actual match outcome ('H', 'D', 'A')
    
    Returns:
        dict: Updated performance metrics
    """
    try:
        prediction = Prediction.query.get(prediction_id)
        if not prediction:
            return {'success': False, 'error': 'Prediction not found'}
        
        # Determine if prediction was correct
        is_correct = prediction.pred_outcome == actual_outcome
        
        # Calculate performance metrics
        if is_correct:
            profit_loss = (prediction.odds or 1.8) * (prediction.stake or 10) - (prediction.stake or 10)
            status = 'Won'
        else:
            profit_loss = -(prediction.stake or 10)
            status = 'Lost'
        
        # Update prediction record
        prediction.status = status
        prediction.profit_loss = profit_loss
        prediction.outcome_date = datetime.utcnow()
        
        # Update or create PredictionPerformance record
        performance = PredictionPerformance.query.filter_by(
            prediction_id=prediction_id
        ).first()
        
        if not performance:
            performance = PredictionPerformance(
                prediction_id=prediction_id,
                user_id=prediction.user_id,
                match_date=prediction.match_date,
                home_team=prediction.home_team,
                away_team=prediction.away_team,
                predicted_outcome=prediction.pred_outcome,
                actual_outcome=actual_outcome,
                is_correct=is_correct,
                confidence_score=prediction.confidence or 50.0,
                profit_loss=profit_loss,
                odds_used=prediction.odds or 1.8,
                stake=prediction.stake or 10,
                model_used=prediction.model_used or 'Unknown',
                notes=f'Updated via prediction outcome update on {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
            )
            db.session.add(performance)
        else:
            # Update existing record
            performance.actual_outcome = actual_outcome
            performance.is_correct = is_correct
            performance.profit_loss = profit_loss
            performance.updated_at = datetime.utcnow()
            performance.notes = (performance.notes or '') + f'\nRe-evaluated on {datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")}'
        
        db.session.commit()
        
        # Update user statistics
        update_user_prediction_stats(prediction.user_id)
        
        # Update model performance if applicable
        if prediction.model_used:
            update_model_performance(prediction.model_used, is_correct, prediction.confidence or 50.0)
        
        logger.info(f"Prediction performance updated for prediction {prediction_id}: {status} with profit/loss: {profit_loss}")
        
        return {
            'success': True,
            'prediction_id': prediction_id,
            'predicted': prediction.pred_outcome,
            'actual': actual_outcome,
            'is_correct': is_correct,
            'profit_loss': profit_loss,
            'status': status,
            'performance_id': performance.id
        }
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error updating prediction performance for {prediction_id}: {e}", exc_info=True)
        return {'success': False, 'error': str(e)}

def update_user_prediction_stats(user_id):
    """
    Update user's prediction statistics based on their PredictionPerformance records.
    
    Args:
        user_id (int): User ID to update stats for
    """
    try:
        # Get all performance records for user
        performances = PredictionPerformance.query.filter_by(
            user_id=user_id
        ).all()
        
        if not performances:
            return
        
        # Calculate statistics
        total_predictions = len(performances)
        correct_predictions = sum(1 for p in performances if p.is_correct)
        total_profit = sum(p.profit_loss or 0 for p in performances)
        
        # Calculate accuracy
        accuracy = (correct_predictions / total_predictions * 100) if total_predictions > 0 else 0
        
        # Calculate average confidence
        avg_confidence = sum(p.confidence_score or 0 for p in performances) / total_predictions if total_predictions > 0 else 0
        
        # Get current streak
        streak = calculate_current_streak(user_id)
        
        # Get best performing model
        model_performance = {}
        for perf in performances:
            model = perf.model_used or 'Unknown'
            if model not in model_performance:
                model_performance[model] = {'correct': 0, 'total': 0}
            model_performance[model]['total'] += 1
            if perf.is_correct:
                model_performance[model]['correct'] += 1
        
        best_model = None
        best_accuracy = 0
        for model, stats in model_performance.items():
            model_accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
            if model_accuracy > best_accuracy:
                best_accuracy = model_accuracy
                best_model = model
        
        # Update user stats in User model if fields exist
        user = User.query.get(user_id)
        if user:
            if hasattr(user, 'total_predictions'):
                user.total_predictions = total_predictions
            
            if hasattr(user, 'correct_predictions'):
                user.correct_predictions = correct_predictions
            
            if hasattr(user, 'prediction_accuracy'):
                user.prediction_accuracy = accuracy
            
            if hasattr(user, 'total_profit'):
                user.total_profit = total_profit
            
            if hasattr(user, 'avg_confidence'):
                user.avg_confidence = avg_confidence
            
            if hasattr(user, 'current_streak'):
                user.current_streak = streak
            
            if hasattr(user, 'best_performing_model'):
                user.best_performing_model = best_model
            
            db.session.commit()
        
        logger.debug(f"Updated prediction stats for user {user_id}: {correct_predictions}/{total_predictions} ({accuracy:.1f}%), Profit: {total_profit:.2f}")
        
    except Exception as e:
        logger.error(f"Error updating user prediction stats for {user_id}: {e}")

def calculate_current_streak(user_id):
    """
    Calculate user's current winning streak based on PredictionPerformance.
    
    Args:
        user_id (int): User ID
    
    Returns:
        int: Current winning streak
    """
    try:
        # Get recent performances ordered by match date (most recent first)
        performances = PredictionPerformance.query.filter_by(
            user_id=user_id
        ).order_by(PredictionPerformance.match_date.desc()).all()
        
        streak = 0
        for perf in performances:
            if perf.is_correct:
                streak += 1
            else:
                break
        
        return streak
        
    except Exception as e:
        logger.error(f"Error calculating streak for user {user_id}: {e}")
        return 0

def update_model_performance(model_name, is_correct, confidence):
    """
    Update performance metrics for a specific model.
    
    Args:
        model_name (str): Name of the model
        is_correct (bool): Whether prediction was correct
        confidence (float): Confidence score
    """
    try:
        # Check if ModelEvaluation exists in your models
        if 'ModelEvaluation' in globals():
            evaluation = ModelEvaluation.query.filter_by(
                model_name=model_name
            ).first()
            
            if not evaluation:
                evaluation = ModelEvaluation(
                    model_name=model_name,
                    total_predictions=0,
                    correct_predictions=0,
                    total_confidence=0,
                    average_confidence=0,
                    last_used=datetime.utcnow()
                )
                db.session.add(evaluation)
            
            # Update metrics
            evaluation.total_predictions += 1
            if is_correct:
                evaluation.correct_predictions += 1
            
            evaluation.total_confidence += confidence
            evaluation.average_confidence = evaluation.total_confidence / evaluation.total_predictions
            evaluation.accuracy = (evaluation.correct_predictions / evaluation.total_predictions * 100) if evaluation.total_predictions > 0 else 0
            evaluation.last_used = datetime.utcnow()
            
            db.session.commit()
            
            logger.debug(f"Updated model performance for {model_name}: {evaluation.correct_predictions}/{evaluation.total_predictions} ({evaluation.accuracy:.1f}%)")
        
    except Exception as e:
        logger.error(f"Error updating model performance for {model_name}: {e}")

def get_prediction_performance_summary(user_id=None, start_date=None, end_date=None, model=None):
    """
    Get comprehensive prediction performance summary.
    
    Args:
        user_id (int, optional): Filter by user ID
        start_date (date, optional): Start date for filtering
        end_date (date, optional): End date for filtering
        model (str, optional): Filter by model name
    
    Returns:
        dict: Performance summary
    """
    try:
        query = PredictionPerformance.query
        
        if user_id:
            query = query.filter_by(user_id=user_id)
        
        if start_date:
            query = query.filter(PredictionPerformance.match_date >= start_date)
        
        if end_date:
            query = query.filter(PredictionPerformance.match_date <= end_date)
        
        if model:
            query = query.filter_by(model_used=model)
        
        performances = query.all()
        
        if not performances:
            return {
                'success': True,
                'total_predictions': 0,
                'message': 'No performance data found'
            }
        
        # Calculate overall metrics
        total = len(performances)
        correct = sum(1 for p in performances if p.is_correct)
        accuracy = (correct / total * 100) if total > 0 else 0
        total_profit = sum(p.profit_loss or 0 for p in performances)
        avg_confidence = sum(p.confidence_score or 0 for p in performances) / total if total > 0 else 0
        avg_stake = sum(p.stake or 0 for p in performances) / total if total > 0 else 0
        avg_odds = sum(p.odds_used or 0 for p in performances) / total if total > 0 else 0
        
        # Calculate by outcome
        home_wins = sum(1 for p in performances if p.actual_outcome == 'H' and p.is_correct)
        draws = sum(1 for p in performances if p.actual_outcome == 'D' and p.is_correct)
        away_wins = sum(1 for p in performances if p.actual_outcome == 'A' and p.is_correct)
        
        # Calculate by model
        model_stats = {}
        for perf in performances:
            model = perf.model_used or 'Unknown'
            if model not in model_stats:
                model_stats[model] = {'total': 0, 'correct': 0, 'profit': 0}
            
            model_stats[model]['total'] += 1
            if perf.is_correct:
                model_stats[model]['correct'] += 1
            model_stats[model]['profit'] += perf.profit_loss or 0
        
        # Calculate ROI
        total_stake = sum(p.stake or 0 for p in performances)
        roi = (total_profit / total_stake * 100) if total_stake > 0 else 0
        
        # Get recent performances
        recent_performances = sorted(performances, key=lambda x: x.match_date, reverse=True)[:10]
        
        # Format recent performances for response
        recent_data = []
        for perf in recent_performances:
            recent_data.append({
                'id': perf.id,
                'match': f"{perf.home_team} vs {perf.away_team}",
                'date': perf.match_date.strftime('%Y-%m-%d') if perf.match_date else 'N/A',
                'predicted': perf.predicted_outcome,
                'actual': perf.actual_outcome,
                'correct': perf.is_correct,
                'profit_loss': perf.profit_loss,
                'confidence': perf.confidence_score,
                'model': perf.model_used
            })
        
        # Get best and worst performing predictions
        best_performers = sorted(performances, key=lambda x: x.profit_loss or 0, reverse=True)[:5]
        worst_performers = sorted(performances, key=lambda x: x.profit_loss or 0)[:5]
        
        return {
            'success': True,
            'summary': {
                'total_predictions': total,
                'correct_predictions': correct,
                'accuracy': round(accuracy, 2),
                'total_profit': round(total_profit, 2),
                'roi': round(roi, 2),
                'average_confidence': round(avg_confidence, 2),
                'average_stake': round(avg_stake, 2),
                'average_odds': round(avg_odds, 2),
                'outcome_accuracy': {
                    'home_wins': home_wins,
                    'draws': draws,
                    'away_wins': away_wins
                },
                'model_stats': model_stats
            },
            'recent_performances': recent_data,
            'best_performers': [
                {
                    'match': f"{p.home_team} vs {p.away_team}",
                    'profit': p.profit_loss,
                    'date': p.match_date.strftime('%Y-%m-%d') if p.match_date else 'N/A'
                } for p in best_performers
            ],
            'worst_performers': [
                {
                    'match': f"{p.home_team} vs {p.away_team}",
                    'profit': p.profit_loss,
                    'date': p.match_date.strftime('%Y-%m-%d') if p.match_date else 'N/A'
                } for p in worst_performers
            ],
            'timestamp': datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logger.error(f"Error getting prediction performance summary: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def generate_performance_report(user_id, report_type='monthly'):
    """
    Generate a detailed performance report for a user.
    
    Args:
        user_id (int): User ID
        report_type (str): 'daily', 'weekly', 'monthly', or 'custom'
    
    Returns:
        dict: Performance report
    """
    try:
        # Determine date range based on report type
        end_date = date.today()
        
        if report_type == 'daily':
            start_date = end_date
        elif report_type == 'weekly':
            start_date = end_date - timedelta(days=7)
        elif report_type == 'monthly':
            start_date = end_date - timedelta(days=30)
        else:
            start_date = end_date - timedelta(days=365)  # Annual by default
        
        # Get performance data
        summary = get_prediction_performance_summary(
            user_id=user_id,
            start_date=start_date,
            end_date=end_date
        )
        
        if not summary['success']:
            return summary
        
        # Get user info
        user = User.query.get(user_id)
        
        # Calculate additional metrics
        performances = PredictionPerformance.query.filter_by(
            user_id=user_id
        ).filter(
            PredictionPerformance.match_date >= start_date,
            PredictionPerformance.match_date <= end_date
        ).all()
        
        # Calculate daily performance
        daily_performance = {}
        for perf in performances:
            day = perf.match_date.strftime('%Y-%m-%d') if perf.match_date else 'Unknown'
            if day not in daily_performance:
                daily_performance[day] = {'total': 0, 'correct': 0, 'profit': 0}
            
            daily_performance[day]['total'] += 1
            if perf.is_correct:
                daily_performance[day]['correct'] += 1
            daily_performance[day]['profit'] += perf.profit_loss or 0
        
        # Format daily performance for charts
        daily_data = []
        for day, stats in sorted(daily_performance.items()):
            daily_accuracy = (stats['correct'] / stats['total'] * 100) if stats['total'] > 0 else 0
            daily_data.append({
                'date': day,
                'total': stats['total'],
                'correct': stats['correct'],
                'accuracy': round(daily_accuracy, 2),
                'profit': round(stats['profit'], 2)
            })
        
        # Calculate risk metrics
        if performances:
            # Sharpe ratio (simplified)
            returns = [p.profit_loss or 0 for p in performances]
            avg_return = sum(returns) / len(returns)
            std_return = (sum((r - avg_return) ** 2 for r in returns) / len(returns)) ** 0.5
            sharpe_ratio = (avg_return / std_return) if std_return > 0 else 0
            
            # Win rate
            win_rate = (summary['summary']['accuracy'] / 100) if summary['summary']['accuracy'] > 0 else 0
            
            # Average win/loss
            wins = [p.profit_loss for p in performances if p.is_correct and p.profit_loss]
            losses = [p.profit_loss for p in performances if not p.is_correct and p.profit_loss]
            
            avg_win = sum(wins) / len(wins) if wins else 0
            avg_loss = sum(losses) / len(losses) if losses else 0
            profit_factor = abs(avg_win / avg_loss) if avg_loss != 0 else float('inf')
        else:
            sharpe_ratio = 0
            win_rate = 0
            profit_factor = 0
        
        # Create report
        report = {
            'success': True,
            'report_type': report_type,
            'period': {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d')
            },
            'user': {
                'id': user_id,
                'username': user.username if user else 'Unknown',
                'email': user.email if user else 'Unknown'
            },
            'performance_summary': summary['summary'],
            'daily_performance': daily_data,
            'risk_metrics': {
                'sharpe_ratio': round(sharpe_ratio, 3),
                'win_rate': round(win_rate, 3),
                'profit_factor': round(profit_factor, 2),
                'total_stake': sum(p.stake or 0 for p in performances),
                'max_drawdown': min(p.profit_loss or 0 for p in performances) if performances else 0
            },
            'insights': generate_performance_insights(performances),
            'recommendations': generate_performance_recommendations(summary['summary']),
            'generated_at': datetime.utcnow().isoformat()
        }
        
        # Save report to database if LearningReport model exists
        if 'LearningReport' in globals():
            learning_report = LearningReport(
                user_id=user_id,
                report_type=report_type,
                period_start=start_date,
                period_end=end_date,
                total_predictions=summary['summary']['total_predictions'],
                correct_predictions=summary['summary']['correct_predictions'],
                accuracy=summary['summary']['accuracy'],
                total_profit=summary['summary']['total_profit'],
                roi=summary['summary']['roi'],
                insights=json.dumps(report['insights']),
                recommendations=json.dumps(report['recommendations']),
                generated=datetime.utcnow()
            )
            db.session.add(learning_report)
            db.session.commit()
        
        return report
        
    except Exception as e:
        logger.error(f"Error generating performance report for user {user_id}: {e}", exc_info=True)
        return {
            'success': False,
            'error': str(e)
        }

def generate_performance_insights(performances):
    """Generate insights from performance data."""
    insights = []
    
    if not performances:
        insights.append("No performance data available for analysis.")
        return insights
    
    # Calculate metrics
    total = len(performances)
    correct = sum(1 for p in performances if p.is_correct)
    accuracy = (correct / total * 100) if total > 0 else 0
    
    # Insight 1: Overall accuracy
    if accuracy > 70:
        insights.append(f"Excellent prediction accuracy of {accuracy:.1f}% - well above average!")
    elif accuracy > 60:
        insights.append(f"Good prediction accuracy of {accuracy:.1f}% - keep up the good work!")
    elif accuracy > 50:
        insights.append(f"Above average accuracy of {accuracy:.1f}% - room for improvement.")
    else:
        insights.append(f"Accuracy of {accuracy:.1f}% - consider refining your prediction strategy.")
    
    # Insight 2: Profit analysis
    total_profit = sum(p.profit_loss or 0 for p in performances)
    if total_profit > 0:
        insights.append(f"Positive profit of ${total_profit:.2f} - profitable strategy!")
    else:
        insights.append(f"Negative profit of ${total_profit:.2f} - review your betting strategy.")
    
    # Insight 3: Model performance
    model_stats = {}
    for perf in performances:
        model = perf.model_used or 'Unknown'
        if model not in model_stats:
            model_stats[model] = {'total': 0, 'correct': 0}
        model_stats[model]['total'] += 1
        if perf.is_correct:
            model_stats[model]['correct'] += 1
    
    if len(model_stats) > 1:
        best_model = max(model_stats.items(), key=lambda x: (x[1]['correct'] / x[1]['total'] * 100) if x[1]['total'] > 0 else 0)
        best_accuracy = (best_model[1]['correct'] / best_model[1]['total'] * 100) if best_model[1]['total'] > 0 else 0
        insights.append(f"Best performing model: {best_model[0]} with {best_accuracy:.1f}% accuracy.")
    
    # Insight 4: Consistency
    if total >= 10:
        # Check for consistency in last 5 predictions
        recent = performances[-5:] if len(performances) >= 5 else performances
        recent_correct = sum(1 for p in recent if p.is_correct)
        recent_accuracy = (recent_correct / len(recent) * 100) if recent else 0
        
        if recent_accuracy > accuracy + 10:
            insights.append("Recent performance is improving significantly!")
        elif recent_accuracy < accuracy - 10:
            insights.append("Recent performance has declined - review recent predictions.")
    
    return insights

def generate_performance_recommendations(summary):
    """Generate recommendations based on performance summary."""
    recommendations = []
    
    # Recommendation based on accuracy
    if summary['accuracy'] < 50:
        recommendations.append("Consider using more conservative betting strategies.")
        recommendations.append("Review predictions for matches with low confidence scores.")
        recommendations.append("Try using different prediction models to compare performance.")
    
    # Recommendation based on profit
    if summary['total_profit'] < 0:
        recommendations.append("Reduce stake sizes until profitability improves.")
        recommendations.append("Focus on value bets rather than frequent predictions.")
        recommendations.append("Set a stop-loss limit to manage risk.")
    
    # Recommendation based on model usage
    if 'model_stats' in summary and len(summary['model_stats']) > 1:
        recommendations.append("Stick with your best performing model more consistently.")
    
    # General recommendations
    recommendations.append("Keep detailed records of all predictions and outcomes.")
    recommendations.append("Regularly review your performance metrics.")
    recommendations.append("Consider using bankroll management strategies.")
    
    return recommendations        

# ==================== EXISTING CODE CONTINUES ====================


# Add to the top of routes.py after imports
def cache_key_generator(prefix, *args):
    """Generate consistent cache keys"""
    key_parts = [prefix] + [str(arg) for arg in args]
    return ":".join(key_parts)

def cache_prediction_result(user_id, match_id, prediction_data, timeout=3600):
    """Cache prediction result"""
    key = cache_key_generator("prediction", user_id, match_id)
    if hasattr(current_app, 'cache'):
        current_app.cache.set(key, prediction_data, timeout=timeout)
    return key

def get_cached_prediction(user_id, match_id):
    """Get cached prediction result"""
    key = cache_key_generator("prediction", user_id, match_id)
    if hasattr(current_app, 'cache'):
        return current_app.cache.get(key)
    return None

def cache_match_list(date_str, matches, timeout=300):
    """Cache match list for a specific date"""
    key = cache_key_generator("matches", date_str)
    if hasattr(current_app, 'cache'):
        current_app.cache.set(key, matches, timeout=timeout)
    return key

def get_cached_matches(date_str):
    """Get cached match list"""
    key = cache_key_generator("matches", date_str)
    if hasattr(current_app, 'cache'):
        return current_app.cache.get(key)
    return None

def cache_team_stats(team_name, stats, timeout=1800):
    """Cache team statistics"""
    key = cache_key_generator("team_stats", team_name)
    if hasattr(current_app, 'cache'):
        current_app.cache.set(key, stats, timeout=timeout)
    return key

def get_cached_team_stats(team_name):
    """Get cached team statistics"""
    key = cache_key_generator("team_stats", team_name)
    if hasattr(current_app, 'cache'):
        return current_app.cache.get(key)
    return None

def cache_head_to_head(team1, team2, stats, timeout=1800):
    """Cache head-to-head statistics"""
    key = cache_key_generator("h2h", team1, team2)
    if hasattr(current_app, 'cache'):
        current_app.cache.set(key, stats, timeout=timeout)
    return key

def get_cached_head_to_head(team1, team2):
    """Get cached head-to-head statistics"""
    key = cache_key_generator("h2h", team1, team2)
    if hasattr(current_app, 'cache'):
        return current_app.cache.get(key)
    return None

def invalidate_user_cache(user_id):
    """Invalidate all cache entries for a user"""
    pattern = cache_key_generator("*", user_id, "*")
    if hasattr(current_app, 'cache'):
        current_app.cache.clear(pattern)
    
def invalidate_match_cache(match_id):
    """Invalidate all cache entries for a match"""
    pattern = cache_key_generator("*", "*", match_id)
    if hasattr(current_app, 'cache'):
        current_app.cache.clear(pattern)

def init_oauth(app):
    """Initialize OAuth with the Flask app"""
    global google_oauth
    
    if not app.config.get('GOOGLE_OAUTH_ENABLED', False):
        logger.warning("Google OAuth is disabled in config")
        return None
    
    try:
        from authlib.integrations.flask_client import OAuth
        
        # IMPORTANT: Disable SSL verification for development on Windows
        import ssl
        import urllib3
        
        # Disable SSL warnings for development
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        
        google_oauth = OAuth(app)
        google_oauth.register(
            name='google',
            client_id=app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=app.config.get('GOOGLE_CLIENT_SECRET'),
            authorize_url='https://accounts.google.com/o/oauth2/auth',
            access_token_url='https://accounts.google.com/o/oauth2/token',
            userinfo_endpoint='https://www.googleapis.com/oauth2/v1/userinfo',
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={
                'scope': 'openid email profile',
                'prompt': 'select_account',
                'verify': False
            },
            
            #redirect_uri=url_for('google_authorize', _external=True)
        )
        logger.info("Google OAuth initialized successfully")
        return google_oauth
    except Exception as e:
        logger.error(f"Failed to initialize Google OAuth: {e}")
        return None

def get_oauth():
    """Get the OAuth instance"""
    global google_oauth
    return google_oauth

# Helper Functions
def generate_random_password(length=12):
    """Generate a secure random password for Google OAuth users"""
    alphabet = string.ascii_letters + string.digits + string.punctuation
    return ''.join(secrets.choice(alphabet) for _ in range(length))

def parse_time_string(time_str):
    """Parse a time string that could be in various formats."""
    if not time_str:
        return None
    
    try:
        time_str = str(time_str).strip().upper()
        
        # Remove extra spaces
        time_str = re.sub(r'\s+', ' ', time_str)
        
        # Try common time formats
        formats = [
            '%H:%M',        # 24-hour: 03:00, 18:30
            '%I:%M %p',     # 12-hour with space: 3:00 AM
            '%I:%M%p',      # 12-hour without space: 3:00AM
            '%H:%M:%S',     # 24-hour with seconds
            '%I:%M:%S %p',  # 12-hour with seconds
        ]
        
        for fmt in formats:
            try:
                return datetime.strptime(time_str, fmt).time()
            except ValueError:
                continue
        
        # If all parsing fails, try to extract time components
        match = re.search(r'(\d{1,2}):(\d{2})', time_str)
        if match:
            hour = int(match.group(1))
            minute = int(match.group(2))
            
            # Check if it's PM
            if 'PM' in time_str and hour < 12:
                hour += 12
            elif 'AM' in time_str and hour == 12:
                hour = 0
            
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                return datetime.time(hour, minute)
        
        return None
    except Exception:
        return None

def normalize_team_name(team_name):
    """Normalize team names using mapping or AI engine"""
    if not team_name:
        return team_name
    
    mapping = TeamNameMapping.query.filter_by(original_name=team_name).first()
    if mapping:
        return mapping.standard_name
    
    if ai_engine and hasattr(ai_engine, 'team_resolver'):
        try:
            resolved = ai_engine.team_resolver.normalize_team_name(team_name)
            if resolved != team_name:
                new_mapping = TeamNameMapping(
                    original_name=team_name,
                    standard_name=resolved,
                    source='auto_detected'
                )
                db.session.add(new_mapping)
                db.session.commit()
            return resolved
        except:
            pass
    
    return team_name

def get_all_teams():
    """Get all unique teams from database"""
    teams = set()
    
    matches = Match.query.with_entities(Match.home_team_id, Match.away_team_id).all()
    for home, away in matches:
        if home: teams.add(home)
        if away: teams.add(away)
    
    predictions = Prediction.query.with_entities(Prediction.home_team, Prediction.away_team).all()
    for home, away in predictions:
        if home: teams.add(home)
        if away: teams.add(away)
        
    team_objects = Team.query.with_entities(Team.name).all()
    for team_tuple in team_objects:
        teams.add(team_tuple[0])
    
    return sorted(list(teams))

def log_activity(user_id, action, details):
    """Log user activity to database"""
    try:
        activity = UserActivity(
            user_id=user_id,
            action=action,
            details=details,
            ip_address=request.remote_addr,
            user_agent=request.user_agent.string,
            timestamp=datetime.utcnow()
        )
        db.session.add(activity)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to log activity: {e}")

def log_orchestration(user_id, match_id, home_team, away_team, status, execution_time, result):
    """Log orchestration run to database"""
    try:
        log = OrchestrationLog(
            match_id=match_id,
            home_team=home_team,
            away_team=away_team,
            user_id=user_id,
            status=status,
            execution_time=execution_time,
            prediction_result=result.get('prediction') if isinstance(result, dict) else None,
            bankroll_result=result.get('betting_strategy') if isinstance(result, dict) else None,
            analysis_result=result.get('analysis') if isinstance(result, dict) else None,
            full_context=json.dumps(result) if isinstance(result, dict) else str(result),
            timestamp=datetime.utcnow()
        )
        
        db.session.add(log)
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Error logging orchestration: {e}")
        
def verification_required(f):
    """Decorator to require email verification"""
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if not current_user.is_verified:
            flash('Please verify your email address to access this feature.', 'warning')
            return redirect(url_for('verify_email'))
        return f(*args, **kwargs)
    return decorated_function

def update_leaderboard():
    """Update user leaderboard rankings - Now uses Celery"""
    celery_update_leaderboard()

def calculate_streak(user_id):
    """Calculate user's current winning streak"""
    predictions = Prediction.query.filter_by(
        user_id=user_id
    ).order_by(Prediction.match_date.desc()).all()
    
    streak = 0
    for pred in predictions:
        if pred.status == 'Won':
            streak += 1
        elif pred.status == 'Lost':
            break
        else:
            continue
    
    return streak

def calculate_accuracy(user_id):
    """Calculate user prediction accuracy"""
    predictions = Prediction.query.filter_by(user_id=user_id).all()
    if not predictions:
        return 0
    
    wins = sum(1 for p in predictions if p.status == 'Won')
    losses = sum(1 for p in predictions if p.status == 'Lost')
    
    if wins + losses == 0:
        return 0
    
    return (wins / (wins + losses)) * 100

def calculate_system_uptime():
    """Calculate system uptime in days and hours"""
    try:
        # Get app start time from config or use a default
        start_time = current_app.config.get('APP_START_TIME', datetime.utcnow() - timedelta(days=15))
        uptime = datetime.utcnow() - start_time
        return {
            'days': uptime.days,
            'hours': uptime.seconds // 3600,
            'minutes': (uptime.seconds % 3600) // 60,
            'total_hours': uptime.days * 24 + uptime.seconds // 3600
        }
    except:
        return {'days': 15, 'hours': 6, 'minutes': 30, 'total_hours': 366}

def generate_trend_data(hours=12, base=50, variation=20):
    """Generate sample trend data for charts"""
    import random
    trend = []
    now = datetime.utcnow()
    
    for i in range(hours, 0, -1):
        hour = now - timedelta(hours=i)
        value = base + random.uniform(-variation, variation)
        trend.append({
            'time': hour.strftime('%H:%M'),
            'value': round(max(0, min(100, value)), 1)
        })
    
    return trend


def calculate_platform_accuracy():
    """Calculate overall platform prediction accuracy"""
    total = Prediction.query.filter(Prediction.status.in_(['Won', 'Lost'])).count()
    wins = Prediction.query.filter_by(status='Won').count()
    
    if total > 0:
        return round((wins / total) * 100, 2)
    return 0

def calculate_user_growth():
    """Calculate user growth over last 30 days"""
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    previous_count = User.query.filter(User.created_at < thirty_days_ago).count()
    current_count = User.query.count()
    
    if previous_count > 0:
        growth = ((current_count - previous_count) / previous_count) * 100
        return round(growth, 2)
    return 100 if current_count > 0 else 0

def calculate_revenue_trend():
    """Calculate revenue trend over last 7 days"""
    seven_days_ago = datetime.utcnow() - timedelta(days=7)
    
    revenue_data = []
    for i in range(7):
        day = date.today() - timedelta(days=i)
        daily_revenue = db.session.query(db.func.sum(Payment.amount)).filter(
            Payment.status == 'COMPLETED',
            func.strftime('%Y-%m-%d', Payment.timestamp) == day.strftime('%Y-%m-%d')
        ).scalar() or 0
        
        revenue_data.append({
            'date': day.strftime('%Y-%m-%d'),
            'revenue': float(daily_revenue)
        })
    
    return revenue_data[::-1]  # Reverse to show oldest first

def apply_advanced_filters(prediction_result, custom_params):
    """Apply advanced filters and adjustments to prediction based on user settings"""
    result = prediction_result.copy()
    
    # 1. Adjust probabilities based on included data sources
    if not custom_params.get('include_head_to_head', True):
        # Reduce weight of historical data
        result['analysis'] = result.get('analysis', '') + "\n⚠️ Head-to-head data excluded per user settings."
        # You could implement actual adjustment logic here
    
    if not custom_params.get('include_form', True):
        # Reduce weight of recent form
        result['analysis'] = result.get('analysis', '') + "\n⚠️ Recent form data excluded per user settings."
    
    if not custom_params.get('include_injuries', True):
        # Note: Injury data not currently implemented
        result['analysis'] = result.get('analysis', '') + "\nℹ️ Injury data option selected but not yet implemented."
    
    # 2. Adjust for betting strategy
    betting_strategy = custom_params.get('betting_strategy', 'conservative')
    risk_level = custom_params.get('risk_level', 'medium')
    
    # Adjust stake based on strategy and risk
    base_stake = result.get('recommended_stake', 2.5)
    
    if betting_strategy == 'aggressive':
        if risk_level == 'high':
            result['recommended_stake'] = base_stake * 2.0
            result['risk_level'] = 'VERY_HIGH'
        elif risk_level == 'medium':
            result['recommended_stake'] = base_stake * 1.5
            result['risk_level'] = 'HIGH'
    elif betting_strategy == 'conservative':
        if risk_level == 'low':
            result['recommended_stake'] = base_stake * 0.5
            result['risk_level'] = 'LOW'
    
    # 3. Add strategy-specific analysis
    strategy_analysis = {
        'value_betting': "Focusing on identifying value bets where AI confidence exceeds market implied probability.",
        'arbitrage': "Looking for arbitrage opportunities across different bookmakers.",
        'accumulator': "Suitable for accumulator bets with multiple selections.",
        'hedging': "Recommends hedging strategies to minimize risk.",
        'in_play': "Optimized for in-play/live betting scenarios."
    }
    
    if betting_strategy in strategy_analysis:
        result['analysis'] = result.get('analysis', '') + f"\n🎯 Strategy: {strategy_analysis[betting_strategy]}"
    
    return result

def get_user_activity_heatmap():
    """Get user activity heatmap data"""
    try:
        # Get activity by hour of day
        activity_by_hour = {}
        for hour in range(24):
            hour_start = datetime.utcnow().replace(hour=hour, minute=0, second=0, microsecond=0)
            hour_end = hour_start + timedelta(hours=1)
            
            count = UserActivity.query.filter(
                UserActivity.timestamp >= hour_start,
                UserActivity.timestamp < hour_end
            ).count()
            
            activity_by_hour[f"{hour:02d}:00"] = count
        
        return activity_by_hour
        
    except Exception as e:
        logger.error(f"Error getting activity heatmap: {e}")
        return {}

def get_league_success_rates():
    """Get prediction success rates by league"""
    try:
        # This would require league data in predictions
        # For now, return placeholder
        return [
            {'league': 'Premier League', 'accuracy': 72.5, 'predictions': 150},
            {'league': 'La Liga', 'accuracy': 68.2, 'predictions': 120},
            {'league': 'Serie A', 'accuracy': 65.8, 'predictions': 95},
            {'league': 'Bundesliga', 'accuracy': 70.1, 'predictions': 110},
            {'league': 'Ligue 1', 'accuracy': 63.4, 'predictions': 85}
        ]
    except Exception as e:
        logger.error(f"Error getting league success rates: {e}")
        return []

def get_head_to_head_stats(team1, team2):
    """Get head-to-head statistics between two teams"""
    try:
        matches = Match.query.filter(
            ((Match.home == team1) & (Match.away == team2)) |
            ((Match.home == team2) & (Match.away == team1))
        ).all()
        
        total_matches = len(matches)
        team1_wins = 0
        team2_wins = 0
        draws = 0
        
        for match in matches:
            if match.result:
                home_score = match.result.split('-')[0].strip()
                away_score = match.result.split('-')[1].strip()
                
                if home_score > away_score:
                    if match.home == team1:
                        team1_wins += 1
                    else:
                        team2_wins += 1
                elif away_score > home_score:
                    if match.away == team1:
                        team1_wins += 1
                    else:
                        team2_wins += 1
                else:
                    draws += 1
        
        return {
            'total_matches': total_matches,
            'team1_wins': team1_wins,
            'team2_wins': team2_wins,
            'draws': draws,
            'team1_win_percentage': (team1_wins / total_matches * 100) if total_matches > 0 else 0,
            'team2_win_percentage': (team2_wins / total_matches * 100) if total_matches > 0 else 0,
            'draw_percentage': (draws / total_matches * 100) if total_matches > 0 else 0
        }
    except Exception as e:
        logger.error(f"Error getting head-to-head stats: {e}")
        return {}

def generate_team_stats(team_name, matches):
    """Generate statistics for a team"""
    stats = {
        'total_matches': len(matches),
        'wins': 0,
        'draws': 0,
        'losses': 0,
        'goals_scored': 0,
        'goals_conceded': 0,
        'clean_sheets': 0
    }
    
    for match in matches:
        if match.result:
            home_team = match.home
            away_team = match.away
            home_score = int(match.result.split('-')[0].strip())
            away_score = int(match.result.split('-')[1].strip())
            
            if home_team == team_name:
                stats['goals_scored'] += home_score
                stats['goals_conceded'] += away_score
                
                if home_score > away_score:
                    stats['wins'] += 1
                elif home_score == away_score:
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1
                    
                if away_score == 0:
                    stats['clean_sheets'] += 1
                    
            elif away_team == team_name:
                stats['goals_scored'] += away_score
                stats['goals_conceded'] += home_score
                
                if away_score > home_score:
                    stats['wins'] += 1
                elif away_score == home_score:
                    stats['draws'] += 1
                else:
                    stats['losses'] += 1
                    
                if home_score == 0:
                    stats['clean_sheets'] += 1
    
    return stats

# Flask-Login user loader
def load_user(user_id):
    """Load user by ID for Flask-Login"""
    return User.query.get(int(user_id))

# Helper to initialize OAuth within app context if needed
def get_oauth():
    """Helper to initialize OAuth within app context if needed"""
    if not current_app.config.get('GOOGLE_OAUTH_ENABLED'):
        return None
    
    try:
        from authlib.integrations.flask_client import OAuth
        oauth = OAuth(current_app)
        oauth.register(
            name='google',
            client_id=current_app.config.get('GOOGLE_CLIENT_ID'),
            client_secret=current_app.config.get('GOOGLE_CLIENT_SECRET'),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
        return oauth
    except Exception as e:
        logger.error(f"⚠️ OAuth Init Error: {e}")
        return None

# =========== ROUTE DEFINITIONS ===========

def create_routes(app):
    """Create all route functions with app decorators"""
    
    # Authentication Routes
    @app.route("/register", methods=['GET', 'POST'])
    def register():
        """User registration route"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        form = RegistrationForm()
        
        if request.method == 'POST' and form.validate_on_submit():
            try:
                # Check if user already exists
                existing_user = User.query.filter(
                    (User.email == form.email.data) | 
                    (User.username == form.username.data)
                ).first()
                
                if existing_user:
                    if existing_user.email == form.email.data:
                        flash('Email already registered! Please use a different email.', 'danger')
                    else:
                        flash('Username already taken! Please choose a different one.', 'danger')
                    return render_template('auth/register.html', form=form)
                
                # Check for pending registration
                pending = PendingRegistration.query.filter_by(email=form.email.data).first()
                if pending and not pending.is_expired():
                    # Resend code if still valid
                    flash('A verification code has already been sent to this email. Check your inbox.', 'info')
                    return redirect(url_for('verify_email', email=form.email.data))
                
                # Clean username
                raw_username = form.username.data.strip()
                clean_username = re.sub(r'\s+', ' ', raw_username)
                
                # Create user (but not verified yet)
                hashed_password = generate_password_hash(form.password.data)
                user = User(
                    username=clean_username,
                    email=form.email.data,
                    password_hash=hashed_password,
                    subscription_tier='free',
                    credits=5,
                    date_joined=datetime.utcnow(),
                    last_seen=datetime.utcnow(),
                    login_count=0,
                    is_verified=False
                )
                
                db.session.add(user)
                db.session.commit()
                
                # Generate and send verification code
                verification_code = user.generate_verification_code()
                
                # Send verification email using Celery
                celery_send_verification_email(user, verification_code)
                logger.info(f"Verification email sent to {user.email}")
                
                # Log the attempt
                log_activity(user.id, 'registration_started', 
                        f'User registered, verification code sent to {user.email}')
                
                flash('Registration successful! Please check your email for the verification code.', 'success')
                return redirect(url_for('verify_email', email=user.email))
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Registration error: {e}")
                flash(f'Registration failed: {str(e)}', 'danger')
        
        # Show form errors if validation failed
        if request.method == 'POST' and not form.validate():
            for field, errors in form.errors.items():
                for error in errors:
                    flash(f"{getattr(form, field).label.text}: {error}", 'danger')
        
        return render_template('auth/register.html', title='Register', form=form)
    
    
    @app.route("/verify-email", methods=['GET', 'POST'])
    def verify_email():
        """Email verification page"""
        if current_user.is_authenticated and current_user.is_verified:
            return redirect(url_for('dashboard'))
        
        email = request.args.get('email', '')
        form = VerificationForm()
        
        # If no email provided and user not logged in, redirect to register
        if not email and not current_user.is_authenticated:
            flash('Please register first or provide your email.', 'warning')
            return redirect(url_for('register'))
        
        # Get user
        if current_user.is_authenticated:
            user = current_user
        else:
            user = User.query.filter_by(email=email).first()
        
        if not user:
            flash('User not found. Please register first.', 'danger')
            return redirect(url_for('register'))
        
        if user.is_verified:
            flash('Your email is already verified!', 'success')
            return redirect(url_for('login'))
        
        # Check if user has a valid code
        if not user.verification_code or datetime.utcnow() > user.verification_code_expiry:
            # Generate new code if expired
            user.generate_verification_code()
            db.session.commit()
            
            # Send verification email using Celery
            celery_send_verification_email(user, user.verification_code)
            flash('A new verification code has been sent to your email.', 'info')
        
        if form.validate_on_submit():
            code = form.verification_code.data
            
            logger.info(f"Verifying code for user {user.email}: entered '{code}', stored '{user.verification_code}'")
            
            if user.verify_code(code):
                # Mark as verified
                user.is_verified = True
                
                # Send welcome email using Celery
                celery_send_welcome_email(user)
                
                # Log the verification
                log_activity(user.id, 'email_verified', 'User verified email successfully')
                
                flash('🎉 Email verified successfully! You can now log in.', 'success')
                
                logger.info(f"User {user.email} verified successfully, redirecting to dashboard")
                
                # Log the user in if they're on verification page
                if not current_user.is_authenticated:
                    login_user(user)
                    user.last_login = datetime.utcnow()
                    user.login_count += 1
                    db.session.commit()
                    return redirect(url_for('dashboard'))
                else:
                    return redirect(url_for('dashboard'))
            else:
                # Check if too many attempts
                if user.verification_attempts >= 3:
                    flash('Too many failed attempts. A new code has been sent to your email.', 'danger')
                    user.generate_verification_code()
                    db.session.commit()
                    
                    # Send new verification email using Celery
                    celery_send_verification_email(user, user.verification_code)
                else:
                    attempts_left = 3 - user.verification_attempts
                    flash(f'Invalid verification code. {attempts_left} attempts remaining.', 'danger')
        
        # Show remaining time
        remaining_time = None
        if user.verification_code_expiry:
            remaining = user.verification_code_expiry - datetime.utcnow()
            if remaining.total_seconds() > 0:
                remaining_time = int(remaining.total_seconds() / 60)  # Minutes
        
        return render_template('auth/verify_email.html',
                            form=form,
                            user=user,
                            email=user.email,
                            username=user.username,
                            remaining_time=remaining_time,
                            can_resend=user.can_resend_code(),
                            title='Verify Your Email')

    @app.route("/resend-verification", methods=['POST'])
    def resend_verification():
        """Resend verification code"""
        email = request.form.get('email', '')
        
        if not email and not current_user.is_authenticated:
            return jsonify({'success': False, 'message': 'Email required'}), 400
        
        # Get user
        if current_user.is_authenticated:
            user = current_user
        else:
            user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'success': False, 'message': 'User not found'}), 404
        
        if user.is_verified:
            return jsonify({'success': False, 'message': 'Email already verified'}), 400
        
        # Check if we can resend
        if not user.can_resend_code():
            return jsonify({
                'success': False, 
                'message': 'Please wait before requesting a new code'
            }), 429  # Too Many Requests
        
        # Generate new code
        verification_code = user.generate_verification_code()
        
        # Send email using Celery
        celery_send_verification_email(user, verification_code)
        logger.info(f"Verification email sent to {user.email}")
        
        log_activity(user.id, 'verification_resent', 'User requested new verification code')
        
        return jsonify({
            'success': True,
            'message': 'New verification code sent to your email'
        })

    @app.route("/verify/<token>")
    def verify_email_token(token):
        """Verify email via token link (from email)"""
        try:
            # Decode token
            from itsdangerous import URLSafeTimedSerializer
            s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
            email = s.loads(token, max_age=3600)  # 1 hour expiry
            
            user = User.query.filter_by(email=email).first()
            if not user:
                flash('Invalid verification link.', 'danger')
                return redirect(url_for('register'))
            
            if user.is_verified:
                flash('Email already verified!', 'info')
            else:
                user.is_verified = True
                user.verification_code = None
                user.verification_code_expiry = None
                db.session.commit()
                
                # Send welcome email using Celery
                celery_send_welcome_email(user)
                
                log_activity(user.id, 'email_verified_via_link', 'User verified via email link')
                
                flash('🎉 Email verified successfully!', 'success')
            
            # Log the user in
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            user.login_count += 1
            db.session.commit()
            
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            flash('Verification link is invalid or has expired.', 'danger')
            return redirect(url_for('register'))
    
    @app.route("/login", methods=['GET', 'POST'])
    def login():
        """User login route"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        form = LoginForm()
        
        if form.validate_on_submit():
            email_or_username = form.email.data.strip()
            
            logger.info(f"Login attempt: {email_or_username}")
            
            # Find user
            user = User.query.filter(
                (User.email == email_or_username) | 
                (User.username == email_or_username)
            ).first()
            
            logger.info(f"User found: {user.email if user else 'None'}")
            
            if user and user.check_password(form.password.data):
                logger.info(f"Password check passed for {user.email}")
                
                # Check if email is verified
                if not user.is_verified:
                    logger.info(f"User {user.email} not verified, sending code")
                    
                    # Generate new verification code
                    user.generate_verification_code()
                    
                    # Send verification email using Celery
                    celery_send_verification_email(user, user.verification_code)
                    
                    flash('⚠️ Please verify your email address first. A new verification code has been sent.', 'warning')
                    return redirect(url_for('verify_email', email=user.email))
                
                # Login successful
                logger.info(f"Login successful for {user.email}")
                
                login_user(user, remember=form.remember.data)
                user.last_login = datetime.utcnow()
                user.login_count += 1
                db.session.commit()
                
                log_activity(user.id, 'login', 'User logged in')
                
                next_page = request.args.get('next')
                if not next_page or url_parse(next_page).netloc != '':
                    next_page = url_for('dashboard')
                
                flash('Login successful!', 'success')
                return redirect(next_page)
            else:
                logger.info(f"Login failed for {email_or_username}: user={bool(user)}, password_check={user.check_password(form.password.data) if user else False}")
                
                flash('Login unsuccessful. Please check credentials and try again.', 'danger')
        
        return render_template('auth/login.html', title='Login', form=form)

    @app.route("/logout")
    @login_required
    def logout():
        """User logout route"""
        log_activity(current_user.id, 'logout', 'User logged out')
        logout_user()
        flash('You have been logged out.', 'info')
        return redirect(url_for('home'))
    

    @app.route("/reset_password_request", methods=['GET', 'POST'])
    def reset_password_request():
        """Request password reset"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        form = ResetPasswordRequestForm()
        if form.validate_on_submit():
            user = User.query.filter_by(email=form.email.data).first()
            if user:
                # Send password reset email using Celery
                celery_send_password_reset_email(user)
                
                log_activity(user.id, 'password_reset_requested', 'User requested password reset')
                
            flash('Check your email for instructions to reset your password.', 'info')
            return redirect(url_for('login'))
        return render_template('auth/reset_password_request.html',
                               title='Reset Password', 
                               form=form, 
                               mode='request')

    @app.route("/reset_password/<token>", methods=['GET', 'POST'])
    def reset_password(token):
        """Reset password with token"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        user = User.verify_reset_token(token)
        if not user:
            flash('That is an invalid or expired token.', 'warning')
            return redirect(url_for('reset_password_request'))
        form = ResetPasswordForm()
        if form.validate_on_submit():
            user.password_hash = generate_password_hash(form.password.data)
            db.session.commit()
            flash('Your password has been updated!', 'success')
            return redirect(url_for('login'))
        return render_template('auth/reset_password.html',form=form, title='Set New Password', mode='reset', token_valid=True)

    # Google OAuth Routes
    @app.route("/login/google")
    def google_login():
        """Initiate Google OAuth login"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        oauth = get_oauth()
        if not oauth:
            flash('Google OAuth is not configured. Please contact administrator.', 'danger')
            return redirect(url_for('login'))
        
        try:
            # Generate the redirect URI - must match EXACTLY what's in Google Cloud Console
            callback_url = url_for('google_authorize', _external=True)  # CHANGED THIS LINE
            logger.info(f"Google OAuth redirect URI: {callback_url}")
            
            # Redirect to Google for authentication
            return oauth.google.authorize_redirect(callback_url)
           #state=secrets.token_urlsafe(16))  # CSRF protection
            
        except Exception as e:
            logger.error(f"Google OAuth redirect error: {e}", exc_info=True)
            flash('Google OAuth configuration error. Please try again later.', 'danger')
            return redirect(url_for('login'))

    @app.route("/auth/google/callback")  # CHANGED THIS LINE
    def google_authorize():  # CHANGED THIS LINE
        """Google OAuth callback handler"""
        if current_user.is_authenticated:
            return redirect(url_for('home'))
        
        oauth = get_oauth()
        if not oauth:
            flash('Google OAuth is not configured.', 'danger')
            return redirect(url_for('login'))
        
        try:
            
             # Debug: Log all request parameters
            logger.info(f"📨 Callback received. Args: {dict(request.args)}")
            
            # Check for error parameter (user might have denied)
            if 'error' in request.args:
                error = request.args.get('error')
                error_desc = request.args.get('error_description', '')
                logger.error(f"Google OAuth error: {error} - {error_desc}")
                flash(f'Google OAuth error: {error}. Please try again.', 'danger')
                return redirect(url_for('login'))
            
            # Check for authorization code
            if 'code' not in request.args:
                logger.error("No authorization code in callback")
                flash('Authorization failed. No code returned from Google.', 'danger')
                return redirect(url_for('login'))
            
            print(f"✅ [GOOGLE OAUTH] Authorization code received: {request.args.get('code')[:20]}...")
        
            # Get authorization code from Google
            token = oauth.google.authorize_access_token()
            logger.info(f"Google OAuth token received: {token.keys() if token else 'No token'}")
            
            userinfo_endpoint = 'https://www.googleapis.com/oauth2/v3/userinfo'
            resp = oauth.google.get(userinfo_endpoint)
            
            # Get user info from Google
            resp = oauth.google.get('https://www.googleapis.com/oauth2/v3/userinfo')
            logger.info(f"Google API response status: {resp.status_code}")
            if resp.status_code != 200:
                logger.error(f"Failed to get user info from Google: {resp.text}")
                flash('Failed to get user info from Google.', 'danger')
                return redirect(url_for('login'))
            
            user_info = resp.json()
            logger.info(f"Google API response data: {user_info}")
            email = user_info.get('email')
            if not email:
                flash('Email not provided by Google.', 'danger')
                return redirect(url_for('login'))
            
            # Check if user already exists
            user = User.query.filter_by(email=email).first()
            
            if not user:
                # Create new user from Google info
                username = user_info.get('name', email.split('@')[0])
                
                # Ensure username is unique
                base_username = username
                counter = 1
                while User.query.filter_by(username=username).first():
                    username = f"{base_username}_{counter}"
                    counter += 1
                
                # Generate random password for OAuth users
                random_password = generate_random_password()
                
                # Create user WITHOUT is_oauth_user field if it doesn't exist
                user_kwargs = {
                    'username': username,
                    'email': email,
                    'password_hash': generate_password_hash(random_password),
                    'created_at': datetime.utcnow(),
                    'last_login': datetime.utcnow(),
                    'login_count': 1,
                    'is_verified': True,  # Google emails are already verified
                    'is_active': True,
                    'subscription_tier': 'free',
                    'credits': 5
                }
                
                # Only add is_oauth_user if the field exists
                try:
                    # Try to create with is_oauth_user
                    user = User(**user_kwargs)
                    # Check if we can set the attribute (field might not exist)
                    if hasattr(user, 'is_oauth_user'):
                        user.is_oauth_user = True
                except Exception as e:
                    # If it fails, create without is_oauth_user
                    logger.warning(f"is_oauth_user field might not exist: {e}")
                    user = User(**user_kwargs)
                
                db.session.add(user)
                db.session.commit()
                
                # Send welcome email using Celery
                celery_send_welcome_email(user)
                
                flash('Account created successfully with Google!', 'success')
                logger.info(f"Created new user via Google OAuth: {email}")
            
            # Log the user in
            login_user(user, remember=True)
            user.last_login = datetime.utcnow()
            user.login_count += 1
            db.session.commit()
            
            log_activity(user.id, 'oauth_login', f'Logged in via Google')
            
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
            
        except Exception as e:
            logger.error(f"Google OAuth error: {e}", exc_info=True)
            flash(f'Google login failed: {str(e)}', 'danger')
            return redirect(url_for('login'))

    # ADD THIS NEW ROUTE FOR BACKWARD COMPATIBILITY
    @app.route("/login/google/callback")
    def google_authorize_legacy():
        """Legacy Google OAuth callback for backward compatibility"""
        # Simply redirect to the new callback URL
        return redirect(url_for('google_authorize'))
    
    @app.route("/debug/login")
    def debug_login():
        """Debug login status"""
        return {
            'authenticated': current_user.is_authenticated,
            'user_id': current_user.id if current_user.is_authenticated else None,
            'username': current_user.username if current_user.is_authenticated else None,
            'email': current_user.email if current_user.is_authenticated else None,
            'is_verified': current_user.is_verified if current_user.is_authenticated else None
        }
        
    @app.route('/favicon.ico')
    def favicon():
        """Serve favicon.ico"""
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                'favicon.ico', mimetype='image/vnd.microsoft.icon')

    @app.route('/favicon.svg')
    def favicon_svg():
        """Serve favicon.svg"""
        return send_from_directory(os.path.join(app.root_path, 'static'),
                                'favicon.svg', mimetype='image/svg+xml')
        
    @app.route('/guest_demo')
    def guest_demo():
        """Allow guests to try predictions without registration"""
        # Check if user is already logged in
        if current_user.is_authenticated:
            return redirect(url_for('dashboard'))
        
        # Create a session for guest user
        session['guest'] = True
        session['guest_expiry'] = datetime.now() + timedelta(hours=1)
        
        # Get today's date and matches for the next 7 days
        today = date.today()
        selected_date_str = str(today)
        
        # Query REAL matches from database
        matches = []
        try:
            matches = Match.query.filter(
                Match.date >= selected_date_str,
                Match.date <= str(today + timedelta(days=7))
            ).order_by(Match.date.asc(), Match.time.asc()).all()
            
            # If no matches in database, show informative message
            if not matches:
                # Try to get matches for today only
                matches = Match.query.filter_by(date=selected_date_str).order_by(Match.time.asc()).all()
                
        except Exception as e:
            logger.error(f"Error fetching matches for guest demo: {e}")
            matches = []
        
        # Get popular teams for suggestions
        popular_teams = []
        try:
            # Get teams with most matches
            from sqlalchemy import func
            popular_teams = db.session.query(
                Match.home.label('team'),
                func.count(Match.id).label('count')
            ).group_by(Match.home).order_by(func.count(Match.id).desc()).limit(10).all()
            
            popular_teams = [team[0] for team in popular_teams]
        except:
            popular_teams = []
        
        # Count total matches and leagues
        total_matches = Match.query.filter(Match.date >= str(today)).count()
        total_leagues = League.query.count()
        
        # Show demo page with real matches
        return render_template('public/guest_demo.html', 
                            matches=matches, 
                            selected_date=selected_date_str,
                            total_matches=total_matches,
                            total_leagues=total_leagues,
                            popular_teams=popular_teams,
                            title='Guest Demo - ScorePulse AI')
        
    @app.route("/api/demo/team-stats/<team_name>")
    def get_demo_team_stats(team_name):
        """Get team statistics for demo mode"""
        try:
            # Get team's recent matches
            matches = Match.query.filter(
                (Match.home == team_name) | (Match.away == team_name)
            ).order_by(Match.date.desc()).limit(10).all()
            
            if not matches:
                return jsonify({
                    'success': True,
                    'team': team_name,
                    'stats': {
                        'total_matches': 0,
                        'wins': 0,
                        'losses': 0,
                        'draws': 0,
                        'goals_scored': 0,
                        'goals_conceded': 0,
                        'win_rate': 0,
                        'avg_goals': 0
                    },
                    'recent_matches': [],
                    'message': 'No recent matches found for this team'
                })
            
            # Calculate basic stats
            stats = {
                'total_matches': len(matches),
                'wins': 0,
                'losses': 0,
                'draws': 0,
                'goals_scored': 0,
                'goals_conceded': 0
            }
            
            recent_matches = []
            for match in matches:
                # Simplified match result check
                is_home = match.home == team_name
                home_score = getattr(match, 'home_score', None)
                away_score = getattr(match, 'away_score', None)
                
                if home_score is not None and away_score is not None:
                    if is_home:
                        stats['goals_scored'] += home_score
                        stats['goals_conceded'] += away_score
                        if home_score > away_score:
                            stats['wins'] += 1
                        elif home_score < away_score:
                            stats['losses'] += 1
                        else:
                            stats['draws'] += 1
                    else:
                        stats['goals_scored'] += away_score
                        stats['goals_conceded'] += home_score
                        if away_score > home_score:
                            stats['wins'] += 1
                        elif away_score < home_score:
                            stats['losses'] += 1
                        else:
                            stats['draws'] += 1
                    
                    # Add to recent matches
                    recent_matches.append({
                        'date': match.date.strftime('%Y-%m-%d') if hasattr(match.date, 'strftime') else str(match.date),
                        'home': match.home,
                        'away': match.away,
                        'score': f"{home_score}-{away_score}" if home_score is not None and away_score is not None else 'N/A',
                        'result': 'W' if (is_home and home_score > away_score) or (not is_home and away_score > home_score) else 
                                'L' if (is_home and home_score < away_score) or (not is_home and away_score < home_score) else 
                                'D'
                    })
            
            # Calculate derived stats
            if stats['total_matches'] > 0:
                stats['win_rate'] = round((stats['wins'] / stats['total_matches']) * 100, 1)
                stats['avg_goals'] = round(stats['goals_scored'] / stats['total_matches'], 1)
            else:
                stats['win_rate'] = 0
                stats['avg_goals'] = 0
            
            return jsonify({
                'success': True,
                'team': team_name,
                'stats': stats,
                'recent_matches': recent_matches[:5]  # Return only last 5 matches
            })
            
        except Exception as e:
            logger.error(f"Error getting team stats for {team_name}: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route("/api/demo/head-to-head/<team1>/<team2>")
    def get_demo_head_to_head(team1, team2):
        """Get head-to-head statistics for demo mode"""
        try:
            # Get matches between the two teams
            matches = Match.query.filter(
                ((Match.home == team1) & (Match.away == team2)) |
                ((Match.home == team2) & (Match.away == team1))
            ).order_by(Match.date.desc()).limit(10).all()
            
            stats = {
                'total_matches': len(matches),
                'team1_wins': 0,
                'team2_wins': 0,
                'draws': 0,
                'team1_goals': 0,
                'team2_goals': 0
            }
            
            h2h_matches = []
            for match in matches:
                home_score = getattr(match, 'home_score', None)
                away_score = getattr(match, 'away_score', None)
                
                if home_score is not None and away_score is not None:
                    stats['team1_goals'] += home_score if match.home == team1 else away_score
                    stats['team2_goals'] += away_score if match.home == team1 else home_score
                    
                    if home_score > away_score:
                        if match.home == team1:
                            stats['team1_wins'] += 1
                        else:
                            stats['team2_wins'] += 1
                    elif home_score < away_score:
                        if match.home == team1:
                            stats['team2_wins'] += 1
                        else:
                            stats['team1_wins'] += 1
                    else:
                        stats['draws'] += 1
                    
                    h2h_matches.append({
                        'date': match.date.strftime('%Y-%m-%d') if hasattr(match.date, 'strftime') else str(match.date),
                        'home': match.home,
                        'away': match.away,
                        'score': f"{home_score}-{away_score}",
                        'winner': team1 if (match.home == team1 and home_score > away_score) or 
                                        (match.away == team1 and away_score > home_score) else
                                team2 if (match.home == team2 and home_score > away_score) or 
                                        (match.away == team2 and away_score > home_score) else
                                'Draw'
                    })
            
            # Calculate percentages
            if stats['total_matches'] > 0:
                stats['team1_win_percentage'] = round((stats['team1_wins'] / stats['total_matches']) * 100, 1)
                stats['team2_win_percentage'] = round((stats['team2_wins'] / stats['total_matches']) * 100, 1)
                stats['draw_percentage'] = round((stats['draws'] / stats['total_matches']) * 100, 1)
            else:
                stats['team1_win_percentage'] = 0
                stats['team2_win_percentage'] = 0
                stats['draw_percentage'] = 0
            
            return jsonify({
                'success': True,
                'team1': team1,
                'team2': team2,
                'stats': stats,
                'matches': h2h_matches
            })
            
        except Exception as e:
            logger.error(f"Error getting head-to-head stats: {e}")
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    @app.route("/api/demo/predict/<home>/<away>")
    def demo_predict(home, away):
        """Demo prediction endpoint that redirects to register"""
        return jsonify({
            'success': False,
            'message': 'Please register to access AI predictions',
            'redirect': url_for('register'),
            'match': {
                'home': home,
                'away': away
            }
        })


    # Main Routes - UPDATED WITH REDIS CACHING
    @app.route("/")
    @app.route("/home")
    def home():
        """Home page with matches and predictions"""
        today = date.today()
        selected_date_str = request.args.get('date', str(today))
        
        try:
            selected_date_str = request.args.get('date', str(date.today()))
            selected_date = datetime.strptime(selected_date_str, '%Y-%m-%d').date()
        except (ValueError, TypeError):
            selected_date = date.today()
            selected_date_str = str(selected_date)

        matches = []
        
        # Try to get from cache first
        cached_matches = get_cached_matches(selected_date_str)
        if cached_matches is not None:
            print(f"✅ Using cached matches for {selected_date_str}")
            matches = cached_matches
        else:
            print(f"🔄 Cache miss for matches on {selected_date_str}")
            try:
                matches = Match.query.filter(
                    Match.date >= selected_date_str,
                    Match.date <= str(selected_date + timedelta(days=7))
                ).order_by(Match.date.asc(), Match.time.asc()).all()
                
                if not matches and selected_date == date.today() and ai_engine:
                    if hasattr(ai_engine, 'get_upcoming_matches'):
                        ai_matches = ai_engine.get_upcoming_matches(count=20)
                        for ai_match in ai_matches:
                            match = Match(
                                date=ai_match.get('date', selected_date_str),
                                time="12:00",
                                league=ai_match.get('league', 'Unknown'),
                                home_team=ai_match.get('home', 'Unknown'),
                                away_team=ai_match.get('away', 'Unknown')
                            )
                            matches.append(match)
                
                # Cache the matches
                cache_match_list(selected_date_str, matches)
                
            except Exception as e:
                logger.error(f"Error in home route: {e}")
                if not matches:
                    matches = []
        
        now = datetime.now()
        for match in matches:
            match.is_live = False
            if selected_date_str == str(date.today()) and match.time:
                try:
                    # Parse time - handle both 12-hour and 24-hour formats
                    time_str = str(match.time).strip().upper()
                    
                    # Remove any extra spaces
                    time_str = re.sub(r'\s+', ' ', time_str)
                    
                    # Try different time formats
                    time_formats = [
                        '%H:%M',        # 24-hour: 03:00, 18:30
                        '%I:%M %p',     # 12-hour with AM/PM: 3:00 AM, 6:30 PM
                        '%I:%M%p',      # 12-hour without space: 3:00AM, 6:30PM
                        '%H:%M:%S',     # 24-hour with seconds: 03:00:00
                    ]
                    
                    match_time_obj = None
                    for fmt in time_formats:
                        try:
                            match_time_obj = datetime.strptime(time_str, fmt).time()
                            break
                        except ValueError:
                            continue
                    
                    if match_time_obj:
                        match_datetime = datetime.combine(date.today(), match_time_obj)
                        
                        if match_datetime <= now <= (match_datetime + timedelta(minutes=115)):
                            match.is_live = True
                    else:
                        logger.debug(f"Could not parse time: {match.time}")
                        
                except Exception as time_err:
                    # Don't log every single error - just debug level
                    logger.debug(f"Time parsing for '{match.time}': {time_err}")
                    continue

        # Convert matches to dictionary format for template
        matches_data = []
        for match in matches:
            try:
                # Get league name safely
                league_name = 'Unknown'
                if hasattr(match, 'league_name_str') and match.league_name_str:
                    league_name = match.league_name_str
                elif match.league and hasattr(match.league, 'name'):
                    league_name = match.league.name
                
                match_data = {
                    'id': match.id,
                    'date': match.date,
                    'time': match.time,
                    'league': league_name,
                    'home_team': match.home_team.name if match.home_team else (match.home or 'Unknown'),
                    'away_team': match.away_team.name if match.away_team else (match.away or 'Unknown'),
                    'home_odds': match.home_odds,
                    'draw_odds': match.draw_odds,
                    'away_odds': match.away_odds,
                    'match_status': match.match_status,
                    'is_live': getattr(match, 'is_live', False)
                }
                matches_data.append(match_data)
            except Exception as e:
                logger.error(f"Error processing match {match.id}: {e}")
                continue
        
        # Fix the sorting issue - ensure we sort by league name
        matches_data.sort(key=lambda x: x['league'])
        
        total_matches = Match.query.filter(Match.date >= str(today)).count()
        total_leagues = League.query.count()

        # Get top predictions for today
        top_predictions = []
        if current_user.is_authenticated:
            cache_key_tp = f"top_predictions_{selected_date_str}"
            top_predictions = current_app.cache.get(cache_key_tp) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if top_predictions is None and ai_engine:
                try:
                    if hasattr(ai_engine, 'get_top_predictions'):
                        top_predictions = ai_engine.get_top_predictions(date=selected_date_str, limit=5)
                    elif hasattr(ai_engine, 'get_premium_batch'):
                        top_predictions = ai_engine.get_premium_batch(count=5)
                    
                    if hasattr(current_app, 'cache') and current_app.cache:
                        current_app.cache.set(cache_key_tp, top_predictions, timeout=1800)
                except Exception as e:
                    logger.error(f"Error getting top predictions: {e}")
                    top_predictions = []

        return render_template('public/home.html', 
                            matches=matches_data, 
                            selected_date=selected_date_str,
                            total_matches=total_matches,
                            total_leagues=total_leagues,
                            top_predictions=top_predictions)
    
    @app.route("/offline")
    def offline():
        """Offline page for when users lose internet connection"""
        return render_template('public/offline.html')
    
    @app.route("/neural_networks")
    def neural_networks():
        """Neural Networks explanation page"""
        return render_template('public/neural_networks.html')
    
    @app.route("/real_time_data")
    def real_time_data():
        """Real-time data pipeline explanation page"""
        return render_template('public/real_time_data.html')
    
    @app.route("/probability_intelligence")
    def probability_intelligence():
        """Probability Intelligence explanation page"""
        return render_template('public/probability_intelligence.html')
    
    @app.route("/pricing")
    def pricing():
        """Display pricing plans page"""
        # Get current user's plan status if logged in
        user_plan = None
        if current_user.is_authenticated:
            days_remaining = 0
            if current_user.premium_expiry:
                delta = current_user.premium_expiry - datetime.utcnow()
                days_remaining = max(0, delta.days)
                
            user_plan = {
                'is_premium': getattr(current_user, 'is_premium', False),
                'premium_expiry': getattr(current_user, 'premium_expiry', None),
                'days_left': days_remaining
            }
        
        # Pricing plans data
        plans = [
            {
                'name': 'Starter',
                'price': 0,
                'currency': 'KES',
                'period': 'free',
                'features': [
                    'Basic match predictions',
                    '10 predictions per day',
                    'Win/Loss predictions only',
                    'Basic statistics',
                    'Email support'
                ],
                'button_text': 'Get Started Free',
                'button_link': url_for('register'),
                'popular': False
            },
            {
                'name': 'Silver Pro',
                'price': 500,
                'currency': 'KES',
                'period': 'month',
                'annual_price': 4800,
                'features': [
                    'Unlimited daily predictions',
                    'Advanced Random Forest Model',
                    'Over/Under & Both Teams to Score',
                    'Detailed match statistics',
                    'Priority customer support',
                    'Value bet alerts'
                ],
                'button_text': 'Choose Silver Pro',
                'button_link': url_for('payment'),
                'popular': True
            },
            {
                'name': 'Gold Elite',
                'price': 1200,
                'currency': 'KES',
                'period': 'month',
                'annual_price': 11520,
                'features': [
                    'Everything in Silver Pro',
                    'Advanced Neural Network Model',
                    'Confidence scores & probability %',
                    'Value bet identification',
                    '24/7 premium support',
                    'Custom model training',
                    'API access'
                ],
                'button_text': 'Upgrade to Gold Elite',
                'button_link': url_for('payment'),
                'popular': False
            }
        ]
        
        return render_template('public/pricing.html', 
                            plans=plans, 
                            user_plan=user_plan,
                            title='Pricing Plans')
        
    
    @app.route("/contact", methods=['GET', 'POST'])
    def contact():
        """Contact page for users to send inquiries"""
        # Simple contact form handling
        if request.method == 'POST':
            try:
                name = request.form.get('name', '').strip()
                email = request.form.get('email', '').strip()
                subject = request.form.get('subject', '').strip()
                message = request.form.get('message', '').strip()
                contact_type = request.form.get('type', 'general')
                
                # Basic validation
                if not all([name, email, subject, message]):
                    flash('Please fill in all required fields.', 'danger')
                    return redirect(url_for('contact'))
                
                if not '@' in email or not '.' in email:
                    flash('Please provide a valid email address.', 'danger')
                    return redirect(url_for('contact'))
                
                # Log the contact attempt
                if current_user.is_authenticated:
                    log_activity(current_user.id, 'contact_form', 
                            f'Submitted contact form: {subject}')
                
                # In a real app, you would:
                # 1. Save to database
                # 2. Send email notification
                # 3. Maybe send auto-response
                
                # For now, simulate saving contact
                contact_data = {
                    'name': name,
                    'email': email,
                    'subject': subject,
                    'message': message,
                    'type': contact_type,
                    'timestamp': datetime.utcnow().isoformat(),
                    'user_id': current_user.id if current_user.is_authenticated else None,
                    'ip_address': request.remote_addr
                }
                
                # Log contact attempt
                logger.info(f"Contact form submitted: {contact_data}")
                
                # You could save to a Contact model if you create one
                # For now, just show success message
                
                flash('Thank you for your message! We\'ll get back to you within 24 hours.', 'success')
                
                # Redirect to prevent form resubmission
                return redirect(url_for('contact'))
                
            except Exception as e:
                logger.error(f"Error processing contact form: {e}")
                flash('Sorry, there was an error sending your message. Please try again.', 'danger')
                return redirect(url_for('contact'))
        
        # GET request - show contact form
        # Pre-fill form if user is logged in
        form_data = {}
        if current_user.is_authenticated:
            form_data = {
                'name': current_user.username,
                'email': current_user.email
            }
        
        # Contact information
        contact_info = {
            'email': 'support@scorepulse.ai',
            'sales_email': 'sales@scorepulse.ai',
            'support_hours': 'Monday - Friday, 9 AM - 5 PM EAT',
            'response_time': 'Within 24 hours',
            'address': 'Nairobi, Kenya'
        }
        
        # FAQ data for contact page
        faqs = [
            {
                'question': 'How long does it take to get a response?',
                'answer': 'We typically respond to all inquiries within 24 hours during business days.'
            },
            {
                'question': 'Do you offer technical support?',
                'answer': 'Yes! Technical support is included with all paid plans. Free users can access our community forums.'
            },
            {
                'question': 'Can I get a demo of the premium features?',
                'answer': 'Absolutely! Contact our sales team for a personalized demo of our premium features.'
            },
            {
                'question': 'Do you offer refunds?',
                'answer': 'We offer a 7-day money-back guarantee for all paid plans. Contact support for refund requests.'
            }
        ]
        
        return render_template('public/contact.html',
                            form_data=form_data,
                            contact_info=contact_info,
                            faqs=faqs,
                            title='Contact Us')
        
        
    @app.route("/about")
    def about():
        """About page explaining the platform"""
        # Platform statistics (these would be calculated from your data)
        stats = {
            'accuracy': calculate_platform_accuracy(),
            'total_predictions': Prediction.query.count(),
            'active_users': User.query.filter(User.last_login >= datetime.utcnow() - timedelta(days=7)).count(),
            'total_matches': Match.query.count()
        }
        
        # Team information
        team_members = [
            {
                'name': 'AI Research Team',
                'role': 'Machine Learning Engineers',
                'description': 'Developing advanced prediction algorithms',
                'expertise': 'Neural Networks, Random Forests, Data Science'
            },
            {
                'name': 'Sports Analytics Team',
                'role': 'Football Analysts',
                'description': 'Analyzing match data and team performance',
                'expertise': 'Sports Statistics, Team Dynamics, Form Analysis'
            },
            {
                'name': 'Platform Team',
                'role': 'Full Stack Developers',
                'description': 'Building and maintaining the platform',
                'expertise': 'Flask, React, Database Architecture'
            }
        ]
        
        return render_template('public/about.html',
                            stats=stats,
                            team=team_members,
                            title='About Us')
            
    @app.route("/privacy")
    def privacy():
        """Privacy policy page"""
        return render_template('public/privacy.html', title='Privacy Policy')
    
    @app.route("/terms")
    def terms():
        """Terms of Service page"""
        return render_template('public/terms.html', title='Terms of Service')

    @app.route("/faq")
    def faq():
        """Frequently Asked Questions page"""
        faqs = [
            {
                'question': 'How accurate are the predictions?',
                'answer': 'Our AI models achieve 72-78% accuracy depending on the league and match conditions. Premium plans use more advanced models with higher accuracy rates.'
            },
            {
                'question': 'What leagues do you cover?',
                'answer': 'We cover 50+ domestic and international leagues including Premier League, La Liga, Serie A, Bundesliga, Ligue 1, Champions League, and Europa League.'
            },
            {
                'question': 'How often are predictions updated?',
                'answer': 'Predictions are updated in real-time as new data becomes available, including team news, lineups, and weather conditions.'
            },
            {
                'question': 'Can I use these predictions for betting?',
                'answer': 'Our predictions are for informational purposes only. We encourage responsible decision-making and compliance with local laws regarding sports betting.'
            },
            {
                'question': 'What payment methods do you accept?',
                'answer': 'We accept M-PESA for Kenyan customers and PayPal for international payments. All transactions are secure and encrypted.'
            },
            {
                'question': 'Is there a free trial?',
                'answer': 'Yes! Our Starter plan is completely free with 10 daily predictions. You can upgrade anytime to unlock unlimited predictions and advanced features.'
            },
            {
                'question': 'How do I cancel my subscription?',
                'answer': 'You can cancel anytime from your account settings. Cancellations take effect at the end of your current billing cycle.'
            },
            {
                'question': 'Do you offer refunds?',
                'answer': 'We offer a 7-day money-back guarantee for all paid plans. Contact support for refund requests.'
            }
        ]
        return render_template('public/faq.html', faqs=faqs, title='FAQ')
    
    
    # Prediction Route - UPDATED WITH REDIS CACHING
    @app.route("/predict", methods=['GET', 'POST'])
    @login_required
    def predict():
        """Page to make match predictions"""
        form = PredictForm()
        
        # Generate hierarchy for dynamic dropdowns - WITH CACHING
        if ai_engine:
            try:
                cache_key = "team_hierarchy"
                hierarchy = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
                if hierarchy is None:
                    hierarchy = ai_engine.get_team_hierarchy()
                    if hasattr(current_app, 'cache') and current_app.cache:
                        current_app.cache.set(cache_key, hierarchy, timeout=3600)  # 1 hour cache
            except Exception as e:
                logger.warning(f"Could not get team hierarchy from AI engine: {e}")
                hierarchy = {}
        else:
            # Fallback: Build simple hierarchy from database
            hierarchy = {}
            try:
                leagues = Match.query.with_entities(Match.league).distinct().all()
                for league_tuple in leagues:
                    league = league_tuple[0]
                    if league:
                        matches = Match.query.filter_by(league=league).all()
                        teams = set()
                        for match in matches:
                            if match.home_team: 
                                teams.add(match.home_team)
                            if match.away_team: 
                                teams.add(match.away_team)
                        hierarchy[league] = sorted(list(teams))
                        
            except Exception as e:
                logger.warning(f"Could not build hierarchy: {e}")
                hierarchy = {}
        
        # Transform hierarchy to map league codes to proper league names
        from config.constants import Constants
        transformed_hierarchy = {}
        for country, leagues_dict in hierarchy.items():
            transformed_hierarchy[country] = {}
            for league_code_or_name, teams in leagues_dict.items():
                # Check if this is a league code that needs mapping
                league_display_name = league_code_or_name
                if league_code_or_name in Constants.DIVISION_MAP:
                    # This is a league code, use the proper name from constants
                    _, league_display_name = Constants.DIVISION_MAP[league_code_or_name]
                transformed_hierarchy[country][league_display_name] = teams
        
        hierarchy = transformed_hierarchy
        
        # Populate team choices
        teams_list = get_all_teams()
        form.home_team.choices = [(team, team) for team in teams_list]
        form.away_team.choices = [(team, team) for team in teams_list]
        
        # Handle form submission
        if form.validate_on_submit():
            print(f"✅ [FORM] Form validated successfully")
            logger.info("Prediction form validated")
            home = form.home_team.data
            away = form.away_team.data
            print(f"📝 [FORM] Home: {home}, Away: {away}")
            
            # Validate teams are different
            if home == away:
                flash('Home and away teams cannot be the same.', 'danger')
                return redirect(url_for('predict'))
            
            # Check for cached prediction
            cache_key = cache_key_generator("prediction_result", home, away, current_user.subscription_tier)
            cached_result = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if cached_result is not None:
                print(f"✅ Using cached prediction for {home} vs {away}")
                result = cached_result
            else:
                print(f"🔄 Cache miss for {home} vs {away}")
                
                # Check if AI engine is available
                if not ai_engine:
                    flash('AI Prediction Engine is currently offline. Please try again later.', 'danger')
                    logger.error("AI Engine not available")
                    return redirect(url_for('predict'))
                
                # Check if user has prediction credits or is within limits
                if not current_user.can_make_prediction():
                    flash('Daily prediction limit reached! Please upgrade your plan.', 'warning')
                    return redirect(url_for('upgrade'))
                
                try:
                    print(f"🔮 [ROUTES] Starting prediction for: {home} vs {away}")
                    logger.info(f"Starting prediction: {home} vs {away}")
                    
                    # Get prediction from AI engine with correct method and subscription tier
                    subscription_tier = getattr(current_user, 'subscription_tier', 'free')
                    print(f"📊 Subscription tier: {subscription_tier}")
                    result = ai_engine.predict_for_web(home, away, subscription_tier)
                    print(f"✅ [ROUTES] AI Prediction received successfully")
                    logger.info(f"AI prediction generated successfully")
                    
                    # Check for AI engine errors
                    if 'error' in result:
                        flash(f'AI Prediction Error: {result["error"]}', 'danger')
                        logger.error(f"AI Engine error: {result['error']}")
                        return redirect(url_for('predict'))
                    
                    print(f"✅ [ROUTES] AI Prediction received successfully")
                    
                    # Cache the result for 30 minutes
                    if hasattr(current_app, 'cache') and current_app.cache:
                        current_app.cache.set(cache_key, result, timeout=1800)
                    
                    # ============================================
                    # Extract data from AI result
                    # ============================================
                    
                    # 1. Get AI's predicted outcome
                    ai_outcome = result.get('prediction_outcome', 'D')  # H, D, or A
                    
                    # 2. Get user's optional prediction from form
                    user_prediction = request.form.get('user_prediction', 'None')
                    if user_prediction == 'None':
                        user_prediction = None
                    
                    # 3. Determine final prediction (user's choice if provided, otherwise AI's)
                    final_outcome = user_prediction if user_prediction else ai_outcome
                    
                    # 4. Extract predicted score
                    score_data = result.get('score', {})
                    predicted_home_score = score_data.get('home', 0)
                    predicted_away_score = score_data.get('away', 0)
                    
                    # 5. Extract probabilities
                    win_prob = result.get('win_prob', {})
                    mcmc_home_prob = win_prob.get('home', result.get('mcmc_home_prob', 0))
                    mcmc_draw_prob = win_prob.get('draw', result.get('mcmc_draw_prob', 0))
                    mcmc_away_prob = win_prob.get('away', result.get('mcmc_away_prob', 0))
                    
                    # 6. Extract betting analysis
                    recommended_stake = result.get('recommended_stake', 2.5)
                    kelly_fraction = result.get('kelly_fraction', 0.5)
                    market_odds = result.get('market_odds', 2.5)
                    risk_level = result.get('risk_level', 'MEDIUM')
                    
                    # 7. Extract advanced stats
                    btts_probability = result.get('btts', 50.0)
                    over25_probability = result.get('over25', 50.0)
                    total_goals_pred = result.get('total_goals', 2.5)
                    
                    # 8. Extract confidence
                    confidence = result.get('prediction_confidence', result.get('confidence_score', 50.0))
                    
                    # 9. Get model used
                    model_used = result.get('model_used', 'Random Forest')
                    
                    # ============================================
                    # Save to Prediction model
                    # ============================================
                    
                    print(f"💾 [ROUTES] Saving prediction to database...")
                    
                    # Create new Prediction object
                    prediction = Prediction(
                        # Basic info
                        user_id=current_user.id,
                        home_team=home,
                        away_team=away,
                        match_date=date.today(),
                        
                        # Prediction outcomes
                        pred_outcome=final_outcome,          # Final prediction (user or AI)
                        ai_prediction=ai_outcome,            # AI's prediction
                        user_prediction=user_prediction,     # User's choice (if any)
                        
                        # Predicted scores
                        pred_home_score=predicted_home_score,
                        pred_away_score=predicted_away_score,
                        
                        # AI confidence and probabilities
                        confidence=confidence,
                        mcmc_home_prob=mcmc_home_prob,
                        mcmc_draw_prob=mcmc_draw_prob,
                        mcmc_away_prob=mcmc_away_prob,
                        
                        # Advanced stats
                        btts_probability=btts_probability,
                        over25_probability=over25_probability,
                        total_goals_pred=total_goals_pred,
                        
                        # Betting analysis
                        recommended_stake=recommended_stake,
                        kelly_fraction=kelly_fraction,
                        market_odds=market_odds,
                        risk_level=risk_level,
                        
                        # Model info
                        model_used=model_used,
                        
                        # Status and tracking
                        status='Pending',
                        created_at=datetime.utcnow(),
                        
                        # Default betting info (can be updated later)
                        odds=market_odds,  # Use same as market odds for now
                        stake=10.0,        # Default stake
                        potential_payout=market_odds * 10 if final_outcome == 'H' else 0,
                        
                        # Store analysis in notes
                        notes=f"AI Analysis:\n"
                            f"- Total Goals: {total_goals_pred:.1f}\n"
                            f"- BTTS Probability: {btts_probability:.1f}%\n"
                            f"- Over 2.5 Probability: {over25_probability:.1f}%\n"
                            f"- Risk Level: {risk_level}\n"
                            f"- Model: {model_used}"
                    )
                    
                    # Save to database
                    db.session.add(prediction)
                    db.session.commit()
                    
                    print(f"✅ [ROUTES] Prediction saved with ID: {prediction.id}")
                    
                    # ============================================
                    # Online Learning Integration
                    # ============================================
                    
                    # Store prediction in online learning system if available
                    if ai_engine and hasattr(ai_engine, 'prediction_storage') and ai_engine.prediction_storage:
                        try:
                            match_id = f"{home}_{away}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"
                            ai_engine.prediction_storage.store_prediction(
                                match_id=match_id,
                                home_team=home,
                                away_team=away,
                                match_date=datetime.utcnow().isoformat(),
                                predicted_data=result
                            )
                            print(f"📚 [ROUTES] Stored in online learning system with ID: {match_id}")
                        except Exception as e:
                            logger.error(f"Failed to store prediction in online learning: {e}")
                    
                    # ============================================
                    # Log Activity
                    # ============================================
                    
                    log_activity(current_user.id, 'prediction_made', 
                                f'{home} vs {away}: {final_outcome} (AI: {ai_outcome}, Confidence: {confidence}%)')
                    
                    # Update user's prediction count
                    current_user.predictions_today = getattr(current_user, 'predictions_today', 0) + 1
                    db.session.commit()
                    
                    # ============================================
                    # Show Success and Redirect
                    # ============================================
                    
                    flash(f'✅ Prediction generated successfully! Confidence: {confidence:.1f}%', 'success')
                    
                    # Redirect to the saved prediction view (RECOMMENDED)
                    return redirect(url_for('view_prediction', prediction_id=prediction.id))
                    
                except AttributeError as e:
                    # This catches the "predict() method doesn't exist" error
                    db.session.rollback()
                    logger.error(f"Critical: AI Engine method missing - {e}")
                    flash(f'System Error: AI Engine method not found. Please contact support. Error: {str(e)}', 'danger')
                    return redirect(url_for('predict'))
                    
                except Exception as e:
                    db.session.rollback()
                    logger.error(f"Prediction error: {e}", exc_info=True)
                    flash(f'Prediction failed: {str(e)}', 'danger')
                    return redirect(url_for('predict'))
        
        # ============================================
        # GET Request - Show prediction form
        # ============================================
        
        # Debug: Log form validation errors
        if request.method == 'POST' and not form.validate_on_submit():
            print(f"❌ [FORM] Form validation failed")
            print(f"📋 [FORM] Errors: {form.errors}")
            logger.warning(f"Form validation errors: {form.errors}")
        
        # Check for query parameters (for quick predictions)
        default_home = request.args.get('home', '')
        default_away = request.args.get('away', '')
        
        # If user came from a match page, pre-select teams
        if default_home and default_away:
            form.home_team.data = default_home
            form.away_team.data = default_away
        
        # Render the prediction form
        return render_template('features/predict.html', 
                            form=form, 
                            title='Make Prediction', 
                            hierarchy=hierarchy,
                            all_teams=teams_list,
                            default_home=default_home,
                            default_away=default_away)
    
    
        # Add to the routes section (around other prediction-related routes)

    @app.route("/performance", methods=['GET'])
    @login_required
    def prediction_performance():
        """User's prediction performance dashboard"""
        # Get performance summary
        summary = get_prediction_performance_summary(user_id=current_user.id)
        
        # Get recent performances
        recent_performances = PredictionPerformance.query.filter_by(
            user_id=current_user.id
        ).order_by(PredictionPerformance.match_date.desc()).limit(20).all()
        
        # Get best and worst predictions
        best_predictions = PredictionPerformance.query.filter_by(
            user_id=current_user.id,
            is_correct=True
        ).order_by(PredictionPerformance.profit_loss.desc()).limit(5).all()
        
        worst_predictions = PredictionPerformance.query.filter_by(
            user_id=current_user.id,
            is_correct=False
        ).order_by(PredictionPerformance.profit_loss).limit(5).all()
        
        # Calculate streak
        streak = calculate_current_streak(current_user.id)
        
        # Get model performance
        model_performances = db.session.query(
            PredictionPerformance.model_used,
            func.count(PredictionPerformance.id).label('total'),
            func.sum(case((PredictionPerformance.is_correct == True, 1), else_=0)).label('correct'),
            func.avg(PredictionPerformance.confidence_score).label('avg_confidence')
        ).filter_by(
            user_id=current_user.id
        ).group_by(PredictionPerformance.model_used).all()
        
        return render_template('features/performance.html',
                            summary=summary,
                            recent_performances=recent_performances,
                            best_predictions=best_predictions,
                            worst_predictions=worst_predictions,
                            streak=streak,
                            model_performances=model_performances,
                            title='Prediction Performance')
    
    @app.route("/api/performance/summary")
    @login_required
    def api_performance_summary():
        """API endpoint for performance summary"""
        try:
            # Get query parameters
            start_date = request.args.get('start_date')
            end_date = request.args.get('end_date')
            model = request.args.get('model')
            
            # Parse dates if provided
            start_date_obj = None
            end_date_obj = None
            
            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            summary = get_prediction_performance_summary(
                user_id=current_user.id,
                start_date=start_date_obj,
                end_date=end_date_obj,
                model=model
            )
            
            return jsonify(summary)
            
        except Exception as e:
            logger.error(f"Error getting performance summary: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route("/api/performance/report")
    @login_required
    def api_performance_report():
        """Generate performance report"""
        try:
            report_type = request.args.get('type', 'monthly')
            
            # Use Celery if available for report generation
            if CELERY_AVAILABLE:
                task = generate_user_report.delay(current_user.id, report_type)
                
                return jsonify({
                    'success': True,
                    'message': 'Report generation queued',
                    'task_id': task.id,
                    'report_type': report_type
                })
            else:
                # Generate report synchronously
                report = generate_performance_report(current_user.id, report_type)
                return jsonify(report)
                
        except Exception as e:
            logger.error(f"Error generating performance report: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route("/api/performance/chart")
    @login_required
    def api_performance_chart():
        """Get performance data for charts"""
        try:
            # Get date range (default: last 30 days)
            days = int(request.args.get('days', 30))
            end_date = date.today()
            start_date = end_date - timedelta(days=days)
            
            # Query daily performance
            daily_data = db.session.query(
                func.date(PredictionPerformance.match_date).label('date'),
                func.count(PredictionPerformance.id).label('total'),
                func.sum(case((PredictionPerformance.is_correct == True, 1), else_=0)).label('correct'),
                func.sum(PredictionPerformance.profit_loss).label('profit')
            ).filter(
                PredictionPerformance.user_id == current_user.id,
                PredictionPerformance.match_date >= start_date,
                PredictionPerformance.match_date <= end_date
            ).group_by(func.date(PredictionPerformance.match_date)).order_by('date').all()
            
            # Format data for chart
            dates = []
            totals = []
            accuracies = []
            profits = []
            
            for day in daily_data:
                dates.append(day.date.strftime('%Y-%m-%d') if day.date else 'Unknown')
                totals.append(day.total)
                
                accuracy = (day.correct or 0) / (day.total or 1) * 100
                accuracies.append(accuracy)
                
                profits.append(day.profit or 0)
            
            return jsonify({
                'success': True,
                'dates': dates,
                'totals': totals,
                'accuracies': accuracies,
                'profits': profits
            })
            
        except Exception as e:
            logger.error(f"Error getting performance chart data: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route("/admin/performance/overview")
    @login_required
    def admin_performance_overview():
        """Admin overview of platform prediction performance"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        try:
            # Get platform-wide performance summary
            summary = get_prediction_performance_summary()
            
            # Get top performing users
            top_users = db.session.query(
                User.username,
                func.count(PredictionPerformance.id).label('total'),
                func.sum(case((PredictionPerformance.is_correct == True, 1), else_=0)).label('correct'),
                func.sum(PredictionPerformance.profit_loss).label('profit'),
                func.avg(PredictionPerformance.confidence_score).label('avg_confidence')
            ).join(PredictionPerformance, User.id == PredictionPerformance.user_id).group_by(
                User.id
            ).order_by(
                func.sum(PredictionPerformance.profit_loss).desc()
            ).limit(10).all()
            
            # Get model performance across platform
            model_performance = db.session.query(
                PredictionPerformance.model_used,
                func.count(PredictionPerformance.id).label('total'),
                func.sum(case((PredictionPerformance.is_correct == True, 1), else_=0)).label('correct'),
                func.avg(PredictionPerformance.confidence_score).label('avg_confidence')
            ).group_by(PredictionPerformance.model_used).all()
            
            # Get recent performance updates
            recent_updates = PredictionPerformance.query.order_by(
                PredictionPerformance.updated_at.desc()
            ).limit(20).all()
            
            # Calculate platform metrics
            if summary['success'] and 'summary' in summary:
                platform_stats = summary['summary']
            else:
                platform_stats = {}
            
            return render_template('admin/performance_overview.html',
                                platform_stats=platform_stats,
                                top_users=top_users,
                                model_performance=model_performance,
                                recent_updates=recent_updates,
                                title='Performance Overview')
            
        except Exception as e:
            logger.error(f"Error in admin performance overview: {e}", exc_info=True)
            flash(f'Error loading performance overview: {str(e)}', 'danger')
            return redirect(url_for('admin_dashboard'))
    
    @app.route("/admin/performance/user/<int:user_id>")
    @login_required
    def admin_user_performance(user_id):
        """Admin view of specific user's performance"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        try:
            user = User.query.get_or_404(user_id)
            
            # Get performance summary
            summary = get_prediction_performance_summary(user_id=user_id)
            
            # Get recent predictions
            recent_predictions = PredictionPerformance.query.filter_by(
                user_id=user_id
            ).order_by(PredictionPerformance.match_date.desc()).limit(20).all()
            
            # Get performance by model
            model_performance = db.session.query(
                PredictionPerformance.model_used,
                func.count(PredictionPerformance.id).label('total'),
                func.sum(case((PredictionPerformance.is_correct == True, 1), else_=0)).label('correct'),
                func.sum(PredictionPerformance.profit_loss).label('profit')
            ).filter_by(user_id=user_id).group_by(
                PredictionPerformance.model_used
            ).all()
            
            # Generate report
            report = generate_performance_report(user_id, 'monthly')
            
            return render_template('admin/user_performance.html',
                                user=user,
                                summary=summary,
                                recent_predictions=recent_predictions,
                                model_performance=model_performance,
                                report=report if report['success'] else None,
                                title=f'Performance - {user.username}')
            
        except Exception as e:
            logger.error(f"Error viewing user performance: {e}", exc_info=True)
            flash(f'Error loading user performance: {str(e)}', 'danger')
            return redirect(url_for('admin_performance_overview'))
    
    @app.route("/admin/performance/export", methods=['POST'])
    @login_required
    def admin_export_performance():
        """Export performance data"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            data = request.get_json()
            user_id = data.get('user_id')
            start_date = data.get('start_date')
            end_date = data.get('end_date')
            format = data.get('format', 'csv')
            
            # Build query
            query = PredictionPerformance.query
            
            if user_id:
                query = query.filter_by(user_id=user_id)
            
            if start_date:
                start_date_obj = datetime.strptime(start_date, '%Y-%m-%d').date()
                query = query.filter(PredictionPerformance.match_date >= start_date_obj)
            
            if end_date:
                end_date_obj = datetime.strptime(end_date, '%Y-%m-%d').date()
                query = query.filter(PredictionPerformance.match_date <= end_date_obj)
            
            performances = query.all()
            
            # Create DataFrame
            data_list = []
            for perf in performances:
                data_list.append({
                    'ID': perf.id,
                    'User ID': perf.user_id,
                    'Match Date': perf.match_date.strftime('%Y-%m-%d') if perf.match_date else '',
                    'Home Team': perf.home_team,
                    'Away Team': perf.away_team,
                    'Predicted Outcome': perf.predicted_outcome,
                    'Actual Outcome': perf.actual_outcome,
                    'Correct': 'Yes' if perf.is_correct else 'No',
                    'Confidence Score': perf.confidence_score,
                    'Profit/Loss': perf.profit_loss,
                    'Odds Used': perf.odds_used,
                    'Stake': perf.stake,
                    'Model Used': perf.model_used,
                    'Created At': perf.created_at.strftime('%Y-%m-%d %H:%M:%S') if perf.created_at else '',
                    'Updated At': perf.updated_at.strftime('%Y-%m-%d %H:%M:%S') if perf.updated_at else ''
                })
            
            df = pd.DataFrame(data_list)
            
            if format == 'csv':
                # Export to CSV
                from io import StringIO
                output = StringIO()
                df.to_csv(output, index=False)
                output.seek(0)
                
                filename = f'performance_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
                
                return send_file(
                    output,
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name=filename
                )
            else:
                # Return as JSON
                return jsonify({
                    'success': True,
                    'data': data_list,
                    'count': len(data_list)
                })
                
        except Exception as e:
            logger.error(f"Error exporting performance data: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route("/admin/performance/cleanup", methods=['POST'])
    @login_required
    def admin_cleanup_performance():
        """Clean up old performance records"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            # Delete records older than 90 days
            cutoff_date = datetime.utcnow() - timedelta(days=90)
            
            deleted_count = PredictionPerformance.query.filter(
                PredictionPerformance.match_date < cutoff_date
            ).delete()
            
            db.session.commit()
            
            logger.info(f"Cleaned up {deleted_count} old performance records")
            
            return jsonify({
                'success': True,
                'message': f'Deleted {deleted_count} old performance records',
                'deleted_count': deleted_count,
                'cutoff_date': cutoff_date.strftime('%Y-%m-%d')
            })
            
        except Exception as e:
            db.session.rollback()
            logger.error(f"Error cleaning up performance records: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500
    
    @app.route("/predictions")
    @login_required
    def my_predictions():
        # Get current user's predictions
        predictions = Prediction.query.filter_by(user_id=current_user.id).all()
        
        # Or more efficiently with counts
        from sqlalchemy import func
        
        stats = {
            'total': Prediction.query.filter_by(user_id=current_user.id).count(),
            'wins': Prediction.query.filter_by(
                user_id=current_user.id,
                status='Won'          # adjust field name if different
            ).count(),
            'losses': Prediction.query.filter_by(
                user_id=current_user.id,
                status='Lost'
            ).count(),
            'pending': Prediction.query.filter_by(
                user_id=current_user.id,
                status='Pending'      # or None, 'In Progress', etc.
            ).count(),
            # Optional: more metrics
            'win_rate': 0.0
        }
        
        if stats['total'] > 0:
            stats['win_rate'] = round((stats['wins'] / stats['total']) * 100, 1)
        
        # You can also add more useful stats
        stats['profit'] = sum(p.profit or 0 for p in predictions)  # if you have profit field
        
        return render_template('features/my_predictions.html',
                            predictions=predictions,     # if you show list too
                            stats=stats,
                            title='my predictions'
                            )

    # History Routes
    @app.route("/history/predictions")
    @login_required
    def predictions_history():
        """View user's past match predictions with detailed history"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status = request.args.get('status', 'all')
        
        # Build query based on status filter
        query = Prediction.query.filter_by(user_id=current_user.id)
        
        if status != 'all':
            query = query.filter_by(status=status)
        
        predictions = query.order_by(
            Prediction.match_date.desc()
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        # Get stats for the filter
        total = Prediction.query.filter_by(user_id=current_user.id).count()
        won = Prediction.query.filter_by(user_id=current_user.id, status='Won').count()
        lost = Prediction.query.filter_by(user_id=current_user.id, status='Lost').count()
        pending = Prediction.query.filter_by(user_id=current_user.id, status='Pending').count()
        
        return render_template('features/history.html',
                             predictions=predictions,
                             stats={
                                 'total': total,
                                 'won': won,
                                 'lost': lost,
                                 'pending': pending,
                                 'accuracy': calculate_accuracy(current_user.id)
                             },
                             current_status=status,
                             title='Predictions History')

    @app.route("/history/orchestration")
    @login_required
    def orchestration_logs():
        """View the AI Agent's thought processes/logs"""
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        logs = OrchestrationLog.query.filter_by(user_id=current_user.id)\
            .order_by(OrchestrationLog.timestamp.desc())\
            .paginate(page=page, per_page=per_page, error_out=False)
        
        return render_template('features/history.html', 
                             logs=logs,
                             title='Orchestration History')

    @app.route("/prediction/<int:prediction_id>")
    @login_required
    def view_prediction(prediction_id):
        prediction = Prediction.query.get_or_404(prediction_id)
        
        # Ensure user owns the prediction
        if prediction.user_id != current_user.id and not current_user.is_admin:
            flash('Access denied.', 'danger')
            return redirect(url_for('my_predictions'))
        
        # You need to create a 'result' dict from the prediction
        result = {
            'home': prediction.home_team,
            'away': prediction.away_team,
            'score': {
                'home': prediction.pred_home_score,
                'away': prediction.pred_away_score
            },
            'win_prob': {
                'home': prediction.mcmc_home_prob,
                'draw': prediction.mcmc_draw_prob,
                'away': prediction.mcmc_away_prob
            },
            'btts': prediction.btts_probability,
            'over25': prediction.over25_probability,
            'tier': current_user.subscription_tier,
            'confidence': {
                'label': f"{prediction.confidence}%",
                'color': 'bg-green-500' if prediction.confidence > 70 
                        else 'bg-yellow-500' if prediction.confidence > 50 
                        else 'bg-red-500'
            }
        }
        
        return render_template('features/results.html',
                            result=result,
                            prediction=prediction,
                            title='Prediction Details')

    @app.route("/prediction/delete/<int:prediction_id>", methods=['POST'])
    @login_required
    def delete_prediction(prediction_id):
        """Delete a prediction"""
        prediction = Prediction.query.get_or_404(prediction_id)
        
        # Ensure user owns the prediction
        if prediction.user_id != current_user.id:
            flash('Access denied.', 'danger')
            return redirect(url_for('my_predictions'))
        
        db.session.delete(prediction)
        db.session.commit()
        
        log_activity(current_user.id, 'prediction_deleted', 
                   f'Deleted prediction #{prediction_id}')
        
        flash('Prediction deleted successfully.', 'success')
        return redirect(url_for('my_predictions'))

    @app.route("/dashboard")
    @login_required
    def dashboard():
        """User dashboard with overview - Advanced Tiered Version"""
        # 1. Get user predictions (last 10)
        predictions = Prediction.query.filter_by(user_id=current_user.id)\
            .order_by(Prediction.match_date.desc())\
            .limit(10).all()
        
        # 2. Get detailed user stats
        total_pred = Prediction.query.filter_by(user_id=current_user.id).count()
        wins = Prediction.query.filter_by(user_id=current_user.id, status='Won').count()
        losses = Prediction.query.filter_by(user_id=current_user.id, status='Lost').count()
        pending = Prediction.query.filter_by(user_id=current_user.id, status='Pending').count()
        
        # Calculate accuracy safely
        settled = wins + losses
        accuracy = (wins / settled * 100) if settled > 0 else 0
        
        # 3. Get streak with a safety fallback
        try:
            streak = calculate_streak(current_user.id)
        except NameError:
            streak = 0
        
        # 4. Get unread notifications
        notifications = Notification.query.filter_by(
            user_id=current_user.id, 
            is_read=False
        ).order_by(Notification.created_at.desc()).limit(5).all()
        
        # 5. Get today's top matches
        today_date = str(date.today())
        today_matches = Match.query.filter_by(date=today_date)\
            .order_by(Match.time.asc())\
            .limit(6).all()
        
        # 6. Leaderboard Data Formatting
        leaderboard_entry = Leaderboard.query.filter_by(user_id=current_user.id).first()
        leaderboard_data = None
        if leaderboard_entry:
            leaderboard_data = {
                'rank': leaderboard_entry.rank,
                'wins': leaderboard_entry.wins,
                'streak': leaderboard_entry.streak,
                'accuracy': getattr(leaderboard_entry, 'accuracy', accuracy)
            }
        
        # 7. Tier-Based Limits (Syncing with your 'is_premium' database column)
        # If is_premium is True, they get 50 predictions. If False (Starter), they get 10.
        is_premium = getattr(current_user, 'is_premium', False)
        daily_limit = 50 if is_premium else 10
        
        # 8. Count predictions made since midnight
        today_start = datetime.combine(date.today(), datetime.min.time())
        predictions_today = Prediction.query.filter(
            Prediction.user_id == current_user.id,
            Prediction.created_at >= today_start
        ).count()
        
        return render_template('public/dashboard.html',
                            predictions=predictions,
                            stats={
                                'total': total_pred,
                                'wins': wins,
                                'losses': losses,
                                'pending': pending,
                                'accuracy': round(accuracy, 1),
                                'streak': streak,
                                'daily_limit': daily_limit,
                                'predictions_today': predictions_today
                            },
                            notifications=notifications,
                            today_matches=today_matches,
                            leaderboard=leaderboard_data,
                            is_premium=is_premium)
        
    @app.route('/generate-password', methods=['POST'])
    def generate_password():
        """Generate a cryptographically secure strong password"""
        try:
            # 1. Define character sets
            lower = string.ascii_lowercase
            upper = string.ascii_uppercase
            digits = string.digits
            symbols = "!@#$%^&*()_+-=[]{}|" # Specific safe symbols
            
            # 2. Guarantee at least one of each type using 'secrets' (Secure)
            password_list = [
                secrets.choice(lower),
                secrets.choice(upper),
                secrets.choice(digits),
                secrets.choice(symbols)
            ]
            
            # 3. Fill the rest to reach 16 characters
            all_chars = lower + upper + digits + symbols
            password_list += [secrets.choice(all_chars) for _ in range(12)]
            
            # 4. Shuffle securely
            secrets.SystemRandom().shuffle(password_list)
            password = ''.join(password_list)
            
            return jsonify({
                'success': True,
                'password': password,
                'strength': 'very_strong',
                'length': len(password)
            })
        except Exception as e:
            logger.error(f"Password generation error: {e}")
            return jsonify({'success': False, 'error': "Failed to generate password"}), 500

    @app.route('/check-password-strength', methods=['POST'])
    def check_password_strength():
        """Check password strength with pattern detection and regex variety checks"""
        try:
            data = request.get_json()
            password = data.get('password', '')
            
            if not password:
                return jsonify({'strength': 'empty', 'score': 0})
            
            score = 0
            feedback = []
            
            # Criteria 1: Length
            if len(password) >= 8: score += 1
            if len(password) >= 12: score += 1
            
            # Criteria 2: Variety (using Regex for performance)
            if re.search(r'[a-z]', password): score += 1
            if re.search(r'[A-Z]', password): score += 1
            if re.search(r'[0-9]', password): score += 1
            if re.search(r'[^A-Za-z0-9]', password): score += 1
            
            # Criteria 3: Pattern Penalty
            common_patterns = ['password', '123456', 'qwerty', 'admin', 'scorepulse', 'soccer']
            if any(pattern in password.lower() for pattern in common_patterns):
                score = max(1, score - 2) # Reduce score but keep it at least 1
                feedback.append("Avoid common words or project names")

            # Determine label
            strength_map = {
                0: ('weak', 'danger'),
                1: ('weak', 'danger'),
                2: ('weak', 'danger'),
                3: ('fair', 'warning'),
                4: ('fair', 'warning'),
                5: ('good', 'info'),
                6: ('strong', 'success')
            }
            
            strength, css_class = strength_map.get(score, ('weak', 'danger'))
            
            return jsonify({
                'success': True,
                'score': score,
                'max_score': 6,
                'strength': strength,
                'css_class': css_class, # Useful for frontend styling
                'feedback': feedback
            })
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500   
   
    @app.route('/password-security')
    def password_security():
        """Educational page about password security"""
        return render_template('auth/password_security.html')
    
    @app.route('/live/start', methods=['POST'])
    @login_required
    def start_live_tracking():
        data = request.json
        match_id = data['match_id']
        home = data['home']
        away = data['away']
        tracker = app.live_tracker.start_tracking(match_id, home, away)
        return jsonify(tracker)

    @app.route('/live/update', methods=['POST'])
    @login_required
    def update_live_match():
        data = request.json
        match_id = data['match_id']
        score = data['score']  # e.g., {'home': 1, 'away': 0}
        minute = data['minute']
        events = data.get('events', [])  # e.g., [{'type': 'goal', 'team': 'home'}]
        updated = app.live_tracker.update_match_state(match_id, score, minute, events=events)
        return jsonify(updated)

    @app.route('/live/summary/<match_id>')
    @login_required
    def get_live_summary(match_id):
        summary = app.live_tracker.get_match_summary(match_id)
        return jsonify(summary) if summary else ('Not found', 404)

    @app.route("/predict/advanced", methods=['GET', 'POST'])
    @login_required
    def advanced_predict():
        """Advanced prediction with custom parameters"""
        form = AdvancedSettingsForm()  # Use correct form name
        
        # Populate team choices
        teams = get_all_teams()
        form.home_team.choices = [(team, team) for team in teams]
        form.away_team.choices = [(team, team) for team in teams]
        
        if form.validate_on_submit():
            home = form.home_team.data
            away = form.away_team.data
            
            # Check if teams are different
            if home == away:
                flash('Home and away teams cannot be the same.', 'danger')
                return redirect(url_for('advanced_predict'))
            
            # Check AI engine availability
            if not ai_engine:
                flash('AI Prediction Engine is currently offline.', 'danger')
                return redirect(url_for('advanced_predict'))
            
            # Check user limits (if applicable)
            if not current_user.can_make_prediction():
                flash('Daily prediction limit reached! Upgrade for unlimited predictions.', 'warning')
                return redirect(url_for('upgrade'))
            
            try:
                # ============================================
                # Collect advanced parameters
                # ============================================
                custom_params = {
                    'confidence_threshold': form.confidence_threshold.data,
                    'include_head_to_head': form.include_head_to_head.data,
                    'include_form': form.include_form.data,
                    'include_injuries': form.include_injuries.data,
                    'betting_strategy': form.betting_strategy.data,
                    'risk_level': form.risk_level.data,
                    'advanced_mode': True,
                    'subscription_tier': getattr(current_user, 'subscription_tier', 'free')
                }
                
                print(f"🔧 [ADVANCED] Custom params: {custom_params}")
                
                # ============================================
                # Get prediction with advanced parameters
                # ============================================
                # CRITICAL FIX: Use predict_for_web() not predict_custom()
                result = ai_engine.predict_for_web(home, away, custom_params['subscription_tier'])
                
                # Apply advanced filtering based on custom parameters
                result = apply_advanced_filters(result, custom_params)
                
                # Check confidence threshold
                confidence = result.get('prediction_confidence', 50)
                threshold = custom_params.get('confidence_threshold', 75)
                
                if confidence < threshold:
                    flash(f'⚠️ Warning: Prediction confidence ({confidence}%) is below your threshold ({threshold}%). Consider analyzing further.', 'warning')
                
                # ============================================
                # Save advanced prediction to database
                # ============================================
                
                # Extract data from result
                ai_outcome = result.get('prediction_outcome', 'D')
                score_data = result.get('score', {})
                predicted_home_score = score_data.get('home', 0)
                predicted_away_score = score_data.get('away', 0)
                
                # Get win probabilities
                win_prob = result.get('win_prob', {})
                mcmc_home_prob = win_prob.get('home', 0)
                mcmc_draw_prob = win_prob.get('draw', 0)
                mcmc_away_prob = win_prob.get('away', 0)
                
                # Create advanced prediction record
                prediction = Prediction(
                    user_id=current_user.id,
                    home_team=home,
                    away_team=away,
                    match_date=date.today(),
                    
                    # Prediction outcomes
                    pred_outcome=ai_outcome,
                    ai_prediction=ai_outcome,
                    
                    # Scores
                    pred_home_score=predicted_home_score,
                    pred_away_score=predicted_away_score,
                    
                    # Probabilities
                    confidence=confidence,
                    mcmc_home_prob=mcmc_home_prob,
                    mcmc_draw_prob=mcmc_draw_prob,
                    mcmc_away_prob=mcmc_away_prob,
                    
                    # Advanced stats
                    btts_probability=result.get('btts', 50.0),
                    over25_probability=result.get('over25', 50.0),
                    total_goals_pred=result.get('total_goals', 2.5),
                    
                    # Betting strategy from advanced form
                    recommended_stake=result.get('recommended_stake', 2.5),
                    kelly_fraction=result.get('kelly_fraction', 0.5),
                    market_odds=result.get('market_odds', 2.5),
                    risk_level=custom_params.get('risk_level', 'MEDIUM'),
                    
                    # Mark as advanced prediction
                    model_used=f"Advanced ({custom_params.get('betting_strategy', 'Conservative')})",
                    
                    # Store custom parameters in notes
                    notes=f"ADVANCED PREDICTION SETTINGS:\n"
                        f"- Confidence Threshold: {threshold}%\n"
                        f"- Data Sources: {'H2H ' if custom_params['include_head_to_head'] else ''}"
                        f"{'Form ' if custom_params['include_form'] else ''}"
                        f"{'Injuries ' if custom_params['include_injuries'] else ''}\n"
                        f"- Betting Strategy: {custom_params['betting_strategy']}\n"
                        f"- Risk Level: {custom_params['risk_level']}\n\n"
                        f"AI ANALYSIS:\n{result.get('analysis', 'No analysis available.')}",
                    
                    # Status
                    status='Pending',
                    created_at=datetime.utcnow()
                )
                
                # Save to database
                db.session.add(prediction)
                db.session.commit()
                
                # ============================================
                # Log activity and update user
                # ============================================
                log_activity(current_user.id, 'advanced_prediction', 
                            f'Advanced: {home} vs {away} | Strategy: {custom_params["betting_strategy"]} | Risk: {custom_params["risk_level"]}')
                
                # Update prediction count
                current_user.predictions_today = getattr(current_user, 'predictions_today', 0) + 1
                db.session.commit()
                
                # ============================================
                # Show results
                # ============================================
                flash(f'✅ Advanced prediction generated! Confidence: {confidence}%', 'success')
                
                # Pass custom parameters to template for display
                return render_template('features/prediction_result.html',
                                    prediction=prediction,
                                    result=result,
                                    custom_params=custom_params,
                                    title='Advanced Prediction Result')
                
            except Exception as e:
                db.session.rollback()
                logger.error(f"Advanced prediction error: {e}", exc_info=True)
                flash(f'Advanced prediction failed: {str(e)}', 'danger')
                return redirect(url_for('advanced_predict'))
        
        # GET request - show advanced prediction form
        return render_template('features/advanced_predict.html', 
                            form=form, 
                            title='Advanced Prediction')

    @app.route("/value-bets")
    @login_required
    def value_bets():
        """Find value bets with positive expected value"""
        if not value_bet_finder:
            flash('Value Bet Finder is currently unavailable', 'warning')
            return redirect(url_for('home'))
        
        try:
            # Get value bets - WITH CACHING
            cache_key = f"value_bets_{date.today()}"
            value_bets_list = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if value_bets_list is None:
                value_bets_list = value_bet_finder.find_value_bets(limit=20)
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, value_bets_list, timeout=3600)  # 1 hour cache
            
            return render_template('features/value_bets.html', 
                                 value_bets=value_bets_list,
                                 title='Value Bets')
            
        except Exception as e:
            logger.error(f"Error finding value bets: {e}")
            flash('Error finding value bets', 'danger')
            return redirect(url_for('home'))

    @app.route("/live-matches")
    def live_matches():
        """View live matches and in-play predictions"""
        if not live_tracker:
            return render_template('features/live_matches.html', 
                                 live_matches=[], 
                                 title='Live Matches')
        
        try:
            live_matches = live_tracker.get_live_matches()
            
            # Add AI predictions for live matches
            for match in live_matches:
                if ai_engine:
                    try:
                        pred = ai_engine.predict_live(match['home'], match['away'])
                        match['ai_prediction'] = pred
                    except:
                        match['ai_prediction'] = None
            
            return render_template('features/live_matches.html', 
                                 live_matches=live_matches,
                                 title='Live Matches')
            
        except Exception as e:
            logger.error(f"Error getting live matches: {e}")
            return render_template('features/live_matches.html', 
                                 live_matches=[], 
                                 title='Live Matches')

    @app.route("/analytics")
    @login_required
    def analytics():
        """User analytics and performance insights"""
        if not performance_analyzer:
            flash('Analytics module is currently unavailable', 'warning')
            return redirect(url_for('dashboard'))
        
        try:
            # Get user performance analytics - WITH CACHING
            cache_key = f"user_analytics_{current_user.id}"
            user_analytics = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if user_analytics is None:
                user_analytics = performance_analyzer.analyze_user_performance(current_user.id)
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, user_analytics, timeout=1800)  # 30 minutes cache
            
            # Get betting patterns
            betting_patterns = performance_analyzer.get_betting_patterns(current_user.id)
            
            # Get ROI analysis
            roi_analysis = performance_analyzer.calculate_roi(current_user.id)
            
            return render_template('features/analytics.html',
                                 analytics=user_analytics,
                                 patterns=betting_patterns,
                                 roi=roi_analysis,
                                 title='Analytics')
            
        except Exception as e:
            logger.error(f"Error getting analytics: {e}")
            flash('Error loading analytics', 'danger')
            return redirect(url_for('dashboard'))

    @app.route("/leaderboard")
    def leaderboard_view():
        """Global leaderboard"""
        period = request.args.get('period', 'all')  # all, weekly, monthly
        
        query = Leaderboard.query
        
        if period == 'weekly':
            # Filter for last 7 days
            one_week_ago = datetime.utcnow() - timedelta(days=7)
            query = query.filter(Leaderboard.last_updated >= one_week_ago)
        elif period == 'monthly':
            # Filter for last 30 days
            one_month_ago = datetime.utcnow() - timedelta(days=30)
            query = query.filter(Leaderboard.last_updated >= one_month_ago)
        
        leaderboard_entries = query.order_by(
            Leaderboard.accuracy.desc()
        ).limit(50).all()
        
        # Get current user's position
        user_entry = None
        if current_user.is_authenticated:
            user_entry = Leaderboard.query.filter_by(
                user_id=current_user.id
            ).first()
            
        for user in users:
            if user.last_updated:
                delta = datetime.utcnow() - user.last_updated
                if delta.total_seconds() < 60:
                    user.relative_time = "just now"
                elif delta.total_seconds() < 3600:
                    user.relative_time = f"{int(delta.total_seconds() // 60)} min ago"
                elif delta.total_seconds() < 86400:
                    user.relative_time = f"{int(delta.total_seconds() // 3600)} hr ago"
                else:
                    user.relative_time = f"{delta.days} day{'s' if delta.days != 1 else ''} ago"
            else:
                user.relative_time = "—"
        
        return render_template('public/leaderboard.html',
                             users=users,
                             leaderboard=leaderboard_entries,
                             user_entry=user_entry,
                             period=period,
                             title='Leaderboard')

    @app.route("/profile", methods=['GET', 'POST'])
    @login_required
    def profile():
        """User profile page"""
        form = ProfileUpdateForm()
        
        if form.validate_on_submit():
            if form.username.data != current_user.username:
                # Check if username is taken
                existing_user = User.query.filter_by(username=form.username.data).first()
                if existing_user and existing_user.id != current_user.id:
                    flash('Username already taken.', 'danger')
                    return redirect(url_for('profile'))
                current_user.username = form.username.data
            
            if form.email.data != current_user.email:
                # Check if email is taken
                existing_user = User.query.filter_by(email=form.email.data).first()
                if existing_user and existing_user.id != current_user.id:
                    flash('Email already in use.', 'danger')
                    return redirect(url_for('profile'))
                current_user.email = form.email.data
            
            if form.bio.data:
                current_user.bio = form.bio.data
            
            db.session.commit()
            flash('Your profile has been updated!', 'success')
            log_activity(current_user.id, 'profile_update', 'Updated profile')
            return redirect(url_for('profile'))
        
        elif request.method == 'GET':
            form.username.data = current_user.username
            form.email.data = current_user.email
            form.bio.data = current_user.bio
        
        return render_template('auth/profile.html', form=form, title='Profile')

    @app.route("/predictions/export")
    @login_required
    def export_predictions():
        """Export user predictions to CSV"""
        try:
            predictions = Prediction.query.filter_by(user_id=current_user.id).all()
            
            # Create DataFrame
            data = []
            for pred in predictions:
                data.append({
                    'Date': pred.match_date,
                    'Home Team': pred.home_team,
                    'Away Team': pred.away_team,
                    'Prediction': pred.pred_outcome,
                    'Status': pred.status,
                    'Confidence': pred.confidence,
                    'Profit/Loss': pred.profit_loss or 0
                })
            
            df = pd.DataFrame(data)
            
            # Create CSV in memory
            from io import StringIO
            output = StringIO()
            df.to_csv(output, index=False)
            output.seek(0)
            
            # Send file
            return send_file(
                output,
                mimetype='text/csv',
                as_attachment=True,
                download_name=f'predictions_{current_user.username}_{date.today()}.csv'
            )
            
        except Exception as e:
            logger.error(f"Error exporting predictions: {e}")
            flash('Error exporting predictions', 'danger')
            return redirect(url_for('profile'))

    @app.route('/settings', methods=['GET', 'POST'])
    @login_required
    def user_settings():
        """User settings page with profile, notifications, advanced prediction settings & password change"""
        
        # ─── Initialize forms (pre-fill from current_user) ─────────────
        profile_form   = ProfileUpdateForm(obj=current_user)
        advanced_form  = AdvancedSettingsForm(obj=current_user)  # Fields match User
        password_form  = PasswordChangeForm()

        # ─── Profile & basic notification update ───────────────────────
        if 'profile_submit' in request.form and profile_form.validate_on_submit():
            profile_form.populate_obj(current_user)
            
            # Notification toggles from profile form
            current_user.email_notifications = profile_form.email_notifications.data
            current_user.sms_notifications   = profile_form.sms_notifications.data
            current_user.weekly_report       = profile_form.weekly_report.data
            
            db.session.commit()
            flash('Profile and notification settings updated successfully.', 'success')
            # log_activity(current_user.id, 'profile_update', 'Updated profile')  # If you have this
            return redirect(url_for('user_settings'))

        # ─── Advanced prediction settings update ───────────────────────
        if 'advanced_submit' in request.form and advanced_form.validate_on_submit():
            # Update User from advanced form
            current_user.confidence_threshold   = advanced_form.confidence_threshold.data
            current_user.include_head_to_head   = advanced_form.include_head_to_head.data
            current_user.include_form           = advanced_form.include_form.data
            current_user.include_injuries       = advanced_form.include_injuries.data
            current_user.betting_strategy       = advanced_form.betting_strategy.data
            current_user.risk_level             = advanced_form.risk_level.data
            # Handle duplicated email_notifications (e.g., update if changed)
            current_user.email_notifications    = advanced_form.email_notifications.data
            
            db.session.commit()
            flash('Advanced prediction settings saved.', 'success')
            # log_activity(current_user.id, 'advanced_settings_update', 'Updated prediction preferences')
            return redirect(url_for('user_settings'))

        # ─── Password change ───────────────────────────────────────────
        if 'password_submit' in request.form and password_form.validate_on_submit():
            if current_user.check_password(password_form.current_password.data):
                current_user.set_password(password_form.new_password.data)
                db.session.commit()
                flash('Password changed successfully.', 'success')
            else:
                flash('Current password is incorrect.', 'danger')
            return redirect(url_for('user_settings'))

        # ─── GET: Additional pre-fill if needed (though obj= handles most) ────
        if request.method == 'GET':
            # For any non-standard fields or defaults
            pass  # obj=current_user should suffice

        return render_template('public/settings.html',
                            profile_form=profile_form,
                            advanced_form=advanced_form,
                            password_form=password_form,
                            user=current_user,
                            title='Account Settings')

    @app.route("/feedback", methods=['GET', 'POST'])
    @login_required
    def submit_feedback():
        """Submit feedback or bug report"""
        form = FeedbackForm()
        
        if form.validate_on_submit():
            feedback = Feedback(
                user_id=current_user.id,
                feedback_type=form.feedback_type.data,
                subject=form.subject.data,
                message=form.message.data,
                priority=form.priority.data,
                created_at=datetime.utcnow()
            )
            
            db.session.add(feedback)
            db.session.commit()
            
            # Send notification to admin using Celery
            admin = User.query.filter_by(id=1).first()
            if admin:
                celery_send_notification(
                    admin.id,
                    'New Feedback Received',
                    f'New {form.feedback_type.value} from {current_user.username}: {form.subject.data}',
                    'info',
                    send_email=True
                )
            
            flash('Thank you for your feedback! We will review it soon.', 'success')
            log_activity(current_user.id, 'feedback_submitted', 
                       f'{form.feedback_type.value}: {form.subject.data}')
            
            return redirect(url_for('home'))
        
        return render_template('features/feedback.html', form=form, title='Feedback')

    @app.route("/payment", methods=['GET', 'POST'])
    @login_required
    def payment():
        """Payment processing page"""
        form = PaymentForm()
        
        if form.validate_on_submit():
            # Process payment (this would integrate with a payment gateway)
            payment_amount = form.amount.data if hasattr(form, 'amount') else 9.99
            payment = Payment(
                user_id=current_user.id,
                status='PENDING',
                timestamp=datetime.utcnow()
            )
            db.session.add(payment)
            db.session.commit()
            
            # In a real app, you would redirect to payment gateway here
            # For demo, we'll just mark as completed
            payment.status = 'COMPLETED'
            db.session.commit()
            
            # Update user's premium status if applicable
            if payment_amount >= 9.99:
                current_user.is_premium = True
                current_user.premium_expiry = datetime.utcnow() + timedelta(days=30)
                db.session.commit()
            
            flash('Payment processed successfully!', 'success')
            log_activity(current_user.id, 'payment_made', 
                       f'Payment via {form.payment_method.data if hasattr(form, "payment_method") else "card"}')
            
            return redirect(url_for('dashboard'))
        
        return render_template('payment.html', form=form, title='Payment')

    # Match Orchestration Chatbot Routes
    @app.route("/orchestrate", methods=['GET', 'POST'])
    @login_required
    def orchestrate_match():
        """Orchestrate a full match prediction pipeline"""
        if request.method == 'GET':
            # Show form for orchestration
            form = MatchOrchestrationForm()
            teams = get_all_teams()
            form.home_team.choices = [(team, team) for team in teams]
            form.away_team.choices = [(team, team) for team in teams]
            
            return render_template('features/orchestrate.html', 
                                 form=form,
                                 title='Match Orchestration')
        
        # POST request - handle orchestration
        try:
            data = request.get_json() if request.is_json else request.form
            home_team = data.get('home_team')
            away_team = data.get('away_team')
            
            if not home_team or not away_team:
                return jsonify({
                    'success': False,
                    'message': 'home_team and away_team are required'
                }), 400
            
            # Get market odds if provided
            market_odds = data.get('market_odds')
            
            # Check if orchestration engine is available
            if not pitch_commander:
                return jsonify({
                    'success': False,
                    'message': 'Orchestration engine is currently unavailable'
                }), 503
            
            # Run orchestration
            start_time = time.time()
            result = pitch_commander.run_match_pipeline(
                home_team=home_team,
                away_team=away_team,
                market_odds=market_odds
            )
            execution_time = time.time() - start_time
            
            # Log orchestration
            match_id = f"{home_team}_{away_team}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            log_orchestration(
                user_id=current_user.id,
                match_id=match_id,
                home_team=home_team,
                away_team=away_team,
                status='success' if 'error' not in result else 'failed',
                execution_time=execution_time,
                result=result
            )
            
            # Log activity
            log_activity(current_user.id, 'orchestration_run', 
                        f'Orchestrated {home_team} vs {away_team}')
            
            return jsonify({
                'success': True,
                'execution_time': execution_time,
                'result': result
            })
            
        except Exception as e:
            logger.error(f"Orchestration error: {e}")
            return jsonify({
                'success': False,
                'message': f'Orchestration failed: {str(e)}'
            }), 500

    @app.route("/orchestrate/status", methods=['GET'])
    @login_required
    def orchestration_status():
        """Get orchestration system status"""
        try:
            status = {
                'pitch_commander_initialized': pitch_commander is not None,
                'ai_engine_available': ai_engine is not None,
                'value_bet_finder_available': value_bet_finder is not None,
                'live_tracker_available': live_tracker is not None,
                'performance_analyzer_available': performance_analyzer is not None,
                'timestamp': datetime.now().isoformat()
            }
            
            # Add agent availability if pitch_commander exists
            if pitch_commander:
                status['agents_available'] = {
                    'data_agent': hasattr(pitch_commander, 'data_agent'),
                    'analyst_agent': hasattr(pitch_commander, 'analyst_agent'),
                    'critic_agent': hasattr(pitch_commander, 'critic_agent'),
                    'bankroll_agent': hasattr(pitch_commander, 'bankroll_agent'),
                    'admin_agent': hasattr(pitch_commander, 'admin_agent')
                }
            
            return jsonify({
                'success': True,
                'status': status
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Error getting status: {str(e)}'
            }), 500

    @app.route("/orchestrate/history", methods=['GET'])
    @login_required
    def orchestration_history():
        """Get user's orchestration history"""
        try:
            page = request.args.get('page', 1, type=int)
            per_page = request.args.get('per_page', 10, type=int)
            
            # Query orchestration logs
            logs = OrchestrationLog.query.filter_by(
                user_id=current_user.id
            ).order_by(OrchestrationLog.timestamp.desc()).paginate(
                page=page, per_page=per_page, error_out=False
            )
            
            log_list = []
            for log in logs.items:
                log_list.append({
                    'id': log.id,
                    'match': f"{log.home_team} vs {log.away_team}",
                    'timestamp': log.timestamp.isoformat(),
                    'status': log.status,
                    'execution_time': log.execution_time,
                    'prediction': log.prediction_result,
                    'analysis': log.analysis_result
                })
            
            return jsonify({
                'success': True,
                'logs': log_list,
                'total': logs.total,
                'pages': logs.pages,
                'current_page': logs.page
            })
            
        except Exception as e:
            logger.error(f"Error getting orchestration history: {e}")
            return jsonify({
                'success': False,
                'message': f'Error getting history: {str(e)}'
            }), 500

    @app.route("/orchestrate/analyze", methods=['POST'])
    @login_required
    def analyze_orchestration():
        """Analyze orchestration results"""
        try:
            data = request.get_json()
            orchestration_id = data.get('orchestration_id')
            
            if not orchestration_id:
                return jsonify({
                    'success': False,
                    'message': 'orchestration_id is required'
                }), 400
            
            # Get orchestration log
            log = OrchestrationLog.query.filter_by(
                id=orchestration_id,
                user_id=current_user.id
            ).first()
            
            if not log:
                return jsonify({
                    'success': False,
                    'message': 'Orchestration log not found'
                }), 404
            
            # Analyze using performance analyzer if available
            analysis_result = {}
            if performance_analyzer:
                try:
                    analysis_result = performance_analyzer.analyze_orchestration(log.id)
                except Exception as e:
                    logger.error(f"Performance analyzer error: {e}")
                    analysis_result = {'error': str(e)}
            
            return jsonify({
                'success': True,
                'analysis': analysis_result,
                'log': {
                    'id': log.id,
                    'match': f"{log.home_team} vs {log.away_team}",
                    'timestamp': log.timestamp.isoformat(),
                    'status': log.status,
                    'prediction': log.prediction_result
                }
            })
            
        except Exception as e:
            logger.error(f"Error analyzing orchestration: {e}")
            return jsonify({
                'success': False,
                'message': f'Analysis failed: {str(e)}'
            }), 500

    # API Routes - UPDATED WITH CACHING
    @app.route("/api/live/scores")
    def live_scores_api():
        """API endpoint for live scores"""
        try:
            if not live_tracker:
                return jsonify({'error': 'Live tracker unavailable'}), 503
            
            cache_key = "live_scores_api"
            live_matches = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if live_matches is None:
                live_matches = live_tracker.get_live_matches(limit=20)
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, live_matches, timeout=60)  # 1 minute cache for live scores
            
            return jsonify({'matches': live_matches, 'timestamp': datetime.utcnow().isoformat()})
            
        except Exception as e:
            logger.error(f"Error in live scores API: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route("/api/predictions/trending")
    def trending_predictions_api():
        """API endpoint for trending predictions"""
        try:
            cache_key = "trending_predictions"
            trending = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if trending is None:
                # Get predictions from last 24 hours
                yesterday = datetime.utcnow() - timedelta(days=1)
                predictions = Prediction.query.filter(
                    Prediction.match_date >= yesterday
                ).all()
                
                # Count team mentions
                team_counts = {}
                for pred in predictions:
                    team_counts[pred.home_team] = team_counts.get(pred.home_team, 0) + 1
                    team_counts[pred.away_team] = team_counts.get(pred.away_team, 0) + 1
                
                # Get top trending
                trending = sorted(team_counts.items(), key=lambda x: x[1], reverse=True)[:10]
                
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, trending, timeout=300)
            
            return jsonify({'trending': trending})
            
        except Exception as e:
            logger.error(f"Error in trending predictions API: {e}")
            return jsonify({'error': str(e)}), 500

    @app.route("/api/notifications/mark-read/<int:notification_id>", methods=['POST'])
    @login_required
    def mark_notification_read(notification_id):
        """Mark notification as read"""
        try:
            notification = Notification.query.filter_by(
                id=notification_id,
                user_id=current_user.id
            ).first()
            
            if notification:
                notification.is_read = True
                notification.read_at = datetime.utcnow()
                db.session.commit()
                
                return jsonify({'success': True})
            
            return jsonify({'error': 'Notification not found'}), 404
            
        except Exception as e:
            logger.error(f"Error marking notification read: {e}")
            return jsonify({'error': str(e)}), 500

    # Admin Features
    @app.route("/admin/dashboard")
    @login_required
    def admin_dashboard():
        """Admin dashboard"""
        if current_user.id != 1:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        # Get admin stats
        stats = {
            'total_users': User.query.count(),
            'active_today': User.query.filter(User.last_login >= date.today()).count(),
            'total_predictions': Prediction.query.count(),
            'pending_predictions': Prediction.query.filter_by(status='Pending').count(),
            'total_feedback': Feedback.query.count(),
            'unread_feedback': Feedback.query.filter_by(status='new').count(),
            'total_orchestrations': OrchestrationLog.query.count(),
            'successful_orchestrations': OrchestrationLog.query.filter_by(status='success').count()
        }
        
        # Recent Activities (from UserActivity)
        recent_activities = UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(10).all()
        
        # Recent Predictions
        recent_predictions = Prediction.query.order_by(Prediction.created_at.desc()).limit(5).all()
        
        # Recent Users
        recent_users = User.query.order_by(User.created_at.desc()).limit(5).all()
        
        # System Logs (last 10 errors/warnings)
        system_logs = SystemLog.query.filter(SystemLog.level.in_(['ERROR', 'WARNING', 'CRITICAL'])).order_by(SystemLog.timestamp.desc()).limit(10).all()
        
        # System Status (from health_checker)
        health_data = app.health_checker.run_all_checks() if health_checker else {'status': 'Not available'}
        
        # Alerts (from alert_manager)
        active_alerts = app.alert_manager.get_active_alerts() if alert_manager else []
        
        # Metrics Summary (from metrics_collector)
        metrics_summary = app.metrics_collector.get_metrics_summary(hours=24) if metrics_collector else {}
        
        # Training Logs / Champions (from logger)
        history_df = app.training_logger.get_history(limit=50) if training_logger else pd.DataFrame()
        champions = history_df.sort_values('Timestamp').groupby('Target').last().to_dict(orient='index') if not history_df.empty else {}
        
        # Dashboard Charts (from dashboard.py)
        overview_metrics_html = dashboard_builder.generate_overview_metrics(history_df) if dashboard_builder else "<div>No metrics available</div>"
        performance_charts_html = dashboard_builder.generate_performance_charts(history_df) if dashboard_builder else "<div>No charts available</div>"
        system_gauges_html = dashboard_builder.generate_system_gauges(metrics_summary.get('system', {})) if dashboard_builder else "<div>No gauges available</div>"
        alert_dashboard_html = dashboard_builder.generate_alert_dashboard(active_alerts) if dashboard_builder else "<div>No alerts</div>"
        prediction_analytics_html = dashboard_builder.generate_prediction_analytics_dashboard(metrics_summary.get('predictions', {})) if dashboard_builder else "<div>No analytics</div>"
        
        # Render the single dashboard template with all data
        return render_template('admin/admin_dashboard.html',
                              stats=stats,
                              recent_activities=recent_activities,
                              recent_predictions=recent_predictions,
                              recent_users=recent_users,
                              system_logs=system_logs,
                              health_data=health_data,
                              active_alerts=active_alerts,
                              metrics_summary=metrics_summary,
                              champions=champions,
                              # Dashboard HTML components
                              overview_metrics_html=overview_metrics_html,
                              performance_charts_html=performance_charts_html,
                              system_gauges_html=system_gauges_html,
                              alert_dashboard_html=alert_dashboard_html,
                              prediction_analytics_html=prediction_analytics_html,
                              title='Admin Dashboard')
        
    @app.route('/admin/performance/report')
    @login_required
    def performance_report():
        if not current_user.is_admin: return 'Unauthorized', 403
        report = app.performance_analyzer.get_comprehensive_report(days=30)
        return jsonify(report)
            
    @app.route("/admin/verifications")
    @login_required
    def admin_verifications():
        """Admin view of pending verifications"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        # Get unverified users
        unverified_users = User.query.filter_by(is_verified=False).order_by(User.date_joined.desc()).all()
        
        # Get stats
        stats = {
            'total_unverified': len(unverified_users),
            'verified_today': User.query.filter(
                User.is_verified == True,
                func.strftime('%Y-%m-%d', User.date_joined) == date.today().strftime('%Y-%m-%d')
            ).count(),
            'pending_expired': User.query.filter(
                User.is_verified == False,
                User.verification_code_expiry < datetime.utcnow()
            ).count()
        }
        
        return render_template('admin/admin_verifications.html',
                            unverified_users=unverified_users,
                            stats=stats,
                            title='Verification Management') 

    # Add to create_routes function, in the appropriate section with other admin routes:

    @app.route("/admin/predictions/update_outcomes", methods=['GET', 'POST'])
    @login_required
    def admin_update_prediction_outcomes():
        """Admin interface to update prediction outcomes"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            try:
                data = request.get_json() if request.is_json else request.form
                
                # Check if it's a single match or batch update
                match_id = data.get('match_id')
                batch_size = int(data.get('batch_size', 50))
                
                # Run synchronous update
                result = update_prediction_outcomes_sync(
                    match_id=int(match_id) if match_id else None,
                    batch_size=batch_size
                )
                
                if request.is_json:
                    return jsonify(result)
                else:
                    if result['success']:
                        flash(result['message'], 'success')
                    else:
                        flash(result['message'], 'danger')
                    
                    return redirect(url_for('admin_update_prediction_outcomes'))
                
            except Exception as e:
                logger.error(f"Error in admin prediction update: {e}", exc_info=True)
                
                if request.is_json:
                    return jsonify({
                        'success': False,
                        'message': f'Error: {str(e)}'
                    }), 500
                else:
                    flash(f'Error: {str(e)}', 'danger')
                    return redirect(url_for('admin_update_prediction_outcomes'))
        
        # GET request - show update interface
        # Get pending predictions count
        pending_count = Prediction.query.filter_by(status='Pending').count()
        
        # Get completed matches with pending predictions
        completed_matches = Match.query.filter(
            Match.home_score.isnot(None),
            Match.away_score.isnot(None),
            Match.date <= date.today()
        ).order_by(Match.date.desc()).limit(20).all()
        
        # Count pending predictions per match
        match_pending_counts = {}
        for match in completed_matches:
            count = Prediction.query.filter_by(
                match_id=match.id,
                status='Pending'
            ).count()
            if count > 0:
                match_pending_counts[match.id] = {
                    'match': f"{match.home} vs {match.away}",
                    'score': f"{match.home_score}-{match.away_score}",
                    'pending': count,
                    'date': match.date
                }
        
        # Get recent prediction updates
        recent_updates = Prediction.query.filter(
            Prediction.status.in_(['Won', 'Lost']),
            Prediction.outcome_date >= datetime.utcnow() - timedelta(days=1)
        ).order_by(Prediction.outcome_date.desc()).limit(10).all()
        
        return render_template('admin/update_prediction_outcomes.html',
                            pending_count=pending_count,
                            completed_matches=completed_matches[:10],
                            match_pending_counts=match_pending_counts,
                            recent_updates=recent_updates,
                            title='Update Prediction Outcomes')
    
    @app.route("/admin/predictions/update_single/<int:match_id>", methods=['POST'])
    @login_required
    def admin_update_single_match_predictions(match_id):
        """Update predictions for a single match"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            result = update_prediction_outcomes_sync(match_id=match_id)
            
            # Log activity
            log_activity(current_user.id, 'single_prediction_update', 
                        f'Updated predictions for match {match_id}')
            
            return jsonify(result)
            
        except Exception as e:
            logger.error(f"Error updating single match predictions: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @app.route("/admin/predictions/batch_update", methods=['POST'])
    @login_required
    def admin_batch_update_predictions():
        """Trigger batch update of prediction outcomes"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            data = request.get_json()
            batch_size = data.get('batch_size', 100)
            
            # Check if using Celery
            if CELERY_AVAILABLE:
                # Queue Celery task
                task = update_prediction_outcomes.delay(batch_size=batch_size)
                
                return jsonify({
                    'success': True,
                    'message': 'Batch update queued for processing',
                    'task_id': task.id,
                    'batch_size': batch_size
                })
            else:
                # Run synchronously
                result = update_prediction_outcomes_sync(batch_size=batch_size)
                
                return jsonify(result)
                
        except Exception as e:
            logger.error(f"Error in batch update: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
    @app.route("/admin/predictions/stats", methods=['GET'])
    @login_required
    def admin_prediction_stats():
        """Get prediction statistics for admin"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            # Get overall stats
            total_predictions = Prediction.query.count()
            pending = Prediction.query.filter_by(status='Pending').count()
            won = Prediction.query.filter_by(status='Won').count()
            lost = Prediction.query.filter_by(status='Lost').count()
            
            # Get accuracy
            settled = won + lost
            accuracy = (won / settled * 100) if settled > 0 else 0
            
            # Get profit stats
            total_profit = db.session.query(
                db.func.sum(Prediction.profit_loss)
            ).filter(Prediction.profit_loss.isnot(None)).scalar() or 0
            
            # Get predictions by day (last 30 days)
            thirty_days_ago = datetime.utcnow() - timedelta(days=30)
            
            daily_stats = db.session.query(
                func.date(Prediction.created_at).label('date'),
                func.count(Prediction.id).label('count'),
                func.sum(case((Prediction.status == 'Won', 1), else_=0)).label('wins'),
                func.sum(case((Prediction.status == 'Lost', 1), else_=0)).label('losses')
            ).filter(
                Prediction.created_at >= thirty_days_ago
            ).group_by(func.date(Prediction.created_at)).order_by('date').all()
            
            # Format daily stats
            formatted_daily = []
            for stat in daily_stats:
                formatted_daily.append({
                    'date': stat.date.strftime('%Y-%m-%d'),
                    'total': stat.count,
                    'wins': stat.wins or 0,
                    'losses': stat.losses or 0,
                    'accuracy': ((stat.wins or 0) / (stat.count or 1)) * 100 if stat.count > 0 else 0
                })
            
            # Get top performing users
            top_users = db.session.query(
                User.username,
                func.count(Prediction.id).label('total'),
                func.sum(case((Prediction.status == 'Won', 1), else_=0)).label('wins'),
                func.sum(case((Prediction.status == 'Lost', 1), else_=0)).label('losses'),
                func.sum(Prediction.profit_loss).label('profit')
            ).join(Prediction, User.id == Prediction.user_id).group_by(User.id).order_by(
                func.sum(Prediction.profit_loss).desc()
            ).limit(10).all()
            
            formatted_top_users = []
            for user in top_users:
                settled = (user.wins or 0) + (user.losses or 0)
                formatted_top_users.append({
                    'username': user.username,
                    'total': user.total,
                    'wins': user.wins or 0,
                    'losses': user.losses or 0,
                    'profit': user.profit or 0,
                    'accuracy': ((user.wins or 0) / settled * 100) if settled > 0 else 0
                })
            
            return jsonify({
                'success': True,
                'stats': {
                    'total_predictions': total_predictions,
                    'pending': pending,
                    'won': won,
                    'lost': lost,
                    'accuracy': round(accuracy, 2),
                    'total_profit': round(total_profit, 2),
                    'settlement_rate': ((won + lost) / total_predictions * 100) if total_predictions > 0 else 0
                },
                'daily_stats': formatted_daily,
                'top_users': formatted_top_users,
                'timestamp': datetime.utcnow().isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting prediction stats: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'message': f'Error: {str(e)}'
            }), 500
    
# =========== COMMAND CENTER ROUTE (UPDATED) ===========
    @app.route("/admin/command-center")
    @login_required
    def admin_command_center():
        """Admin Command Center - Advanced monitoring, real-time metrics, and system control"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        try:
            # Get brand colors from config or use defaults
            brand_colors = {
                'primary': '#00f2c3',  # Teal accent
                'secondary': '#0099ff', # Blue
                'accent': '#ff6b35',    # Orange
                'success': '#10b981',   # Green
                'warning': '#f59e0b',   # Yellow
                'danger': '#ef4444',    # Red
                'dark': '#0a1128',      # Dark blue
                'light': '#f8fafc'      # Light
            }
            
            # 1. Comprehensive Health Checks
            health_data = {}
            health_checks = {}
            if hasattr(current_app, 'health_checker'):
                health_data = current_app.health_checker.run_all_checks()
                health_checks = health_data.get('checks', {})
            
            # 2. Real-time Metrics Collection
            metrics_summary = {}
            if hasattr(current_app, 'metrics_collector'):
                metrics_summary = current_app.metrics_collector.get_metrics_summary(hours=24)
            
            # 3. Active Alerts
            active_alerts = []
            if hasattr(current_app, 'alert_manager'):
                active_alerts = current_app.alert_manager.get_active_alerts()
            
            # 4. Alert Statistics
            alert_stats = {}
            if hasattr(current_app, 'alert_manager'):
                try:
                    alert_stats = current_app.alert_manager.get_alert_stats(days=7)
                except:
                    alert_stats = {'total': 0, 'critical': 0, 'warning': 0, 'info': 0}
            
            # 5. System Performance Data
            performance_data = {
                'uptime': calculate_system_uptime(),
                'cpu_usage': metrics_summary.get('system', {}).get('cpu_percent', 0),
                'memory_usage': metrics_summary.get('system', {}).get('memory_percent', 0),
                'disk_usage': metrics_summary.get('system', {}).get('disk_percent', 0),
                'active_users': User.query.filter(
                    User.last_login >= datetime.utcnow() - timedelta(minutes=15)
                ).count(),
                'total_predictions_today': Prediction.query.filter(
                    Prediction.created_at >= datetime.utcnow().date()
                ).count(),
                'prediction_accuracy': calculate_platform_accuracy(),
                'response_time': metrics_summary.get('performance', {}).get('average_response_time', 0)
            }
            
            # 6. Quick Stats Cards
            quick_stats = [
                {
                    'title': 'Total Users',
                    'value': User.query.count(),
                    'icon': 'users',
                    'color': 'primary',
                    'trend': '+12%',
                    'trend_up': True
                },
                {
                    'title': 'Active Today',
                    'value': performance_data['active_users'],
                    'icon': 'user-check',
                    'color': 'success',
                    'trend': '+5%',
                    'trend_up': True
                },
                {
                    'title': 'Predictions',
                    'value': performance_data['total_predictions_today'],
                    'icon': 'chart-line',
                    'color': 'secondary',
                    'trend': '+18%',
                    'trend_up': True
                },
                {
                    'title': 'Accuracy',
                    'value': f"{performance_data['prediction_accuracy']:.1f}%",
                    'icon': 'bullseye',
                    'color': 'accent',
                    'trend': '+2.5%',
                    'trend_up': True
                }
            ]
            
            # 7. System Status
            system_status = {
                'ai_engine': ai_engine is not None,
                'database': True,
                'cache': hasattr(current_app, 'cache') and current_app.cache is not None,
                'email_service': current_app.config.get('MAIL_SERVER') is not None,
                'celery': CELERY_AVAILABLE,
                'monitoring': hasattr(current_app, 'health_checker')
            }
            
            # 8. Recent Activities
            recent_activities = UserActivity.query.order_by(
                UserActivity.timestamp.desc()
            ).limit(8).all()
            
            # 9. Recent Predictions
            recent_predictions = Prediction.query.order_by(
                Prediction.created_at.desc()
            ).limit(6).all()
            
            # 10. CPU & Memory Trends (simulated data for demo)
            cpu_trend = generate_trend_data(hours=12, base=30, variation=20)
            memory_trend = generate_trend_data(hours=12, base=40, variation=15)
            
            return render_template('admin/command_centre.html',
                                # Core Data
                                health_data=health_data,
                                health_checks=health_checks,
                                metrics=performance_data,
                                active_alerts=active_alerts,
                                alert_stats=alert_stats,
                                
                                # Display Data
                                quick_stats=quick_stats,
                                system_status=system_status,
                                recent_activities=recent_activities,
                                recent_predictions=recent_predictions,
                                cpu_trend=cpu_trend,
                                memory_trend=memory_trend,
                                
                                # Brand & Theme
                                brand_colors=brand_colors,
                                page_title='Command Center',
                                refresh_interval=30000,  # 30 seconds
                                
                                title='Command Center | ScorePulse AI',
                                last_updated=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S'))
            
        except Exception as e:
            logger.error(f"Error loading command center: {e}", exc_info=True)
            flash(f'Error loading command center: {str(e)}', 'danger')
            return redirect(url_for('admin_dashboard'))

    # Add to routes.py
    @app.route('/insights/daily')
    @login_required
    def get_daily_insights():
        insights = app.insights_generator.get_recent_insights(days=1)
        return jsonify(insights)
    
    @app.route('/bets/value', methods=['POST'])
    @login_required
    def find_value_bets():
        if current_user.subscription_tier != 'premium': return 'Upgrade required', 403
        data = request.json
        home = data['home']
        away = data['away']
        bets = app.value_bet_finder.find_value_bets(home, away, threshold=5.0)
        return jsonify(bets)


    @app.route("/api/learning/process_match", methods=['POST'])
    @login_required
    def process_match_for_learning():
        """Process a completed match for online learning"""
        if current_user.id != 1:  # Admin only
            return jsonify({"error": "Forbidden"}), 403
        
        try:
            data = request.get_json()
            
            required_fields = ['match_id', 'home_team', 'away_team', 
                            'home_goals', 'away_goals', 'result']
            
            for field in required_fields:
                if field not in data:
                    return jsonify({"error": f"Missing field: {field}"}), 400
            
            # Get the MatchPredictor instance
            predictor = current_app.ai_engine
            
            if not predictor:
                return jsonify({"error": "Predictor not available"}), 503
            
            # Process the match
            success = predictor.process_completed_match({
                'match_id': data['match_id'],
                'home_team': data['home_team'],
                'away_team': data['away_team'],
                'match_date': data.get('match_date', datetime.now().isoformat()),
                'home_goals': int(data['home_goals']),
                'away_goals': int(data['away_goals']),
                'result': data['result']
            })
            
            if success:
                return jsonify({
                    "success": True,
                    "message": "Match processed for online learning"
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "Failed to process match"
                }), 500
                
        except Exception as e:
            logger.error(f"Error processing match for learning: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/learning/insights")
    @login_required
    def get_learning_insights():
        """Get insights from online learning system"""
        if not current_user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        
        try:
            predictor = current_app.ai_engine
            if not predictor:
                return jsonify({"error": "Predictor not available"}), 503
            
            insights = predictor.get_learning_insights()
            
            if insights:
                return jsonify({
                    "success": True,
                    "insights": insights
                })
            else:
                return jsonify({
                    "success": False,
                    "message": "No insights available"
                })
                
        except Exception as e:
            logger.error(f"Error getting learning insights: {e}")
            return jsonify({"error": str(e)}), 500

    @app.route("/api/learning/status")
    def get_learning_status():
        """Get status of online learning system"""
        try:
            predictor = current_app.ai_engine
            if not predictor:
                return jsonify({
                    "online_learning_active": False,
                    "message": "Predictor not available"
                })
            
            status = predictor.online_learner.get_system_status()
            
            return jsonify({
                "online_learning_active": True,
                "status": status
            })
            
        except Exception as e:
            logger.error(f"Error getting learning status: {e}")
            return jsonify({
                "online_learning_active": False,
                "error": str(e)
            }), 500

    @app.route("/admin/learning", methods=['GET', 'POST'])
    @login_required
    def admin_learning():
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        learner = current_app.online_learner
        context = {
            'status': learner.get_system_status(),
            'top_adjusted_teams': [],
            'task_status': None,
            'message': None,
            'message_type': 'info'
        }
        
        if request.method == 'POST':
            action = request.form.get('action')
            
            if action == 'process_unprocessed':
                limit = int(request.form.get('limit', 50))
                # Launch Celery task asynchronously
                if CELERY_AVAILABLE:
                    task = process_unprocessed_learning.delay(limit=limit)
                    context['message'] = f'Task started (ID: {task.id}) – processing up to {limit} results'
                    context['task_id'] = task.id
                    context['message_type'] = 'success'
                else:
                    context['message'] = 'Celery not available for async processing'
                    context['message_type'] = 'warning'
                
                # Also do synchronous processing if prediction_storage is available
                if prediction_storage:
                    try:
                        unprocessed = prediction_storage.get_unprocessed_results(limit=50)
                        processed_count = 0
                        
                        for result in unprocessed:
                            success = learner.process_match_result(result)
                            if success:
                                prediction_storage.mark_as_processed(result['match_id'])
                                processed_count += 1
                        
                        context['message'] = f"Processed {processed_count} new match results."
                        context['message_type'] = 'success' if processed_count > 0 else 'warning'
                        context['form_action_performed'] = True
                    except Exception as e:
                        logger.error(f"Error processing unprocessed results: {e}")
                        context['message'] = f"Error: {str(e)}"
                        context['message_type'] = 'danger'
                else:
                    context['message'] = 'PredictionStorage not available'
                    context['message_type'] = 'warning'
            
            elif action == 'reset_team':
                team_name = request.form.get('team_name', '').strip()
                if team_name and team_name in learner.team_weights.weights['teams']:
                    del learner.team_weights.weights['teams'][team_name]
                    learner.team_weights.save_weights()
                    context['message'] = f"Reset weights for {team_name}"
                    context['message_type'] = 'success'
                else:
                    context['message'] = "Team not found or no weights to reset"
                    context['message_type'] = 'warning'
            
            elif action == 'refresh_status':
                # Just force reload — no heavy computation
                pass
        
        # Refresh status after any action
        context['status'] = learner.get_system_status()
        
        # Get some interesting views
        all_teams = learner.team_weights.weights.get('teams', {})
        if all_teams:
            sorted_teams = sorted(
                all_teams.items(),
                key=lambda x: abs(x[1].get('weight', 1.0) - 1.0),
                reverse=True
            )
            context['top_adjusted_teams'] = sorted_teams[:8]   # top 8 most drifted
            
            context['recent_adjustments'] = sorted_teams[:5]
            
            # Add recent reports
        recent_reports = LearningReport.query.order_by(LearningReport.generated.desc()).limit(5).all()
        context['recent_reports'] = [r.to_dict() for r in recent_reports]
    
        return render_template(
            'admin/admin_learning.html',
            **context,
            title="Online Learning & Adaptive Weights"
        )

    @app.route("/admin/analytics")
    @login_required
    def admin_analytics():
        """Admin analytics dashboard - FIXED VERSION"""
        if current_user.id != 1 and not getattr(current_user, 'is_admin', False):
            flash("Access Denied", 'danger')
            return redirect(url_for('admin_dashboard'))
        
        try:
            # CACHE KEY for analytics
            cache_key = f"admin_analytics_{date.today()}"
            cached_stats = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if cached_stats:
                stats = cached_stats
                activity_data = cached_stats.get('activity_data', {})
                league_success = cached_stats.get('league_success', [])
            else:
                # Platform statistics with simplified calculations
                stats = {
                    'total_users': User.query.count(),
                    'active_users': User.query.filter(
                        User.last_login >= date.today() - timedelta(days=7)
                    ).count(),
                    'total_predictions': Prediction.query.count(),
                    'total_revenue': db.session.query(
                        db.func.sum(Payment.amount)
                    ).filter(
                        Payment.status == 'COMPLETED'
                    ).scalar() or 0,
                    'prediction_accuracy': calculate_platform_accuracy(),
                    'user_growth': calculate_user_growth(),
                    'revenue_trend': calculate_revenue_trend()[:5]  # Only last 5 days
                }
                
                # User activity heatmap data (simplified)
                activity_data = get_user_activity_heatmap()
                
                # Prediction success by league (simplified)
                league_success = get_league_success_rates()[:5]  # Only top 5
                
                # Cache for 10 minutes
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, {
                        'stats': stats,
                        'activity_data': activity_data,
                        'league_success': league_success
                    }, timeout=600)
            
            # Check if template exists
            template_path = os.path.join(current_app.root_path, 'templates', 'admin', 'admin_analytics.html')
            if not os.path.exists(template_path):
                # Use fallback template
                logger.warning(f"Template not found: {template_path}")
                return render_template('admin/fallback_analytics.html',
                                    stats=stats,
                                    activity_data=activity_data,
                                    league_success=league_success,
                                    title='Admin Analytics')
            
            return render_template('admin/admin_analytics.html',
                                stats=stats,
                                activity_data=activity_data,
                                league_success=league_success,
                                title='Admin Analytics')
            
        except Exception as e:
            logger.error(f"Error in admin analytics: {e}", exc_info=True)
            flash('Error loading analytics dashboard. Template might be missing.', 'danger')
            return redirect(url_for('admin_dashboard'))

    @app.route("/admin/run_insights", methods=['POST'])
    @login_required
    def run_insights():
        """Run insights generation"""
        if current_user.id != 1:
            return jsonify({"error": "Forbidden"}), 403

        def task():
            try:
                # Try to import and run insights generator
                current_file_path = os.path.abspath(__file__)
                project_root = os.path.dirname(os.path.dirname(current_file_path))
                
                if project_root not in sys.path:
                    sys.path.insert(0, project_root)
                
                try:
                    from scripts.insights_generator import InsightsGenerator
                    generator = InsightsGenerator()
                    generator.generate_daily_insights()
                    
                    logger.info("Insights generation completed")
                except ImportError as e:
                    logger.warning(f"Insights generator not found: {e}")
                    # Create a simple insights file if it doesn't exist
                    logger.info("Could not create insights generator")
                except Exception as e:
                    logger.error(f"Insights generation failed: {e}")
                    
            except Exception as e:
                logger.error(f"Task setup failed: {e}")

        thread = threading.Thread(target=task)
        thread.daemon = True  # Daemon thread will exit when main exits
        thread.start()
            
        return jsonify({
            "status": "Insights generation started",
            "message": "Check logs for details"
        })

    @app.route("/admin/feedback")
    @login_required
    def admin_feedback():
        """View all feedback"""
        if current_user.id != 1:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        feedback_list = Feedback.query.order_by(Feedback.created_at.desc()).all()
        return render_template('admin/feedback.html',
                             feedback_list=feedback_list,
                             title='Admin - Feedback')

    @app.route("/admin/feedback/mark-read/<int:feedback_id>", methods=['POST'])
    @login_required
    def mark_feedback_read(feedback_id):
        """Updates feedback status from 'new' to 'reviewed'"""
        # Use is_admin for better flexibility than hardcoding ID 1
        if not getattr(current_user, 'is_admin', False) and current_user.id != 1:
            return jsonify({"error": "Forbidden"}), 403
        
        feedback = Feedback.query.get_or_404(feedback_id)
        
        # Update the status to 'reviewed' (This replaces is_read = True)
        feedback.status = 'reviewed'
        
        try:
            db.session.commit()
            return jsonify({
                "success": True, 
                "new_status": feedback.status
            })
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": str(e)}), 500

    # =========== NEW ROUTES ADDED ===========

    @app.route("/notifications")
    @login_required
    def notifications():
        """View all notifications"""
        page = request.args.get('page', 1, type=int)
        unread_only = request.args.get('unread', 'false') == 'true'
        
        query = Notification.query.filter_by(user_id=current_user.id)
        
        if unread_only:
            query = query.filter_by(is_read=False)
        
        notifications = query.order_by(
            Notification.created_at.desc()
        ).paginate(page=page, per_page=20)
        
        # Mark all as read if requested
        if request.args.get('mark_read') == 'all':
            for notif in Notification.query.filter_by(
                user_id=current_user.id,
                is_read=False
            ).all():
                notif.is_read = True
                notif.read_at = datetime.utcnow()
            db.session.commit()
            flash('All notifications marked as read!', 'success')
            return redirect(url_for('notifications'))
        
        return render_template('features/notifications.html',
                             notifications=notifications,
                             unread_only=unread_only,
                             title='Notifications')

    @app.route("/notification/<int:notification_id>/read")
    @login_required
    def notification_read(notification_id):
        """Mark a notification as read"""
        notification = Notification.query.get_or_404(notification_id)
        
        # Check ownership
        if notification.user_id != current_user.id:
            abort(403)
        
        notification.is_read = True
        notification.read_at = datetime.utcnow()
        db.session.commit()
        
        next_url = request.args.get('next', url_for('notifications'))
        return redirect(next_url)

    @app.route("/upgrade")
    @login_required
    def upgrade():
        """Subscription upgrade page"""
        # Get current subscription details
        subscription_details = {
            'current_tier': current_user.subscription_tier,
            'is_premium': current_user.is_premium,
            'premium_expiry': current_user.premium_expiry,
            'days_left': (current_user.premium_expiry - datetime.utcnow()).days if current_user.premium_expiry else 0
        }
        
        # Get available tiers
        tiers = [
            {
                'name': 'free',
                'daily_limit': 3,
                'monthly_price': 0,
                'features': ['Basic predictions', 'Basic analytics', 'Email support'],
                'popular': False
            },
            {
                'name': 'silver',
                'daily_limit': 10,
                'monthly_price': 9.99,
                'features': ['Advanced predictions', 'Team analytics', 'Priority support', 'Email & SMS alerts'],
                'popular': False
            },
            {
                'name': 'gold',
                'daily_limit': 50,
                'monthly_price': 29.99,
                'features': ['Unlimited predictions', 'AI insights', 'Risk analysis', 'API access', '24/7 support'],
                'popular': True
            },
            {
                'name': 'platinum',
                'daily_limit': 999,
                'monthly_price': 99.99,
                'features': ['Everything in Gold', 'Custom models', 'Dedicated account manager', 'White-label solutions'],
                'popular': False
            }
        ]
        
        return render_template('public/upgrade.html',
                         current_tier=current_user.subscription_tier,
                         tiers=tiers,
                         subscription_details=subscription_details,
                         title='Upgrade Subscription')

    # Team Analysis Route - UPDATED WITH REDIS CACHING
    @app.route("/team-analysis", methods=['GET', 'POST'])
    @login_required
    def team_analysis():
        """Team analysis page"""
        form = TeamAnalysisForm()
        
        if form.validate_on_submit():
            team_name = form.team_name.data
            analysis_type = form.analysis_type.data
            time_period = form.time_period.data
            
            # Try to get from cache first
            cache_key = cache_key_generator("team_analysis", team_name, analysis_type, time_period)
            cached_data = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if cached_data:
                team_stats = cached_data.get('team_stats')
                matches = cached_data.get('matches')
                print(f"✅ Using cached team analysis for {team_name}")
            else:
                print(f"🔄 Cache miss for team analysis: {team_name}")
                
                # Get team stats
                team_stats = TeamStats.query.filter_by(
                    team_name=normalize_team_name(team_name)
                ).first()
                
                # Get team matches
                matches = Match.query.filter(
                    or_(
                        Match.home == team_name,
                        Match.away == team_name
                    )
                ).order_by(Match.date.desc()).limit(50).all()
                
                # Calculate stats if not in database
                if not team_stats and matches:
                    stats = generate_team_stats(team_name, matches)
                    team_stats = TeamStats(
                        team_name=team_name,
                        statistics=json.dumps(stats),
                        matches_analyzed=len(matches)
                    )
                    db.session.add(team_stats)
                    db.session.commit()
                
                # Cache the results
                cache_data = {
                    'team_stats': team_stats,
                    'matches': matches
                }
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, cache_data, timeout=1800)
            
            return render_template('features/team_analysis_result.html',
                                 team_name=team_name,
                                 analysis_type=analysis_type,
                                 time_period=time_period,
                                 team_stats=team_stats,
                                 matches=matches[:10] if matches else [],  # Show only 10 recent matches
                                 form=form)
        
        # Get popular teams for suggestions
        popular_teams = TeamStats.query.order_by(
            TeamStats.matches_analyzed.desc()
        ).limit(10).all()
        
        return render_template('features/team_analysis.html',
                             form=form,
                             popular_teams=popular_teams,
                             title='Team Analysis')

    @app.route("/head-to-head", methods=['GET', 'POST'])
    @login_required
    def head_to_head():
        """Head-to-head comparison page"""
        form = HeadToHeadForm()
        
        if form.validate_on_submit():
            team1 = form.team1.data
            team2 = form.team2.data
            include_venue = form.include_venue.data
            recency_weight = form.recency_weight.data
            show_market = form.show_market.data
            
            # Get head-to-head stats - WITH CACHING
            cache_key = cache_key_generator("h2h_full", team1, team2)
            cached_data = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
            
            if cached_data:
                h2h_stats = cached_data.get('h2h_stats')
                recent_matches = cached_data.get('recent_matches')
                print(f"✅ Using cached head-to-head for {team1} vs {team2}")
            else:
                print(f"🔄 Cache miss for head-to-head: {team1} vs {team2}")
                
                # Get head-to-head stats
                h2h_stats = get_head_to_head_stats(team1, team2)
                
                # Get recent matches between teams
                recent_matches = Match.query.filter(
                    ((Match.home == team1) & (Match.away == team2)) |
                    ((Match.home == team2) & (Match.away == team1))
                ).order_by(Match.date.desc()).limit(20).all()
                
                # Cache the results
                cache_data = {
                    'h2h_stats': h2h_stats,
                    'recent_matches': recent_matches
                }
                if hasattr(current_app, 'cache') and current_app.cache:
                    current_app.cache.set(cache_key, cache_data, timeout=1800)
            
            return render_template('features/head_to_head_result.html',
                                 team1=team1,
                                 team2=team2,
                                 h2h_stats=h2h_stats,
                                 recent_matches=recent_matches,
                                 include_venue=include_venue,
                                 recency_weight=recency_weight,
                                 show_market=show_market,
                                 form=form)
        
        # Get team suggestions
        teams = Match.query.with_entities(Match.home).distinct().limit(20).all()
        team_suggestions = [team[0] for team in teams]
        
        return render_template('features/head_to_head.html',
                             form=form,
                             team_suggestions=team_suggestions,
                             title='Head-to-Head Analysis')

    @app.route("/match-prediction", methods=['GET', 'POST'])
    @login_required
    def match_prediction():
        """Match prediction page"""
        form = MatchPredictionForm()
        
        # Populate league choices dynamically
        leagues = Match.query.with_entities(Match.league).distinct().all()
        league_choices = [('', 'Any League')] + [(league[0], league[0]) for league in leagues if league[0]]
        form.league.choices = league_choices
        
        if form.validate_on_submit():
            home_team = normalize_team_name(form.home_team.data)
            away_team = normalize_team_name(form.away_team.data)
            league = form.league.data
            include_form = form.include_form.data
            include_h2h = form.include_h2h.data
            include_odds = form.include_odds.data
            
            # Check daily prediction limit
            if not current_user.can_make_prediction():
                flash('Daily prediction limit reached! Please upgrade your plan.', 'warning')
                return redirect(url_for('upgrade'))
            
            # Generate real prediction using AI engine
            if not app.ai_engine:
                flash('Prediction engine is currently unavailable. Please try again later.', 'danger')
                return redirect(url_for('dashboard'))
            
            try:
                # Check for cached prediction
                cache_key = cache_key_generator("match_pred", home_team, away_team, league, 
                                               include_form, include_h2h, include_odds)
                cached_result = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
                
                if cached_result:
                    prediction = cached_result
                    print(f"✅ Using cached match prediction for {home_team} vs {away_team}")
                else:
                    print(f"🔄 Cache miss for match prediction: {home_team} vs {away_team}")
                    
                    prediction = app.ai_engine.predict_for_web(
                        home_team, 
                        away_team, 
                        subscription_tier=current_user.subscription_tier
                    )
                    
                    # Cache the result
                    if hasattr(current_app, 'cache') and current_app.cache:
                        current_app.cache.set(cache_key, prediction, timeout=1800)
                
                if 'error' in prediction:
                    flash(prediction['error'], 'danger')
                    return redirect(url_for('match_prediction'))
                
                # Adjust prediction dict to match template expectations
                prediction['confidence'] = {
                    'label': prediction.pop('confidence_label', 'MEDIUM'),
                    'color': prediction.pop('confidence_color', 'text-yellow-400'),
                    'score': prediction.pop('confidence_score', 50.0)  # Optional, not used in template
                }
                
                # Note: include_form, include_h2h, include_odds are not directly supported in predict_for_web
                # For now, add a note to analysis if exclusions are requested
                if not include_form or not include_h2h or not include_odds:
                    exclusions = []
                    if not include_form:
                        exclusions.append("recent form")
                    if not include_h2h:
                        exclusions.append("head-to-head")
                    if not include_odds:
                        exclusions.append("odds analysis")
                    prediction['analysis'] = (prediction.get('analysis', '') + 
                                            f"\nℹ️ Excluded per user request: {', '.join(exclusions)}.")
                    
                app.performance_analyzer.record_prediction(match_id, prediction, actual_result=None)
                
                # Add league if provided (though not used in prediction)
                
                prediction['league'] = league or 'Unknown'
                
                # Save prediction to database
                new_pred = Prediction(
                    user_id=current_user.id,
                    home_team=home_team,
                    away_team=away_team,
                    pred_outcome=prediction['prediction_outcome'],
                    confidence=prediction['prediction_confidence'],
                    status='Pending',
                    match_date=datetime.now(),  # TODO: Use actual match date if available from form or AI
                    created_at=datetime.utcnow()
                )
                db.session.add(new_pred)
                db.session.commit()
                
                # Log activity
                log_activity(
                    current_user.id, 
                    'match_prediction', 
                    f"Generated prediction for {home_team} vs {away_team}"
                )
                
                # Render results using the provided results.html template
                return render_template('features/results.html',
                                    result=prediction,
                                    form=form)
            
            except Exception as e:
                logger.error(f"Error generating prediction: {e}")
                flash('An error occurred while generating the prediction. Please try again.', 'danger')
                return redirect(url_for('match_prediction'))
        
        # For GET request, provide team suggestions from AI engine if available
        team_suggestions = app.ai_engine.all_teams if app.ai_engine else get_all_teams()
        team_suggestions = sorted(team_suggestions)[:20]  # Limit to top 20 for suggestions
        
        return render_template('features/match_prediction.html', 
                            form=form, 
                            team_suggestions=team_suggestions,
                            title='Match Prediction')

    # Data Agent Routes
    @app.route("/load-data", methods=['GET', 'POST'])
    @login_required
    def load_data():
        """Data loading page"""
        # Only allow admin or premium users
        if current_user.subscription_tier not in ['gold', 'platinum']:
            flash('This feature requires Gold or Platinum subscription.', 'warning')
            return redirect(url_for('dashboard'))
        
        form = DataLoadForm()
        
        if form.validate_on_submit():
            # Process data loading
            source = form.data_source.data
            file_path = form.file_path.data
            
            # Log the attempt
            validation_log = DataValidationLog(
                source_name=source,
                total_rows=0,
                valid=False,
                issues=["Feature implementation in progress"],
                warnings=[],
                statistics={}
            )
            db.session.add(validation_log)
            db.session.commit()
            
            flash('Data loading functionality coming soon!', 'info')
            return redirect(url_for('dashboard'))
        
        # Get recent data validation logs
        validation_logs = DataValidationLog.query.order_by(
            DataValidationLog.created_at.desc()
        ).limit(10).all()
        
        return render_template('features/load_data.html',
                             form=form,
                             validation_logs=validation_logs,
                             title='Load Data')
        
        
    @app.route('/health')
    def health_check():
        """Public health endpoint — used by load balancers, uptime monitors, etc."""
        try:
            result = app.health_checker.run_all_checks()
            
            # Quick overall status
            overall = result['overall_status']
            critical_count = sum(1 for c in result['checks'].values() if c.get('status') == 'critical')
            
            return jsonify({
                'status': overall,
                'critical_components': critical_count,
                'timestamp': datetime.utcnow().isoformat(),
                'details': {
                    k: {'status': v['status'], 'message': v.get('message')} 
                    for k, v in result['checks'].items()
                }
            })
        except Exception as e:
            return jsonify({'status': 'critical', 'error': str(e)}), 503
        
    @app.route("/generate-features", methods=['GET', 'POST'])
    @login_required
    def generate_features():
        """Feature generation page"""
        # Only allow admin or premium users
        if current_user.subscription_tier not in ['gold', 'platinum']:
            flash('This feature requires Gold or Platinum subscription.', 'warning')
            return redirect(url_for('dashboard'))
        
        form = FeatureGenerationForm()
        
        if form.validate_on_submit():
            feature_type = form.feature_type.data
            window_sizes = form.window_sizes.data
            
            # Log the attempt
            cache_entry = FeatureCache(
                cache_key=f"features_{datetime.utcnow().timestamp()}",
                data={"status": "processing", "type": feature_type},
                expiry=datetime.utcnow() + timedelta(hours=1)
            )
            db.session.add(cache_entry)
            db.session.commit()
            
            flash('Feature generation initiated! Results will be cached for 1 hour.', 'success')
            return redirect(url_for('dashboard'))
        
        # Get recent feature cache entries
        recent_cache = FeatureCache.query.order_by(
            FeatureCache.created_at.desc()
        ).limit(5).all()
        
        return render_template('features/generate_features.html',
                             form=form,
                             recent_cache=recent_cache,
                             title='Generate Features')

    # Utility routes for the dashboard
    @app.route("/api/dashboard-stats")
    @login_required
    def dashboard_stats():
        """API endpoint for dashboard statistics"""
        # Get basic stats - WITH CACHING
        cache_key = f"dashboard_stats_{current_user.id}"
        cached_stats = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
        
        if cached_stats:
            return jsonify(cached_stats)
        
        # Calculate stats if not cached
        total_pred = Prediction.query.filter_by(user_id=current_user.id).count()
        wins = Prediction.query.filter_by(user_id=current_user.id, status='Won').count()
        losses = Prediction.query.filter_by(user_id=current_user.id, status='Lost').count()
        pending = Prediction.query.filter_by(user_id=current_user.id, status='Pending').count()
        
        accuracy = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
        
        # Get recent predictions
        recent_predictions = Prediction.query.filter_by(
            user_id=current_user.id
        ).order_by(Prediction.created_at.desc()).limit(5).all()
        
        recent_data = []
        for pred in recent_predictions:
            recent_data.append({
                'id': pred.id,
                'home_team': pred.home_team,
                'away_team': pred.away_team,
                'prediction': pred.pred_outcome,
                'status': pred.status,
                'date': pred.match_date.strftime('%Y-%m-%d'),
                'confidence': pred.confidence
            })
        
        # Get unread notifications count
        unread_count = Notification.query.filter_by(
            user_id=current_user.id,
            is_read=False
        ).count()
        
        stats_data = {
            'stats': {
                'total_predictions': total_pred,
                'wins': wins,
                'losses': losses,
                'pending': pending,
                'accuracy': round(accuracy, 1),
                'daily_predictions_left': getattr(current_user, 'daily_prediction_limit', 10) - getattr(current_user, 'predictions_today', 0),
                'credits': getattr(current_user, 'credits', 0)
            },
            'recent_predictions': recent_data,
            'unread_notifications': unread_count
        }
        
        # Cache the stats for 5 minutes
        if hasattr(current_app, 'cache') and current_app.cache:
            current_app.cache.set(cache_key, stats_data, timeout=300)
        
        return jsonify(stats_data)

    @app.route("/api/performance-chart")
    @login_required
    def performance_chart():
        """API endpoint for performance chart data"""
        # Get performance data for last 30 days - WITH CACHING
        cache_key = f"performance_chart_{current_user.id}"
        cached_data = current_app.cache.get(cache_key) if hasattr(current_app, 'cache') and current_app.cache else None
        
        if cached_data:
            return jsonify(cached_data)
        
        # Calculate if not cached
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Query predictions by day
        daily_stats = db.session.query(
            func.strftime('%Y-%m-%d', Prediction.created_at).label('date'),
            func.count(Prediction.id).label('total'),
            func.sum(case((Prediction.status == 'Won', 1), else_=0)).label('wins')
        ).filter(
            Prediction.user_id == current_user.id,
            Prediction.created_at >= thirty_days_ago
        ).group_by(func.strftime('%Y-%m-%d', Prediction.created_at)).order_by('date').all()
        
        # Prepare chart data
        dates = []
        totals = []
        accuracies = []
        
        for stat in daily_stats:
            dates.append(stat.date.strftime('%Y-%m-%d'))
            totals.append(stat.total)
            if stat.total > 0:
                accuracy = (stat.wins or 0) / stat.total * 100
            else:
                accuracy = 0
            accuracies.append(accuracy)
        
        chart_data = {
            'dates': dates,
            'totals': totals,
            'accuracies': accuracies
        }
        
        # Cache for 10 minutes
        if hasattr(current_app, 'cache') and current_app.cache:
            current_app.cache.set(cache_key, chart_data, timeout=600)
        
        return jsonify(chart_data)

    # Cache Management Endpoints
    @app.route("/api/cache/stats")
    @login_required
    def api_cache_stats():
        """Get cache statistics (admin only)"""
        if not current_user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        
        if not hasattr(current_app, 'cache') or current_app.cache is None:
            return jsonify({
                "success": False,
                "message": "Cache not available"
            })
        
        try:
            stats = current_app.cache.get_stats()
            return jsonify({
                "success": True,
                "stats": stats
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route("/api/cache/clear", methods=['POST'])
    @login_required
    def api_cache_clear():
        """Clear cache entries (admin only)"""
        if not current_user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        
        if not hasattr(current_app, 'cache') or current_app.cache is None:
            return jsonify({
                "success": False,
                "message": "Cache not available"
            })
        
        try:
            data = request.get_json()
            pattern = data.get('pattern', '*')
            
            current_app.cache.clear(pattern)
            
            return jsonify({
                "success": True,
                "message": f"Cache cleared for pattern: {pattern}"
            })
        except Exception as e:
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500

    @app.route("/api/cache/patterns")
    @login_required
    def api_cache_patterns():
        """List cache key patterns (admin only)"""
        if not current_user.is_admin:
            return jsonify({"error": "Forbidden"}), 403
        
        # Common cache patterns used in the app
        patterns = [
            "prediction:*",
            "matches:*",
            "team_stats:*",
            "h2h:*",
            "team_hierarchy",
            "value_bets:*",
            "top_predictions:*",
            "trending_predictions",
            "user_stats:*",
            "league_success:*",
            "prediction_result:*",
            "team_analysis:*",
            "h2h_full:*",
            "match_pred:*",
            "dashboard_stats:*",
            "performance_chart:*",
            "live_scores_api",
            "user_analytics:*"
        ]
        
        return jsonify({
            "success": True,
            "patterns": patterns
        })
        

    # ────────────────────────────────────────────────
#         MONITORING & OBSERVABILITY ROUTES
# ────────────────────────────────────────────────

    @app.route("/admin/monitoring/health", methods=['GET'])
    @login_required
    def admin_monitoring_health():
        """Get comprehensive system health status (JSON API)"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        try:
            # Run all health checks
            health_data = current_app.health_checker.run_all_checks()
            
            # Get active alerts (no check_health_data anymore — we use existing alerts)
            active_alerts = current_app.alert_manager.get_active_alerts()
            
            return jsonify({
                'success': True,
                'health': health_data,
                'active_alerts_count': len(active_alerts),
                'alerts_sample': active_alerts[:5],  # first 5 for preview
                'timestamp': datetime.utcnow().isoformat()
            })
        
        except Exception as e:
            logger.error(f"Health check endpoint failed: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


    @app.route("/admin/monitoring/metrics", methods=['GET'])
    @login_required
    def admin_monitoring_metrics():
        """Get system metrics summary (JSON API)"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            hours = request.args.get('hours', 24, type=int)
            if hours < 1 or hours > 168:  # reasonable limit: 1 hour to 7 days
                hours = 24
                
            metrics = current_app.metrics_collector.get_metrics_summary(hours=hours)
            
            return jsonify({
                'success': True,
                'metrics': metrics,
                'hours': hours,
                'timestamp': datetime.utcnow().isoformat()
            })
        
        except Exception as e:
            logger.error(f"Metrics endpoint failed: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500


    @app.route("/admin/monitoring/dashboard", methods=['GET'])
    @login_required
    def admin_monitoring_dashboard():
        """Main monitoring/command center dashboard (HTML view)"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        try:
            # ── Health ───────────────────────────────────────
            health_data = current_app.health_checker.run_all_checks()
            
            # ── Metrics ──────────────────────────────────────
            metrics_summary = current_app.metrics_collector.get_metrics_summary(hours=24)
            
            # ── Alerts ───────────────────────────────────────
            active_alerts = current_app.alert_manager.get_active_alerts()
            alert_stats = current_app.alert_manager.get_alert_stats(days=7)
            
            # ── Training / Model Champions (from logger) ─────
            history_df = current_app.training_logger.get_history(limit=100)
            champions_summary = {}
            if not history_df.empty:
                latest_by_target = history_df.sort_values('Timestamp').groupby('Target').last()
                champions_summary = latest_by_target.to_dict(orient='index')
            
            # ── Dashboard HTML components (from dashboard.py) ─
            overview_metrics_html = current_app.dashboard_builder.generate_overview_metrics(history_df)
            performance_charts_html = current_app.dashboard_builder.generate_performance_charts(history_df)
            system_gauges_html = current_app.dashboard_builder.generate_system_gauges(
                metrics_summary.get('system', {})
            )
            alert_dashboard_html = current_app.dashboard_builder.generate_alert_dashboard(active_alerts)
            prediction_analytics_html = current_app.dashboard_builder.generate_prediction_analytics_dashboard(
                metrics_summary.get('predictions', {})
            )
            
            return render_template(
                'admin/monitoring_dashboard.html',   # ← rename your command_center.html to this, or keep as-is
                title='Monitoring Command Center',
                health_data=health_data,
                metrics=metrics_summary,
                active_alerts=active_alerts,
                alert_stats=alert_stats,
                champions=champions_summary,
                # HTML snippets to inject
                overview_metrics_html=overview_metrics_html,
                performance_charts_html=performance_charts_html,
                system_gauges_html=system_gauges_html,
                alert_dashboard_html=alert_dashboard_html,
                prediction_analytics_html=prediction_analytics_html,
                last_updated=datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')
            )
        
        except Exception as e:
            logger.error(f"Monitoring dashboard failed: {e}", exc_info=True)
            flash(f'Error loading monitoring dashboard: {str(e)}', 'danger')
            return redirect(url_for('admin_dashboard'))


    @app.route("/admin/monitoring/alerts", methods=['GET', 'POST'])
    @login_required
    def admin_monitoring_alerts():
        """Alert viewing and management interface"""
        if not current_user.is_admin:
            flash("Access Denied", 'danger')
            return redirect(url_for('home'))
        
        if request.method == 'POST':
            action = request.form.get('action')
            alert_id = request.form.get('alert_id')  # assuming alert_id is string or int
            
            if not alert_id:
                flash("No alert selected", 'warning')
                return redirect(request.url)
            
            success = False
            
            if action == 'acknowledge':
                note = request.form.get('note', '').strip()
                success = current_app.alert_manager.acknowledge_alert(alert_id, current_user.id, note)
                flash('Alert acknowledged' if success else 'Alert not found', 'success' if success else 'warning')
            
            elif action == 'resolve':
                note = request.form.get('note', '').strip()
                success = current_app.alert_manager.resolve_alert(alert_id, current_user.id, note)
                flash('Alert resolved' if success else 'Alert not found', 'success' if success else 'warning')
            
            elif action == 'silence':
                try:
                    hours = int(request.form.get('hours', 24))
                    reason = request.form.get('reason', '').strip()
                    current_app.alert_manager.silence_alert(alert_id, hours, reason)
                    flash(f'Alert silenced for {hours} hours', 'success')
                except ValueError:
                    flash('Invalid hours value', 'danger')
            
            return redirect(request.url)
        
        # GET: show alerts
        try:
            active_alerts = current_app.alert_manager.get_active_alerts()
            alert_stats = current_app.alert_manager.get_alert_stats(days=14)  # extended to 14 days
            recent_alerts = current_app.alert_manager.alerts[-50:]  # last 50 for display
            
            return render_template(
                'admin/alerts.html',
                active_alerts=active_alerts,
                alert_stats=alert_stats,
                all_alerts=recent_alerts,
                title='Alert Management'
            )
        
        except Exception as e:
            logger.error(f"Alerts page failed: {e}", exc_info=True)
            flash('Error loading alerts', 'danger')
            return redirect(url_for('admin_dashboard'))


    @app.route("/admin/monitoring/metrics/export", methods=['GET'])
    @login_required
    def admin_metrics_export():
        """Export metrics in JSON or CSV"""
        if not current_user.is_admin:
            return jsonify({'error': 'Forbidden'}), 403
        
        try:
            hours = request.args.get('hours', 24, type=int)
            fmt = request.args.get('format', 'json').lower()
            
            if hours < 1 or hours > 720:  # max 30 days
                hours = 24
            
            summary = current_app.metrics_collector.get_metrics_summary(hours=hours)
            
            if fmt == 'csv':
                # Flatten and export as CSV
                df = pd.json_normalize(summary, sep='_')
                csv_data = df.to_csv(index=False)
                
                filename = f"scorepulse_metrics_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
                
                return Response(
                    csv_data,
                    mimetype='text/csv',
                    headers={'Content-Disposition': f'attachment; filename="{filename}"'}
                )
            
            # Default: JSON
            return jsonify({
                'success': True,
                'hours': hours,
                'metrics': summary,
                'exported_at': datetime.utcnow().isoformat()
            })
        
        except Exception as e:
            logger.error(f"Metrics export failed: {e}", exc_info=True)
            return jsonify({
                'success': False,
                'error': str(e)
            }), 500

    # Context processor  
    @app.context_processor
    def inject_google_oauth():
        return dict(
            google_oauth_enabled=current_app.config.get('GOOGLE_OAUTH_ENABLED', True),
            current_year=datetime.now().year,
            app_name=current_app.config.get('APP_NAME', 'ScorePulse AI'),
            current_user=current_user,
            now=datetime.now,
            orchestration_enabled=pitch_commander is not None,
            cache_enabled=hasattr(current_app, 'cache') and current_app.cache is not None,
            celery_available=CELERY_AVAILABLE
        )

def register_routes(app):
    """Register all routes with the Flask app"""
    global ai_engine, value_bet_finder, live_tracker, performance_analyzer, pitch_commander
    global health_checker, alert_manager, metrics_collector, training_logger, dashboard_builder
    
    # Note: Errors blueprint is registered in __init__.py
    # No need to register it here again
    init_oauth(app)
    
    # Initialize AI engines
    try:
        # Use the already-initialized AI engine from app context
        if hasattr(app, 'ai_engine') and app.ai_engine:
            ai_engine = app.ai_engine
            print("[OK] Using pre-initialized AI Engine from app context")
        else:
            # Fallback: try to initialize here if not done in __init__.py
            print("[INFO] AI Engine not pre-initialized, attempting initialization in register_routes...")
            current_file_path = os.path.abspath(__file__)
            project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))
            
            if project_root not in sys.path:
                sys.path.insert(0, project_root)
            
            print(f"[INFO] Linking ML Engine from: {project_root}")
            
            import main
            ai_engine = main.MatchPredictor()
            app.ai_engine = ai_engine
            print("[OK] SCORE_PULSE Engine Online.")
        
        # Load additional engines if available
        try:
            from soccer_match_prediction.scripts.value_bet_finder import ValueBetFinder
            value_bet_finder = ValueBetFinder()
            print("[OK] Value Bet Finder Online.")
        except ImportError as e:
            print(f"[WARN] Value Bet Finder not available: {e}")
            value_bet_finder = None
            
        try:
            from soccer_match_prediction.scripts.live_tracker import LiveMatchTracker
            live_tracker = LiveMatchTracker()
            print("[OK] Live Match Tracker Online.")
        except ImportError as e:
            print(f"[WARN] Live Match Tracker not available: {e}")
            live_tracker = None
            
        try:
            from soccer_match_prediction.scripts.performance_analyzer import PerformanceAnalyzer
            performance_analyzer = PerformanceAnalyzer()
            print("[OK] Performance Analyzer Online.")
        except ImportError as e:
            print(f"[WARN] Performance Analyzer not available: {e}")
            performance_analyzer = None
            
        # Try to load Pitch Commander (orchestration engine)
        try:
            from ..pitch_commander import PitchCommander
            pitch_commander = PitchCommander()
            print("[OK] Pitch Commander (Orchestration) Online.")
        except ImportError as e:
            print(f"[WARN] Pitch Commander not available: {e}")
            pitch_commander = None
            
    except ImportError as e:
        print(f"[ERROR] Failed to import 'main': {e}")
        ai_engine = None
    except Exception as e:
        print(f"[WARN] SCORE_PULSE Engine Error: {e}")
        ai_engine = None
        
    # Set app start time for uptime calculation
        
    if not hasattr(app, 'app_start_time'):
        app.app_start_time = datetime.utcnow()
        app.config['APP_START_TIME'] = app.app_start_time
    # ────────────────────────────────────────────────
    #     MONITORING & OBSERVABILITY INITIALIZATION
    # ────────────────────────────────────────────────
    try:
        # Health checking system
        health_checker = HealthChecker(app)
        app.health_checker = health_checker
        print("✅ HealthChecker initialized")

        # Alert system (very important — matches your existing usage of alert_manager)
        alert_manager = AlertSystem()
        app.alert_manager = alert_manager
        print("✅ AlertSystem (alert_manager) initialized")

        # Real-time metrics collector
        metrics_collector = MetricsCollector(app)
        app.metrics_collector = metrics_collector
        metrics_collector.start()   # ← starts background thread
        print("✅ MetricsCollector started")

        # Centralized training/performance logger
        training_logger = get_logger(log_level="INFO")
        app.training_logger = training_logger
        print("✅ TrainingLogger ready")

        # Dashboard builder (optional — if you render charts in admin)
        dashboard_builder = Dashboard()
        app.dashboard_builder = dashboard_builder
        print("✅ DashboardBuilder initialized")

    except Exception as e:
        print(f"⚠️ Monitoring initialization failed: {e}")
        import traceback
        traceback.print_exc()
        
    # Attach AI engines to app for easy access
    app.ai_engine = ai_engine
    app.alert_manager       = alert_manager
    app.metrics_collector   = metrics_collector
    app.health_checker      = health_checker
    app.training_logger     = training_logger
    app.value_bet_finder = value_bet_finder
    app.live_tracker = live_tracker
    app.performance_analyzer = performance_analyzer
    app.pitch_commander = pitch_commander
    app.online_learner = online_learner
    
    # Create all routes
    create_routes(app)
    
    # Register user loader
    login_manager.user_loader(load_user)
    
    print("✅ Routes registered successfully with Redis caching")
    print(f"✅ Celery integration: {'Enabled' if CELERY_AVAILABLE else 'Disabled (fallback to sync mode)'}")