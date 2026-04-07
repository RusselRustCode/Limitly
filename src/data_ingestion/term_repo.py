from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional
from src.core.database import get_database
from src.core.models import TermContent
from bson import ObjectId
class TermRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.terms_and_materials
        
    async def save_terms(self, terms: TermContent) -> Optional[str]:
        doc = terms.model_dump(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_terms_by_id(self, id: str) -> Optional[TermContent]:
        ...
    
    async def get_terms_by_teacher_id(self, teacher_id: str) -> Optional[TermContent]:
        ...
        
    async def get_terms_by_topic(self, topic_id: str) -> Optional[TermContent]:
        ...
        
    async def term_exists(self, topic_id: str, term_name: str) -> bool:
        count = await self.collection.count_documents({
            "topic_id": ObjectId(topic_id),
            "term_name": term_name
        })
        return count > 0
        
    #.....