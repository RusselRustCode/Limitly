"""
Trace Router — приём цифрового следа от Telegram-бота и веб-интерфейса.

Эндпоинты:
  POST /trace/log       — сохранить один лог
  POST /trace/logs/bulk — массовое сохранение логов
  GET  /trace/artifact/{id} — логи по артефакту
  GET  /trace/student/{id}  — логи по студенту
"""

from typing import List
from fastapi import APIRouter, HTTPException, Depends
from bson import ObjectId

from src.core.models import TraceLog
from src.data_ingestion.trace_repo import TraceRepository

trace_router = APIRouter(prefix="/trace", tags=["Trace (Digital Footprint)"])


def get_trace_repo() -> TraceRepository:
    return TraceRepository()


@trace_router.post("/log", status_code=201, summary="Сохранить лог взаимодействия")
async def save_log(
    log:  TraceLog,
    repo: TraceRepository = Depends(get_trace_repo),
) -> dict:
    """Принимает один TraceLog от Telegram-бота или фронтенда."""
    log_id = await repo.save_log(log)
    return {"log_id": log_id, "status": "saved"}


@trace_router.post("/logs/bulk", status_code=201, summary="Массовое сохранение логов")
async def save_logs_bulk(
    logs: List[TraceLog],
    repo: TraceRepository = Depends(get_trace_repo),
) -> dict:
    """Принимает пакет логов — удобно для синхронизации с ботом."""
    if not logs:
        raise HTTPException(status_code=400, detail="Пустой список логов")
    count = await repo.save_logs_bulk(logs)
    return {"saved": count, "status": "ok"}


@trace_router.get("/artifact/{artifact_id}", summary="Логи по артефакту")
async def get_logs_by_artifact(
    artifact_id: str,
    limit:       int  = 500,
    repo: TraceRepository = Depends(get_trace_repo),
) -> dict:
    try:
        ObjectId(artifact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")

    logs = await repo.get_logs_by_artifact(artifact_id, limit=limit)
    return {"count": len(logs), "logs": [log.model_dump() for log in logs]}


@trace_router.get("/student/{student_id}", summary="Логи по студенту")
async def get_logs_by_student(
    student_id: str,
    limit:      int = 200,
    repo: TraceRepository = Depends(get_trace_repo),
) -> dict:
    """
    Принимает любой формат student_id:
    - ObjectId: "507f1f77bcf86cd799439011"
    - Строка:   "student_050", "user_abc" и т.д.
    """
    if not student_id or not student_id.strip():
        raise HTTPException(status_code=400, detail="student_id не может быть пустым")

    logs = await repo.get_logs_by_student(student_id.strip(), limit=limit)
    return {"count": len(logs), "logs": [log.model_dump() for log in logs]}