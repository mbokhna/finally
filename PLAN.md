# PulseDesk — Multi-Market Trading Terminal

## 1. Vision

PulseDesk is a real-time trading terminal for **crypto and Warsaw Stock Exchange (GPW)** equities,
with a simulated portfolio, price alerts, and lightweight strategy backtesting.

It streams live prices over WebSocket, lets the user trade a paper portfolio, and evaluates
simple rule-based strategies against historical data — all from a single self-hosted container.

**Design goal:** every external data source is free. No paid market data subscription is
required to run the full product.

## 2. Scope

### In scope (v1)

- Live price streaming for crypto (Binance) and GPW equities (Stooq)
- Deterministic price **simulator** used for development, demos, and tests
- Watchlist management (add/remove instruments)
- Paper portfolio: virtual cash, market buy/sell, positions, unrealised P&L
- Price alerts: threshold rules that fire a browser notification
- Backtest-lite: run a simple moving-average crossover over historical candles
- **AI assistant** in a collapsible side panel — opened by an explicit click, never
  occupying terminal space by default (§11)
- Dark, data-dense terminal UI

### Out of scope (v1)

- Real order execution against a broker
- Options, futures, margin, short selling
- User accounts and authentication (single-user, self-hosted)
- **Any paid data source or paid model** — see §2a
- **Any form of deployment or cloud hosting** — see §2a
- AI placing trades autonomously — the assistant proposes, the user confirms (§11)

## 2a. Hard constraints — cost and hosting

These are project constraints, not preferences. A change that violates one of them is
out of scope regardless of how useful it seems.

### Zero monetary cost

**No component of this project may require payment, a credit card, or a paid subscription.**

| Layer | Choice | Cost |
|---|---|---|
| Crypto prices | Binance public WebSocket + REST | Free, no key, no account |
| GPW prices | Stooq CSV endpoints | Free, no key, no account |
| Development prices | Built-in GBM simulator | Free, offline |
| AI assistant | OpenRouter, free-tier models only | Free, key required |
| Database | SQLite | Free, bundled with Python |
| Backend | FastAPI, uvicorn, uv | Open source |
| Frontend | Vite, React, TypeScript | Open source |
| Container | Docker / Docker Desktop | Free for personal use |

**Exactly one credential exists in this project: `OPENROUTER_API_KEY`, and it is optional.**

- It unlocks the AI assistant (§11) and nothing else
- Without it, every other feature works normally — the assistant panel simply reports
  that it is unconfigured
- Only OpenRouter models on the free tier may be used. The configured model must carry
  the `:free` suffix; a paid model id is a defect, not a preference

No other key may be introduced. If a feature appears to need one, drop the feature or find
a free alternative.

### Local only — no deployment

**This project is not deployed.** It runs on `localhost` and nowhere else.

Out of scope, permanently:

- Cloud hosting of any kind — fly.io, Render, Railway, Vercel, AWS, Azure
- Domain names, DNS, TLS certificates
- Managed databases or hosted caches
- CI pipelines that deploy anything

`Dockerfile` and `docker-compose.yml` exist only so the app starts with one command on the
developer's own machine. They are packaging, not deployment.

Consequences accepted deliberately:

- No authentication — the app binds to localhost and is never internet-facing
- No horizontal scaling, no load balancing, no health-check orchestration
- No secrets management — there are no secrets

### Known limitations of free sources

Honesty about what "free" costs in quality:

| Source | Limitation |
|---|---|
| **Binance** | Real-time and reliable, but geo-restricted in some jurisdictions (notably the US). Fine from the EU. Sockets are closed by the server every 24 h — the reconnect loop must treat this as routine, not as an error. |
| **Stooq** | No published API contract or SLA. Data is delayed, not real-time. Returns `N/D` outside trading hours. Endpoints could change without notice — treat this source as best-effort and degrade gracefully rather than crashing. |
| **Both** | No historical depth guarantees. The backtester should handle short candle series rather than assuming years of data. |

The simulator exists partly as insurance: if either live source breaks, the product still
runs and still demonstrates every feature.

## 3. Users and flows

Single user, self-hosted, no login.

**First launch**

1. `./start.sh` builds and runs the container
2. Browser opens `http://localhost:8000`
3. Default watchlist is populated (5 crypto pairs, 5 GPW tickers)
4. Virtual cash balance is 100,000 PLN
5. Prices begin streaming within 2 seconds

**Core loop**

- Watch prices tick in the watchlist grid; uptick flashes green, downtick red
- Click an instrument to load its detail chart
- Buy or sell at the current price — instant fill, no fees, no confirmation
- Set an alert ("BTCUSDT above 80000") and get notified when it fires
- Open Backtest, pick an instrument and an MA pair, see the equity curve

