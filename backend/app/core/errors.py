"""Uniform error envelope.

Every non-2xx response in the API has exactly this shape (plan.md 6.1)::

    {"error": {"code": "...", "message": "...", "field": null, "details": {}}}

``code`` is a stable machine-readable enum - the frontend renders its own
translation of it and only falls back to ``message``. ``message`` is
localised server-side from Accept-Language.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.i18n import translate_error
from app.core.logging import get_logger

log = get_logger(__name__)


class ErrorCode(StrEnum):
    """Stable error codes. Add to this enum, never invent strings inline."""

    # --- generic ---
    INTERNAL_ERROR = "INTERNAL_ERROR"
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    RATE_LIMITED = "RATE_LIMITED"
    PAYLOAD_TOO_LARGE = "PAYLOAD_TOO_LARGE"

    # --- auth ---
    UNAUTHORIZED = "UNAUTHORIZED"
    FORBIDDEN = "FORBIDDEN"
    TOKEN_EXPIRED = "TOKEN_EXPIRED"
    TOKEN_INVALID = "TOKEN_INVALID"
    REFRESH_REUSED = "REFRESH_REUSED"
    GOOGLE_NOT_CONFIGURED = "GOOGLE_NOT_CONFIGURED"
    GOOGLE_TOKEN_INVALID = "GOOGLE_TOKEN_INVALID"
    PHONE_AUTH_DISABLED = "PHONE_AUTH_DISABLED"
    PHONE_NOT_VERIFIED = "PHONE_NOT_VERIFIED"
    OTP_INVALID = "OTP_INVALID"
    OTP_EXPIRED = "OTP_EXPIRED"
    OTP_TOO_MANY_ATTEMPTS = "OTP_TOO_MANY_ATTEMPTS"

    # --- domain ---
    CART_EMPTY = "CART_EMPTY"
    PRODUCT_UNAVAILABLE = "PRODUCT_UNAVAILABLE"
    CATEGORY_NOT_EMPTY = "CATEGORY_NOT_EMPTY"
    UPLOAD_REJECTED = "UPLOAD_REJECTED"


# ---------------------------------------------------------------------------
# OpenAPI documentation of the envelope
# ---------------------------------------------------------------------------
class ErrorDetail(BaseModel):
    code: str = Field(description="Stable machine-readable enum member")
    message: str = Field(description="Localised text; clients prefer their own copy of `code`")
    field: str | None = Field(default=None, description="Offending field, for 422s")
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorEnvelope(BaseModel):
    """The shape of EVERY non-2xx response (plan.md 6.1).

    Declared as a model so Swagger documents what the API actually returns.
    Without it FastAPI advertises its own `HTTPValidationError` for 422 and
    says nothing at all about 401/403/404 - so the documented error contract
    would be one the server never emits.
    """

    error: ErrorDetail


_DESCRIPTIONS: dict[int, str] = {
    400: "Bad request - see `error.code`",
    401: "Missing, expired or invalid access token",
    403: "Authenticated but not allowed (`FORBIDDEN`, `PHONE_NOT_VERIFIED`)",
    404: "No such resource, or the feature is switched off",
    409: "Conflict with current state (`CATEGORY_NOT_EMPTY`)",
    413: "Payload too large",
    422: "Validation failed; `error.field` names the offender",
    429: "Rate limited",
    500: "Unhandled server error - never carries internals",
}


def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` for a router or route, documenting the real envelope."""
    return {
        code: {"model": ErrorEnvelope, "description": _DESCRIPTIONS[code]} for code in sorted(codes)
    }


class AppError(Exception):
    """Base class for every deliberate error the API raises."""

    status_code: int = status.HTTP_400_BAD_REQUEST
    code: ErrorCode = ErrorCode.INTERNAL_ERROR

    def __init__(
        self,
        code: ErrorCode | None = None,
        *,
        status_code: int | None = None,
        field: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.code = code or self.code
        self.status_code = status_code or self.status_code
        self.field = field
        self.details = details or {}
        super().__init__(self.code)


class NotFoundError(AppError):
    status_code = status.HTTP_404_NOT_FOUND
    code = ErrorCode.NOT_FOUND


class UnauthorizedError(AppError):
    status_code = status.HTTP_401_UNAUTHORIZED
    code = ErrorCode.UNAUTHORIZED


class ForbiddenError(AppError):
    status_code = status.HTTP_403_FORBIDDEN
    code = ErrorCode.FORBIDDEN


def _envelope(
    code: str,
    message: str,
    field: str | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "error": {
            "code": code,
            "message": message,
            "field": field,
            "details": details or {},
        }
    }


def _lang_of(request: Request) -> str:
    """Resolve response language: ?lang= wins, then Accept-Language, then az."""
    q = request.query_params.get("lang")
    if q in ("az", "en"):
        return q
    header = request.headers.get("accept-language", "")
    return "en" if header[:2].lower() == "en" else "az"


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(
                exc.code.value,
                translate_error(exc.code.value, _lang_of(request)),
                exc.field,
                exc.details,
            ),
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        first = exc.errors()[0] if exc.errors() else {}
        loc = [str(p) for p in first.get("loc", []) if p not in ("body", "query", "path")]
        return JSONResponse(
            # Starlette deprecated the ENTITY spelling; same 422 either way.
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=_envelope(
                ErrorCode.VALIDATION_ERROR.value,
                translate_error(ErrorCode.VALIDATION_ERROR.value, _lang_of(request)),
                ".".join(loc) or None,
                {"reason": first.get("msg", "")},
            ),
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = {
            401: ErrorCode.UNAUTHORIZED,
            403: ErrorCode.FORBIDDEN,
            404: ErrorCode.NOT_FOUND,
            413: ErrorCode.PAYLOAD_TOO_LARGE,
            429: ErrorCode.RATE_LIMITED,
        }.get(exc.status_code, ErrorCode.INTERNAL_ERROR)
        return JSONResponse(
            status_code=exc.status_code,
            content=_envelope(code.value, translate_error(code.value, _lang_of(request))),
            headers={"Cache-Control": "no-store"},
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        # Log the detail, return none of it - stack traces are not a public API.
        log.exception("unhandled_error", path=request.url.path, error=type(exc).__name__)
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_envelope(
                ErrorCode.INTERNAL_ERROR.value,
                translate_error(ErrorCode.INTERNAL_ERROR.value, _lang_of(request)),
            ),
            headers={"Cache-Control": "no-store"},
        )
