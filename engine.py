import pandas as pd
import numpy as np
import sqlite3
import time
import os




# NEW: a custom exception class just for this engine.
# Why: right now, if pandas throws an error, or sqlite throws an error, they all
# look identical to whoever's calling this code — just "some Exception."
# By wrapping engine failures in our OWN exception type, calling code (app.py)
# can tell "this failed because of MY backtest logic" apart from
# "this failed because of something totally unrelated in Flask itself."
class BacktestError(Exception):
    """Raised when any step of the backtest pipeline fails."""
    pass


class BacktestEngine:
    def __init__(self, ticker_symbol, dataframe, db_connection,db_lock):
        self.ticker = ticker_symbol
        self.df = dataframe
        self.conn = db_connection
        self.cursor = self.conn.cursor()
        self.lock=db_lock

    def generate_signals(self, fast_window=10, slow_window=50):
        """Calculates moving averages and buy/sell signals."""
        # NEW: wrapped in try/except.
        # Why: this is pure pandas math. If someone passes a fast_window bigger
        # than the number of rows in the dataframe, or the dataframe is empty,
        # pandas won't always crash loudly — sometimes it just produces NaN columns
        # silently, and the real crash happens LATER in a confusing place.
        # Catching it here means the error message points at the actual cause.
        try:
            self.df['SMA_Fast'] = self.df['Close'].rolling(window=fast_window).mean()
            self.df['SMA_Slow'] = self.df['Close'].rolling(window=slow_window).mean()
            self.df['Signal'] = 0
            self.df.loc[self.df['SMA_Fast'] > self.df['SMA_Slow'], 'Signal'] = 1
            self.df.loc[self.df['SMA_Fast'] <= self.df['SMA_Slow'], 'Signal'] = -1
        except Exception as e:
            # NEW: "raise ... from e" instead of just "raise BacktestError(...)"
            # Why: "from e" keeps the ORIGINAL error attached as context.
            # If you print the traceback, you'll see both: your clean message,
            # AND the real underlying pandas error underneath it. You don't lose
            # the original clue while still giving the caller a clean message.
            raise BacktestError(f"generate_signals failed for {self.ticker}: {e}") from e

    def run_backtest(self):
        """Calculates returns and cumulative performance."""
        try:
            self.df['Stock_Returns'] = self.df['Close'].pct_change()
            self.df['Algo_Returns'] = self.df['Signal'].shift(1) * self.df['Stock_Returns']
            self.df['Stock_Cumulative'] = (1 + self.df['Stock_Returns']).cumprod()
            self.df['Algo_Cumulative'] = (1 + self.df['Algo_Returns']).cumprod()
        except Exception as e:
            raise BacktestError(f"run_backtest failed for {self.ticker}: {e}") from e

    def log_trades_safely(self):
        """Writes trade history to SQLite, protected by a global write lock."""
        state_change = self.df['Signal'].diff()
        trade_days = self.df[state_change != 0].dropna()
        trades_saved = 0

        with self.lock:
            try:
                for date, row in trade_days.iterrows():
                    if row['Signal'] == 1:
                        action = "BUY"
                    elif row['Signal'] == -1:
                        action = "SELL"
                    else:
                        continue

                    insert_query = "INSERT INTO trade_history (trade_date, ticker, action, price) VALUES (?, ?, ?, ?)"
                    self.cursor.execute(insert_query, (str(date.date()), self.ticker, action, row['Close']))
                    trades_saved += 1

                self.conn.commit()
                print(f"✅ VAULT LOCKED: {trades_saved} trades saved for {self.ticker}.")

            except Exception as e:
                self.conn.rollback()
                # CHANGED: this used to just print() the error and swallow it —
                # the function would return normally like nothing went wrong.
                # Why that was a bug: the caller (app.py) had NO WAY of knowing
                # the database write actually failed. It would happily report
                # "success" back to the user even though zero trades got saved.
                # Now we re-raise as BacktestError so the failure actually
                # propagates up and app.py is FORCED to handle it.
                raise BacktestError(f"log_trades_safely failed for {self.ticker}: {e}") from e

    def run_full_pipeline(self):
        """Runs the full sequence: signals -> backtest -> db write."""
        self.generate_signals()
        self.run_backtest()
        self.log_trades_safely()