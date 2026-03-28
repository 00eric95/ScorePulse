"""
This module implements a standard Scikit-Learn Gradient Boosting wrapper.
It supports both classification and regression tasks via a 'mode' switch.
The class initializes with robust default hyperparameters for tree depth and learning rate.
Methods are provided for training, prediction, and probabilistic output for matches.
It utilizes joblib for persistence, saving trained weights to the project's models directory.
"""

from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
import joblib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class GradientBoostingModel:
    def __init__(self, mode='classification', **kwargs):
        self.config = Config()
        self.mode = mode
        
        kwargs.pop('mode', None)
        
        # Defaults
        if 'n_estimators' not in kwargs: kwargs['n_estimators'] = 100
        if 'learning_rate' not in kwargs: kwargs['learning_rate'] = 0.1
        if 'max_depth' not in kwargs: kwargs['max_depth'] = 3
        
        kwargs['random_state'] = 42
        
        if self.mode == 'classification':
            self.model = GradientBoostingClassifier(**kwargs)
        else:
            self.model = GradientBoostingRegressor(**kwargs)

    def train(self, X, y):
        print(f"   🚀 Training Gradient Boosting ({self.mode})...")
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

    def predict_proba(self, X):
        if self.mode == 'classification':
            return self.model.predict_proba(X)
        raise NotImplementedError("Regression does not support probabilities.")

    def save(self, filename="gb_model.pkl"):
        path = self.config.MODELS_DIR / filename
        joblib.dump(self.model, path)
        print(f"   💾 Model saved to {path}")
        
    def load(self, filename):
        path = self.config.MODELS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Model not found at {path}")
        self.model = joblib.load(path)