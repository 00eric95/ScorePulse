# ⚽ ScorePulse AI - v2

ScorePulse AI is an advanced football prediction engine that combines Machine Learning models (XGBoost, Random Forest, LightGBM, Neural Networks) with a Flask web dashboard, Telegram bot, and comprehensive monitoring system. The system predicts match outcomes, expected goals (xG), and BTTS (Both Teams To Score) based on historical data, Elo ratings, and advanced feature engineering.

## 🚀 Features

* **AI Brain:** Multi-model prediction engine supporting XGBoost, Random Forest, LightGBM, and Neural Networks for Win/Draw/Loss, xG, and BTTS predictions.
* **Web Dashboard:** "Stadium Board" UI with cascading dropdowns (Country -> League -> Team) built with Flask and SocketIO.
* **Recency Filter:** Automatically filters out relegated/inactive teams based on the last 2 years of data.
* **Premium Insights:** Subscription-based access to advanced stats (Elo, Form, H2H) with M-Pesa integration.
* **Telegram Bot:** Instant predictions via chat command `/predict` with payment processing.
* **Real-time Monitoring:** Comprehensive health checks, metrics collection, and alerting system.
* **Background Processing:** Celery-based task queue for model retraining, data updates, and scheduled predictions.
* **Data Pipeline:** Automated data collection, feature engineering, and model evaluation.
* **Online Learning:** Continuous model improvement with new match results.

## 🏗️ Architecture

The system follows a modular microservices architecture:

### Core Components
- **Orchestrator (`orchastrator.py`):** Central controller managing the full ML pipeline from data ingestion to model deployment.
- **AI Engine (`main.py`):** Primary prediction logic with team resolution, feature engineering, and model inference.
- **Model Factory (`models/model_factory.py`):** Factory pattern for dynamic model instantiation and loading.

### Services
- **Web App (`soccer_match_prediction/`):** Flask application with SocketIO for real-time updates.
- **Telegram Bot (`telegram_bot/`):** Asynchronous bot handling user interactions and payments.
- **Monitoring (`monitoring/`):** Health checks, metrics collection, dashboard, and alerting.
- **Background Workers:** Celery tasks for model retraining, data updates, and scheduled operations.

### Data Flow
1. **Data Collection:** Raw match data from `data/raw/` processed into features.
2. **Feature Engineering:** Advanced stats calculation in `utils/feature_engineering.py`.
3. **Model Training:** Multiple ML models trained and evaluated in `models/`.
4. **Prediction:** Real-time inference for upcoming matches.
5. **Feedback Loop:** Online learning updates models with new results.

## 📂 Project Structure

```
SCORE_PULSEAIv2/
├── analysis/                    # Model evaluation and ROI simulation
│   ├── import_matches.py       # Data import utilities
│   ├── roi_simulator.py        # Return on investment calculations
│   └── validate_predictions.py # Prediction validation scripts
├── backups/                     # Backup storage
├── config/                      # Configuration management
│   ├── __init__.py
│   ├── config.py               # Main configuration class
│   └── constants.py            # System constants
├── data/                        # Data management
│   ├── processed/              # Cleaned and engineered datasets
│   ├── raw/                    # Raw match data and Elo ratings
│   └── betting_odds.csv        # Betting odds data
├── instance/                    # Instance-specific data (DB, etc.)
├── logs/                        # Application logs
├── migrations/                  # Database migrations
├── models/                      # Machine learning models
│   ├── __init__.py
│   ├── best_hyperparameters.json # Optimized model parameters
│   ├── gradient_boosting.py    # Gradient boosting implementation
│   ├── lgbm_model.py           # LightGBM model wrapper
│   ├── model_factory.py        # Model factory for instantiation
│   ├── nn_model.py             # Neural network model
│   ├── rf_model.py             # Random Forest model
│   └── xgb_model.py            # XGBoost model
├── monitoring/                  # System monitoring and health
│   ├── __init__.py
│   ├── alert_system.py         # Alerting mechanisms
│   ├── dashboard.py            # Monitoring dashboard
│   ├── health_checker.py       # Comprehensive health checks
│   ├── logger.py               # Logging utilities
│   └── metrics_collector.py    # Performance metrics
├── notebooks/                   # Jupyter notebooks for analysis
├── scripts/                     # Utility scripts
│   ├── check_teams.py          # Team validation
│   ├── create_migration.py     # DB migration helpers
│   ├── debug_csv.py            # CSV debugging tools
│   ├── diagnostic_check.py     # System diagnostics
│   ├── fix_dataloader.py       # Data loader fixes
│   ├── inspect_eval.py         # Evaluation inspection
│   ├── seed_initial_data.py    # Initial data seeding
│   └── show_project_root.py    # Project root utilities
├── soccer_match_prediction/     # Flask web application
│   ├── __init__.py
│   ├── celery_worker.py        # Celery worker configuration
│   ├── init_db.py              # Database initialization
│   ├── pitch_commander.py      # Prediction interface
│   ├── run.py                  # Flask app entry point
│   ├── settings.py             # App settings
│   ├── agents/                 # AI agents for different roles
│   ├── app/                    # Flask app core
│   └── static/                 # Static assets
├── telegram_bot/                # Telegram bot service
│   ├── __init__.py
│   ├── bot.py                  # Main bot logic
│   ├── check_token.py          # Token validation
│   └── mpesa_utils.py          # M-Pesa payment integration
├── updating/                    # Model updating and learning
│   ├── __init__.py
│   ├── data_collection.py      # Data collection scripts
│   ├── model_retraining.py     # Automated retraining
│   ├── online_learner.py       # Online learning algorithms
│   └── prediction_storage.py   # Prediction result storage
├── utils/                       # Utility modules
│   ├── __init__.py
│   ├── data_loader.py          # Data loading utilities
│   ├── email_service.py        # Email notifications
│   ├── error_handler.py        # Error handling
│   ├── evaluation.py           # Model evaluation metrics
│   ├── feature_engineering.py  # Feature creation and processing
│   ├── feature_generator.py    # Feature generation logic
│   ├── status_logger.py        # Status logging
│   └── tuner.py                # Hyperparameter tuning
├── celery_app.py               # Celery application configuration
├── docker-compose.yaml         # Docker orchestration
├── Dockerfile                  # Container definition
├── evaluate.py                 # Model evaluation script
├── main.py                     # Core AI prediction engine
├── orchastrator.py             # System orchestrator
├── Procfile                    # Heroku deployment configuration
├── README.md                   # This file
├── requirements.txt            # Python dependencies
├── scheduler.py                # Task scheduling
└── training.py                 # Model training script
```