## 4. Architecture

Single container, single port. FastAPI serves both the JSON API and the built frontend.

```
┌──────────────────────────────────────────────────┐
│ Docker container — port 8000                     │
│                                                  │
│  FastAPI (Python 3.12, uv)                       │
│   ├── /api/*           REST                      │
│   ├── /api/stream/*    Server-Sent Events        │
│   └── /*               static (Vite build)       │
│                                                  │
│  SQLite (volume-mounted at /data)                │
└──────────────────────────────────────────────────┘
          │                        │
          ▼                        ▼
   Binance WebSocket         Stooq CSV endpoint
   (crypto, live)            (GPW, delayed)
```

### Why these choices

| Decision | Reason |
|---|---|
| **FastAPI** | Native async — required for holding a WebSocket upstream while serving HTTP |
| **SSE to the browser** | One-way push; simpler than WebSocket, auto-reconnects, no extra library |
| **WebSocket upstream** | Binance pushes; polling would be wasteful and rate-limited |
| **SQLite** | Single user, single container. No separate DB service to run |
| **Vite + React + TS** | Fast dev server, static build, no Node runtime in production |
| **uv** | Fast, reproducible Python dependency resolution |

### Layer boundaries

- `app/market/` never imports from `app/portfolio/` or `app/api/`
- All price consumers read from `PriceCache` — never from a data source directly
- The frontend talks only to `/api/*`; it never contacts Binance or Stooq

## 5. Directory structure

```
pulsedesk/
├── PLAN.md
├── CLAUDE.md
├── README.md
├── docs/
│   ├── ARCHITECTURE.md
│   ├── MARKET_DATA.md
│   ├── API.md
│   └── BUILD_ORDER.md
├── backend/
│   ├── pyproject.toml
│   ├── app/
│   │   ├── main.py             FastAPI app, lifespan, router mounting
│   │   ├── config.py           env var loading, Settings
│   │   ├── db.py               SQLite connection, schema init
│   │   ├── market/
│   │   │   ├── models.py       PriceUpdate, Candle
│   │   │   ├── interface.py    MarketDataSource ABC
│   │   │   ├── cache.py        PriceCache
│   │   │   ├── simulator.py    SimulatorDataSource
│   │   │   ├── binance.py      BinanceDataSource
│   │   │   ├── stooq.py        StooqDataSource
│   │   │   ├── composite.py    CompositeDataSource — routes by instrument
│   │   │   ├── factory.py      create_market_data_source()
│   │   │   └── stream.py       SSE endpoint
│   │   ├── portfolio/
│   │   │   ├── models.py       Position, Trade
│   │   │   └── service.py      buy/sell, valuation, P&L
│   │   ├── alerts/
│   │   │   ├── models.py       Alert
│   │   │   └── engine.py       evaluates alerts on each price tick
│   │   ├── backtest/
│   │   │   ├── strategies.py   MA crossover
│   │   │   └── runner.py       executes strategy over candles
│   │   ├── ai/                 optional — see docs/AI_ASSISTANT.md
│   │   │   ├── client.py       OpenRouter streaming client
│   │   │   ├── context.py      portfolio/price context assembly
│   │   │   ├── prompts.py      system prompt
│   │   │   └── proposals.py    parse + validate proposed actions
│   │   └── api/
│   │       ├── market.py
│   │       ├── portfolio.py
│   │       ├── watchlist.py
│   │       ├── alerts.py
│   │       ├── backtest.py
│   │       └── ai.py
│   └── tests/
├── frontend/
│   ├── package.json
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── lib/
├── Dockerfile
├── docker-compose.yml
├── .env.example
└── start.sh
```

## 6. Instruments

An instrument is identified by a **prefixed symbol** so the router knows which source owns it.

| Prefix | Market | Example | Source |
|---|---|---|---|
| `CRYPTO:` | Crypto pairs | `CRYPTO:BTCUSDT` | Binance |
| `GPW:` | Warsaw Stock Exchange | `GPW:PKN` | Stooq |

Default watchlist:

```
CRYPTO:BTCUSDT  CRYPTO:ETHUSDT  CRYPTO:SOLUSDT  CRYPTO:BNBUSDT  CRYPTO:XRPUSDT
GPW:PKN         GPW:PKO         GPW:PZU         GPW:KGH         GPW:CDR
```

## 7. Data model

