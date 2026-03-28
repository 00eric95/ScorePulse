"""
This script provides the final quality assurance gate by testing trained models against a dedicated test dataset.
It dynamically loads the saved 'champion' models from the models directory for all betting targets.
The pipeline calculates standard metrics like Accuracy for classifications and Mean Absolute Error for goal totals.
For Win-Loss-Draw (WLD) predictions, it specifically calculates the projected ROI to assess financial viability.
Detailed results and diagnostic snapshots are sent to the TrainingLogger to maintain a record of model reliability.
"""

import pandas as pd
import sys
import os

# --- Import Project Modules ---
from config.config import Config
from utils.evaluation import Evaluator
from utils.feature_engineering import FeatureEngineer
from models.model_factory import ModelFactory
from monitoring.logger import TrainingLogger

class EvaluationPipeline:
    def __init__(self):
        self.config = Config()
        self.evaluator = Evaluator()
        self.engineer = FeatureEngineer()
        self.models = {}
        self.logger = TrainingLogger()

    def load_models(self):
        """Loads trained models using Absolute Paths."""
        print("📥 Loading models for evaluation...")
        
        # 1. Define Strict Path to Models Folder
        project_root = os.getcwd()
        models_dir = os.path.join(project_root, "models")
        
        print(f"   📂 Looking in: {models_dir}")

        if not os.path.exists(models_dir):
            print(f"   ❌ Error: Directory not found!")
            return

        for target_name in self.config.TARGETS.keys():
            filename = f"model_{target_name}.pkl"
            full_path = os.path.join(models_dir, filename)
            mode = 'regression' if target_name == 'TotalGoals' else 'classification'
            
            # 2. Check existence BEFORE loading
            if not os.path.exists(full_path):
                print(f"   ⚠️ MISSING: {filename}")
                continue

            try:
                # We use 'rf' wrapper as a container (it can load any sklearn model pickle)
                model = ModelFactory.get_model('rf', mode=mode)
                model.load(full_path)
                self.models[target_name] = model
                print(f"   ✅ Loaded: {filename}")
                
            except Exception as e:
                print(f"   ❌ CRITICAL: Found {filename} but failed to load it.")
                print(f"      Error Details: {e}")

    def run(self):
        # 3. Load Test Data
        test_path = self.config.PROCESSED_DATA_DIR / "test.csv"
        
        # Handle path object vs string
        if not os.path.exists(test_path):
             # Fallback for string paths
             test_path = os.path.join(os.getcwd(), "data", "processed", "test.csv")
             
        if not os.path.exists(test_path):
            print(f"❌ Test data not found at {test_path}")
            print("   Run 'python training.py' or 'python compare_models.py' to generate data.")
            return

        print(f"📂 Loading Test Data: {test_path}")
        test_df = pd.read_csv(test_path)
        
        if not self.models:
            print("❌ No models were loaded. Cannot proceed with evaluation.")
            return

        # 4. Evaluate Each Target
        for target_name, model in self.models.items():
            if target_name not in self.config.TARGETS:
                continue
                
            print(f"\n🚀 TEST RUN: {target_name}")
            
            try:
                # Prepare Features
                X_test, y_true = self.engineer.transform(test_df, target_name=target_name)
                # Sanity prints: show feature columns and sample target values for debugging
                try:
                    cols = getattr(X_test, 'columns', None)
                    if cols is not None:
                        print(f"   🔎 Feature columns ({len(cols)}): {list(cols)[:10]}{'...' if len(cols)>10 else ''}")
                except Exception:
                    pass
                try:
                    if y_true is not None:
                        print(f"   🔎 y_true sample values: {pd.Series(y_true).unique()[:10]}")
                except Exception:
                    pass
                
                # Predict
                preds = model.predict(X_test)
                
                # Calculate Metrics
                if target_name == 'WLD':
                    acc = self.evaluator.evaluate_classification(
                        y_true, preds, target_name=target_name, class_names=['Home', 'Draw', 'Away']
                    )
                    # Log accuracy
                    try:
                        self.logger.log_evaluation(target_name, model.__class__.__name__, 'Accuracy', acc,
                                                   details=f"n_test={len(y_true)}")
                    except Exception:
                        pass

                    # ROI
                    capital, roi_percent = self.evaluator.calculate_roi(test_df, preds, target_col=self.config.TARGETS['WLD'])
                    try:
                        self.logger.log_evaluation(target_name, model.__class__.__name__, 'ROI', roi_percent,
                                                   details=f"NetProfit={capital:.2f}")
                    except Exception:
                        pass
                    
                elif target_name == 'BTTS':
                    acc = self.evaluator.evaluate_classification(
                        y_true, preds, target_name=target_name, class_names=['No', 'Yes']
                    )
                    try:
                        self.logger.log_evaluation(target_name, model.__class__.__name__, 'Accuracy', acc,
                                                   details=f"n_test={len(y_true)}")
                    except Exception:
                        pass
                    
                elif target_name == 'Over25':
                    acc = self.evaluator.evaluate_classification(
                        y_true, preds, target_name=target_name, class_names=['Under', 'Over']
                    )
                    try:
                        self.logger.log_evaluation(target_name, model.__class__.__name__, 'Accuracy', acc,
                                                   details=f"n_test={len(y_true)}")
                    except Exception:
                        pass
                    
                elif target_name == 'TotalGoals':
                    mae = self.evaluator.evaluate_regression(y_true, preds, target_name=target_name)
                    try:
                        self.logger.log_evaluation(target_name, model.__class__.__name__, 'MAE', mae,
                                                   details=f"n_test={len(y_true)}")
                    except Exception:
                        pass
            
            except Exception as e:
                print(f"   ⚠️ Evaluation failed for {target_name}: {e}")

if __name__ == "__main__":
    pipeline = EvaluationPipeline()
    pipeline.load_models()
    pipeline.run()