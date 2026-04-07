from pydantic import BaseModel, Field, EmailStr, BeforeValidator
from bson import ObjectId
from enum import Enum
from datetime import datetime
from typing import List, Optional, Annotated, Dict, Union
def convert_objectid(v):
    if isinstance(v, ObjectId):
        return str(v)
    return v

PyObjectId = Annotated[str, BeforeValidator(convert_objectid)] #Чекнуть BeforeValidator

# ----------------- ENUMS ДЛЯ АНАЛИЗА ЦС -----------------

class BloomLevel(str, Enum):
    """Таксономия Блума для когнитивной классификации заданий"""
    KNOWLEDGE = "knowledge"  # Знание, воспроизведение фактов
    COMPREHENSION = "comprehension"  # Понимание
    APPLICATION = "application"  # Применение
    ANALYSIS = "analysis"  # Анализ
    SYNTHESIS = "synthesis"  # Синтез
    EVALUATION = "evaluation"  # Оценка

    @property
    def weight(self) -> float:
        """Вес когнитивной сложности по таксономии Блума"""
        weights = {
            BloomLevel.KNOWLEDGE: 1.0,
            BloomLevel.COMPREHENSION: 1.0,
            BloomLevel.APPLICATION: 2.0,
            BloomLevel.ANALYSIS: 2.0,
            BloomLevel.SYNTHESIS: 3.0,
            BloomLevel.EVALUATION: 3.0,
        }
        return weights.get(self, 1.0)

class ErrorType(str, Enum):
    """Типы ошибок для дистракторного анализа"""
    OPERATIONAL = "operational"  # Вычислительные ошибки, знаки
    CONCEPTUAL = "conceptual"  # Непонимание сути термина
    PROCEDURAL = "procedural"  # Нарушение алгоритма решения
    STRATEGIC = "strategic"  # Неверный выбор метода решения

class AdaptationStrategy(str, Enum):
    """Стратегии адаптации контента для Агента-Планировщика"""
    SIMPLIFICATION = "simplification"  # Упрощение синтаксиса, лексики
    ACCENTUATION = "accentuation"  # Акцентирование на проблемной зоне
    DECOMPOSITION = "decomposition"  # Декомпозиция на шаги
    CONCEPT_BLOCK = "concept_block"  # Внедрение концептуальных блоков
    PROCEDURAL_CHECKLIST = "procedural_checklist"  # Трансформация в чек-лист
    
    # Новые стратегии для жёстких правил
    DECOMPOSE = "decompose"  # Декомпозиция на мелкие шаги
    CONTRAST = "contrast"  # Противопоставление правильного и ошибочного
    REINFORCE = "reinforce"  # Усиление примерами и практикой
    GUIDE = "guide"  # Пошаговое ведение с подсказками
    REVIEW = "review"  # Полное ревью контента

class AnalysisTrigger(str, Enum):
    """Триггеры для запуска анализа и перегенерации"""
    N_THRESHOLD = "n_threshold"  # Накопление N пользователей
    CRITICAL_EFFICIENCY = "critical_efficiency"  # Падение E < F
    EXPERT_REQUEST = "expert_request"  # Принудительный запрос преподавателя

# ----------------- МОДЕЛИ ДЛЯ СТРУКТУРЫ КУРСА -----------------

class Subject(BaseModel):
    """Модель предмета/дисциплины"""
    id: PyObjectId = Field(alias="_id", description="Уникальный ID предмета")
    slug: str = Field(..., description="Человекочитаемый ID для URL")
    title: str = Field(..., description="Название предмета")
    created_by: PyObjectId = Field(..., description="ID преподавателя-владельца")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")

    class Config:
        populate_by_name = True

class Topic(BaseModel):
    """Модель темы внутри предмета"""
    id: PyObjectId = Field(alias="_id", description="ID Темы")
    subject_id: PyObjectId = Field(..., description="Ссылка на родительский предмет")
    title: str = Field(..., description="Название темы")
    complexity_rating: int = Field(default=3, ge=1, le=5, description="Целевая сложность (1-5)")
    order_index: int = Field(default=0, description="Позиция в иерархии курса")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Дата создания")

    class Config:
        populate_by_name = True

