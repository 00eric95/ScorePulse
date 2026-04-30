from datetime import datetime, timedelta
from app import db, login_manager
from flask import current_app
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import Index, MetaData, UniqueConstraint, ForeignKey, Text, JSON, Boolean, Integer, Float, String, DateTime, Table
import json
import jwt
from time import time


#db.metadata = MetaData()
#db.metadata.clear()

# Login manager user loader
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ============================================
# ASSOCIATION TABLES
# ============================================

# Association table for League-Team many-to-many relationship
league_memberships = db.Table('league_memberships',
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id'), primary_key=True),
    db.Column('league_id', db.Integer, db.ForeignKey('leagues.id'), primary_key=True),
    db.Column('joined_date', db.DateTime, default=datetime.utcnow),
    db.Column('is_active', db.Boolean, default=True),
    extend_existing=True
)

# Association table for Match-Venue (could be used for venue history)
match_venues = db.Table('match_venues',
    db.Column('match_id', db.Integer, db.ForeignKey('matches.id'), primary_key=True),
    db.Column('venue_id', db.Integer, db.ForeignKey('venues.id'), primary_key=True),
    db.Column('is_home_venue', db.Boolean, default=True),
    extend_existing=True
)

# Association table for User-Favorite Teams
user_favorite_teams = db.Table('user_favorite_teams',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('team_id', db.Integer, db.ForeignKey('teams.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    extend_existing=True
)

# Association table for User-Favorite Leagues
user_favorite_leagues = db.Table('user_favorite_leagues',
    db.Column('user_id', db.Integer, db.ForeignKey('users.id'), primary_key=True),
    db.Column('league_id', db.Integer, db.ForeignKey('leagues.id'), primary_key=True),
    db.Column('created_at', db.DateTime, default=datetime.utcnow),
    extend_existing=True
)


# ============================================
# USER MODELS
# ============================================

class User(db.Model, UserMixin):
    """User model with authentication and profile information"""
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False, index=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(128))
    
    # Profile information
    profile_pic = db.Column(db.String(500), nullable=True)
    bio = db.Column(db.Text, nullable=True)
    
    # Authentication & Status
    google_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    email_verified = db.Column(db.Boolean, default=False)  # Keep for compatibility
    is_verified = db.Column(db.Boolean, default=False)     # New field from routes
    is_active = db.Column(db.Boolean, default=True)
    last_login = db.Column(db.DateTime)
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)
    login_count = db.Column(db.Integer, default=0)
    
    # Verification fields (from routes)
    verification_code = db.Column(db.String(6), nullable=True)
    verification_code_expiry = db.Column(db.DateTime, nullable=True)
    verification_attempts = db.Column(db.Integer, default=0)
    
    # Admin field (from routes)
    is_admin = db.Column(db.Boolean, default=False)
    
    # OAuth field (from routes)
    is_oauth_user = db.Column(db.Boolean, default=False)
    
    # Subscription & Credits
    subscription_tier = db.Column(db.String(20), default='free')  # 'free', 'silver', 'gold', 'platinum'
    is_premium = db.Column(db.Boolean, default=False)
    premium_expiry = db.Column(db.DateTime, nullable=True)
    daily_prediction_limit = db.Column(db.Integer, default=3)
    predictions_today = db.Column(db.Integer, default=0)
    last_prediction_reset = db.Column(db.DateTime, default=datetime.utcnow)
    credits = db.Column(db.Integer, default=0)
    total_spent = db.Column(db.Float, default=0.0)
    
    # Telegram Integration
    telegram_id = db.Column(db.String(100), unique=True, nullable=True, index=True)
    telegram_username = db.Column(db.String(100), nullable=True, index=True)
    telegram_first_name = db.Column(db.String(100), nullable=True)
    telegram_last_name = db.Column(db.String(100), nullable=True)
    
    # Referral System
    referral_code = db.Column(db.String(20), unique=True, nullable=True)
    referred_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    referral_count = db.Column(db.Integer, default=0)
    referral_bonus = db.Column(db.Integer, default=0)
    
    # Newsletter preferences
    newsletter_subscribed = db.Column(db.Boolean, default=True)
    newsletter_frequency = db.Column(db.String(20), default='weekly')
    
    # Timestamps
    date_joined = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    predictions = db.relationship('Prediction', back_populates='user', lazy=True, cascade='all, delete-orphan')
    payments = db.relationship('Payment', back_populates='user', lazy=True, cascade='all, delete-orphan')
    activities = db.relationship('UserActivity', back_populates='user', lazy=True, cascade='all, delete-orphan')
    feedback = db.relationship('Feedback', back_populates='user', lazy=True, cascade='all, delete-orphan')
    notifications = db.relationship('Notification', back_populates='user', lazy=True, cascade='all, delete-orphan')
    custom_predictions = db.relationship('CustomPrediction', back_populates='user', lazy=True, cascade='all, delete-orphan')
    settings = db.relationship('UserSettings', back_populates='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    prediction_performance = db.relationship('PredictionPerformance', back_populates='user', lazy=True, cascade='all, delete-orphan')
    leaderboard_entry = db.relationship('Leaderboard', back_populates='user', uselist=False, lazy=True, cascade='all, delete-orphan')
    stored_predictions = db.relationship('StoredPrediction', back_populates='user', lazy=True, cascade='all, delete-orphan')
    orchestration_logs = db.relationship('OrchestrationLog', back_populates='user', lazy=True, cascade='all, delete-orphan')
    credit_transactions = db.relationship('CreditTransaction', back_populates='user', lazy=True, cascade='all, delete-orphan')
    chat_sessions = db.relationship('ChatSession', back_populates='user', lazy=True, cascade='all, delete-orphan')
    chat_messages = db.relationship('ChatMessage', back_populates='user', lazy=True, cascade='all, delete-orphan')
    
    # Many-to-many relationships
    favorite_teams = db.relationship('Team', secondary=user_favorite_teams, lazy='dynamic',
                                     back_populates='favorited_by')
    favorite_leagues = db.relationship('League', secondary=user_favorite_leagues, lazy='dynamic',
                                       back_populates='favorited_by')
    
    # Self-referential relationship for referrals
    referred_users = db.relationship('User', 
                                     backref=db.backref('referrer', remote_side=[id]),
                                     foreign_keys=[referred_by],
                                     lazy='dynamic')
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def set_password(self, password):
        """Create hashed password."""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Check hashed password."""
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)
    
    def get_reset_token(self, expires_sec=1800):
        """Generate password reset token"""
        return jwt.encode(
            {'user_id': self.id, 'exp': time() + expires_sec},
            current_app.config['SECRET_KEY'],
            algorithm='HS256'
        )
    
    @staticmethod
    def verify_reset_token(token):
        """Verify password reset token"""
        try:
            user_id = jwt.decode(
                token,
                current_app.config['SECRET_KEY'],
                algorithms=['HS256']
            )['user_id']
        except:
            return None
        return User.query.get(user_id)
    
    def can_make_prediction(self):
        """Check if user can make a prediction based on daily limits."""
        if self.last_prediction_reset.date() < datetime.utcnow().date():
            self.predictions_today = 0
            self.last_prediction_reset = datetime.utcnow()
            db.session.commit()
        return self.predictions_today < self.daily_prediction_limit
    
    def increment_prediction_count(self):
        """Increment the daily prediction counter."""
        if self.can_make_prediction():
            self.predictions_today += 1
            return True
        return False
    
    def get_subscription_details(self):
        """Get subscription tier details."""
        tiers = {
            'free': {
                'daily_limit': 3,
                'monthly_price': 0,
                'features': ['basic_predictions', 'basic_analysis']
            },
            'silver': {
                'daily_limit': 10,
                'monthly_price': 9.99,
                'features': ['basic_predictions', 'advanced_analysis', 'team_comparisons']
            },
            'gold': {
                'daily_limit': 50,
                'monthly_price': 29.99,
                'features': ['unlimited_predictions', 'ai_insights', 'risk_analysis', 'premium_support']
            },
            'platinum': {
                'daily_limit': 999,
                'monthly_price': 99.99,
                'features': ['unlimited_predictions', 'custom_models', 'api_access', 'priority_support']
            }
        }
        return tiers.get(self.subscription_tier, tiers['free'])
    
    # New methods from routes.py
    def generate_verification_code(self, length=6):
        """Generate a verification code"""
        import random
        import string
        code = ''.join(random.choices(string.digits, k=length))
        self.verification_code = code
        self.verification_code_expiry = datetime.utcnow() + timedelta(minutes=30)
        self.verification_attempts = 0
        db.session.commit()
        return code
    
    def verify_code(self, code):
        """Verify a verification code"""
        if self.verification_code_expiry and datetime.utcnow() > self.verification_code_expiry:
            return False
        
        if self.verification_code == code:
            self.is_verified = True
            self.verification_code = None
            self.verification_code_expiry = None
            db.session.commit()
            return True
        else:
            self.verification_attempts += 1
            db.session.commit()
            return False
    
    def can_resend_code(self):
        """Check if user can request a new verification code"""
        if not self.verification_code_expiry:
            return True
        
        # Allow resend after 2 minutes
        return datetime.utcnow() > self.verification_code_expiry - timedelta(minutes=28)
    
    def to_dict(self):
        """Convert user to dictionary for API responses."""
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'subscription_tier': self.subscription_tier,
            'date_joined': self.date_joined.isoformat() if self.date_joined else None,
            'profile_pic': self.profile_pic,
            'email_verified': self.email_verified,
            'is_verified': self.is_verified,  # Added from routes
            'last_login': self.last_login.isoformat() if self.last_login else None,
            'login_count': self.login_count,
            'telegram_id': self.telegram_id,
            'telegram_username': self.telegram_username,
            'credits': self.credits,
            'daily_predictions_used': self.predictions_today,
            'daily_predictions_left': self.daily_prediction_limit - self.predictions_today,
            'is_admin': self.is_admin  # Added from routes
        }


class UserActivity(db.Model):
    """Track user activities for analytics"""
    __tablename__ = 'user_activities'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    action = db.Column(db.String(50), nullable=False)  # login, logout, prediction, payment, etc.
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    user = db.relationship('User', back_populates='activities')
    
    # Index for frequently queried combinations
    __table_args__ = (
        Index('idx_user_action_time', 'user_id', 'action', 'timestamp'),
    )
    
    def to_dict(self):
        """Convert activity to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'action': self.action,
            'details': json.loads(self.details) if self.details else None,
            'ip_address': self.ip_address,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }


