"""
Конфигурация логирования.
"""

import logging
import sys
from typing import Optional


def setup_logging(level: Optional[str] = None) -> None:
    """
    Настраивает единый формат логов для всего приложения.

    Уровень берётся из параметра или из переменной окружения LOG_LEVEL.
    По умолчанию: INFO.
    """
    import os
    log_level_str = level or os.getenv("LOG_LEVEL", "INFO").upper()
    log_level     = getattr(logging, log_level_str, logging.INFO)

    fmt = logging.Formatter(
        fmt   = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt = "%Y-%m-%d %H:%M:%S",
    )

    # Консоль
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(fmt)

    # Корневой логгер
    root = logging.getLogger()
    root.setLevel(log_level)

    # Не дублируем хэндлеры при повторном вызове
    if not root.handlers:
        root.addHandler(handler)

    # Приглушаем шумные библиотеки
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("motor").setLevel(logging.WARNING)
    logging.getLogger("pymongo").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        f"Логирование настроено | level={log_level_str}"
    )