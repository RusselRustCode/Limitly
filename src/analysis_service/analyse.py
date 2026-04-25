"""
AnalysisService — основной сервис анализа цифрового следа.

Отвечает только за:
- Получение логов
- Расчёт метрик (через MetricsCalculator)
- Генерацию директив (через PlannerAgentV2)
- Сохранение результата
"""

from typing import List, Optional, Tuple
 
from src.core.models import TraceLog, MlAnalysisResult, AnalysisTrigger
from src.data_ingestion.trace_repo import TraceRepository
from src.analysis_service.analyse_repo import AnalyseRepository
from src.analysis_service.metrics_service import MetricsCalculator
from src.analysis_service.planner_agent import PlannerAgent


class AnalyseService:
    
    def __init__(self, trace_repo: TraceRepository, repo: Optional[AnalyseRepository]):
        self.trace_repo = trace_repo
        self.repo = repo or AnalyseRepository()
        self.metrics_calc = MetricsCalculator()
        self.agent = PlannerAgent()


    async def fetch_logs_for_artifact(
        self, artifact_id: str, student_id: Optional[str] = None
    ) -> List[TraceLog]:
        if student_id:
            return await self.trace_repo.get_logs_by_student_and_artifact(student_id, artifact_id)
        return await self.trace_repo.get_logs_by_artifact(artifact_id)
    
    async def analyze_artifact(self, 
        artifact_id: str, 
        topic_id: Optional[str] = None, 
        term_id: Optional[str] = None, 
        bloom_weight = 1.0, 
        force = False
    ) -> Optional[MlAnalysisResult]:
        logs = self.trace_repo.get_logs_by_artifact(artifact_id)
        if not logs:
            return None
        
        unique_students = len({log.student_id for log in logs})
        should_run, trigger = self._should_trigger_analysis(unique_students, logs, force)

        if not should_run:
            return None
        
        result = self.metrics_calc.analyze_artifact(trace_logs=logs,
            artifact_id=artifact_id,
            topic_id=topic_id,
            term_id=term_id,
            bloom_weight=bloom_weight,
            trigger=trigger,
            )
        
        metrics_dict = {
            "m_term":          result.average_mastery,
            "efficiency_score": result.efficiency_score,
            "efficiency_fresh": result.efficiency_fresh,
            "max_d_p":         max(result.distractor_indices.values(), default=0.0),
            "t_ratio":         1.0,   # усреднённое значение; детальный расчёт — в MetricsCalculator
            "attempts":        sum(log.attempts for log in logs) / max(len(logs), 1),
        }
        result.adaptation_directives = self.agent.get_directives(metrics_dict)
 
        await self.repo.save_analysis_result(result)
        return result
    
    async def get_analysis_for_artifact(
        self, artifact_id: str
    ) -> Optional[MlAnalysisResult]:
        return self.repo.get_latest_analysis_for_artifact(artifact_id)
    
    async def check_analysis_trigger(
        self, artifact_id: str
    ) -> Tuple[bool, Optional[AnalysisTrigger]]:
        logs = await self.trace_repo.get_logs_by_artifact(artifact_id)
        if not logs:
            return False, None
        unique_students = len({log.student_id for log in logs})
        return self._should_trigger_analysis(unique_students, logs, force=False)
    
    async def generate_adaptation_plan(
        self,
        artifact_id:    str,
        force_analysis: bool = False,
    ) -> Optional[dict]:
        """
        Генерирует план адаптации для передачи в Agent-Executor (LLM).
 
        Returns:
            Словарь с директивами и метаданными или None.
        """
        result = await self.get_analysis_for_artifact(artifact_id)
 
        if result is None or force_analysis:
            result = await self.analyze_artifact(artifact_id, force=True)
 
        if result is None:
            return None
 
        return {
            "artifact_id":          artifact_id,
            "efficiency_fresh":     result.efficiency_fresh,
            "average_mastery":      result.average_mastery,
            "top_error_patterns":   [e.value for e in result.top_error_patterns],
            "adaptation_directives": [
                d.model_dump() for d in result.adaptation_directives
            ],
        }
