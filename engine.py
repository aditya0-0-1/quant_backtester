import pandas as pd
import numpy as np
import sqlite3
import threading
import time
import os
# These are your tools. pandas and numpy handle the math. sqlite3 talks to the database. threading talks directly to your computer's CPU scheduler to create parallel processes. time tracks performance, and os handles file paths.


# ==========================================
# DAY 6: MULTITHREADED ARCHITECTURE
# ==========================================    

# 1. THE BOUNCER: Global Mutex Lock for the Database

class BacktestEngine:


    def __init__(self, ticker_symbol, dataframe, db_connection,db_lock):#add db_lock on d11
        """1. DAY 6 INIT: Bypasses OS limits and uses Dependency Injection"""
        self.ticker = ticker_symbol
        self.df = dataframe 
        self.conn = db_connection
        self.cursor = self.conn.cursor()
        self.lock=db_lock   #added this on d11

    def generate_signals(self, fast_window=10, slow_window=50):
        """2. The Logic Module (Math in RAM - Unchanged)"""
        self.df['SMA_Fast'] = self.df['Close'].rolling(window=fast_window).mean()
        self.df['SMA_Slow'] = self.df['Close'].rolling(window=slow_window).mean()
        self.df['Signal'] = 0
        self.df.loc[self.df['SMA_Fast'] > self.df['SMA_Slow'], 'Signal'] = 1
        self.df.loc[self.df['SMA_Fast'] <= self.df['SMA_Slow'], 'Signal'] = -1

    def run_backtest(self):
        """3. The Math Module (Math in RAM - Unchanged)"""
        self.df['Stock_Returns'] = self.df['Close'].pct_change()
        self.df['Algo_Returns'] = self.df['Signal'].shift(1) * self.df['Stock_Returns']
        self.df['Stock_Cumulative'] = (1 + self.df['Stock_Returns']).cumprod()
        self.df['Algo_Cumulative'] = (1 + self.df['Algo_Returns']).cumprod()

    def log_trades_safely(self):
        """4. DAY 6 CONCURRENCY: Safe Database Writing with Mutex Locks"""
        state_change = self.df['Signal'].diff()
        trade_days = self.df[state_change != 0].dropna()
        trades_saved = 0
        
        # The OS Lab Wait() / Signal() command is automated by 'with'
        with self.lock:#added on day11 previously had with db_lock
            try:
                # 💥 CRITICAL SECTION
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
                    
                # The Trigger: Commit only if the entire loop succeeds
                self.conn.commit()
                print(f"✅ VAULT LOCKED: {trades_saved} trades saved for {self.ticker}.")
                
            except Exception as e:
                # EMERGENCY BRAKES
                self.conn.rollback()
                print(f"❌ CRASH ON {self.ticker}: {e}. Rolling back ledger.")

    def run_full_pipeline(self):
        """5. THE THREAD TARGET: Runs math then logs to DB"""
        self.generate_signals()
        self.run_backtest()
        self.log_trades_safely()

# ==========================================
# THE IGNITION SCRIPT (MASTER PROCESS)
# ==========================================
if __name__ == "__main__":
    print("🚀 INITIATING DAY 6 MULTITHREADED ENGINE...")
    start_time = time.time()

    # 1. ONE SHARED CONNECTION (Dependency Injection)
    # check_same_thread=False allows multiple bots to share this one connection
    master_conn = sqlite3.connect("trading_ledger.db", check_same_thread=False)
    cursor = master_conn.cursor()
    
    # 2. MASTER SCHEMA SETUP (Built once by the master, not 500 times by bots)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS trade_history (
        trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
        trade_date TEXT,
        ticker TEXT,
        action TEXT,
        price REAL
    )
    """)
    master_conn.commit()

    # 3. BYPASSING ulimit (Loading data into RAM sequentially)
    # We will simulate having 3 different stocks using your existing CSV to test concurrency
    tickers = ["AAPL", "TSLA", "MSFT"] 
    prepared_data = {}
    
    filepath = 'data/historical_prices.csv'
    if not os.path.exists(filepath):
        print(f"❌ ERROR: Put your Day 1 CSV in {filepath}")
        exit()

    print("📂 Loading datasets into RAM...")
    for ticker in tickers:
        df = pd.read_csv(filepath, header=0, skiprows=[1,2])
        df.rename(columns={'Price': 'Date'}, inplace=True)
        df['Date'] = pd.to_datetime(df['Date'])
        df.set_index('Date', inplace=True)
        prepared_data[ticker] = df

    # 4. SPAWN THE THREADS
    active_threads = []
    print("⚙️ Unleashing the bots...")
    
    for ticker in tickers:
        # Inject the RAM data and the Shared Connection
        bot = BacktestEngine(ticker, prepared_data[ticker], master_conn)
        
        # Target the full pipeline (Math -> Database)
        t = threading.Thread(target=bot.run_full_pipeline)
        active_threads.append(t)
        
        # Hit the gas
        t.start()

    # 5. THE WAITING ROOM
    for t in active_threads:
        t.join() # Freezes the main script until all bots report back

    # 6. SHUTDOWN
    master_conn.close()
    
    print(f"🏁 DAY 6 COMPLETE in {time.time() - start_time:.2f} seconds. All threads safely executed.")