class UserSettings(db.Model):
    """User preferences and settings"""
    __tablename__ = 'user_settings'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    
    # Notification settings
    email_notifications = db.Column(db.Boolean, default=True)
    push_notifications = db.Column(db.Boolean, default=True)
    bet_alert_threshold = db.Column(db.Float, default=0.0)
    
    # UI/UX preferences
    theme = db.Column(db.Enum('light', 'dark', 'auto', name='theme_modes'), default='light')
    language = db.Column(db.String(10), default='en')
    
    # Prediction preferences
    prediction_preferences = db.Column(db.Text, default='{}')  # JSON of prediction preferences
    
    # Added from routes - favorite leagues
    favorite_leagues = db.Column(db.Text, default='[]')  # JSON list of favorite leagues
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='settings')
    
    def get_prediction_preferences(self):
        """Return prediction preferences as Python dict"""
        try:
            return json.loads(self.prediction_preferences)
        except:
            return {}
    
    def get_favorite_leagues(self):
        """Return favorite leagues as Python list"""
        try:
            return json.loads(self.favorite_leagues)
        except:
            return []


class CreditTransaction(db.Model):
    """Track credit transactions"""
    __tablename__ = 'credit_transactions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    amount = db.Column(db.Integer, nullable=False)
    balance_after = db.Column(db.Integer, nullable=False)
    transaction_type = db.Column(db.String(20))  # credit, debit, referral, bonus
    description = db.Column(db.String(200))
    reference_id = db.Column(db.String(100))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='credit_transactions')
    
    def to_dict(self):
        """Convert credit transaction to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'balance_after': self.balance_after,
            'transaction_type': self.transaction_type,
            'description': self.description,
            'reference_id': self.reference_id,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================
# TEAM AND LEAGUE MODELS
# ============================================

class TeamNameMapping(db.Model):
    """Map different team name variations to standard names"""
    __tablename__ = 'team_name_mappings'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    original_name = db.Column(db.String(100), nullable=False, index=True)  # Changed from standard_name
    standard_name = db.Column(db.String(100), nullable=False)  # Keep for backward compatibility
    alias = db.Column(db.String(100), nullable=True, unique=True, index=True)  # Made nullable
    source = db.Column(db.String(50), default='manual')  # 'manual', 'ai_detected', 'import'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<TeamNameMapping {self.original_name} -> {self.standard_name}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'original_name': self.original_name,
            'standard_name': self.standard_name,
            'alias': self.alias,
            'source': self.source
        }


class League(db.Model):
    """League/Competition model"""
    __tablename__ = 'leagues'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(50))
    tier = db.Column(db.Integer, default=1)  # 1 for Premier League, 2 for Championship
    type = db.Column(db.String(20))  # "Club" or "International"
    logo = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    seasons = db.relationship('Season', back_populates='league', lazy=True, cascade='all, delete-orphan')
    matches = db.relationship('Match', back_populates='league', lazy=True, cascade='all, delete-orphan')
    
    # Many-to-many relationships
    teams = db.relationship('Team', secondary=league_memberships, lazy='dynamic',
                            back_populates='leagues')
    favorited_by = db.relationship('User', secondary=user_favorite_leagues,
                                   back_populates='favorite_leagues')
    
    def __repr__(self):
        return f'<League {self.name}>'


class Season(db.Model):
    """Season model for leagues"""
    __tablename__ = 'seasons'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(20))  # e.g., "2025/26"
    start_date = db.Column(db.DateTime)
    end_date = db.Column(db.DateTime)
    is_current = db.Column(db.Boolean, default=True)
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'))
    
    # Relationships
    league = db.relationship('League', back_populates='seasons')
    matches = db.relationship('Match', back_populates='season', lazy=True)
    
    def __repr__(self):
        return f'<Season {self.name} - {self.league.name if self.league else "No League"}>'


class Team(db.Model):
    """Team model with tactical and statistical data"""
    __tablename__ = 'teams'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    short_name = db.Column(db.String(10))  # e.g., "MCI", "LIV"
    founded_year = db.Column(db.Integer)
    logo_path = db.Column(db.String(255))
    
    # Tactical Diversity (For Spider Map)
    attack_rating = db.Column(db.Float, default=50.0)  # Scoring potential
    defense_rating = db.Column(db.Float, default=50.0)  # Clean sheet probability
    possession_style = db.Column(db.Float, default=50.0)  # High = Tiki-taka, Low = Counter-attack
    discipline_index = db.Column(db.Float, default=50.0)  # Frequency of fouls/cards
    squad_depth = db.Column(db.Float, default=50.0)  # Quality of bench
    form_rating = db.Column(db.Float, default=50.0)
    corners_avg = db.Column(db.Float, default=50.0)
    win_rate = db.Column(db.Float, default=0.0)
    avg_goals_scored = db.Column(db.Float, default=0.0)
    avg_goals_conceded = db.Column(db.Float, default=0.0)
    elo_rating = db.Column(db.Float, default=1500.0)
    
    # Momentum
    recent_form_score = db.Column(db.Float, default=0.0)  # Weighted last 5 games
    home_advantage_multiplier = db.Column(db.Float, default=1.1)
    
    # Financial/Contextual
    market_value = db.Column(db.Float)  # Estimated squad value in millions
    stadium_id = db.Column(db.Integer, db.ForeignKey('venues.id'))
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    stadium = db.relationship('Venue', back_populates='home_teams')
    players = db.relationship('Player', back_populates='current_team', lazy='dynamic')
    home_matches = db.relationship('Match', foreign_keys='Match.home_team_id',
                                   back_populates='home_team', lazy='dynamic')
    away_matches = db.relationship('Match', foreign_keys='Match.away_team_id',
                                   back_populates='away_team', lazy='dynamic')
    team_stats = db.relationship('TeamStats', back_populates='team', uselist=False,
                                 lazy=True, cascade='all, delete-orphan')
    
    # Many-to-many relationships
    leagues = db.relationship('League', secondary=league_memberships, lazy='dynamic',
                              back_populates='teams')
    favorited_by = db.relationship('User', secondary=user_favorite_teams,
                                   back_populates='favorite_teams')
    
    def __repr__(self):
        return f'<Team {self.name}>'
    
    def get_power_index(self):
        """Calculates a single 'Strength' number for the Green/Orange bars."""
        return (self.attack_rating + self.defense_rating + self.recent_form_score) / 3
    
    @property
    def safe_attack_rating(self):
        return self.attack_rating if self.attack_rating is not None else 50.0
    
    @property
    def safe_defense_rating(self):
        return self.defense_rating if self.defense_rating is not None else 50.0
    
    def get_radar_data(self):
        """Returns a clean list for Chart.js even if columns are empty"""
        return [
            self.safe_attack_rating,
            self.safe_defense_rating,
            self.possession_style or 50.0,
            self.discipline_index or 50.0,
            self.squad_depth or 50.0
        ]


class Venue(db.Model):
    """Stadium/Venue model"""
    __tablename__ = 'venues'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    city = db.Column(db.String(50))
    country = db.Column(db.String(50))
    capacity = db.Column(db.Integer)
    surface_type = db.Column(db.String(20))  # grass, artificial, hybrid
    
    # Relationships
    home_teams = db.relationship('Team', back_populates='stadium', lazy='dynamic')
    matches = db.relationship('Match', secondary=match_venues, lazy='dynamic',
                              back_populates='venues')
    
    def __repr__(self):
        return f'<Venue {self.name}>'


class Player(db.Model):
    """Player model (basic structure - can be expanded)"""
    __tablename__ = 'players'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    position = db.Column(db.String(20))  # GK, DEF, MID, FWD
    nationality = db.Column(db.String(50))
    date_of_birth = db.Column(db.DateTime)
    jersey_number = db.Column(db.Integer)
    market_value = db.Column(db.Float)  # in millions
    
    # Foreign keys
    current_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'))
    
    # Relationships
    current_team = db.relationship('Team', back_populates='players')
    
    def __repr__(self):
        return f'<Player {self.name}>'


# ============================================
# MATCH MODELS
# ============================================

class Match(db.Model):
    """Football match model"""
    __tablename__ = 'matches'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    
    # Match details
    date = db.Column(db.String(20), index=True)  # Stored as string "YYYY-MM-DD"
    time = db.Column(db.String(20))
    matchday = db.Column(db.Integer)  # Match week number
    
    # Teams - Foreign keys to Team model
    home_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    away_team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), nullable=False)
    
    # Team name strings (from import)
    home = db.Column(db.String(100), nullable=True)  
    away = db.Column(db.String(100), nullable=True)
    
    # Scores - FIXED: Change from result to separate score columns
    home_score = db.Column(db.Integer, nullable=True)
    away_score = db.Column(db.Integer, nullable=True)
    
    # Status
    match_status = db.Column(db.String(20), default='scheduled')  # scheduled, ongoing, completed, cancelled
    
    # League information
    league_id = db.Column(db.Integer, db.ForeignKey('leagues.id'), nullable=False)
    league_name_str = db.Column(db.String(100), nullable=True)  # String representation of league
    
    # Season
    season_id = db.Column(db.Integer, db.ForeignKey('seasons.id'), nullable=True)
    
    # Additional info
    referee = db.Column(db.String(100), nullable=True)
    attendance = db.Column(db.Integer, nullable=True)
    
    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Betting odds
    home_odds = db.Column(db.Float, nullable=True)
    draw_odds = db.Column(db.Float, nullable=True)
    away_odds = db.Column(db.Float, nullable=True)
    
    # Original names from source
    source_original_home = db.Column(db.String(100), nullable=True)
    source_original_away = db.Column(db.String(100), nullable=True)
    
    # Relationships
    league = db.relationship('League', back_populates='matches')
    season = db.relationship('Season', back_populates='matches')
    home_team = db.relationship('Team', foreign_keys=[home_team_id], back_populates='home_matches')
    away_team = db.relationship('Team', foreign_keys=[away_team_id], back_populates='away_matches')
    prediction_record = db.relationship('StoredPrediction', back_populates='match',
                                        uselist=False, lazy=True, cascade='all, delete-orphan')
    venues = db.relationship('Venue', secondary=match_venues, lazy='dynamic',
                             back_populates='matches')
    
    # Indexes
    __table_args__ = (
        Index('idx_league_date', 'league_id', 'date'),
        Index('idx_home_away_date', 'home_team_id', 'away_team_id', 'date'),
        UniqueConstraint('home_team_id', 'away_team_id', 'date', name='uq_match_home_away_date'),
    )
    
    def __repr__(self):
        home_name = self.home_team.name if self.home_team else self.home
        away_name = self.away_team.name if self.away_team else self.away
        return f'<Match {home_name} vs {away_name} on {self.date}>'
    
    def to_dict(self):
        """Convert match to dictionary for API responses."""
        home_name = self.home_team.name if self.home_team else self.home
        away_name = self.away_team.name if self.away_team else self.away
        league_name = self.league.name if self.league else self.league_name_str
        
        return {
            'id': self.id,
            'date': self.date,
            'time': self.time,
            'league': league_name,
            'home_team_id': self.home_team_id,
            'away_team_id': self.away_team_id,
            'home_team_name': home_name,
            'away_team_name': away_name,
            'home': self.home,
            'away': self.away,
            'home_score': self.home_score,
            'away_score': self.away_score,
            'match_status': self.match_status,
            'home_odds': self.home_odds,
            'draw_odds': self.draw_odds,
            'away_odds': self.away_odds,
            'source_original_home': self.source_original_home,
            'source_original_away': self.source_original_away,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }
    
    def is_completed(self):
        """Check if match is completed."""
        return self.match_status == 'completed' and self.home_score is not None and self.away_score is not None
    
    def get_result(self):
        """Get match result as string."""
        if not self.is_completed():
            return None
        
        if self.home_score > self.away_score:
            return 'H'
        elif self.home_score < self.away_score:
            return 'A'
        else:
            return 'D'
    
    def get_home_team_name(self):
        """Get home team name, preferring Team model name if available."""
        return self.home_team.name if self.home_team else self.home
    
    def get_away_team_name(self):
        """Get away team name, preferring Team model name if available."""
        return self.away_team.name if self.away_team else self.away


class TeamStats(db.Model):
    """Model for caching team statistics"""
    __tablename__ = 'team_stats'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column(db.Integer, db.ForeignKey('teams.id'), unique=True, nullable=False)
    team_name = db.Column(db.String(100), nullable=False, index=True)  # Added from routes
    statistics = db.Column(db.Text)  # JSON string of team stats
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    matches_analyzed = db.Column(db.Integer, default=0)
    win_rate = db.Column(db.Float, default=0.0)
    avg_goals_scored = db.Column(db.Float, default=0.0)
    avg_goals_conceded = db.Column(db.Float, default=0.0)
    
    # Relationships
    team = db.relationship('Team', back_populates='team_stats')
    
    def get_statistics(self):
        """Return statistics as Python dict"""
        try:
            return json.loads(self.statistics)
        except:
            return {}
    
    def update_statistics(self, stats_dict):
        """Update statistics from Python dict"""
        self.statistics = json.dumps(stats_dict)
        self.last_updated = datetime.utcnow()


# ============================================
# PREDICTION MODELS
# ============================================

class Prediction(db.Model):
    """User prediction model"""
    __tablename__ = 'predictions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), nullable=True, index=True)
    outcome_date = db.Column(db.DateTime, nullable=True)
    
    # Match information
    match_date = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    
    # Prediction details
    pred_outcome = db.Column(db.String(10), nullable=False)  # 'H', 'D', 'A'
    status = db.Column(db.String(20), default='Pending')  # 'Pending', 'Won', 'Lost', 'Cancelled'
    actual_score = db.Column(db.String(20), nullable=True)
    pred_home_score = db.Column(db.Integer, nullable=True)  # Predicted home goals
    pred_away_score = db.Column(db.Integer, nullable=True)  # Predicted away goals
    btts_probability = db.Column(db.Float, nullable=True)   # Both teams to score %
    over25_probability = db.Column(db.Float, nullable=True) # Over 2.5 goals %
    total_goals_pred = db.Column(db.Float, nullable=True)   # Total goals prediction
    
    # AI prediction fields
    ai_prediction = db.Column(db.String(20), nullable=True)  # Store AI's prediction
    confidence = db.Column(db.Float, nullable=True)  # AI confidence score
    profit_loss = db.Column(db.Float, nullable=True)  # Store monetary profit/loss
    
    # Added from routes - user prediction field
    user_prediction = db.Column(db.String(10), nullable=True)  # User's choice if different from AI
    
    # Added from routes - model used
    model_used = db.Column(db.String(50), nullable=True, default='Random Forest')
    
    # Odds information
    odds = db.Column(db.Float, nullable=True)
    stake = db.Column(db.Float, nullable=True)  # If users want to track virtual stakes
    potential_payout = db.Column(db.Float, nullable=True)
    
    # Orchestrator Data
    mcmc_home_prob = db.Column(db.Float, nullable=True)
    mcmc_away_prob = db.Column(db.Float, nullable=True)
    mcmc_draw_prob = db.Column(db.Float, nullable=True)
    
    # Bankroll Agent Integration
    recommended_stake = db.Column(db.Float, nullable=True)  # Units to bet
    kelly_fraction = db.Column(db.Float, nullable=True)  # Kelly multiplier
    market_odds = db.Column(db.Float, nullable=True)  # Odds used for calculation
    
    # Analyst Agent Integration
    narrative_report = db.Column(db.Text, nullable=True)  # The AI-generated story
    risk_level = db.Column(db.String(20), nullable=True)  # LOW, MEDIUM, HIGH
    
    # Critic Agent Integration
    is_evaluated = db.Column(db.Boolean, default=False)
    prediction_error = db.Column(db.Float, nullable=True)  # Log-loss or Brier score
    
    # Additional tracking
    notes = db.Column(db.Text, nullable=True)  # User notes about the prediction
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='predictions')
    
    # Indexes for common queries
    __table_args__ = (
        Index('idx_user_status_date', 'user_id', 'status', 'match_date'),
        Index('idx_teams_date', 'home_team', 'away_team', 'match_date'),
    )
    
    def __repr__(self):
        return f'<Prediction {self.home_team} vs {self.away_team} by User {self.user_id}>'
    
    def to_dict(self):
        """Convert prediction to dictionary for API responses."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'match_date': self.match_date.isoformat() if self.match_date else None,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'pred_outcome': self.pred_outcome,
            'status': self.status,
            'actual_score': self.actual_score,
            'ai_prediction': self.ai_prediction,
            'user_prediction': self.user_prediction,
            'confidence': self.confidence,
            'odds': self.odds,
            'stake': self.stake,
            'potential_payout': self.potential_payout,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'notes': self.notes,
            'mcmc_home_prob': self.mcmc_home_prob,
            'mcmc_draw_prob': self.mcmc_draw_prob,
            'mcmc_away_prob': self.mcmc_away_prob,
            'recommended_stake': self.recommended_stake,
            'kelly_fraction': self.kelly_fraction,
            'market_odds': self.market_odds,
            'narrative_report': self.narrative_report,
            'risk_level': self.risk_level,
            'is_evaluated': self.is_evaluated,
            'prediction_error': self.prediction_error,
            'model_used': self.model_used
        }
    
    def get_outcome_text(self):
        """Convert outcome code to text."""
        outcomes = {
            'H': 'Home Win',
            'D': 'Draw',
            'A': 'Away Win'
        }
        return outcomes.get(self.pred_outcome, self.pred_outcome)
    
    def update_status(self, home_score, away_score):
        """Update prediction status based on actual score."""
        if home_score is None or away_score is None:
            return False
        
        self.actual_score = f"{home_score}-{away_score}"
        
        # Determine actual outcome
        if home_score > away_score:
            actual_outcome = 'H'
        elif home_score < away_score:
            actual_outcome = 'A'
        else:
            actual_outcome = 'D'
        
        # Update status
        if self.pred_outcome == actual_outcome:
            self.status = 'Won'
        else:
            self.status = 'Lost'
        
        return True
    
    @property
    def predicted_score(self):
        return f"{self.pred_home_score or 0}-{self.pred_away_score or 0}"


