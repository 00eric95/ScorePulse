# ⚽ ScorePulse AI - v2

ScorePulse AI is an advanced football prediction engine that combines Machine Learning (Random Forest/XGBoost) with a Flask web dashboard and a Telegram bot.

## 🚀 Features

* **AI Brain:** Predicts Win/Draw/Loss, Expected Goals (xG), and BTTS based on historical data.
* **Web Dashboard:** "Stadium Board" UI with cascading dropdowns (Country -> League -> Team).
* **Recency Filter:** Automatically filters out relegated/inactive teams based on the last 2 years of data.
* **Premium Insights:** Subscription-based access to advanced stats (Elo, Form, H2H).
* **Telegram Bot:** Instant predictions via chat command `/predict`.
* **M-Pesa Integration:** STK Push integration for premium payments.

## 📂 Project Structure

```text
SCORE_PULSEv2/
├── config/             # ML Configurations
├── data/               # Raw and Processed CSVs
├── models/             # Trained .pkl models
├── soccer_match_prediction/ # Flask Web App
├── telegram_bot/       # Bot Scripts
├── utils/              # Feature Engineering Scripts
├── main.py             # The AI Logic Core (API)
├── training.py         # Script to retrain models
└── requirements.txt    # Dependencies