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

# Placeholders for the dynamic header and table
header_placeholder = st.empty()
table_placeholder = st.empty()

while True:
    alerts = load_alerts()
    
    if alerts:
        df = pd.DataFrame(alerts)
        
        # 🛡️ THE BULLETPROOF UI FILTER 🛡️
        # Strictly hide any row that contains "FORMING" or "VOID"
        df = df[~df['action'].str.contains("FORMING|VOID", case=False, na=False)]
        
        # 🕰️ THE STRICT TIME FILTER (Removes old days like July 3rd) 🕰️
        if 'time_received' in df.columns and not df.empty:
            # Convert the time text into real Python Date objects
            df['time_received'] = pd.to_datetime(df['time_received'])
            # Find the absolute newest day in the dataset
            latest_date = df['time_received'].dt.date.max()
            # Filter the table to ONLY show stocks from that newest day
            df = df[df['time_received'].dt.date == latest_date]
        
        # Drop the conflicting MTF Alignment and Trade Plan columns to keep the UI clean
        df = df.drop(columns=['aligned', 'plan'], errors='ignore')
        
        if not df.empty:
            # Inject the true active row count and the EXACT date of the data
            display_date = latest_date.strftime("%d %b %Y") if 'latest_date' in locals() else datetime.now().strftime("%d %b %Y")
            header_placeholder.markdown(
                f"Monitoring for EMA Crossovers inside Fibonacci Impulse Zones. &nbsp;&nbsp;&nbsp; "
                f"<span style='color:#ff4b4b; font-weight:bold;'>Total scan ({display_date}) is {len(df)}</span>", 
                unsafe_allow_html=True
            )
            
            with table_placeholder.container():
                st.dataframe(
                    df,
                    column_config={
                        "ticker": st.column_config.TextColumn("Stock", width="medium"),
                        "action": st.column_config.TextColumn("Signal", width="small"),
                        "entry": st.column_config.NumberColumn("Entry (₹)", format="%.2f"),
                        "sl": st.column_config.NumberColumn("Stop Loss (₹)", format="%.2f"),
                        "tp1": st.column_config.NumberColumn("TP1 (₹)", format="%.2f"),
                        "tp2": st.column_config.NumberColumn("TP2 (₹)", format="%.2f"),
                        "tp3": st.column_config.NumberColumn("TP3 (₹)", format="%.2f"),
                        "time_received": st.column_config.DatetimeColumn("Trigger Time", format="D MMM YYYY, h:mm a")
                    },
                    hide_index=True,
                    use_container_width=True
                )
        else:
            header_placeholder.empty()
            with table_placeholder.container():
                st.info("Scan complete. No active setups found in the Buy Zone today. 📡")
    else:
        with table_placeholder.container():
            st.info("Waiting for market data... Run the Python Screener to update targets. 📡")
            
    time.sleep(5)
