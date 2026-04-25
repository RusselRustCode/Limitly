"""
Модуль анализа цифрового следа студента (Analysis Module).

Компоненты:
- MetricsCalculator          → расчёт всех метрик (M_j, M_term, E, E_fresh, D_p)
- PlannerAgentV2             → современный агент-планировщик на YAML-правилах
- AnalysisService            → основной сервис анализа
- AnalyseRepository          → работа с MongoDB (анализы + артефакты)
"""

from src.analysis_service.metrics_service import (
    MetricsCalculator,
    calculate_kt_coefficient,
    calculate_mastery_score,
    calculate_weighted_mastery,
    calculate_efficiency_score,
    calculate_distractor_index,
    # ← новый важный метод
)

from src.analysis_service.planner_agent import PlannerAgent

from src.analysis_service.analyse import AnalyseService

from src.analysis_service.analyse_repo import AnalyseRepository


__all__ = [
    # Метрики
    "MetricsCalculator",
    "calculate_kt_coefficient",
    "calculate_mastery_score",
    "calculate_weighted_mastery",
    "calculate_efficiency_score",
    "calculate_distractor_index",
    "calculate_artifact_efficiency_fresh",

    # Планировщик
    "PlannerAgentV2",

    # Сервис и репозиторий
    "AnalyseService",
    "AnalyseRepository",
]
