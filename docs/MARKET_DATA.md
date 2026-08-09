# Market Data Design

The heart of the system. Everything else consumes prices; only this subsystem produces them.

## The problem

Three constraints pull in different directions:

1. Development and tests must work **offline, deterministically, for free**
2. The product must show **real prices** when the user wants them
3. Crypto and GPW equities have **completely different transport** — one pushes over
   WebSocket at high frequency, the other is a delayed CSV endpoint you poll

The answer is one interface with several implementations behind it, plus a router that
picks the right one per instrument.

## Structure

```
                    MarketDataSource (ABC)
                            │
      ┌─────────────────────┼─────────────────────┐
      │                     │                     │
SimulatorDataSource  BinanceDataSource   StooqDataSource
  (GBM, offline)      (WebSocket push)    (CSV poll, 60s)
      │                     │                     │
      └─────────────────────┼─────────────────────┘
                            │
                  CompositeDataSource
                  routes by symbol prefix
                            │
                            ▼
                       PriceCache
                  (thread-safe, versioned)
                            │
         ┌──────────────────┼──────────────────┐
         ▼                  ▼                  ▼
    SSE stream      portfolio valuation    alert engine
```

Downstream code sees only `PriceCache`. It cannot tell whether a price came from Binance
or from the simulator, and it must never need to.

## The interface

```python
class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push updates into a shared PriceCache on their own schedule.
    Downstream code never calls a data source directly — it reads the cache.
    """

    @abstractmethod
    async def start(self, symbols: list[str]) -> None:
        """Begin producing updates. Called exactly once."""

    @abstractmethod
    async def stop(self) -> None:
        """Stop and release resources. Idempotent."""

    @abstractmethod
    async def add_symbol(self, symbol: str) -> None:
        """Add to the active set. No-op if present."""

    @abstractmethod
    async def remove_symbol(self, symbol: str) -> None:
        """Remove from the active set and from the cache. No-op if absent."""

    @abstractmethod
    def get_symbols(self) -> list[str]:
        """Currently tracked symbols."""

    @abstractmethod
    async def get_candles(self, symbol: str, interval: str, limit: int) -> list[Candle]:
        """Historical candles, newest last. Used by the backtester."""
```

`get_candles` is the one addition beyond live streaming — the backtester needs history,
and each source fetches it differently.

## Implementations

### SimulatorDataSource — the default

Generates plausible prices offline using **Geometric Brownian Motion**:

```
S(t+1) = S(t) · exp( (μ − σ²/2)·Δt + σ·√Δt · Z )
```

- `μ` (drift) and `σ` (volatility) are per-instrument; crypto gets higher σ than GPW equities
- `Z` is a standard normal draw
- **Correlation**: draws are correlated within a group via Cholesky decomposition of a
  correlation matrix — crypto pairs move together at 0.7, GPW banks at 0.5, cross-market 0.1
- **Shock events**: ~0.1 % chance per tick per instrument of a 2–5 % jump, so the UI has
  something dramatic to render

Seeded RNG. Given the same seed, the same price sequence — that is what makes tests
deterministic.

Tick interval: 500 ms.

### BinanceDataSource — live crypto

Binance offers a **public WebSocket stream with no API key and no account**.

```
wss://stream.binance.com:9443/stream?streams=btcusdt@trade/ethusdt@trade
```

- Push-based: no polling, no rate limit on the stream itself
- Subscribe/unsubscribe at runtime via a JSON control message on the same socket
- Reconnect with exponential backoff (1 s → 30 s cap) on disconnect
- Binance forcibly closes sockets after 24 h — the reconnect loop must treat this as normal

Candles come from the REST endpoint:

```
GET https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=1h&limit=500
```

Weight-based rate limit, generous. No key required.

**Symbol mapping:** `CRYPTO:BTCUSDT` → `btcusdt` for the stream, `BTCUSDT` for REST.

### StooqDataSource — live GPW

Stooq publishes free CSV for the Warsaw Stock Exchange. No key, no account.

```
GET https://stooq.pl/q/l/?s=pkn&f=sd2t2ohlcv&h&e=csv     # latest quote
GET https://stooq.pl/q/d/l/?s=pkn&i=d                     # daily history
```

