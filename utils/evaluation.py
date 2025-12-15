import pandas as pd
import numpy as np
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix, mean_absolute_error, mean_squared_error
import matplotlib.pyplot as plt
import seaborn as sns
from config.config import Config

class Evaluator:
    def __init__(self):
        self.config = Config()

    def evaluate_classification(self, y_true, y_pred, target_name="WLD", class_names=None):
        """
        Prints standard classification metrics.
        """
        print(f"\n📊 EVALUATION REPORT: {target_name}")
        print("=========================================")
        
        acc = accuracy_score(y_true, y_pred)
        print(f"✅ Accuracy: {acc:.2%}")
        
        print("\n📝 Classification Report:")
        print(classification_report(y_true, y_pred, target_names=class_names))
        
        # Confusion Matrix (Text based for CLI)
        cm = confusion_matrix(y_true, y_pred)
        print("\n🧩 Confusion Matrix:")
        print(cm)
        return acc

    def evaluate_regression(self, y_true, y_pred, target_name="TotalGoals"):
        """
        Prints regression metrics for goals.
        """
        print(f"\n📊 EVALUATION REPORT: {target_name}")
        print("=========================================")
        
        mae = mean_absolute_error(y_true, y_pred)
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        
        print(f"📉 Mean Absolute Error (MAE): {mae:.4f} goals")
        print(f"📉 Root Mean Squared Error (RMSE): {rmse:.4f} goals")
        return mae

    def calculate_roi(self, df, preds, target_col="Target_WLD"):
        """
        Calculates the Return on Investment (ROI) assuming a flat stake bet on every game.
        Crucial for betting models.
        """
        print(f"\n💰 BETTING ROI ANALYSIS ({target_col})")
        print("=========================================")
        
        # We need the odds from the dataframe
        # Assuming preds align with df index (Test Set)
        
        capital = 0.0
        stake = 10.0 # Bet $10 per game
        wins = 0
        losses = 0
        
        roi_data = []

        # Iterate through the test set
        for i, (index, row) in enumerate(df.iterrows()):
            actual = row[target_col]
            prediction = preds[i]
            
            # Get the odds for the PREDICTED outcome
            # Map prediction (0,1,2) to column names (OddHome, OddDraw, OddAway)
            if prediction == 0: # Home
                odds = row['OddHome']
            elif prediction == 1: # Draw
                odds = row['OddDraw']
            else: # Away
                odds = row['OddAway']
            
            # Betting Logic
            if prediction == actual:
                profit = (odds * stake) - stake
                capital += profit
                wins += 1
            else:
                loss = stake
                capital -= loss
                losses += 1
                
            roi_data.append(capital)

        total_bets = wins + losses
        roi_percent = (capital / (total_bets * stake)) * 100
        
        print(f"💵 Total Bets: {total_bets}")
        print(f"✅ Wins: {wins} | ❌ Losses: {losses} | Win Rate: {wins/total_bets:.1%}")
        print(f"💲 Net Profit: ${capital:.2f}")
        print(f"📈 ROI: {roi_percent:.2f}%")
        
        return capital, roi_percent