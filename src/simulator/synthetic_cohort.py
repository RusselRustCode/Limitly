"""
Синтетический симулятор студентов на основе IRT 3PL.

Используется для:
  - Тестирования системы без реальных студентов
  - Демонстрации цикла: генерация → анализ → регенерация
  - Экспериментов с разными параметрами когорт

Модель: трёхпараметрическая логистическая (3PL)
  P(S=1 | θ, a, b, c) = c + (1-c) / (1 + exp(-a*(θ-b)))

  θ — способность студента
  a — дискриминация вопроса
  b — сложность (зависит от content_quality)
  c — вероятность угадывания
"""

import numpy as np
from scipy.stats import skewnorm
from bson import ObjectId
from datetime import datetime
from typing import List, Dict, Optional

from src.core.models import TraceLog, ErrorType


# ==================== ПРЕСЕТЫ КОГОРТ ====================

COHORT_PRESETS = {
    "strong": {
        "description": "Сильная группа (μ=1.2, σ=0.4)",
        "skew": 0.0,
        "loc":  1.2,
        "scale": 0.4,
    },
    "average": {
        "description": "Средняя группа (μ=0.8, σ=0.5)",
        "skew": 0.0,
        "loc":  0.8,
        "scale": 0.5,
    },
    "weak": {
        "description": "Слабая группа (скошенное влево)",
        "skew": -0.5,
        "loc":  0.3,
        "scale": 0.6,
    },
    "mixed": {
        "description": "Смешанная группа (стандартное нормальное)",
        "skew": 0.0,
        "loc":  0.0,
        "scale": 1.1,
    },
}


