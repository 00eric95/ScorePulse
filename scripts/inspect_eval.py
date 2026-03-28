import pandas as pd, joblib, os
from config.config import Config
from utils.feature_engineering import FeatureEngineer
cfg=Config()
print('TARGETS:', cfg.TARGETS)
print('RESULT_MAP:', cfg.RESULT_MAP)

test_path = cfg.PROCESSED_DATA_DIR / 'test.csv'
print('test_path:', test_path, 'exists:', test_path.exists())
if not test_path.exists():
    test_path = os.path.join('data','processed','test.csv')
    print('fallback path:', test_path, 'exists:', os.path.exists(test_path))

if os.path.exists(test_path):
    df = pd.read_csv(test_path)
    print('\nColumns (first 40):', list(df.columns)[:40])
    col = cfg.TARGETS['WLD']
    print('\nWLD target column:', col)
    if col in df.columns:
        print('WLD unique values sample:', pd.Series(df[col]).unique()[:20])
        print('dtype:', df[col].dtype)
    else:
        print('WLD column not found in test df')

    fe = FeatureEngineer()
    X,y = fe.transform(df, target_name='WLD')
    print('\nFeature output type:', type(X))
    try:
        print('Feature columns (first 30):', list(X.columns)[:30])
    except Exception:
        print('Feature array shape:', getattr(X,'shape',None))
    try:
        print('y unique sample:', pd.Series(y).unique()[:20])
    except Exception:
        print('y not available')

    print('\nScaler path:', cfg.SCALER_PATH, 'exists:', os.path.exists(cfg.SCALER_PATH))
    if os.path.exists(cfg.SCALER_PATH):
        sc = joblib.load(cfg.SCALER_PATH)
        print('scaler n_features_in_:', getattr(sc,'n_features_in_',None))
        try:
            print('scaler mean length:', len(sc.mean_))
        except Exception:
            pass

    model_file = os.path.join('models','model_WLD.pkl')
    print('\nmodel_file:', model_file, 'exists:', os.path.exists(model_file))
    if os.path.exists(model_file):
        try:
            m = joblib.load(model_file)
            print('Loaded model type:', type(m))
            print('has feature_name_:', getattr(m,'feature_name_',None))
            print('has n_features_in_:', getattr(m,'n_features_in_',None))
            try:
                booster = getattr(m,'booster_',None) or getattr(m,'_Booster',None)
                print('booster attr exists:', booster is not None)
            except Exception:
                pass
        except Exception as e:
            print('Failed loading model file:', e)
else:
    print('test data not found; cannot inspect')
