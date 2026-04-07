from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.models import TopicContent
from src.core.database import get_database
from typing import Optional
class TopicRepository:
    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.topics
        
    async def save_topics(self, topic: TopicContent) -> str:
        doc = topic.model_dump(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
        
    async def get_topics_by_id(self, id) -> Optional[TopicContent]:
        cursor = self.collection.find({"_id": id})
        return TopicContent(**cursor)