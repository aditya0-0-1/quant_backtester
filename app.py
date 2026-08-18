from flask import Flask, request, jsonify
import sqlite3
import pandas as pd
import os
import functools
import threading
from concurrent.futures import ThreadPoolExecutor

from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from engine import BacktestEngine, BacktestError

app = Flask(__name__)

# FIX: cap request body size (1 MB is generous for this payload shape).
# Without this, nothing stops an oversized/garbage body from being accepted
# and parsed before validation even runs.
app.config['MAX_CONTENT_LENGTH'] = 1 * 1024 * 1024

executor = ThreadPoolExecutor(max_workers=4)
db_lock = threading.Lock()

MAX_WINDOW = 500  # FIX: upper bound on fast/slow window size

API_KEY = os.environ.get("API_KEY", "dev-key-change-me")
if API_KEY == "dev-key-change-me":
    print("WARNING: Using default dev API key. Set the API_KEY environment "
          "variable before deploying anywhere real.")


def require_api_key(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        provided_key = request.headers.get("X-API-Key")
        if provided_key is None or provided_key != API_KEY:
            return error_response("Invalid or missing API key.", 401)
        return f(*args, **kwargs)
    return decorated


limiter = Limiter(
    key_func=get_remote_address,
    app=app,
    default_limits=[],
)


def error_response(message, status_code=400):
    return jsonify({"status": "error", "message": message}), status_code


def init_db():
    conn = sqlite3.connect("trading_ledger.db")
    conn.cursor().execute("""
        CREATE TABLE IF NOT EXISTS trade_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            trade_date TEXT,
            ticker TEXT,
            action TEXT,
            price REAL
        )
    """)
    conn.commit()
    conn.close()


init_db()


filepath = 'data/historical_prices.csv'
if not os.path.exists(filepath):
    print(f"ERROR: Cannot find {filepath}")

df = pd.read_csv(filepath, header=0, skiprows=[1, 2])
df.rename(columns={'Price': 'Date'}, inplace=True)
df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)

# NOTE: these are the master copies. Never hand these objects directly to
# a worker thread — always .copy() at the point of submission (see below).
prepared_data = {
    "AAPL": df.copy(),   # FIX: was bare `df` — every AAPL request used to
                          # mutate the one true source-of-truth object directly.
    "TSLA": df.copy(),
    "MSFT": df.copy()
}


def validate_payload(data):
    """Ensures the JSON payload is safe before running math."""
    if not data or 'ticker' not in data:
        return False, "Missing 'ticker' in payload."

    ticker = str(data['ticker']).upper()
    if ticker not in prepared_data:
        # FIX: message no longer claims a "database" lookup happened —
        # this is a fixed in-memory dict, not a DB query.
        return False, f"Ticker {ticker} not supported."

    fast = data.get('fast_window', 10)
    slow = data.get('slow_window', 50)

    if type(fast) is not int or type(slow) is not int or fast <= 0 or slow <= 0:
        return False, "Windows must be positive integers."

    # FIX: upper bound so no one can request an absurd window size.
    if fast > MAX_WINDOW or slow > MAX_WINDOW:
        return False, f"Windows must not exceed {MAX_WINDOW}."

    if fast >= slow:
        return False, "Fast window must be strictly less than slow window."

    return True, {"ticker": ticker, "fast": fast, "slow": slow}


def run_backtest_task(ticker, df_data, fast, slow):
    """Background worker: runs the full pipeline in its own thread/connection."""
    print(f"Background thread started for {ticker}...")
    thread_conn = sqlite3.connect("trading_ledger.db")

    try:
        bot = BacktestEngine(
            ticker_symbol=ticker,
            dataframe=df_data,
            db_connection=thread_conn,
            db_lock=db_lock
        )
        # FIX: fast/slow now actually reach the engine.
        bot.run_full_pipeline(fast, slow)

        total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1
        print(f"Background task for {ticker} complete! Return: {round(total_return * 100, 2)}%")

    except BacktestError as e:
        print(f"Backtest pipeline failed for {ticker}: {e}")
    except Exception as e:
        print(f"UNEXPECTED crash in background thread for {ticker}: {e}")
    finally:
        thread_conn.close()
        print("Background thread closed its SQLite connection.")


@app.route('/api/run-backtest', methods=['POST'])
@limiter.limit("10 per minute")
@require_api_key
def trigger_backtest():
    try:
        payload = request.get_json(force=False)
    except Exception:
        return error_response("Request body is not valid JSON.", 400)

    is_valid, parsed_data = validate_payload(payload)
    if not is_valid:
        return error_response(parsed_data, 400)

    ticker = parsed_data['ticker']
    fast = parsed_data['fast']
    slow = parsed_data['slow']

    try:
        # FIX: .copy() here is what actually kills the race condition —
        # every request now mutates its own private DataFrame, never the
        # shared master copy in `prepared_data`, and never another
        # concurrent request's copy.
        executor.submit(run_backtest_task, ticker, prepared_data[ticker].copy(), fast, slow)
    except Exception as e:
        # FIX: log the real exception server-side, but never leak it to
        # the client — matches every other 500 path in this file.
        print(f"Failed to schedule backtest: {e}")
        return error_response("Internal server error.", 500)

    return jsonify({
        "status": "processing",
        "ticker": ticker,
        "message": "Backtest submitted to background worker. Check your terminal for results."
    }), 202


@app.errorhandler(404)
def not_found(e):
    return error_response("Endpoint not found.", 404)


@app.errorhandler(405)
def method_not_allowed(e):
    return error_response("HTTP method not allowed on this endpoint.", 405)


@app.errorhandler(429)
def rate_limit_exceeded(e):
    return error_response("Rate limit exceeded. Try again in a minute.", 429)


@app.errorhandler(500)
def internal_error(e):
    return error_response("Internal server error.", 500)


if __name__ == '__main__':
    app.run(port=5000, debug=True)