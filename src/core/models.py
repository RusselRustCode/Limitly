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
    reasoning: str
    explanation_body: str
    formula_block: str

class DistractorAnalyse(BaseModel):
    option_text: str
    error_explanation: str

class TestContent(BaseModel):
    reasoning: str
    question_body: str
    solution_steps: str
    options: list[str]
    correct_answer: Union[str, list[str]] #может быть строкой при SingleChoice, а может списком строк при MultipleChoice
    distractor_analysis: list[DistractorAnalyse]

class ProblemContent(BaseModel):
    reasoning: str
    problem_scenario: str
    required_input_values: str #Подумать оставляем так или меняем на  Dict[str, Any] или вообще кастомную модель делае
    solution_steps: str
    final_answer: str 

class TopicContent(BaseModel):
    reasoning: str
    topic_title: str
    topic_short_summary: str
    estimated_time_min: int = Field(ge=1, le=1000)
    complexity_rating: int

class TermContent(BaseModel):
    reasoning: str
    term_name: str
    learning_goal: str
    estimated_time_min: int = Field(ge=1, le=1000)
    complexity_rating: int

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

    # output_format: OutputFormat = Field(
    #     ...,
    #     description="Формат, в котором LLM должен представить итоговый контент (Markdown или LaTeX)."
    # )
    subject_specialization: str = Field(default="Математическое обеспечение и Администрирование информационных систем", description="Специальность")
    term_name: str = Field(..., description="Название термина")
    target_audience: TargetAudience = Field(
        ...,
        description="Уровень сложности и акцент на разных сферах"
    )

    usage_toggle: UsageToggle = Field(
        ...,
        description="Использовать ли метафоры для облегчения усвоения материала"
    )

    historical_content: UsageToggle = Field(
        ...,
        description="Использовать ли исторический контекст"
    )

    language_style: LanguageStyle = Field(
        ...,
        description="Стиль и общий тон объяснения "
    )

    explanation_len: ExplanationLenght = Field(
        ...,
        description="В каком формате(коротко, средне, детально)"
    )

    example_type: ExampleType = Field(
        ...,
        description="Фокусировка примеров (на теории или на реальных жизненных/научных кейсах)"
    )
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
    student_id: str = Field(..., description="id Студента")
    material_id: str = Field(..., description="id учебного материала")
    question_id: str = Field(..., description="id Вопроса")

    attempts: int = Field(..., description="Количество попыток")
    is_correct: bool = Field(..., description="Правильность ответа")
    time_spent_on_q: int = Field(..., description="Время потраченное на вопрос(секунды)")
    time_spent_on_m: int = Field(..., description="Время потраченное на материал(в секундах)")

    selected_distractor: Optional[str] = Field(None, description="Текст выбранного дистрактора")

    viewed_material_before: bool = Field(..., description="Смотрел ли материал до этого")
    timestamped: datetime = Field(default_factory=datetime.utcnow, description="Время записи лога")

#-------------------------
#Добавить компоненты для AnalyseResult
class StudentCluster(BaseModel):
    # type: str = Field(..., description="")
    cluster_label: int = Field(..., description="К какому кластеру принадлежит студент")

class EffectivenessSummary(BaseModel):
    success_coeff: float = Field(..., description="Коэффициент успешности")
    attempts_mean: float = Field(..., description="Среднее количество попыток")
    mean_time_on_material: float = Field(..., description="среднее количество времени потраченное на материал")
    usage_coeff: float = Field(..., description="Процент студентов использующих материал больше n минут")
    difficlty_coeff: float = Field(..., description="Коэффициент сложности")
    mean_time_on_question: float = Field(..., description="Среднее время потраченное на вопрос")
    learn_curve: float = Field(..., description="Кривая обчуения")
    success_coeff_vs_mean: float = Field(..., description="Коэффицент успешности в сравнении с средним по курсу")
    top_distractors: List[str] = Field(..., description="Список самых частых дистракторов")
    distractor_rates: Dict[str, int] = Field(..., description="Частота выбора дистрактора")
    wrong_attempts: int = Field(..., description="Общее количество неудачных попыток")
    total_events: int = Field(..., description="Общее количество взаимодействий")
    unique_students: int = Field(..., description="Уникальные студенты")
    

#--------------EngagementAnalyse-------------------
class ActivityMetrics(BaseModel):
    total_events: int = Field(..., description="Общее количетсво событий")
    events_per_day: float = Field(..., description="Событий в день")
    avg_correctness: float = Field(..., description="Средняя правильность")
    total_learning_time: float = Field(..., description="Общее время на обучение")
    total_material_time: float = Field(..., description="время потраченное на материал")
    total_question_time: float = Field(..., description="время потраченное на вопросы")
    total_attempts: int = Field(..., description="общее кол-во попыток")
    activity_duration_days: int = Field(..., description="Продолжительность активности дней")

class LearningPAtternMetrics(BaseModel):
    engagement_material_coeff: float = Field(..., description="Коэффициент_вовлеченности_материала")
    attempts_rate: float = Field(..., description="Частота_попыток")
    mean_attempts_on_question: float = Field(..., description="Ср_кол_во_попыток_на_вопрос")
    consistency_score: float = Field(..., description="")
    time_spent_on_material_vs_on_total_time: float = Field(..., description="Отношение времени потраченное на материал и общего времени")
    passive_consumption: float = Field(..., description="Индекс пассивного потребления")
    efficiency_of_efforts: float = Field(..., description="Эффективность усилий")

class TempPatternMetrics(BaseModel):
    hour_distr: Optional[int] = Field(..., description="Распределение часов")
    activity_on_wekend_coeff: float = Field(..., description="Активность на выходных")
    regular_coeff: float = Field(..., description="Коэффициент регулярности")
    most_activity_day: Optional[int] = Field(..., description="Самые активные дни")
    mean_time_session: float = Field(..., description="Среднее время сессии")
    activity_var: float = Field(..., description="Дисперсия активности")


class EfficiencyMetrics(BaseModel):
    learn_efficiency: float = Field(..., description="Эффективность обучения")
    learn_curve: float = Field(..., description="Кривая обучения")
    knowledge_retention: float = Field(..., description="")
    time_effiency: float = Field(..., description="Эффективность по времени")
    session_regular: float = Field(..., description="регулярность занятий")


class AnomalyAssesmentsMetrics(BaseModel):
    anomaly_flag: int = Field(..., description="Принадлежность к аномалии")
    anomaly_score: float = Field(..., description="Коэффициент аномальности")

class EngagementAnalyse(BaseModel):
    student_id: str = Field(..., description="ID студента")
    activity: ActivityMetrics = Field(..., description="Метрика активности")
    leanring_patterns: LearningPAtternMetrics = Field(..., description="Паттерны обчуения")
    temp_patterns: TempPatternMetrics = Field(..., description="Временные паттерны")
    efficiency: EfficiencyMetrics = Field(..., description="Эффективность")
    anomaly_assestment: AnomalyAssesmentsMetrics = Field(..., description="Признаки аномальности")


#-------------------------
class AnalyseResult(BaseModel):
    last_analysis_date: datetime = Field(default_factory=datetime.utcnow, description="")
    student_id: str = Field(..., description="ID студента")
    topic_id: str = Field(..., description="ID темы")


    studentcluster: StudentCluster = Field(..., description="")
    effectiveness: EffectivenessSummary = Field(..., description="")
    engagement: EngagementAnalyse = Field(..., description="")

    top_distractors_list: List[str] = Field(..., description="Список 5 самых проблемных дистракторов в этой теме/группе.")

AnalyseResult.model_rebuild()