# ----------------- МОДЕЛИ АУТЕНТИФИКАЦИИ -----------------
class TeacherLogin(BaseModel):
    email: EmailStr = Field(...)
    password: str = Field(...)

class TeacherCreate(BaseModel):
    email: EmailStr = Field(...)
    full_name: str = Field(...)
    password: str = Field(..., min_length=1)

class TeacherDB(BaseModel):
    id: PyObjectId = Field(alias="_id")
    email: EmailStr
    full_name: str
    hashed_password: str
    created_time: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True

#Модели для валидации content в LLMGeneratedContent
class ExplanationContent(BaseModel):
    explanation_body: str

class DistractorAnalyse(BaseModel):
    option_text: str
    error_explanation: str

class TestContent(BaseModel):
    question_body: str
    solution_steps: list[str]  # Список шагов решения
    options: list[str]
    correct_answer: Union[str, list[str]]  # может быть строкой при SingleChoice, а может списком строк при MultipleChoice
    distractor_analysis: list[DistractorAnalyse]

class ProblemContent(BaseModel):
    problem_scenario: str
    required_input_values: list[str]  # Список входных данных для задачи
    solution_steps: list[str]  # Список шагов решения
    final_answer: str

class TopicItem(BaseModel):
    reason: str
    topic_title: str
    topic_short_summary: str
    estimated_time_min: int = Field(ge=1, le=1000)
    complexity_rating: int


class TopicContent(BaseModel):
    topics: List[TopicItem]

class TermItem(BaseModel):
    reason: str
    term_name: str
    learning_goal: str
    estimated_time_min: int = Field(ge=1, le=1000)
    complexity_rating: int

class TermContent(BaseModel):
    terms: List[TermItem]

class LLMGeneratedContent(BaseModel):
    reasoning: str
    content: Union[ProblemContent, TopicContent, TestContent, TermContent, ExplanationContent]

#Параметры для промпта, который передастяс LLM
class OutputFormat(str, Enum):
    MARKDOWN = "Markdown"
    LATEX = "LaTeX"

class TargetAudience(str, Enum):
    MATHEMATICIANS = "для математиков (строгий, с доказательствами)"
    NON_MATHEMATICIANS = "для нематематиков (с практическим применением)"

class UsageToggle(str, Enum):
    YES = "Да"
    NO = "Нет"

class LanguageStyle(str, Enum):
    ACADEMIC = "Академический"
    CASUAL = "Разговорный"
    FORMAL = "Официальный"
    STRICT = "Строгий"

class ExplanationLenght(str, Enum):
    BRIEF = "Кратко (около 100 слов)"
    MEDIUM = "Средне (около 250 слов)"
    DETAILED = "Подробно (около 500 слов)"

class ExampleType(str, Enum):
    THEORETICAL = "Теоретический (классические примеры)"
    REAL_CASE = "Реальный кейс (физика/экономика/астрономия)"



# ------------------
class ContentParams(BaseModel):
    """Минимальные параметры. Всё остальное (стиль, метафоры, Bloom и т.д.) берётся из profiles.yaml"""
    term_name: str = Field(..., description="Название термина")
    subject_specialization: str = Field(..., description="Специализация (Матанализ, Физика и т.д.)")
    profile_id: str = Field(default="engineer", description="ID профиля из profiles.yaml (theorist / engineer / lighthouse)")
    
    # Опционально
    topic_title: Optional[str] = None
#-------------------------
#Добавить компоненты для Промта по генерации тестов(вопросов)
class QuestionFormat(str, Enum):
    SINGLE_CHOICE = "Один правильный ответ (Multiple Choice Single Answer)"
    MULTIPLE_CHOICE = "Несколько правильных ответов (Multiple Choice Multiple Answer)"
    OPEN_ENDED = "Открытый вопрос (Числовой ответ или короткий текст)"

