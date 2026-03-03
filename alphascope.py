"""
AlphaScope — Live Crypto Intelligence Dashboard
Free. Open Source. No subscriptions. No enterprise BS.
Built by Vision33X.

Usage: python alphascope.py
Then open: http://localhost:8080
"""
import json
import time
import asyncio
import os
from datetime import datetime, timezone
from pathlib import Path

import requests
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
import uvicorn

# ═══════════════════════════════════════════════
# CONFIG — point to your signal engine output
# ═══════════════════════════════════════════════
BEAST_DIR = Path(r"C:\Users\King Geo\OneDrive\Desktop\V33X_Beast_Pack\V33X_BEAST_PACK")
SIGNALS_FILE  = BEAST_DIR / "v33x_signals_latest.json"
WHALE_FILE    = BEAST_DIR / "v33x_enhanced_whale_state.json"
FUNDING_FILE  = BEAST_DIR / "v33x_funding_analysis.json"
PORT = 8080

# Kill Zone schedule (UTC hour → label, win rate, direction)
KILL_ZONES = [
    {"hour": 2,  "label": "LATE NIGHT",      "wr": 80.0,  "dir": "SHORT", "et": "9 PM ET"},
    {"hour": 10, "label": "EU OPEN",          "wr": 88.9,  "dir": "SHORT", "et": "5 AM ET · London Market Open"},
    {"hour": 17, "label": "US MARKET OPEN",   "wr": 78.7,  "dir": "SHORT", "et": "12 PM ET"},
    {"hour": 20, "label": "NY CLOSE",         "wr": 98.4,  "dir": "SHORT", "et": "3 PM ET"},
]

app = FastAPI(title="AlphaScope")
app.mount("/static", StaticFiles(directory="static"), name="static")

clients: list[WebSocket] = []


def get_next_kill_zone():
    now_utc = datetime.now(timezone.utc)
    current_hour = now_utc.hour
    current_minute = now_utc.minute
    current_second = now_utc.second

    best = None
    min_secs = float("inf")

    for kz in KILL_ZONES:
        kz_hour = kz["hour"]
        if kz_hour > current_hour:
            secs = (kz_hour - current_hour) * 3600 - current_minute * 60 - current_second
        elif kz_hour == current_hour and current_minute < 30:
            secs = 0  # active now
        else:
            # next day
            secs = (24 - current_hour + kz_hour) * 3600 - current_minute * 60 - current_second

        if secs < min_secs:
            min_secs = secs
            best = {**kz, "seconds_away": max(0, secs)}

    h = best["seconds_away"] // 3600
    m = (best["seconds_away"] % 3600) // 60
    s = best["seconds_away"] % 60
    best["countdown"] = f"{h:02d}:{m:02d}:{s:02d}"
    best["active"] = best["seconds_away"] < 1800  # within 30 min = active
    return best


def get_prices():
    # Try Binance US first
    try:
        symbols = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]
        resp = requests.get(
            "https://api.binance.us/api/v3/ticker/24hr",
            params={"symbols": json.dumps(symbols)},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=4,
        )
        tickers = resp.json()
        result = {}
        for t in tickers:
            sym = t["symbol"].replace("USDT", "")
            result[sym] = {
                "price": float(t["lastPrice"]),
                "change24h": float(t["priceChangePercent"]),
            }
        if result:
            return result
    except Exception:
        pass
    # Fallback: CoinGecko Pro
    try:
        resp = requests.get(
            "https://pro-api.coingecko.com/api/v3/simple/price",
            params={
                "ids": "bitcoin,ethereum,solana",
                "vs_currencies": "usd",
                "include_24hr_change": "true",
            },
            headers={
                "User-Agent": "Mozilla/5.0",
                "x-cg-pro-api-key": "CG-i9sV4dKkf3YwwA4PJQBPvwaw",
            },
            timeout=5,
        )
        data = resp.json()
        return {
            "BTC": {"price": data["bitcoin"]["usd"], "change24h": data["bitcoin"].get("usd_24h_change", 0)},
            "ETH": {"price": data["ethereum"]["usd"], "change24h": data["ethereum"].get("usd_24h_change", 0)},
            "SOL": {"price": data["solana"]["usd"], "change24h": data["solana"].get("usd_24h_change", 0)},
        }
    except Exception:
        pass
    return {}


