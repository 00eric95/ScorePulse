import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path
import os

# Set page title
st.set_page_config(page_title="SCORE_PULSE AI Monitor", layout="wide")

st.title("🧠 Model Performance Monitor")

# Path to logs
LOG_FILE = Path(__file__).resolve().parent.parent / "logs" / "training_history.csv"

def load_data():
    if not LOG_FILE.exists():
        st.error("No log data found. Run 'training.py' first.")
        return None
    return pd.read_csv(LOG_FILE)

df = load_data()

if df is not None:
    # Sidebar Filters
    st.sidebar.header("Filters")
    selected_target = st.sidebar.selectbox("Select Target", df['Target'].unique())
    
    # Filter Data
    filtered_df = df[df['Target'] == selected_target]
    
    # KPIs
    latest_run = filtered_df.iloc[-1]
    best_run = filtered_df['Value'].max() if latest_run['Metric'] == 'Accuracy' else filtered_df['Value'].min()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Latest Performance", f"{latest_run['Value']:.4f}", f"{latest_run['Metric']}")
    col2.metric("Best All-Time", f"{best_run:.4f}")
    col3.metric("Total Training Runs", len(filtered_df))

    # Plot
    st.subheader(f"Performance History: {selected_target}")
    
    fig = px.line(filtered_df, x='Timestamp', y='Value', color='Metric', markers=True,
                  title=f"{selected_target} Performance Over Time")
    st.plotly_chart(fig, use_container_width=True)
    
    # Raw Data
    st.subheader("Raw Logs")
    st.dataframe(filtered_df.sort_values(by='Timestamp', ascending=False))

else:
    st.info("Waiting for training data...")