class CognitiveLevel(str, Enum):
    RECALL = "Запоминание/Воспроизведение (простые определения)"
    APPLICATION = "Применение/Вычисления (использование формул, базовые задачи)"
    ANALYSIS = "Анализ/Синтез (сложные, многошаговые задачи)"

class DistractorErrorType(str, Enum):
    CONCEPTUAL = "Концептуальные (ошибки в понимании принципов и определений)"
    CALCULATION = "Вычислительные (ошибки в арифметике или подстановке)"
    MISCONCEPTION = "Распространенные заблуждения (типичные ошибки начинающих)"

class NumberOfChoices(int, Enum):
    LOW = 3  # (2 дистрактора)
    MEDIUM = 4 # (3 дистрактора)
    HIGH = 5   # (4 дистрактора)


class ContextRequirement(str, Enum):
    ABSTRACT = "Абстрактный (чистая математическая формулировка)"
    SCENARIO = "Сценарный (вопрос должен быть обернут в реальную/прикладную историю)"

class DifficultyLevel(str, Enum):
    EASY = "Легкий"
    MEDIUM = "Средний"
    HARD = "Сложный"
#-------------------------

class TestParams(BaseModel):
    term_name: str
    question_format: QuestionFormat
    cognitive_level: CognitiveLevel
    distractor_error_type: DistractorErrorType
    number_of_choices: NumberOfChoices
    context_requirement: ContextRequirement
    difficulty_level: DifficultyLevel
    
class TopicsParams(BaseModel):
    subject_name: str = Field(..., description="Название предмета")
    number_of_topics: int = Field(..., description="Количество тем")
    
class TermsParams(BaseModel):
    topic_title: str = Field(..., description="Название темы")
    number_of_terms: int = Field(..., description="Кол-во терминов")
    
class ProblemParams(BaseModel):
    term_name: str = Field(..., description="Название темы")
    # explanation_body: str = Field(..., description="Текст объяснения")
    subject_specialization: str = Field(..., description="Специализация")
    

#-------------------------
#Добавить компоненты для TraceLog
#-------------------------
class TraceLog(BaseModel):
    student_id: PyObjectId = Field(..., description="ID Студента")
    artifact_id: PyObjectId = Field(..., description="ID конкретной версии артефакта")
    material_id: Optional[PyObjectId] = Field(None)
    question_id: Optional[PyObjectId] = Field(None)

    attempts: int = Field(...)
    is_correct: bool = Field(...)
    time_spent_on_q: Optional[int] = Field(None)
    time_spent_on_m: Optional[int] = Field(None)
    time_spent_sec: int = Field(...)

    selected_distractor: Optional[str] = Field(None)
    selected_error_type: Optional[ErrorType] = Field(None)

    viewed_material_before: bool = Field(...)
    is_nav_back: bool = Field(default=False)

    # === НОВОЕ ПОЛЕ ===
    first_exposure: bool = Field(default=True, description="True, если студент видит этот термин/артефакт впервые")

    timestamped: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        populate_by_name = True


ArtifactContent = Union[
    TestContent, 
    ExplanationContent, 
    ProblemContent, 
    TopicContent, 
    TermContent
]

# Параметры генерации также могут быть разными в зависимости от типа артефакта 
ArtifactParams = Union[
    TestParams, 
    ContentParams, 
    ProblemParams, 
    TopicsParams, 
    TermsParams
]

class GeneratedArtifact(BaseModel):
    id: PyObjectId = Field(alias="_id", description="")
    materia_id: PyObjectId = Field(..., description="Ссылка на learning_materials._id")
    term_id: PyObjectId = Field(..., description="Ссылка на термин/материал")
    artifact_type: str = Field(..., description="Тип: explanation, problem_case, test_question")
    version: str = Field(default="1.0", description="Версия контента (например, 1.1)")
    is_active: bool = Field(default=True, description="Флаг актуальной версии для выдачи группе")
    bloom_weight: float = Field(default=1.0, description="Вес по таксономии Блума (1.0, 2.0, 3.0)")
    content: ArtifactContent = Field(..., description="")
    distractor_analysis: Optional[List[DistractorAnalyse]] = Field(
        None,
        description="Типизация ошибок для каждого варианта ответа"
    )
    params_used: Optional[ArtifactParams] = Field(
        None,
        description="Параметры генерации (TestParams, ContentParams и т.д.)"
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Время регистрации"
    )
    created_by: PyObjectId = Field(..., description="ID Преподавателя")

    class Config:
        populate_by_name = True

