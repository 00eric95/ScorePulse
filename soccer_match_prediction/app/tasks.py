# app/tasks.py

import time
import json
import logging
import traceback
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from celery import Task, group, chain, chord
from celery.exceptions import MaxRetriesExceededError
from flask import current_app, render_template
from flask_mail import Message
from sqlalchemy import func

from . import db, mail, celery
from .models import (
    User, Prediction, Payment, Notification, 
    Leaderboard, Feedback, UserActivity,
    SystemLog, LearningReport, ModelEvaluation
)

from updating.online_learner import OnlineLearningSystem     # adjusted path
from updating.prediction_storage import prediction_storage

logger = logging.getLogger(__name__)

# ==================== EMAIL TASKS ====================

@celery.task(bind=True, max_retries=3, default_retry_delay=30)
def send_email_task(self, to: List[str], subject: str, body: str, 
                    html: Optional[str] = None, attachments: Optional[List] = None):
    """Send email asynchronously"""
    try:
        msg = Message(
            subject=subject,
            recipients=to,
            body=body,
            html=html,
            sender=current_app.config.get('MAIL_DEFAULT_SENDER', 'noreply@scorepulse.ai')
        )
        
        if attachments:
            for attachment in attachments:
                msg.attach(*attachment)
        
        mail.send(msg)
        logger.info(f"✅ Email sent to {', '.join(to)}: {subject}")
        return {'status': 'success', 'recipients': to}
        
    except Exception as e:
        logger.error(f"❌ Email sending failed: {e}")
        
        # Retry logic
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.error(f"❌ Max retries exceeded for email to {to}")
            return {'status': 'failed', 'error': str(e)}



@celery.task
def send_verification_email(user_id: int, verification_code: str):
    """Send verification email"""
    user = User.query.get(user_id)
    if not user:
        logger.error(f"User {user_id} not found for verification email")
        return
    
    # Render email template
    html = render_template('emails/verification.html',
                          user=user,
                          verification_code=verification_code,
                          app_name=current_app.config.get('APP_NAME', 'ScorePulse AI'))
    
    send_email_task.delay(
        to=[user.email],
        subject=f"Verify your email - {current_app.config.get('APP_NAME', 'ScorePulse AI')}",
        body=f"Your verification code is: {verification_code}",
        html=html
    )

@celery.task
def send_welcome_email(user_id: int):
    """Send welcome email to new user"""
    user = User.query.get(user_id)
    if not user:
        return
    
    html = render_template('emails/welcome.html',
                          user=user,
                          app_name=current_app.config.get('APP_NAME', 'ScorePulse AI'))
    
    send_email_task.delay(
        to=[user.email],
        subject=f"Welcome to {current_app.config.get('APP_NAME', 'ScorePulse AI')}!",
        body=f"Welcome {user.username}! Thank you for joining us.",
        html=html
    )

@celery.task
def send_password_reset_email(user_id: int, reset_token: str):
    """Send password reset email"""
    user = User.query.get(user_id)
    if not user:
        return
    
    reset_url = f"{current_app.config.get('BASE_URL', 'http://localhost:5000')}/reset_password/{reset_token}"
    
    html = render_template('emails/password_reset.html',
                          user=user,
                          reset_url=reset_url,
                          app_name=current_app.config.get('APP_NAME', 'ScorePulse AI'))
    
    send_email_task.delay(
        to=[user.email],
        subject="Password Reset Request",
        body=f"Click here to reset your password: {reset_url}",
        html=html
    )

@celery.task
def perform_health_check():
    """Scheduled health check"""
    from monitoring.health_checker import HealthChecker
    checker = HealthChecker(current_app._get_current_object())
    result = checker.run_all_checks()
    
    # Check for alerts
    from monitoring.alert_manager import AlertManager
    alert_manager = AlertManager(current_app._get_current_object())
    alert_manager.check_health_data(result)
    
    return result

