from typing import Union, Optional, List
from fastapi import HTTPException, APIRouter, Depends, Request, Query

from src.llm.external_api_models import generate_adaptive_content
from src.llm.client import LLMModel, ModelPreset

from src.core.models import (
    ContentParams, TestParams, ProblemParams, TopicsParams, TermsParams,
    TopicContent, TermContent,
    ArtifactCreate, GeneratedArtifact,
    LLMGeneratedContent
)

from src.data_ingestion.topic_repo import TopicRepository
from src.data_ingestion.artifacts_repo import ArtifactRepository
from src.data_ingestion.term_repo import TermRepository

llm_router = APIRouter(prefix="/llm", tags=["LLM"])



@llm_router.post("/generate", response_model=LLMGeneratedContent)
async def generate(
    params: Union[ContentParams, TestParams, ProblemParams, TopicsParams, TermsParams],
    version_to: int = Query(1),
    old_content: str = Query(""),
    pseudo_gradient: Optional[List[dict]] = None,
    related_terms: Optional[List[str]] = None,
    profile_id: str = Query("engineer"),
    prompt_mode: Optional[str] = Query(None),
    model: Optional[LLMModel] = Query(None),
    temperature:        float                = Query(0.7, ge=0.0, le=1.0),
    max_tokens:         int                  = Query(8000, ge=100, le=32000)
):
    try:
        return await generate_adaptive_content(
            params=params,
            version_to=version_to,
            old_content=old_content,
            imaginary_gradient=pseudo_gradient,
            related_terms=related_terms,
            profile_id=profile_id,
            prompt_mode=prompt_mode,
            model=model,
            temperature=temperature,
            max_tokens=max_tokens,
        )
    except HTTPException:
        raise 
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации: {e}")
    
@llm_router.post("/save", status_code=201, summary="Сохранить артефакт")
async def save_artifact(
    artifact: ArtifactCreate,
    request: Request,
    repo: ArtifactRepository = Depends()
) -> dict:
    teacher_id = _get_teacher_id(request=request)
    artifact_id = await repo.save_artifact(artifact, teacher_id=teacher_id)   
    return {"artifact_id": artifact_id, "status": "saved"}


#Справочник моделей
llm_router.get("/models", summary="Список доступных LLM-моделей")
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
            "ContentParams":  ModelPreset.DEFAULT.value,
            "TestParams":     ModelPreset.FAST_ACCURATE.value,
            "ProblemParams":  ModelPreset.FAST_ACCURATE.value,
            "TopicsParams":   ModelPreset.LIGHT.value,
            "TermsParams":    ModelPreset.LIGHT.value,
        },
    }
    
    
@llm_router.post("/save_topics")
async def save_topics(topic: TopicContent, repo: TopicRepository = Depends()) -> dict:
    topic_id = await repo.save_topics(topic)
    return {"topic_id": topic_id}

@llm_router.post("/save_terms")
async def save_terms(terms: TermContent, repo: TermRepository = Depends()) -> dict:
    term_id = await repo.save_terms(terms)
    return {"term_id": term_id}


@llm_router.get("/by_topic/{topic_id}")
async def get_term_for_topics(topic_id: str, repo: TermRepository = Depends()) -> dict:
    terms = await repo.get_terms_by_id(topic_id)
    return {"terms": terms}

@llm_router.get("/by-material/{material_id}/type/{artifact_type}")
async def get_artifacts(material_id: str, artifact_type: str, repo: ArtifactRepository = Depends()) -> dict:
    allowed = {"explanation", "problem_case", "test_question"}
    if artifact_type not in allowed:
        raise HTTPException(status_code=401, detail=f"Недопустимый тип. Допустимые: {allowed}")
    artifacts = await repo.get_arifact_by_material_and_type(material_id=material_id, artifact_type=artifact_type)
    return {"artifacts": [a.model_dump() for a in artifacts]}



def _get_teacher_id(request: Request) -> str:
    uid = getattr(request.state, "uid", None)
    if not uid:
        raise HTTPException(status_code=401, detail="Требуется авторизация.")
    return uid