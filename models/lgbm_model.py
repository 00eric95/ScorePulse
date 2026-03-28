"""
Implements a LightGBM model wrapper specifically tuned for soccer analytics targets.
It features a tiered parameter loading system: defaults, target-specific fallbacks, and JSON tuning.
The architecture supports multi-class classification for Win/Loss/Draw outcomes and goal regression.
It includes automatic handling of categorical features and optimized multi-core processing settings.
Parameter overrides can be passed via kwargs to facilitate easy hyperparameter experimentation.
"""

import joblib
import json
import os
from lightgbm import LGBMClassifier, LGBMRegressor
from config.config import Config

class LGBMModel:
    # Default "Safe" Parameters
    FALLBACK_PARAMS = {
        "WLD": {
            'n_estimators': 500, 'learning_rate': 0.05, 'num_leaves': 31,
            'subsample': 0.8, 'colsample_bytree': 0.8
        },
        "TotalGoals": {
            'n_estimators': 500, 'learning_rate': 0.05, 'num_leaves': 31,
            'subsample': 0.8, 'colsample_bytree': 0.8
        }
    }

    def __init__(self, mode='classification', target_name='WLD', **kwargs):
        self.config = Config()
        self.mode = mode
        self.target_name = target_name

        # 1. Start with Defaults
        self.params = self.FALLBACK_PARAMS.get(target_name, self.FALLBACK_PARAMS['WLD']).copy()
        
        # 2. Try loading Tuned Params from JSON
        if self.config.BEST_PARAMS_PATH.exists():
            try:
                with open(self.config.BEST_PARAMS_PATH, 'r') as f:
                    all_params = json.load(f)
                    key = f"lgbm_{target_name}"
                    if key in all_params:
                        self.params.update(all_params[key])
                        # print(f"   ⚙️ Loaded tuned params for {key}")
            except Exception:
                pass 

        # 3. Override with manual kwargs
        self.params.update(kwargs)
        
        # Ensure critical non-tunable params are set
        self.params['n_jobs'] = -1
        self.params['random_state'] = 42
        self.params['verbose'] = -1
        
        # Initialize Model
        if mode == 'classification':
            self.model = LGBMClassifier(**self.params)
        else:
            self.model = LGBMRegressor(**self.params)

    def train(self, X, y):
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

    def predict_proba(self, X):
        return self.model.predict_proba(X) if self.mode == 'classification' else None 

    def save(self, filepath):
        joblib.dump(self.model, filepath)

    def load(self, filepath):
        self.model = joblib.load(filepath)