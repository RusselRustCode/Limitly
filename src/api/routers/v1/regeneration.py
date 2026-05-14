"""
Regeneration Router — полный цикл улучшения контента.
 
Цикл:
  1. Берём активный артефакт по term_id
  2. Анализируем цифровой след (MetricsCalculator)
  3. Agent-Planner формирует директивы (мнимый градиент)
  4. Agent-Executor регенерирует контент с учётом директив
  5. Сохраняем новую версию, деактивируем старую
 
Эндпоинты:
  POST /regen/{artifact_id}         — регенерировать один артефакт
  POST /regen/term/{term_id}/full   — полный цикл по термину (все типы контента)
  GET  /regen/{artifact_id}/plan    — только посмотреть план (без регенерации)
"""

from typing import Optional
from fastapi import APIRouter, Depends, Query, Request, HTTPException
from pydantic import BaseModel, Field

from src.core.models import ArtifactCreate
from src.data_ingestion.artifacts_repo import ArtifactRepository
from src.data_ingestion.trace_repo import TraceRepository
from src.analysis_service.analyse import AnalyseService
from src.analysis_service.analyse_repo import AnalyseRepository
from src.llm.external_api_models import generate_adaptive_content
from src.llm.client import LLMModel

regen_router = APIRouter(prefix="/regen", tags=["Full cycle"])

class RegenRequest(BaseModel):
    profile_id:  str            = Field(default="engineer")
    model:       Optional[str]  = Field(default=None, description="LLM модель (None=авто)")
    force:       bool           = Field(default=False, description="Регенерировать даже если метрики OK")
    dry_run:     bool           = Field(default=False, description="Только план, без реальной регенерации")
    
def get_trace_repo()    -> TraceRepository:    return TraceRepository()
def get_analyse_repo()  -> AnalyseRepository:  return AnalyseRepository()
def get_artifact_repo() -> ArtifactRepository: return ArtifactRepository()
 
def get_analysis_service(
    trace_repo:   TraceRepository   = Depends(get_trace_repo),
    analyse_repo: AnalyseRepository = Depends(get_analyse_repo),
) -> AnalyseService:
    return AnalyseService(trace_repo=trace_repo, repo=analyse_repo)

@regen_router.get("/{artifact_id}/plan", summary="План адаптации (без регенерации)")
async def get_plan(
    artifact_id: str,
    force:       bool = Query(False),
    service:     AnalyseService = Depends(get_analysis_service),
) -> dict:
    """
    Возвращает план адаптации — какие директивы выдаст Agent-Planner.
    Регенерацию НЕ запускает.
    """
    plan = await service.generate_adaptation_plan(
        artifact_id=artifact_id,
        force_analysis=force,
    )
    if plan is None:
        raise HTTPException(
            status_code=404,
            detail="Нет данных для анализа. Сначала накопите цифровой след или используйте симулятор."
        )
    return {"status": "ok", "plan": plan}

@regen_router.post("/{artifact_id}", summary="Регенерировать артефакт")
async def regenerate_artifact(
    artifact_id:   str,
    req:           RegenRequest,
    request:       Request,
    artifact_repo: ArtifactRepository = Depends(get_artifact_repo),
    service:       AnalyseService     = Depends(get_analysis_service),
) -> dict:
    """
    Полный цикл регенерации одного артефакта:
 
    1. Загружаем текущий артефакт из БД
    2. Анализируем цифровой след → получаем метрики
    3. Agent-Planner → директивы (мнимый градиент)
    4. Если dry_run=True — возвращаем только план
    5. Agent-Executor (LLM) → новая версия контента
    6. Сохраняем новый артефакт, деактивируем старый
    """
    # --- 1. Загружаем артефакт ---
    artifact = await artifact_repo.get_artifact_by_id(artifact_id)
    if artifact is None:
        raise HTTPException(status_code=404, detail=f"Артефакт {artifact_id} не найден")
 
    # --- 2. Анализ + план ---
    plan = await service.generate_adaptation_plan(
        artifact_id=artifact_id,
        force_analysis=req.force,
    )
    if plan is None:
        raise HTTPException(
            status_code=400,
            detail="Нет данных для анализа. Накопите цифровой след или используйте /simulator/run."
        )
 
    # Если метрики OK и force=False — не регенерируем
    if not req.force and plan["efficiency_fresh"] >= 0.55:
        return {
            "status":  "skipped",
            "reason":  f"E_fresh={plan['efficiency_fresh']:.3f} выше порога 0.55, регенерация не нужна.",
            "plan":    plan,
        }
 
    # --- 3. Dry run — только план ---
    if req.dry_run:
        return {"status": "dry_run", "plan": plan}
 
    # --- 4. Регенерация через LLM ---
    directives       = plan.get("adaptation_directives", [])
    old_content_text = _extract_text(artifact.content)
    new_version      = _bump_version(artifact.version)
    params           = _build_params(artifact)
 
    # Выбираем модель
    llm_model = None
    if req.model:
        try:
            llm_model = LLMModel(req.model)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Неизвестная модель: {req.model}")
 
    generated = await generate_adaptive_content(
        params=params,
        version_to=int(new_version.split(".")[0]),
        old_content=old_content_text,
        imaginary_gradient=directives,
        profile_id=req.profile_id,
        model=llm_model,
    )
 
    # --- 5. Сохраняем новую версию ---
    teacher_id = getattr(request.state, "uid", "system")
 
    new_artifact = ArtifactCreate(
        term_id       = artifact.term_id,
        artifact_type = artifact.artifact_type,
        version       = new_version,
        is_active     = True,
        bloom_weight  = artifact.bloom_weight,
        profile_id    = req.profile_id,
        content       = generated.content,
        imaginary_gradient = directives,
        params_used   = artifact.params_used,
    )
 
    new_id = await artifact_repo.save_artifact(new_artifact, created_by=teacher_id)
 
    # Деактивируем старую версию
    await artifact_repo.deactivate_version(artifact_id)
 
    return {
        "status":      "regenerated",
        "old_artifact_id": artifact_id,
        "new_artifact_id": new_id,
        "new_version":     new_version,
        "plan":            plan,
        "reasoning":       generated.reasoning,
    }
    
