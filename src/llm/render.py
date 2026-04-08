from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Dict, Any, Optional
import yaml

PROMPTS_DIR = Path("src/llm/prompts")
CONFIG_DIR = Path("config")
PROMPT_MODES_CONFIG = CONFIG_DIR / "prompt_modes.yaml"

env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(["j2"]),
    trim_blocks=True,
    lstrip_blocks=True
)


def render_template(template_name: str, context: Dict[str, Any]) -> str:
    template = env.get_template(template_name)
    return template.render(**context)


def load_prompt_modes_config() -> Dict[str, Any]:
    """Загружает конфигурацию режимов промптов из YAML."""
    if not PROMPT_MODES_CONFIG.exists():
        # Fallback на значения по умолчанию
        return {
            "prompt_modes": {
                "topics": {"mode": "full"},
                "terms": {"mode": "full"},
                "explanation": {"mode": "full"},
                "problem_example": {"mode": "min"},
                "test": {"mode": "min"},
            },
            "defaults": {
                "fallback_mode": "full",
                "allow_override": True,
            }
        }
    
    with open(PROMPT_MODES_CONFIG, encoding="utf-8") as f:
        return yaml.safe_load(f)


def select_prompt_template(
    params_type: str,
    prompt_mode: Optional[str] = None
) -> str:
    """
    Выбирает шаблон промпта на основе типа контента и режима (Full/Min).
    
    Args:
        params_type: Тип параметров ('topics', 'terms', 'explanation', 'problem_example', 'test')
        prompt_mode: Принудительный режим ('full', 'min' или None для авто-выбора)
    
    Returns:
        Имя файла шаблона Jinja2
    """
    # Маппинг типов параметров на ключи конфигурации
    type_mapping = {
        "ContentParams": "explanation",
        "TestParams": "test",
        "ProblemParams": "problem_example",
        "TopicsParams": "topics",
        "TermsParams": "terms",
    }
    
    config_key = type_mapping.get(params_type, params_type)
    
    # Загружаем конфигурацию
    config = load_prompt_modes_config()
    modes = config.get("prompt_modes", {})
    defaults = config.get("defaults", {})
    fallback_mode = defaults.get("fallback_mode", "full")
    
    # Определяем режим: принудительно или из конфига
    if prompt_mode and prompt_mode.lower() in ["full", "min"]:
        mode = prompt_mode.lower()
    elif config_key in modes:
        mode = modes[config_key].get("mode", fallback_mode)
    else:
        mode = fallback_mode
    
    # Маппинг на имена шаблонов
    template_map = {
        ("explanation", "full"): "explanation_adaptive.j2",
        ("explanation", "min"): "explanation_adaptive.j2",  # Для объяснений Min не используется
        ("test", "full"): "test_generate_adaptive.j2",
        ("test", "min"): "test_generate_min.j2",
        ("problem_example", "full"): "problem_example_adaptive.j2",
        ("problem_example", "min"): "problem_example_min.j2",
        ("topics", "full"): "topics_adaptive.j2",
        ("topics", "min"): "topics_adaptive.j2",  # Для тем Min не используется
        ("terms", "full"): "terms_adaptive.j2",
        ("terms", "min"): "terms_adaptive.j2",  # Для терминов Min не используется
    }
    
    template_name = template_map.get((config_key, mode))
    if not template_name:
        # Fallback на Full-версию
        fallback_map = {
            "explanation": "explanation_adaptive.j2",
            "test": "test_generate_adaptive.j2",
            "problem_example": "problem_example_adaptive.j2",
            "topics": "topics_adaptive.j2",
            "terms": "terms_adaptive.j2",
        }
        template_name = fallback_map.get(config_key, "explanation_adaptive.j2")
    
    return template_name

