"""
LLM Router — генерация и сохранение учебного контента.
"""

import logging
from typing import Optional, List, Annotated
from fastapi import APIRouter, HTTPException, Depends, Query, Request, Body

from src.api.schemas import (
    GenerateRequest,
    ContentRequest, TestRequest, ProblemRequest, TopicsRequest, TermsRequest,
)
from src.llm.external_api_models import generate_adaptive_content
from src.llm.client import LLMModel, ModelPreset
from src.core.models import (
    TopicContent, TermContent,
    ArtifactCreate, LLMGeneratedContent,
)
from src.core.exceptions import ValidationError
from src.data_ingestion.topic_repo import TopicRepository
from src.data_ingestion.term_repo import TermRepository
from src.data_ingestion.artifacts_repo import ArtifactRepository

logger = logging.getLogger(__name__)

llm_router = APIRouter(prefix="/llm", tags=["LLM"])


# ==================== ГЕНЕРАЦИЯ ====================

@llm_router.post(
    "/generate",
    response_model = LLMGeneratedContent,
    summary        = "Генерация учебного контента",
    description    = """
Генерирует учебный материал нужного типа.

**Тип контента задаётся полем `content_type` в теле запроса:**

| content_type  | Что генерирует         | Обязательные поля                        |
|---------------|------------------------|------------------------------------------|
| `explanation` | Объяснение термина     | `term_name`, `subject_specialization`    |
| `test`        | Тестовый вопрос        | `term_name`, `question_format`, ...      |
| `problem`     | Практическая задача    | `term_name`, `subject_specialization`    |
| `topics`      | Список тем курса       | `subject_name`, `number_of_topics`       |
| `terms`       | Список терминов темы   | `topic_title`, `number_of_terms`         |
""",
)
async def generate_content(
    params:             Annotated[GenerateRequest, Body(discriminator="content_type")],
    version_to:         int              = Query(1,          description="Версия (1=первичная, >1=адаптация)"),
    old_content:        str              = Query("",         description="Предыдущий текст для адаптации"),
    imaginary_gradient: Optional[List[dict]] = None,
    related_terms:      Optional[List[str]]  = None,
    profile_id:         str              = Query("engineer", description="Профиль: engineer | theorist | lighthouse"),
    prompt_mode:        Optional[str]    = Query(None,       description="Режим промпта: full | min | None=авто"),
    model:              Optional[LLMModel] = Query(None,     description="LLM модель (None=авто по типу контента)"),
    temperature:        float            = Query(0.7,        ge=0.0, le=1.0),
    max_tokens:         int              = Query(8000,       ge=100, le=32000),
) -> LLMGeneratedContent:
    try:
        return await generate_adaptive_content(
            params             = params,
            version_to         = version_to,
            old_content        = old_content,
            imaginary_gradient = imaginary_gradient,
            related_terms      = related_terms,
            profile_id         = profile_id,
            prompt_mode        = prompt_mode,
            model              = model,
            temperature        = temperature,
            max_tokens         = max_tokens,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[/generate] неожиданная ошибка: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))



@llm_router.get(
    "/generate/examples",
    summary     = "Примеры тел запросов для /generate",
    description = "Возвращает готовые примеры JSON для каждого типа контента.",
    tags        = ["LLM"],
)
async def generate_examples() -> dict:
    return {
        "explanation": {
            "content_type":            "explanation",
            "term_name":               "Производная",
            "subject_specialization":  "математический анализ",
            "profile_id":              "engineer",
            "topic_title":             "Дифференциальное исчисление",
        },
        "test": {
            "content_type":         "test",
            "term_name":            "Производная",
            "question_format":      "Один правильный ответ (Multiple Choice Single Answer)",
            "cognitive_level":      "Применение/Вычисления (использование формул, базовые задачи)",
            "distractor_error_type": "Вычислительные (ошибки в арифметике или подстановке)",
            "number_of_choices":    4,
            "context_requirement":  "Абстрактный (чистая математическая формулировка)",
            "difficulty_level":     "Средний",
        },
        "problem": {
            "content_type":            "problem",
            "term_name":               "Производная",
            "subject_specialization":  "физика (механика)",
        },
        "topics": {
            "content_type":    "topics",
            "subject_name":    "Математический анализ",
            "number_of_topics": 7,
        },
        "terms": {
            "content_type":    "terms",
            "topic_title":     "Ряды Тейлора",
            "number_of_terms": 5,
        },
    }


