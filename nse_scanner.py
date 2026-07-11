import yfinance as yf
import pandas as pd
import numpy as np
import json
import os
import time
import requests
from datetime import datetime

DATA_FILE = "trading_alerts.json"
CSV_FILE = "watchlist.csv"

# ═══════════════════════════════════════════════════════════════════════
# STEALTH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})


def load_watchlist(filename=CSV_FILE):
    if not os.path.exists(filename):
        sample_df = pd.DataFrame({"Symbol": ["RELIANCE", "TATAMOTORS", "INFY", "SHAKTIPUMP"]})
        sample_df.to_csv(filename, index=False)
        return ["RELIANCE.NS", "TATAMOTORS.NS", "INFY.NS", "SHAKTIPUMP.NS"]

    try:
        df = pd.read_csv(filename)
        if df.empty: return []

        target_col = None
        for col in df.columns:
            if str(col).strip().lower() in ['symbol', 'ticker', 'stock', 'name']:
                target_col = col
                break

        if target_col is None:
            target_col = df.columns[0]

        raw_tickers = df[target_col].dropna().astype(str).tolist()
        processed_tickers = []

        for ticker in raw_tickers:
            clean_ticker = ticker.strip().upper()
            if clean_ticker and not clean_ticker.startswith('#'):
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
        df = yf.download(ticker, period="max", progress=False, session=session, auto_adjust=True)
        if df.empty or len(df) < 60:
            return None

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)

        df['EMA9'] = df['Close'].ewm(span=9, adjust=False).mean()
        df['EMA21'] = df['Close'].ewm(span=21, adjust=False).mean()
        df['ATR'] = calculate_atr(df, 14)

        daily_bull = df['EMA9'].iloc[-1] > df['EMA21'].iloc[-1]

        df_wk = df['Close'].resample('W-SUN').last().to_frame()
        df_wk['EMA9'] = df_wk['Close'].ewm(span=9, adjust=False).mean()
        df_wk['EMA21'] = df_wk['Close'].ewm(span=21, adjust=False).mean()
        wk_bull = df_wk['EMA9'].iloc[-1] > df_wk['EMA21'].iloc[-1]

        df_mo = df['Close'].resample('ME').last().to_frame()
        df_mo['EMA9'] = df_mo['Close'].ewm(span=9, adjust=False).mean()
        df_mo['EMA21'] = df_mo['Close'].ewm(span=21, adjust=False).mean()
        mo_bull = df_mo['EMA9'].iloc[-1] > df_mo['EMA21'].iloc[-1]

        if wk_bull and mo_bull:
            aligned_text = "ALIGNED ▲ LONGS"
            plan_text = "BUY pullbacks" if daily_bull else "low conviction — wait"
        elif wk_bull or mo_bull:
            aligned_text = "MIXED — WEAK EDGE"
            plan_text = "CAUTION: Low Conviction"
        else:
            aligned_text = "ALIGNED ▼ SHORTS"
            plan_text = "AVOID: Macro Downtrend"

        # ─────────────────────────────────────────────────────────────
        # STRICT STRUCTURE VALIDATION MATH
        # ─────────────────────────────────────────────────────────────
        recent_data = df.tail(60)

        # 1. Find the Highest Peak in the swing window
        max_idx = recent_data['High'].idxmax()
        impulse_high = recent_data.loc[max_idx, 'High']

        # 2. Find the true Origin (Lowest point strictly BEFORE the peak)
        pre_peak_data = recent_data.loc[:max_idx]
        impulse_low = pre_peak_data['Low'].min()
        diff = impulse_high - impulse_low

        # 3. Check for Structure Break (Did price crash below origin after the peak?)
        post_peak_data = recent_data.loc[max_idx:]
        structure_broken = post_peak_data['Low'].min() < impulse_low

        today = df.iloc[-1]
        yesterday = df.iloc[-2]

        # 🛡️ THE IMPENETRABLE FILTERS 🛡️
        # - structure_broken: Deletes crashed stocks.
        # - diff <= 0: Deletes downtrends (High happened at day 1, Low happened today).
        # - len(pre_peak_data) < 4: Deletes dead/flat structures.
        if structure_broken or diff <= 0 or len(pre_peak_data) < 4:
            signal_text = "⚪ FORMING"
        else:
            fib_382 = impulse_high - (diff * 0.382)
            fib_618 = impulse_high - (diff * 0.618)

            # Is it actively sitting inside the Amber Box?
            in_zone = fib_618 <= today['Close'] <= fib_382
            crossover = (today['EMA9'] > today['EMA21']) and (yesterday['EMA9'] <= yesterday['EMA21'])

            if in_zone and crossover:
                signal_text = "🟢 BUY TRIGGERED"
            elif in_zone and not crossover:
                signal_text = "🔵 IN BUY ZONE"
            elif crossover and not in_zone:
                signal_text = "🟡 WAIT FOR BUY ZONE"
            else:
                # If price is at 81% (too deep) or 20% (too shallow), it is ignored!
                signal_text = "⚪ FORMING"

        entry = float(today['Close'])
        sl = entry - (float(today['ATR']) * 2.0)
        risk = entry - sl

        return {
            "ticker": ticker.replace(".NS", ""),
            "action": signal_text,
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

    watchlist = load_watchlist()
    if not watchlist:
        print("❌ Watchlist is empty or could not be loaded. Exiting scan.")
        return

    existing_alerts = []
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                existing_alerts = json.load(f)
            except:
                existing_alerts = []

    alerts_dict = {a['ticker']: a for a in existing_alerts}
    found_setups = 0

    for ticker in watchlist:
        setup = scan_stock(ticker)

        if setup:
            # ─────────────────────────────────────────────────────────────
            # DASHBOARD PUBLISH LOGIC
            # ─────────────────────────────────────────────────────────────
            if setup['action'] in ["🟢 BUY TRIGGERED", "🔵 IN BUY ZONE", "🟡 WAIT FOR BUY ZONE"]:
                alerts_dict[setup['ticker']] = setup
                found_setups += 1
                print(f"   -> {setup['ticker']}: {setup['action']}")
            else:
                # Delete any stock that is outside the box or broken
                if setup['ticker'] in alerts_dict:
                    del alerts_dict[setup['ticker']]

        time.sleep(1.5)

    final_list = sorted(list(alerts_dict.values()), key=lambda x: x['ticker'])
    with open(DATA_FILE, "w") as f:
        json.dump(final_list, f, indent=4)

    today_date = datetime.now().strftime("%d %b %Y")
    print(f"✅ Scan complete. Total valid setups ({today_date}) is {len(final_list)}")


if __name__ == "__main__":
    run_screener()
