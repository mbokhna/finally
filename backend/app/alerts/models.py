from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal

Condition = Literal["ABOVE", "BELOW"]


@dataclass(frozen=True)
class Alert:
    id: int
    symbol: str
    condition: Condition
    threshold: float
    triggered: bool
    created_at: datetime
