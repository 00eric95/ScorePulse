from datetime import datetime
from app import db, login_manager
from flask_login import UserMixin

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    image_file = db.Column(db.String(20), nullable=False, default='default.jpg')
    password_hash = db.Column(db.String(60), nullable=False)
    subscription_tier = db.Column(db.String(20), default='free')
    
    # Relationships
    predictions = db.relationship('Prediction', backref='author', lazy=True)
    payments = db.relationship('Payment', backref='payer', lazy=True)

    def check_password(self, password):
        from flask_bcrypt import Bcrypt
        bcrypt = Bcrypt()
        return bcrypt.check_password_hash(self.password_hash, password)

class Prediction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    match_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    pred_outcome = db.Column(db.String(20), nullable=False) # "Home Win", "Draw", "Away Win"
    
    # NEW FIELDS FOR RESULTS
    status = db.Column(db.String(20), default='Pending') # Pending, Won, Lost
    actual_score = db.Column(db.String(10), nullable=True) # e.g. "2-1"

class Payment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='KES')
    provider = db.Column(db.String(20), default='mpesa')
    status = db.Column(db.String(20), default='PENDING')
    transaction_id = db.Column(db.String(50), unique=True)
    timestamp = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)