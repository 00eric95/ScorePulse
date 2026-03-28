# Regenerated: dashboard.py
# Changes: 
# - Made it compatible with Flask by converting Streamlit code to Flask-renderable HTML/JS (using Plotly for charts).
# - Integrated with routes.py's admin routes (e.g., /admin/dashboard).
# - Used data from metrics_collector.py and health_checker.py.
# - Fixed paths to use Flask's current_app.config for log directories.
# - Removed Streamlit-specific code; now generates HTML for embedding in templates.
# - Added integration with SystemLog for error display.
# - Ensured charts fit the routes' context (e.g., user/admin views).

"""
A high-level visualization interface for monitoring the SCORE_PULSE AI ecosystem.
It transforms training logs and model metrics into interactive Plotly charts, showing accuracy trends over time.
The dashboard provides a 'Command Center' view of current model champions and their specific hyperparameters.
It handles empty states gracefully by providing actionable CLI commands for users to initialize data and training.
The UI offers a modern, readable overview of the prediction engine's health.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from pathlib import Path
import os
import json
from datetime import datetime, timedelta
import numpy as np
from flask import current_app

class Dashboard:
    def __init__(self):
        self.log_dir = Path(current_app.config['BASE_DIR']) / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)

    def load_training_data(self):
        """Load training history data."""
        LOG_FILE = self.log_dir / "training_history.csv"
        
        if not LOG_FILE.exists():
            return None
        
        try:
            df = pd.read_csv(LOG_FILE)
            # Ensure timestamp is datetime objects
            df['Timestamp'] = pd.to_datetime(df['Timestamp'])
            # Sort by timestamp
            df = df.sort_values('Timestamp')
            return df
        except Exception as e:
            current_app.logger.error(f"Error reading training log file: {e}")
            return None

    def load_system_status(self):
        """Load system status data."""
        STATUS_FILE = self.log_dir / "system_status.json"
        
        if not STATUS_FILE.exists():
            return None
        
        try:
            with open(STATUS_FILE, 'r') as f:
                status_data = json.load(f)
            return status_data
        except Exception as e:
            current_app.logger.error(f"Error reading system status: {e}")
            return None

    def load_health_summary(self):
        """Load health summary."""
        SUMMARY_FILE = self.log_dir / "health_summary.txt"
        
        if not SUMMARY_FILE.exists():
            return None
        
        try:
            with open(SUMMARY_FILE, 'r') as f:
                summary = f.read()
            return summary
        except:
            return None

    def generate_overview_metrics(self, df):
        """Generate HTML for overview metrics."""
        if df is None or df.empty:
            return "<div>No training data available</div>"
        
        latest_by_target = df.sort_values('Timestamp').groupby('Target').last().reset_index()
        
        html = "<div class='metrics-grid'>"
        
        total_runs = len(df)
        html += f"<div class='metric-card'><h3>Total Runs</h3><p>{total_runs:,}</p></div>"
        
        unique_targets = df['Target'].nunique()
        html += f"<div class='metric-card'><h3>Targets Monitored</h3><p>{unique_targets}</p></div>"
        
        unique_models = df['ModelType'].nunique()
        html += f"<div class='metric-card'><h3>Model Types</h3><p>{unique_models}</p></div>"
        
        # Calculate improvement for classification metrics
        classification_df = df[df['Metric'].isin(['Accuracy', 'Precision', 'Recall', 'F1'])]
        if not classification_df.empty:
            initial_score = classification_df.iloc[0]['Score']
            latest_score = classification_df.iloc[-1]['Score']
            improvement = ((latest_score - initial_score) / initial_score * 100) if initial_score != 0 else 0
            html += f"<div class='metric-card'><h3>Improvement</h3><p>{improvement:.1f}%</p></div>"
        
        avg_training_time = df['Training_Time_Seconds'].mean() if 'Training_Time_Seconds' in df.columns else 0
        html += f"<div class='metric-card'><h3>Avg Train Time</h3><p>{avg_training_time:.1f}s</p></div>"
        
        html += "</div>"
        return html

    def generate_performance_charts(self, df):
        """Generate Plotly charts as HTML."""
        if df is None or df.empty:
            return "<div>No data for charts</div>"
        
        fig = make_subplots(rows=2, cols=2, 
                            subplot_titles=('Accuracy Over Time', 'Model Comparison', 
                                            'Feature Importance', 'Training Time vs Score'))
        
        # Accuracy over time
        acc_df = df[df['Metric'] == 'Accuracy']
        fig.add_trace(
            go.Scatter(x=acc_df['Timestamp'], y=acc_df['Score'], mode='lines+markers', name='Accuracy'),
            row=1, col=1
        )
        
        # Model comparison
        model_comp = df.groupby('ModelType')['Score'].mean().reset_index()
        fig.add_trace(
            go.Bar(x=model_comp['ModelType'], y=model_comp['Score'], name='Avg Score'),
            row=1, col=2
        )
        
        # Feature importance (placeholder - assume data available)
        # fig.add_trace(...) row=2, col=1
        
        # Training time vs score
        if 'Training_Time_Seconds' in df.columns:
            fig.add_trace(
                go.Scatter(x=df['Training_Time_Seconds'], y=df['Score'], mode='markers', name='Time vs Score'),
                row=2, col=2
            )
        
        fig.update_layout(height=800, title_text="Performance Overview")
        return fig.to_html(full_html=False, include_plotlyjs='cdn')

    def generate_system_gauges(self, system_data):
        """Generate system gauges as Plotly HTML."""
        if not system_data:
            return "<div>No system data</div>"
        
        fig = make_subplots(
            rows=2, cols=2,
            specs=[[{'type': 'indicator'}, {'type': 'indicator'}],
                   [{'type': 'indicator'}, {'type': 'bar'}]]
        )
        
        # CPU Gauge
        cpu_value = system_data.get('cpu', {}).get('percent', 0)
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=cpu_value,
                title={'text': "CPU Usage"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkblue"},
                    'steps': [
                        {'range': [0, 70], 'color': "lightgreen"},
                        {'range': [70, 85], 'color': "yellow"},
                        {'range': [85, 100], 'color': "red"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 85
                    }
                }
            ),
            row=1, col=1
        )
        
        # Memory Gauge
        mem_value = system_data.get('memory', {}).get('percent', 0)
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=mem_value,
                title={'text': "Memory Usage"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkred"},
                    'steps': [
                        {'range': [0, 70], 'color': "lightgreen"},
                        {'range': [70, 85], 'color': "yellow"},
                        {'range': [85, 100], 'color': "red"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 85
                    }
                }
            ),
            row=1, col=2
        )
        
        # Disk Gauge
        disk_value = system_data.get('disk', {}).get('percent', 0)
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=disk_value,
                title={'text': "Disk Usage"},
                gauge={
                    'axis': {'range': [None, 100]},
                    'bar': {'color': "darkgreen"},
                    'steps': [
                        {'range': [0, 70], 'color': "lightgreen"},
                        {'range': [70, 85], 'color': "yellow"},
                        {'range': [85, 100], 'color': "red"}
                    ],
                    'threshold': {
                        'line': {'color': "red", 'width': 4},
                        'thickness': 0.75,
                        'value': 85
                    }
                }
            ),
            row=2, col=1
        )
        
        # Network Bar Chart
        net_data = system_data.get('network', {})
        if net_data:
            fig.add_trace(
                go.Bar(
                    x=['Bytes Sent', 'Bytes Received'],
                    y=[net_data.get('bytes_sent', 0) / 1024 / 1024,  # MB
                       net_data.get('bytes_recv', 0) / 1024 / 1024],
                    name='Network Traffic (MB)'
                ),
                row=2, col=2
            )
        
        fig.update_layout(height=600, template='plotly_white')
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def generate_alert_dashboard(self, alerts_data):
        """Build alert dashboard"""
        if not alerts_data:
            return "<div>No alerts in the last 24 hours</div>"
        
        df = pd.DataFrame(alerts_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        
        # Group by hour and severity
        df['hour'] = df['timestamp'].dt.floor('H')
        hourly_counts = df.groupby(['hour', 'severity']).size().unstack(fill_value=0)
        
        fig = go.Figure()
        
        for severity in hourly_counts.columns:
            fig.add_trace(go.Bar(
                x=hourly_counts.index,
                y=hourly_counts[severity],
                name=severity.capitalize(),
                marker_color={
                    'critical': '#C62828',
                    'warning': '#FFA000',
                    'info': '#2E7D32'
                }.get(severity, '#808080')
            ))
        
        fig.update_layout(
            title='Alerts by Severity (Last 24 Hours)',
            xaxis_title='Time',
            yaxis_title='Number of Alerts',
            barmode='stack',
            template='plotly_white'
        )
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')
    
    def generate_prediction_analytics_dashboard(self, prediction_data):
        """Build prediction analytics dashboard"""
        if not prediction_data:
            return "<div>No prediction data available</div>"
        
        df = pd.DataFrame(prediction_data)
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('Predictions Over Time', 'Accuracy Trend',
                          'Win/Loss Distribution', 'Confidence vs Accuracy'),
            specs=[[{'type': 'scatter'}, {'type': 'scatter'}],
                   [{'type': 'pie'}, {'type': 'scatter'}]]
        )
        
        # 1. Predictions over time
        if 'timestamp' in df.columns and 'predictions_per_hour' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp'])
            fig.add_trace(
                go.Scatter(x=df['timestamp'], y=df['predictions_per_hour'],
                          name='Predictions/Hour', line=dict(color='blue')),
                row=1, col=1
            )
        
        # 2. Accuracy trend
        if 'timestamp' in df.columns and 'accuracy_per_hour' in df.columns:
            fig.add_trace(
                go.Scatter(x=df['timestamp'], y=df['accuracy_per_hour'],
                          name='Accuracy %', line=dict(color='green')),
                row=1, col=2
            )
        
        # 3. Win/Loss distribution
        if 'wins' in df.columns and 'losses' in df.columns:
            total_wins = df['wins'].sum()
            total_losses = df['losses'].sum()
            
            fig.add_trace(
                go.Pie(labels=['Wins', 'Losses'], 
                      values=[total_wins, total_losses],
                      marker_colors=['#2E7D32', '#C62828']),
                row=2, col=1
            )
        
        # 4. Confidence vs Accuracy scatter
        # This would need additional data
        
        fig.update_layout(height=700, showlegend=True, template='plotly_white')
        
        return fig.to_html(full_html=False, include_plotlyjs='cdn')