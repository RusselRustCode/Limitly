from typing import Union, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from src.llm.external_api import generate_adaptive_content
from src.core.models import (
    ContentParams, TestParams, ProblemParams, TopicsParams, TermsParams,
    TopicContent, TermContent, GeneratedArtifact, LLMGeneratedContent
)
from src.data_ingestion.topic_repo import TopicRepository
from src.data_ingestion.term_repo import TermRepository
from src.data_ingestion.artifacts_repo import ArtifactRepository

llm_router = APIRouter(prefix='/llm', tags=['LLM'])


@llm_router.post("/generate")
async def generate(
    params: Union[ContentParams, TestParams, ProblemParams, TopicsParams, TermsParams],
    version_to: int = 1,
    old_content: str = "",
    imaginary_gradient: Optional[List[dict]] = None,
    related_terms: Optional[List[str]] = None,
    profile_id: str = "engineer"
) -> LLMGeneratedContent:
    """
    Универсальный эндпоинт для генерации контента.
    """
    try:
        result = await generate_adaptive_content(
            params=params,
            version_to=version_to,
            old_content=old_content,
            imaginary_gradient=imaginary_gradient,
            related_terms=related_terms,
            profile_id=profile_id
        )
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Ошибка при генерации: {e}")


@llm_router.post('/save_topics')
async def save_topic(topic: TopicContent, repo: TopicRepository = Depends()):
    topic_id = repo.save_topics(topic)
    return {"topic_id": topic_id}

@llm_router.post("/save_terms")
async def create_term(term: TermContent, repo: TermRepository = Depends()):
    term_id = await repo.save_terms(term)
    return {"term_id": term_id}


@llm_router.get("/by-topic/{topic_id}")
async def get_terms_for_topic(topic_id: str, repo: TermRepository = Depends()):
    terms = await repo.get_terms_by_topic(topic_id)
    return {"terms": terms}


@llm_router.post("/save")
async def save_artifact(
    artifact: GeneratedArtifact,
    repo: ArtifactRepository = Depends()
):
    artifact_id = await repo.save_artifact(artifact)
    return {"artifact_id": artifact_id}

@llm_router.get("/by-material/{material_id}/type/{artifact_type}")
async def get_artifacts(material_id: str, artifact_type: str, repo: ArtifactRepository = Depends()):
    if artifact_type not in ["explanation", "problem_case", "test_question"]:
        raise HTTPException(status_code=400, detail="Недопустимый тип артефакта")
    artifacts = await repo.get_arifact_by_material_and_type(material_id, artifact_type)
    return {"artifacts": artifacts}
