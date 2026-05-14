from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from src.core.models import ArtifactCreate, GeneratedArtifact
from src.core.database import get_database
from bson import ObjectId
from datetime import datetime, UTC



class ArtifactRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.generated_artifacts
        
    
    async def save_artifact(self, artifact: ArtifactCreate, created_by: str = None) -> str:
        """
        Сохраняет новую версию артефакта.
 
        id генерирует MongoDB, created_by приходит с бэка из JWT.
        """
        
        doc = artifact.model_dump(exclude_none=True)
        doc["created_by"] = created_by
        doc["create_at"] = datetime.now(UTC)
        
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    
    async def activate_version(self, artifact_id: str, term_id: str) -> bool:
        await self.collection.update_many(
            {"term_id": term_id, "is_active": True},
            {"$set": {"is_active": False}},
        )
        
        result = await self.collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_activate": True}},
        )
        
        return result.modified_count > 0
    
    async def deactivate_version(self, artifact_id: str) -> bool:
        result = await self.collection.update_one(
            {"_id": ObjectId(artifact_id)},
            {"$set": {"is_active": False}},
        )
        return result.modified_count > 0
    
    async def get_artifact_by_id(self, artifact_id: str) -> Optional[GeneratedArtifact]:
        doc = await self.collection.find_one({"_id": ObjectId(artifact_id)})
        return GeneratedArtifact(**doc) if doc else None
    
    async def get_activate_artifact(self, term_id: str, artifact_type: Optional[str] = None) -> Optional[GeneratedArtifact]:
        query: dict = {"term_id":term_id, "is_activate": True}
        if artifact_type:
            query["artifact_type"] = artifact_type
            
        doc = await self.collection.find_one(query, sort=[("version", -1)])
        return GeneratedArtifact(**doc) if doc else None
    
    
    async def get_artifact_by_material_and_type(self, 
        material_id: str, 
        artifact_type: str,
        active_only: bool = False
    ) -> List[GeneratedArtifact]:
        query: dict = {"term_id": material_id, "artifact_type": artifact_type}
        if active_only:
            query["is_active"] = True
        cursor = self.collection.find(query).sort("version", -1)
        docs   = [doc async for doc in cursor]
        return [GeneratedArtifact(**doc) for doc in docs]
 
    async def get_all_versions(self, term_id: str) -> List[GeneratedArtifact]:
        cursor = self.collection.find({"term_id": term_id}).sort("version", -1)
        docs   = [doc async for doc in cursor]
        return [GeneratedArtifact(**doc) for doc in docs]