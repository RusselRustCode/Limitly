"""
Модуль адаптивной генерации контента.
Единая точка входа для всех типов учебных материалов.
"""

import logging
import re
import json
from json_repair import repair_json
from typing import Union, Optional, List

from src.core.models import (
    ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams,
    LLMGeneratedContent,
    ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent,
)
from src.core.exceptions import GenerationError, ValidationError
from src.llm.client import LLMClient, LLMModel, ModelPreset
from src.llm.render import render_template, select_prompt_template
from src.llm.profiles import get_profile

logger = logging.getLogger(__name__)

_CONTENT_MODEL_MAP = {
    ContentParams: ExplanationContent,
    TestParams:    TestContent,
    ProblemParams: ProblemContent,
    TopicsParams:  TopicContent,
    TermsParams:   TermContent,
}

_DEFAULT_MODEL_BY_CONTENT = {
    ContentParams: ModelPreset.DEFAULT,
    TestParams:    ModelPreset.FAST_ACCURATE,
    ProblemParams: ModelPreset.FAST_ACCURATE,
    TopicsParams:  ModelPreset.LIGHT,
    TermsParams:   ModelPreset.LIGHT,
}


async def generate_adaptive_content(
    params:             Union[ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams],
    version_to:         int                  = 1,
    old_content:        str                  = "",
    imaginary_gradient: Optional[List[dict]] = None,
    related_terms:      Optional[List[str]]  = None,
    profile_id:         Optional[str]        = None,
    prompt_mode:        Optional[str]        = None,
    model:              Optional[LLMModel]   = None,
    temperature:        float                = 0.7,
    max_tokens:         int                  = 8000,
) -> LLMGeneratedContent:

    final_profile_id = profile_id or getattr(params, "profile_id", "engineer")
    profile = get_profile(final_profile_id)
    if not profile:
        raise ValidationError(f"Профиль '{final_profile_id}' не найден в profiles.yaml")

    selected_model = model or _DEFAULT_MODEL_BY_CONTENT.get(type(params), ModelPreset.DEFAULT)

    context = {
        "term_name":              getattr(params, "term_name", ""),
        "topic_title":            getattr(params, "topic_title", ""),
        "subject_name":           getattr(params, "subject_name", ""),
        "subject_specialization": getattr(params, "subject_specialization", "математика"),
        "number_of_topics":       getattr(params, "number_of_topics", 5),
        "number_of_terms":        getattr(params, "number_of_terms", 5),
        "question_format":        getattr(params, "question_format", ""),
        "cognitive_level":        getattr(params, "cognitive_level", ""),
        "distractor_error_type":  getattr(params, "distractor_error_type", ""),
        "number_of_choices":      getattr(params, "number_of_choices", 4),
        "difficulty_level":       getattr(params, "difficulty_level", ""),
        "profile":                profile,
        "profile_id":             final_profile_id,
        "related_terms":          related_terms or [],
        "task": {
            "version_to":         version_to,
            "version_from":       max(version_to - 1, 0),
            "imaginary_gradient": imaginary_gradient or [],
        },
        "old_content": old_content,
        "parameters":  params.model_dump() if hasattr(params, "model_dump") else {},
    }

    params_type   = type(params).__name__
    template_name = select_prompt_template(params_type, prompt_mode)

    logger.info(
        f"[generate] model={selected_model.value} | "
        f"template={template_name} | profile={final_profile_id} | v{version_to}"
    )

    try:
        prompt_text = render_template(template_name, context)
    except Exception as e:
        logger.error(f"[generate] ошибка рендеринга {template_name}: {e}", exc_info=True)
        raise GenerationError(f"Ошибка формирования промпта: {e}")

    client     = LLMClient.get_instance()
    raw_output = client.invoke(
        prompt      = prompt_text,
        model       = selected_model,
        temperature = temperature,
        max_tokens  = max_tokens,
    )

    return _parse_response(raw_output, params)


def _parse_response(
    raw_output: str,
    params:     Union[ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams],
) -> LLMGeneratedContent:
    try:
        json_str = _extract_json(raw_output)
        repaired = repair_json(json_str, return_objects=True)

        if isinstance(repaired, list):
            data = next((i for i in repaired if isinstance(i, dict)), {})
        elif isinstance(repaired, dict):
            data = repaired
        else:
            data = {}

        target_model  = _CONTENT_MODEL_MAP[type(params)]
        expected_keys = set(target_model.model_fields.keys())
        reasoning     = data.pop("reasoning", "")
        filtered      = {k: v for k, v in data.items() if k in expected_keys}

        if "explanation_body" in filtered and isinstance(filtered["explanation_body"], dict):
            filtered["explanation_body"] = json.dumps(
                filtered["explanation_body"], ensure_ascii=False
            )

        for field_name, field_info in target_model.model_fields.items():
            if field_name not in filtered and field_info.default is not None:
                filtered[field_name] = field_info.default

        parsed = target_model.model_validate(filtered)
        logger.info(f"[generate] парсинг OK | type={type(params).__name__}")
        return LLMGeneratedContent(reasoning=reasoning, content=parsed)

    except Exception as e:
        logger.error(
            f"[generate] ошибка парсинга JSON: {e}\n"
            f"RAW (first 500): {raw_output[:500]}",
            exc_info=True,
        )
        raise GenerationError(f"Не удалось распарсить ответ LLM: {e}")


def _extract_json(text: str) -> str:
    match = re.search(r"```(?:json)?\s*({)", text, re.DOTALL)
    if match:
        start = match.start(1)
        depth = 0
        for i in range(start, len(text)):
            if text[i] == "{":
                depth += 1
            elif text[i] == "}":
                depth -= 1
                if depth == 0:
                    return text[start: i + 1]
        end = re.search(r"```", text[start:])
        return text[start: start + end.start()] if end else text[start:]

    start = text.find("{")
    end   = text.rfind("}")
    if start != -1 and end > start:
        return text[start: end + 1]
    return text.strip()