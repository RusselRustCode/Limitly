"""
Pydantic-модели системы.

Ключевые принципы:
  - ArtifactCreate  — входная модель для POST /llm/save. БЕЗ id и created_by.
  - GeneratedArtifact — полная модель из БД. Содержит id (от MongoDB) и created_by (от JWT).
  - materia_id удалён — он был дублем _id и путал фронт.
  - Устаревшие модели (AnalyseResult, EngagementAnalyse и иже с ними) удалены.
"""

from pydantic import BaseModel, Field, EmailStr, BeforeValidator
from bson import ObjectId
from enum import Enum
from datetime import datetime
from typing import List, Optional, Annotated, Dict, Union


def convert_objectid(v):
    """Конвертирует ObjectId → str. Строки оставляет как есть (student_050, etc.)"""
    if isinstance(v, ObjectId):
        return str(v)
    return v


def flexible_id(v):
    """
    Гибкий ID — принимает:
      - ObjectId            → str (MongoDB документы)
      - "507f1f77bc..."     → str (24-hex строка)
      - "student_050"       → str (произвольная строка, Telegram бот)
    """
    if isinstance(v, ObjectId):
        return str(v)
    if v is not None:
        return str(v)
    return v


PyObjectId   = Annotated[str, BeforeValidator(convert_objectid)]
FlexibleId   = Annotated[str, BeforeValidator(flexible_id)]


# =============================================================================
# ENUMS
# =============================================================================

class BloomLevel(str, Enum):
    KNOWLEDGE     = "knowledge"
    COMPREHENSION = "comprehension"
    APPLICATION   = "application"
    ANALYSIS      = "analysis"
    SYNTHESIS     = "synthesis"
    EVALUATION    = "evaluation"

    @property
    def weight(self) -> float:
        return {
            BloomLevel.KNOWLEDGE:     1.0,
            BloomLevel.COMPREHENSION: 1.0,
            BloomLevel.APPLICATION:   2.0,
            BloomLevel.ANALYSIS:      2.0,
            BloomLevel.SYNTHESIS:     3.0,
            BloomLevel.EVALUATION:    3.0,
        }.get(self, 1.0)


class ErrorType(str, Enum):
    OPERATIONAL = "operational"
    CONCEPTUAL  = "conceptual"
    PROCEDURAL  = "procedural"
    STRATEGIC   = "strategic"


class AdaptationStrategy(str, Enum):
    DECOMPOSE            = "decompose"
    CONTRAST             = "contrast"
    REINFORCE            = "reinforce"
    GUIDE                = "guide"
    REVIEW               = "review"
    SIMPLIFICATION       = "simplification"
    ACCENTUATION         = "accentuation"
    CONCEPT_BLOCK        = "concept_block"
    PROCEDURAL_CHECKLIST = "procedural_checklist"


class AnalysisTrigger(str, Enum):
    N_THRESHOLD         = "n_threshold"
    CRITICAL_EFFICIENCY = "critical_efficiency"
    EXPERT_REQUEST      = "expert_request"


# =============================================================================
# АУТЕНТИФИКАЦИЯ
# =============================================================================

class TeacherLogin(BaseModel):
    email:    EmailStr
    password: str


class TeacherCreate(BaseModel):
    email:     EmailStr
    full_name: str
    password:  str = Field(..., min_length=1)


class TeacherDB(BaseModel):
    id:              PyObjectId = Field(alias="_id")
    email:           EmailStr
    full_name:       str
    hashed_password: str
    created_time:    datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# =============================================================================
# КОНТЕНТ — типы результатов LLM
# =============================================================================

class DistractorAnalyse(BaseModel):
    option_text:       str
    error_explanation: str


class ExplanationContent(BaseModel):
    explanation_body: str


class TestContent(BaseModel):
    question_body:       str
    solution_steps:      List[str]
    options:             List[str]
    correct_answer:      Union[str, List[str]]
    distractor_analysis: List[DistractorAnalyse]


class ProblemContent(BaseModel):
    problem_scenario:      str
    required_input_values: List[str]
    solution_steps:        List[str]
    final_answer:          str


class TopicItem(BaseModel):
    reason:              str
    topic_title:         str
    topic_short_summary: str
    estimated_time_min:  int = Field(ge=1, le=1000)
    complexity_rating:   int


class TopicContent(BaseModel):
    topics: List[TopicItem]


class TermItem(BaseModel):
    reason:             str
    term_name:          str
    learning_goal:      str
    estimated_time_min: int = Field(ge=1, le=1000)
    complexity_rating:  int


class TermContent(BaseModel):
    terms: List[TermItem]


class LLMGeneratedContent(BaseModel):
    reasoning: str
    content: Union[
        ExplanationContent,
        TestContent,
        ProblemContent,
        TopicContent,
        TermContent,
    ]


# =============================================================================
# ПАРАМЕТРЫ ГЕНЕРАЦИИ
# =============================================================================

class ContentParams(BaseModel):
    term_name:              str
    subject_specialization: str
    profile_id:             str          = Field(default="engineer")
    topic_title:            Optional[str] = None


