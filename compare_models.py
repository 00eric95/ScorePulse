import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, mean_squared_error
import sys
import os

# --- Import Project Modules ---
from config.config import Config
from utils.data_loader import DataLoader
from utils.feature_engineering import FeatureEngineer
from models.model_factory import ModelFactory
from monitoring.logger import TrainingLogger

class ModelComparator:
    def __init__(self):
        self.config = Config()
        self.loader = DataLoader()
        self.engineer = FeatureEngineer()
        self.logger = TrainingLogger()
        
    def run(self):
        print("⚖️  STARTING MODEL COMPARISON TOURNAMENT ⚖️")
        print("============================================")
        self.logger.log_event("🏆 Tournament Started: RF vs GB vs NN vs SVM")
        
        # 1. Load Data
        if not (self.config.PROCESSED_DATA_DIR / "train.csv").exists():
            print("⚠️ Data not found. Running Loader...")
            raw_df = self.loader.load_raw_data()
            clean_df = self.loader.preprocess(raw_df)
            self.loader.save_splits(clean_df)

        train_df = pd.read_csv(self.config.PROCESSED_DATA_DIR / "train.csv")
        val_df = pd.read_csv(self.config.PROCESSED_DATA_DIR / "val.csv")
        
        # --- DEFINE THE CONTENDERS ---
        model_types = ['rf', 'gb', 'nn', 'svm'] # <--- SVM ADDED HERE
        model_names = {
            'rf': 'Random Forest', 
            'gb': 'Gradient Boosting', 
            'nn': 'Neural Network',
            'svm': 'Support Vector Machine'
        }
        
        # Loop through each prediction target (WLD, Goals, etc.)
        for target_name in self.config.TARGETS.keys():
            print(f"\n⚽ TARGET: {target_name}")
            print("---------------------------------------------")
            
            mode = 'regression' if target_name == 'TotalGoals' else 'classification'
            
            # Prepare Data (Scaling)
            X_train, y_train = self.engineer.fit_transform(train_df, target_name=target_name)
            X_val, y_val = self.engineer.transform(val_df, target_name=target_name)
            
            # Track the winner
            best_score = -float('inf') if mode == 'classification' else float('inf')
            best_model_name = ""
            best_model_obj = None
            
            # --- THE TOURNAMENT LOOP ---
            for m_type in model_types:
                # Prepare arguments
                params = {'mode': mode}
                
                # Special handling for Neural Networks (needs input dimensions)
                if m_type == 'nn':
                    params['input_size'] = X_train.shape[1]
                    params['output_size'] = 3 if target_name == 'WLD' else 1
                    if target_name in ['BTTS', 'Over25']:
                        params['output_size'] = 2
                    params['epochs'] = 20 
                
                # Initialize & Train
                try:
                    model = ModelFactory.get_model(m_type, **params)
                    model.train(X_train, y_train)
                    
                    # Evaluate
                    preds = model.predict(X_val)
                    score = 0
                    score_display = ""
                    
                    if mode == 'classification':
                        score = accuracy_score(y_val, preds)
                        score_display = f"Accuracy: {score:.2%}"
                        # Higher Accuracy is Better
                        if score > best_score:
                            best_score = score
                            best_model_name = m_type
                            best_model_obj = model
                    else:
                        score = mean_squared_error(y_val, preds)
                        rmse = np.sqrt(score)
                        score_display = f"MSE: {score:.4f} (RMSE: {rmse:.4f})"
                        # Lower Error is Better
                        if score < best_score:
                            best_score = score
                            best_model_name = m_type
                            best_model_obj = model
                    
                    print(f"   🔹 {model_names[m_type]:<25} | {score_display}")
                    self.logger.log_metric(target_name, m_type, 'Comparison_Score', score)
                    
                except Exception as e:
                    print(f"   ❌ {model_names[m_type]} Failed: {e}")

            # --- THE CHAMPION ---
            winner_display = model_names.get(best_model_name, "None")
            print(f"\n   🏆 WINNER: {winner_display}")
            
            if best_model_obj:
                filename = f"model_{target_name}.pkl"
                best_model_obj.save(filename)
                print(f"   💾 Saved to models/{filename}")
                self.logger.log_event(f"Tournament {target_name} Winner: {winner_display}")

if __name__ == "__main__":
    comp = ModelComparator()
    comp.run()