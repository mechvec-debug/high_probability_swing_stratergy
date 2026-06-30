from fastapi import FastAPI, Request
import json
import os
from datetime import datetime

app = FastAPI()
DATA_FILE = "trading_alerts.json"

if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


@app.post("/tv-webhook")
async def receive_webhook(request: Request):
    payload = await request.json()

    # Stamp the exact time the signal was caught
    payload["time_received"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with open(DATA_FILE, "r") as f:
        alerts = json.load(f)

    alerts.insert(0, payload)

    with open(DATA_FILE, "w") as f:
        json.dump(alerts, f, indent=4)

    print(f"[{payload['time_received']}] Logged: {payload['ticker']} - {payload['action']}")
    return {"status": "success", "message": "Alert recorded"}