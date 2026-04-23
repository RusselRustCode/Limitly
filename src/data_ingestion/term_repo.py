from motor.motor_asyncio import AsyncIOMotorDatabase
from typing import Optional, List
from src.core.database import get_database
from src.core.models import TermContent, TermItem
from bson import ObjectId


class TermRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.terms_and_materials
        
        
    async def save_terms(self, terms: TermContent) -> str:
        doc = terms.model_dump(exclude_none=True, by_alias=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def get_terms_by_id(self, doc_id: str) -> Optional[TermContent]:
        doc = await self.collection.find_one({"_id": ObjectId(doc_id)})
        return TermContent(**doc) if doc else None
    
    async def get_terms_by_topic(self, topic_id: str) -> List[dict]:
        cursor = await self.collection.find({"topic_id": topic_id})
        docs = [doc async for doc in cursor]
        
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs
    async def term_exists(self, topic_id: str, term_name: str) -> bool:
        count = await self.collection.count_documents({
            "topic_id":  topic_id,
            "term_name": term_name,
        })
        return count > 0
 
    async def delete_terms_by_topic(self, topic_id: str) -> int:
        result = await self.collection.delete_many({"topic_id": topic_id})
        return result.deleted_count