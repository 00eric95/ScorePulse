import pandas as pd
import numpy as np
import sys
import os
import joblib
from sklearn.metrics import accuracy_score, mean_squared_error, mean_absolute_error

# --- 1. SETUP PATHS ---
# This block ensures Python can find your 'config' and 'utils' folders
# even if you run the script from a weird location.
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

# --- 2. IMPORT PROJECT MODULES ---
from config.config import Config
from utils.data_loader import DataLoader
from utils.feature_engineering import FeatureEngineer
from utils.tuner import HyperparameterTuner
from models.model_factory import ModelFactory
from monitoring.logger import TrainingLogger

class TrainingPipeline:
    def __init__(self):
        self.config = Config()
        self.loader = DataLoader()
        self.engineer = FeatureEngineer()
        self.tuner = HyperparameterTuner()
        self.logger = TrainingLogger()
        
    def run(self, tune_models=True):
        print("\n🚀 STARTING TRAINING PIPELINE")
        print("==================================")
        
        # --- PHASE 1: DATA LOADING ---
        # Check if processed data exists; if not, generate it.
        train_path = self.config.PROCESSED_DATA_DIR / "train.csv"
        val_path = self.config.PROCESSED_DATA_DIR / "val.csv"

        if not train_path.exists() or not val_path.exists():
            print("⚠️  Processed data missing. Initializing Data Loader...")
            raw_df = self.loader.load_raw_data()
            clean_df = self.loader.preprocess(raw_df)
            self.loader.save_splits(clean_df)
        
        print(f"📥 Loading datasets...")
        train_df = pd.read_csv(train_path)
        val_df = pd.read_csv(val_path)
        print(f"   - Train Rows: {len(train_df)}")
        print(f"   - Val Rows:   {len(val_df)}")

        # --- PHASE 2: TRAINING LOOP ---
        # We train a separate model for every target in config.TARGETS
        for target_name, target_col in self.config.TARGETS.items():
            print(f"\n⚽ TRAINING TARGET: {target_name}")
            print("----------------------------------")
            
            # 1. Define Problem Type
            # TotalGoals is regression (predicting a number), others are classification (Win/Loss, Yes/No)
            mode = 'regression' if target_name == 'TotalGoals' else 'classification'
            metric_name = 'MSE' if mode == 'regression' else 'Accuracy'

            # 2. Feature Engineering
            # fit_transform on Train to learn scaling, transform on Val to apply it
            print(f"⚙️  Engineering Features...")
            X_train, y_train = self.engineer.fit_transform(train_df, target_name=target_name)
            X_val, y_val = self.engineer.transform(val_df, target_name=target_name)
            
            # Save the scaler immediately so main.py can use it later
            # We save it after the first target (WLD) loop, or overwrite it safely
            if target_name == 'WLD':
                joblib.dump(self.engineer.scaler, self.config.SCALER_PATH)
                print(f"   - Scaler saved to {self.config.SCALER_PATH}")

            # 3. Hyperparameter Tuning (Optional)
            model_params = {}
            if tune_models:
                print(f"🔧 Tuning Hyperparameters (Random Search)...")
                # We default to Random Forest ('rf')
                best_params = self.tuner.tune('rf', mode, X_train, y_train, n_iter=5)
                model_params = best_params
            
            # 4. Train Model
            print(f"🧠 Training Model ({mode})...")
            model = ModelFactory.get_model('rf', mode=mode, **model_params)
            model.train(X_train, y_train)
            
            # 5. Evaluate
            print(f"📊 Evaluating...")
            preds = model.predict(X_val)
            
            if mode == 'classification':
                score = accuracy_score(y_val, preds)
                print(f"   ✅ {metric_name}: {score:.2%}")
            else:
                score = mean_squared_error(y_val, preds)
                print(f"   📉 {metric_name}: {score:.4f}")

            # 6. Log Metrics
            self.logger.log_metric(target_name, 'RandomForest', metric_name, score)

            # 7. Save Model
            filename = f"model_{target_name}.pkl"
            model.save(filename)
            print(f"   💾 Model saved: {filename}")

        print("\n==================================")
        print("✅ PIPELINE COMPLETE. READY FOR INFERENCE.")
        print("==================================")

if __name__ == "__main__":
    pipeline = TrainingPipeline()
    # Set tune_models=True for better accuracy (takes longer)
    # Set tune_models=False for fast debugging
    pipeline.run(tune_models=True)