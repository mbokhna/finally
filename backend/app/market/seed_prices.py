from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class InstrumentSeed:
    symbol: str
    start_price: float
    drift: float
    volatility: float
    group: str


# drift/volatility are per-tick (Delta t = 1 in the GBM step), not annualised —
# the simulator ticks every 500ms and only needs plausible, visible movement.
SEEDS: tuple[InstrumentSeed, ...] = (
    InstrumentSeed("CRYPTO:BTCUSDT", 79000.0, 0.00002, 0.0025, "crypto"),
    InstrumentSeed("CRYPTO:ETHUSDT", 3000.0, 0.00002, 0.0030, "crypto"),
    InstrumentSeed("CRYPTO:SOLUSDT", 150.0, 0.00003, 0.0035, "crypto"),
    InstrumentSeed("CRYPTO:BNBUSDT", 600.0, 0.00002, 0.0028, "crypto"),
    InstrumentSeed("CRYPTO:XRPUSDT", 0.60, 0.00001, 0.0032, "crypto"),
    InstrumentSeed("GPW:PKN", 65.0, 0.000005, 0.0009, "gpw"),
    InstrumentSeed("GPW:PKO", 55.0, 0.000005, 0.0008, "gpw"),
    InstrumentSeed("GPW:PZU", 45.0, 0.000005, 0.0008, "gpw"),
    InstrumentSeed("GPW:KGH", 130.0, 0.000005, 0.0011, "gpw"),
    InstrumentSeed("GPW:CDR", 150.0, 0.000010, 0.0013, "gpw"),
)

SEED_BY_SYMBOL: dict[str, InstrumentSeed] = {seed.symbol: seed for seed in SEEDS}

GROUP_CORRELATION: dict[tuple[str, str], float] = {
    ("crypto", "crypto"): 0.7,
    ("gpw", "gpw"): 0.5,
    ("crypto", "gpw"): 0.1,
    ("gpw", "crypto"): 0.1,
}

SHOCK_PROBABILITY = 0.001
SHOCK_MIN_MAGNITUDE = 0.02
SHOCK_MAX_MAGNITUDE = 0.05


def default_seed(symbol: str) -> InstrumentSeed:
    """Fallback for a symbol added at runtime with no preset entry."""
    prefix = symbol.split(":", 1)[0]
    group = "crypto" if prefix == "CRYPTO" else "gpw"
    return InstrumentSeed(
        symbol=symbol, start_price=100.0, drift=0.0, volatility=0.002, group=group
    )
