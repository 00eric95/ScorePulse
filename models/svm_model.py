from sklearn.linear_model import SGDClassifier, SGDRegressor
from sklearn.calibration import CalibratedClassifierCV
import joblib
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class SVMModel:
    def __init__(self, mode='classification', **kwargs):
        self.config = Config()
        self.mode = mode
        
        kwargs.pop('mode', None)
        
        # Defaults
        if 'alpha' not in kwargs: kwargs['alpha'] = 0.0001
        
        kwargs['max_iter'] = kwargs.get('max_iter', 1000)
        kwargs['tol'] = kwargs.get('tol', 1e-3)
        kwargs['random_state'] = 42
        
        # SGDClassifier/Regressor parameters
        # We need to filter kwargs because CalibratedClassifierCV doesn't take the same args as SGD
        sgd_params = {k:v for k,v in kwargs.items() if k in ['alpha', 'penalty', 'max_iter', 'tol', 'random_state', 'n_jobs']}
        sgd_params['n_jobs'] = 1 # Fix for windows
        
        if self.mode == 'classification':
            base_model = SGDClassifier(loss='hinge', **sgd_params)
            # Wrap for probabilities
            self.model = CalibratedClassifierCV(base_model, method='sigmoid')
        else:
            self.model = SGDRegressor(**sgd_params)

    def train(self, X, y):
        print(f"   📐 Training SVM (Linear SGD) ({self.mode})...")
        self.model.fit(X, y)

    def predict(self, X):
        return self.model.predict(X)
        
    def predict_proba(self, X):
        if self.mode == 'classification':
            return self.model.predict_proba(X)
        raise NotImplementedError("Regression does not support probabilities.")

    def save(self, filename="svm_model.pkl"):
        path = self.config.MODELS_DIR / filename
        joblib.dump(self.model, path)
        print(f"   💾 Model saved to {path}")
        
    def load(self, filename):
        path = self.config.MODELS_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Model not found at {path}")
        self.model = joblib.load(path)