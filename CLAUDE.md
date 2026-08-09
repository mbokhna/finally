# CLAUDE.md — working agreement for this repository

Read this before making any change. `PLAN.md` is the specification; this file is *how* to work.

## Project in one line

PulseDesk — a self-hosted trading terminal streaming live crypto (Binance) and GPW (Stooq)
prices into a paper-trading portfolio, with alerts and a lightweight backtester.

## Non-negotiables

1. **Zero cost, always.** Never introduce anything requiring payment — data sources,
   libraries, services, or models. Exactly **one** credential exists in this project:
   the optional `OPENROUTER_API_KEY`, and the model it uses must end in `:free`. No other
   key may be added. If a task appears to need one, stop and say so. See `PLAN.md` §2a.
1b. **The AI assistant is optional and non-intrusive.** With no key set, every other
   feature and every test must pass unchanged. The drawer is closed by default, opens on
   click, and overlays the terminal — it must never reflow the grid. The AI proposes
   actions; only a user click executes them, through the ordinary `/api/trade` endpoint.
1a. **Local only. Never deploy.** No fly.io, Render, Railway, Vercel, AWS, or any cloud
   target. Do not add deploy steps, deploy workflows, or hosting configuration. Docker here
   is packaging so the app starts with one command locally — nothing more.
2. **The simulator must always work offline.** A fresh clone with no network and no `.env`
   must start and stream prices. Never let live-mode code paths break simulator mode.
3. **Everything goes through `MarketDataSource`.** No module outside `app/market/` may
   import `binance`, `httpx` for Stooq, or reference a vendor by name.
4. **`PriceCache` is the single source of truth for prices.** Producers write to it,
   consumers read from it. No consumer ever calls a data source directly.

## Layer rules

```
app/api/         may import  →  app/portfolio, app/alerts, app/backtest, app/market
app/portfolio/   may import  →  app/market (cache only), app/db
app/alerts/      may import  →  app/market (cache only), app/db
app/backtest/    may import  →  app/market (models only), app/db
app/market/      may import  →  nothing from app/ except app/config
```

If a change would violate this, propose an interface instead of reaching across layers.

## Code conventions

- Python 3.12, `from __future__ import annotations` at the top of every module
- Full type hints on every public function; `mypy --strict` must pass
- Dataclasses for value objects; `frozen=True` where the object represents an event
- `async def` for anything that touches I/O; never block the event loop
- Errors: raise domain exceptions from `app/errors.py`, translate to HTTP only in `app/api/`
- No comments that restate the code. Comment *why*, never *what*
- Line length 100

Frontend:
- TypeScript strict mode, no `any`
- Components are function components with typed props; no class components
- No global state library — `useState` plus one `PriceContext` is enough for v1

## Testing rules

- Every new module gets tests in the same commit
- The simulator uses a seeded RNG — tests must be deterministic, never flaky
- **Contract tests**: `tests/market/test_contract.py` runs the same suite against every
  `MarketDataSource` implementation. Adding a new source means adding it to that
  parametrised list, not writing a separate suite.
- Never hit the network in a test. Binance and Stooq are tested against fixtures in
  `tests/fixtures/`
- Run `uv run pytest` before declaring anything done

## Commit conventions

Conventional commits, one logical change per commit:

```
feat(market): add Binance WebSocket data source
fix(portfolio): correct average cost on partial sell
test(market): add contract suite for data sources
docs: document the instrument symbol format
refactor(api): extract watchlist router
chore: bump uv lock
```

Do not bundle unrelated changes. Do not commit unless asked.

## Working style

- **Plan before writing code** for anything spanning more than one file.
- Follow `docs/BUILD_ORDER.md`. Phases are ordered by dependency — do not skip ahead.
- When a phase is complete, run the full test suite and say so explicitly.
- If the spec is ambiguous, state the assumption in your reply and continue — do not stall.
- Prefer editing an existing module over creating a new one.
- Do not add libraries without saying why the standard library is insufficient.

## Cost discipline

This project is deliberately built in a single session context.

- Do **not** spawn sub-agents or agent teams — they re-read the codebase from scratch.
- Do **not** read the whole repository when a task touches two files. Name the files.
- Keep this file and `PLAN.md` current — they are the context that replaces re-reading code.

## Commands

```bash
# backend
cd backend && uv sync
uv run uvicorn app.main:app --reload      # dev server on :8000
uv run pytest                             # tests
uv run mypy app                           # type check
uv run ruff check app                     # lint

# frontend
cd frontend && npm install
npm run dev                               # vite dev server on :5173
npm run build                             # static build into backend/static/

# whole product
./start.sh                                # docker build + run on :8000
```
