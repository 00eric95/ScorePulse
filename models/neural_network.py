import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, TensorDataset
import sys
import os

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from config.config import Config

# --- PyTorch Architecture ---
class SoccerNet(nn.Module):
    def __init__(self, input_size, output_size):
        super(SoccerNet, self).__init__()
        
        self.layer1 = nn.Sequential(
            nn.Linear(input_size, 128),
            nn.BatchNorm1d(128),
            nn.ReLU(),
            nn.Dropout(0.3)
        )
        self.layer2 = nn.Sequential(
            nn.Linear(128, 64),
            nn.BatchNorm1d(64),
            nn.ReLU(),
            nn.Dropout(0.2)
        )
        self.output = nn.Linear(64, output_size)
        
    def forward(self, x):
        x = self.layer1(x)
        x = self.layer2(x)
        return self.output(x)

# --- Model Wrapper ---
class NeuralNetworkModel:
    def __init__(self, input_size, output_size=3, mode='classification', epochs=30, batch_size=64):
        self.config = Config()
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.epochs = epochs
        self.batch_size = batch_size
        self.mode = mode
        
        self.model = SoccerNet(input_size, output_size).to(self.device)
        
        if mode == 'classification':
            self.criterion = nn.CrossEntropyLoss()
        else:
            self.criterion = nn.MSELoss() # For Goal prediction
            
        self.optimizer = optim.Adam(self.model.parameters(), lr=0.001)

    def train(self, X, y):
        # Convert Pandas/Numpy to Tensor
        X_tensor = torch.tensor(X.values, dtype=torch.float32)
        
        if self.mode == 'classification':
            y_tensor = torch.tensor(y, dtype=torch.long)
        else:
            y_tensor = torch.tensor(y, dtype=torch.float32).view(-1, 1)

        dataset = TensorDataset(X_tensor, y_tensor)
        loader = DataLoader(dataset, batch_size=self.batch_size, shuffle=True)
        
        print(f"🧠 Training Neural Network on {self.device}...")
        self.model.train()
        
        for epoch in range(self.epochs):
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
        self.model.eval()
        X_tensor = torch.tensor(X.values, dtype=torch.float32).to(self.device)
        
        with torch.no_grad():
            outputs = self.model(X_tensor)
            
            if self.mode == 'classification':
                _, predicted = torch.max(outputs, 1)
                return predicted.cpu().numpy()
            else:
                return outputs.cpu().numpy().flatten()

    def save(self, filename="nn_model.pth"):
        path = self.config.MODELS_DIR / filename
        torch.save(self.model.state_dict(), path)
        print(f"💾 Model saved to {path}")