class StoredPrediction(db.Model):
    """Store predictions for later comparison with actual results"""
    __tablename__ = 'stored_predictions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey('matches.id'), unique=True, nullable=False, index=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    match_date = db.Column(db.DateTime, nullable=False, index=True)
    predicted_data = db.Column(db.Text)  # JSON string of prediction data
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    match = db.relationship('Match', back_populates='prediction_record')
    user = db.relationship('User', back_populates='stored_predictions')
    
    def get_predicted_data(self):
        """Return predicted data as Python dict"""
        try:
            return json.loads(self.predicted_data)
        except:
            return {}
    
    def set_predicted_data(self, data_dict):
        """Set predicted data from Python dict"""
        self.predicted_data = json.dumps(data_dict)
    
    def to_dict(self):
        """Convert stored prediction to dictionary."""
        return {
            'id': self.id,
            'match_id': self.match_id,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'match_date': self.match_date.isoformat() if self.match_date else None,
            'predicted_data': self.get_predicted_data(),
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class CustomPrediction(db.Model):
    """Model for storing advanced/custom predictions"""
    __tablename__ = 'custom_predictions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)
    parameters = db.Column(db.Text)  # JSON string of custom parameters
    prediction_result = db.Column(db.Text)  # JSON string of prediction result
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='custom_predictions')
    
    def get_parameters(self):
        """Return parameters as Python dict"""
        try:
            return json.loads(self.parameters)
        except:
            return {}
    
    def get_prediction_result(self):
        """Return prediction result as Python dict"""
        try:
            return json.loads(self.prediction_result)
        except:
            return {}


