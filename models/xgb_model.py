"""
Implements a sophisticated XGBoost wrapper with hardcoded 'Golden Parameters' for soccer targets.
It automatically handles binary classification for BTTS and multi-class logic for WLD outcomes.
The module integrates with the project's Config system to manage model paths and data directories.
It features dynamic objective function assignment based on the detected number of unique classes.
Methods include automated training, persistence using joblib, and probability extraction for odds analysis.
"""

import pandas as pd
import numpy as np
import json
import joblib
import os

from xgboost import XGBClassifier, XGBRegressor
from pathlib import Path
from config.config import Config

class XGBModel:
    # --- 1. HARDCODED "GOLDEN" PARAMETERS ---
    # These are your tuned settings. The model uses these by default.
    FALLBACK_PARAMS = {
        "WLD": {
            "subsample": 0.8,
            "n_estimators": 200,
            "max_depth": 3,
            "learning_rate": 0.05,
            "gamma": 0.1,
            "colsample_bytree": 0.8
        },
        "TotalGoals": {
            "subsample": 0.8,
            "n_estimators": 200,
            "max_depth": 3,
            "learning_rate": 0.05,
            "gamma": 0.1,
            "colsample_bytree": 0.8
        },
        "BTTS": {
            "subsample": 1.0,
            "n_estimators": 100,
            "max_depth": 3,
            "learning_rate": 0.05,
            "gamma": 0,
            "colsample_bytree": 1.0
        }
    }

    def __init__(self, mode='classification', target_name='WLD', **kwargs):
        self.config = Config()
        self.mode = mode
        self.target_name = target_name
        
        # 1. Start with the Hardcoded "Golden" Params
        # We use .copy() to avoid modifying the original dictionary
        self.params = self.FALLBACK_PARAMS.get(target_name, {}).copy()
        
        # 2. Try loading NEW params from JSON (if you re-tune later)
        # This allows the Tuner to override the hardcoded values without changing code
        if self.config.BEST_PARAMS_PATH.exists():
            try:
                with open(self.config.BEST_PARAMS_PATH, 'r') as f:
                    all_params = json.load(f)
                    key = f"xgb_{target_name}"
                    if key in all_params:
                        self.params = all_params[key]
                        # print(f"   ⚙️ Loaded dynamic params for {key}")
            except Exception as e:
                pass # Silently fail back to the hardcoded defaults

        # 3. Override with any manual arguments passed explicitly
        self.params.update(kwargs)
        
        self.model = None

    def train(self, X, y):
        # Smart Logic: Detect Binary vs Multi-class automatically
        unique_classes = len(np.unique(y))
        
        # Common args for all modes
        common_args = {
            "n_jobs": -1,
            "random_state": 42,
            **self.params # Unpack the dictionary of parameters here
        }
        
        if self.mode == 'regression':
            self.model = XGBRegressor(objective='reg:squarederror', **common_args)
            
        else: # Classification
            if unique_classes == 2:
                # Binary (Yes/No for BTTS)
                self.model = XGBClassifier(
                    objective='binary:logistic',
                    eval_metric='logloss',
                    **common_args
                )
            else:
                # Multi-class (Win/Draw/Loss for WLD)
                self.model = XGBClassifier(
                    objective='multi:softprob',
                    num_class=unique_classes,
                    eval_metric='mlogloss',
                    **common_args
                )

        # Train
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)

    def predict_proba(self, X):
        # Only for classification
        if self.mode == 'classification':
            return self.model.predict_proba(X)
        return None

    def save(self, filepath):
        joblib.dump(self.model, filepath)

    def load(self, filepath):
        self.model = joblib.load(filepath)