import pandas as pd
import numpy as np
import sqlite3
import time
import os


class BacktestError(Exception):
    """Raised when any step of the backtest pipeline fails."""
    pass


class BacktestEngine:
    def __init__(self, ticker_symbol, dataframe, db_connection, db_lock):
        self.ticker = ticker_symbol
        self.df = dataframe
        self.conn = db_connection
        self.cursor = self.conn.cursor()
        self.lock = db_lock

    def generate_signals(self, fast_window=10, slow_window=50):
        """Calculates moving averages and buy/sell signals."""
        try:
            self.df['SMA_Fast'] = self.df['Close'].rolling(window=fast_window).mean()
            self.df['SMA_Slow'] = self.df['Close'].rolling(window=slow_window).mean()
            self.df['Signal'] = 0
            self.df.loc[self.df['SMA_Fast'] > self.df['SMA_Slow'], 'Signal'] = 1
            self.df.loc[self.df['SMA_Fast'] <= self.df['SMA_Slow'], 'Signal'] = -1
        except Exception as e:
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
                print(f"VAULT LOCKED: {trades_saved} trades saved for {self.ticker}.")

            except Exception as e:
                self.conn.rollback()
                raise BacktestError(f"log_trades_safely failed for {self.ticker}: {e}") from e

    # FIX: now accepts fast_window/slow_window and forwards them to
    # generate_signals(). Previously this always called generate_signals()
    # with zero args, so every request silently ran with the hardcoded
    # defaults (10, 50) no matter what the client sent — a user could ask
    # for a 20/100 crossover, get a 202 "processing" response, and receive
    # numbers computed with 10/50 instead. Silent wrong answers are worse
    # than crashes; this is the fix that matters most in this file.
    def run_full_pipeline(self, fast_window=10, slow_window=50):
        """Runs the full sequence: signals -> backtest -> db write."""
        self.generate_signals(fast_window, slow_window)
        self.run_backtest()
        self.log_trades_safely()