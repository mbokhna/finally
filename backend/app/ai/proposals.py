from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal

# Matches any fenced ```proposal block regardless of what's inside, so even a
# malformed one is stripped from the prose the user sees — only a well-formed
# {...} body goes on to parse successfully in _parse_block.
_PROPOSAL_PATTERN = re.compile(r"```proposal\s*(.*?)\s*```", re.DOTALL)

Action = Literal["BUY", "SELL"]


@dataclass(frozen=True)
class Proposal:
    action: Action
    symbol: str
    quantity: float
    reason: str


@dataclass(frozen=True)
class ExtractedResponse:
    prose: str
    proposal: Proposal | None


def extract_proposal(text: str) -> ExtractedResponse:
    """Strips a fenced ```proposal block from the reply and parses it.

    The raw block — valid or not — never reaches the prose the user sees.
    An invalid block is dropped silently; the surrounding prose still shows.
    """
    match = _PROPOSAL_PATTERN.search(text)
    if match is None:
        return ExtractedResponse(prose=text.strip(), proposal=None)

    prose = (text[: match.start()] + text[match.end() :]).strip()
    return ExtractedResponse(prose=prose, proposal=_parse_block(match.group(1)))


def _parse_block(raw: str) -> Proposal | None:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None

    raw_action = data.get("action")
    action: Action
    if raw_action == "BUY":
        action = "BUY"
    elif raw_action == "SELL":
        action = "SELL"
    else:
        return None

    symbol = data.get("symbol")
    if not isinstance(symbol, str) or ":" not in symbol:
        return None

    quantity = data.get("quantity")
    if not isinstance(quantity, int | float) or isinstance(quantity, bool) or quantity <= 0:
        return None

    reason = data.get("reason")
    if not isinstance(reason, str):
        reason = ""

    return Proposal(action=action, symbol=symbol, quantity=float(quantity), reason=reason)
