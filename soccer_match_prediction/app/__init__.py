from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
import os

# IMPORTANT:
# We now import Flask config from settings.py, NOT config.py
from soccer_match_prediction.settings import Config

# Initialize Extensions
db = SQLAlchemy()
bcrypt = Bcrypt()
login_manager = LoginManager()
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

def create_app(config_class=Config):

    # --- Locate app folders ---
    app_dir = os.path.dirname(os.path.abspath(__file__))
    template_folder = os.path.join(app_dir, 'templates')
    static_folder = os.path.join(app_dir, 'static')

    # Debug output
    print(f"📂 App Directory: {app_dir}")
    print(f"📂 Templates Path: {template_folder}")

    if not os.path.exists(template_folder):
        print("❌ ERROR: templates/ folder NOT found.")
    else:
        print("✅ templates/ located.")
        if os.path.exists(os.path.join(template_folder, 'home.html')):
            print("   ✅ home.html OK")
        else:
            print("   ❌ home.html missing!")

    # Create Flask app with explicit template/static folders
    app = Flask(__name__, 
                template_folder=template_folder, 
                static_folder=static_folder)

    # Apply Flask settings
    app.config.from_object(config_class)

    # Ensure instance folder exists
    try:
        os.makedirs(app.instance_path, exist_ok=True)
    except OSError:
        pass

    # Init extensions
    db.init_app(app)
    bcrypt.init_app(app)
    login_manager.init_app(app)

    # Register routes
    with app.app_context():
        from app import routes
        db.create_all()

    return app
