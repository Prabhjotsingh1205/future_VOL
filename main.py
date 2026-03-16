import pandas as pd
import sqlite3
from datetime import datetime, timedelta
import time
import os
from auth import get_groww_client

# Database name
DB_NAME = "groww_data.db"

def setup_db():
    """Initializes the SQLite database and creates tables if they don't exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Table for Stock Historical Data (EOD)
    # Added exchange to Primary Key to avoid collisions between NSE/BSE
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS stock_history (
        exchange TEXT,
        trading_symbol TEXT,
        timestamp INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (exchange, trading_symbol, timestamp)
    )
    ''')

    # Table for Future Historical Data (EOD)
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS future_history (
        exchange TEXT,
        trading_symbol TEXT,
        expiry_date TEXT,
        timestamp INTEGER,
        open REAL,
        high REAL,
        low REAL,
        close REAL,
        volume INTEGER,
        PRIMARY KEY (exchange, trading_symbol, expiry_date, timestamp)
    )
    ''')

    conn.commit()
    return conn

def get_instruments(groww):
    """Fetches all tradable instruments from Groww."""
    print("Fetching all instruments...")
    try:
        # Preferred way using SDK
        df = groww.get_all_instruments()
    except Exception as e:
        print(f"SDK method failed: {e}. Attempting to download CSV directly.")
        # Fallback to direct CSV download
        df = pd.read_csv("https://growwapi-assets.groww.in/instruments/instrument.csv")
    return df

def fetch_and_store_stock_data(groww, conn, stocks):
    """Fetches and stores historical EOD data for stocks."""
    print(f"Fetching historical data for {len(stocks)} stocks...")
    # Fetch last 30 days of EOD data for stocks by default
    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time = (datetime.now() - timedelta(days=30)).strftime('%Y-%m-%d %H:%M:%S')

    for _, stock in stocks.iterrows():
        symbol = stock['trading_symbol']
        exchange = stock['exchange']
        try:
            response = groww.get_historical_candle_data(
                trading_symbol=symbol,
                exchange=exchange,
                segment=stock['segment'],
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=1440 # Daily/EOD
            )

            if 'candles' in response and response['candles']:
                candles = response['candles']
                data_to_insert = [(exchange, symbol, c[0], c[1], c[2], c[3], c[4], c[5]) for c in candles]
                conn.executemany('''
                INSERT OR REPLACE INTO stock_history
                (exchange, trading_symbol, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                conn.commit()
                print(f"Stored {len(candles)} candles for stock: {exchange}:{symbol}")

            time.sleep(0.05) # Gentle rate limiting
        except Exception as e:
            print(f"Error fetching stock {exchange}:{symbol}: {e}")

def fetch_and_store_future_data(groww, conn, futures):
    """Fetches and stores historical EOD data for futures (last 20 days)."""
    print(f"Fetching historical data for {len(futures)} future contracts...")
    # User requested last 20 days
    end_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    start_time = (datetime.now() - timedelta(days=20)).strftime('%Y-%m-%d %H:%M:%S')

    for _, future in futures.iterrows():
        symbol = future['trading_symbol']
        exchange = future['exchange']
        expiry = future['expiry_date']
        try:
            response = groww.get_historical_candle_data(
                trading_symbol=symbol,
                exchange=exchange,
                segment=future['segment'],
                start_time=start_time,
                end_time=end_time,
                interval_in_minutes=1440 # Daily/EOD
            )

            if 'candles' in response and response['candles']:
                candles = response['candles']
                # volume is the last element (index 5) in the candle array
                data_to_insert = [(exchange, symbol, expiry, c[0], c[1], c[2], c[3], c[4], c[5]) for c in candles]
                conn.executemany('''
                INSERT OR REPLACE INTO future_history
                (exchange, trading_symbol, expiry_date, timestamp, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', data_to_insert)
                conn.commit()
                print(f"Stored {len(candles)} candles for future: {exchange}:{symbol} (Exp: {expiry})")

            time.sleep(0.05)
        except Exception as e:
            print(f"Error fetching future {exchange}:{symbol}: {e}")

def main():
    groww = get_groww_client()
    df = get_instruments(groww)

    # 1. Filter all stocks (CASH segment)
    stocks = df[df['segment'] == 'CASH'].copy()

    # 2. Filter Stock Futures (FNO segment, instrument_type might be FUTSTK or others depending on API)
    # Typically FUTSTK for individual stock futures, FUTIDX for index futures.
    # We filter where segment is FNO and name/trading_symbol suggests it's a future and NOT an option.
    # Based on docs, FUTSTK and FUTIDX are common.
    futures_df = df[(df['segment'] == 'FNO') & (df['instrument_type'].str.contains('FUT', na=False))].copy()

    # 3. Identify current and next expiry
    today = datetime.now().strftime('%Y-%m-%d')
    all_expiries = sorted(futures_df['expiry_date'].dropna().unique())
    # Recent two expiries: Always two expiry which has current expiry.
    # We take the first two expiries that are >= today.
    future_expiries = [e for e in all_expiries if e >= today]

    if len(future_expiries) < 2:
        print(f"Only found {len(future_expiries)} upcoming expiries: {future_expiries}")
        selected_expiries = future_expiries
    else:
        selected_expiries = future_expiries[:2]

    print(f"Selected Expiries for Futures: {selected_expiries}")
    filtered_futures = futures_df[futures_df['expiry_date'].isin(selected_expiries)].copy()

    # 4. Initialize Database
    conn = setup_db()

    # 5. Fetch and store data
    fetch_and_store_stock_data(groww, conn, stocks)
    fetch_and_store_future_data(groww, conn, filtered_futures)

    conn.close()
    print(f"Job completed. Data saved in {DB_NAME}")

if __name__ == "__main__":
    main()
