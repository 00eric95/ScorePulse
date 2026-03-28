"""
Updated training script that integrates data loading, feature generation, engineering, 
optional hyperparameter loading from tuner, model comparison, and logging.
It ensures consistency with feature_engineering.py, feature_generator.py, 
data_loader.py, and tuner.py by:
- Checking/Running DataLoader if processed data is missing.
- Adding advanced features via AdvancedFeatureGenerator if not present.
- Using FeatureEngineer for safe feature selection, cleaning, and scaling.
- Loading best params from best_hyperparameters.json if available.
- Handling LGBM optionally.
- Evaluating on validation set to select and save the best model per target.
- Logging results to training_history.csv.
"""

import pandas as pd
import numpy as np
import os
import sys
import joblib
import json
from datetime import datetime
from sklearn.metrics import accuracy_score, mean_absolute_error

# Optional LGBM
try:
    from lightgbm import LGBMClassifier, LGBMRegressor
    LGBM_AVAILABLE = True
except ImportError:
    LGBM_AVAILABLE = False

# Path Setup (use current working dir as base)
current_dir = os.getcwd()
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from config.config import Config
    from utils.feature_engineering import FeatureEngineer
    from models.model_factory import ModelFactory
    from utils.data_loader import DataLoader
    from utils.feature_generator import AdvancedFeatureGenerator
except ImportError as e:
    raise ImportError(f"Failed to import required modules: {e}")

class ModelTrainer:
    def __init__(self):
        self.config = Config()
        self.engineer = FeatureEngineer(use_advanced_features=True)
        self.generator = AdvancedFeatureGenerator(use_data_loader_features=True)
        self.best_params_path = self.config.BEST_PARAMS_PATH
        self.contenders = ['xgb', 'rf'] if not LGBM_AVAILABLE else ['xgb', 'lgbm', 'rf']
        self.targets = ['WLD', 'BTTS', 'Over25', 'TotalGoals']
    
    def _load_or_process_data(self):
        """Run DataLoader if processed data is missing."""
        train_path = self.config.PROCESSED_DATA_DIR / "train.csv"
        if not train_path.exists():
            print("⚠️ Processed data not found. Running data loader...")
            loader = DataLoader()
            loader.run()
    
    def _load_best_params(self, model_type, target_name):
        """Load tuned params if available."""
        if self.best_params_path.exists():
            try:
                with open(self.best_params_path, 'r') as f:
                    data = json.load(f)
                key = f"{model_type}_{target_name}"
                params = data.get(key, {})
                print(f"   ✓ Loaded tuned params for {key}")
                return params
            except Exception as e:
                print(f"   ⚠️ Failed to load params: {e}")
        return {}
    
    def train_and_evaluate(self, target_name):
        """Train and select best model for a target."""
        print(f"\n⚽ Training for Target: {target_name}")
        print("---------------------------------------------")
        
        mode = 'regression' if target_name == 'TotalGoals' else 'classification'
        
        # Load train/val data
        train_df = pd.read_csv(self.config.PROCESSED_DATA_DIR / "train.csv", low_memory=False)
        val_df = pd.read_csv(self.config.PROCESSED_DATA_DIR / "val.csv", low_memory=False)
        
        # Add advanced features if missing
        if not all(col in train_df.columns for col in ['Home_AttackEff', 'Away_AttackEff']):  # Check for advanced
            print("   Adding advanced features to train...")
            train_df = self.generator.generate(train_df)
        if not all(col in val_df.columns for col in ['Home_AttackEff', 'Away_AttackEff']):
            print("   Adding advanced features to val...")
            val_df = self.generator.generate(val_df)
        
        # Feature Engineering (fit on train, transform on val)
        X_train, y_train = self.engineer.fit_transform(train_df, target_name=target_name)[:2]  # Ignore selected_features for now
        X_val_result = self.engineer.transform(val_df, target_name=target_name)
        if isinstance(X_val_result, tuple):
            X_val, y_val = X_val_result
        else:
            X_val = X_val_result
            y_val = self.engineer._get_target(val_df, target_name)
        
        best_score = -np.inf if mode == 'classification' else np.inf
        best_model = None
        best_name = ""
        
        for model_name in self.contenders:
            print(f"   🔹 Training {model_name.upper()}")
            
            # Load tuned params
            params = self._load_best_params(model_name, target_name)
            
            # Get and train model
            try:
                model = ModelFactory.get_model(model_name, mode=mode, params=params)
                model.train(X_train, y_train)
                
                # Evaluate
                preds = model.predict(X_val)
                if mode == 'classification':
                    score = accuracy_score(y_val, preds)
                    score_display = f"Acc: {score:.2%}"
                    is_better = score > best_score
                else:
                    score = mean_absolute_error(y_val, preds)
                    score_display = f"MAE: {score:.4f}"
                    is_better = score < best_score
                
                print(f"      {score_display}")
                
                if is_better:
                    best_score = score
                    best_model = model
                    best_name = model_name
            except Exception as e:
                print(f"      ❌ Failed: {e}")
        
        # Save best model
        if best_model:
            filename = f"model_{target_name}.pkl"
            save_path = self.config.MODELS_DIR / filename
            best_model.save(save_path)
            print(f"   👑 Winner: {best_name.upper()} ({best_score:.4f}) saved to {filename}")
            
            # Log
            self._log_results(target_name, best_name, mode, best_score, X_train.shape[1])
    
    def _log_results(self, target_name, model_name, mode, score, feature_count):
        """Log training results to CSV."""
        log_row = {
            'Timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'Target': target_name,
            'ModelType': model_name.upper(),
            'Metric': 'Accuracy' if mode == 'classification' else 'MAE',
            'Score': float(score),
            'Feature_Count': int(feature_count),
            'Best_Params': json.dumps(self._load_best_params(model_name, target_name))
        }
        
        logs_dir = os.path.join(os.getcwd(), 'logs')
        os.makedirs(logs_dir, exist_ok=True)
        log_path = os.path.join(logs_dir, 'training_history.csv')
        
        import csv
        write_header = not os.path.exists(log_path)
        with open(log_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=log_row.keys())
            if write_header:
                writer.writeheader()
            writer.writerow(log_row)
        print("   📝 Logged results")
    
    def run(self):
        """Run full training pipeline."""
        print("\n⚖️ STARTING UPDATED MODEL TRAINING ⚖️")
        print("==========================================================")
        
        self._load_or_process_data()
        for target in self.targets:
            self.train_and_evaluate(target)
        
        print("\n✅ Training completed!")

if __name__ == "__main__":
    trainer = ModelTrainer()
    trainer.run()