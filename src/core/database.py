"""
Подключение к MongoDB.

Поддерживает:
  - Локальную БД:  mongodb://localhost:27017
  - MongoDB Atlas: mongodb+srv://user:pass@cluster.mongodb.net/?appName=App
"""

import logging
from typing import Optional

from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
from config.settings import settings

logger = logging.getLogger(__name__)


class DataBase:
    client: Optional[AsyncIOMotorClient] = None
    db:     Optional[AsyncIOMotorDatabase] = None


def connect_to_mongo() -> None:
    """
    Инициализирует подключение к MongoDB.
    Для Atlas автоматически добавляет нужные TLS-параметры.
    """
    url = settings.MONGODB_URL_ATLAS

    # Atlas требует TLS — motor обрабатывает это через строку подключения,
    # но явно передаём serverSelectionTimeoutMS чтобы быстро падать при недоступности
    is_atlas = "mongodb+srv" in url

    DataBase.client = AsyncIOMotorClient(
        url,
        serverSelectionTimeoutMS=5000,  # 5 сек таймаут на коннект
        connectTimeoutMS=10000,
        socketTimeoutMS=30000,
    )
    DataBase.db = DataBase.client[settings.MONGODB_NAME]

    mode = "Atlas (облако)" if is_atlas else "локальная"
    logger.info(f"[DB] Подключено к MongoDB {mode} | db={settings.MONGODB_NAME}")


def close_mongo_db() -> None:
    if DataBase.client:
        DataBase.client.close()
        logger.info("[DB] Соединение с MongoDB закрыто")


def get_database() -> AsyncIOMotorDatabase:
    if DataBase.db is None:
        raise ConnectionError(
            "База данных не инициализирована. "
            "Убедитесь что connect_to_mongo() вызван при старте приложения."
        )
    return DataBase.db