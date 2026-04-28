"""
Кастомные исключения системы.

Иерархия:
  AppException              — базовое исключение
  ├── NotFoundError         — 404
  ├── ValidationError       — 422
  ├── AuthError             — 401
  ├── AnalysisError         — ошибки модуля анализа
  ├── GenerationError       — ошибки LLM генерации
  └── DatabaseError         — ошибки БД
"""

from typing import Optional, Any


class AppException(Exception):
    """Базовое исключение приложения."""
    status_code: int = 500
    detail:      str = "Внутренняя ошибка сервера"

    def __init__(self, detail: Optional[str] = None, context: Optional[Any] = None):
        self.detail  = detail or self.__class__.detail
        self.context = context
        super().__init__(self.detail)


class NotFoundError(AppException):
    status_code = 404
    detail      = "Объект не найден"


class ValidationError(AppException):
    status_code = 422
    detail      = "Ошибка валидации данных"


class AuthError(AppException):
    status_code = 401
    detail      = "Требуется авторизация"


class AnalysisError(AppException):
    status_code = 500
    detail      = "Ошибка модуля анализа"


class GenerationError(AppException):
    status_code = 500
    detail      = "Ошибка генерации контента"


class DatabaseError(AppException):
    status_code = 500
    detail      = "Ошибка базы данных"


class InsufficientDataError(AnalysisError):
    """Недостаточно данных для анализа (мало студентов / нет логов)."""
    status_code = 400
    detail      = "Недостаточно данных для анализа"


class RegenerationSkippedError(AppException):
    """Регенерация не нужна — метрики выше порога."""
    status_code = 200
    detail      = "Регенерация не требуется"