```sql
CREATE TABLE watchlist (
    symbol      TEXT PRIMARY KEY,
    added_at    TEXT NOT NULL
);

CREATE TABLE positions (
    symbol      TEXT PRIMARY KEY,
    quantity    REAL NOT NULL,
    avg_cost    REAL NOT NULL
);

CREATE TABLE trades (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    side        TEXT NOT NULL CHECK (side IN ('BUY','SELL')),
    quantity    REAL NOT NULL,
    price       REAL NOT NULL,
    executed_at TEXT NOT NULL
);

CREATE TABLE account (
    id          INTEGER PRIMARY KEY CHECK (id = 1),
    cash        REAL NOT NULL
);

CREATE TABLE alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol      TEXT NOT NULL,
    condition   TEXT NOT NULL CHECK (condition IN ('ABOVE','BELOW')),
    threshold   REAL NOT NULL,
    triggered   INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL
);
```

Seed on first run: `account.cash = 100000`, default watchlist inserted.

## 8. Configuration

```bash
# Market data mode: simulator | live
PULSEDESK_MARKET_MODE=simulator

# Base currency for the portfolio
PULSEDESK_CURRENCY=PLN

# SQLite location
PULSEDESK_DB_PATH=/data/pulsedesk.db

# Seconds between Stooq polls (GPW data is delayed, no need to poll fast)
PULSEDESK_STOOQ_INTERVAL=60

# --- AI assistant (optional) ---
# The only credential in the project. Omit it and the assistant is simply disabled.
OPENROUTER_API_KEY=
# Must end in ':free' — validated at startup
PULSEDESK_AI_MODEL=some-provider/some-model:free
PULSEDESK_AI_MAX_TOKENS=800
```

No market data key is required in either mode. `simulator` is the default so a fresh
clone runs offline with no network access and no configuration at all.

## 9. Non-functional requirements

| Requirement | Target |
|---|---|
| First price on screen | < 2 s after page load |
| SSE tick latency (simulator) | < 250 ms |
| Cold container start | < 5 s |
| Test suite runtime | < 30 s |
| Backend unit test coverage | > 80 % on `app/market` and `app/portfolio` |

## 10. Testing strategy

- **Unit** — every module in `app/market` and `app/portfolio` in isolation
- **Deterministic simulator** — seeded RNG, so price sequences are reproducible in tests
- **Contract tests** — one shared test suite run against every `MarketDataSource`
  implementation, guaranteeing they are truly interchangeable
- **Integration** — FastAPI `TestClient` against the real SQLite schema in a temp file
- **No network in tests** — Binance and Stooq clients are tested against recorded fixtures

## 11. AI Assistant

An optional analyst that answers questions about the portfolio and the market. Full design
in `docs/AI_ASSISTANT.md`.

### It is a panel, not a pane

**The assistant must never occupy terminal space unless the user opens it.**

- Default state: closed. The terminal renders exactly as if the feature did not exist
- A single circular button sits in the bottom-right corner, above the layout
- Clicking it slides a 400 px drawer in from the right, over the terminal — the grid does
  **not** reflow, resize, or shift
- `Esc` or clicking the button again closes it
- The open/closed state persists in `localStorage`, so it stays closed between reloads
  unless the user chose otherwise

This is deliberate: the product is a data terminal first. The assistant is a tool the user
reaches for, not a companion that is always present.

### Optional by construction

| `OPENROUTER_API_KEY` | Behaviour |
|---|---|
| Set | Assistant works |
| Not set | Button still visible; opening it shows "AI assistant not configured — set OPENROUTER_API_KEY to enable". Nothing else changes |

The key is never required for the app to start, for tests to pass, or for any other feature
to work. `GET /api/health` reports `"ai": "configured" | "unconfigured"`.

### What it can do

Read-only context, assembled server-side on each request:

- Current portfolio: cash, positions, unrealised P&L
- Current prices for watched symbols
- Recent trade history
- Active alerts

Typical questions: *"Which position is hurting me most?"*, *"How concentrated am I in
crypto?"*, *"What did I trade this week?"*

### Actions require confirmation

The assistant may **propose** an action — a trade, an alert, a watchlist change — but never
performs one. A proposal renders as a card in the chat with the exact parameters and a
**Confirm** button. Nothing reaches `/api/trade` until the user clicks it.

This is a hard rule, not a UX preference. An LLM on a free tier is not something to hand
unsupervised write access to, even in a paper portfolio.

### Model policy

- Model id comes from `PULSEDESK_AI_MODEL` and must end in `:free`
- The backend validates the suffix at startup and refuses to enable the assistant otherwise
- Free-tier models are rate-limited; the panel surfaces 429s as "rate limited, try again
  shortly" rather than as an error
- Streaming responses via SSE, reusing the existing streaming infrastructure

## 12. Definition of done

- `./start.sh` works from a clean clone with no `.env` file **and no network access**
- All tests pass, `mypy --strict` and `ruff` are clean
- Switching `PULSEDESK_MARKET_MODE=live` streams real prices without code changes
  and **without any credential**
- No API key field exists anywhere in the codebase or configuration
- README documents setup, architecture, and how to add a new data source