class QuestionFormat(str, Enum):
    SINGLE_CHOICE   = "Один правильный ответ (Multiple Choice Single Answer)"
    MULTIPLE_CHOICE = "Несколько правильных ответов (Multiple Choice Multiple Answer)"
    OPEN_ENDED      = "Открытый вопрос (Числовой ответ или короткий текст)"


class CognitiveLevel(str, Enum):
    RECALL      = "Запоминание/Воспроизведение (простые определения)"
    APPLICATION = "Применение/Вычисления (использование формул, базовые задачи)"
    ANALYSIS    = "Анализ/Синтез (сложные, многошаговые задачи)"


class DistractorErrorType(str, Enum):
    CONCEPTUAL    = "Концептуальные (ошибки в понимании принципов и определений)"
    CALCULATION   = "Вычислительные (ошибки в арифметике или подстановке)"
    MISCONCEPTION = "Распространенные заблуждения (типичные ошибки начинающих)"


class NumberOfChoices(int, Enum):
    LOW    = 3
    MEDIUM = 4
    HIGH   = 5


class ContextRequirement(str, Enum):
    ABSTRACT = "Абстрактный (чистая математическая формулировка)"
    SCENARIO = "Сценарный (вопрос должен быть обернут в реальную/прикладную историю)"


class DifficultyLevel(str, Enum):
    EASY   = "Легкий"
    MEDIUM = "Средний"
    HARD   = "Сложный"


class TestParams(BaseModel):
    term_name:             str
    question_format:       QuestionFormat
    cognitive_level:       CognitiveLevel
    distractor_error_type: DistractorErrorType
    number_of_choices:     NumberOfChoices
    context_requirement:   ContextRequirement
    difficulty_level:      DifficultyLevel


class TopicsParams(BaseModel):
    subject_name:     str
    number_of_topics: int


class TermsParams(BaseModel):
    topic_title:     str
    number_of_terms: int


class ProblemParams(BaseModel):
    term_name:              str
    subject_specialization: str


# =============================================================================
# АРТЕФАКТЫ
# =============================================================================

ArtifactContent = Union[
    ExplanationContent,
    TestContent,
    ProblemContent,
    TopicContent,
    TermContent,
]

ArtifactParams = Union[
    ContentParams,
    TestParams,
    ProblemParams,
    TopicsParams,
    TermsParams,
]


class ArtifactCreate(BaseModel):
    """
    Входная модель для POST /llm/save.

    Фронт передаёт ТОЛЬКО эти поля.
    id — создаёт MongoDB сам.
    created_by — бэк берёт из JWT токена.
    """
    term_id:       str   = Field(..., description="ID термина")
    artifact_type: str   = Field(..., description="explanation | problem_case | test_question")
    version:       str   = Field(default="1.0")
    is_active:     bool  = Field(default=True)
    bloom_weight:  float = Field(default=1.0)
    profile_id:    Optional[str]  = None

    content:             ArtifactContent
    distractor_analysis: Optional[List[DistractorAnalyse]] = None
    params_used:         Optional[ArtifactParams]          = None
    imaginary_gradient:  Optional[List[dict]]              = None


class GeneratedArtifact(ArtifactCreate):
    """
    Полная модель артефакта из БД.
    Используется только для чтения — MongoDB заполняет id и created_by.
    """
    id:         PyObjectId = Field(alias="_id")
    created_by: PyObjectId
    created_at: datetime   = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# =============================================================================
# ЦИФРОВОЙ СЛЕД
# =============================================================================

class TraceLog(BaseModel):
    student_id:  FlexibleId            # строка любого формата: ObjectId, "student_050", etc.
    artifact_id: PyObjectId
    question_id: Optional[PyObjectId] = None

    attempts:        int
    is_correct:      bool
    time_spent_sec:  int
    time_spent_on_q: Optional[int] = None
    time_spent_on_m: Optional[int] = None

    selected_distractor: Optional[str]       = None
    selected_error_type: Optional[ErrorType] = None

    viewed_material_before: bool = False
    is_nav_back:             bool = False
    first_exposure:          bool = Field(
        default=True,
        description="True если студент видит этот артефакт впервые"
    )
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


# =============================================================================
# АНАЛИЗ
# =============================================================================

class AdaptationDirective(BaseModel):
    strategy:       AdaptationStrategy
    trigger_metric: str
    trigger_value:  float
    directive_text: str
    priority:       int = Field(default=1, ge=1, le=5)


class MlAnalysisResult(BaseModel):
    artifact_id: PyObjectId
    topic_id:    Optional[PyObjectId] = None
    term_id:     Optional[PyObjectId] = None

    efficiency_score: float
    efficiency_fresh: float = 0.0
    average_mastery:  float

    top_error_patterns:    List[ErrorType]           = Field(default_factory=list)
    distractor_indices:    Dict[str, float]          = Field(default_factory=dict)
    adaptation_directives: List[AdaptationDirective] = Field(default_factory=list)

    analysis_date:   datetime               = Field(default_factory=datetime.utcnow)
    unique_students: int
    total_events:    int
    trigger:         Optional[AnalysisTrigger] = None

    class Config:
        populate_by_name = True
        use_enum_values  = True