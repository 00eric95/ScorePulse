import pandas as pd
import numpy as np
from sklearn.preprocessing import StandardScaler
import joblib
import sys
import os

# Link to Config
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class FeatureEngineer:  # <--- Class Name must match this exactly!
    def __init__(self):
        self.config = Config()
        self.scaler = StandardScaler()
        # We load the list of numeric features from config to ensure consistency
        self.features = self.config.FEATURES_NUMERIC

    def fit_transform(self, df, target_name="WLD"):
        """
        1. Selects the numeric features.
        2. Fits the Scaler (learns mean/std) on the TRAINING set.
        3. Returns Scaled X and the specific Target y.
        """
        # Data Validation
        missing_cols = [c for c in self.features if c not in df.columns]
        if missing_cols:
            raise ValueError(f"❌ Missing features in dataframe: {missing_cols}")

        X = df[self.features].copy()
        
        # Get the correct target column based on the name (WLD, Over25, etc.)
        target_col = self.config.TARGETS.get(target_name)
        if target_col not in df.columns:
            raise ValueError(f"❌ Target column '{target_col}' not found for '{target_name}'")
            
        y = df[target_col].values

        # Scaling (Standardization: Mean=0, Std=1)
        # We only fit on the training data to prevent data leakage
        print(f"   ⚙️ Scaling {len(self.features)} features for {target_name}...")
        X_scaled = self.scaler.fit_transform(X)
        
        # Save the scaler so we can use it later for predictions
        self._save_scaler()

        return pd.DataFrame(X_scaled, columns=self.features), y

    def transform(self, df, target_name=None):
        """
        Used for VALIDATION, TEST, and LIVE predictions.
        Uses the ALREADY FITTED scaler.
        """
        # Check if scaler is fitted
        if not hasattr(self.scaler, 'mean_'):
            self._load_scaler()

        X = df[self.features].copy()
        X_scaled = self.scaler.transform(X)
        
        X_final = pd.DataFrame(X_scaled, columns=self.features)

        # If we are training/validating, return y. If predicting live, just return X.
        if target_name:
            target_col = self.config.TARGETS.get(target_name)
            y = df[target_col].values
            return X_final, y
        
        return X_final

    def _save_scaler(self):
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.config.SCALER_PATH), exist_ok=True)
        joblib.dump(self.scaler, self.config.SCALER_PATH)

    def _load_scaler(self):
        if self.config.SCALER_PATH.exists():
            self.scaler = joblib.load(self.config.SCALER_PATH)
        else:
            raise FileNotFoundError("⚠️ Scaler not found. You must run fit_transform (Training) first.")