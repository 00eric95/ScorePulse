from sklearn.model_selection import TimeSeriesSplit, RandomizedSearchCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier, RandomForestRegressor, GradientBoostingRegressor
import numpy as np
import sys
import os

# Allow importing config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class HyperparameterTuner:
    def __init__(self):
        self.config = Config()
        # TimeSeriesSplit prevents "future data leakage"
        # We perform 3 splits (train on past, test on near future)
        self.cv = TimeSeriesSplit(n_splits=3)

    def tune(self, model_type, mode, X, y, n_iter=10):
        """
        Finds the best parameters for a given model type.
        :param model_type: 'rf' (Random Forest) or 'gb' (Gradient Boosting)
        :param mode: 'classification' (Win/Loss) or 'regression' (Goals)
        """
        print(f"🔧 Tuning {model_type.upper()} ({mode}) with {n_iter} iterations...")
        
        # 1. Select the Base Algorithm & Param Grid
        if model_type == 'rf':
            model, param_grid = self._get_rf_config(mode)
        elif model_type == 'gb':
            model, param_grid = self._get_gb_config(mode)
        else:
            print("⚠️ Neural Networks require manual tuning. Skipping.")
            return {}

        # 2. Run Randomized Search (Faster than Grid Search)
        search = RandomizedSearchCV(
            estimator=model,
            param_distributions=param_grid,
            n_iter=n_iter,
            cv=self.cv,
            scoring='accuracy' if mode == 'classification' else 'neg_mean_squared_error',
            n_jobs=-1, # Use all CPU cores
            random_state=42,
            verbose=1
        )
        
        search.fit(X, y)
        
        print(f"✅ Best Params found: {search.best_params_}")
        return search.best_params_

    def _get_rf_config(self, mode):
        """Returns Random Forest model and search grid."""
        if mode == 'classification':
            model = RandomForestClassifier(random_state=42)
        else:
            model = RandomForestRegressor(random_state=42)
            
        grid = {
            'n_estimators': [100, 200, 300, 500],
            'max_depth': [None, 10, 20, 30],
            'min_samples_split': [2, 5, 10],
            'min_samples_leaf': [1, 2, 4]
        }
        return model, grid

    def _get_gb_config(self, mode):
        """Returns Gradient Boosting model and search grid."""
        if mode == 'classification':
            model = GradientBoostingClassifier(random_state=42)
        else:
            model = GradientBoostingRegressor(random_state=42)
            
        grid = {
            'n_estimators': [100, 200, 300],
            'learning_rate': [0.01, 0.05, 0.1, 0.2],
            'max_depth': [3, 5, 7],
            'subsample': [0.8, 0.9, 1.0]
        }
        return model, grid