@celery.task
def send_daily_reports_task():
    """Send daily reports to users who opted in"""
    users = User.query.filter_by(
        email_notifications=True,
        weekly_report=True,
        is_active=True
    ).all()
    
    today = datetime.utcnow().date()
    yesterday = today - timedelta(days=1)
    
    tasks = []
    for user in users:
        # Get yesterday's predictions
        predictions = Prediction.query.filter(
            Prediction.user_id == user.id,
            Prediction.match_date == yesterday,
            Prediction.status.in_(['Won', 'Lost'])
        ).all()
        
        if not predictions:
            continue
        
        # Calculate stats
        wins = sum(1 for p in predictions if p.status == 'Won')
        losses = sum(1 for p in predictions if p.status == 'Lost')
        accuracy = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
        
        # Render report
        html = render_template('emails/daily_report.html',
                              user=user,
                              date=yesterday,
                              predictions=predictions,
                              wins=wins,
                              losses=losses,
                              accuracy=accuracy,
                              total=len(predictions))
        
        # Schedule email task
        task = send_email_task.s(
            to=[user.email],
            subject=f"Daily Prediction Report - {yesterday.strftime('%Y-%m-%d')}",
            body=f"Your daily report: {wins} wins, {losses} losses, {accuracy:.1f}% accuracy",
            html=html
        )
        tasks.append(task)
    
    # Send all emails in parallel
    if tasks:
        group(tasks).apply_async()
        logger.info(f"📧 Scheduled daily reports for {len(tasks)} users")
    
    return {'users_notified': len(tasks)}

# ==================== PREDICTION TASKS ====================

class PredictionTask(Task):
    """Base class for prediction tasks"""
    abstract = True
    
    def on_success(self, retval, task_id, args, kwargs):
        logger.info(f"✅ Prediction task {task_id} completed successfully")
        
    def on_failure(self, exc, task_id, args, kwargs, einfo):
        logger.error(f"❌ Prediction task {task_id} failed: {exc}")
        # Log to database
        log = SystemLog(
            level='ERROR',
            module='tasks',
            function=self.__name__,
            message=f"Task {task_id} failed: {str(exc)}",
            traceback=traceback.format_exc()
        )
        db.session.add(log)
        db.session.commit()

@celery.task(base=PredictionTask, bind=True, queue='predictions')
def process_batch_predictions(self, predictions_data: List[Dict]):
    """Process multiple predictions in batch"""
    results = []
    
    for i, pred_data in enumerate(predictions_data):
        try:
            # Update progress
            self.update_state(
                state='PROGRESS',
                meta={'current': i + 1, 'total': len(predictions_data)}
            )
            
            # Process single prediction
            result = process_single_prediction.delay(pred_data).get(timeout=30)
            results.append(result)
            
        except Exception as e:
            logger.error(f"Error processing prediction {i}: {e}")
            results.append({'error': str(e), 'data': pred_data})
    
    return {'processed': len(results), 'results': results}

@celery.task(base=PredictionTask, bind=True, queue='predictions')
def process_single_prediction(self, prediction_data: Dict):
    """Process a single prediction"""
    try:
        start_time = time.time()
        
        # Get AI engine
        ai_engine = current_app.ai_engine
        if not ai_engine:
            raise Exception("AI engine not available")
        
        # Extract data
        home_team = prediction_data.get('home_team')
        away_team = prediction_data.get('away_team')
        user_id = prediction_data.get('user_id')
        subscription_tier = prediction_data.get('subscription_tier', 'free')
        
        # Get prediction from AI engine
        result = ai_engine.predict_for_web(home_team, away_team, subscription_tier)
        
        if 'error' in result:
            raise Exception(result['error'])
        
        # Save to database
        prediction = Prediction(
            user_id=user_id,
            home_team=home_team,
            away_team=away_team,
            match_date=datetime.utcnow().date(),
            pred_outcome=result.get('prediction_outcome', 'D'),
            ai_prediction=result.get('prediction_outcome', 'D'),
            confidence=result.get('prediction_confidence', 50),
            mcmc_home_prob=result.get('win_prob', {}).get('home', 0),
            mcmc_draw_prob=result.get('win_prob', {}).get('draw', 0),
            mcmc_away_prob=result.get('win_prob', {}).get('away', 0),
            btts_probability=result.get('btts', 50.0),
            over25_probability=result.get('over25', 50.0),
            total_goals_pred=result.get('total_goals', 2.5),
            recommended_stake=result.get('recommended_stake', 2.5),
            market_odds=result.get('market_odds', 2.5),
            risk_level=result.get('risk_level', 'MEDIUM'),
            model_used=result.get('model_used', 'Random Forest'),
            status='Pending',
            created_at=datetime.utcnow()
        )
        
        db.session.add(prediction)
        db.session.commit()
        
        execution_time = time.time() - start_time
        
        return {
            'prediction_id': prediction.id,
            'status': 'success',
            'execution_time': execution_time,
            'confidence': prediction.confidence,
            'outcome': prediction.pred_outcome
        }
        
    except Exception as e:
        logger.error(f"Error in process_single_prediction: {e}")
        raise self.retry(exc=e, countdown=60)