@regen_router.post("/term/{term_id}/full", summary="Полный цикл по термину")
async def regenerate_term_full(
    term_id:       str,
    req:           RegenRequest,
    request:       Request,
    artifact_repo: ArtifactRepository = Depends(get_artifact_repo),
    service:       AnalyseService     = Depends(get_analysis_service),
) -> dict:
    """
    Регенерирует ВСЕ активные артефакты термина (explanation, test_question, problem_case).
    """
    results = {}
    for artifact_type in ["explanation", "test_question", "problem_case"]:
        artifact = await artifact_repo.get_active_artifact(term_id, artifact_type)
        if artifact is None:
            results[artifact_type] = {"status": "not_found"}
            continue
 
        # Рекурсивно вызываем логику одного артефакта
        plan = await service.generate_adaptation_plan(
            artifact_id=str(artifact.id),
            force_analysis=req.force,
        )
        if plan is None:
            results[artifact_type] = {"status": "no_data"}
            continue
 
        if not req.force and plan["efficiency_fresh"] >= 0.55:
            results[artifact_type] = {
                "status":       "skipped",
                "efficiency_fresh": plan["efficiency_fresh"],
            }
            continue
 
        if req.dry_run:
            results[artifact_type] = {"status": "dry_run", "plan": plan}
            continue
 
        # Регенерация
        old_content_text = _extract_text(artifact.content)
        new_version      = _bump_version(artifact.version)
        params           = _build_params(artifact)
        teacher_id       = getattr(request.state, "uid", "system")
 
        llm_model = None
        if req.model:
            try:
                llm_model = LLMModel(req.model)
            except ValueError:
                pass
 
        generated = await generate_adaptive_content(
            params=params,
            version_to=int(new_version.split(".")[0]),
            old_content=old_content_text,
            imaginary_gradient=plan.get("adaptation_directives", []),
            profile_id=req.profile_id,
            model=llm_model,
        )
 
        new_artifact = ArtifactCreate(
            term_id            = artifact.term_id,
            artifact_type      = artifact_type,
            version            = new_version,
            is_active          = True,
            bloom_weight       = artifact.bloom_weight,
            profile_id         = req.profile_id,
            content            = generated.content,
            imaginary_gradient = plan.get("adaptation_directives", []),
        )
 
        new_id = await artifact_repo.save_artifact(new_artifact, created_by=teacher_id)
        await artifact_repo.deactivate_version(str(artifact.id))
 
        results[artifact_type] = {
            "status":          "regenerated",
            "old_artifact_id": str(artifact.id),
            "new_artifact_id": new_id,
            "new_version":     new_version,
        }
 
    return {"status": "ok", "term_id": term_id, "results": results}

def _extract_text(content) -> str:
    """Извлекает текстовое содержимое из любого типа контента."""
    if hasattr(content, "explanation_body"):
        return content.explanation_body
    if hasattr(content, "problem_scenario"):
        return content.problem_scenario
    if hasattr(content, "question_body"):
        return content.question_body
    return str(content.model_dump())
 
 
def _bump_version(version: str) -> str:
    """1.0 → 2.0, 2.0 → 3.0 и т.д."""
    try:
        major = int(version.split(".")[0])
        return f"{major + 1}.0"
    except (ValueError, IndexError):
        return "2.0"
 
 
def _build_params(artifact):
    """Восстанавливает параметры генерации из сохранённого артефакта."""
    from src.core.models import ContentParams, TestParams, ProblemParams
 
    if artifact.params_used is not None:
        return artifact.params_used
 
    # Fallback — минимальный ContentParams
    term_id = getattr(artifact, "term_id", "unknown")
    return ContentParams(
        term_name="unknown",
        subject_specialization="математика",
        profile_id=getattr(artifact, "profile_id", "engineer") or "engineer",
    )