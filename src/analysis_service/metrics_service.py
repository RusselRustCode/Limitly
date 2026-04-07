"""
Модуль расчёта метрик анализа цифрового следа студента.

Реализует только математический аппарат:
- M_j, M_term, E, D_p, Kt
- E_fresh (защита от carry-over)
"""

from typing import List, Dict, Optional, Tuple
from collections import defaultdict
import statistics
from pathlib import Path
import yaml
from src.core.models import TraceLog, ErrorType, MlAnalysisResult



# ==================== ФОРМУЛЫ ====================

def calculate_kt_coefficient(
    time_spent_sec: int, 
    time_ref: int,
    min_ratio: float = 0.5,
    max_ratio: float = 1.5
) -> float:
    if time_ref == 0:
        return 1.0
    ratio = time_spent_sec / time_ref
    if min_ratio <= ratio <= max_ratio:
        return 1.0
    return 0.7 if ratio < min_ratio else 0.8


def calculate_mastery_score(
    is_correct: bool,
    attempts: int,
    kt_coefficient: float
) -> float:
    if attempts <= 0:
        return 0.0
    s = 1.0 if is_correct else 0.0
    return (s * kt_coefficient) / attempts


def calculate_weighted_mastery(
    mastery_scores: List[float],
    bloom_weights: List[float]
) -> float:
    if not mastery_scores or not bloom_weights:
        return 0.0
    total = sum(m * w for m, w in zip(mastery_scores, bloom_weights))
    return total / sum(bloom_weights)


def calculate_efficiency_score(
    mastery_scores: List[float],
    d_target: float = 0.8
) -> float:
    if not mastery_scores:
        return 0.0
    n = len(mastery_scores)
    return sum(mastery_scores) / (n * d_target) if n > 0 else 0.0


def calculate_distractor_index(
    error_counts: Dict[ErrorType, int]
) -> Dict[str, float]:
    total_errors = sum(error_counts.values())
    if total_errors == 0:
        return {}
    return {
        et.value: count / total_errors 
        for et, count in error_counts.items()
    }


# ==================== ОСНОВНОЙ КЛАСС ====================

class MetricsCalculator:
    def __init__(self):
        self.config = self.load_config()
        self.thresholds = self.config["thresholds"]
        
        self.n_threshold           = self.thresholds["n_threshold"]
        self.m_min                 = self.thresholds["m_min"]
        self.t_low                 = self.thresholds["t_low"]
        self.t_high                = self.thresholds["t_high"]
        self.dp_critical           = self.thresholds["dp_critical"]
        self.attempts_critical     = self.thresholds["attempts_critical"]
        self.e_fresh_min           = self.thresholds["e_fresh_min"]
        self.time_ref              = self.thresholds["time_ref"]
        
    def load_config(self):
        path = Path("config/planner/planner_rules.yaml")
        with open(path, encoding='utf-8') as f:
            return yaml.safe_load(f)

    def calculate_artifact_mastery(
        self, 
        trace_logs: List[TraceLog],
        bloom_weight: float = 1.0
    ) -> Tuple[float, List[float]]:
        if not trace_logs:
            return 0.0, []
        
        mastery_scores = []
        for log in trace_logs:
            time_ref = self._get_time_ref(bloom_weight)
            time_spent = log.time_spent_sec or log.time_spent_on_q or 0
            kt = calculate_kt_coefficient(time_spent, time_ref)
            
            m_j = calculate_mastery_score(
                is_correct=log.is_correct,
                attempts=log.attempts,
                kt_coefficient=kt
            )
            mastery_scores.append(m_j)
        
        avg_mastery = statistics.mean(mastery_scores) if mastery_scores else 0.0
        return avg_mastery, mastery_scores

    def _get_time_ref(self, bloom_weight: float) -> int:
        if bloom_weight <= 1.0:
            return self.time_ref.get("knowledge", 30)
        elif bloom_weight <= 2.0:
            return self.time_ref.get("application", 90)
        return self.time_ref.get("synthesis", 180)

    def calculate_artifact_efficiency(
        self,
        mastery_scores: List[float],
        d_target: float = 0.8
    ) -> float:
        return calculate_efficiency_score(mastery_scores, d_target)

    def calculate_artifact_efficiency_fresh(
        self,
        trace_logs: List[TraceLog],
        d_target: float = 0.8
    ) -> float:
        fresh_logs = [log for log in trace_logs if getattr(log, 'first_exposure', True)]
        if not fresh_logs:
            return 0.0
        _, mastery_scores = self.calculate_artifact_mastery(fresh_logs)
        return self.calculate_artifact_efficiency(mastery_scores, d_target)

    def analyze_distractors(
        self,
        trace_logs: List[TraceLog]
    ) -> Tuple[Dict[str, float], List[ErrorType]]:
        error_counts: Dict[ErrorType, int] = defaultdict(int)
        for log in trace_logs:
            if log.selected_error_type:
                error_counts[log.selected_error_type] += 1

        distractor_indices = calculate_distractor_index(error_counts)
        top_error_patterns = [
            et for et, idx in distractor_indices.items() if idx > 0.4
        ]
        return distractor_indices, top_error_patterns

    def analyze_artifact(
        self,
        trace_logs: List[TraceLog],
        artifact_id: str,
        topic_id: Optional[str] = None,
        term_id: Optional[str] = None,
        bloom_weight: float = 1.0,
        trigger = None
    ) -> MlAnalysisResult:
        avg_mastery, mastery_scores = self.calculate_artifact_mastery(trace_logs, bloom_weight)
        efficiency_score = self.calculate_artifact_efficiency(mastery_scores)
        efficiency_fresh = self.calculate_artifact_efficiency_fresh(trace_logs)

        distractor_indices, top_error_patterns = self.analyze_distractors(trace_logs)

        return MlAnalysisResult(
            artifact_id=artifact_id,
            topic_id=topic_id,
            term_id=term_id,
            efficiency_score=efficiency_score,
            efficiency_fresh=efficiency_fresh,
            average_mastery=avg_mastery,
            top_error_patterns=top_error_patterns,
            distractor_indices=distractor_indices,
            unique_students=len({log.student_id for log in trace_logs}),
            total_events=len(trace_logs),
            trigger=trigger
        )