"""
AnalysisService — основной сервис анализа цифрового следа.
"""

import logging
from typing import List, Optional, Tuple

from src.core.models import TraceLog, MlAnalysisResult, AnalysisTrigger
from src.core.exceptions import InsufficientDataError, AnalysisError
from src.data_ingestion.trace_repo import TraceRepository
from src.analysis_service.analyse_repo import AnalyseRepository
from src.analysis_service.metrics_service import MetricsCalculator
from src.analysis_service.planner_agent import PlannerAgent

logger = logging.getLogger(__name__)


class AnalyseService:

    def __init__(
        self,
        trace_repo: TraceRepository,
        repo:       Optional[AnalyseRepository] = None,
    ):
        self.trace_repo   = trace_repo
        self.repo         = repo or AnalyseRepository()
        self.metrics_calc = MetricsCalculator()
        self.agent        = PlannerAgent()

    async def analyze_artifact(
        self,
        artifact_id:  str,
        topic_id:     Optional[str] = None,
        term_id:      Optional[str] = None,
        bloom_weight: float = 1.0,
        force:        bool  = False,
    ) -> Optional[MlAnalysisResult]:
        logs = await self.trace_repo.get_logs_by_artifact(artifact_id)

        if not logs:
            if force:
                raise InsufficientDataError(
                    f"Нет цифрового следа для артефакта {artifact_id}. "
                    "Используйте /simulator/run для генерации тестовых логов."
                )
            logger.debug(f"[AnalyseService] нет логов для {artifact_id}")
            return None

        unique_students = len({log.student_id for log in logs})
        should_run, trigger = self._should_trigger(unique_students, logs, force)

        if not should_run:
            logger.info(
                f"[AnalyseService] анализ не нужен | artifact={artifact_id} | "
                f"students={unique_students}"
            )
            return None

        try:
            result = self.metrics_calc.analyze_artifact(
                trace_logs=logs,
                artifact_id=artifact_id,
                topic_id=topic_id,
                term_id=term_id,
                bloom_weight=bloom_weight,
                trigger=trigger,
            )
        except Exception as e:
            logger.error(f"[AnalyseService] ошибка расчёта метрик: {e}", exc_info=True)
            raise AnalysisError(f"Ошибка расчёта метрик: {e}")

        metrics_dict = {
            "m_term":           result.average_mastery,
            "efficiency_score": result.efficiency_score,
            "efficiency_fresh": result.efficiency_fresh,
            "max_d_p":          max(result.distractor_indices.values(), default=0.0),
            "t_ratio":          1.0,
            "attempts":         sum(log.attempts for log in logs) / max(len(logs), 1),
        }
        result.adaptation_directives = self.agent.get_directives(metrics_dict)

        await self.repo.save_analysis_result(result)

        logger.info(
            f"[AnalyseService] OK | artifact={artifact_id} | "
            f"E_fresh={result.efficiency_fresh:.3f} | "
            f"M_term={result.average_mastery:.3f} | "
            f"directives={len(result.adaptation_directives)}"
        )
        return result

    async def get_analysis_for_artifact(
        self, artifact_id: str
    ) -> Optional[MlAnalysisResult]:
        import inspect
        result = self.repo.get_latest_analysis_for_artifact(artifact_id)
        # Защита: если метод не async в старой версии репо — awaitable проверка
        if inspect.isawaitable(result):
            result = await result
        return result

    async def check_analysis_trigger(
        self, artifact_id: str
    ) -> Tuple[bool, Optional[AnalysisTrigger]]:
        logs = await self.trace_repo.get_logs_by_artifact(artifact_id)
        if not logs:
            return False, None
        unique_students = len({log.student_id for log in logs})
        return self._should_trigger(unique_students, logs, force=False)

    async def generate_adaptation_plan(
        self,
        artifact_id:    str,
        force_analysis: bool = False,
    ) -> Optional[dict]:
        result = await self.get_analysis_for_artifact(artifact_id)

        if result is None or force_analysis:
            result = await self.analyze_artifact(artifact_id, force=True)

        if result is None:
            return None

        return {
            "artifact_id":           artifact_id,
            "efficiency_fresh":      result.efficiency_fresh,
            "average_mastery":       result.average_mastery,
            "top_error_patterns":    [e for e in result.top_error_patterns],
            "adaptation_directives": [d.model_dump() for d in result.adaptation_directives],
        }

    def _should_trigger(
        self,
        unique_students: int,
        logs:            List[TraceLog],
        force:           bool,
    ) -> Tuple[bool, Optional[AnalysisTrigger]]:

        if force:
            return True, AnalysisTrigger.EXPERT_REQUEST
        if unique_students >= self.metrics_calc.n_threshold:
            return True, AnalysisTrigger.N_THRESHOLD

        e_fresh = self.metrics_calc.calculate_artifact_efficiency_fresh(logs)
        if e_fresh < self.metrics_calc.e_fresh_min:
            return True, AnalysisTrigger.CRITICAL_EFFICIENCY

        return False, None