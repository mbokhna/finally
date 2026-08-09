from __future__ import annotations

from app.ai.proposals import extract_proposal


def test_no_proposal_block_returns_prose_unchanged() -> None:
    result = extract_proposal("Your BTC position is up 4% today.")

    assert result.prose == "Your BTC position is up 4% today."
    assert result.proposal is None


def test_valid_proposal_is_extracted_and_stripped_from_prose() -> None:
    text = (
        "Your worst performer is GPW:CDR, down 8.2%.\n"
        "```proposal\n"
        '{"action": "SELL", "symbol": "GPW:CDR", "quantity": 10, "reason": "largest drag"}\n'
        "```"
    )

    result = extract_proposal(text)

    assert result.prose == "Your worst performer is GPW:CDR, down 8.2%."
    assert result.proposal is not None
    assert result.proposal.action == "SELL"
    assert result.proposal.symbol == "GPW:CDR"
    assert result.proposal.quantity == 10.0
    assert result.proposal.reason == "largest drag"
    assert "```" not in result.prose


def test_malformed_json_drops_proposal_but_keeps_prose() -> None:
    text = "Here's an idea.\n```proposal\n{not valid json\n```"

    result = extract_proposal(text)

    assert result.prose == "Here's an idea."
    assert result.proposal is None


def test_unknown_action_is_rejected() -> None:
    text = '```proposal\n{"action": "HOLD", "symbol": "CRYPTO:BTCUSDT", "quantity": 1}\n```'

    result = extract_proposal(text)

    assert result.proposal is None


def test_non_positive_quantity_is_rejected() -> None:
    text = '```proposal\n{"action": "BUY", "symbol": "CRYPTO:BTCUSDT", "quantity": 0}\n```'

    result = extract_proposal(text)

    assert result.proposal is None


def test_negative_quantity_is_rejected() -> None:
    text = '```proposal\n{"action": "BUY", "symbol": "CRYPTO:BTCUSDT", "quantity": -5}\n```'

    result = extract_proposal(text)

    assert result.proposal is None


def test_symbol_without_market_prefix_is_rejected() -> None:
    text = '```proposal\n{"action": "BUY", "symbol": "BTCUSDT", "quantity": 1}\n```'

    result = extract_proposal(text)

    assert result.proposal is None


def test_missing_reason_defaults_to_empty_string() -> None:
    text = '```proposal\n{"action": "BUY", "symbol": "CRYPTO:BTCUSDT", "quantity": 1}\n```'

    result = extract_proposal(text)

    assert result.proposal is not None
    assert result.proposal.reason == ""


def test_boolean_quantity_is_rejected() -> None:
    # bool is a subclass of int in Python — must not sneak past the quantity check.
    text = '```proposal\n{"action": "BUY", "symbol": "CRYPTO:BTCUSDT", "quantity": true}\n```'

    result = extract_proposal(text)

    assert result.proposal is None
