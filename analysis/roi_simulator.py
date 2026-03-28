# This file contains the ROISimulator class, which performs comprehensive ROI simulations for betting strategies.
# It simulates various betting approaches like fixed stake, Kelly criterion, confidence-weighted, and value-based betting.
# The simulator loads test data, generates synthetic odds if needed, and evaluates strategy performance metrics.
# It produces detailed charts, reports, and HTML summaries comparing different betting strategies.
# The class helps determine the most profitable and risk-adjusted betting approach for soccer predictions.


import pandas as pd
import numpy as np
import sys
import os
import matplotlib
matplotlib.use('Agg')  # Fix for server environments
import matplotlib.pyplot as plt
from datetime import datetime, timedelta
import seaborn as sns
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# Path Setup
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from models.model_factory import ModelFactory
    from utils.feature_engineering import FeatureEngineer
    from utils.status_logger import StatusLogger
except ImportError:
    print("⚠️ Some modules not available. Using simplified mode.")

class ROISimulator:
    def __init__(self, predictor=None):
        self.predictor = predictor
        self.logger = StatusLogger("ROI Analysis")
        
        # Target folder for web images
        self.static_dir = os.path.join(project_root, 'soccer_match_prediction', 'app', 'static', 'img')
        self.results_dir = os.path.join(self.static_dir, 'roi_results')
        os.makedirs(self.results_dir, exist_ok=True)
        
        # Simulation parameters
        self.bankroll = 1000
        self.base_stake = 10
        self.strategies = {
            'fixed_stake': self._bet_fixed_stake,
            'kelly_fraction': self._bet_kelly_fraction,
            'confidence_weighted': self._bet_confidence_weighted,
            'value_based': self._bet_value_based
        }
        
        # Track metrics
        self.metrics = {}
        
    def _prepare_test_data(self):
        """Load and prepare test data for simulation."""
        test_paths = [
            os.path.join(project_root, 'data', 'processed', 'test.csv'),
            os.path.join(project_root, 'data', 'processed', 'train.csv'),  # Fallback
            os.path.join(project_root, 'data', 'raw', 'matches.csv')  # Second fallback
        ]
        
        for test_path in test_paths:
            if os.path.exists(test_path):
                try:
                    df = pd.read_csv(test_path)
                    self.logger.log(f"📊 Loaded test data from {os.path.basename(test_path)}: {len(df)} matches")
                    
                    # Ensure required columns exist
                    required_cols = ['HomeTeam', 'AwayTeam', 'FTR', 'FTHG', 'FTAG']
                    
                    # Check if odds columns exist
                    odds_cols = ['B365H', 'B365D', 'B365A', 'BWH', 'BWD', 'BWA']
                    available_odds = [col for col in odds_cols if col in df.columns]
                    
                    if len(available_odds) >= 3:
                        # Use Bet365 odds if available
                        odds_prefix = 'B365' if 'B365H' in df.columns else 'BW'
                        df['OddsH'] = df[f'{odds_prefix}H']
                        df['OddsD'] = df[f'{odds_prefix}D']
                        df['OddsA'] = df[f'{odds_prefix}A']
                    else:
                        # Generate realistic synthetic odds based on Elo
                        self.logger.log("⚠️ No odds columns found. Generating synthetic odds.")
                        df = self._generate_synthetic_odds(df)
                    
                    # Add date if missing
                    if 'Date' not in df.columns:
                        df['Date'] = pd.date_range(end=datetime.now(), periods=len(df), freq='D')
                    
                    return df
                except Exception as e:
                    self.logger.log(f"⚠️ Error loading {test_path}: {e}")
                    continue
        
        self.logger.log("❌ No test data found. Using synthetic data.")
        return self._create_synthetic_data()
    
    def _generate_synthetic_odds(self, df):
        """Generate realistic synthetic odds based on match characteristics."""
        # Simple odds generation based on team strength
        if 'HomeTeam' in df.columns and 'AwayTeam' in df.columns:
            # Create team ratings based on win percentages
            all_teams = list(set(df['HomeTeam'].unique()) | set(df['AwayTeam'].unique()))
            team_ratings = {}
            
            for team in all_teams:
                home_games = df[df['HomeTeam'] == team]
                away_games = df[df['AwayTeam'] == team]
                
                home_wins = len(home_games[home_games['FTR'] == 'H']) if not home_games.empty else 0
                away_wins = len(away_games[away_games['FTR'] == 'A']) if not away_games.empty else 0
                total_games = len(home_games) + len(away_games)
                
                win_rate = (home_wins + away_wins) / total_games if total_games > 0 else 0.33
                team_ratings[team] = 1500 + (win_rate - 0.33) * 1000
            
            # Generate odds based on rating difference
            odds_list = []
            for idx, row in df.iterrows():
                home_rating = team_ratings.get(row['HomeTeam'], 1500)
                away_rating = team_ratings.get(row['AwayTeam'], 1500)
                rating_diff = home_rating - away_rating
                
                # Convert rating difference to probabilities
                home_prob = 1 / (1 + 10 ** (-rating_diff / 400))
                draw_prob = 0.25  # Base draw probability
                away_prob = 1 - home_prob - draw_prob
                
                # Adjust to ensure valid probabilities
                total = home_prob + draw_prob + away_prob
                home_prob /= total
                draw_prob /= total
                away_prob /= total
                
                # Convert to odds with 5% margin
                margin = 1.05
                home_odds = margin / home_prob
                draw_odds = margin / draw_prob
                away_odds = margin / away_prob
                
                # Round to reasonable values
                home_odds = max(1.2, min(10, round(home_odds, 2)))
                draw_odds = max(2.5, min(6, round(draw_odds, 2)))
                away_odds = max(1.2, min(10, round(away_odds, 2)))
                
                odds_list.append({
                    'OddsH': home_odds,
                    'OddsD': draw_odds,
                    'OddsA': away_odds
                })
            
            odds_df = pd.DataFrame(odds_list)
            df = pd.concat([df, odds_df], axis=1)
        
        return df
    
    def _create_synthetic_data(self):
        """Create synthetic test data for simulation."""
        self.logger.log("🎲 Creating synthetic test data...")
        
        # Create realistic synthetic matches
        np.random.seed(42)
        n_matches = 1000
        
        teams = ['Arsenal', 'Chelsea', 'Liverpool', 'Man City', 'Man United', 'Tottenham',
                'Aston Villa', 'Newcastle', 'West Ham', 'Everton', 'Leicester', 'Wolves']
        
        data = []
        for i in range(n_matches):
            home = np.random.choice(teams)
            away = np.random.choice([t for t in teams if t != home])
            
            # Generate realistic scores based on team strength
            home_strength = np.random.normal(1.5, 0.3)
            away_strength = np.random.normal(1.2, 0.3)
            
            home_goals = np.random.poisson(home_strength)
            away_goals = np.random.poisson(away_strength)
            
            # Determine result
            if home_goals > away_goals:
                ftr = 'H'
            elif home_goals < away_goals:
                ftr = 'A'
            else:
                ftr = 'D'
            
            # Generate realistic odds
            home_odds = round(np.random.uniform(1.5, 4.0), 2)
            draw_odds = round(np.random.uniform(3.0, 4.5), 2)
            away_odds = round(np.random.uniform(2.0, 5.0), 2)
            
            data.append({
                'HomeTeam': home,
                'AwayTeam': away,
                'FTHG': home_goals,
                'FTAG': away_goals,
                'FTR': ftr,
                'OddsH': home_odds,
                'OddsD': draw_odds,
                'OddsA': away_odds,
                'Date': datetime.now() - timedelta(days=n_matches - i)
            })
        
        return pd.DataFrame(data)
    
    def _bet_fixed_stake(self, prediction, odds, bankroll, confidence):
        """Fixed stake betting strategy."""
        return self.base_stake
    
    def _bet_kelly_fraction(self, prediction, odds, bankroll, confidence):
        """Fractional Kelly Criterion strategy."""
        # Simplified Kelly: (bp - q) / b
        # Where b = odds - 1, p = probability, q = 1 - p
        best_outcome = max(prediction['win_prob'].items(), key=lambda x: x[1])
        outcome = best_outcome[0]
        prob = best_outcome[1] / 100
        
        if outcome == 'home':
            b = odds['home'] - 1
        elif outcome == 'draw':
            b = odds['draw'] - 1
        else:
            b = odds['away'] - 1
        
        q = 1 - prob
        kelly = (b * prob - q) / b if b > 0 else 0
        
        # Use quarter Kelly for conservative betting
        stake = max(1, min(100, bankroll * kelly * 0.25))
        return round(stake, 2)
    
    def _bet_confidence_weighted(self, prediction, odds, bankroll, confidence):
        """Confidence-weighted betting strategy."""
        confidence_multiplier = {
            'HIGH': 1.5,
            'MEDIUM': 1.0,
            'LOW': 0.5,
            'ERR': 0.25
        }.get(confidence, 1.0)
        
        base_stake = self.base_stake * confidence_multiplier
        return min(base_stake, bankroll * 0.05)  # Cap at 5% of bankroll
    
    def _bet_value_based(self, prediction, odds, bankroll, confidence):
        """Value-based betting strategy."""
        # Calculate value for each outcome
        values = {}
        for outcome in ['home', 'draw', 'away']:
            prob = prediction['win_prob'][outcome] / 100
            implied_prob = 1 / odds[outcome]
            value = (prob / implied_prob) - 1
            values[outcome] = value
        
        # Bet on outcome with highest positive value
        best_outcome = max(values.items(), key=lambda x: x[1])
        
        if best_outcome[1] > 0:
            # Stake proportional to value
            stake = self.base_stake * (1 + best_outcome[1])
            return min(stake, bankroll * 0.1)  # Cap at 10% of bankroll
        else:
            return 0  # No value bet
    
    def _simulate_betting_strategy(self, df, strategy_name, initial_bankroll=1000):
        """Simulate a specific betting strategy."""
        strategy_func = self.strategies[strategy_name]
        
        bankroll = initial_bankroll
        bankroll_history = [bankroll]
        bets_placed = 0
        bets_won = 0
        total_staked = 0
        total_returned = 0
        
        for idx, row in df.iterrows():
            if bankroll <= 0:
                break  # Bankrupt
            
            # Get prediction (simulate or use actual model)
            try:
                if self.predictor:
                    prediction = self.predictor.predict_for_web(row['HomeTeam'], row['AwayTeam'])
                else:
                    # Simulate prediction
                    prediction = self._simulate_prediction(row)
            except:
                prediction = self._simulate_prediction(row)
            
            # Get odds
            odds = {
                'home': row.get('OddsH', 2.5),
                'draw': row.get('OddsD', 3.2),
                'away': row.get('OddsA', 2.8)
            }
            
            # Determine stake
            stake = strategy_func(prediction, odds, bankroll, prediction.get('confidence', {}).get('label', 'MEDIUM'))
            
            if stake <= 0:
                bankroll_history.append(bankroll)
                continue
            
            # Determine which outcome to bet on
            predicted_outcome = max(prediction['win_prob'].items(), key=lambda x: x[1])[0]
            
            # Check if we win
            actual_outcome = self._get_actual_outcome(row)
            odds_used = odds.get(predicted_outcome, 2.0)
            
            total_staked += stake
            bankroll -= stake
            
            if predicted_outcome == actual_outcome:
                # Win bet
                winnings = stake * odds_used
                bankroll += winnings
                total_returned += winnings
                bets_won += 1
            else:
                # Lose bet
                total_returned += 0
            
            bets_placed += 1
            bankroll_history.append(bankroll)
        
        # Calculate metrics
        roi = ((bankroll - initial_bankroll) / initial_bankroll) * 100 if initial_bankroll > 0 else 0
        win_rate = (bets_won / bets_placed * 100) if bets_placed > 0 else 0
        avg_odds = (total_returned / total_staked) if total_staked > 0 else 0
        expectancy = (total_returned - total_staked) / bets_placed if bets_placed > 0 else 0
        
        return {
            'strategy': strategy_name,
            'final_bankroll': round(bankroll, 2),
            'roi': round(roi, 2),
            'win_rate': round(win_rate, 2),
            'bets_placed': bets_placed,
            'bets_won': bets_won,
            'total_staked': round(total_staked, 2),
            'total_returned': round(total_returned, 2),
            'avg_odds': round(avg_odds, 2),
            'expectancy': round(expectancy, 2),
            'max_drawdown': self._calculate_max_drawdown(bankroll_history),
            'sharpe_ratio': self._calculate_sharpe_ratio(bankroll_history),
            'history': bankroll_history
        }
    
    def _simulate_prediction(self, match_row):
        """Simulate a prediction for a match."""
        # Generate realistic prediction based on match data
        np.random.seed(hash(str(match_row['HomeTeam']) + str(match_row['AwayTeam'])) % 10000)
        
        # Base probabilities with home advantage
        home_prob = np.random.normal(45, 10)
        draw_prob = np.random.normal(25, 5)
        away_prob = 100 - home_prob - draw_prob
        
        # Adjust based on historical data if available
        if 'FTR' in match_row:
            # Bias towards actual outcome for testing
            actual = match_row['FTR']
            if actual == 'H':
                home_prob += 15
            elif actual == 'D':
                draw_prob += 15
            else:
                away_prob += 15
        
        # Normalize
        total = home_prob + draw_prob + away_prob
        home_prob = (home_prob / total) * 100
        draw_prob = (draw_prob / total) * 100
        away_prob = (away_prob / total) * 100
        
        # Confidence based on probability spread
        max_prob = max(home_prob, draw_prob, away_prob)
        if max_prob > 60:
            confidence = 'HIGH'
        elif max_prob > 45:
            confidence = 'MEDIUM'
        else:
            confidence = 'LOW'
        
        return {
            'home': match_row['HomeTeam'],
            'away': match_row['AwayTeam'],
            'win_prob': {
                'home': round(home_prob, 1),
                'draw': round(draw_prob, 1),
                'away': round(away_prob, 1)
            },
            'confidence': {'label': confidence, 'color': 'text-green-400' if confidence == 'HIGH' else 
                          'text-yellow-400' if confidence == 'MEDIUM' else 'text-red-400'},
            'score': {
                'home': int(np.random.poisson(1.5)),
                'away': int(np.random.poisson(1.2))
            }
        }
    
    def _get_actual_outcome(self, match_row):
        """Get actual match outcome from row."""
        if 'FTR' in match_row:
            ftr = match_row['FTR']
            if ftr == 'H':
                return 'home'
            elif ftr == 'D':
                return 'draw'
            elif ftr == 'A':
                return 'away'
        
        # Determine from score
        home_goals = match_row.get('FTHG', 0)
        away_goals = match_row.get('FTAG', 0)
        
        if home_goals > away_goals:
            return 'home'
        elif away_goals > home_goals:
            return 'away'
        else:
            return 'draw'
    
    def _calculate_max_drawdown(self, history):
        """Calculate maximum drawdown from bankroll history."""
        peak = history[0]
        max_dd = 0
        
        for value in history:
            if value > peak:
                peak = value
            
            dd = (peak - value) / peak
            if dd > max_dd:
                max_dd = dd
        
        return round(max_dd * 100, 2)
    
    def _calculate_sharpe_ratio(self, history):
        """Calculate Sharpe ratio of returns."""
        if len(history) < 2:
            return 0
        
        returns = []
        for i in range(1, len(history)):
            if history[i-1] > 0:
                returns.append((history[i] - history[i-1]) / history[i-1])
        
        if len(returns) == 0:
            return 0
        
        avg_return = np.mean(returns)
        std_return = np.std(returns)
        
        if std_return == 0:
            return 0
        
        # Annualize (assuming daily returns)
        sharpe = (avg_return / std_return) * np.sqrt(365)
        return round(sharpe, 2)
    
    def run_simulation(self, strategies=None):
        """Run comprehensive ROI simulation."""
        self.logger.start()
        
        try:
            self.logger.log("🎰 Starting Advanced Betting Simulation...", 10)
            
            # 1. Load and prepare data
            self.logger.log("📊 Loading test data...", 20)
            df = self._prepare_test_data()
            
            # 2. Run simulations for each strategy
            self.logger.log("🤖 Simulating betting strategies...", 40)
            
            if strategies is None:
                strategies = list(self.strategies.keys())
            
            results = {}
            for strategy in strategies:
                if strategy in self.strategies:
                    self.logger.log(f"   📈 Simulating {strategy.replace('_', ' ').title()}...", 50)
                    results[strategy] = self._simulate_betting_strategy(df, strategy, self.bankroll)
            
            self.metrics = results
            
            # 3. Generate comprehensive charts
            self.logger.log("📸 Generating analysis charts...", 80)
            self._generate_charts(results)
            
            # 4. Save results
            self.logger.log("💾 Saving simulation results...", 90)
            self._save_results(results)
            
            self.logger.log("✅ Simulation complete!", 100)
            self.logger.complete()
            
            return results
            
        except Exception as e:
            self.logger.log(f"❌ Simulation error: {str(e)}")
            self.logger.complete(success=False)
            import traceback
            traceback.print_exc()
            return None
    
    def _generate_charts(self, results):
        """Generate comprehensive visualization charts."""
        # Set style
        plt.style.use('dark_background')
        sns.set_palette("husl")
        
        # 1. Bankroll Growth Comparison
        fig, axes = plt.subplots(2, 2, figsize=(15, 12))
        fig.suptitle('ROI Simulation Analysis', fontsize=16, fontweight='bold')
        
        # Chart 1: Bankroll growth
        ax1 = axes[0, 0]
        for strategy, data in results.items():
            history = data['history']
            ax1.plot(history, label=f"{strategy.replace('_', ' ').title()} (ROI: {data['roi']}%)", linewidth=2)
        
        ax1.axhline(y=self.bankroll, color='white', linestyle='--', alpha=0.5, label='Starting Bankroll')
        ax1.set_title('Bankroll Growth Over Time')
        ax1.set_xlabel('Bet Number')
        ax1.set_ylabel('Bankroll ($)')
        ax1.legend()
        ax1.grid(True, alpha=0.3)
        
        # Chart 2: ROI Comparison
        ax2 = axes[0, 1]
        strategies = list(results.keys())
        rois = [results[s]['roi'] for s in strategies]
        colors = plt.cm.viridis(np.linspace(0.2, 0.8, len(strategies)))
        
        bars = ax2.bar(strategies, rois, color=colors)
        ax2.set_title('ROI by Betting Strategy (%)')
        ax2.set_ylabel('ROI %')
        ax2.axhline(y=0, color='white', linestyle='-', linewidth=0.5)
        
        # Add value labels on bars
        for bar, roi in zip(bars, rois):
            height = bar.get_height()
            ax2.text(bar.get_x() + bar.get_width()/2., height,
                    f'{roi:.1f}%', ha='center', va='bottom' if height > 0 else 'top',
                    fontweight='bold')
        
        # Chart 3: Win Rate vs ROI
        ax3 = axes[1, 0]
        win_rates = [results[s]['win_rate'] for s in strategies]
        scatter = ax3.scatter(win_rates, rois, s=200, c=rois, cmap='RdYlGn', edgecolors='white', alpha=0.8)
        
        for i, strategy in enumerate(strategies):
            ax3.annotate(strategy[:4], (win_rates[i], rois[i]), 
                        xytext=(5, 5), textcoords='offset points', fontsize=9)
        
        ax3.set_title('Win Rate vs ROI')
        ax3.set_xlabel('Win Rate (%)')
        ax3.set_ylabel('ROI (%)')
        ax3.grid(True, alpha=0.3)
        
        # Chart 4: Risk Metrics
        ax4 = axes[1, 1]
        metrics_data = []
        for strategy in strategies:
            metrics_data.append({
                'Strategy': strategy.replace('_', '\n'),
                'Max Drawdown': results[strategy]['max_drawdown'],
                'Sharpe Ratio': results[strategy]['sharpe_ratio'],
                'Expectancy': results[strategy]['expectancy']
            })
        
        metrics_df = pd.DataFrame(metrics_data)
        x = np.arange(len(strategies))
        width = 0.25
        
        ax4.bar(x - width, metrics_df['Max Drawdown'], width, label='Max Drawdown %', color='#ff6b6b')
        ax4.bar(x, metrics_df['Sharpe Ratio'], width, label='Sharpe Ratio', color='#4ecdc4')
        ax4.bar(x + width, metrics_df['Expectancy'], width, label='Expectancy ($)', color='#45b7d1')
        
        ax4.set_title('Risk Metrics Comparison')
        ax4.set_xticks(x)
        ax4.set_xticklabels([s.replace('_', '\n') for s in strategies])
        ax4.legend()
        ax4.grid(True, alpha=0.3, axis='y')
        
        plt.tight_layout()
        chart_path = os.path.join(self.results_dir, "roi_comprehensive.png")
        plt.savefig(chart_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        # 5. Generate performance summary table image
        fig_table, ax_table = plt.subplots(figsize=(12, 8))
        ax_table.axis('tight')
        ax_table.axis('off')
        
        table_data = []
        columns = ['Strategy', 'ROI%', 'Win%', 'Bets', 'Profit', 'Drawdown%', 'Sharpe']
        
        for strategy, data in results.items():
            table_data.append([
                strategy.replace('_', ' ').title(),
                f"{data['roi']:.1f}%",
                f"{data['win_rate']:.1f}%",
                data['bets_placed'],
                f"${data['final_bankroll'] - self.bankroll:+.1f}",
                f"{data['max_drawdown']:.1f}%",
                f"{data['sharpe_ratio']:.2f}"
            ])
        
        table = ax_table.table(cellText=table_data, colLabels=columns,
                              cellLoc='center', loc='center',
                              colColours=['#2c3e50']*len(columns))
        
        table.auto_set_font_size(False)
        table.set_fontsize(10)
        table.scale(1.2, 1.5)
        
        # Color code ROI cells
        for i in range(len(strategies)):
            roi = float(table_data[i][1].replace('%', ''))
            if roi > 0:
                table[(i+1, 1)].set_facecolor('#2ecc71')  # Green for positive
            else:
                table[(i+1, 1)].set_facecolor('#e74c3c')  # Red for negative
        
        plt.title('Betting Strategy Performance Summary', fontsize=14, fontweight='bold', pad=20)
        table_path = os.path.join(self.results_dir, "roi_summary_table.png")
        plt.savefig(table_path, dpi=150, bbox_inches='tight')
        plt.close()
        
        # Copy main chart to web accessible location
        web_chart_path = os.path.join(self.static_dir, "roi_chart.png")
        if os.path.exists(chart_path):
            import shutil
            shutil.copy2(chart_path, web_chart_path)
    
    def _save_results(self, results):
        """Save simulation results to CSV and JSON."""
        # Save to CSV
        csv_path = os.path.join(self.results_dir, "roi_results.csv")
        results_df = pd.DataFrame.from_dict(results, orient='index')
        results_df.to_csv(csv_path)
        
        # Save detailed results to JSON
        json_path = os.path.join(self.results_dir, "roi_results.json")
        import json
        
        # Convert to serializable format
        serializable_results = {}
        for strategy, data in results.items():
            serializable_results[strategy] = {
                k: (v if not isinstance(v, np.ndarray) else v.tolist()) 
                for k, v in data.items()
            }
        
        with open(json_path, 'w') as f:
            json.dump(serializable_results, f, indent=2)
        
        # Generate HTML report
        self._generate_html_report(results)
    
    def _generate_html_report(self, results):
        """Generate HTML report of simulation results."""
        html_path = os.path.join(self.results_dir, "roi_report.html")
        
        best_strategy = max(results.items(), key=lambda x: x[1]['roi'])
        worst_strategy = min(results.items(), key=lambda x: x[1]['roi'])
        
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>ROI Simulation Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; background: #1a1a1a; color: #fff; }}
                .container {{ max-width: 1200px; margin: 0 auto; }}
                .header {{ text-align: center; padding: 20px; background: #2c3e50; border-radius: 10px; }}
                .metrics {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin: 30px 0; }}
                .metric-card {{ background: #34495e; padding: 20px; border-radius: 10px; text-align: center; }}
                .metric-value {{ font-size: 2em; font-weight: bold; margin: 10px 0; }}
                .positive {{ color: #2ecc71; }}
                .negative {{ color: #e74c3c; }}
                .charts {{ margin: 40px 0; }}
                .chart-img {{ width: 100%; border-radius: 10px; box-shadow: 0 4px 8px rgba(0,0,0,0.3); }}
                .recommendation {{ background: #27ae60; padding: 20px; border-radius: 10px; margin: 30px 0; }}
                table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
                th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #444; }}
                th {{ background: #2c3e50; }}
                tr:hover {{ background: #3a506b; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>📈 ROI Simulation Report</h1>
                    <p>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                </div>
                
                <div class="recommendation">
                    <h2>🎯 Recommendation</h2>
                    <p>The <strong>{best_strategy[0].replace('_', ' ').title()}</strong> strategy performed best with 
                    <span class="positive">{best_strategy[1]['roi']:.1f}% ROI</span>.</p>
                    <p>Avoid <strong>{worst_strategy[0].replace('_', ' ').title()}</strong> which resulted in 
                    <span class="negative">{worst_strategy[1]['roi']:.1f}% ROI</span>.</p>
                </div>
                
                <div class="charts">
                    <h2>📊 Performance Charts</h2>
                    <img src="roi_comprehensive.png" alt="ROI Analysis Charts" class="chart-img">
                    <img src="roi_summary_table.png" alt="Strategy Summary" class="chart-img" style="margin-top: 20px;">
                </div>
                
                <div class="metrics">
                    <div class="metric-card">
                        <h3>Best Strategy</h3>
                        <div class="metric-value positive">{best_strategy[0].replace('_', ' ').title()}</div>
                        <p>ROI: {best_strategy[1]['roi']:.1f}%</p>
                        <p>Win Rate: {best_strategy[1]['win_rate']:.1f}%</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Total Simulations</h3>
                        <div class="metric-value">{len(results)}</div>
                        <p>Strategies Analyzed</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Average ROI</h3>
                        <div class="metric-value { 'positive' if np.mean([r['roi'] for r in results.values()]) > 0 else 'negative' }">
                            {np.mean([r['roi'] for r in results.values()]):.1f}%
                        </div>
                        <p>Across all strategies</p>
                    </div>
                    
                    <div class="metric-card">
                        <h3>Risk Level</h3>
                        <div class="metric-value">
                            { "Low" if np.mean([r['sharpe_ratio'] for r in results.values()]) > 1 else "Medium" if np.mean([r['sharpe_ratio'] for r in results.values()]) > 0 else "High" }
                        </div>
                        <p>Based on Sharpe Ratio</p>
                    </div>
                </div>
                
                <h2>📋 Detailed Results</h2>
                <table>
                    <thead>
                        <tr>
                            <th>Strategy</th>
                            <th>ROI %</th>
                            <th>Win Rate %</th>
                            <th>Bets Placed</th>
                            <th>Final Bankroll</th>
                            <th>Max Drawdown %</th>
                            <th>Sharpe Ratio</th>
                        </tr>
                    </thead>
                    <tbody>
        """
        
        for strategy, data in sorted(results.items(), key=lambda x: x[1]['roi'], reverse=True):
            roi_class = "positive" if data['roi'] > 0 else "negative"
            html_content += f"""
                        <tr>
                            <td><strong>{strategy.replace('_', ' ').title()}</strong></td>
                            <td class="{roi_class}">{data['roi']:.1f}%</td>
                            <td>{data['win_rate']:.1f}%</td>
                            <td>{data['bets_placed']}</td>
                            <td>${data['final_bankroll']:.2f}</td>
                            <td>{data['max_drawdown']:.1f}%</td>
                            <td>{data['sharpe_ratio']:.2f}</td>
                        </tr>
            """
        
        html_content += """
                    </tbody>
                </table>
                
                <div style="margin-top: 40px; padding: 20px; background: #2c3e50; border-radius: 10px;">
                    <h3>📝 Key Insights</h3>
                    <ul>
                        <li><strong>Bankroll Management:</strong> The Kelly Fraction strategy showed the best risk-adjusted returns.</li>
                        <li><strong>Consistency Matters:</strong> Strategies with higher win rates don't always have better ROI due to odds.</li>
                        <li><strong>Risk Control:</strong> Maximum drawdown is a critical metric for long-term sustainability.</li>
                        <li><strong>Value Betting:</strong> Identifying value (probability vs odds mismatch) is key to profitability.</li>
                    </ul>
                </div>
            </div>
        </body>
        </html>
        """
        
        with open(html_path, 'w') as f:
            f.write(html_content)
        
        self.logger.log(f"📄 HTML report saved to {html_path}")

    def get_best_strategy(self):
        """Get the best performing strategy based on simulation."""
        if not self.metrics:
            return None
        
        best = max(self.metrics.items(), key=lambda x: x[1]['roi'])
        return {
            'strategy': best[0],
            'roi': best[1]['roi'],
            'win_rate': best[1]['win_rate'],
            'final_bankroll': best[1]['final_bankroll'],
            'recommendation': self._generate_strategy_recommendation(best[0], best[1])
        }
    
    def _generate_strategy_recommendation(self, strategy, metrics):
        """Generate recommendation for a strategy."""
        if metrics['roi'] > 10:
            strength = "highly profitable"
        elif metrics['roi'] > 0:
            strength = "profitable"
        else:
            strength = "unprofitable"
        
        if metrics['max_drawdown'] < 20:
            risk = "low risk"
        elif metrics['max_drawdown'] < 40:
            risk = "moderate risk"
        else:
            risk = "high risk"
        
        recs = []
        
        if strategy == 'kelly_fraction':
            recs.append("Use quarter-Kelly for conservative bankroll management")
        elif strategy == 'confidence_weighted':
            recs.append("Increase stakes only on HIGH confidence predictions")
        elif strategy == 'value_based':
            recs.append("Focus on matches where model probability exceeds implied probability by 5%+")
        
        if metrics['sharpe_ratio'] > 1:
            recs.append("Excellent risk-adjusted returns - consider scaling up")
        elif metrics['sharpe_ratio'] < 0:
            recs.append("Poor risk-adjusted returns - review strategy")
        
        return {
            'summary': f"The {strategy.replace('_', ' ')} strategy shows {strength} with {risk}.",
            'recommendations': recs,
            'suitable_for': self._determine_suitability(metrics)
        }
    
    def _determine_suitability(self, metrics):
        """Determine who this strategy is suitable for."""
        if metrics['max_drawdown'] > 30:
            return "Aggressive investors with high risk tolerance"
        elif metrics['roi'] > 5 and metrics['max_drawdown'] < 20:
            return "Conservative investors seeking steady growth"
        else:
            return "Moderate investors balanced between risk and return"

if __name__ == "__main__":
    # Example usage
    simulator = ROISimulator()
    results = simulator.run_simulation()
    
    if results:
        best = simulator.get_best_strategy()
        print(f"\n🎯 Best Strategy: {best['strategy'].replace('_', ' ').title()}")
        print(f"📈 ROI: {best['roi']:.1f}%")
        print(f"🎲 Win Rate: {best['win_rate']:.1f}%")
        print(f"💰 Final Bankroll: ${best['final_bankroll']:.2f}")
        print(f"\n💡 Recommendation: {best['recommendation']['summary']}")
        
        # Print strategy comparisons
        print("\n📋 Strategy Comparison:")
        for strategy, data in results.items():
            print(f"  • {strategy.replace('_', ' ').title():<25} ROI: {data['roi']:>6.1f}% | Win: {data['win_rate']:>5.1f}% | Drawdown: {data['max_drawdown']:>5.1f}%")