# Architecture

Why the system is shaped this way. `PLAN.md` says *what* is built; this says *why*.

## The one idea

**Producers write prices into a cache. Consumers read from the cache. They never meet.**

```
data sources  ──write──▶  PriceCache  ──read──▶  SSE stream
                                      ──read──▶  portfolio valuation
                                      ──read──▶  alert engine
```

Everything else follows from this. Swapping Binance for a simulator changes one line in a
factory, because nothing downstream knows a data source exists.

## Runtime shape

One process, one port, one container.

```
FastAPI (asyncio event loop)
│
├── lifespan startup
│   ├── init SQLite (create schema + seed if first run)
│   ├── build PriceCache
│   ├── create data source via factory
│   └── source.start(watchlist)   →  spawns background task(s)
│
├── background tasks
│   ├── simulator tick loop         (500 ms)  ─┐
│   ├── Binance WebSocket reader    (push)     ├─▶ PriceCache
│   └── Stooq poll loop             (60 s)    ─┘
│
├── request handlers                 read cache, read/write SQLite
│
└── lifespan shutdown
    └── source.stop()               cancel tasks, close sockets
```

Everything runs in one event loop. No threads except SQLite's, no queue, no broker.
For a single-user terminal, that is the right amount of machinery.

## Why SSE downstream and WebSocket upstream

They look like the same problem but are not.

| | Upstream (Binance → us) | Downstream (us → browser) |
|---|---|---|
| Direction | Server pushes to us | We push to browser |
| Bidirectional? | Yes — we send subscribe messages | No — browser only receives |
| Reconnect | We implement it | `EventSource` does it natively |
| Choice | **WebSocket** | **SSE** |

Using WebSocket to the browser would mean writing reconnect logic, heartbeats, and a
message protocol for something that only ever flows one way. SSE is plain HTTP with a
`text/event-stream` content type — it passes through proxies, survives reconnects for free,
and needs no client library.

## Why a version counter on the cache

Naive SSE re-sends the whole snapshot on a timer. That is wasteful when nothing has moved —
and outside GPW trading hours, nothing moves for sixteen hours a day.

Instead, every cache write increments a counter. The SSE handler holds the last version it
sent and only emits when the counter advances:

```python
last_seen = -1
while True:
    snapshot, version = cache.snapshot()
    if version != last_seen:
        yield sse(snapshot)
        last_seen = version
    await asyncio.sleep(0.1)
```

Cheap, correct, and no pub/sub infrastructure.

## Why the composite router

Crypto and GPW are different in every respect that matters: transport, frequency, trading
hours, symbol format. Forcing them into one client would produce a class full of `if
market == ...` branches.

Instead each market gets a clean implementation, and a router dispatches by symbol prefix:

```
CRYPTO:BTCUSDT  ──▶ BinanceDataSource
GPW:PKN         ──▶ StooqDataSource
```

The prefix lives in the symbol itself rather than in a lookup table, so routing needs no
database round-trip and a symbol is self-describing wherever it appears — in the URL, in
the SSE payload, in the trades table.

## Why the simulator is the default

Three reasons, in order of importance:

1. **Tests must be deterministic.** A seeded GBM produces the same sequence every run.
   Tests that depend on live BTC prices are tests that fail on a Sunday.
2. **A clean clone must work.** No key, no account, no network. Someone evaluating the
   project gets a running terminal in one command.
3. **Development is faster.** Prices tick every 500 ms instead of waiting for GPW to open.

Live mode is the special case, not the baseline. That inversion is deliberate.

## Layer boundaries

```
app/api/        ──▶ portfolio, alerts, backtest, market, ai
app/ai/         ──▶ portfolio, alerts, market (cache only)   ← leaf, nothing imports it
app/portfolio/  ──▶ market (cache only), db
app/alerts/     ──▶ market (cache only), db
app/backtest/   ──▶ market (models only), db
app/market/     ──▶ config only
```

`app/ai/` is a **leaf**: it reads from the domain but nothing in the domain imports it.
Delete the directory and the terminal still builds, still passes its tests, and still
runs — which is the structural expression of "the assistant is optional".

`app/market/` is the lowest layer and imports nothing from the application above it. That is
what lets the market subsystem be tested, and reasoned about, entirely on its own.

The rule that matters most: **no module outside `app/market/` may name a vendor.** Search the
codebase for "binance" and you should find hits in exactly one directory.

## Trade-offs accepted

| Decision | Cost | Why it is acceptable |
|---|---|---|
| SQLite | One writer at a time | Single user; concurrent writes never happen |
| In-memory cache | Prices lost on restart | They are re-populated within one tick |
| No auth | Not internet-safe | Self-hosted on localhost by design |
| Paper trading only | Not a real broker | Real execution is a regulatory problem, not a technical one |
| Polling Stooq | Up to 60 s stale | The source itself is delayed; faster polling buys nothing |

Each of these becomes wrong if the product grows beyond one user on one machine. They are
documented here so the cost is visible when that happens.

## What would change at scale

Not planned, but worth knowing where the seams are:

- **Multi-user** → cache becomes Redis, SQLite becomes Postgres, auth middleware appears
- **Many symbols** → the composite fans out to one task per market rather than one loop
- **Horizontal scale** → the cache moves out of process; SSE handlers become stateless
- **Real execution** → a broker adapter behind an `OrderExecutor` interface, mirroring how
  `MarketDataSource` isolates price providers today

The `MarketDataSource` pattern is the template for all of these: define the contract, keep
the vendor behind it, and let the rest of the system stay ignorant.