class PredictionPerformance(db.Model):
    """Store detailed performance data for each settled prediction (one row per prediction)."""
    __tablename__ = 'prediction_performances'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)

    # Link to original prediction (optional but recommended)
    prediction_id = db.Column(db.Integer, db.ForeignKey('predictions.id'), unique=True, nullable=False, index=True)

    # User (denormalized for faster queries)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)

    # Match information
    match_date = db.Column(db.DateTime, nullable=False, index=True)
    home_team = db.Column(db.String(100), nullable=False)
    away_team = db.Column(db.String(100), nullable=False)

    # Prediction outcome details
    predicted_outcome = db.Column(db.String(10), nullable=False)   # 'H', 'D', 'A'
    actual_outcome = db.Column(db.String(10), nullable=False)     # 'H', 'D', 'A'
    is_correct = db.Column(db.Boolean, nullable=False)

    # Performance metrics
    confidence_score = db.Column(db.Float, nullable=True)
    profit_loss = db.Column(db.Float, nullable=True)
    odds_used = db.Column(db.Float, nullable=True)
    stake = db.Column(db.Float, nullable=True)

    # Model that generated the prediction
    model_used = db.Column(db.String(100), nullable=True)

    # Optional notes
    notes = db.Column(db.Text, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    prediction = db.relationship('Prediction', backref=db.backref('performance_record', uselist=False))
    user = db.relationship('User', backref='prediction_performances')

    __table_args__ = (
        db.Index('idx_user_date', 'user_id', 'match_date'),
        db.Index('idx_user_model', 'user_id', 'model_used'),
        db.Index('idx_match_date', 'match_date'),
        db.UniqueConstraint('prediction_id', name='uq_prediction_performance'),
    )

    def to_dict(self):
        return {
            'id': self.id,
            'prediction_id': self.prediction_id,
            'user_id': self.user_id,
            'match_date': self.match_date.isoformat() if self.match_date else None,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'predicted_outcome': self.predicted_outcome,
            'actual_outcome': self.actual_outcome,
            'is_correct': self.is_correct,
            'confidence_score': self.confidence_score,
            'profit_loss': self.profit_loss,
            'odds_used': self.odds_used,
            'stake': self.stake,
            'model_used': self.model_used,
            'notes': self.notes,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }
# ============================================
# PAYMENT AND SUBSCRIPTION MODELS
# ============================================

class Payment(db.Model):
    """Payment transaction model"""
    __tablename__ = 'payments'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, index=True)
    amount = db.Column(db.Float, nullable=False)
    currency = db.Column(db.String(10), default='KES')
    provider = db.Column(db.String(20), default='mpesa')
    transaction_id = db.Column(db.String(50), unique=True, index=True)
    status = db.Column(db.String(20), default='PENDING')  # PENDING, COMPLETED, FAILED, CANCELLED
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    
    # Additional payment details
    payment_method = db.Column(db.String(50), nullable=True)
    description = db.Column(db.String(200), nullable=True)
    receipt_url = db.Column(db.String(500), nullable=True)
    
    # For subscription payments
    subscription_period = db.Column(db.String(20), nullable=True)  # monthly, yearly
    valid_until = db.Column(db.DateTime, nullable=True)
    
    # Credits purchased
    credits_purchased = db.Column(db.Integer, default=0)
    
    # Relationships
    user = db.relationship('User', back_populates='payments')
    
    def to_dict(self):
        """Convert payment to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'amount': self.amount,
            'currency': self.currency,
            'provider': self.provider,
            'transaction_id': self.transaction_id,
            'status': self.status,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'description': self.description,
            'valid_until': self.valid_until.isoformat() if self.valid_until else None,
            'credits_purchased': self.credits_purchased
        }


class Coupon(db.Model):
    """Store coupon codes"""
    __tablename__ = 'coupons'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(20), unique=True, nullable=False, index=True)
    discount_type = db.Column(db.String(20))  # percentage, fixed, credits
    discount_value = db.Column(db.Float)
    credits_awarded = db.Column(db.Integer, default=0)
    upgrade_tier = db.Column(db.String(20), nullable=True)
    expiry_date = db.Column(db.DateTime, nullable=True)
    max_uses = db.Column(db.Integer, default=0)
    uses_count = db.Column(db.Integer, default=0)
    description = db.Column(db.String(200))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def is_valid(self):
        """Check if coupon is still valid."""
        if not self.is_active:
            return False
        if self.max_uses > 0 and self.uses_count >= self.max_uses:
            return False
        if self.expiry_date and datetime.utcnow() > self.expiry_date:
            return False
        return True
    
    def apply_discount(self, amount):
        """Apply discount to amount."""
        if not self.is_valid():
            return amount
        
        if self.discount_type == 'percentage':
            discount = amount * (self.discount_value / 100)
            return amount - discount
        elif self.discount_type == 'fixed':
            return amount - self.discount_value
        else:
            return amount
    
    def to_dict(self):
        """Convert coupon to dictionary."""
        return {
            'id': self.id,
            'code': self.code,
            'discount_type': self.discount_type,
            'discount_value': self.discount_value,
            'credits_awarded': self.credits_awarded,
            'upgrade_tier': self.upgrade_tier,
            'expiry_date': self.expiry_date.isoformat() if self.expiry_date else None,
            'max_uses': self.max_uses,
            'uses_count': self.uses_count,
            'description': self.description,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


# ============================================
# ANALYTICS AND FEEDBACK MODELS
# ============================================

class Feedback(db.Model):
    """Model for user feedback and bug reports"""
    __tablename__ = 'feedbacks'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    feedback_type = db.Column(db.Enum('bug', 'feature', 'general', name='feedback_types'), nullable=False)
    subject = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    priority = db.Column(db.Enum('low', 'medium', 'high', name='priority_levels'), default='medium')
    status = db.Column(db.Enum('new', 'reviewed', 'in_progress', 'resolved', name='feedback_status'), default='new')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='feedback')
    
    def to_dict(self):
        """Convert feedback to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'feedback_type': self.feedback_type,
            'subject': self.subject,
            'message': self.message,
            'priority': self.priority,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class Leaderboard(db.Model):
    """Model for user leaderboard rankings"""
    __tablename__ = 'leaderboards'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True, nullable=False)
    username = db.Column(db.String(64), nullable=False)
    rank = db.Column(db.Integer)
    total_predictions = db.Column(db.Integer, default=0)
    wins = db.Column(db.Integer, default=0)
    losses = db.Column(db.Integer, default=0)
    accuracy = db.Column(db.Float, default=0.0)
    profit = db.Column(db.Float, default=0.0)
    streak = db.Column(db.Integer, default=0)
    last_updated = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='leaderboard_entry')
    
    def __repr__(self):
        return f'<Leaderboard {self.username}: {self.accuracy}%>'
    
    def update_stats(self, user_predictions):
        """Update leaderboard stats based on user predictions."""
        total = len(user_predictions)
        if total == 0:
            return
        
        wins = sum(1 for p in user_predictions if p.status == 'Won')
        losses = sum(1 for p in user_predictions if p.status == 'Lost')
        
        self.total_predictions = total
        self.wins = wins
        self.losses = losses
        self.accuracy = (wins / total * 100) if total > 0 else 0
        
        # Calculate profit (simplified)
        self.profit = sum(p.profit_loss or 0 for p in user_predictions if p.profit_loss)
        
        self.last_updated = datetime.utcnow()


