import streamlit as st
import json
import pandas as pd
import time
import os
from datetime import datetime

st.set_page_config(page_title="NSE Setup Tracker", layout="wide")
st.title("🎯 High-Probability Setup Dashboard")

DATA_FILE = "trading_alerts.json"

def load_alerts():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r") as f:
            try:
                return json.load(f)
            except:
                return []
    return []

# 1. Load Data
alerts = load_alerts()

if alerts:
    df = pd.DataFrame(alerts)
    
    # Background Engine Filters (Hidden from UI)
    df = df[~df['action'].str.contains("FORMING|VOID", case=False, na=False)]
    
    if 'time_received' in df.columns and not df.empty:
        df['time_received'] = pd.to_datetime(df['time_received'])
        latest_date = df['time_received'].dt.date.max()
        df = df[df['time_received'].dt.date == latest_date]
    
    if not df.empty:
        # ─────────────────────────────────────────────────────────────
        # 2. INTERACTIVE UI FILTERS
        # ─────────────────────────────────────────────────────────────
        st.markdown("### 🔍 Quick Filters")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            signal_filter = st.multiselect("Signal", options=df['action'].unique(), default=df['action'].unique())
        with col2:
            mtf_filter = st.multiselect("MTF Alignment", options=df['aligned'].unique(), default=df['aligned'].unique())
        with col3:
            plan_filter = st.multiselect("Trade Plan", options=df['plan'].unique(), default=df['plan'].unique())

        # Apply the selections to the dataframe
        filtered_df = df[
            (df['action'].isin(signal_filter)) & 
            (df['aligned'].isin(mtf_filter)) & 
            (df['plan'].isin(plan_filter))
        ]
        
        # 3. Dynamic Header based on FILTERED results
        display_date = latest_date.strftime("%d %b %Y")
        st.markdown(
            f"Monitoring for EMA Crossovers inside Fibonacci Impulse Zones. &nbsp;&nbsp;&nbsp; "
            f"<span style='color:#ff4b4b; font-weight:bold;'>Total scan ({display_date}) is {len(filtered_df)}</span>", 
            unsafe_allow_html=True
        )
        
        # 4. Display the Table
        st.dataframe(
            filtered_df,
            column_config={
                "ticker": st.column_config.TextColumn("Stock", width="medium"),
                "action": st.column_config.TextColumn("Signal", width="small"),
                "entry": st.column_config.NumberColumn("Entry (₹)", format="%.2f"),
                "sl": st.column_config.NumberColumn("Stop Loss (₹)", format="%.2f"),
                "tp1": st.column_config.NumberColumn("TP1 (₹)", format="%.2f"),
                "tp2": st.column_config.NumberColumn("TP2 (₹)", format="%.2f"),
                "tp3": st.column_config.NumberColumn("TP3 (₹)", format="%.2f"),
                "aligned": st.column_config.TextColumn("MTF Alignment", width="medium"),
                "plan": st.column_config.TextColumn("Trade Plan", width="medium"),
                "time_received": st.column_config.DatetimeColumn("Trigger Time", format="D MMM YYYY, h:mm a")
            },
            hide_index=True,
            use_container_width=True
        )
    else:
        st.info("Scan complete. No active setups found in the Buy Zone today. 📡")
else:
    st.info("Waiting for market data... Run the Python Screener to update targets. 📡")

# ─────────────────────────────────────────────────────────────
# 5. SMART AUTO-REFRESH LOOP
# ─────────────────────────────────────────────────────────────
# This pauses for 5 seconds, then safely reruns the app without breaking UI inputs
time.sleep(5)
st.rerun()
