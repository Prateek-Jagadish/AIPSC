"""
core/error_handlers.py
──────────────────────
Global exception handlers for the FastAPI application.
Provides structured JSON error responses for all error types.
"""

from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.exc import IntegrityError, OperationalError
from loguru import logger


def setup_error_handlers(app: FastAPI) -> None:
    """
    Register global exception handlers on the FastAPI app.
    """

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """
        Structured 4xx/5xx HTTP errors.
        """
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": True,
                "status_code": exc.status_code,
                "message": exc.detail,
                "type": "http_error",
            },
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """
        422 Validation errors — make them readable.
        """
        errors = []
        for err in exc.errors():
            field = " → ".join(str(loc) for loc in err["loc"]) if err.get("loc") else "unknown"
            errors.append({
                "field": field,
                "message": err.get("msg", "Invalid value"),
                "type": err.get("type", "validation_error"),
            })

        logger.warning(f"⚠️ Validation error: {errors}")

        return JSONResponse(
            status_code=422,
            content={
                "error": True,
                "status_code": 422,
                "message": "Request validation failed",
                "type": "validation_error",
                "details": errors,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """
        Database integrity errors (duplicate key, FK violation, etc.)
        """
        logger.error(f"🔴 DB IntegrityError: {exc.orig}")
        return JSONResponse(
            status_code=409,
            content={
                "error": True,
                "status_code": 409,
                "message": "Database conflict — this record may already exist.",
                "type": "integrity_error",
            },
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        """
        Database connection errors.
        """
        logger.error(f"🔴 DB OperationalError: {exc.orig}")
        return JSONResponse(
            status_code=503,
            content={
                "error": True,
                "status_code": 503,
                "message": "Database is temporarily unavailable. Please try again.",
                "type": "database_error",
            },
        )

    @app.exception_handler(Exception)
    async def catch_all_handler(request: Request, exc: Exception):
        """
        Catch-all for unhandled exceptions.
        Never leak stack traces to the client.
        """
        logger.exception(f"🔴 Unhandled exception on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "status_code": 500,
                "message": "An internal error occurred. Our team has been notified.",
                "type": "internal_error",
            },
        )