def get_funding_coins():
    """Top funding coins from Beast Pack funding analysis (Binance rates)."""
    try:
        if FUNDING_FILE.exists():
            with open(FUNDING_FILE, encoding="utf-8") as f:
                data = json.load(f)
            coins = data.get("coins", {})
            sorted_coins = sorted(
                coins.items(),
                key=lambda x: abs(x[1].get("current_rate_pct", 0)),
                reverse=True
            )
            return [
                {
                    "coin": coin,
                    "rate": round(info.get("current_rate_pct", 0) * 100, 4),
                    "direction": info.get("direction", ""),
                }
                for coin, info in sorted_coins[:15]
                if info.get("current_rate_pct") is not None
            ]
    except Exception:
        pass
    return []


def get_signals_data():
    try:
        if SIGNALS_FILE.exists():
            with open(SIGNALS_FILE, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return {"signals": [], "funding_extremes_count": 0, "timestamp": None}


def get_whale_data():
    try:
        if WHALE_FILE.exists():
            with open(WHALE_FILE, encoding="utf-8") as f:
                data = json.load(f)
            snapshots = data.get("whale_snapshots", {})
            # Count positions
            long_count = short_count = 0
            active_whales = []
            for whale_id, whale in list(snapshots.items())[:10]:
                positions = whale.get("positions", {})
                name = whale.get("display_name", whale_id[:12])
                pos_list = []
                for coin, pos in positions.items():
                    side = pos.get("side", "").upper()
                    size = pos.get("size_usd", 0)
                    if side == "LONG":
                        long_count += 1
                        pos_list.append({"coin": coin, "side": "LONG", "size": size})
                    elif side == "SHORT":
                        short_count += 1
                        pos_list.append({"coin": coin, "side": "SHORT", "size": size})
                if pos_list:
                    active_whales.append({"name": name, "positions": pos_list[:3]})
            total = long_count + short_count
            bias = "NEUTRAL"
            bias_pct = 50
            if total > 0:
                lp = long_count / total * 100
                sp = short_count / total * 100
                if lp >= 65:
                    bias = "LONG"
                    bias_pct = lp
                elif sp >= 65:
                    bias = "SHORT"
                    bias_pct = sp
            return {
                "total_tracked": len(snapshots),
                "long_count": long_count,
                "short_count": short_count,
                "bias": bias,
                "bias_pct": round(bias_pct, 1),
                "active_whales": active_whales[:5],
            }
    except Exception:
        pass
    return {"total_tracked": 53, "long_count": 0, "short_count": 0,
            "bias": "NEUTRAL", "bias_pct": 50, "active_whales": []}


def build_payload():
    signals_data = get_signals_data()
    signals = signals_data.get("signals", [])
    fire = [s for s in signals if s.get("score", 0) >= 7.0]
    watch = [s for s in signals if 4.0 <= s.get("score", 0) < 7.0]

    # Top funding extremes from signal data
    top_funding = sorted(
        [s for s in signals if s.get("signal_type") == "FUNDING_FARM"],
        key=lambda x: abs(x.get("funding", {}).get("avg", 0)),
        reverse=True
    )[:10]

    ts = signals_data.get("timestamp", "")
    last_scan = ts[:19].replace("T", " ") if ts else "---"

    return {
        "timestamp": int(time.time()),
        "last_scan": last_scan,
        "funding_extremes_count": signals_data.get("funding_extremes_count", 0),
        "fire_signals": fire,
        "watch_signals": watch,
        "top_funding": top_funding,
        "raw_funding": get_funding_coins(),
        "kill_zone": get_next_kill_zone(),
        "prices": get_prices(),
        "whales": get_whale_data(),
    }


@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = Path("static/index.html")
    if html_path.exists():
        return html_path.read_text(encoding="utf-8")
    return "<h1>AlphaScope</h1><p>static/index.html not found</p>"


@app.get("/api/data")
async def api_data():
    return build_payload()


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    clients.append(websocket)
    try:
        # Send initial data immediately
        await websocket.send_json(build_payload())
        while True:
            await asyncio.sleep(15)
            await websocket.send_json(build_payload())
    except WebSocketDisconnect:
        clients.remove(websocket)
    except Exception:
        if websocket in clients:
            clients.remove(websocket)


if __name__ == "__main__":
    print("=" * 60)
    print("  AlphaScope — Live Crypto Intelligence Dashboard")
    print("  Open: http://localhost:8080")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
