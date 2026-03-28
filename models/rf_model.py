"""
This module provides a robust wrapper for Scikit-Learn's Random Forest implementation.
It includes a 'Manual Parameter Zone' for pasting tuned hyperparameters directly into the code.
The class supports both classification for match results and regression for total goals prediction.
It utilizes joblib for model serialization and includes built-in support for multi-core processing.
The interface provides standard methods for training, predicting, and returning class probabilities.
"""

import joblib
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

class RFModel:
    def __init__(self, mode='classification', target_name='WLD', **kwargs):
        self.mode = mode
        
        # =========================================================
        # 🛠️ MANUAL PARAMETER ZONE
        # Paste your "Best Hyperparameters" from the Tuner here.
        # =========================================================
        if mode == 'classification':
            # Best Params for WLD / BTTS / Over25
            self.params = {
                'n_estimators': 500,        # <-- Replace with tuner result (e.g., 300)
                'max_depth': None,          # <-- Replace with tuner result (e.g., 20)
                'min_samples_split': 2,     # <-- Replace with tuner result (e.g., 5)
                'min_samples_leaf': 1,      # <-- Replace with tuner result (e.g., 2)
                'max_features': 'sqrt',     # <-- Replace with tuner result
                'n_jobs': -1,
                'random_state': 42
            }
        else:
            # Best Params for TotalGoals (Regression)
            self.params = {
                'n_estimators': 500,        # <-- Replace with tuner result
                'max_depth': None,          # <-- Replace with tuner result
                'min_samples_split': 2,     # <-- Replace with tuner result
                'min_samples_leaf': 1,      # <-- Replace with tuner result
                'max_features': 'sqrt',     # <-- Replace with tuner result
                'n_jobs': -1,
                'random_state': 42
            }
        
        # Allow overriding specific params if passed via kwargs
        for key, value in kwargs.items():
            if key in self.params:
                self.params[key] = value

        # Initialize the Model
        if mode == 'classification':
            self.model = RandomForestClassifier(**self.params)
        else:
            self.model = RandomForestRegressor(**self.params)

    def train(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

    def predict_proba(self, X):
        return self.model.predict_proba(X) if self.mode == 'classification' else None

    def save(self, filepath):
        joblib.dump(self.model, filepath)
        print(f"   💾 Random Forest Model saved to {filepath}")

    def load(self, filepath):
        self.model = joblib.load(filepath)