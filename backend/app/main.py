from __future__ import annotations

from fastapi import FastAPI

app = FastAPI(title="PulseDesk")


@app.get("/api/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