class Notification(db.Model):
    """Model for user notifications"""
    __tablename__ = 'notifications'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    message = db.Column(db.Text, nullable=False)
    notification_type = db.Column(db.Enum('info', 'success', 'warning', 'danger', name='notification_types'), default='info')
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    read_at = db.Column(db.DateTime, nullable=True)
    
    # Relationships
    user = db.relationship('User', back_populates='notifications')
    
    def mark_as_read(self):
        self.is_read = True
        self.read_at = datetime.utcnow()
    
    def to_dict(self):
        """Convert notification to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'title': self.title,
            'message': self.message,
            'notification_type': self.notification_type,
            'is_read': self.is_read,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'read_at': self.read_at.isoformat() if self.read_at else None
        }


# ============================================
# ORCHESTRATION AND AI MODELS
# ============================================

class OrchestrationLog(db.Model):
    """Log for orchestration pipeline runs"""
    __tablename__ = 'orchestration_logs'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.String(100))
    match = db.Column(db.String(255), nullable=False)
    home_team = db.Column(db.String(100))
    away_team = db.Column(db.String(100))
    session_id = db.Column(db.String(100))
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    status = db.Column(db.String(20), default='pending')  # success, failed, partial
    execution_time = db.Column(db.Float, default=0.0)  # seconds
    data_agent_result = db.Column(JSON)  # Store data agent output
    prediction_result = db.Column(JSON)  # Store prediction output
    bankroll_result = db.Column(JSON)  # Store bankroll output
    analysis_result = db.Column(JSON)  # Store analysis output
    critic_result = db.Column(JSON)  # Store critic output
    full_context = db.Column(JSON)  # Store full orchestration context
    
    # Relationships
    user = db.relationship('User', back_populates='orchestration_logs')
    
    def __repr__(self):
        return f'<OrchestrationLog {self.match}>'
    
    def to_dict(self):
        """Convert orchestration log to dictionary."""
        return {
            'id': self.id,
            'match_id': self.match_id,
            'home_team': self.home_team,
            'away_team': self.away_team,
            'session_id': self.session_id,
            'user_id': self.user_id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'status': self.status,
            'execution_time': self.execution_time,
            'data_agent_result': self.data_agent_result,
            'prediction_result': self.prediction_result,
            'bankroll_result': self.bankroll_result,
            'analysis_result': self.analysis_result,
            'critic_result': self.critic_result
        }


class OrchestrationSession(db.Model):
    """Track orchestration sessions"""
    __tablename__ = 'orchestration_sessions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.String(100), primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    active = db.Column(db.Boolean, default=True)
    total_predictions = db.Column(db.Integer, default=0)
    total_success = db.Column(db.Integer, default=0)
    total_failed = db.Column(db.Integer, default=0)
    average_execution_time = db.Column(db.Float, default=0.0)
    
    # Relationships
    user = db.relationship('User', backref='orchestration_sessions')
    
    def to_dict(self):
        """Convert orchestration session to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'active': self.active,
            'total_predictions': self.total_predictions,
            'total_success': self.total_success,
            'total_failed': self.total_failed,
            'average_execution_time': self.average_execution_time
        }


