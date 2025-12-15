import sys
import os

# --- PATH FIXER ---
# 1. Get the folder containing this file (.../soccer_match_prediction)
current_dir = os.path.dirname(os.path.abspath(__file__))

# 2. Get the project root (.../SCORE_PULSEv2)
project_root = os.path.dirname(current_dir)

# 3. Add BOTH to the Python path
# This allows finding 'config' (in root) AND 'app' (in current dir)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from app import create_app, db
from app.models import User, Prediction, Payment

app = create_app()

@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User, 'Prediction': Prediction, 'Payment': Payment}

if __name__ == '__main__':
    app.run(debug=True)