#-------------------------
#Добавить компоненты для AnalyseResult
class StudentCluster(BaseModel):
    cluster_label: int = Field(..., description="К какому кластеру принадлежит студент")
    confidence: float = Field(default=0.0, description="Уверенность классификации")

class EffectivenessSummary(BaseModel):
    """Метрики эффективности контента для эволюционного анализа"""
    efficiency_score: float = Field(..., description="Метрика эффективности контента E")
    average_mastery: float = Field(..., description="Средний уровень освоения группы M_term")
    
    # Базовые метрики
    success_coeff: float = Field(..., description="Коэффициент успешности")
    attempts_mean: float = Field(..., description="Среднее количество попыток")
    mean_time_on_material: float = Field(..., description="Среднее количество времени потраченное на материал")
    usage_coeff: float = Field(..., description="Процент студентов использующих материал больше n минут")
    difficulty_coeff: float = Field(..., description="Коэффициент сложности")
    mean_time_on_question: float = Field(..., description="Среднее время потраченное на вопрос")
    learn_curve: float = Field(..., description="Кривая обучения")
    success_coeff_vs_mean: float = Field(..., description="Коэффициент успешности в сравнении со средним по курсу")
    
    # Дистракторный анализ
    top_distractors: List[str] = Field(..., description="Список самых частых дистракторов")
    distractor_rates: Dict[str, float] = Field(..., description="Частота выбора дистрактора (D_p индекс)")
    error_pattern_weights: Dict[str, float] = Field(default_factory=dict, description="Вес паттерна ошибки W_p")
    
    # Агрегированные данные
    wrong_attempts: int = Field(..., description="Общее количество неудачных попыток")
    total_events: int = Field(..., description="Общее количество взаимодействий")
    unique_students: int = Field(..., description="Уникальные студенты")
    
    # Таксономия Блума
    mastery_by_bloom_level: Dict[str, float] = Field(default_factory=dict, description="Уровень освоения по уровням Блума")

class ActivityMetrics(BaseModel):
    """Метрики активности студента"""
    total_events: int = Field(..., description="Общее количество событий")
    events_per_day: float = Field(..., description="Событий в день")
    avg_correctness: float = Field(..., description="Средняя правильность")
    total_learning_time: float = Field(..., description="Общее время на обучение")
    total_material_time: float = Field(..., description="Время потраченное на материал")
    total_question_time: float = Field(..., description="Время потраченное на вопросы")
    total_attempts: int = Field(..., description="Общее кол-во попыток")
    activity_duration_days: int = Field(..., description="Продолжительность активности дней")

class LearningPatternMetrics(BaseModel):
    engagement_material_coeff: float = Field(..., description="Коэффициент вовлеченности материала")
    attempts_rate: float = Field(..., description="Частота попыток")
    mean_attempts_on_question: float = Field(..., description="Ср. кол-во попыток на вопрос")
    consistency_score: float = Field(..., description="")
    time_spent_on_material_vs_on_total_time: float = Field(..., description="Отношение времени потраченное на материал и общего времени")
    passive_consumption: float = Field(..., description="Индекс пассивного потребления")
    efficiency_of_efforts: float = Field(..., description="Эффективность усилий")

class TempPatternMetrics(BaseModel):
    hour_distr: Optional[Dict[int, float]] = Field(None, description="Распределение часов")
    activity_on_weekend_coeff: float = Field(..., description="Активность на выходных")
    regular_coeff: float = Field(..., description="Коэффициент регулярности")
    most_activity_day: Optional[int] = Field(None, description="Самые активные дни")
    mean_time_session: float = Field(..., description="Среднее время сессии")
    activity_var: float = Field(..., description="Дисперсия активности")