class AgentPerformance(db.Model):
    """Track performance metrics for each agent"""
    __tablename__ = 'agent_performances'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(50))  # data_agent, analyst_agent, etc.
    operation = db.Column(db.String(50))  # get_team_stats, generate_insight, etc.
    execution_time = db.Column(db.Float)
    success = db.Column(db.Boolean)
    error_message = db.Column(db.Text)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    session_id = db.Column(db.String(100))
    
    def to_dict(self):
        """Convert agent performance to dictionary."""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'operation': self.operation,
            'execution_time': self.execution_time,
            'success': self.success,
            'error_message': self.error_message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'session_id': self.session_id
        }


class DataAgentState(db.Model):
    """Track the state of the data agent for persistence"""
    __tablename__ = 'data_agent_states'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    agent_name = db.Column(db.String(100), nullable=False, index=True)
    last_data_load = db.Column(db.DateTime)
    total_matches_loaded = db.Column(db.Integer, default=0)
    total_features_generated = db.Column(db.Integer, default=0)
    data_quality_score = db.Column(db.Float, default=0.0)
    agent_metadata = db.Column(JSON)  # Store agent metadata
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<DataAgentState {self.agent_name}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'agent_name': self.agent_name,
            'last_data_load': self.last_data_load.isoformat() if self.last_data_load else None,
            'total_matches_loaded': self.total_matches_loaded,
            'total_features_generated': self.total_features_generated,
            'data_quality_score': self.data_quality_score,
            'agent_metadata': self.agent_metadata,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }


