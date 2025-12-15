from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor
import joblib
import sys
import os

# Link to Config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class RandomForestModel:
    def __init__(self, mode='classification', **kwargs):
        self.config = Config()
        self.mode = mode
        
        # 1. CLEANUP ARGS
        # Remove 'mode' if it's in kwargs to avoid duplicate argument error
        kwargs.pop('mode', None)
        
        # 2. SET DEFAULTS (Only if not provided by Tuner)
        if 'n_estimators' not in kwargs: kwargs['n_estimators'] = 200
        if 'max_depth' not in kwargs: kwargs['max_depth'] = 10
        
        # 3. FORCE CRITICAL SETTINGS
        # n_jobs=1 prevents Windows freeze
        kwargs['n_jobs'] = 1 
        kwargs['random_state'] = 42
        
        # 4. INITIALIZE MODEL
        # We pass **kwargs directly to sklearn. 
        # Since sklearn supports 'min_samples_split', this will now work.
        if self.mode == 'classification':
            self.model = RandomForestClassifier(**kwargs)
        else:
            self.model = RandomForestRegressor(**kwargs)

    def train(self, X, y):
        print(f"   🌲 Training Random Forest ({self.mode})...")
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)
        
    def predict_proba(self, X):
        if self.mode == 'classification':
            return self.model.predict_proba(X)
        raise NotImplementedError("Regression does not support probabilities.")

    def save(self, filename="rf_model.pkl"):
        # Create directory if missing
        os.makedirs(self.config.MODELS_DIR, exist_ok=True)
        path = self.config.MODELS_DIR / filename
        joblib.dump(self.model, path)
        print(f"   💾 Model saved to {path}")
        
    def load(self, filename):
        path = self.config.MODELS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Model not found at {path}")
        self.model = joblib.load(path)