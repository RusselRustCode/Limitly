from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from src.core.models import GeneratedArtifact
from src.core.database import get_database

class ArtifactRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.generated_artifacts
        
    async def save_artifact(self, artifact: GeneratedArtifact) -> Optional[str]:
        doc = artifact.model_dump(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_artifact_by_id(self, id: str) -> Optional[GeneratedArtifact]:
        ...
        
    async def get_artifact_by_teacher_id(self, teacher_id: str) -> Optional[GeneratedArtifact]:
        ...
        
    async def get_arifact_by_material_and_type(self, material_id: str, artifact_type: str) -> List[GeneratedArtifact]:
        ...