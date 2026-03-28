"""
Manages a dedicated SQLite database for archiving AI predictions and corresponding actual match results.
The module provides a persistent record for calculating long-term accuracy and ROI metrics.
It includes complex SQL queries to extract performance statistics over specific time windows (e.g., last 30 days).
The storage interface handles the serialization of complex JSON prediction data into relational tables.
This serves as the ground-truth repository for the AlertSystem and PerformanceAnalyzer modules.
"""


import sqlite3
import json
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class PredictionStorage:
    """Store predictions for later comparison with actual results"""
    
    def __init__(self, db_path="data/predictions.db"):
        self.db_path = Path(db_path)
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database"""
        try:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Create predictions table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS predictions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT UNIQUE,
                    home_team TEXT,
                    away_team TEXT,
                    match_date TEXT,
                    predicted_data TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create results table
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    match_id TEXT UNIQUE,
                    home_team TEXT,
                    away_team TEXT,
                    match_date TEXT,
                    actual_home_goals INTEGER,
                    actual_away_goals INTEGER,
                    actual_result TEXT,
                    processed_for_learning BOOLEAN DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create index for faster queries
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_match_date ON predictions(match_date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_processed ON results(processed_for_learning)')
            
            conn.commit()
            conn.close()
            
            logger.info(f"Database initialized at {self.db_path}")
            
        except Exception as e:
            logger.error(f"Error initializing database: {e}")
    
    def store_prediction(self, match_id, home_team, away_team, match_date, predicted_data):
        """Store a prediction for future comparison"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            predicted_json = json.dumps(predicted_data)
            
            cursor.execute('''
                INSERT OR REPLACE INTO predictions 
                (match_id, home_team, away_team, match_date, predicted_data, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (match_id, home_team, away_team, match_date, predicted_json, datetime.now().isoformat()))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored prediction for {home_team} vs {away_team}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing prediction: {e}")
            return False
    
    def store_result(self, match_id, home_team, away_team, match_date, 
                     home_goals, away_goals, result):
        """Store actual match result"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT OR REPLACE INTO results 
                (match_id, home_team, away_team, match_date, 
                 actual_home_goals, actual_away_goals, actual_result)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (match_id, home_team, away_team, match_date, 
                  home_goals, away_goals, result))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Stored result for {home_team} {home_goals}-{away_goals} {away_team}")
            return True
            
        except Exception as e:
            logger.error(f"Error storing result: {e}")
            return False
    
    def get_unprocessed_results(self, limit=50):
        """Get results that haven't been processed for online learning"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT r.*, p.predicted_data
                FROM results r
                LEFT JOIN predictions p ON r.match_id = p.match_id
                WHERE r.processed_for_learning = 0
                ORDER BY r.match_date
                LIMIT ?
            ''', (limit,))
            
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                result = dict(row)
                if result['predicted_data']:
                    result['predicted_data'] = json.loads(result['predicted_data'])
                results.append(result)
            
            conn.close()
            return results
            
        except Exception as e:
            logger.error(f"Error getting unprocessed results: {e}")
            return []
    
    def mark_as_processed(self, match_id):
        """Mark a result as processed for online learning"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE results 
                SET processed_for_learning = 1 
                WHERE match_id = ?
            ''', (match_id,))
            
            conn.commit()
            conn.close()
            return True
            
        except Exception as e:
            logger.error(f"Error marking as processed: {e}")
            return False
    
    def get_prediction_stats(self, days=30):
        """Get statistics about predictions"""
        try:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            cutoff_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            
            # Get total predictions
            cursor.execute('''
                SELECT COUNT(*) as total FROM predictions
                WHERE date(created_at) >= date(?, '-? days')
            ''', (cutoff_date.isoformat(), days))
            
            total = cursor.fetchone()[0]
            
            # Get accuracy
            cursor.execute('''
                SELECT 
                    COUNT(*) as total_matches,
                    SUM(CASE WHEN 
                        (r.actual_result = 'H' AND json_extract(p.predicted_data, '$.win_prob.home') >= 
                         GREATEST(json_extract(p.predicted_data, '$.win_prob.draw'), 
                                 json_extract(p.predicted_data, '$.win_prob.away')))
                        OR
                        (r.actual_result = 'D' AND json_extract(p.predicted_data, '$.win_prob.draw') >= 
                         GREATEST(json_extract(p.predicted_data, '$.win_prob.home'), 
                                 json_extract(p.predicted_data, '$.win_prob.away')))
                        OR
                        (r.actual_result = 'A' AND json_extract(p.predicted_data, '$.win_prob.away') >= 
                         GREATEST(json_extract(p.predicted_data, '$.win_prob.home'), 
                                 json_extract(p.predicted_data, '$.win_prob.draw')))
                    THEN 1 ELSE 0 END) as correct_predictions
                FROM results r
                JOIN predictions p ON r.match_id = p.match_id
                WHERE date(r.match_date) >= date(?, '-? days')
            ''', (cutoff_date.isoformat(), days))
            
            row = cursor.fetchone()
            conn.close()
            
            if row and row[0] > 0:
                accuracy = row[1] / row[0]
                return {
                    'total_predictions': total,
                    'total_matches_with_results': row[0],
                    'correct_predictions': row[1],
                    'accuracy': round(accuracy, 3)
                }
            
            return None
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return None


# Singleton instance
prediction_storage = PredictionStorage()