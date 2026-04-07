"""
API роутер для модуля анализа цифрового следа студента.

Эндпоинты:
- POST /analysis/artifact/{artifact_id}/analyze - Запуск анализа артефакта
- GET /analysis/artifact/{artifact_id} - Получение результата анализа
- GET /analysis/artifact/{artifact_id}/plan - Получение плана адаптации
- GET /analysis/artifacts/low-efficiency - Артефакты с низкой эффективностью
- POST /analysis/trigger/check - Проверка триггеров анализа
- GET /analysis/statistics - Статистика по анализам
"""

from fastapi import APIRouter, Query, HTTPException, Depends, Body
from typing import List, Optional, Dict
from datetime import datetime
from bson import ObjectId

from src.core.models import (
    MlAnalysisResult,
    AnalysisTrigger,
    GeneratedArtifact,
)
from src.analysis_service import AnalysisService, AnalyseRepository
from src.data_ingestion.trace_repo import TraceRepository


analysis_router = APIRouter(prefix="/analysis", tags=["Analysis Module"])


# ==================== DEPENDENCIES ====================

def get_trace_repo() -> TraceRepository:
    """Зависимость для получения TraceRepository"""
    return TraceRepository()


def get_analysis_repo() -> AnalyseRepository:
    """Зависимость для получения AnalyseRepository"""
    return AnalyseRepository()


def get_analysis_service(
    trace_repo: TraceRepository = Depends(get_trace_repo),
    analysis_repo: AnalyseRepository = Depends(get_analysis_repo)
) -> AnalysisService:
    """Зависимость для получения AnalysisService"""
    return AnalysisService(
        trace_repo=trace_repo,
        repo=analysis_repo
    )


# ==================== ANALYSIS ENDPOINTS ====================

@analysis_router.post("/artifact/{artifact_id}/analyze")
async def analyze_artifact(
    artifact_id: str,
    force: bool = Query(False, description="Принудительный запуск анализа"),
    bloom_weight: float = Query(1.0, ge=1.0, le=3.0, description="Вес Блума для артефакта"),
    service: AnalysisService = Depends(get_analysis_service)
) -> Dict:
    """
    Запуск анализа цифрового следа для артефакта.
    
    Расчёт метрик:
    - M_j: Индивидуальное освоение вопроса
    - M_term: Агрегированное освоение термина
    - E: Эффективность контента
    - D_p: Индекс деструктивности дистрактора
    
    Генерация адаптивных директив для LLM.
    """
    try:
        # Валидация artifact_id
        try:
            ObjectId(artifact_id)
        except Exception:
            raise HTTPException(status_code=400, detail="Некорректный artifact_id")
        
        result = await service.analyze_artifact(
            artifact_id=artifact_id,
            bloom_weight=bloom_weight,
            force=force
        )
        
        if result is None:
            raise HTTPException(
                status_code=400, 
                detail="Анализ не требуется (не достигнут порог триггера). Используйте force=true для принудительного запуска."
            )
        
        return {
            "status": "success",
            "analysis": result.model_dump(mode="json"),
            "message": f"Анализ завершён. Эффективность: {result.efficiency_score:.3f}, Освоение: {result.average_mastery:.3f}"
        }
    
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка анализа: {str(e)}")


