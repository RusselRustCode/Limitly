from typing import List, Optional
from bson import ObjectId

from motor.motor_asyncio import AsyncIOMotorDatabase
from src.core.database import get_database
from src.core.models import TraceLog

class TraceRepository:
    
    def __init__(self):
        self.db : AsyncIOMotorDatabase = get_database()
        self.collection = self.db.student_trace_logs
        
    async def save_log(self, log: TraceLog) -> str:
        doc = log.model_dump(by_alias=True, exclude_unset=True)
        result = await self.collection.insert_one(doc)
        return str(result.inserted_id)
    
    async def save_log_bulk(self, logs: List[TraceLog]) -> int:
        if not logs:
            return 0
        docs = [log.model_dump(by_alias=True, exclude_unset=True) for log in logs]
        result = await self.collection.insert_many(docs)
        return len(result.inserted_ids)
    
    
    async def get_logs_by_artifact(self, artifact_id: str, limit: Optional[int] = None) -> List[TraceLog]:
        try:
            query = {"artifact_id": ObjectId(artifact_id)}
            cursor = self.collection.find(query).sort("timestamped", -1)
            if limit:
                cursor = cursor.limit(limit=limit)
            raw = [doc async for doc in cursor]
            return [TraceLog(**doc) for doc in raw]
        except Exception as e:
            print(f"[TraceRepository] get_logs_by_artifact error: {e}")
            return []
    
    async def get_logs_by_student_and_artifact(self, artifact_id: str, student_id: str) -> List[TraceLog]:
        try:
            query = {
                "student_id":  ObjectId(student_id),
                "artifact_id": ObjectId(artifact_id),
            }
            raw = [doc async for doc in self.collection.find(query)]
            return [TraceLog(**doc) for doc in raw]
        except Exception as e:
            print(f"[TraceRepository] get_logs_by_student_and_artifact error: {e}")
            return []
    
    
    async def get_logs_by_student(self, student_id: str, limit: Optional[int] = None) -> List[TraceLog]:
        try:
            cursor = self.collection.find(
                {"student_id": ObjectId(student_id)}
            ).sort("timestamped", -1)
            if limit:
                cursor = cursor.limit(limit)
            raw = [doc async for doc in cursor]
            return [TraceLog(**doc) for doc in raw]
        except Exception as e:
            print(f"[TraceRepository] get_logs_by_student error: {e}")
            return []
    
    async def count_unique_students(self, artifact_id: str) -> int:
        pass