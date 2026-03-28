"""
The 'Optimization Architect' that uses Randomized Search to find the most effective hyperparameter settings for models.
It implements 'TimeSeriesSplit' cross-validation to prevent data leakage and ensure models generalize to future matches.
The tuner supports multiple model types, including XGBoost, Random Forest, and LightGBM, with customizable search grids.
Best parameters are automatically persisted to 'best_params.json' for immediate use by the Model Factory.
This script automates the tedious process of fine-tuning, ensuring the AI always operates at its peak mathematical capacity.
"""

import pandas as pd
import numpy as np
import os
import sys
import json
from sklearn.model_selection import RandomizedSearchCV, TimeSeriesSplit
from xgboost import XGBClassifier, XGBRegressor
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor

# Optional Imports
try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config
from utils.feature_engineering import FeatureEngineer

class HyperparameterTuner:
    def __init__(self):
        self.config = Config()
        self.engineer = FeatureEngineer()
        self.best_params_path = self.config.BEST_PARAMS_PATH
        self.config.ensure_dirs()

    def get_param_grid(self, model_type):
        if model_type == 'xgb':
            return {
                'n_estimators': [100, 200, 300, 500],
                'max_depth': [3, 5, 7],
                'learning_rate': [0.01, 0.05, 0.1],
                'subsample': [0.7, 0.8, 1.0],
                'colsample_bytree': [0.7, 0.8, 1.0],
                'gamma': [0, 0.1, 0.5]
            }
        elif model_type == 'lgbm':
            return {
                'n_estimators': [100, 200, 500],
                'num_leaves': [20, 31, 50, 100],
                'learning_rate': [0.01, 0.05, 0.1],
                'feature_fraction': [0.7, 0.8, 1.0]
            }
        elif model_type == 'rf':
            return {
                'n_estimators': [100, 200],
                'max_depth': [10, 20, None],
                'min_samples_leaf': [1, 2, 4]
            }
        return {}

    def tune(self, model_type, target_name, n_iter=10):
        print(f"\n🔍 TUNING: {model_type.upper()} for Target: {target_name}")
        
        train_path = self.config.PROCESSED_DATA_DIR / "train.csv"
        if not train_path.exists():
            print("❌ Train data missing.")
            return

        df = pd.read_csv(train_path, low_memory=False)
        mode = 'regression' if target_name == 'TotalGoals' else 'classification'
        
        try:
            X, y = self.engineer.fit_transform(df, target_name=target_name)
        except Exception as e:
            print(f"⚠️ Skipping {target_name}: {e}")
            return
        
        # Setup Model
        if model_type == 'xgb':
            base_model = XGBRegressor(n_jobs=-1, random_state=42) if mode == 'regression' else XGBClassifier(n_jobs=-1, random_state=42)
        elif model_type == 'lgbm':
            if not LGBM_AVAILABLE: return
            base_model = LGBMRegressor(n_jobs=-1, random_state=42) if mode == 'regression' else LGBMClassifier(n_jobs=-1, random_state=42)
        elif model_type == 'rf':
            base_model = RandomForestRegressor(n_jobs=-1, random_state=42) if mode == 'regression' else RandomForestClassifier(n_jobs=-1, random_state=42)
        else:
            return

        # Search
        search = RandomizedSearchCV(
            estimator=base_model,
            param_distributions=self.get_param_grid(model_type),
            n_iter=n_iter,
            scoring='neg_mean_absolute_error' if mode == 'regression' else 'accuracy',
            cv=TimeSeriesSplit(n_splits=3),
            verbose=1,
            n_jobs=-1,
            random_state=42
        )
        
        try:
            search.fit(X, y)
            print(f"✅ Best Score: {search.best_score_:.4f}")
            self._save_best_params(model_type, target_name, search.best_params_)
        except Exception as e:
            print(f"❌ Tuning Failed: {e}")

    def _save_best_params(self, model_type, target_name, params):
        data = {}
        if self.best_params_path.exists():
            try:
                with open(self.best_params_path, 'r') as f:
                    data = json.load(f)
            except: pass
        
        key = f"{model_type}_{target_name}"
        data[key] = params
        
        with open(self.best_params_path, 'w') as f:
            json.dump(data, f, indent=4)
        print(f"💾 Saved params for {key}")

if __name__ == "__main__":
    tuner = HyperparameterTuner()
    # Tune XGB and LGBM for main markets
    for m in ['xgb', 'lgbm']:
        for t in ['WLD', 'BTTS', 'TotalGoals']:
            tuner.tune(m, t, n_iter=15)