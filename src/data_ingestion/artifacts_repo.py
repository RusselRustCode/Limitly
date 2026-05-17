"""
ArtifactRepository — хранилище версионированных учебных артефактов.
"""

from datetime import datetime
from typing import List, Optional
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.database import get_database
from src.core.models import ArtifactCreate, GeneratedArtifact



def _safe_parse_artifact(doc: dict):
    """Безопасный парсинг артефакта — устанавливает дефолты для старых документов."""
    if not doc:
        return None
    try:
        # Дефолты для старых документов
        doc.setdefault("created_by", None)
        doc.setdefault("version", "1.0")
        doc.setdefault("is_active", True)
        doc.setdefault("bloom_weight", 1.0)
        return GeneratedArtifact(**doc)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(
            f"[ArtifactRepository] пропускаем документ {doc.get('_id')}: {e}"
        )
        return None


class ArtifactRepository:

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.generated_artifacts

    # ==================== ЗАПИСЬ ====================

    async def save_artifact(
        self,
        artifact:   ArtifactCreate,
        created_by: str,
    ) -> str:
        """
        Сохраняет новую версию артефакта.

        id генерирует MongoDB, created_by приходит с бэка из JWT.
        """
        doc = artifact.model_dump(exclude_none=True)
        doc["created_by"] = created_by
        doc["created_at"] = datetime.utcnow()

        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def activate_version(self, artifact_id: str, term_id: str) -> bool:
        """Деактивирует все предыдущие версии и активирует указанную."""
        await self.collection.update_many(
            {"term_id": term_id, "is_active": True},
            {"$set": {"is_active": False}},
        )
        result = await self.collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_active": True}},
        )
        return result.modified_count > 0

    async def deactivate_version(self, artifact_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_active": False}},
        )
        return result.modified_count > 0

    # ==================== ЧТЕНИЕ ====================

    async def get_artifact_by_id(self, artifact_id: str) -> Optional[GeneratedArtifact]:
        try:
            doc = await self.collection.find_one({"_id": ObjectId(artifact_id)})
        except Exception:
            doc = await self.collection.find_one({"_id": artifact_id})
        return _safe_parse_artifact(doc) if doc else None

    async def get_active_artifact(
        self,
        term_id:       str,
        artifact_type: Optional[str] = None,
    ) -> Optional[GeneratedArtifact]:
        query: dict = {"term_id": term_id, "is_active": True}
        if artifact_type:
            query["artifact_type"] = artifact_type
        doc = await self.collection.find_one(query, sort=[("version", -1)])
        return _safe_parse_artifact(doc) if doc else None

    async def get_artifact_by_material_and_type(
        self,
        material_id:   str,
        artifact_type: str,
        active_only:   bool = False,
    ) -> List[GeneratedArtifact]:
        query: dict = {"term_id": material_id, "artifact_type": artifact_type}
        if active_only:
            query["is_active"] = True
        cursor = self.collection.find(query).sort("version", -1)
        docs   = [doc async for doc in cursor]
        return [a for doc in docs if (a := _safe_parse_artifact(doc)) is not None]

    async def get_all_versions(self, term_id: str) -> List[GeneratedArtifact]:
        cursor = self.collection.find({"term_id": term_id}).sort("version", -1)
        docs   = [doc async for doc in cursor]
        return [a for doc in docs if (a := _safe_parse_artifact(doc)) is not None]