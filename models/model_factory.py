"""
An implementation of the Factory Design Pattern for dynamic model instantiation and loading.
It utilizes 'Lazy Loading' (importing within methods) to prevent crashes if specific dependencies are missing.
The factory manages the lifecycle of XGBoost, Random Forest, LightGBM, and Neural Network models.
Static methods allow for standardized model creation and auto-detection of model types from disk.
This serves as the central orchestration point for the 'ScorePulse' AI prediction engine.
"""

class ModelFactory:
    @staticmethod
    def get_model(model_type, **kwargs):
        """
        Factory method to return the correct model instance.
        Imports happen INSIDE the function (Lazy Loading).
        """
        
        # 1. XGBoost (The Champion)
        if model_type == 'xgb':
            from models.xgb_model import XGBModel
            return XGBModel(**kwargs)

        # 2. Random Forest (Legacy/Missing)
        elif model_type == 'rf':
            try:
                from models.rf_model import RFModel
                return RFModel(**kwargs)
            except ImportError:
                raise ImportError("RFModel file is missing. You previously deleted it (SAFE to ignore if using XGB).")

        # 3. LightGBM (Legacy/Missing)
        elif model_type == 'lgbm':
            try:
                from models.lgbm_model import LGBMModel
                return LGBMModel(**kwargs)
            except ImportError:
                raise ImportError("LGBMModel file is missing.")

        # 4. Neural Network (Legacy/Missing)
        elif model_type == 'nn':
            try:
                from models.nn_model import NNModel
                return NNModel(**kwargs)
            except ImportError:
                raise ImportError("NNModel file is missing.")

        else:
            raise ValueError(f"Unknown model type: {model_type}")
    
    @staticmethod
    def load_model(filepath, model_type=None):
        """Loads a saved model, auto-detecting type if not specified."""
        import joblib
        model = joblib.load(filepath)
        
        # Auto-detect model type from loaded object
        if hasattr(model, 'booster') or 'XGB' in str(type(model)):
            from models.xgb_model import XGBModel
            wrapper = XGBModel()
        elif 'RandomForest' in str(type(model)):
            from models.rf_model import RFModel
            wrapper = RFModel()
        # ... other type detection
        
        wrapper.model = model
        return wrapper