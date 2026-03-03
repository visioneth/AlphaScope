"""
AlphaScope — Live Crypto Intelligence Dashboard
Free. Open Source. No subscriptions. No enterprise BS.
Built by Vision33X.

Usage: python alphascope.py
Then open: http://localhost:8080

Standalone mode: runs fully on public APIs — no signal engine required.
Beast Pack mode: point BEAST_DIR at your signal engine output for enhanced data.
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
# CONFIG — optional Beast Pack integration
# If JSON files exist → use Beast Pack data (enhanced)
# If not → live public APIs are used automatically (standalone)
# ═══════════════════════════════════════════════
BEAST_DIR     = Path(r"C:\Users\King Geo\OneDrive\Desktop\V33X_Beast_Pack\V33X_BEAST_PACK")
SIGNALS_FILE  = BEAST_DIR / "v33x_signals_latest.json"
WHALE_FILE    = BEAST_DIR / "v33x_enhanced_whale_state.json"
FUNDING_FILE  = BEAST_DIR / "v33x_funding_analysis.json"
PORT = 8080

# Kill Zone schedule (UTC hour → label, win rate, direction)
KILL_ZONES = [
    {"hour": 2,  "label": "LATE NIGHT",    "wr": 80.0,  "dir": "SHORT", "et": "9 PM ET"},
    {"hour": 10, "label": "EU OPEN",        "wr": 88.9,  "dir": "SHORT", "et": "5 AM ET · London Market Open"},
    {"hour": 17, "label": "US MARKET OPEN", "wr": 78.7,  "dir": "SHORT", "et": "12 PM ET"},
    {"hour": 20, "label": "NY CLOSE",       "wr": 98.4,  "dir": "SHORT", "et": "3 PM ET"},
]

app = FastAPI(title="AlphaScope")
app.mount("/static", StaticFiles(directory="static"), name="static")

clients: list[WebSocket] = []

# Simple cache so we don't hammer APIs on every WS tick
_cache: dict = {}
_cache_ts: dict = {}
CACHE_TTL = 60  # seconds


def _cached(key: str, fn, ttl: int = CACHE_TTL):
    now = time.time()
    if key not in _cache_ts or now - _cache_ts[key] > ttl:
        result = fn()
        _cache[key] = result
        _cache_ts[key] = now
    return _cache[key]


# ─────────────────────────────────────────────
# KILL ZONE
# ─────────────────────────────────────────────
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
            secs = 0
        else:
            secs = (24 - current_hour + kz_hour) * 3600 - current_minute * 60 - current_second

        if secs < min_secs:
            min_secs = secs
            best = {**kz, "seconds_away": max(0, secs)}

    h = best["seconds_away"] // 3600
    m = (best["seconds_away"] % 3600) // 60
    s = best["seconds_away"] % 60
    best["countdown"] = f"{h:02d}:{m:02d}:{s:02d}"
    best["active"] = best["seconds_away"] < 1800
    return best


# ─────────────────────────────────────────────
# PRICES
# ─────────────────────────────────────────────
def get_prices():
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
    try:
        resp = requests.get(
            "https://api.binance.com/api/v3/ticker/24hr",
            params={"symbols": json.dumps(["BTCUSDT", "ETHUSDT", "SOLUSDT"])},
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
    return {}


# ─────────────────────────────────────────────
# FUNDING — Beast Pack first, Binance futures fallback
# ─────────────────────────────────────────────
def _funding_from_beast():
    """Pull from Beast Pack funding analysis JSON."""
    if not FUNDING_FILE.exists():
        return None
    with open(FUNDING_FILE, encoding="utf-8") as f:
        data = json.load(f)
    coins = data.get("coins", {})
    sorted_coins = sorted(
        coins.items(),
        key=lambda x: abs(x[1].get("current_rate_pct", 0)),
        reverse=True,
    )
    result = []
    for coin, info in sorted_coins[:15]:
        rate = info.get("current_rate_pct")
        if rate is None:
            continue
        result.append({
            "coin": coin,
            "rate": round(rate * 100, 4),
            "direction": "SHORT" if rate > 0 else "LONG",
        })
    return result if result else None


def _funding_from_binance():
    """Pull all futures funding rates from Binance — no API key needed."""
    resp = requests.get(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    data = resp.json()
    usdt = [d for d in data if d["symbol"].endswith("USDT")]
    usdt.sort(key=lambda x: abs(float(x.get("lastFundingRate", 0))), reverse=True)
    result = []
    for item in usdt[:15]:
        rate = float(item.get("lastFundingRate", 0))
        rate_pct = rate * 100  # decimal → percent per 8h
        coin = item["symbol"].replace("USDT", "")
        result.append({
            "coin": coin,
            "rate": round(rate_pct, 4),
            "direction": "SHORT" if rate > 0 else "LONG",
        })
    return result


def get_funding_coins():
    try:
        beast = _funding_from_beast()
        if beast is not None:
            return beast
    except Exception:
        pass
    try:
        return _funding_from_binance()
    except Exception:
        pass
    return []


# ─────────────────────────────────────────────
# SIGNALS — Beast Pack first, live funding fallback
# ─────────────────────────────────────────────
def _signals_from_beast():
    if not SIGNALS_FILE.exists():
        return None
    with open(SIGNALS_FILE, encoding="utf-8") as f:
        return json.load(f)


def _signals_from_binance():
    """Generate FIRE/WATCH signals from Binance futures funding extremes."""
    resp = requests.get(
        "https://fapi.binance.com/fapi/v1/premiumIndex",
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=8,
    )
    data = resp.json()
    usdt = [d for d in data if d["symbol"].endswith("USDT")]

    signals = []
    extreme_count = 0

    for item in usdt:
        rate = float(item.get("lastFundingRate", 0))
        rate_pct = rate * 100  # percent per 8h
        coin = item["symbol"].replace("USDT", "")

        if abs(rate_pct) >= 0.05:   # ≥5x baseline = worth noting
            extreme_count += 1

        # Score: normal baseline ~0.01%/8h → scale extremes
        abs_rate = abs(rate_pct)
        if abs_rate >= 0.50:
            score = 9.0
        elif abs_rate >= 0.30:
            score = 8.0
        elif abs_rate >= 0.15:
            score = 7.0
        elif abs_rate >= 0.08:
            score = 5.0
        else:
            continue  # not extreme enough

        direction = "LONG" if rate < 0 else "SHORT"
        signals.append({
            "coin": coin,
            "score": score,
            "direction": direction,
            "signal_type": "FUNDING_FARM",
            "funding": {"avg": round(rate_pct, 4)},
            "reason": f"Funding {rate_pct:+.4f}%/8h → {direction}",
        })

    signals.sort(key=lambda x: x["score"], reverse=True)
    return {
        "signals": signals[:20],
        "funding_extremes_count": extreme_count,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


def get_signals_data():
    try:
        beast = _signals_from_beast()
        if beast is not None:
            return beast
    except Exception:
        pass
    try:
        return _signals_from_binance()
    except Exception:
        pass
    return {"signals": [], "funding_extremes_count": 0, "timestamp": None}


# ─────────────────────────────────────────────
# WHALE DATA — Beast Pack first, Hyperliquid fallback
# ─────────────────────────────────────────────
def _whales_from_beast():
    if not WHALE_FILE.exists():
        return None
    with open(WHALE_FILE, encoding="utf-8") as f:
        data = json.load(f)
    snapshots = data.get("whale_snapshots", {})
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
            bias_pct = round(lp, 1)
        elif sp >= 65:
            bias = "SHORT"
            bias_pct = round(sp, 1)
    return {
        "total_tracked": len(snapshots),
        "long_count": long_count,
        "short_count": short_count,
        "bias": bias,
        "bias_pct": bias_pct,
        "active_whales": active_whales[:5],
        "source": "beast",
    }


def _whales_from_hyperliquid():
    """Pull top trader positions from Hyperliquid public API — no key needed."""
    # Get leaderboard
    resp = requests.post(
        "https://api.hyperliquid.xyz/info",
        json={"type": "leaderboard"},
        headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
        timeout=8,
    )
    leaderboard_data = resp.json()

    # Leaderboard returns list of {ethAddress, accountValue, pnl, ...}
    traders = []
    if isinstance(leaderboard_data, dict):
        traders = leaderboard_data.get("leaderboardRows", [])
    elif isinstance(leaderboard_data, list):
        traders = leaderboard_data

    long_count = short_count = 0
    active_whales = []

    for entry in traders[:15]:
        address = entry.get("ethAddress") or entry.get("address", "")
        if not address:
            continue
        try:
            pos_resp = requests.post(
                "https://api.hyperliquid.xyz/info",
                json={"type": "clearinghouseState", "user": address},
                headers={"User-Agent": "Mozilla/5.0", "Content-Type": "application/json"},
                timeout=4,
            )
            state = pos_resp.json()
            asset_positions = state.get("assetPositions", [])
            pos_list = []
            for ap in asset_positions[:3]:
                pos = ap.get("position", {})
                szi = float(pos.get("szi", 0))
                coin = pos.get("coin", "")
                if not coin or szi == 0:
                    continue
                if szi > 0:
                    long_count += 1
                    pos_list.append({"coin": coin, "side": "LONG", "size": round(abs(szi), 2)})
                else:
                    short_count += 1
                    pos_list.append({"coin": coin, "side": "SHORT", "size": round(abs(szi), 2)})
            if pos_list:
                name = address[:6] + "..." + address[-4:]
                active_whales.append({"name": name, "positions": pos_list})
        except Exception:
            continue

    total = long_count + short_count
    bias = "NEUTRAL"
    bias_pct = 50
    if total > 0:
        lp = long_count / total * 100
        sp = short_count / total * 100
        if lp >= 65:
            bias = "LONG"
            bias_pct = round(lp, 1)
        elif sp >= 65:
            bias = "SHORT"
            bias_pct = round(sp, 1)

    return {
        "total_tracked": len(traders),
        "long_count": long_count,
        "short_count": short_count,
        "bias": bias,
        "bias_pct": bias_pct,
        "active_whales": active_whales[:5],
        "source": "hyperliquid",
    }


def get_whale_data():
    try:
        beast = _whales_from_beast()
        if beast is not None:
            return beast
    except Exception:
        pass
    try:
        return _whales_from_hyperliquid()
    except Exception:
        pass
    return {
        "total_tracked": 0,
        "long_count": 0,
        "short_count": 0,
        "bias": "NEUTRAL",
        "bias_pct": 50,
        "active_whales": [],
        "source": "unavailable",
    }


# ─────────────────────────────────────────────
# PAYLOAD BUILDER
# ─────────────────────────────────────────────
def build_payload():
    signals_data = _cached("signals", get_signals_data, ttl=60)
    funding_coins = _cached("funding", get_funding_coins, ttl=60)
    whale_data    = _cached("whales",  get_whale_data,    ttl=120)
    prices        = _cached("prices",  get_prices,        ttl=15)

    signals = signals_data.get("signals", [])
    fire  = [s for s in signals if s.get("score", 0) >= 7.0]
    watch = [s for s in signals if 4.0 <= s.get("score", 0) < 7.0]

    top_funding = sorted(
        [s for s in signals if s.get("signal_type") == "FUNDING_FARM"],
        key=lambda x: abs(x.get("funding", {}).get("avg", 0)),
        reverse=True,
    )[:10]

    ts = signals_data.get("timestamp", "")
    last_scan = ts[:19].replace("T", " ") if ts else "---"

    # Detect mode for UI indicator
    beast_mode = SIGNALS_FILE.exists()

    return {
        "timestamp": int(time.time()),
        "last_scan": last_scan,
        "beast_mode": beast_mode,
        "funding_extremes_count": signals_data.get("funding_extremes_count", 0),
        "fire_signals": fire,
        "watch_signals": watch,
        "top_funding": top_funding,
        "raw_funding": funding_coins,
        "kill_zone": get_next_kill_zone(),
        "prices": prices,
        "whales": whale_data,
    }


# ─────────────────────────────────────────────
# ROUTES
# ─────────────────────────────────────────────
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
    beast_active = SIGNALS_FILE.exists()
    mode = "BEAST PACK" if beast_active else "STANDALONE (live public APIs)"
    print("=" * 60)
    print("  AlphaScope — Live Crypto Intelligence Dashboard")
    print(f"  Mode: {mode}")
    print("  Open: http://localhost:8080")
    print("=" * 60)
    uvicorn.run(app, host="0.0.0.0", port=PORT, log_level="warning")
