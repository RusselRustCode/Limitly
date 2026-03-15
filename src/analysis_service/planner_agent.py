"""
PlannerAgentV2 — современная версия Агента-Планировщика.

Загружает правила из planner_rules.yaml и возвращает директивы.
Больше не генерирует огромные системные промпты (это делает external_api.py + .j2 шаблоны).
"""
from pathlib import Path
import yaml 
from typing import Dict, List

from src.core.models import MlAnalysisResult, AdaptationDirective, AdaptationStrategy

CONFIG_PATH = Path("config/planner/planner_rules.yaml")

class PlannerAgent:
    
    def __init__(self):
        self.config = self.load_config()
        self.thresholds = self.config['thresholds']
        self.rules = self.config['rules']
        self.global_settings = self.config['global']
        self.fallback = self.config['fallback']
        
        
    def load_config(self):
        with open(CONFIG_PATH, encoding='utf-8') as f:
            return yaml.safe_load(f)
        
        
    def evaluate_condition(self, condition: str, metrics: Dict) -> bool:
        safe_globals = {"__builtins__": {}}
        eval(condition, safe_globals, {**self.thresholds, **metrics})        
        
        
    def get_derectives(self, metrics: Dict) -> List[AdaptationDirective]:
        """
        Главный метод: возвращает список директив на основе метрик.
        Автоматически использует E_fresh если включено в настройках.
        """
        
        if self.global_settings.get("use_fresh_only", True):
            if "efficiency_fresh" in metrics and metrics["efficiency_fresh"] is not None:
                metrics = metrics.copy()
                metrics["efficiency_score"] = metrics["efficiency_fresh"]

        active = []
        for rule in self.rules:
            if self.evaluate_condition(rule["condition"], metrics):
                active.append(rule)

        active.sort(key=lambda r: r["priority"])
        selected = active[:self.global_settings.get("max_directives_per_iteration", 3)]

        if not selected:
            selected = [self.fallback]

        return [self._create_directive(r) for r in selected]  
    
    def create_directive(self, rule: Dict) -> AdaptationDirective:
        return AdaptationDirective(
            strategy=AdaptationStrategy(rule["directive"]["action"]),
            trigger_metric=rule.get("trigger_metric", "M_term"),
            trigger_value=0.0,                    # можно заполнить позже
            directive_text=rule["directive"]["insight"],
            priority=rule["priority"]
        )   