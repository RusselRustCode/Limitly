from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.models import TopicContent, TopicItem
from src.core.database import get_database
from typing import Optional, List
from bson import ObjectId



class TopicRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.topics
        
    async def save_topic(self, topics: TopicContent) -> str:
        doc = topics.model_dump(exclude_none=None)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    
    async def get_topics_by_id(self, doc_id: str) -> Optional[TopicContent]:
        result = await self.collection.find_one({"_id": ObjectId(doc_id)})
        return TopicContent(**result) if result else None
    
    async def get_topics_by_subject(self, subject: str) -> List[dict]:
        cursor = self.collection.find({
            "subject_id": subject
        }).sort("order_index", 1)   
        docs = [doc async for doc in cursor]
        if docs:
            docs["_id"] = str(docs["_id"])
        return docs
    
    async def get_topic_by_id(self, topic_id: str) -> Optional[dict]:
        doc = await self.collection.find_one({"_id": ObjectId(topic_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc
 
    async def delete_topic(self, topic_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(topic_id)})
        return result.deleted_count > 0