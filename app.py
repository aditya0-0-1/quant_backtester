from flask import Flask, request, jsonify
import sqlite3
import pandas as pd
import os
#1
from engine import BacktestEngine

# 2
app = Flask(__name__)

# 3
print("🚀 Flask Server starting... Loading RAM.")
master_conn = sqlite3.connect("trading_ledger.db", check_same_thread=False)

master_conn.cursor().execute("""
    CREATE TABLE IF NOT EXISTS trade_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT,
        ticker TEXT,
        action TEXT,
        price REAL
    )
""")
master_conn.commit()

# LoadING Data into RAM
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

#4
def validate_payload(data):
    """Ensures the JSON payload is safe before running math."""
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

# 5. 
@app.route('/api/run-backtest', methods=['POST'])
def trigger_backtest():
    # A. Catch the JSON
    payload = request.get_json()

    # B. Validate the data manually
    is_valid, parsed_data = validate_payload(payload)
    if not is_valid:
        return jsonify({"status": "error", "message": parsed_data}), 400

    ticker = parsed_data['ticker']
    
    # C. Run the Engine
    bot = BacktestEngine(
        ticker_symbol=ticker,
        dataframe=prepared_data[ticker],
        db_connection=master_conn
    )

    bot.generate_signals(parsed_data['fast'], parsed_data['slow'])
    bot.run_backtest()
    bot.log_trades_safely()

    total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1

    # D. Return JSON Response
    return jsonify({
        "status": "success",
        "ticker": ticker,
        "message": "Backtest complete. Trades safely locked in SQLite.",
        "algo_return_percent": round(total_return * 100, 2)
    }), 200

# 6. RUNNING THE SERVER
if __name__ == '__main__':
    app.run(port=5000, debug=True)




