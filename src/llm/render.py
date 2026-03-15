from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
from typing import Dict, Any

PROMPTS_DIR = Path("src/llm/prompts")

env = Environment(
    loader=FileSystemLoader(PROMPTS_DIR),
    autoescape=select_autoescape(["j2"]),
    trim_blocks=True,
    lstrip_blocks=True
)


def render_template(template_name: str, context: Dict[str, Any]) -> str:
    template = env.get_template(template_name)
    return template.render(**context)