- Poll-based. Data is delayed, so polling faster than 60 s gains nothing
- One request per symbol; batch by iterating the watchlist on each cycle
- Handle the "N/D" placeholder Stooq returns outside trading hours — emit no update
  rather than a bogus price
- GPW trades 09:00–17:00 CET on weekdays; outside that window prices are static

**Symbol mapping:** `GPW:PKN` → `pkn`.

### CompositeDataSource — the router

Holds one child source per market and dispatches by prefix:

```python
PREFIX_MAP = {
    "CRYPTO": BinanceDataSource,
    "GPW":    StooqDataSource,
}
```

- `start()` partitions the symbol list by prefix and starts only the children that are needed
- `add_symbol()` routes to the owning child, starting it lazily if it was not running
- In `simulator` mode the composite is bypassed entirely — a single `SimulatorDataSource`
  handles every prefix

## PriceCache

```python
@dataclass(frozen=True)
class PriceUpdate:
    symbol: str
    price: float
    previous_price: float | None
    timestamp: datetime

    @property
    def change(self) -> float | None: ...
    @property
    def direction(self) -> Literal["up", "down", "flat"]: ...
```

The cache is a dict plus a lock plus a **version counter**. Every write bumps the version.

The SSE endpoint remembers the last version it sent and only pushes when the version has
moved. That is what stops the stream from spamming identical frames when GPW is closed and
nothing is changing.

## Choosing a source

```python
def create_market_data_source(cache: PriceCache, settings: Settings) -> MarketDataSource:
    if settings.market_mode == "simulator":
        return SimulatorDataSource(cache, seed=settings.seed)
    return CompositeDataSource(cache, settings)
```

One environment variable, no code change:

```bash
PULSEDESK_MARKET_MODE=simulator   # default — offline, free, deterministic
PULSEDESK_MARKET_MODE=live        # Binance + Stooq
```

## Contract tests

Because all sources implement the same ABC, they share one test suite:

```python
@pytest.mark.parametrize("source_factory", [
    lambda cache: SimulatorDataSource(cache, seed=42),
    lambda cache: BinanceDataSource(cache, transport=FakeWebSocket()),
    lambda cache: StooqDataSource(cache, transport=FakeHttp()),
])
async def test_source_contract(source_factory): ...
```

The suite asserts the behaviours the ABC promises: `start` populates the cache,
`stop` is idempotent, `remove_symbol` clears the cache entry, `add_symbol` on an unknown
symbol does not crash, and so on.

**This is the payoff of the abstraction.** Adding a fourth market later means writing one
class and adding one line to the parametrised list.

## Free data sources — reference

Sources considered, and why the two above won.

| Source | Coverage | Free tier | Key | Verdict |
|---|---|---|---|---|
| **Binance** | Crypto | Unlimited WS stream | No | **Chosen** — true real-time, no key |
| **Stooq** | GPW, WSE, some global | Unrestricted CSV | No | **Chosen** — only free GPW source |
| yfinance | Global equities, ETFs | Generous, unofficial | No | Viable fallback; unofficial scraping, can break |
| CoinGecko | Crypto | 30 req/min | No | Poll-only, slower than Binance |
| Finnhub | US equities | 60 req/min, WS | Yes | Good, but needs a key |
| Twelve Data | Multi-market | 800 req/day | Yes | Day limit too tight for streaming |
| Alpha Vantage | Equities | 25 req/day | Yes | Unusable for a live product |
| Polygon.io | US equities | Very limited | Yes | What the reference project used; paid in practice |

Verify current limits before relying on any of these — free tiers change.

## Adding a new source

1. Implement `MarketDataSource` in `app/market/<name>.py`
2. Add the prefix to `PREFIX_MAP` in `composite.py`
3. Add seed prices and GBM parameters for the new instruments in `seed_prices.py`
   so simulator mode covers them too
4. Add the factory lambda to the contract-test parametrisation
5. Record fixtures under `tests/fixtures/<name>/`

No other file should need to change. If one does, the abstraction has leaked — fix that
rather than working around it.
