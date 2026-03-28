"""
A deep learning implementation using PyTorch to model complex non-linear soccer match relationships.
The 'SoccerNet' architecture features dynamic hidden layers, Batch Normalization, and Dropout layers.
It encapsulates the full training loop, including tensor conversion, loss calculation, and backpropagation.
The wrapper manages device placement, automatically utilizing CUDA GPUs if available for faster training.
Model state dicts and architectural parameters are saved together to ensure perfect reconstruction on load.
"""


import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import sys
import os
import pandas as pd
import numpy as np

# --- Path Setup ---
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

# --- PyTorch Architecture (The Brain) ---
class SoccerNet(nn.Module):
    def __init__(self, input_size, output_size, hidden_layers=[128, 64], dropout_rate=0.3):
        super(SoccerNet, self).__init__()
        
        layers = []
        in_dim = input_size
        
        # Dynamically build layers based on the list
        for h_dim in hidden_layers:
            layers.append(nn.Linear(in_dim, h_dim))
            layers.append(nn.BatchNorm1d(h_dim)) # Stabilizes learning
            layers.append(nn.ReLU())             # Activation function
            layers.append(nn.Dropout(dropout_rate)) # Prevents overfitting
            in_dim = h_dim
            
        # Output Layer
        layers.append(nn.Linear(in_dim, output_size))
        
        self.network = nn.Sequential(*layers)
        
    def forward(self, x):
        return self.network(x)

# --- Model Wrapper (The Interface) ---
class NNModel:
    def __init__(self, mode='classification', target_name='WLD', **kwargs):
        self.config = Config()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.mode = mode
        self.target_name = target_name
        
        # =========================================================
        # 🛠️ MANUAL PARAMETER ZONE
        # =========================================================
        if mode == 'classification':
            self.params = {
                'epochs': 50,
                'batch_size': 32,
                'learning_rate': 0.001,
                'hidden_layers': [128, 64],
                'dropout_rate': 0.3
            }
        else:
            # Regression settings (TotalGoals)
            self.params = {
                'epochs': 100,
                'batch_size': 16,
                'learning_rate': 0.0005,
                'hidden_layers': [256, 128, 64], 
                'dropout_rate': 0.2
            }
        
        # Override defaults with any kwargs passed
        self.params.update(kwargs)
        
        self.model = None
        self.optimizer = None
        self.criterion = None

    def _init_model(self, input_size, output_size):
        """Initializes the inner PyTorch model."""
        self.model = SoccerNet(
            input_size=input_size, 
            output_size=output_size,
            hidden_layers=self.params['hidden_layers'],
            dropout_rate=self.params['dropout_rate']
        ).to(self.device)
        
        # Define Loss Function
        if self.mode == 'classification':
            self.criterion = nn.CrossEntropyLoss()
        else:
            self.criterion = nn.MSELoss()
            
        # Define Optimizer
        self.optimizer = optim.Adam(self.model.parameters(), lr=self.params['learning_rate'])

    def train(self, X, y):
        # 1. Determine Shapes
        input_size = X.shape[1]
        
        if self.mode == 'classification':
            # WLD = 3 classes, BTTS = 2 classes
            output_size = len(np.unique(y))
        else:
            # Regression = 1 output (Goals)
            output_size = 1

        # 2. Initialize Model
        self._init_model(input_size, output_size)
        
        # 3. Prepare Data
        X_values = X.values if isinstance(X, pd.DataFrame) else X
        X_tensor = torch.tensor(X_values, dtype=torch.float32)
        
        if self.mode == 'classification':
            y_tensor = torch.tensor(y, dtype=torch.long)
        else:
            y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.params['batch_size'], shuffle=True)
        
        # 4. Training Loop
        print(f"   🧠 Training PyTorch NN on {self.device}...")
        self.model.train()
        
        for epoch in range(self.params['epochs']):
            total_loss = 0
            for batch_X, batch_y in loader:
                batch_X, batch_y = batch_X.to(self.device), batch_y.to(self.device)
                
                self.optimizer.zero_grad()
                outputs = self.model(batch_X)
                loss = self.criterion(outputs, batch_y)
                loss.backward()
                self.optimizer.step()
                total_loss += loss.item()

    def predict(self, X):
        if self.model is None:
            raise Exception("Model not trained or loaded.")
            
        self.model.eval()
        X_values = X.values if isinstance(X, pd.DataFrame) else X
        X_tensor = torch.tensor(X_values, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            
            if self.mode == 'classification':
                _, predicted = torch.max(outputs, 1)
                return predicted.cpu().numpy()
            else:
                return outputs.cpu().numpy().flatten()

    def predict_proba(self, X):
        if self.mode != 'classification':
            return None
            
        self.model.eval()
        X_values = X.values if isinstance(X, pd.DataFrame) else X
        X_tensor = torch.tensor(X_values, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            probs = torch.softmax(outputs, dim=1)
            return probs.cpu().numpy()

    def save(self, filepath):
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        # We save the state dict AND the params so we can reconstruct it
        checkpoint = {
            'state_dict': self.model.state_dict(),
            'params': self.params,
            'input_size': self.model.network[0].in_features,
            'output_size': self.model.network[-1].out_features
        }
        torch.save(checkpoint, filepath)

    def load(self, filepath):
        if os.path.exists(filepath):
            checkpoint = torch.load(filepath, map_location=self.device)
            
            # Reconstruct the model structure from saved metadata
            self.params = checkpoint['params']
            self._init_model(checkpoint['input_size'], checkpoint['output_size'])
            
            # Load weights
            self.model.load_state_dict(checkpoint['state_dict'])
            self.model.eval()
        else:
            print(f"   ⚠️ Model file not found: {filepath}")