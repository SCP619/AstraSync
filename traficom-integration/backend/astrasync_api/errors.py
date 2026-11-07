"""Standard error envelope (BSD section 5) for every failure path."""

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from .contract.enums import ErrorCode
from .contract.models import ApiErrorBody, ErrorResponse

_HTTP_STATUS_CODES = {
    401: ErrorCode.UNAUTHENTICATED,
    403: ErrorCode.FORBIDDEN,
    404: ErrorCode.NOT_FOUND,
    405: ErrorCode.NOT_FOUND,
    409: ErrorCode.CONFLICT,
    429: ErrorCode.RATE_LIMITED,
    501: ErrorCode.NOT_IMPLEMENTED,
    503: ErrorCode.SERVICE_UNAVAILABLE,
}


class ApiError(Exception):
    def __init__(
        self,
        status_code: int,
        code: ErrorCode,
        message: str,
        details: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}
        self.headers = headers or {}


def request_id_for(request: Request) -> str:
    """Server-generated, so a client cannot inject values into logs through a request header."""
    existing: str | None = getattr(request.state, "request_id", None)
    if existing is None:
        existing = uuid4().hex
        request.state.request_id = existing
    return existing


def _error_response(
    request: Request,
    status_code: int,
    code: ErrorCode,
    message: str,
    details: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    request_id = request_id_for(request)
    body = ErrorResponse(
        error=ApiErrorBody(
            code=code, message=message, details=details or {}, request_id=request_id
        )
    )
    return JSONResponse(
        status_code=status_code,
        content=body.model_dump(mode="json"),
        headers={"X-Request-ID": request_id, **(headers or {})},
    )


def install_error_handlers(app: FastAPI) -> None:
    @app.middleware("http")
    async def _assign_request_id(request: Request, call_next: Any) -> Any:
        request_id = request_id_for(request)
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        # Responses can hold restricted data and must not stay in shared or device caches.
        response.headers["Cache-Control"] = "no-store"
        return response

    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _error_response(
            request, exc.status_code, exc.code, exc.message, exc.details, exc.headers
        )

    @app.exception_handler(HTTPException)
    async def _http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = _HTTP_STATUS_CODES.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return _error_response(request, exc.status_code, code, str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def _validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Field location and type only: submitted values must not be echoed back or logged.
        issues = [
            {"location": list(error["loc"]), "type": error["type"], "message": error["msg"]}
            for error in exc.errors()
        ]
        return _error_response(
            request,
            422,
            ErrorCode.VALIDATION_ERROR,
            "Request validation failed.",
            {"issues": issues},
        )

    @app.exception_handler(Exception)
    async def _unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # Includes responses that break a contract invariant. Internals never reach the client.
        return _error_response(
            request, 500, ErrorCode.INTERNAL_ERROR, "An internal error occurred."
        )
