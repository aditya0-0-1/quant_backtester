from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
import pandas as pd
import os

# 1. IMPORT YOUR ENGINE (Bridging the files)
from engine import BacktestEngine, db_lock 

# 2. INITIALIZE THE SERVER
app = FastAPI(title="Quant Engine API", version="1.0")

# 3. GLOBAL SERVER STARTUP (The New Master Script)
print("🚀 Server starting... Opening vault and loading RAM.")
master_conn = sqlite3.connect("trading_ledger.db", check_same_thread=False)

# Build the table just in case it doesn't exist
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

# Load the Dummy Data into RAM
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

# 4. DEFINE THE HTTP PAYLOAD (What the user sends us)
class BacktestRequest(BaseModel):
    ticker: str
    fast_window: int = 10
    slow_window: int = 50

# 5. THE API ENDPOINT (The Web Bridge)
@app.post("/run-backtest/")
def trigger_backtest(request: BacktestRequest):
    """
    This endpoint catches an HTTP POST request, extracts the JSON payload, 
    and hands it to your multithreaded engine.
    """
    ticker = request.ticker.upper()

    # Safety Check: Does the ticker exist in our RAM?
    if ticker not in prepared_data:
        raise HTTPException(status_code=404, detail=f"Ticker {ticker} not found in dataset.")

    # A. Hire the bot and inject dependencies
    bot = BacktestEngine(
        ticker_symbol=ticker,
        dataframe=prepared_data[ticker],
        db_connection=master_conn
    )

    # B. Run the math (using the user's custom MA windows)
    bot.generate_signals(request.fast_window, request.slow_window)
    bot.run_backtest()

    # C. Lock the vault and save
    bot.log_trades_safely()

    # D. Calculate final metric to send back to the user's browser
    total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1

    return {
        "status": "success",
        "ticker": ticker,
        "message": f"Backtest complete. Trades safely locked in SQLite.",
        "algo_return_percent": round(total_return * 100, 2)
    }