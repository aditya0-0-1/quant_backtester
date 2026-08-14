from flask import Flask, request, jsonify
import sqlite3
import pandas as pd
import os
import threading
from concurrent.futures import ThreadPoolExecutor

from engine import BacktestEngine, BacktestError

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=4)

# The lock now lives here, at the app level — where it's created ONCE and
# handed to every BacktestEngine instance that gets built. This is the
# injection point: app.py owns the lock's lifecycle, engine.py just uses
# whatever it's given.
db_lock = threading.Lock()


# NEW: one function that builds every error response.
# Why: before this, every route built its own jsonify({"status": "error", ...})
# by hand, with slightly different keys/wording each time. If a frontend dev
# (future you) is checking `if data.status === "error"`, ANY inconsistency here
# breaks that check silently. One function = one guaranteed shape, everywhere.
def error_response(message, status_code=400):
    return jsonify({"status": "error", "message": message}), status_code


# FIX: get_db() was dead code — nothing called it anymore since Day 11 moved
# to background workers that open their own connection directly. That meant
# CREATE TABLE never actually ran, and every fresh database would fail with
# "no such table: trade_history" on the very first backtest.
# This runs ONCE, at import time (server startup), so the table always
# exists before any request can possibly hit the database.
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
    print(f"❌ ERROR: Cannot find {filepath}")

df = pd.read_csv(filepath, header=0, skiprows=[1, 2])
df.rename(columns={'Price': 'Date'}, inplace=True)
df['Date'] = pd.to_datetime(df['Date'])
df.set_index('Date', inplace=True)

prepared_data = {
    "AAPL": df,
    "TSLA": df.copy(),
    "MSFT": df.copy()
}


def validate_payload(data):
    """Ensures the JSON payload is safe before running math."""
    if not data or 'ticker' not in data:
        return False, "Missing 'ticker' in payload."

    ticker = str(data['ticker']).upper()
    if ticker not in prepared_data:
        return False, f"Ticker {ticker} not found in database."

    fast = data.get('fast_window', 10)
    slow = data.get('slow_window', 50)

    # if not isinstance(fast, int) or not isinstance(slow, int) or fast <= 0 or slow <= 0:
    #     return False, "Windows must be positive integers."
    # instead of this if type(fast) is not int or type(slow) is not int or fast <= 0 or slow <= 0:
    # Why type(x) is not int instead of isinstance: isinstance(True, int) returns True because bool is a subclass of int in Python — isinstance says "yes" to anything in that whole family tree. type(x) is int is stricter — it asks "is this literally, exactly the int type, not some subclass pretending to be one?" type(True) is int returns False, because the type of True is bool, not int. That's the fix.
    if type(fast) is not int or type(slow) is not int or fast <= 0 or slow <= 0:
         return False, "Windows must be positive integers."
    
    if fast >= slow:
        return False, "Fast window must be strictly less than slow window."

    return True, {"ticker": ticker, "fast": fast, "slow": slow}


def run_backtest_task(ticker, df_data, fast, slow):
    """Background worker: runs the full pipeline in its own thread/connection."""
    print(f"⚙️ Background thread started for {ticker}...")
    thread_conn = sqlite3.connect("trading_ledger.db")

    try:
        bot = BacktestEngine(
            ticker_symbol=ticker,
            dataframe=df_data,
            db_connection=thread_conn,
            db_lock=db_lock  # same injection pattern as db_connection
        )
        bot.run_full_pipeline()

        total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1
        print(f"✅ Background task for {ticker} complete! Return: {round(total_return * 100, 2)}%")

    # CHANGED: split into two except blocks instead of one generic one.
    # Why: BacktestError means "something inside OUR pipeline failed in a way
    # we already understand and labeled" (bad math, bad db write). A bare
    # Exception could ALSO mean something we never anticipated at all —
    # like the disk running out of space, or a completely unrelated bug.
    # Separating them means your logs immediately tell you which category
    # you're dealing with, instead of every failure looking identical.
    except BacktestError as e:
        print(f"❌ Backtest pipeline failed for {ticker}: {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED crash in background thread for {ticker}: {e}")
    finally:
        thread_conn.close()
        print(f"🔒 Background thread closed its SQLite connection.")


@app.route('/api/run-backtest', methods=['POST'])
def trigger_backtest():
    # NEW: try/except around request.get_json() itself.
    # Why: if the client sends a POST with a broken/malformed JSON body
    # (missing a closing brace, wrong Content-Type, empty body), get_json()
    # can raise an exception BEFORE your code even reaches validate_payload.
    # Previously this would crash as an unhandled 500 with no clean message.
    try:
        payload = request.get_json(force=False)
    except Exception:
        return error_response("Request body is not valid JSON.", 400)

    is_valid, parsed_data = validate_payload(payload)
    if not is_valid:
        # CHANGED: now uses the shared error_response() helper
        # instead of hand-building jsonify each time.
        return error_response(parsed_data, 400)

    ticker = parsed_data['ticker']
    fast = parsed_data['fast']
    slow = parsed_data['slow']

    # NEW: try/except around submitting to the executor.
    # Why: executor.submit() itself can fail — for example, if the thread
    # pool has been shut down, or the process is out of resources. This is
    # rare, but "the code that KICKS OFF the background job" failing is
    # different from "the background job itself" failing, and deserves
    # its own handling so the client gets a real answer either way.
    try:
        executor.submit(run_backtest_task, ticker, prepared_data[ticker], fast, slow)
    except Exception as e:
        return error_response(f"Failed to schedule backtest: {e}", 500)

    return jsonify({
        "status": "processing",
        "ticker": ticker,
        "message": "Backtest submitted to background worker. Check your terminal for results."
    }), 202


# NEW: global error handlers.
# Why: these catch errors Flask ITSELF raises before your route code ever runs —
# like hitting a URL that doesn't exist (404), or sending the wrong HTTP method
# to a route (405). Without these, Flask's DEFAULT behavior is to return its
# own generic HTML error page — not JSON. For an API, that's wrong: every
# client talking to you expects JSON back, even for errors.
@app.errorhandler(404)
def not_found(e):
    return error_response("Endpoint not found.", 404)

# 2. The 405 Alarm (Wrong Method)
# Your route has @app.route('/api/run-backtest', methods=['POST']). You explicitly demanded a POST request.

# If a user just pastes http://localhost:5000/api/run-backtest into their Chrome browser and hits Enter, browsers always send a GET request.

# Flask acts like a bouncer at a club. It sees the GET request, says "You aren't on the list," and blocks them before they ever reach your code.

# Flask pulls the 405 alarm and automatically calls your method_not_allowed function.
@app.errorhandler(405)
def method_not_allowed(e):
    return error_response("HTTP method not allowed on this endpoint.", 405)


@app.errorhandler(500)
def internal_error(e):
    # NEW: this is the final safety net. If ANY route anywhere raises an
    # exception you didn't explicitly catch, Flask funnels it here instead
    # of leaking a raw Python traceback (with file paths, line numbers,
    # variable contents) to whoever's calling your API.
    return error_response("Internal server error.", 500)


if __name__ == '__main__':
    app.run(port=5000, debug=True)
 