@celery.task(base=PredictionTask, queue='predictions')
def update_prediction_outcomes():
    """Update prediction outcomes based on match results"""
    pending_predictions = Prediction.query.filter_by(status='Pending').all()
    
    updated = 0
    for prediction in pending_predictions:
        # Check if match has ended (simplified logic)
        # In real app, you'd check actual match results
        match_result = None  # Get from match API
        
        if match_result:
            # Determine if prediction was correct
            is_correct = (prediction.pred_outcome == match_result['outcome'])
            
            prediction.status = 'Won' if is_correct else 'Lost'
            prediction.actual_outcome = match_result['outcome']
            prediction.actual_score = match_result.get('score')
            prediction.settled_at = datetime.utcnow()
            
            if is_correct:
                prediction.profit_loss = (prediction.stake or 10) * (prediction.odds or 2) - (prediction.stake or 10)
            else:
                prediction.profit_loss = -(prediction.stake or 10)
            
            updated += 1
    
    if updated > 0:
        db.session.commit()
    
    return {'predictions_updated': updated}

# ==================== ANALYTICS & REPORTS ====================

@celery.task(bind=True, queue='reports')
def generate_user_report(self, user_id: int, report_type: str = 'monthly'):
    """Generate detailed user report"""
    user = User.query.get(user_id)
    if not user:
        return {'error': 'User not found'}
    
    start_date = None
    if report_type == 'weekly':
        start_date = datetime.utcnow() - timedelta(days=7)
    elif report_type == 'monthly':
        start_date = datetime.utcnow() - timedelta(days=30)
    else:
        start_date = user.created_at
    
    # Query predictions in period
    predictions = Prediction.query.filter(
        Prediction.user_id == user_id,
        Prediction.created_at >= start_date
    ).all()
    
    # Calculate statistics
    total = len(predictions)
    wins = sum(1 for p in predictions if p.status == 'Won')
    losses = sum(1 for p in predictions if p.status == 'Lost')
    pending = sum(1 for p in predictions if p.status == 'Pending')
    accuracy = (wins / (wins + losses)) * 100 if (wins + losses) > 0 else 0
    total_profit = sum(p.profit_loss or 0 for p in predictions)
    
    # Most successful leagues
    league_stats = {}
    for pred in predictions:
        # This would require league data in predictions
        pass
    
    # Render report
    html = render_template('reports/user_report.html',
                          user=user,
                          report_type=report_type,
                          start_date=start_date,
                          end_date=datetime.utcnow(),
                          predictions=predictions,
                          stats={
                              'total': total,
                              'wins': wins,
                              'losses': losses,
                              'pending': pending,
                              'accuracy': accuracy,
                              'total_profit': total_profit
                          })
    
    return {
        'user_id': user_id,
        'report_type': report_type,
        'statistics': {
            'total_predictions': total,
            'wins': wins,
            'losses': losses,
            'accuracy': accuracy,
            'total_profit': total_profit
        },
        'html': html
    }

@celery.task(queue='reports')
def generate_platform_report():
    """Generate platform-wide analytics report"""
    # User statistics
    total_users = User.query.count()
    active_users = User.query.filter(
        User.last_login >= datetime.utcnow() - timedelta(days=7)
    ).count()
    new_users_today = User.query.filter(
        func.date(User.created_at) == datetime.utcnow().date()
    ).count()
    
    # Prediction statistics
    total_predictions = Prediction.query.count()
    predictions_today = Prediction.query.filter(
        func.date(Prediction.created_at) == datetime.utcnow().date()
    ).count()
    
    # Accuracy statistics
    settled_predictions = Prediction.query.filter(
        Prediction.status.in_(['Won', 'Lost'])
    ).all()
    
    wins = sum(1 for p in settled_predictions if p.status == 'Won')
    accuracy = (wins / len(settled_predictions)) * 100 if settled_predictions else 0
    
    # Revenue statistics
    total_revenue = db.session.query(
        func.sum(Payment.amount)
    ).filter(Payment.status == 'COMPLETED').scalar() or 0
    
    return {
        'timestamp': datetime.utcnow().isoformat(),
        'users': {
            'total': total_users,
            'active_last_7_days': active_users,
            'new_today': new_users_today
        },
        'predictions': {
            'total': total_predictions,
            'today': predictions_today,
            'accuracy': accuracy,
            'wins': wins,
            'losses': len(settled_predictions) - wins
        },
        'revenue': {
            'total': float(total_revenue),
            'currency': 'KES'
        }
    }

