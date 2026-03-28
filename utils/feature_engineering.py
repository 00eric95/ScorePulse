"""
The primary transformation layer that converts raw match data into high-dimensional input vectors for AI models.
It manages the serialization and loading of 'StandardScalers' to ensure consistent data normalization across training and inference.
The module organizes features into 'Basic,' 'Advanced,' and 'Market' groups for modular experimental tracking.
It handles the logic for calculating target variables like Win/Loss/Draw (WLD) and Over/Under 2.5 goals.
This script ensures that the mathematical 'view' of a football match is identical during both training and real-time prediction.
"""

import pandas as pd
import numpy as np
import joblib
import os
import sys
from sklearn.preprocessing import StandardScaler
from pathlib import Path

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

class FeatureEngineer:
    def __init__(self, use_advanced_features=True):
        self.config = Config()
        self.scaler_path = Path(self.config.SCALER_PATH)
        self.scaler = StandardScaler()
        self.use_advanced_features = use_advanced_features
        
        # Ensure scaler directory exists
        self.scaler_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Define feature groups for better organization
        self._init_feature_groups()

    def _init_feature_groups(self):
        """Initialize feature groups for whitelisting."""
        # Basic Features (always safe)
        self.basic_features = [
            # Rolling Stats
            'Home_Avg', 'Away_Avg', 'Home_Form', 'Away_Form',
            'Home_Streak', 'Away_Streak',
            # Elo & Strength
            'Home_Elo', 'Away_Elo', 'Elo', 'Points',
            'H_Attack', 'A_Attack', 'H_Defense', 'A_Defense'
        ]
        
        # Advanced Features (from FeatureGenerator)
        self.advanced_features = [
            'AttackEff', 'DefenseRes', 'Dominance', 'xG_Diff', 'xG_Proxy',
            'RestDays', 'Momentum', 'RecentPoints', 'AvgGoals', 'AvgConceded',
            'EloDifference', 'EloAdvantage'
        ]
        
        # Market/Odds Features
        self.market_features = [
            'B365H', 'B365D', 'B365A', 'AvgH', 'AvgD', 'AvgA',
            'OddHome', 'OddDraw', 'OddAway', 'ImpliedProb', 'MarketMargin'
        ]
        
        # Forbidden Features (data leakage)
        self.forbidden_features = [
            'HomeTeam', 'AwayTeam', 'FTHG', 'FTAG', 'FTR', 'FTResult',
            'Res', 'TotalGoals', 'Over25', 'BTTS', 
            'FTHome', 'FTAway', 'GoalsFor', 'GoalsAgainst',
            'Result', 'Points', 'Team'  # Team identifiers and results
        ]

    def fit_transform(self, df, target_name='WLD'):
        """
        Prepares features (X) and target (y) for TRAINING.
        Uses STRICT WHITELISTING to prevent data leakage.
        """
        print("🔧 Preparing Features for Training...")
        
        # 1. Get safe features based on whitelist
        selected_features = self._get_safe_features(df)
        
        # 2. Create X (Features)
        X = df[selected_features].copy()
        
        # 3. Safety: Handle Infinity/NaNs
        X = self._clean_features(X)
        
        # 4. Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # 5. Save scaler for later use
        joblib.dump(self.scaler, self.scaler_path)
        print(f"   💾 Scaler saved to: {self.scaler_path}")
        
        # 6. Get target (y)
        y = self._get_target(df, target_name)
        
        # 7. Validate feature consistency
        self._validate_features(X, is_training=True)
        
        return X_scaled, y, selected_features

    def transform(self, df, target_name='WLD'):
        """
        Prepares features (X) for PREDICTION (Validation/Test).
        """
        print("🔧 Preparing Features for Prediction...")
        
        # 1. Get safe features (same logic as fit_transform)
        selected_features = self._get_safe_features(df)
        
        # 2. Create X (Features)
        X = df[selected_features].copy()
        
        # 3. Safety: Handle Infinity/NaNs
        X = self._clean_features(X)
        
        # 4. Load and apply scaler
        X_scaled = self._scale_features(X)
        
        # 5. Get target if available
        y = None
        try:
            y = self._get_target(df, target_name)
        except Exception as e:
            print(f"   ⚠️ Could not extract target: {e}")
        
        # 6. Validate feature consistency with training
        self._validate_features(X_scaled, is_training=False)
        
        # Return as DataFrame with column names preserved
        if hasattr(X_scaled, 'shape') and X_scaled.shape[1] == len(selected_features):
            X_out = pd.DataFrame(X_scaled, columns=selected_features, index=df.index)
        else:
            X_out = X_scaled
        
        return X_out, y

    def _get_safe_features(self, df):
        """Select safe features based on whitelist."""
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Combine all safe keywords
        all_safe_keywords = self.basic_features.copy()
        
        if self.use_advanced_features:
            all_safe_keywords.extend(self.advanced_features)
        
        all_safe_keywords.extend(self.market_features)
        
        selected_features = []
        for col in numeric_cols:
            # Check if column is safe
            is_safe = (
                any(keyword in col for keyword in all_safe_keywords) or
                col in self.market_features
            )
            
            # Check if column is forbidden
            is_forbidden = any(forbidden in col for forbidden in self.forbidden_features)
            
            if is_safe and not is_forbidden:
                selected_features.append(col)
        
        # Remove any duplicates
        selected_features = list(dict.fromkeys(selected_features))
        
        # Remove any remaining forbidden features by exact match
        selected_features = [f for f in selected_features if f not in self.forbidden_features]
        
        # Debug info
        print(f"   🛡️ Security Audit: Selected {len(selected_features)} safe features")
        print(f"   📊 Feature Types: Basic={sum(1 for f in selected_features if any(k in f for k in self.basic_features))}, "
              f"Advanced={sum(1 for f in selected_features if any(k in f for k in self.advanced_features))}, "
              f"Market={sum(1 for f in selected_features if f in self.market_features)}")
        
        if len(selected_features) == 0:
            raise ValueError("❌ No valid features found! Check FeatureGenerator or Column Names.")
        
        return selected_features

    def _clean_features(self, X):
        """Clean and prepare feature matrix."""
        # Replace infinities with NaN first
        X = X.replace([np.inf, -np.inf], np.nan)
        
        # Fill NaN values with column median (safer than 0 for some features)
        for col in X.columns:
            if X[col].isna().any():
                X[col] = X[col].fillna(X[col].median() if X[col].notna().any() else 0)
        
        return X

    def _scale_features(self, X):
        """Scale features using saved scaler or return raw values."""
        if self.scaler_path.exists():
            try:
                scaler = joblib.load(self.scaler_path)
                X_scaled = scaler.transform(X)
                return X_scaled
            except (ValueError, AttributeError) as e:
                print(f"   ⚠️ Scaler mismatch: {e}. Using raw values.")
                return X.values
        else:
            print("   ⚠️ Scaler not found. Using raw values.")
            return X.values

    def _get_target(self, df, target_name):
        """Extract target variable."""
        target_mappings = {
            'WLD': self._get_wld_target,
            'BTTS': self._get_btts_target,
            'Over25': self._get_over25_target,
            'TotalGoals': self._get_total_goals_target
        }
        
        if target_name not in target_mappings:
            raise ValueError(f"Unknown target: {target_name}")
        
        return target_mappings[target_name](df)

    def _get_wld_target(self, df):
        """Extract Win/Loss/Draw target."""
        # Try different column names for result
        result_cols = ['FTR', 'FTResult', 'Res']
        for col in result_cols:
            if col in df.columns:
                mapping = self.config.RESULT_MAP  # {'H': 2, 'D': 1, 'A': 0}
                return df[col].map(mapping).fillna(1).astype(int)
        
        raise ValueError("Result column not found for WLD target")

    def _get_btts_target(self, df):
        """Extract Both Teams To Score target."""
        if 'BTTS' in df.columns:
            return df['BTTS'].fillna(0).astype(int)
        elif all(col in df.columns for col in ['FTHG', 'FTAG']):
            return ((df['FTHG'] > 0) & (df['FTAG'] > 0)).astype(int)
        else:
            raise ValueError("Cannot compute BTTS target")

    def _get_over25_target(self, df):
        """Extract Over 2.5 Goals target."""
        if 'Over25' in df.columns:
            return df['Over25'].fillna(0).astype(int)
        elif 'TotalGoals' in df.columns:
            return (df['TotalGoals'] > 2.5).astype(int)
        elif all(col in df.columns for col in ['FTHG', 'FTAG']):
            return ((df['FTHG'] + df['FTAG']) > 2.5).astype(int)
        else:
            raise ValueError("Cannot compute Over25 target")

    def _get_total_goals_target(self, df):
        """Extract Total Goals target."""
        if 'TotalGoals' in df.columns:
            return df['TotalGoals'].fillna(0).astype(float)
        elif all(col in df.columns for col in ['FTHG', 'FTAG']):
            return (df['FTHG'] + df['FTAG']).astype(float)
        else:
            raise ValueError("Cannot compute TotalGoals target")

    def _validate_features(self, X, is_training=True):
        """Validate feature consistency."""
        if is_training:
            print(f"   ✅ Training features validated: {X.shape[1]} features")
        else:
            if hasattr(X, 'shape'):
                print(f"   ✅ Prediction features validated: {X.shape[1]} features")
    
    def get_feature_summary(self, X):
        """Get summary of features being used."""
        if hasattr(X, 'columns'):
            features_by_type = {
                'Basic': [f for f in X.columns if any(k in f for k in self.basic_features)],
                'Advanced': [f for f in X.columns if any(k in f for k in self.advanced_features)],
                'Market': [f for f in X.columns if f in self.market_features]
            }
            
            summary = {}
            for type_name, features in features_by_type.items():
                if features:
                    summary[type_name] = len(features)
            
            return summary
        return {}