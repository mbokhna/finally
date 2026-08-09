# Build Order

Phases are ordered by dependency. Do not skip ahead — each phase leaves the project in a
working, testable state.

Every phase ends with: **tests pass, commit made, nothing broken.**

Estimated total: 2–3 focused days.

---

## Phase 0 — Skeleton

**Goal:** an empty app that starts.

- [x] `backend/pyproject.toml` with uv, FastAPI, uvicorn, pytest, mypy, ruff
- [x] `app/main.py` — FastAPI instance, `/api/health` returning `{"status": "ok"}`
- [x] `app/config.py` — `Settings` loaded from env with the defaults in `PLAN.md` §8
- [x] `tests/test_health.py`

**Done when:** `uv run uvicorn app.main:app` serves `/api/health`.

---

## Phase 1 — Market data core

**Goal:** prices exist in memory. No HTTP yet.

Read `docs/MARKET_DATA.md` first.

- [x] `market/models.py` — `PriceUpdate` (frozen), `Candle`
- [x] `market/interface.py` — the `MarketDataSource` ABC
- [x] `market/cache.py` — `PriceCache` with lock and version counter
- [x] `market/seed_prices.py` — starting prices, per-symbol drift/volatility, correlation groups
- [x] `market/simulator.py` — GBM with Cholesky-correlated draws, seeded RNG, shock events
- [x] `market/factory.py` — returns the simulator for now
- [x] `tests/market/` — cache, models, simulator determinism

**Done when:** a seeded simulator produces the identical price sequence across two runs.

---

## Phase 2 — Streaming to the browser

**Goal:** prices visible in `curl`.

- [x] `market/stream.py` — SSE endpoint, version-based change detection
- [x] `api/market.py` — `GET /api/prices`, `GET /api/stream/prices`
- [x] Wire the data source into FastAPI lifespan (start on boot, stop on shutdown)
- [x] Integration test with `TestClient`

**Done when:** `curl -N localhost:8000/api/stream/prices` prints a live event stream.

---

## Phase 3 — Persistence and portfolio

**Goal:** you can buy and sell.

- [x] `db.py` — SQLite connection, schema from `PLAN.md` §7, lazy init, seed on first run
- [x] `portfolio/models.py` — `Position`, `Trade`
- [x] `portfolio/service.py` — `buy()`, `sell()`, `get_positions()`, `get_valuation()`
- [x] `api/portfolio.py` — `GET /api/portfolio`, `POST /api/trade`
- [x] `api/watchlist.py` — `GET`/`POST`/`DELETE /api/watchlist`
- [x] Tests: average cost on repeated buys, partial sell, insufficient cash, insufficient shares

**Careful:** average cost changes on buy but **not** on sell. Realised P&L is booked on sell.
This is where bugs hide — test it hard.

**Done when:** buy 10, buy 10 more at a different price, sell 5 — average cost and cash are correct.

---

## Phase 4 — Frontend shell

**Goal:** something on screen.

- [x] Vite + React + TypeScript scaffold in `frontend/`
- [x] `useEventSource` hook consuming `/api/stream/prices`
- [x] Watchlist grid with green/red flash on tick (CSS transition, ~500 ms fade)
- [x] Positions table
- [x] Cash + total value header
- [x] Buy/sell form
- [x] Vite build outputs into `backend/static/`; FastAPI serves it

**Done when:** open `localhost:8000`, see prices ticking, place a trade, see the position appear.

---

## Phase 5 — Live data

**Goal:** real prices.

- [x] `market/binance.py` — WebSocket client, reconnect with exponential backoff,
      runtime subscribe/unsubscribe, `get_candles` via REST klines
- [x] `market/stooq.py` — CSV poller, 60 s interval, "N/D" handling, daily history
- [x] `market/composite.py` — prefix router, lazy child start
- [x] Update `factory.py` to honour `PULSEDESK_MARKET_MODE`
- [x] `tests/market/test_contract.py` — parametrised contract suite over all three sources
- [x] Fixtures under `tests/fixtures/`

**Done when:** `PULSEDESK_MARKET_MODE=live` streams real BTC and PKN prices, and switching
back to `simulator` still works with no code change.

**Verified live 2026-08-09:** Binance streams real trades correctly (BTCUSDT ticking at its
real market price, cache version climbing fast). Stooq's documented endpoints have changed
since `docs/MARKET_DATA.md` was written — `/q/l/` now 404s outright and `/q/d/l/` sits behind
a JS proof-of-work challenge, for every symbol, not just GPW ones. `StooqDataSource` handles
this exactly as designed: any non-CSV or error response degrades to "no update" (same path as
"N/D"), so live mode runs with crypto prices flowing and GPW simply absent, no crash. Re-check
whether Stooq is reachable before relying on real GPW prices; the contract/unit tests don't
depend on it since they run against fixtures.

---

## Phase 6 — Alerts

- [x] `alerts/models.py`, `alerts/engine.py` — evaluated on each cache write
- [x] `api/alerts.py` — CRUD
- [x] SSE channel `/api/stream/alerts`
- [x] Frontend: alert list, create form, browser notification on fire
- [x] Tests: fires once and only once, both directions, deleted alert never fires

---

## Phase 7 — Backtest