class ModelEvaluation(db.Model):
    """Model for tracking model evaluation metrics"""
    __tablename__ = 'model_evaluations'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False, index=True)
    evaluation_date = db.Column(db.DateTime, default=datetime.utcnow)
    dataset_type = db.Column(db.String(50), default='validation')  # 'validation', 'test', 'production'
    metrics = db.Column(JSON)  # Store all evaluation metrics as JSON
    
    # Model performance metrics
    accuracy = db.Column(db.Float, default=0.0)
    precision = db.Column(db.Float, default=0.0)
    recall = db.Column(db.Float, default=0.0)
    f1_score = db.Column(db.Float, default=0.0)
    log_loss = db.Column(db.Float, default=0.0)
    roc_auc = db.Column(db.Float, default=0.0)
    
    # Additional metadata
    sample_size = db.Column(db.Integer, default=0)
    training_time = db.Column(db.Float, default=0.0)  # seconds
    inference_time = db.Column(db.Float, default=0.0)  # seconds per sample
    
    # Model configuration
    model_config = db.Column(JSON)  # Store model hyperparameters
    feature_list = db.Column(JSON)  # Store list of features used
    
    # Status
    status = db.Column(db.String(20), default='completed')  # 'pending', 'running', 'completed', 'failed'
    notes = db.Column(db.Text, nullable=True)
    
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f'<ModelEvaluation {self.model_name} - {self.evaluation_date}>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'model_name': self.model_name,
            'evaluation_date': self.evaluation_date.isoformat() if self.evaluation_date else None,
            'dataset_type': self.dataset_type,
            'metrics': self.metrics,
            'accuracy': self.accuracy,
            'precision': self.precision,
            'recall': self.recall,
            'f1_score': self.f1_score,
            'log_loss': self.log_loss,
            'roc_auc': self.roc_auc,
            'sample_size': self.sample_size,
            'status': self.status,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

