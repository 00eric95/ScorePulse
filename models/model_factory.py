from models.random_forest import RandomForestModel
from models.gradient_boosting import GradientBoostingModel
from models.neural_network import NeuralNetworkModel

class ModelFactory:
    @staticmethod
    def get_model(model_type, **kwargs):
        """
        Factory method to create models.
        :param model_type: 'rf' (Random Forest), 'gb' (Gradient Boosting), 'nn' (Neural Network)
        """
        if model_type == 'rf':
            return RandomForestModel(**kwargs)
        elif model_type == 'gb':
            return GradientBoostingModel(**kwargs)
        elif model_type == 'nn':
            return NeuralNetworkModel(**kwargs)
        elif model_type == 'svm':
            return SVMModel(**kwargs)
        else:
            raise ValueError(f"Unknown model type: {model_type}")