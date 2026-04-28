"""
TopicRepository — хранилище тем курса.
"""

from typing import List, Optional
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.database import get_database
from src.core.models import TopicContent, TopicItem


class TopicRepository:

    def __init__(self):
        self.db: AsyncIOMotorDatabase = get_database()
        self.collection = self.db.topics

    async def save_topics(self, topics: TopicContent) -> str:
        """Сохраняет список тем. Возвращает id документа."""
        doc    = topics.model_dump(exclude_unset=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)

    async def get_topics_by_id(self, doc_id: str) -> Optional[TopicContent]:
        doc = await self.collection.find_one({"_id": ObjectId(doc_id)})
        return TopicContent(**doc) if doc else None

    async def get_topics_by_subject(self, subject_id: str) -> List[dict]:
        """Все темы предмета, сортированные по порядку."""
        cursor = self.collection.find(
            {"subject_id": subject_id}
        ).sort("order_index", 1)
        docs = [doc async for doc in cursor]
        for doc in docs:
            doc["_id"] = str(doc["_id"])
        return docs

    async def get_topic_by_id(self, topic_id: str) -> Optional[dict]:
        doc = await self.collection.find_one({"_id": ObjectId(topic_id)})
        if doc:
            doc["_id"] = str(doc["_id"])
        return doc

    async def delete_topic(self, topic_id: str) -> bool:
        result = await self.collection.delete_one({"_id": ObjectId(topic_id)})
        return result.deleted_count > 0