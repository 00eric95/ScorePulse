import pandas as pd
import sys
import os

# --- Import Project Modules ---
from config.config import Config
from utils.evaluation import Evaluator
from utils.feature_engineering import FeatureEngineer
from models.model_factory import ModelFactory

class EvaluationPipeline:
    def __init__(self):
        self.config = Config()
        self.evaluator = Evaluator()
        self.engineer = FeatureEngineer()
        self.models = {}

    def load_models(self):
        """Loads trained models."""
        print("📥 Loading models for evaluation...")
        for target_name in self.config.TARGETS.keys():
            filename = f"model_{target_name}.pkl"
            mode = 'regression' if target_name == 'TotalGoals' else 'classification'
            
            try:
                model = ModelFactory.get_model('rf', mode=mode)
                model.load(filename)
                self.models[target_name] = model
            except FileNotFoundError:
                print(f"⚠️ Warning: {filename} not found. Skipping.")

    def run(self):
        # 1. Load Test Data
        test_path = self.config.PROCESSED_DATA_DIR / "test.csv"
        if not test_path.exists():
            print("❌ Test data not found. Run training.py first.")
            return

        print(f"📂 Loading Test Data: {test_path}")
        test_df = pd.read_csv(test_path)
        
        # 2. Evaluate Each Target
        for target_name, model in self.models.items():
            if target_name not in self.config.TARGETS:
                continue
                
            print(f"\n🚀 TEST RUN: {target_name}")
            
            # Prepare Features (Using same scaler as training)
            # transform() automatically handles scaling
            X_test, y_true = self.engineer.transform(test_df, target_name=target_name)
            
            # Predict
            preds = model.predict(X_test)
            
            # Calculate Metrics
            if target_name == 'WLD':
                self.evaluator.evaluate_classification(
                    y_true, preds, 
                    target_name=target_name, 
                    class_names=['Home', 'Draw', 'Away']
                )
                # Calculate Betting ROI for Win/Loss/Draw
                self.evaluator.calculate_roi(
                    test_df, preds, 
                    target_col=self.config.TARGETS['WLD']
                )
                
            elif target_name == 'BTTS':
                self.evaluator.evaluate_classification(
                    y_true, preds, 
                    target_name=target_name, 
                    class_names=['No', 'Yes']
                )
                
            elif target_name == 'Over25':
                self.evaluator.evaluate_classification(
                    y_true, preds, 
                    target_name=target_name, 
                    class_names=['Under', 'Over']
                )
                
            elif target_name == 'TotalGoals':
                self.evaluator.evaluate_regression(y_true, preds, target_name=target_name)

if __name__ == "__main__":
    pipeline = EvaluationPipeline()
    pipeline.load_models()
    pipeline.run()