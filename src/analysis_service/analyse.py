"""
AnalysisService — основной сервис анализа цифрового следа.

Отвечает только за:
- Получение логов
- Расчёт метрик (через MetricsCalculator)
- Генерацию директив (через PlannerAgentV2)
- Сохранение результата
"""

from typing import List, Optional, Tuple
from datetime import datetime

from src.core.models import (
    TraceLog,
    MlAnalysisResult,
    AnalysisTrigger,
)
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
    
    async def analyze_artifact(
        self, 
        artifact_id: str,
        topic_id: Optional[str] = None,
        term_id: Optional[str] = None,
        bloom_weight: float = 1.0,
        force: bool = False
    ) ->  Optional[MlAnalysisResult]:
        logs = await self.fetch_logs_for_artifact(artifact_id=artifact_id)
        if not logs:
            return None
        
        unique_students = len({log.student_id for log in logs})
        should_analyze, trigger = self.should_trigger_analysis(
            unique_students, logs, force
        )
        
        if not should_analyze and not force:
            return None
        
        analysis_result = self.metrics_calc.analyze_artifact(
            trace_logs=logs,
            artifact_id=artifact_id, 
            topic_id=topic_id,
            term_id=term_id,
            bloom_weight=bloom_weight,
            trigger=trigger or (AnalysisTrigger.EXPERT_REQUEST if force else None)
        )
        
        await self.repo.save_analysis_result(analysis_result)
        return analysis_result
        
    def should_trigger_analysis(self, unique_students: int, logs: List[TraceLog], force: bool) -> Tuple[bool, Optional[AnalysisTrigger]]:
        if force:
            return True, AnalysisTrigger.EXPERT_REQUEST

        if unique_students > self.metrics_calc.n_threshold:
            return True, AnalysisTrigger.N_THRESHOLD
        
        # Считаем E_fresh для более точного триггера
        e_fresh = self.metrics_calculator.calculate_artifact_efficiency_fresh(logs)
        if e_fresh < self.metrics_calculator.critical_efficiency:
            return True, AnalysisTrigger.CRITICAL_EFFICIENCY

        return False, None
    
    async def get_analysis_for_artifact(self, artifact_id: str) -> Optional[MlAnalysisResult]:
        return await self.repo.get_latest_analysis_for_artifact(artifact_id)
    
    async def check_analysis_trigger(self, artifact_id: str) -> Tuple[bool, Optional[AnalysisTrigger]]:
        logs = await self.fetch_logs_for_artifact(artifact_id=artifact_id)
        if not logs: 
            return False, None
        unique_students = len({log.student_id for log in logs})
        return self.should_trigger_analysis(unique_students=unique_students, logs=logs, force=False)
    
    