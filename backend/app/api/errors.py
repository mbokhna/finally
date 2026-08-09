from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.errors import (
    BusinessRuleError,
    NotFoundError,
    RateLimitedError,
    UpstreamUnavailableError,
    ValidationError,
)

ExceptionHandler = Callable[[Request, Exception], Awaitable[JSONResponse]]

_STATUS_BY_ERROR: dict[type[Exception], int] = {
    ValidationError: 400,
    NotFoundError: 404,
    BusinessRuleError: 409,
    RateLimitedError: 429,
    UpstreamUnavailableError: 503,
}


def register_error_handlers(app: FastAPI) -> None:
    for error_type, status_code in _STATUS_BY_ERROR.items():
        app.add_exception_handler(error_type, _make_handler(status_code))


def _make_handler(status_code: int) -> ExceptionHandler:
    async def handler(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exc)})

    return handler