@analysis_router.get("/artifact/{artifact_id}")
async def get_analysis_result(
    artifact_id: str,
    service: AnalysisService = Depends(get_analysis_service)
) -> Dict:
    """
    Получение последнего результата анализа для артефакта.
    """
    try:
        ObjectId(artifact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")
    
    result = await service.get_analysis_for_artifact(artifact_id)
    
    if result is None:
        raise HTTPException(status_code=404, detail="Анализ для данного артефакта не найден")
    
    return {
        "status": "success",
        "analysis": result.model_dump(mode="json")
    }


@analysis_router.get("/artifact/{artifact_id}/plan")
async def get_adaptation_plan(
    artifact_id: str,
    force_analysis: bool = Query(False, description="Принудительный запуск анализа перед генерацией плана"),
    service: AnalysisService = Depends(get_analysis_service)
) -> Dict:
    """
    Генерация плана адаптации контента для LLM.
    
    Возвращает:
    - План адаптации с директивами
    - Системный промпт для LLM
    - Контекст для перегенерации
    """
    try:
        ObjectId(artifact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")
    
    plan = await service.generate_adaptation_plan(
        artifact_id=artifact_id,
        force_analysis=force_analysis
    )
    
    if plan is None:
        raise HTTPException(
            status_code=400, 
            detail="Не удалось сгенерировать план. Возможно, отсутствует анализ или цифровой след."
        )
    
    return {
        "status": "success",
        "plan": plan
    }


@analysis_router.get("/artifacts/low-efficiency")
async def get_low_efficiency_artifacts(
    threshold: float = Query(0.5, ge=0.0, le=1.0, description="Порог эффективности"),
    repo: AnalyseRepository = Depends(get_analysis_repo)
) -> Dict:
    """
    Получение списка артефактов, требующих перегенерации.
    
    Артефакты с эффективностью E < threshold.
    """
    try:
        artifacts = await repo.get_artifacts_needing_regeneration(threshold)
        
        return {
            "status": "success",
            "count": len(artifacts),
            "threshold": threshold,
            "artifacts": artifacts
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения списка: {str(e)}")


@analysis_router.post("/trigger/check")
async def check_analysis_trigger(
    artifact_id: str = Body(..., embed=True, description="ID артефакта для проверки"),
    service: AnalysisService = Depends(get_analysis_service)
) -> Dict:
    """
    Проверка необходимости запуска анализа для артефакта.
    
    Триггеры:
    - N_THRESHOLD: Накопление N уникальных студентов
    - CRITICAL_EFFICIENCY: Падение эффективности ниже критического уровня
    - EXPERT_REQUEST: Принудительный запрос преподавателя
    """
    try:
        ObjectId(artifact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")
    
    should_analyze, trigger = await service.check_analysis_trigger(artifact_id)
    
    return {
        "status": "success",
        "artifact_id": artifact_id,
        "should_analyze": should_analyze,
        "trigger": trigger.value if trigger else None,
        "message": "Анализ требуется" if should_analyze else "Анализ не требуется"
    }


@analysis_router.get("/statistics")
async def get_analysis_statistics(
    start_date: Optional[datetime] = Query(None, description="Начало периода"),
    end_date: Optional[datetime] = Query(None, description="Конец периода"),
    repo: AnalyseRepository = Depends(get_analysis_repo)
) -> Dict:
    """
    Получение статистики по анализам.
    
    Возвращает:
    - Общее количество анализов
    - Средняя эффективность
    - Средний уровень освоения
    - Распределение по триггерам
    """
    try:
        stats = await repo.get_analysis_statistics(start_date, end_date)
        
        return {
            "status": "success",
            "statistics": stats,
            "period": {
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None
            }
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения статистики: {str(e)}")


@analysis_router.get("/history/{artifact_id}")
async def get_analysis_history(
    artifact_id: str,
    limit: int = Query(10, ge=1, le=100, description="Максимальное количество записей"),
    repo: AnalyseRepository = Depends(get_analysis_repo)
) -> Dict:
    """
    Получение истории анализа для артефакта (все версии).
    """
    try:
        ObjectId(artifact_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Некорректный artifact_id")
    
    history = await repo.get_analysis_history_for_artifact(artifact_id, limit)
    
    return {
        "status": "success",
        "count": len(history),
        "history": [h.model_dump(mode="json") for h in history]
    }


@analysis_router.get("/trigger/{trigger_type}")
async def get_analysis_by_trigger(
    trigger_type: str,
    repo: AnalyseRepository = Depends(get_analysis_repo)
) -> Dict:
    """
    Получение результатов анализа по типу триггера.
    
    Доступные триггеры:
    - n_threshold: Накопление N студентов
    - critical_efficiency: Критическое падение эффективности
    - expert_request: Запрос эксперта
    """
    try:
        trigger = AnalysisTrigger(trigger_type)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Некорректный тип триггера. Доступные: {[t.value for t in AnalysisTrigger]}"
        )
    
    results = await repo.get_analysis_by_trigger(trigger)
    
    return {
        "status": "success",
        "trigger": trigger.value,
        "count": len(results),
        "results": [r.model_dump(mode="json") for r in results]
    }


@analysis_router.get("/low-mastery")
async def get_low_mastery_analyses(
    threshold: float = Query(0.6, ge=0.0, le=1.0, description="Порог освоения"),
    repo: AnalyseRepository = Depends(get_analysis_repo)
) -> Dict:
    """
    Получение анализов с низким уровнем освоения.
    """
    try:
        all_analyses = await repo.get_all_analysis_results(limit=100)
        low_mastery = [
            a for a in all_analyses 
            if a.average_mastery < threshold
        ]
        
        return {
            "status": "success",
            "threshold": threshold,
            "count": len(low_mastery),
            "analyses": [a.model_dump(mode="json") for a in low_mastery]
        }
    
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка получения анализов: {str(e)}")
