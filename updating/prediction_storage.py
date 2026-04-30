"""
Manages a dedicated SQLite database for archiving AI predictions and corresponding actual match results.
The module provides a persistent record for calculating long-term accuracy and ROI metrics.
It includes complex SQL queries to extract performance statistics over specific time windows (e.g., last 30 days).
The storage interface handles the serialization of complex JSON prediction data into relational tables.
This serves as the ground-truth repository for the AlertSystem and PerformanceAnalyzer modules.

MODIFIED: Now uses the main ScorePulse database (SQLAlchemy) instead of a separate SQLite file.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List

from sqlalchemy import func, and_
from sqlalchemy.exc import SQLAlchemyError

# Import from your Flask application
from app import db
from app.models import Prediction

logger = logging.getLogger(__name__)


class PredictionStorage:
    """Store predictions for later comparison with actual results using the main database"""

    def __init__(self, db_path: str = None):
        """
        db_path is ignored – kept for backward compatibility.
        All data is stored in the main SQLAlchemy database.
        """
        self.db_path = None
        # No separate initialization needed; the main db is already set up.
        logger.info("PredictionStorage using main ScorePulse database")

    def _ensure_prediction_record(self, match_id: str) -> Optional[Prediction]:
        """Get or create a Prediction record for the given match_id."""
        try:
            pred = Prediction.query.filter_by(match_id=match_id).first()
            if pred is None:
                pred = Prediction(match_id=match_id)
                db.session.add(pred)
                db.session.commit()
            return pred
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error ensuring prediction record for {match_id}: {e}")
            return None

    def store_prediction(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        match_date: str,
        predicted_data: Dict[str, Any]
    ) -> bool:
        """
        Store a prediction for future comparison.
        Updates the existing prediction record or creates a new one.
        """
        try:
            # Convert match_date to datetime if it's a string
            if isinstance(match_date, str):
                try:
                    match_date = datetime.fromisoformat(match_date)
                except ValueError:
                    # Keep as string – model may handle it
                    pass

            pred = self._ensure_prediction_record(match_id)
            if not pred:
                return False

            pred.home_team = home_team
            pred.away_team = away_team
            pred.match_date = match_date

            # Extract and store key prediction values
            # predicted_data typically contains win_prob, scores, etc.
            if 'win_prob' in predicted_data:
                pred.mcmc_home_prob = predicted_data['win_prob'].get('home')
                pred.mcmc_away_prob = predicted_data['win_prob'].get('away')
                pred.mcmc_draw_prob = predicted_data['win_prob'].get('draw')
            if 'predicted_score' in predicted_data:
                pred.pred_home_score = predicted_data['predicted_score'].get('home')
                pred.pred_away_score = predicted_data['predicted_score'].get('away')
            if 'confidence' in predicted_data:
                pred.confidence = predicted_data['confidence']
            if 'ai_prediction' in predicted_data:
                pred.ai_prediction = predicted_data['ai_prediction']
            if 'total_goals_pred' in predicted_data:
                pred.total_goals_pred = predicted_data['total_goals_pred']
            if 'btts_probability' in predicted_data:
                pred.btts_probability = predicted_data['btts_probability']
            if 'over25_probability' in predicted_data:
                pred.over25_probability = predicted_data['over25_probability']

            # Store the full JSON for compatibility
            pred.narrative_report = json.dumps(predicted_data)

            pred.updated_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Stored prediction for {home_team} vs {away_team} (match_id={match_id})")
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error storing prediction: {e}")
            return False

    def store_result(
        self,
        match_id: str,
        home_team: str,
        away_team: str,
        match_date: str,
        home_goals: int,
        away_goals: int,
        result: str
    ) -> bool:
        """
        Store actual match result and update the prediction record.
        result expected: 'H', 'D', or 'A' (home win, draw, away win).
        """
        try:
            # Convert match_date if string
            if isinstance(match_date, str):
                try:
                    match_date = datetime.fromisoformat(match_date)
                except ValueError:
                    pass

            pred = self._ensure_prediction_record(match_id)
            if not pred:
                # Create a minimal record even if no prediction existed
                pred = Prediction(match_id=match_id, home_team=home_team, away_team=away_team, match_date=match_date)
                db.session.add(pred)

            pred.actual_score = f"{home_goals}-{away_goals}"
            pred.status = 'completed'
            # Optionally set pred_outcome based on result
            pred.pred_outcome = result  # Storing actual outcome in pred_outcome? Could rename but keep existing fields.
            # Alternatively, use a different field. We'll use 'pred_outcome' to store the actual result for evaluation.

            # Also store the result in a structured way if needed
            pred.notes = json.dumps({
                'actual_home_goals': home_goals,
                'actual_away_goals': away_goals,
                'actual_result': result
            })

            pred.updated_at = datetime.utcnow()
            db.session.commit()

            logger.info(f"Stored result for {home_team} {home_goals}-{away_goals} {away_team}")
            return True

        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error storing result: {e}")
            return False

    def get_unprocessed_results(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Get results that haven't been processed for online learning.
        Uses the 'is_evaluated' flag from the predictions table.
        """
        try:
            # Find predictions that have an actual_score and are not yet evaluated
            records = Prediction.query.filter(
                Prediction.actual_score.isnot(None),
                Prediction.is_evaluated == False   # noqa: E712
            ).limit(limit).all()

            results = []
            for pred in records:
                # Parse actual score
                score_parts = pred.actual_score.split('-') if pred.actual_score else []
                home_goals = int(score_parts[0]) if len(score_parts) > 0 else None
                away_goals = int(score_parts[1]) if len(score_parts) > 1 else None

                # Parse predicted data from narrative_report
                predicted_data = {}
                if pred.narrative_report:
                    try:
                        predicted_data = json.loads(pred.narrative_report)
                    except json.JSONDecodeError:
                        pass

                results.append({
                    'match_id': pred.match_id,
                    'home_team': pred.home_team,
                    'away_team': pred.away_team,
                    'match_date': pred.match_date.isoformat() if pred.match_date else None,
                    'actual_home_goals': home_goals,
                    'actual_away_goals': away_goals,
                    'actual_result': pred.pred_outcome,  # stored as H/D/A
                    'predicted_data': predicted_data,
                    'processed_for_learning': pred.is_evaluated
                })

            return results

        except SQLAlchemyError as e:
            logger.error(f"Error getting unprocessed results: {e}")
            return []

    def mark_as_processed(self, match_id: str) -> bool:
        """
        Mark a result as processed for online learning by setting is_evaluated = True.
        """
        try:
            pred = Prediction.query.filter_by(match_id=match_id).first()
            if pred:
                pred.is_evaluated = True
                pred.updated_at = datetime.utcnow()
                db.session.commit()
                return True
            else:
                logger.warning(f"Cannot mark as processed: match_id {match_id} not found")
                return False
        except SQLAlchemyError as e:
            db.session.rollback()
            logger.error(f"Error marking as processed: {e}")
            return False

    def get_prediction_stats(self, days: int = 30) -> Optional[Dict[str, Any]]:
        """
        Get statistics about predictions (accuracy, count) over the last 'days'.
        """
        try:
            cutoff = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff = func.date(cutoff, f'-{days} days')

            # Total predictions in that period
            total_predictions = Prediction.query.filter(
                Prediction.created_at >= cutoff
            ).count()

            # Matches that have results and were predicted
            # We need to count correct predictions where pred_outcome matches actual result.
            # Since we stored result in pred_outcome, we can compare with something?
            # Actually, we need to know the predicted outcome. Let's assume there's a field 'pred_outcome' for prediction,
            # but we overwrote it with actual result. We'll instead compare the highest probability from stored JSON.

            # For simplicity, we'll compute accuracy using the results table logic:
            # We'll fetch predictions with actual_score and evaluate if the predicted outcome (from JSON) matches result.
            records = Prediction.query.filter(
                Prediction.actual_score.isnot(None),
                Prediction.created_at >= cutoff
            ).all()

            total_with_results = len(records)
            correct = 0
            for pred in records:
                # Get predicted outcome from stored JSON
                if pred.narrative_report:
                    try:
                        data = json.loads(pred.narrative_report)
                        # Assume predicted winner is the outcome with highest win_prob
                        win_prob = data.get('win_prob', {})
                        if win_prob:
                            predicted_outcome = max(win_prob, key=win_prob.get)
                            if predicted_outcome == pred.pred_outcome:  # pred_outcome holds actual result
                                correct += 1
                    except:
                        pass

            if total_with_results > 0:
                accuracy = correct / total_with_results
                return {
                    'total_predictions': total_predictions,
                    'total_matches_with_results': total_with_results,
                    'correct_predictions': correct,
                    'accuracy': round(accuracy, 3)
                }
            else:
                return None

        except SQLAlchemyError as e:
            logger.error(f"Error getting stats: {e}")
            return None


# Singleton instance (now using the main database)
prediction_storage = PredictionStorage()