# ==================== СПРАВОЧНИК МОДЕЛЕЙ ====================

@llm_router.get("/models", summary="Список доступных LLM моделей")
async def list_models() -> dict:
    return {
        "models": [m.value for m in LLMModel],
        "presets": {
            "default":       ModelPreset.DEFAULT.value,
            "fast_accurate": ModelPreset.FAST_ACCURATE.value,
            "premium":       ModelPreset.PREMIUM.value,
            "light":         ModelPreset.LIGHT.value,
        },
        "auto_selection": {
            "explanation": ModelPreset.DEFAULT.value,
            "test":        ModelPreset.FAST_ACCURATE.value,
            "problem":     ModelPreset.FAST_ACCURATE.value,
            "topics":      ModelPreset.LIGHT.value,
            "terms":       ModelPreset.LIGHT.value,
        },
    }


# ==================== СОХРАНЕНИЕ АРТЕФАКТОВ ====================

@llm_router.post("/save", status_code=201, summary="Сохранить артефакт")
async def save_artifact(
    artifact: ArtifactCreate,
    request:  Request,
    repo:     ArtifactRepository = Depends(),
) -> dict:
    teacher_id  = _get_teacher_id(request)
    artifact_id = await repo.save_artifact(artifact, created_by=teacher_id)
    return {"artifact_id": artifact_id, "status": "saved"}


# ==================== CRUD ====================

@llm_router.post("/save_topics", summary="Сохранить список тем")
async def save_topic(
    topic: TopicContent,
    repo:  TopicRepository = Depends(),
) -> dict:
    topic_id = await repo.save_topics(topic)
    return {"topic_id": topic_id}


@llm_router.post("/save_terms", summary="Сохранить список терминов")
async def create_term(
    term: TermContent,
    repo: TermRepository = Depends(),
) -> dict:
    term_id = await repo.save_terms(term)
    return {"term_id": term_id}


@llm_router.get("/by-topic/{topic_id}", summary="Термины по теме")
async def get_terms_for_topic(
    topic_id: str,
    repo:     TermRepository = Depends(),
) -> dict:
    terms = await repo.get_terms_by_topic(topic_id)
    return {"terms": terms}


@llm_router.get(
    "/by-material/{material_id}/type/{artifact_type}",
    summary = "Артефакты по материалу и типу",
)
async def get_artifacts(
    material_id:   str,
    artifact_type: str,
    repo:          ArtifactRepository = Depends(),
) -> dict:
    allowed = {"explanation", "problem_case", "test_question"}
    if artifact_type not in allowed:
        raise HTTPException(
            status_code = 400,
            detail      = f"Недопустимый тип. Допустимые: {allowed}",
        )
    artifacts = await repo.get_artifact_by_material_and_type(material_id, artifact_type)
    return {"artifacts": [a.model_dump() for a in artifacts]}


# ==================== УТИЛИТЫ ====================

def _get_teacher_id(request: Request) -> str:
    """
    Извлекает teacher_id из JWT токена.
    Поддерживает: Authorization: Bearer <token> и cookies.
    """
    import jwt as pyjwt
    from config.settings import settings

    token = None

    # 1. Пробуем из Authorization header
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]

    # 2. Пробуем из cookie
    if not token:
        token = request.cookies.get("access_token")

    # 3. Пробуем request.state.uid (authx заполняет при декораторе)
    if not token:
        uid = getattr(request.state, "uid", None)
        if uid:
            return uid

    if not token:
        raise HTTPException(status_code=401, detail="Требуется авторизация. Передай Bearer токен.")

    try:
        payload = pyjwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        uid = payload.get("sub") or payload.get("uid") or payload.get("id")
        if not uid:
            raise HTTPException(status_code=401, detail="Невалидный токен: нет subject.")
        return str(uid)
    except pyjwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Токен истёк.")
    except pyjwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Невалидный токен: {e}")