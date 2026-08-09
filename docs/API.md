# HTTP API

Base path `/api`. JSON in, JSON out. No authentication — single-user, self-hosted.

Errors use the standard shape:

```json
{ "detail": "Insufficient cash: need 5200.00 PLN, have 3100.00 PLN" }
```

| Status | Meaning |
|---|---|
| 400 | Invalid request — bad symbol format, non-positive quantity |
| 404 | Unknown symbol, alert, or position |
| 409 | Business rule violated — insufficient cash or shares |
| 503 | Live mode requested but the upstream source is unreachable |

---

## Market

### `GET /api/prices`

Current snapshot for every watched symbol.

```json
{
  "prices": [
    { "symbol": "CRYPTO:BTCUSDT", "price": 79411.20, "previous_price": 79380.10,
      "change": 31.10, "direction": "up", "timestamp": "2026-08-09T11:04:22Z" }
  ],
  "version": 8412
}
```

### `GET /api/stream/prices`

Server-Sent Events. One `message` event per changed batch; heartbeat comment every 15 s to
keep proxies from closing the connection.

```
data: {"prices":[...],"version":8413}

: heartbeat
```

The client reconnects automatically — `EventSource` does this natively. The server does not
attempt to replay missed frames; the next full snapshot supersedes them.

### `GET /api/candles/{symbol}?interval=1h&limit=200`

Historical candles, newest last. Backed by `MarketDataSource.get_candles`.

```json
{ "symbol": "CRYPTO:BTCUSDT", "interval": "1h",
  "candles": [{ "t": "2026-08-09T10:00:00Z", "o": 79100.0, "h": 79500.0,
                "l": 79020.0, "c": 79411.2, "v": 812.4 }] }
```

---

## Watchlist

### `GET /api/watchlist`

```json
{ "symbols": ["CRYPTO:BTCUSDT", "GPW:PKN"] }
```

### `POST /api/watchlist`

```json
{ "symbol": "CRYPTO:SOLUSDT" }
```

Validates the prefix against known markets, then calls `add_symbol` on the data source.
Returns 400 for an unknown prefix.

### `DELETE /api/watchlist/{symbol}`

Removes from the watchlist and clears the cache entry. Positions in that symbol are
**not** affected — you can hold something you no longer watch.

---

## Portfolio

### `GET /api/portfolio`

```json
{
  "cash": 91200.50,
  "positions": [
    { "symbol": "CRYPTO:BTCUSDT", "quantity": 0.1, "avg_cost": 78000.0,
      "current_price": 79411.2, "market_value": 7941.12,
      "unrealised_pnl": 141.12, "unrealised_pnl_pct": 1.81 }
  ],
  "total_value": 99141.62,
  "currency": "PLN"
}
```

`total_value` is `cash + Σ market_value`. Positions are valued from `PriceCache`, so a
symbol with no cached price is returned with `current_price: null` and excluded from totals.

### `POST /api/trade`

```json
{ "symbol": "CRYPTO:BTCUSDT", "side": "BUY", "quantity": 0.05 }
```

Market order, instant fill at the current cached price, no fees, no confirmation.

- 409 if buying with insufficient cash, or selling more than held
- 503 if no price is cached for the symbol — you cannot trade what you cannot price

```json
{ "trade": { "id": 41, "symbol": "CRYPTO:BTCUSDT", "side": "BUY",
             "quantity": 0.05, "price": 79411.2,
             "executed_at": "2026-08-09T11:04:30Z" },
  "cash": 87230.94 }
```

### `GET /api/trades?limit=50`

Trade history, newest first.

---

## Alerts

### `GET /api/alerts`

### `POST /api/alerts`

```json
{ "symbol": "CRYPTO:BTCUSDT", "condition": "ABOVE", "threshold": 80000 }
```

### `DELETE /api/alerts/{id}`

### `GET /api/stream/alerts`

SSE channel emitting an event when an alert fires. An alert fires **once**, then its
`triggered` flag is set and it stops evaluating until deleted and recreated.

---

## Backtest

### `POST /api/backtest`

```json
{ "symbol": "CRYPTO:BTCUSDT", "interval": "1h", "limit": 500,
  "strategy": "ma_crossover", "params": { "fast": 20, "slow": 50 },
  "initial_cash": 10000 }
```

```json
{
  "trades": [{ "t": "...", "side": "BUY", "price": 78100.0, "quantity": 0.128 }],
  "equity_curve": [{ "t": "...", "value": 10000.0 }],
  "metrics": { "total_return_pct": 12.4, "max_drawdown_pct": -6.1, "trade_count": 14 }
}
```

Signals are computed on candle `i` and executed at candle `i+1` open — see the look-ahead
warning in `docs/BUILD_ORDER.md` Phase 7.

---

## AI assistant

Optional. Returns `503` throughout when `OPENROUTER_API_KEY` is unset — that is a normal
state, not an error condition.

### `GET /api/ai/status`

```json
{ "configured": true, "model": "some-provider/some-model:free" }
```

The frontend calls this once on load to decide what the drawer shows before the first message.

### `POST /api/ai/chat`

```json
{ "message": "Which position is hurting me most?",
  "history": [{ "role": "user", "content": "..." },
              { "role": "assistant", "content": "..." }] }
```

Streams SSE. Two event types:

```
event: token
data: {"text":"Your worst performer is "}

event: proposal
data: {"action":"SELL","symbol":"GPW:CDR","quantity":10,
       "reason":"Down 8.2%, largest drag on the portfolio"}
```

Portfolio context is assembled **server-side** — the client sends only the message and the
conversation history. It never uploads positions or prices.

A `proposal` event is a suggestion and nothing more. No trade has occurred. The frontend
renders a card; confirming it issues an ordinary `POST /api/trade`. There is no privileged
path from the model to the portfolio.

| Status | Meaning |
|---|---|
| 429 | OpenRouter free-tier rate limit — show "try again shortly", not an error state |
| 503 | Key not set, or upstream unavailable |

---

## System

### `GET /api/health`

```json
{ "status": "ok", "market_mode": "simulator", "sources": ["simulator"],
  "ai": "unconfigured" }
```

In live mode, `sources` lists the active children of the composite and their connection
state — useful for debugging a dead Binance socket.