- [x] `backtest/strategies.py` — moving-average crossover, parametrised windows
- [x] `backtest/runner.py` — walk candles, simulate fills, produce an equity curve
- [x] `api/backtest.py` — `POST /api/backtest`
- [x] Frontend: instrument picker, MA inputs, equity curve chart
- [x] Tests: known candle series → known trade list

**Careful:** do not look ahead. A signal computed from candle `i` may only be executed at
candle `i+1`'s open. Look-ahead bias is the classic backtest bug.

---

## Phase 8 — AI assistant (optional feature)

**Goal:** a drawer that answers questions about the portfolio, and disappears completely
when unconfigured.

Read `docs/AI_ASSISTANT.md` first.

- [x] `ai/client.py` — OpenRouter via httpx, streaming, `:free` model validation at startup
- [x] `ai/context.py` — compact plain-text portfolio/price/trade/alert context
- [x] `ai/prompts.py` — system prompt
- [x] `ai/proposals.py` — extract and validate proposal blocks
- [x] `api/ai.py` — `POST /api/ai/chat` (SSE), `GET /api/ai/status`
- [x] `/api/health` reports `"ai": "configured" | "unconfigured"`
- [x] Frontend: `AiButton`, `AiDrawer`, `AiMessage`, `AiProposal`, `useAiChat`
- [x] Tests: fake transport, context assembly, proposal parsing, **app fully works with
      no key set**, drawer opening does not reflow the terminal grid

**Careful:** the drawer overlays with `transform`; it must not be a flex sibling of the
grid. And the AI never calls `/api/trade` — the Confirm button does, through the ordinary
endpoint.

**Done when:** with `OPENROUTER_API_KEY` unset, every test passes and the terminal is
unchanged; with it set, the drawer answers questions and proposes trades that require a click.

**Notes from implementation:**
- `Settings.ai_configured` requires *both* a key and a model ending in `:free`. A key with a
  non-free model is treated as unconfigured (503, not a startup crash) — the assistant must
  never be able to take down the rest of the app (PLAN.md §11 / non-negotiable #1b).
- The chat SSE response is not token-by-token: `open_chat_stream`/`iter_tokens` fully buffer
  the OpenRouter reply server-side before emitting one `token` event and (if present) one
  `proposal` event. This was deliberate — streaming raw deltas to the browser would flash the
  raw ` ```proposal ` fence before it could be parsed and stripped, which the spec explicitly
  rules out ("Extracts the block, strips it from the prose"). True incremental streaming with
  fence look-ahead is a reasonable v2 improvement, not required for v1.
- 429 from OpenRouter needs to surface as a real HTTP 429, but by the time an SSE
  `StreamingResponse` starts, the status code can't change. `open_chat_stream` uses
  `http_client.send(request, stream=True)` (not the `client.stream()` context manager) so the
  route can inspect `response.status_code` *before* deciding whether to return a
  `StreamingResponse` at all.
- Verified live end-to-end against the real OpenRouter API with `openai/gpt-oss-20b:free`:
  asked a real question, got a correct answer from live portfolio state; asked for a trade
  proposal, got a valid `proposal` event, clicked Confirm, and the trade executed through the
  ordinary `/api/trade` endpoint (cash and positions updated correctly). Also verified with no
  key set: drawer shows the unconfigured message, and the terminal grid's bounding box is
  pixel-identical before and after opening the drawer.

---

## Phase 9 — Local packaging

**Goal:** one command starts the whole product on this machine.

This is packaging for local use, **not deployment**. Nothing here targets a cloud host —
see `PLAN.md` §2a.

- [x] Multi-stage `Dockerfile` — node build → python runtime, static copied in
- [x] `docker-compose.yml` with a named volume for `/data`, port bound to `127.0.0.1:8000`
- [x] `start.sh` / `stop.sh`
- [x] README quickstart verified from a clean clone with no `.env` and no network
- [x] Full test suite green, `mypy --strict` clean, `ruff` clean

**Done when:** a clean clone runs `./start.sh` and works offline in simulator mode.

**Caught during verification:** the first `CMD` used `uv run uvicorn ...`. `uv run`
re-checks the project's full sync state (dev dependency group included) on every
invocation and reaches for the network to fix any mismatch against the image's
`--no-dev` install — so the container failed outright under `docker run --network
none`. Fixed by calling the venv's `uvicorn` binary directly (`.venv/bin/uvicorn`),
bypassing `uv run`'s sync check entirely. Re-verified with `--network none`: starts
clean, all 10 default symbols streaming. Also confirmed data survives a container
restart (named volume) and the port is bound to `127.0.0.1` only.

---

## Deferred (v2)

Deliberately out of scope for v1 — listed so nobody adds them by accident.

- Multi-user accounts and auth
- More markets (US equities via yfinance, forex)
- Additional strategies (RSI, Bollinger, pairs)
- Persisted chat history

## Never in scope

Not "later" — excluded by the project constraints in `PLAN.md` §2a.

- Any paid data provider, paid service, or paid model
- Any credential other than the optional `OPENROUTER_API_KEY`
- The AI executing an action without an explicit user click
- Deployment or cloud hosting of any kind

---

## Working notes

- Run `uv run pytest` at the end of every phase, not at the end of the project.
- Commit per phase minimum; per logical change is better.
- If a phase feels too big for one session, split at a natural seam and note where you stopped.
- Keep `PLAN.md` and `CLAUDE.md` accurate as decisions change — they are the context that
  saves you from re-reading the whole codebase next session.
