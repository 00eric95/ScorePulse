import sys
import os
import threading
import json
import time
import pandas as pd
from datetime import datetime
from flask import render_template, url_for, flash, redirect, request, jsonify, current_app as app
from app import db, login_manager
from app.forms import RegistrationForm, LoginForm, PredictForm
from app.models import User, Prediction, Payment
from flask_login import login_user, current_user, logout_user, login_required
from flask_bcrypt import Bcrypt

# ==========================================
# 1. CONNECT TO ML ENGINE (Robust Pathing)
# ==========================================
current_file_path = os.path.abspath(__file__)
project_root = os.path.dirname(os.path.dirname(os.path.dirname(current_file_path)))

if project_root not in sys.path:
    sys.path.insert(0, project_root)

print(f"🔍 Linking ML Engine from: {project_root}")

# Import Brain
ai_engine = None
try:
    import main
    ai_engine = main.MatchPredictor()
    print("✅ SCORE_PULSE Engine Online.")
except ImportError as e:
    print(f"❌ Failed to import 'main': {e}")
except Exception as e:
    print(f"⚠️ SCORE_PULSE Engine Error: {e}")

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

# ==========================================
# 2. STANDARD ROUTES (Home, Auth)
# ==========================================

@app.route("/")
@app.route("/home")
def home():
    # Fetch upcoming matches for the homepage ticker
    upcoming = []
    if ai_engine and hasattr(ai_engine, 'get_upcoming_matches'):
        try:
            upcoming = ai_engine.get_upcoming_matches(count=20)
        except: pass
    return render_template('home.html', matches=upcoming)

@app.route("/register", methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = RegistrationForm()
    if form.validate_on_submit():
        bcrypt = Bcrypt()
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        
        # Check if this is the first user (Auto-Admin)
        is_first_user = User.query.first() is None
        tier = 'gold' if is_first_user else 'free'
        
        user = User(username=form.username.data, email=form.email.data, password_hash=hashed_password, subscription_tier=tier)
        db.session.add(user)
        db.session.commit()
        
        msg = 'Account created! Please log in.'
        if is_first_user: msg += ' (Admin Access Granted)'
        
        flash(msg, 'success')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route("/login", methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember.data)
            return redirect(url_for('home'))
        else:
            flash('Login Failed. Check email and password.', 'danger')
    return render_template('login.html', title='Login', form=form)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('home'))

# ==========================================
# 3. PREDICTION & API ROUTES
# ==========================================

@app.route("/api/team_stats/<team_name>")
def get_team_stats(team_name):
    """Called by JS to show the 'Team Report Card' before predicting."""
    if not ai_engine: return jsonify({"error": "Engine Offline"}), 500
    try:
        if hasattr(ai_engine, 'get_team_report_card'):
            report = ai_engine.get_team_report_card(team_name)
            if report: return jsonify(report)
        return jsonify({"error": "Team not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route("/predict", methods=['GET', 'POST'])
@login_required
def predict():
    form = PredictForm()
    hierarchy = {}
    if ai_engine: hierarchy = ai_engine.get_team_hierarchy()
    
    # Autofill variables
    default_home = None
    default_away = None

    # --- A. ONE-CLICK FLOW (GET Request) ---
    if request.method == 'GET':
        q_home = request.args.get('home_team')
        q_away = request.args.get('away_team')
        
        if q_home and q_away:
            default_home = q_home
            default_away = q_away
            
            if ai_engine:
                tier = 'gold' if current_user.id == 1 else current_user.subscription_tier
                res = ai_engine.predict_for_web(q_home, q_away, tier)
                
                if "error" not in res:
                    return render_template('results.html', result=res)
                else:
                    flash(f"Auto-analysis failed: {res['error']}", 'warning')

    # --- B. MANUAL FORM FLOW (POST Request) ---
    if request.method == 'POST':
        home = request.form.get('home_team')
        away = request.form.get('away_team')
        pick = request.form.get('user_prediction')
        
        if ai_engine and home and away:
            tier = 'gold' if current_user.id == 1 else current_user.subscription_tier
            res = ai_engine.predict_for_web(home, away, tier)
            
            if "error" not in res:
                # Save History
                if pick and pick != 'None':
                    db.session.add(Prediction(
                        user_id=current_user.id, match_date=datetime.now(),
                        home_team=home, away_team=away, pred_outcome=pick
                    ))
                    db.session.commit()
                return render_template('results.html', result=res)
            else:
                flash(f"Error: {res['error']}", 'danger')
        else:
            if not ai_engine: flash("AI Engine Offline", 'danger')

    return render_template('predict.html', title='Predict', form=form, hierarchy=hierarchy, 
                           default_home=default_home, default_away=default_away)

# ==========================================
# 4. USER PROFILE & PAYMENTS
# ==========================================

@app.route("/profile")
@login_required
def profile():
    transactions = Payment.query.filter_by(user_id=current_user.id).order_by(Payment.timestamp.desc()).all()
    predictions = Prediction.query.filter_by(user_id=current_user.id).order_by(Prediction.match_date.desc()).all()
    
    # Calculate Stats
    total = len(predictions)
    wins = sum(1 for p in predictions if p.status == 'Won')
    losses = sum(1 for p in predictions if p.status == 'Lost')
    pending = sum(1 for p in predictions if p.status == 'Pending')
    accuracy = round((wins / (wins + losses)) * 100, 1) if (wins + losses) > 0 else 0

    return render_template('profile.html', 
                           title='Profile', 
                           user=current_user, 
                           transactions=transactions,
                           stats={'total': total, 'wins': wins, 'losses': losses, 'pending': pending, 'accuracy': accuracy})

@app.route("/pricing")
def pricing():
    return render_template('pricing.html', title='Pricing')

@app.route("/mpesa/stkpush", methods=['POST'])
@login_required
def mpesa_stkpush():
    phone = request.form.get('phone_number')
    amount = request.form.get('amount')
    if not phone or not amount: return jsonify({"error": "Missing info"}), 400
    
    db.session.add(Payment(
        user_id=current_user.id, amount=float(amount), currency='KES',
        provider='mpesa', status='PENDING', transaction_id=f"WS_{datetime.now().strftime('%H%M%S')}"
    ))
    db.session.commit()
    return jsonify({"message": "Success", "detail": "Check phone for PIN."})

# ==========================================
# 5. ADMIN DASHBOARD & TASKS
# ==========================================

@app.route("/admin")
@login_required
def admin_dashboard():
    if current_user.id != 1: 
        flash("Access Denied", 'danger')
        return redirect(url_for('home'))
        
    stats = {
        "total_users": User.query.count(),
        "total_revenue": db.session.query(db.func.sum(Payment.amount)).filter(Payment.status=='COMPLETED').scalar() or 0
    }
    
    # Check Schedule Age (Alert System)
    alert = False
    age = 0
    csv_path = os.path.join(project_root, 'data', 'upcoming.csv')
    if os.path.exists(csv_path):
        age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(csv_path))).days
        if age > 7: alert = True
    else: alert = True; age = 999

    # Load System Health
    health = {"status": "UNKNOWN", "active_alerts": []}
    try:
        with open(os.path.join(project_root, 'logs', 'system_status.json'), 'r') as f: health = json.load(f)
    except: pass
            
    return render_template('admin.html', title='Admin', stats=stats, health=health, schedule_alert=alert, schedule_age=age)

