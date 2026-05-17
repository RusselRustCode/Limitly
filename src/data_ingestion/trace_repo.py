"""
TraceRepository — хранилище цифрового следа студентов.
"""

import logging
from typing import List, Optional
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.database import get_database
from src.core.models import TraceLog
from src.core.exceptions import DatabaseError


def _safe_parse_log(doc: dict):
    """
    Безопасный парсинг документа из MongoDB в TraceLog.

    Обрабатывает:
    - Старые документы с другой схемой полей (timestamp vs timestamp)
    - Документы без обязательных полей (attempts, is_correct)
    - Разные форматы student_id (ObjectId, строка)
    """
    try:
        # Нормализуем поля — старые документы могут иметь другие имена
        if "timestamp" in doc and "timestamp" not in doc:
            doc["timestamp"] = doc.pop("timestamp")

        # Добавляем дефолты для обязательных полей если их нет
        doc.setdefault("attempts", 1)
        doc.setdefault("is_correct", False)
        doc.setdefault("time_spent_sec", 0)
        doc.setdefault("viewed_material_before", False)
        doc.setdefault("is_nav_back", False)
        doc.setdefault("first_exposure", True)

        return TraceLog(**doc)
    except Exception as e:
        logger.warning(f"[TraceRepository] пропускаем документ {doc.get('_id')}: {e}")
        return None


logger = logging.getLogger(__name__)


class TraceRepository:

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.trace_logs

    async def save_log(self, log: TraceLog) -> str:
        try:
            doc    = log.model_dump(by_alias=True, exclude_unset=True)
            result = await self.collection.insert_one(doc)
            return str(result.inserted_id)
        except Exception as e:
            logger.error(f"[TraceRepository] save_log error: {e}", exc_info=True)
            raise DatabaseError(f"Ошибка сохранения лога: {e}")

    async def save_logs_bulk(self, logs: List[TraceLog]) -> int:
        if not logs:
            return 0
        try:
            docs = []
            for log in logs:
                doc = log.model_dump(by_alias=True, exclude_none=True)
                # Гарантируем что timestamp — это datetime объект (не строка)
                if "timestamp" in doc and isinstance(doc["timestamp"], str):
                    from datetime import datetime
                    doc["timestamp"] = datetime.fromisoformat(doc["timestamp"])
                docs.append(doc)
            result = await self.collection.insert_many(docs)
            saved  = len(result.inserted_ids)
            logger.info(f"[TraceRepository] bulk save: {saved} logs")
            return saved
        except Exception as e:
            logger.error(f"[TraceRepository] save_logs_bulk error: {e}", exc_info=True)
            raise DatabaseError(f"Ошибка массового сохранения логов: {e}")

    async def get_logs_by_artifact(
        self,
        artifact_id: str,
        limit:       Optional[int] = None,
    ) -> List[TraceLog]:
        try:
            query  = {"artifact_id": ObjectId(artifact_id)}
            cursor = self.collection.find(query).sort("timestamp", -1)
            if limit:
                cursor = cursor.limit(limit)
            raw = [doc async for doc in cursor]
            return [log for doc in raw if (log := _safe_parse_log(doc)) is not None]
        except Exception as e:
            logger.error(f"[TraceRepository] get_logs_by_artifact error: {e}", exc_info=True)
            return []

    async def get_logs_by_student_and_artifact(
        self,
        student_id:  str,
        artifact_id: str,
    ) -> List[TraceLog]:
        try:
            query = {
                "student_id":  ObjectId(student_id),
                "artifact_id": ObjectId(artifact_id),
            }
            raw = [doc async for doc in self.collection.find(query)]
            return [log for doc in raw if (log := _safe_parse_log(doc)) is not None]
        except Exception as e:
            logger.error(f"[TraceRepository] get_logs_by_student_and_artifact error: {e}", exc_info=True)
            return []

    async def get_logs_by_student(
        self,
        student_id: str,
        limit:      Optional[int] = None,
    ) -> List[TraceLog]:
        try:
            # student_id может быть как ObjectId так и строкой ("student_050")
            # пробуем оба варианта
            try:
                sid_query = {"$in": [student_id, ObjectId(student_id)]}
            except Exception:
                sid_query = student_id
            cursor = self.collection.find(
                {"student_id": sid_query}
            ).sort("timestamp", -1)
            if limit:
                cursor = cursor.limit(limit)
            raw = [doc async for doc in cursor]
            return [_safe_parse_log(doc) for doc in raw if _safe_parse_log(doc) is not None]
        except Exception as e:
            logger.error(f"[TraceRepository] get_logs_by_student error: {e}", exc_info=True)
            return []

    async def count_unique_students(self, artifact_id: str) -> int:
        try:
            result = await self.collection.distinct(
                "student_id",
                {"artifact_id": ObjectId(artifact_id)},
            )
            return len(result)
        except Exception as e:
            logger.error(f"[TraceRepository] count_unique_students error: {e}", exc_info=True)
            return 0