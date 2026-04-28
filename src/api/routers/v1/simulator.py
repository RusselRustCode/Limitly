from typing import Optional
from fastapi import HTTPException, APIRouter, Depends
from pydantic import BaseModel, Field
from src.simulator.synthetic_cohort import SyntheticCohort, COHORT_PRESETS
from src.data_ingestion.trace_repo import TraceRepository
from src.analysis_service.analyse import AnalyseService
from src.analysis_service.analyse_repo import AnalyseRepository

simulator_router = APIRouter(prefix="/simulator", tags=["Simulator IRT 3PL"])

class SimulatorRequest(BaseModel):
    artifact_id:     str   = Field(..., description="ID артефакта для симуляции")
    n:               int   = Field(default=250, ge=10, le=2000, description="Количество студентов")
    content_quality: float = Field(default=0.6, ge=0.0, le=1.0, description="Качество контента [0–1]")
    cohort_type:     str   = Field(default="mixed", description="Тип когорты: strong | average | weak | mixed")
    error_bias:      str   = Field(default="balanced", description="Тип ошибок: conceptual | operational | procedural | balanced")
    seed:            int   = Field(default=42, description="Seed для воспроизводимости")
    
    
class EvolutionRequest(BaseModel):
    artifact_id:         str   = Field(..., description="ID стартового артефакта")
    iterations:          int   = Field(default=5, ge=1, le=20, description="Количество итераций")
    n_per_iteration:     int   = Field(default=100, ge=10, le=500)
    initial_quality:     float = Field(default=0.3, ge=0.0, le=1.0, description="Начальное качество контента")
    quality_improvement: float = Field(default=0.08, ge=0.0, le=0.3, description="Прирост качества за итерацию")
    cohort_type:         str   = Field(default="mixed")
    
    
def get_trace_repo() -> TraceRepository: return TraceRepository()
def get_analyse_repo() -> AnalyseRepository: return AnalyseRepository()

def get_analyse_service(trace_repo : TraceRepository = Depends(get_trace_repo), analyse_repo: AnalyseRepository =  Depends(get_analyse_repo)) -> AnalyseService:
    return AnalyseService(trace_repo=trace_repo, repo=analyse_repo)


@simulator_router.get("/presets", summary="Пресеты когорт студентов")
async def get_presets() -> dict:
    """Возвращает доступные пресеты когорт с описанием параметров."""
    return {
        "cohort_presets": {
            k: v["description"] for k, v in COHORT_PRESETS.items()
        },
        "error_bias_options": [
            "balanced", "conceptual", "operational", "procedural"
        ],
    }
    
@simulator_router.post("/run", summary="Запустить симуляцию -> сохранить логи")
async def run_simulation(
    req: SimulatorRequest,
    service: AnalyseService = Depends(get_analyse_service),
    repo: TraceRepository = Depends(get_trace_repo)
) -> dict:
    validate_cohort_type(req.cohort_type)
    
    cohort = SyntheticCohort(
        n=req.n,
        content_quality=req.content_quality,
        cohort_type=req.cohort_type,
        error_bias=req.error_bias,
        seed=req.seed,
    )
    
    logs = cohort.get_trace_logs(req.artifact_id)
    await repo.save_log_bulk(logs)
    
    result = await service.analyze_artifact(
        artifact_id=req.artifact_id,
        force=True,
    )
    
    if result is None:
        raise HTTPException(status_code=500, detail="Анализ не удался")
    
    return {
        "status":      "ok",
        "artifact_id": req.artifact_id,
        "simulation": {
            "n_students":      req.n,
            "content_quality": req.content_quality,
            "cohort_type":     req.cohort_type,
            "metrics_preview": cohort.compute_metrics(),
        },
        "analysis": {
            "efficiency_score":  result.efficiency_score,
            "efficiency_fresh":  result.efficiency_fresh,
            "average_mastery":   result.average_mastery,
            "top_error_patterns": [e for e in result.top_error_patterns],
            "directives": [
                {
                    "strategy":  d.strategy,
                    "priority":  d.priority,
                    "directive": d.directive_text,
                }
                for d in result.adaptation_directives
            ],
        },
    }
    
@simulator_router.post("/evolution", summary="Симуляция N итераций эволюции контента")
async def run_evolution(
    req:     EvolutionRequest,
    service: AnalyseService  = Depends(get_analyse_service),
    repo:    TraceRepository = Depends(get_trace_repo),
) -> dict:
    """
    Симулирует несколько итераций улучшения контента.
 
    На каждой итерации:
    1. Генерирует логи с текущим качеством
    2. Анализирует → получает метрики
    3. Увеличивает quality (имитируя регенерацию)
    4. Возвращает динамику метрик по итерациям
 
    Воспроизводит результаты из ВКР (раздел 8.2).
    """
    validate_cohort_type(req.cohort_type)
 
    history = []
    quality = req.initial_quality
 
    for i in range(req.iterations):
        cohort = SyntheticCohort(
            n=req.n_per_iteration,
            content_quality=quality,
            cohort_type=req.cohort_type,
            seed=req.seed + i,   # разный seed на каждой итерации
        )
 
        logs = cohort.get_trace_logs(req.artifact_id)
        await repo.save_logs_bulk(logs)
 
        result = await service.analyze_artifact(
            artifact_id=req.artifact_id,
            force=True,
        )
 
        metrics = cohort.compute_metrics()
        step = {
            "iteration":       i + 1,
            "content_quality": round(quality, 3),
            "M_term":          metrics["M_term"],
            "E_fresh":         result.efficiency_fresh if result else metrics["E_fresh"],
            "accuracy":        metrics["accuracy"],
            "max_D_p":         max(metrics["D_p"].values(), default=0.0),
            "directives_count": len(result.adaptation_directives) if result else 0,
        }
        history.append(step)
 
        # Качество растёт после каждой "регенерации"
        quality = min(1.0, quality + req.quality_improvement)
 
    # Итоговая статистика
    e_fresh_start = history[0]["E_fresh"]
    e_fresh_end   = history[-1]["E_fresh"]
    dp_start      = history[0]["max_D_p"]
    dp_end        = history[-1]["max_D_p"]
 
    return {
        "status":     "ok",
        "iterations": req.iterations,
        "history":    history,
        "summary": {
            "E_fresh_start":    e_fresh_start,
            "E_fresh_end":      e_fresh_end,
            "E_fresh_gain_pct": round((e_fresh_end - e_fresh_start) / max(e_fresh_start, 0.001) * 100, 1),
            "max_Dp_start":     dp_start,
            "max_Dp_end":       dp_end,
            "max_Dp_drop_pct":  round((dp_start - dp_end) / max(dp_start, 0.001) * 100, 1),
        },
    }
    

def validate_cohort_type(cohort_type: str):
    if cohort_type not in COHORT_PRESETS:
        raise HTTPException(
            status_code=400,
            detail=f"Неизвестный cohort_type '{cohort_type}'. Доступные: {list(COHORT_PRESETS.keys())}",
        )