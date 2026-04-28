from typing import List
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId


from src.core.models import TraceLog
from src.data_ingestion.trace_repo import TraceRepository


trace_router = APIRouter(prefix="/trace", tags=["Trace (Digital Footprint)"])

def get_trace_repo() -> TraceRepository:
    return TraceRepository()

# @trace_router.post("/log", status_code=201, summary="Сохранить лог взаимодействия")
# async def save_log():
#     pass

@trace_router.get("/artifact/{artifact_id}", summary="Логи по артефакту")
async def get_logs_by_artifact(
    artifact_id: str,
    limit: int = 500,
    repo: TraceRepository = Depends(get_trace_repo)
) -> dict:
    try:
        ObjectId(artifact_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")
    
    logs = await repo.get_logs_by_artifact(artifact_id=artifact_id, limit=limit)
    return {"count": len(logs), "logs": [log.model_dump() for log in logs]}

@trace_router.get("/student/{student_id}", summary="Логи по студенту")
async def get_logs_by_student_id(
    student_id: str,
    repo: TraceRepository = Depends(get_trace_repo)
):
    try:
        ObjectId(student_id)
    except Exception as e:
        raise HTTPException(status_code=400, detail="Некорректный student_id")
    student_logs = await repo.get_log_by_student_id(student_id=student_id)
    return {"count": len(student_logs), "logs": [log.model_dump() for log in student_logs]}