class SyntheticCohort:
    """
    Синтетическая когорта студентов для симуляции цифрового следа.

    Args:
        n:               Количество студентов
        content_quality: Качество контента [0.0–1.0]. Влияет на b (сложность) и тип ошибок.
        cohort_type:     Пресет когорты: "strong" | "average" | "weak" | "mixed"
        skew:            Скос распределения способностей (переопределяет пресет)
        error_bias:      Доминирующий тип ошибок: "conceptual" | "operational" | "procedural" | "balanced"
        seed:            Seed для воспроизводимости
    """

    def __init__(
        self,
        n:               int   = 250,
        content_quality: float = 0.6,
        cohort_type:     str   = "mixed",
        skew:            Optional[float] = None,
        error_bias:      str  = "balanced",
        seed:            int  = 42,
    ):
        self.n               = n
        self.content_quality = np.clip(content_quality, 0.0, 1.0)
        self.cohort_type     = cohort_type
        self.error_bias      = error_bias
        self.seed            = seed

        preset       = COHORT_PRESETS.get(cohort_type, COHORT_PRESETS["mixed"])
        self._loc    = preset["loc"]
        self._scale  = preset["scale"]
        self._skew   = skew if skew is not None else preset["skew"]

        self._generate()

    # ==================== ГЕНЕРАЦИЯ ====================

    def _generate(self):
        np.random.seed(self.seed)

        # Способности студентов θ ~ skew_norm
        self.theta = skewnorm.rvs(
            a=self._skew,
            loc=self._loc,
            scale=self._scale,
            size=self.n,
        )

        # IRT параметры
        a = np.clip(np.random.normal(1.7, 0.25, self.n), 0.5, 3.0)  # discrimination
        b = -self.content_quality * 2.85                              # difficulty (чем выше quality, тем легче)
        c = 0.15                                                       # guessing

        # Вероятность правильного ответа
        p_correct = c + (1 - c) / (1 + np.exp(-a * (self.theta - b)))
        self.S = np.random.binomial(1, p_correct)

        # Временной коэффициент и попытки
        self.T_ratio = np.clip(np.random.normal(1.0, 0.38, self.n), 0.35, 2.8)
        self.attempts = np.random.randint(1, 7, self.n)

        # Типы ошибок (зависят от качества контента)
        probs = self._error_probs()
        self.distractor_type = np.random.choice(
            ["conceptual", "operational", "procedural", "strategic"],
            self.n,
            p=probs,
        )

        # Флаг первой экспозиции (82% студентов видят контент впервые)
        self.first_exposure = np.random.choice(
            [True, False], self.n, p=[0.82, 0.18]
        )

    def _error_probs(self) -> List[float]:
        """
        Распределение типов ошибок.
        При низком quality доминируют conceptual/procedural ошибки.
        При высоком — operational (механические).
        """
        if self.error_bias == "conceptual":
            return [0.55, 0.20, 0.15, 0.10]
        elif self.error_bias == "operational":
            return [0.20, 0.50, 0.20, 0.10]
        elif self.error_bias == "procedural":
            return [0.15, 0.25, 0.50, 0.10]
        else:  # balanced — зависит от качества
            conceptual = max(0.25, 0.55 - self.content_quality * 0.6)
            operational = min(0.45, 0.20 + self.content_quality * 0.35)
            procedural = 0.20
            strategic = max(0.05, 1.0 - conceptual - operational - procedural)
            # Нормализуем на случай округлений
            total = conceptual + operational + procedural + strategic
            return [
                round(conceptual / total, 3),
                round(operational / total, 3),
                round(procedural / total, 3),
                round(strategic / total, 3),
            ]

    # ==================== ПУБЛИЧНЫЕ МЕТОДЫ ====================

    def update_quality(self, new_quality: float):
        """Обновляет качество контента и перегенерирует данные."""
        self.content_quality = np.clip(new_quality, 0.0, 1.0)
        self._generate()

    def get_trace_logs(self, artifact_id: str) -> List[TraceLog]:
        """Генерирует список TraceLog для сохранения в БД."""
        logs = []
        for i in range(self.n):
            logs.append(TraceLog(
                student_id          = f"student_{i:03d}",  # "student_000" ... "student_249"
                artifact_id         = artifact_id,
                attempts            = int(self.attempts[i]),
                is_correct          = bool(self.S[i]),
                time_spent_sec      = int(self.T_ratio[i] * 95),
                time_spent_on_q     = int(self.T_ratio[i] * 95),
                viewed_material_before = False,
                is_nav_back         = False,
                selected_error_type = (
                    ErrorType(self.distractor_type[i]) if not self.S[i] else None
                ),
                first_exposure      = bool(self.first_exposure[i]),
                timestamp         = datetime.utcnow(),
            ))
        return logs

    def compute_metrics(self) -> Dict:
        """
        Вычисляет метрики когорты аналитически (без обращения к БД).
        Используется для быстрой проверки симулятора.
        """
        K_t = np.where(
            self.T_ratio < 0.7, 0.6,
            np.where(self.T_ratio > 1.3, 0.8, 1.0)
        )
        M_j   = self.S * K_t / np.clip(self.attempts, 1, None)
        M_term = float(np.mean(M_j))
        E      = M_term / 0.8   # нормировка на D_target=0.8

        errors      = self.S == 0
        total_error = int(errors.sum())
        D_p = {}
        for et in ["conceptual", "operational", "procedural", "strategic"]:
            count   = int(((np.array(self.distractor_type) == et) & errors).sum())
            D_p[et] = round(count / total_error, 3) if total_error > 0 else 0.0

        return {
            "n_students":   self.n,
            "cohort_type":  self.cohort_type,
            "content_quality": self.content_quality,
            "M_term":       round(M_term, 3),
            "E":            round(E, 3),
            "E_fresh":      round(E * 0.95, 3),   # приближение для first_exposure
            "D_p":          D_p,
            "avg_attempts": round(float(self.attempts.mean()), 2),
            "accuracy":     round(float(self.S.mean()), 3),
            "theta_mean":   round(float(self.theta.mean()), 3),
            "theta_std":    round(float(self.theta.std()), 3),
        }

    def summary(self) -> str:
        """Текстовое резюме для логов."""
        m = self.compute_metrics()
        return (
            f"SyntheticCohort | n={m['n_students']} | type={m['cohort_type']} | "
            f"quality={m['content_quality']:.2f} | "
            f"accuracy={m['accuracy']:.2%} | M_term={m['M_term']:.3f} | E={m['E']:.3f}"
        )