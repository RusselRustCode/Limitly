"""
Обёртка для запроса генерации с discriminator-полем.
Позволяет Swagger UI показывать правильные поля в зависимости от типа контента.
"""

from typing import Union, Literal, Optional
from pydantic import BaseModel, Field
from src.core.models import (
    ContentParams, TestParams, ProblemParams, TopicsParams, TermsParams,
)


class ContentRequest(ContentParams):
    """Объяснение термина"""
    content_type: Literal["explanation"] = "explanation"


class TestRequest(TestParams):
    """Тестовый вопрос"""
    content_type: Literal["test"] = "test"


class ProblemRequest(ProblemParams):
    """Практическая задача"""
    content_type: Literal["problem"] = "problem"


class TopicsRequest(TopicsParams):
    """Список тем курса"""
    content_type: Literal["topics"] = "topics"


class TermsRequest(TermsParams):
    """Список терминов темы"""
    content_type: Literal["terms"] = "terms"


# Discriminated union — FastAPI/Swagger поймёт по полю content_type
GenerateRequest = Union[
    ContentRequest,
    TestRequest,
    ProblemRequest,
    TopicsRequest,
    TermsRequest,
]