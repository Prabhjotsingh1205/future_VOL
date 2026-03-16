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
        df = groww.get_all_instruments()
    except Exception as e:
        print(f"SDK method failed: {e}. Attempting to download CSV directly.")
        df = pd.read_csv("https://growwapi-assets.groww.in/instruments/instrument.csv", low_memory=False)
    return df

def fetch_and_store_stock_data(groww, conn, stocks):
    """Fetches and stores historical EOD data for stocks."""
    print(f"Fetching historical data for {len(stocks)} FNO-eligible stocks...")
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
                interval_in_minutes=1440
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

            time.sleep(0.05)
        except Exception as e:
            print(f"Error fetching stock {exchange}:{symbol}: {e}")

def fetch_and_store_future_data(groww, conn, futures):
    """Fetches and stores historical EOD data for futures (last 20 days)."""
    print(f"Fetching historical data for {len(futures)} future contracts...")
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
                interval_in_minutes=1440
            )

            if 'candles' in response and response['candles']:
                candles = response['candles']
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

    # 1. Identify stocks that are in FNO segment
    # Filter NSE futures only to avoid BSE duplication if not needed,
    # but the user said "only those stocks who are in FNO segment".
    # Most FNO stocks are on NSE.
    fno_futures = df[(df['segment'] == 'FNO') & (df['instrument_type'] == 'FUT')]
    fno_underlyings = fno_futures['underlying_symbol'].dropna().unique()

    print(f"Found {len(fno_underlyings)} unique underlying symbols in FNO Futures.")

    # 2. Filter 'CASH' segment for only these underlyings, specifically NSE
    # This usually yields around 200+ stocks as the user suggested.
    stocks_in_fno = df[(df['segment'] == 'CASH') &
                       (df['trading_symbol'].isin(fno_underlyings)) &
                       (df['exchange'] == 'NSE')].copy()

    print(f"Filtered {len(stocks_in_fno)} NSE stocks from CASH segment that are FNO-eligible.")

    # 3. Filter Stock Futures (current and next expiry)
    # We include all futures for these underlyings
    futures_df = fno_futures[fno_futures['underlying_symbol'].isin(fno_underlyings)].copy()

    # Identify current and next expiry
    today = datetime.now().strftime('%Y-%m-%d')
    all_expiries = sorted(futures_df['expiry_date'].dropna().unique())
    future_expiries = [e for e in all_expiries if e >= today]

    if len(future_expiries) < 2:
        selected_expiries = future_expiries
    else:
        selected_expiries = future_expiries[:2]

    print(f"Selected Expiries for Futures: {selected_expiries}")
    filtered_futures = futures_df[futures_df['expiry_date'].isin(selected_expiries)].copy()

    # 4. Initialize Database
    conn = setup_db()

    # 5. Fetch and store data
    fetch_and_store_stock_data(groww, conn, stocks_in_fno)
    fetch_and_store_future_data(groww, conn, filtered_futures)

    conn.close()
    print(f"Job completed. Data saved in {DB_NAME}")

if __name__ == "__main__":
    main()