class EfficiencyMetrics(BaseModel):
    learn_efficiency: float = Field(..., description="Эффективность обучения")
    learn_curve: float = Field(..., description="Кривая обучения")
    knowledge_retention: float = Field(..., description="")
    time_efficiency: float = Field(..., description="Эффективность по времени")
    session_regular: float = Field(..., description="Регулярность занятий")

class AnomalyAssessmentsMetrics(BaseModel):
    anomaly_flag: int = Field(..., description="Принадлежность к аномалии")
    anomaly_score: float = Field(..., description="Коэффициент аномальности")

class EngagementAnalyse(BaseModel):
    student_id: PyObjectId = Field(..., description="ID студента")
    activity: ActivityMetrics = Field(..., description="Метрика активности")
    learning_patterns: LearningPatternMetrics = Field(..., description="Паттерны обучения")
    temp_patterns: TempPatternMetrics = Field(..., description="Временные паттерны")
    efficiency: EfficiencyMetrics = Field(..., description="Эффективность")
    anomaly_assessment: AnomalyAssessmentsMetrics = Field(..., description="Признаки аномальности")

class AdaptationDirective(BaseModel):
    """Директива для Агента-Планировщика на перегенерацию контента"""
    strategy: AdaptationStrategy = Field(..., description="Стратегия адаптации")
    trigger_metric: str = Field(..., description="Метрика, вызвавшая директиву (E, D_p, M_term)")
    trigger_value: float = Field(..., description="Значение метрики")
    directive_text: str = Field(..., description="Текстовая инструкция для LLM")
    priority: int = Field(default=1, ge=1, le=5, description="Приоритет директивы (1-высший)")

class MlAnalysisResult(BaseModel):
    """Результат агрегированного анализа для группы (хранится в ml_analysis_results)"""
    artifact_id: PyObjectId = Field(..., description="Ссылка на оцениваемую версию контента")
    topic_id: Optional[PyObjectId] = Field(None, description="ID темы")
    term_id: Optional[PyObjectId] = Field(None, description="ID термина")
    
    # Метрики
    efficiency_score: float = Field(..., description="Метрика эффективности контента E")
    efficiency_fresh: float = Field(0.0, description="Метрика эффективности контента E на новой когорте")
    average_mastery: float = Field(..., description="Средний уровень освоения группы M_term")
    
    # Дистракторный анализ
    top_error_patterns: List[ErrorType] = Field(default_factory=list, description="Массив доминирующих типов ошибок в группе")
    distractor_indices: Dict[str, float] = Field(default_factory=dict, description="Индексы деструктивности D_p по типам ошибок")
    
    # Директивы для перегенерации
    adaptation_directives: List[AdaptationDirective] = Field(default_factory=list, description="Инструкции для Агента-Планировщика")
    
    # Метаданные анализа
    analysis_date: datetime = Field(default_factory=datetime.utcnow, description="Дата анализа")
    unique_students: int = Field(..., description="Количество уникальных студентов в выборке")
    total_events: int = Field(..., description="Общее количество событий")
    trigger: Optional[AnalysisTrigger] = Field(None, description="Триггер, вызвавший анализ")
    
    class Config:
        populate_by_name = True
        use_enum_values = True

#-------------------------
class AnalyseResult(BaseModel):
    """Устаревшая модель, используется MlAnalysisResult для нового анализа"""
    last_analysis_date: datetime = Field(default_factory=datetime.utcnow, description="")
    student_id: PyObjectId = Field(..., description="ID студента")
    topic_id: PyObjectId = Field(..., description="ID темы")

    studentcluster: StudentCluster = Field(..., description="")
    effectiveness: EffectivenessSummary = Field(..., description="")
    engagement: EngagementAnalyse = Field(..., description="")

    top_distractors_list: List[str] = Field(..., description="Список 5 самых проблемных дистракторов в этой теме/группе.")

AnalyseResult.model_rebuild()