# --- BACKGROUND TASKS ---

@app.route("/admin/run_retrain", methods=['POST'])
@login_required
def run_retrain():
    if current_user.id != 1: return jsonify({"error": "Forbidden"}), 403
    def task():
        if project_root not in sys.path: sys.path.insert(0, project_root)
        from updating.model_retraining import ModelRetrainer
        ModelRetrainer().run_update_cycle(force=True)
    thread = threading.Thread(target=task)
    thread.start()
    return jsonify({"status": "started"})

@app.route("/admin/run_roi", methods=['POST'])
@login_required
def run_roi():
    if current_user.id != 1: return jsonify({"error": "Forbidden"}), 403
    def task():
        if project_root not in sys.path: sys.path.insert(0, project_root)
        from analysis.roi_simulator import ROISimulator
        ROISimulator().run_simulation()
    thread = threading.Thread(target=task)
    thread.start()
    return jsonify({"status": "started"})

@app.route("/admin/update_results", methods=['POST'])
@login_required
def update_results():
    if current_user.id != 1: return redirect(url_for('home'))
    
    csv_path = os.path.join(project_root, 'data', 'real_results.csv')
    if not os.path.exists(csv_path):
        flash('real_results.csv not found!', 'danger')
        return redirect(url_for('admin_dashboard'))

    try:
        df = pd.read_csv(csv_path)
        count = 0
        pending = Prediction.query.filter_by(status='Pending').all()
        
        for pred in pending:
            match = df[(df['HomeTeam'] == pred.home_team) & (df['AwayTeam'] == pred.away_team)]
            if not match.empty:
                row = match.iloc[0]
                hg = int(row['FTHG'])
                ag = int(row['FTAG'])
                actual = "Home Win" if hg > ag else "Away Win" if ag > hg else "Draw"
                
                pred.status = 'Won' if pred.pred_outcome == actual else 'Lost'
                pred.actual_score = f"{hg}-{ag}"
                count += 1
        
        db.session.commit()
        flash(f'Graded {count} predictions.', 'success')
    except Exception as e:
        flash(f'Error: {str(e)}', 'danger')

    return redirect(url_for('admin_dashboard'))

@app.route("/admin/force_update", methods=['POST'])
@login_required
def force_update():
    return run_retrain() # Alias for fallback forms

@app.route("/api/admin/job_status")
@login_required
def job_status():
    if current_user.id != 1: return jsonify({}), 403
    try:
        with open(os.path.join(project_root, 'logs', 'active_job.json'), 'r') as f: return jsonify(json.load(f))
    except: return jsonify({"status": "idle", "logs": [], "progress": 0})