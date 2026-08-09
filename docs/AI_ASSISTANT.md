# AI Assistant

An optional analyst living in a drawer. Everything about its design follows from two rules:

1. **It must never get in the way.** Closed by default, opened by one click, overlaying the
   terminal rather than displacing it.
2. **It must never be required.** No key, no problem — every other feature works untouched.

## Interaction model

```
┌──────────────────────────────────────────────┬────────────────┐
│                                              │                │
│   Watchlist        Chart                     │   AI drawer    │
│                                              │   400 px       │
│   Positions        P&L                       │   slides in    │
│                                              │   over the     │
│                                       ┌────┐ │   terminal     │
│                                       │ AI │ │                │
└───────────────────────────────────────┴────┴─┴────────────────┘
                                          ▲
                        floating button, bottom-right, always visible
```

**Rules for the drawer:**

- `position: fixed`, `right: 0`, full height, `z-index` above the grid
- Slides in with a 200 ms transform transition — transform only, never `width` on the
  parent, so the terminal grid never reflows
- Terminal content behind it stays live: prices keep ticking while the drawer is open
- Closes on `Esc`, on the button, and on click outside the drawer
- Open/closed state in `localStorage` under `pulsedesk.ai.open`, defaulting to **closed**
- On viewports under 900 px the drawer goes full-width — no side-by-side squeeze

**Rules for the button:**

- 56 px circle, bottom-right, 24 px inset
- Visible whether or not the key is configured — discoverability matters more than hiding
  an unconfigured feature
- Subtle unread dot when the assistant has finished a response while closed

## Backend

```
app/ai/
├── client.py      OpenRouter HTTP client, streaming
├── context.py     assembles portfolio/price/trade context
├── prompts.py     system prompt
├── proposals.py   parses and validates proposed actions
└── __init__.py

app/api/ai.py      POST /api/ai/chat  (SSE), GET /api/ai/status
```

`app/ai/` may read from `portfolio`, `market` (cache), and `alerts`. Nothing may import
**from** `app/ai/` except `app/api/` — the assistant is a leaf, and removing it must never
break anything else.

### OpenRouter client

OpenRouter exposes an OpenAI-compatible endpoint:

```
POST https://openrouter.ai/api/v1/chat/completions
Authorization: Bearer $OPENROUTER_API_KEY
```

Use `httpx` directly rather than an SDK — the request is a single JSON POST and an SDK is
weight for nothing.

Model selection:

```python
model = settings.ai_model            # e.g. "some-provider/some-model:free"
if not model.endswith(":free"):
    raise ConfigError("PULSEDESK_AI_MODEL must be a free-tier model (ending in ':free')")
```

Pick a current model from https://openrouter.ai/models filtered to free — the free roster
changes, so treat the id as configuration, never as a constant in code.

**Failure handling:**

| Condition | Response |
|---|---|
| No key | `503` with `"AI assistant not configured"` — the panel renders a setup hint |
| `429` from OpenRouter | `429` passed through; panel shows "rate limited, try again shortly" |
| Upstream 5xx or timeout | `503` with a plain message; never surface a raw stack trace |
| Model returns malformed proposal JSON | Drop the proposal, keep the prose reply |

Free tiers are rate-limited by design. Treat `429` as an expected state, not an incident.

### Context assembly

Built fresh per request, server-side. The client never sends portfolio data up — it sends
only the user's message, and the server attaches the truth it already holds.

```python
def build_context() -> str:
    return textwrap.dedent(f"""
        CASH: {cash:.2f} {currency}
        TOTAL VALUE: {total:.2f} {currency}

        POSITIONS:
        {positions_table}

        PRICES (watchlist):
        {prices_table}

        RECENT TRADES (last 10):
        {trades_table}

        ACTIVE ALERTS:
        {alerts_table}
    """)
```

Keep it compact — free-tier models have smaller context windows and stricter rate limits.
Tables as plain text, not JSON: fewer tokens, and models read them fine.

### Proposals, not actions

The system prompt instructs the model that when it wants to act, it appends a fenced block:

````
```proposal
{"action": "BUY", "symbol": "CRYPTO:BTCUSDT", "quantity": 0.05,
 "reason": "Reduces cash drag; crypto weight is currently 4%"}
```
````

The backend:

1. Extracts the block, strips it from the prose
2. Validates it — known action, known symbol, positive quantity, sufficient cash or shares
3. Emits it as a separate SSE event of type `proposal`
4. **Does nothing else.** No trade is executed.

The frontend renders it as a card with the parameters and a **Confirm** button. Confirming
calls the ordinary `POST /api/trade` — the same endpoint the manual buy form uses, with the
same validation. There is no privileged path for the AI.

Invalid proposals are dropped silently and logged; the prose reply still shows.

## System prompt

Kept in `prompts.py`, versioned like code.

```
You are the analyst panel inside PulseDesk, a paper-trading terminal for crypto and
Warsaw Stock Exchange equities. The portfolio is virtual — no real money is involved.

You will be given the user's current cash, positions, prices, recent trades, and alerts.
Answer from that context. If the context does not contain what you need, say so plainly
rather than guessing at a number.

Be concise. This is a data terminal: two or three sentences beat a paragraph. Use figures
from the context rather than vague descriptions.

When the user asks you to trade, set an alert, or change the watchlist, emit a proposal
block. Never claim to have performed an action — you cannot. The user confirms every action
themselves.

Do not give real-world financial advice, and do not speculate about future prices. You are
analysing a simulated portfolio, not advising an investor.
```

That last paragraph matters. A free model asked "should I buy Bitcoin" will happily answer;
the prompt keeps it describing the portfolio rather than issuing recommendations.

## Frontend

```
src/components/ai/
├── AiButton.tsx       floating trigger + unread dot
├── AiDrawer.tsx       the panel, transform animation, Esc handling
├── AiMessage.tsx      one message; markdown rendering
├── AiProposal.tsx     proposal card with Confirm
└── useAiChat.ts       SSE consumption, message state
```

Chat history lives in component state only — it is cleared on reload. Persisting it would
mean another table and a migration for something nobody re-reads.

Reuse the existing SSE hook from the price stream rather than adding a second mechanism.

## Configuration

```bash
# Optional. Without it the assistant is disabled and everything else works.
OPENROUTER_API_KEY=sk-or-v1-...

# Must end in ':free'. Pick a current one from https://openrouter.ai/models
PULSEDESK_AI_MODEL=some-provider/some-model:free

# Cap the response length — free tiers are rate-limited
PULSEDESK_AI_MAX_TOKENS=800
```

## Testing

- **No network in tests.** The OpenRouter client is tested against a fake transport
- Context assembly tested directly: known portfolio state → expected string
- Proposal parsing tested with valid blocks, malformed JSON, unknown symbols, and
  quantities exceeding the balance
- One integration test asserts that **with no key set, every other endpoint still works**
  and `/api/health` reports `"ai": "unconfigured"`
- Frontend: drawer opens and closes, terminal grid does not reflow when it opens

That reflow test is the one that protects the design decision. Without it, someone will
eventually switch the drawer to a flex sibling and quietly break the layout.
