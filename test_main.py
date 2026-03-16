import unittest
from unittest.mock import MagicMock, patch
import pandas as pd
import sqlite3
import os
from main import setup_db, fetch_and_store_stock_data, fetch_and_store_future_data

class TestGrowwDataFetcher(unittest.TestCase):
    def setUp(self):
        self.db_name = "test_groww_data.db"
        if os.path.exists(self.db_name):
            os.remove(self.db_name)
        self.conn = sqlite3.connect(self.db_name)

    def tearDown(self):
        self.conn.close()
        if os.path.exists(self.db_name):
            os.remove(self.db_name)

    def test_setup_db(self):
        with patch('main.DB_NAME', self.db_name):
            conn = setup_db()
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
            tables = [row[0] for row in cursor.fetchall()]
            self.assertIn('stock_history', tables)
            self.assertIn('future_history', tables)

            # Check for exchange column in Primary Key
            cursor.execute("PRAGMA table_info(stock_history);")
            columns = {row[1]: row[5] for row in cursor.fetchall()}
            self.assertEqual(columns['exchange'], 1) # PK part
            self.assertEqual(columns['trading_symbol'], 2)
            self.assertEqual(columns['timestamp'], 3)
            conn.close()

    def test_fetch_and_store_stock_data(self):
        groww_mock = MagicMock()
        groww_mock.get_historical_candle_data.return_value = {
            'candles': [
                [1633072800, 150.0, 155.0, 145.0, 152.0, 10000]
            ]
        }

        # Initialize tables using the actual setup_db logic (with patched name)
        with patch('main.DB_NAME', self.db_name):
            conn = setup_db()

        stocks_df = pd.DataFrame([{
            'trading_symbol': 'RELIANCE',
            'exchange': 'NSE',
            'segment': 'CASH'
        }])

        fetch_and_store_stock_data(groww_mock, conn, stocks_df)

        cursor = conn.execute("SELECT * FROM stock_history")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'NSE')
        self.assertEqual(rows[0][1], 'RELIANCE')
        self.assertEqual(rows[0][7], 10000) # Volume
        conn.close()

    def test_fetch_and_store_future_data(self):
        groww_mock = MagicMock()
        groww_mock.get_historical_candle_data.return_value = {
            'candles': [
                [1633072800, 2500.0, 2510.0, 2490.0, 2505.0, 5000]
            ]
        }

        with patch('main.DB_NAME', self.db_name):
            conn = setup_db()

        futures_df = pd.DataFrame([{
            'trading_symbol': 'RELIANCE25MARFUT',
            'exchange': 'NSE',
            'segment': 'FNO',
            'expiry_date': '2025-03-27'
        }])

        fetch_and_store_future_data(groww_mock, conn, futures_df)

        cursor = conn.execute("SELECT * FROM future_history")
        rows = cursor.fetchall()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0][0], 'NSE')
        self.assertEqual(rows[0][1], 'RELIANCE25MARFUT')
        self.assertEqual(rows[0][2], '2025-03-27')
        self.assertEqual(rows[0][8], 5000) # Volume
        conn.close()

if __name__ == '__main__':
    unittest.main()