class ModelLiveStats(db.Model):
    """Track live performance statistics for each prediction model."""
    __tablename__ = 'model_live_stats'
    __table_args__ = {'extend_existing': True}

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(100), nullable=False, index=True)

    # Rolling window configuration
    window_days = db.Column(db.Integer, default=30)  # e.g., last 30 days

    # Cumulative counters (since last reset)
    total_predictions = db.Column(db.Integer, default=0)
    correct_predictions = db.Column(db.Integer, default=0)
    total_profit = db.Column(db.Float, default=0.0)
    total_confidence = db.Column(db.Float, default=0.0)

    # Derived fields (updated automatically)
    accuracy = db.Column(db.Float, default=0.0)
    avg_confidence = db.Column(db.Float, default=0.0)

    # Timestamps
    last_updated = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def update_derived(self):
        """Recalculate accuracy and average confidence from counters."""
        if self.total_predictions > 0:
            self.accuracy = (self.correct_predictions / self.total_predictions) * 100
            self.avg_confidence = self.total_confidence / self.total_predictions
        else:
            self.accuracy = 0.0
            self.avg_confidence = 0.0

    @classmethod
    def record_prediction(cls, model_name, is_correct, confidence, profit_loss):
        """Record a single prediction outcome for a model (upsert)."""
        stats = cls.query.filter_by(model_name=model_name).first()
        if not stats:
            stats = cls(model_name=model_name)
            db.session.add(stats)

        stats.total_predictions += 1
        if is_correct:
            stats.correct_predictions += 1
        stats.total_profit += profit_loss or 0.0
        stats.total_confidence += confidence or 0.0

        stats.update_derived()
        stats.last_updated = datetime.utcnow()
        db.session.commit()

class LearningReport(db.Model):
    """Store learning system reports"""
    __tablename__ = 'learning_reports'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    report_type = db.Column(db.String(20))  # daily, weekly, monthly
    period_start = db.Column(db.DateTime)
    period_end = db.Column(db.DateTime)
    total_predictions = db.Column(db.Integer)
    correct_predictions = db.Column(db.Integer)
    accuracy = db.Column(db.Float)
    total_profit = db.Column(db.Float)
    roi = db.Column(db.Float)
    insights = db.Column(db.Text)  # JSON string
    recommendations = db.Column(db.Text)  # JSON string
    learning_metrics = db.Column(JSON)  # Store learning system metrics
    prediction_performance = db.Column(JSON)  # Store detailed performance data
    key_insights = db.Column(JSON)  # Parsed insights
    file_path = db.Column(db.String(500))
    generated = db.Column(db.DateTime, default=datetime.utcnow)
    
    def to_dict(self):
        """Convert learning report to dictionary."""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'report_type': self.report_type,
            'period_start': self.period_start.isoformat() if self.period_start else None,
            'period_end': self.period_end.isoformat() if self.period_end else None,
            'total_predictions': self.total_predictions,
            'correct_predictions': self.correct_predictions,
            'accuracy': self.accuracy,
            'total_profit': self.total_profit,
            'roi': self.roi,
            'insights': self.insights,
            'recommendations': self.recommendations,
            'learning_metrics': self.learning_metrics,
            'prediction_performance': self.prediction_performance,
            'key_insights': self.key_insights,
            'file_path': self.file_path,
            'generated': self.generated.isoformat() if self.generated else None
        }


# ============================================
# DATA AND CACHE MODELS
# ============================================

class DataValidationLog(db.Model):
    """Log data validation results"""
    __tablename__ = 'data_validation_logs'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    source_name = db.Column(db.String(200))
    total_rows = db.Column(db.Integer)
    valid = db.Column(db.Boolean, default=False)
    issues = db.Column(JSON)  # Store list of issues
    warnings = db.Column(JSON)  # Store list of warnings
    statistics = db.Column(JSON)  # Store statistics
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<DataValidationLog {self.source_name}: {self.total_rows} rows>'
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'source_name': self.source_name,
            'total_rows': self.total_rows,
            'valid': self.valid,
            'issues': self.issues,
            'warnings': self.warnings,
            'statistics': self.statistics,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class FeatureCache(db.Model):
    """Cache for computed features to improve performance"""
    __tablename__ = 'feature_cache'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    cache_key = db.Column(db.String(255), unique=True, nullable=False, index=True)
    data = db.Column(JSON)  # Store cached data
    expiry = db.Column(db.DateTime, nullable=False, index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_accessed = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<FeatureCache {self.cache_key[:50]}>'
    
    def is_valid(self):
        """Check if cache entry is still valid."""
        return datetime.utcnow() < self.expiry
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'cache_key': self.cache_key,
            'data': self.data,
            'expiry': self.expiry.isoformat() if self.expiry else None,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None
        }


class SystemLog(db.Model):
    """System logging for monitoring and debugging"""
    __tablename__ = 'system_logs'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    level = db.Column(db.String(20))
    module = db.Column(db.String(50))
    log_type = db.Column(db.String(50))  # metrics, error, info, warning
    message = db.Column(db.Text)
    data = db.Column(db.Text)  # JSON as text
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<SystemLog {self.log_type}>'


# ============================================
# CHAT AND COMMUNICATION MODELS
# ============================================

class ChatSession(db.Model):
    """Chat session model"""
    __tablename__ = 'chat_sessions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    session_id = db.Column(db.String(100), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', back_populates='chat_sessions')
    messages = db.relationship('ChatMessage', back_populates='session', lazy=True, cascade='all, delete-orphan')


class ChatMessage(db.Model):
    """Chat message model"""
    __tablename__ = 'chat_messages'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('chat_sessions.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'bot'
    content = db.Column(db.Text, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    session = db.relationship('ChatSession', back_populates='messages')
    user = db.relationship('User', back_populates='chat_messages')


# ============================================
# NEWSLETTER MODELS
# ============================================

class NewsletterSubscription(db.Model):
    """Store newsletter subscriptions"""
    __tablename__ = 'newsletter_subscriptions'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    frequency = db.Column(db.String(20), default='weekly')
    interests = db.Column(db.Text, default='all')
    subscribed_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_sent = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    
    def to_dict(self):
        """Convert newsletter subscription to dictionary."""
        return {
            'id': self.id,
            'email': self.email,
            'frequency': self.frequency,
            'interests': json.loads(self.interests) if self.interests else [],
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'last_sent': self.last_sent.isoformat() if self.last_sent else None,
            'is_active': self.is_active
        }
        
class PendingRegistration(db.Model):
    """Temporary storage for unverified registrations"""
    __tablename__ = 'pending_registrations'
    __table_args__ = {'extend_existing': True}  
    
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    username = db.Column(db.String(80), nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    verification_code = db.Column(db.String(6), nullable=False)
    verification_code_expiry = db.Column(db.DateTime, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.Text)
    
    def is_expired(self):
        return datetime.utcnow() > self.verification_code_expiry
    
    def to_user(self):
        """Convert to User object"""
        user = User(
            email=self.email,
            username=self.username,
            password_hash=self.password_hash,
            is_verified=True,  # Will be set after verification
            created_at=datetime.utcnow()
        )
        return user

