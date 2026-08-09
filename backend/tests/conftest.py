from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from app.config import get_settings


@pytest.fixture(autouse=True)
def _isolated_db_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[None]:
    """Every test gets its own temp SQLite file — never the /data default,

    which isn't writable outside the Docker container this project targets.
    """
    monkeypatch.setenv("PULSEDESK_DB_PATH", str(tmp_path / "pulsedesk.db"))
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()
