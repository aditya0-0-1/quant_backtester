from flask import Flask, request, jsonify, g
import sqlite3
import pandas as pd
import os
from concurrent.futures import ThreadPoolExecutor

from engine import BacktestEngine

app = Flask(__name__)

# DAY 11: INITIALIZE THE WORKER POOL
executor = ThreadPoolExecutor(max_workers=4)

# DAY 10: SECURE DATABASE MANAGEMENT
def get_db():
    if 'db' not in g:
        print("🗄️ Opening secure SQLite connection for this request...")
        g.db = sqlite3.connect("trading_ledger.db")
        g.db.cursor().execute("""
            CREATE TABLE IF NOT EXISTS trade_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                trade_date TEXT,
                ticker TEXT,
                action TEXT,
                price REAL
            )
        """)
        g.db.commit()
    return g.db

@app.teardown_appcontext
def close_db(error):
    db = g.pop('db', None)
    if db is not None:
        print("🔒 Closing SQLite connection.")
        db.close()

# LOAD DATA INTO RAM
filepath = 'data/historical_prices.csv'
if not os.path.exists(filepath):
    print(f"❌ ERROR: Cannot find {filepath}")

df = pd.read_csv(filepath, header=0, skiprows=[1,2])
df.rename(columns={'Price': 'Date'}, inplace=True)
df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)

prepared_data = {
    "AAPL": df,
    "TSLA": df.copy(), 
    "MSFT": df.copy()
}

def validate_payload(data):
    if not data or 'ticker' not in data:
        return False, "Missing 'ticker' in payload."
    
    ticker = str(data['ticker']).upper()
    if ticker not in prepared_data:
        return False, f"Ticker {ticker} not found in database."
    
    fast = data.get('fast_window', 10)
    slow = data.get('slow_window', 50)

    if not isinstance(fast, int) or not isinstance(slow, int) or fast <= 0 or slow <= 0:
        return False, "Windows must be positive integers."
    
    if fast >= slow:
        return False, "Fast window must be strictly less than slow window."

    return True, {"ticker": ticker, "fast": fast, "slow": slow}

# DAY 11: THE BACKGROUND WORKER TASK
def run_backtest_task(ticker, df_data, fast, slow):
    print(f"⚙️ Background thread started for {ticker}...")
    thread_conn = sqlite3.connect("trading_ledger.db")
    
    try:
        bot = BacktestEngine(
            ticker_symbol=ticker,
            dataframe=df_data,
            db_connection=thread_conn
        )
        bot.generate_signals(fast, slow)
        bot.run_backtest()
        bot.log_trades_safely()

        total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1
        print(f"✅ Background task for {ticker} complete! Return: {round(total_return * 100, 2)}%")
        
    except Exception as e:
        print(f"❌ Background thread crashed on {ticker}: {e}")
    finally:
        thread_conn.close()
        print(f"🔒 Background thread closed its SQLite connection.")

# FLASK ENDPOINT
@app.route('/api/run-backtest', methods=['POST'])
def trigger_backtest():
    payload = request.get_json()

    is_valid, parsed_data = validate_payload(payload)
    if not is_valid:
        return jsonify({"status": "error", "message": parsed_data}), 400

    ticker = parsed_data['ticker']
    fast = parsed_data['fast']
    slow = parsed_data['slow']
    
    # DAY 11: Toss the math to the background pool
    executor.submit(run_backtest_task, ticker, prepared_data[ticker], fast, slow)

    # DAY 11: INSTANT 202 Response
    return jsonify({
        "status": "processing",
        "ticker": ticker,
        "message": "Backtest submitted to background worker. Check your terminal for results."
    }), 202

if __name__ == '__main__':
    app.run(port=5000, debug=True)