# AlphaScope — Live Crypto Intelligence Dashboard

> *"668 funding extremes. 53 whale positions. 1 FIRE signal. All in one dashboard. All free."*

[![Live](https://img.shields.io/badge/Status-LIVE-brightgreen?style=for-the-badge)](https://github.com/visioneth/AlphaScope)
[![Free](https://img.shields.io/badge/Price-FREE-gold?style=for-the-badge)](https://github.com/visioneth/AlphaScope)
[![Open Source](https://img.shields.io/badge/Open_Source-Yes-purple?style=for-the-badge)](https://github.com/visioneth/AlphaScope)
[![Kill Zone](https://img.shields.io/badge/Kill_Zone_WR-98.4%25-red?style=for-the-badge)](https://github.com/visioneth/crypto-kill-zones)

---

## What This Is

A **real-time crypto intelligence dashboard** that combines everything serious traders actually need — in one screen. No subscription. No enterprise pricing. No 14-day trial. Just clone it and run it.

**What you see on screen, right now, live:**

- **FIRE signals** — coins scoring 7.0+ across funding, RSI, whale consensus, and kill zone timing
- **Kill Zone countdown** — exact time to the next high-probability SHORT window (98.4% WR at 20:00 UTC)
- **Funding rate heatmap** — top 10 most extreme funding rates across 1,000+ coins
- **Whale consensus panel** — what the 53 tracked Hyperliquid whales are actually positioned in
- **Live prices** — BTC, ETH, SOL with 24h change
- **WebSocket real-time** — updates every 15 seconds without a page refresh

---

## Screenshots

```
┌─────────────────────────────────────────────────────────────┐
│  ◈ ALPHASCOPE          ● LIVE    Last scan: 2026-03-03 04:12 │
├──────────────┬──────────────┬──────────────────────────────┤
│ BTC $67,289  │ ETH $2,012   │ SOL $87.69  +7.3%            │
├──────────────┴──────────────┴──────────────────────────────┤
│ 🔥 FIRE SIGNALS (1)        │ ⚡ KILL ZONE COUNTDOWN         │
│ POWER  score=8.0           │  NY CLOSE 20:00 UTC           │
│ FUNDING_FARM               │  ██████████░░░░░  06:42:15    │
│ funding: -156%/8h          │  98.4% WIN RATE               │
│ Z-score: -1.2              │  SHORT                        │
├────────────────────────────┼──────────────────────────────┤
│ 📊 FUNDING HEATMAP (668)   │ 🐋 WHALE CONSENSUS            │
│ POWER   -156% ██████████   │  53 whales tracked            │
│ BARD    -144% █████████    │  LONG  ████░░░░░  44%         │
│ GAIB     -98% ██████       │  SHORT ██████░░░  56%         │
│ DENT     +87% ██████       │  NEUTRAL — no strong consensus│
└────────────────────────────┴──────────────────────────────┘
```

---

## Why I Built This

Every dashboard I found was either:
- **$200/month** for data you can get free from Binance and CoinGlass
- **Built for casual traders** — colorful noise, no actual edge
- **Missing the kill zone timing** — the most reliable SHORT pattern I've found (98.4% WR, 65 real trades)
- **Missing whale positioning** — institutional smart money tells you more than any indicator

So I built it myself. FastAPI backend, WebSocket real-time feed, dark glassmorphism UI. The whole thing is ~200 lines of Python and ~400 lines of HTML/CSS/JS. No databases. No Docker. No cloud required.

Your machine. Your data. Your edge.

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/visioneth/AlphaScope.git
cd AlphaScope

# 2. Install
pip install fastapi uvicorn requests

# 3. Point it at your signal engine (or run standalone)
# Edit BEAST_DIR in alphascope.py to your signal output directory
# Or skip this — the dashboard runs standalone with live prices only

# 4. Run
python alphascope.py

# 5. Open
# http://localhost:8080
```

**Runs on:** Python 3.9+ | Windows, Mac, Linux | No GPU required

---

## Signal Engine Integration

AlphaScope reads two JSON files from your signal engine (optional):

```
v33x_signals_latest.json       → fire signals, watch signals, funding extremes
v33x_enhanced_whale_state.json → whale positions and consensus
```

Without these files, AlphaScope runs standalone — showing live BTC/ETH/SOL prices and kill zone timing only.

**Want the signal engine?** → [V33X Beast Pack](https://github.com/visioneth) *(private — DM @Vision33X)*

---

## The Kill Zone Logic

The kill zone countdown is the most important feature on this dashboard.

At **20:00 UTC** every day — US close, European close, Asian pre-market opening simultaneously — institutional selling pressure is at its peak. I've documented **64 wins out of 65 trades** shorting this exact window.

AlphaScope shows you:
- Which kill zone is next (4 windows: 02:00, 10:00, 17:00, 20:00 UTC)
- Exact countdown in HH:MM:SS
- Win rate and direction for that window
- **ACTIVE** indicator when you're within 30 minutes

Full data: [crypto-kill-zones](https://github.com/visioneth/crypto-kill-zones)

---

## The Funding Heatmap

Funding rates are the most overlooked edge in crypto perpetuals.

When funding hits **-100% or worse**, longs are paying shorts 1% every 8 hours. That's **~3% per day**. The market will eventually correct — violently. AlphaScope shows you the top 10 most extreme funding rates in real time, color-coded by direction.

This is how I found POWER at **-156% funding** before it moved.

---

## Architecture

```
alphascope.py          FastAPI app + WebSocket server
static/index.html      Single-page dashboard (CSS + vanilla JS)

Data sources:
  Binance US API  → BTC/ETH/SOL live prices
  Local JSON      → signals, whale data (from Beast Pack signal engine)
  Internal        → kill zone countdown (pure logic, no API needed)

WebSocket pushes every 15 seconds.
REST endpoint /api/data for polling if preferred.
```

No database. No Redis. No message queue. It's as simple as it can be while still being useful.

---

## What's Next

- [ ] CoinGecko fallback for prices (Binance US intermittent)
- [ ] RSI heatmap panel (top 10 coins approaching RSI extremes)
- [ ] Kill zone alert system (browser notification at T-5 minutes)
- [ ] Historical signal log (how many FIRE signals were right)
- [ ] Dark/light theme toggle
- [ ] Docker compose for one-command deploy

PRs welcome. Keep it simple.

---

## Related

- [crypto-kill-zones](https://github.com/visioneth/crypto-kill-zones) — 98.4% SHORT win rate, 65 real trades
- [rsi-extreme-edge](https://github.com/visioneth/rsi-extreme-edge) — RSI reversal signals, 138 real trades
- [follow-the-whales](https://github.com/visioneth/follow-the-whales) — 50,000+ verified whale wallets

---

## Copy Trade

Every signal that fires on this dashboard, I execute on BloFin.

**Profile: [Vision33X](https://partner.blofin.com/d/Vision33X)**
Code: **Vision33X** (reduced fees)

---

*Free. Open source. No subscriptions. Not financial advice.*

*Built by [@Vision33X](https://x.com/Vision33X) — because good tools shouldn't cost $200/month.*
