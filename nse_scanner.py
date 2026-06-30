import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime

DATA_FILE = "trading_alerts.json"
CSV_FILE = "watchlist.csv"


def load_watchlist(filename=CSV_FILE):
    """Loads tickers from a CSV file and automatically ensures the .NS suffix."""
    # If the CSV file doesn't exist yet, create a sample one automatically
    if not os.path.exists(filename):
        sample_df = pd.DataFrame({"Symbol": ["RELIANCE", "TATAMOTORS", "INFY", "SHAKTIPUMP"]})
        sample_df.to_csv(filename, index=False)
        print(f"⚠️ Created a template '{filename}'. Please open it and add your stocks!")
        return ["RELIANCE.NS", "TATAMOTORS.NS", "INFY.NS", "SHAKTIPUMP.NS"]

    try:
        df = pd.read_csv(filename)
        if df.empty:
            print(f"⚠️ '{filename}' is empty. Please add tickers to it.")
            return []

        # Detect which column holds the tickers (looks for common headers case-insensitively)
        target_col = None
        for col in df.columns:
            if str(col).strip().lower() in ['symbol', 'ticker', 'stock', 'name']:
                target_col = col
                break

        # If no known column header is found, default to using the very first column
        if target_col is None:
            target_col = df.columns[0]

        raw_tickers = df[target_col].dropna().astype(str).tolist()
        processed_tickers = []

        for ticker in raw_tickers:
            clean_ticker = ticker.strip().upper()
            if clean_ticker and not clean_ticker.startswith('#'):  # Skip blank lines or comments
                if not clean_ticker.endswith('.NS'):
                    clean_ticker = f"{clean_ticker}.NS"
                processed_tickers.append(clean_ticker)

        return processed_tickers

    except Exception as e:
        print(f"❌ Error reading '{filename}': {e}")
        return []


def calculate_atr(df, period=14):
    high_low = df['High'] - df['Low']
    high_close = np.abs(df['High'] - df['Close'].shift())
    low_close = np.abs(df['Low'] - df['Close'].shift())
    ranges = pd.concat([high_low, high_close, low_close], axis=1)
    return np.max(ranges, axis=1).rolling(period).mean()


def scan_stock(ticker):
    try:
        df = yf.download(ticker, period="2y", progress=False)
        if df.empty or len(df) < 30:
            return None

        # Robust multi-index column fix to prevent terminal formatting crashes
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        # 1. Daily Calculations
        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['ATR'] = calculate_atr(df, 14)

        # 2. Weekly Calculations (Resampling)
        df_wk = df['Close'].resample('W-SUN').last().to_frame()  # Updated to 'W-SUN'
        df_wk['EMA9'] = df_wk['Close'].ewm(span=9, adjust=False).mean()
        df_wk['EMA21'] = df_wk['Close'].ewm(span=21, adjust=False).mean()
        wk_bull = df_wk['EMA9'].iloc[-1] > df_wk['EMA21'].iloc[-1]

        # 3. Monthly Calculations (Resampling)
        df_mo = df['Close'].resample('ME').last().to_frame()  # Updated to 'ME'
        df_mo['EMA9'] = df_mo['Close'].ewm(span=9, adjust=False).mean()
        df_mo['EMA21'] = df_mo['Close'].ewm(span=21, adjust=False).mean()
        mo_bull = df_mo['EMA9'].iloc[-1] > df_mo['EMA21'].iloc[-1]

        # 4. Multi-Timeframe Alignment Logic
        if wk_bull and mo_bull:
            aligned_text = "ALIGNED ▲ LONGS"
            plan_text = "BUY pullbacks"
        elif wk_bull or mo_bull:
            aligned_text = "MIXED — WEAK EDGE"
            plan_text = "CAUTION: Low Conviction"
        else:
            aligned_text = "ALIGNED ▼ SHORTS"
            plan_text = "AVOID: Macro Downtrend"

        # 5. Impulse Logic (Look back 30 candles)
        recent_data = df.tail(30)
        impulse_high = recent_data['High'].max()
        impulse_low = recent_data['Low'].min()

        diff = impulse_high - impulse_low
        fib_382 = impulse_high - (diff * 0.382)
        fib_618 = impulse_high - (diff * 0.618)

        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        in_zone = fib_618 <= today['Close'] <= fib_382
        crossover = (today['EMA9'] > today['EMA21']) and (yesterday['EMA9'] <= yesterday['EMA21'])

        if in_zone and crossover:
            entry = float(today['Close'])
            sl = entry - (float(today['ATR']) * 2.0)
            risk = entry - sl

            return {
                "ticker": ticker.replace(".NS", ""),
                "action": "BUY",
                "entry": round(entry, 2),
                "sl": round(sl, 2),
                "tp1": round(entry + (risk * 1.0), 2),
                "tp2": round(entry + (risk * 2.0), 2),
                "tp3": round(entry + (risk * 3.0), 2),
                "aligned": aligned_text,
                "plan": plan_text,
                "time_received": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

    except Exception as e:
        print(f"Error analyzing {ticker}: {e}")
    return None


def run_screener():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Starting NSE Algorithmic Scan...")

    # Dynamically load the watchlist from the CSV file
    watchlist = load_watchlist()
    if not watchlist:
        print("❌ Watchlist is empty or could not be loaded. Exiting scan.")
        return

    if not os.path.exists(DATA_FILE):
        with open(DATA_FILE, "w") as f:
            json.dump([], f)

    with open(DATA_FILE, "r") as f:
        existing_alerts = json.load(f)

    found_setups = 0

    for ticker in watchlist:
        print(f"Scanning {ticker}...")
        setup = scan_stock(ticker)

        if setup:
            already_logged = any(
                a['ticker'] == setup['ticker'] and
                a['time_received'].split()[0] == setup['time_received'].split()[0]
                for a in existing_alerts
            )

            if not already_logged:
                existing_alerts.insert(0, setup)
                found_setups += 1
                print(f"🎯 MATCH: {setup['ticker']} ({setup['aligned']})")

    if found_setups > 0:
        with open(DATA_FILE, "w") as f:
            json.dump(existing_alerts, f, indent=4)
        print(f"✅ Scan complete. {found_setups} new setups pushed to Dashboard.")
    else:
        print("✅ Scan complete. No active setups found today.")


if __name__ == "__main__":
    run_screener()