## 🔧 How the App Runs

### Local Development
1. **Setup Environment:**
   ```bash
   pip install -r requirements.txt
   cp .env.example .env  # Configure environment variables
   ```

2. **Initialize Database:**
   ```bash
   python soccer_match_prediction/init_db.py
   ```

3. **Run Flask Web App:**
   ```bash
   python soccer_match_prediction/run.py
   ```
   Access at http://127.0.0.1:5000

4. **Run Telegram Bot:**
   ```bash
   python telegram_bot/bot.py
   ```

5. **Run Celery Workers:**
   ```bash
   celery -A celery_app worker --loglevel=info
   celery -A celery_worker.celery worker --loglevel=info --pool=solo
   ```

### Docker Deployment
```bash
docker-compose up --build
```

### Production Deployment (Heroku)
- Web service: Gunicorn with Flask app
- Worker: Telegram bot process
- Background tasks: Celery with Redis

### Key Entry Points
- `main.py`: Core prediction logic and CLI interface
- `soccer_match_prediction/run.py`: Flask web server
- `telegram_bot/bot.py`: Telegram bot service
- `training.py`: Model training pipeline
- `evaluate.py`: Model evaluation and ROI analysis

## 🔄 Systematics

### Data Pipeline
1. **Collection:** Automated data ingestion from various sources
2. **Processing:** Feature engineering and data cleaning
3. **Training:** Model training with hyperparameter optimization
4. **Evaluation:** Cross-validation and ROI simulation
5. **Deployment:** Model serialization and loading
6. **Monitoring:** Continuous performance tracking

### Prediction Flow
1. **Input:** Match details (teams, league, date)
2. **Resolution:** Team name standardization and mapping
3. **Features:** Real-time feature calculation
4. **Inference:** Multi-model prediction aggregation
5. **Output:** Formatted predictions with confidence scores

### Background Tasks
- **Model Retraining:** Scheduled model updates with new data
- **Data Updates:** Regular data collection and processing
- **Health Checks:** System monitoring and alerting
- **Prediction Storage:** Result archiving and analysis

## 📊 Monitoring & Health

The system includes comprehensive monitoring:
- **Health Checks:** AI engine, database, Redis, SSL validation
- **Metrics Collection:** Prediction accuracy, response times, system resources
- **Alerting:** Email notifications for critical issues
- **Dashboard:** Real-time system status visualization
- **Logging:** Structured logging across all components

## 🔒 Security & Configuration

- Environment-based configuration (.env files)
- OAuth integration (Google)
- Secure payment processing (M-Pesa)
- Database encryption and access controls
- API rate limiting and authentication

## 📈 Model Performance

- Multi-model ensemble for improved accuracy
- Continuous learning from new match results
- Hyperparameter optimization and validation
- ROI simulation and backtesting
- Feature importance analysis

## celery initialization

- -NetConnection localhost -Port 6379 
- celery -A celery_worker.celery inspect ping


This architecture ensures scalability, maintainability, and high availability for professional sports prediction services.