# ==================== MAINTENANCE TASKS ====================

@celery.task(queue='maintenance')
def update_leaderboard_task():
    """Update leaderboard rankings"""
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
        
        logger.info(f"✅ Leaderboard updated with {len(leaderboard_entries)} entries")
        return {'entries_updated': len(leaderboard_entries)}
        
    except Exception as e:
        logger.error(f"❌ Leaderboard update failed: {e}")
        db.session.rollback()
        raise

@celery.task(queue='maintenance')
def cleanup_old_tasks():
    """Clean up old Celery task results and logs"""
    # This would clean up old task results from Redis
    # Implementation depends on your storage strategy
    
    # Clean old system logs (older than 30 days)
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    old_logs = SystemLog.query.filter(
        SystemLog.created_at < thirty_days_ago
    ).delete()
    
    # Clean old user activities (older than 90 days)
    ninety_days_ago = datetime.utcnow() - timedelta(days=90)
    old_activities = UserActivity.query.filter(
        UserActivity.timestamp < ninety_days_ago
    ).delete()
    
    db.session.commit()
    
    return {
        'old_logs_deleted': old_logs,
        'old_activities_deleted': old_activities
    }

@celery.task(queue='maintenance')
def update_platform_stats():
    """Update platform statistics cache"""
    from .routes import calculate_platform_accuracy, calculate_user_growth
    
    stats = {
        'platform_accuracy': calculate_platform_accuracy(),
        'user_growth': calculate_user_growth(),
        'total_users': User.query.count(),
        'total_predictions': Prediction.query.count(),
        'updated_at': datetime.utcnow().isoformat()
    }
    
    # Cache the stats
    if hasattr(current_app, 'cache'):
        current_app.cache.set('platform_stats', stats, timeout=3600)
    
    return stats

@celery.task(queue='maintenance')
def refresh_ai_models():
    """Refresh and retrain AI models periodically"""
    ai_engine = current_app.ai_engine
    if not ai_engine:
        return {'error': 'AI engine not available'}
    
    try:
        if hasattr(ai_engine, 'refresh_models'):
            result = ai_engine.refresh_models()
            
            # Log the refresh
            report = LearningReport(
                report_type='model_refresh',
                user_id=None,  # System-generated
                period_start=datetime.utcnow(),
                period_end=datetime.utcnow(),
                insights=json.dumps(result) if result else "Model refresh completed",
                recommendations="Check model performance metrics",
                learning_metrics={'refresh_result': result},
                generated=datetime.utcnow()
            )
            db.session.add(report)
            db.session.commit()
            
            return result
        else:
            return {'warning': 'AI engine does not support model refresh'}
    except Exception as e:
        logger.error(f"AI model refresh failed: {e}")
        raise

# ==================== NOTIFICATION TASKS ====================

@celery.task
def send_bulk_notifications(notifications_data: List[Dict]):
    """Send bulk notifications to multiple users"""
    for data in notifications_data:
        send_notification_task.delay(**data)
    
    return {'notifications_scheduled': len(notifications_data)}


