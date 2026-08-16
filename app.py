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
executor = ThreadPoolExecutor(max_workers=4)

db_lock = threading.Lock()


# ============================================================
# DAY 14 — API KEY AUTH
# ============================================================
#
# NEW: os.environ.get(...) instead of a hardcoded string.
# Why: this is a taste of Day 15 (env vars) early, for one specific reason —
# an API key is a SECRET. If we hardcode it as a plain string right here in
# app.py, and this file ever gets pushed to a public GitHub repo (which it
# will, for your portfolio), the secret is now public forever, sitting in
# your git history even if you delete it later in a future commit.
# The fallback ("dev-key-change-me") only exists so the app doesn't crash
# on your local machine if you forget to set the env var — it's obviously
# not meant for anything real. We print a loud warning if it's being used.
API_KEY = os.environ.get("API_KEY", "dev-key-change-me")
if API_KEY == "dev-key-change-me":
    print("⚠️  WARNING: Using default dev API key. Set the API_KEY environment "
          "variable before deploying anywhere real.")


def require_api_key(f):
    # NEW: functools.wraps(f)
    # Why: without this, Flask breaks — not with a vague error, but a very
    # specific one. Flask identifies each route internally by the wrapped
    # function's __name__. If you decorate two different routes with the
    # same undecorated wrapper, both routes' internal name becomes "wrapped",
    # and Flask raises "View function mapping is overwriting an existing
    # endpoint function." functools.wraps copies the ORIGINAL function's
    # name (and docstring, etc.) onto the wrapper, so Flask still sees
    # "trigger_backtest", not "wrapped".
    # The one sentence to remember
    # @functools.wraps(f) isn't magic — it's just "relabel this wrapper with the original function's real name," and it exists purely because Flask breaks without it the moment you reuse one decorator on more than one route.
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        # NEW: reading a custom header, not query params or the JSON body.
        # Why headers and not, say, ?api_key=xyz in the URL: URLs get logged
        # everywhere — browser history, server access logs, proxy logs.
        # A key sitting in a URL leaks into places you don't control.
        # Headers aren't logged by default the same way.
        provided_key = request.headers.get("X-API-Key")

        # CHANGED: one condition, one response, instead of two separate
        # branches with two separate messages.
        # Why: this is the fix for a real bug — the previous version returned
        # "Missing X-API-Key header." when the header was absent, and a
        # DIFFERENT message ("Invalid or missing API key.") when it was
        # present but wrong. That's a leak: an attacker probing the endpoint
        # could tell "no key" apart from "wrong key" just by reading the
        # message, which confirms the header name is right and a key system
        # exists at all — information they shouldn't get for free. Collapsing
        # both cases into one condition guarantees they're indistinguishable.
        if provided_key is None or provided_key != API_KEY:
            return error_response("Invalid or missing API key.", 401)

        return f(*args, **kwargs)

    return decorated


# ============================================================
# DAY 14 — RATE LIMITING
# ============================================================
#
# NEW: key_func=get_remote_address
# Why: flask-limiter needs to know WHO to count requests against. This
# function returns the caller's IP address, so the limiter keeps a separate
# counter PER IP. Without this, it would either refuse to run or (with the
# wrong key_func) count every request from every user as if they were the
# same person — meaning one person could exhaust the limit for everyone else.
#
# NEW: default_limits=[]
# Why: this means "don't apply any limit automatically to every route."
# We only want the expensive route (the one doing real work — pandas math +
# a DB write) to be limited. Being explicit with @limiter.limit(...) per
# route, instead of one blanket limit on everything, means a lightweight
# route later (like a health check) doesn't get throttled for no reason.
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
            db_lock=db_lock
        )
        bot.run_full_pipeline()

        total_return = bot.df['Algo_Cumulative'].iloc[-1] - 1
        print(f"✅ Background task for {ticker} complete! Return: {round(total_return * 100, 2)}%")

    except BacktestError as e:
        print(f"❌ Backtest pipeline failed for {ticker}: {e}")
    except Exception as e:
        print(f"❌ UNEXPECTED crash in background thread for {ticker}: {e}")
    finally:
        thread_conn.close()
        print(f"🔒 Background thread closed its SQLite connection.")


# CHANGED: two new decorators stacked on top of the route.
#
# Why THIS order specifically (top to bottom = outermost to innermost):
#   @app.route(...)          <- Flask's own routing, always outermost
#   @limiter.limit(...)      <- runs FIRST, before we even check the API key
#   @require_api_key         <- runs SECOND, only if not rate-limited
#   def trigger_backtest...  <- runs LAST, only if both checks pass
#
# Decorators wrap bottom-up but EXECUTE top-down at request time:
# @a @b def f() is really f = a(b(f)), so when a request comes in, a's
# wrapper code runs first, and only if it decides to proceed does it call
# into b's wrapper.
#
# Why rate-limit BEFORE checking the API key, not after:
# if we checked the API key first, someone could send thousands of guesses
# at the key with zero limit on how fast they can try — the auth check
# would reject each one individually, but nothing would ever slow them down.
# By rate-limiting first, even wrong-key attempts count against that IP's
# 10-per-minute budget, so brute-forcing the key becomes impractically slow.
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
        executor.submit(run_backtest_task, ticker, prepared_data[ticker], fast, slow)
    except Exception as e:
        return error_response(f"Failed to schedule backtest: {e}", 500)

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


# NEW: 429 = "Too Many Requests". This is the status code flask-limiter
# raises internally when a caller goes over their limit.
# Why we still need this handler: without it, flask-limiter's DEFAULT
# response is a plain text/HTML page, not JSON — same problem as the
# 404/405 case in Day 12. Every error your API returns should have the
# same {"status": "error", "message": ...} shape, no exceptions, or
# whoever's writing the frontend has to special-case this one endpoint.
@app.errorhandler(429)
def rate_limit_exceeded(e):
    return error_response("Rate limit exceeded. Try again in a minute.", 429)


@app.errorhandler(500)
def internal_error(e):
    return error_response("Internal server error.", 500)


if __name__ == '__main__':
    app.run(port=5000, debug=True)