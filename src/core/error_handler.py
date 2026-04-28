"""
Централизованная обработка ошибок.
"""

import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError as PydanticValidationError

from src.core.exceptions import AppException

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI) -> None:
    """Регистрирует все обработчики ошибок на приложении."""

    # --- Наши кастомные исключения ---
    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        logger.warning(
            f"[{exc.__class__.__name__}] {exc.detail} | "
            f"path={request.url.path} | context={exc.context}"
        )
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error":   exc.__class__.__name__,
                "detail":  exc.detail,
                "path":    str(request.url.path),
            },
        )

    # --- Ошибки валидации Pydantic (входные данные) ---
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        errors = []
        for err in exc.errors():
            errors.append({
                "field":   " → ".join(str(loc) for loc in err["loc"]),
                "message": err["msg"],
                "type":    err["type"],
            })

        logger.warning(f"[ValidationError] path={request.url.path} | errors={errors}")
        return JSONResponse(
            status_code=422,
            content={
                "error":   "ValidationError",
                "detail":  "Ошибка валидации входных данных",
                "errors":  errors,
                "path":    str(request.url.path),
            },
        )

    # --- Необработанные исключения (500) ---
    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            f"[UnhandledException] {type(exc).__name__}: {exc} | "
            f"path={request.url.path}",
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error":  "InternalServerError",
                "detail": "Внутренняя ошибка сервера",
                "path":   str(request.url.path),
            },
        )