@celery.task(bind=True, name='process_unprocessed_learning')
def process_unprocessed_learning(self, limit=50):
    app = current_app._get_current_object()
    
    with app.app_context():
        learner = app.online_learner
        storage = prediction_storage
        
        try:
            # ── Before ───────────────────────────────────────
            before_status = learner.get_system_status()
            before_weights = learner.team_weights.weights.copy()  # shallow copy
            
            unprocessed = storage.get_unprocessed_results(limit=limit)
            if not unprocessed:
                return {'status': 'no_data', 'processed': 0}
            
            processed_count = 0
            for result in unprocessed:
                if learner.process_match_result(result):
                    storage.mark_as_processed(result['match_id'])
                    processed_count += 1
            
            learner.team_weights.save_weights()
            
            # ── After ────────────────────────────────────────
            after_status = learner.get_system_status()
            
            # Simple delta / insights (expand later)
            adjustment_count = after_status['total_adjustments'] - before_status['total_adjustments']
            teams_changed = len(set(before_weights.keys()) ^ set(learner.team_weights.weights.keys()))
            
            now = datetime.utcnow()
            report = LearningReport(
                user_id=None,  # System-generated report, not user-specific
                report_type='task_run',
                period_start=now - timedelta(minutes=5),  # Approximate window when task ran
                period_end=now,
                total_predictions=processed_count,
                correct_predictions=adjustment_count,
                accuracy=(adjustment_count / processed_count * 100) if processed_count > 0 else 0,
                total_profit=0,  # Not calculated in online learning task
                roi=0,  # Not calculated in online learning task
                insights=f"Processed {processed_count} matches with {adjustment_count} weight adjustments",
                recommendations="Review top drifted teams" if teams_changed > 5 else "System stable",
                learning_metrics={
                    'before': before_status,
                    'after': after_status,
                    'adjustments_made': adjustment_count,
                    'teams_affected': teams_changed
                },
                prediction_performance={},
                key_insights=[
                    f"Adjusted {adjustment_count} team weights",
                    f"{teams_changed} teams had weight changes",
                    "Decay applied successfully" if processed_count > 0 else "No new data"
                ],
                file_path=None,
                generated=now
            )
            
            db.session.add(report)
            db.session.commit()
            
            return {
                'status': 'success',
                'processed': processed_count,
                'report_id': report.id,
                'message': f'Processed {processed_count} matches – report #{report.id} generated'
            }
        
        except Exception as exc:
            db.session.rollback()
            raise self.retry(exc=exc, countdown=60, max_retries=3)

@celery.task(name='periodic_learning_refresh')
def periodic_learning_refresh():
    """Scheduled task: full refresh / cleanup"""
    with current_app.app_context():
        learner = current_app.online_learner
        # Example: decay all weights slightly or clean old data
        # (extend OnlineLearningSystem with a .periodic_maintenance() method if needed)
        
        status_before = learner.get_system_status()
        # ... custom logic ...
        learner.team_weights.save_weights()
        
        return {
            'status': 'refreshed',
            'before': status_before,
            'after': learner.get_system_status()
        }

@celery.task
def send_notification_task(user_id: int, title: str, message: str, 
                          notification_type: str = 'info', send_email: bool = False):
    """Send notification to user"""
    try:
        # Save to database
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
        
        # Emit socket event
        if hasattr(current_app, 'socketio'):
            current_app.socketio.emit('new_notification', {
                'title': title,
                'message': message,
                'type': notification_type
            }, room=f'user_{user_id}')
        
        # Send email if requested
        if send_email:
            user = User.query.get(user_id)
            if user and user.email_notifications:
                send_email_task.delay(
                    to=[user.email],
                    subject=title,
                    body=message
                )
        
        return {'notification_id': notification.id, 'status': 'success'}
        
    except Exception as e:
        logger.error(f"Notification task failed: {e}")
        raise

# ==================== UTILITY FUNCTIONS ====================

# Add near other Celery-related functions

def celery_update_prediction_outcomes(batch_size=100):
    """Update prediction outcomes using Celery if available"""
    if CELERY_AVAILABLE:
        update_prediction_outcomes.delay(batch_size=batch_size)
        logger.info(f"Prediction outcome update queued via Celery")
    else:
        # Fallback to synchronous update
        result = update_prediction_outcomes_sync(batch_size=batch_size)
        logger.info(f"Prediction outcomes updated synchronously: {result}")

def get_task_status(task_id: str) -> Dict:
    """Get status of a Celery task"""
    if not celery:
        return {'error': 'Celery not initialized'}
    
    task = celery.AsyncResult(task_id)
    
    response = {
        'task_id': task_id,
        'status': task.status,
        'result': task.result if task.ready() else None
    }
    
    if task.status == 'FAILURE':
        response['error'] = str(task.result)
        response['traceback'] = task.traceback
    
    elif task.status == 'PROGRESS':
        response['progress'] = task.info.get('current', 0)
        response['total'] = task.info.get('total', 0)
        response['percent'] = (task.info.get('current', 0) / task.info.get('total', 1)) * 100
    
    return response

def cancel_task(task_id: str) -> Dict:
    """Cancel a running Celery task"""
    if not celery:
        return {'error': 'Celery not initialized'}
    
    task = celery.AsyncResult(task_id)
    
    if task.state in ('PENDING', 'STARTED', 'RETRY'):
        task.revoke(terminate=True)
        return {'task_id': task_id, 'status': 'cancelled'}
    else:
        return {'task_id': task_id, 'status': 'cannot_cancel', 'current_state': task.state}