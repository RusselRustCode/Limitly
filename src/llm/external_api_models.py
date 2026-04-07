import logging
import re
import json
from json_repair import repair_json
from typing import Union, Any, Optional, List
from fastapi import HTTPException
from langchain_core.messages import HumanMessage, AIMessage
from openai import OpenAI

from config.settings import settings
from src.core.models import (
    ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams,
    LLMGeneratedContent,
    ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent
)

from src.llm.render import render_template          # Jinja2 рендерер
from src.llm.profiles import get_profile            # загрузка профилей
from src.analysis_service.planner_agent import PlannerAgent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

try:
    client = OpenAI(
        api_key=settings.RUSGPT_API_KEY.strip(),
        base_url="https://rus-gpt.com/api/v1",
    )
    logger.info("Qwen (rus-gpt.com) API инициализирован")
except Exception as e:
    logger.error(f"Ошибка инициализации Qwen API: {e}")
    raise


async def generate_adaptive_content_qwen(
    params: Union[ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams],
    version_to: int = 1,
    old_content: str = "",
    imaginary_gradient: Optional[List[dict]] = None,
    related_terms: Optional[List[str]] = None,
    profile_id: Optional[str] = None
) -> LLMGeneratedContent:
    """
    Универсальная адаптивная генерация через Qwen API.
    Теперь profile_id — главный переключатель. Всё остальное берётся из profiles.yaml.
    """
    # Приоритет: если передали profile_id в параметрах — используем его
    final_profile_id = profile_id or getattr(params, "profile_id", "engineer")

    profile = get_profile(final_profile_id)
    if not profile:
        raise HTTPException(status_code=400, detail=f"Профиль '{final_profile_id}' не найден в profiles.yaml")

    # Формируем контекст — минимум дублирования
    context = {
        "term_name": getattr(params, "term_name", ""),
        "topic_title": getattr(params, "topic_title", ""),
        "subject_name": getattr(params, "subject_name", ""),
        "subject_specialization": getattr(params, "subject_specialization", "математика"),

        "profile": profile,                    
        "profile_id": final_profile_id,

        "related_terms": ", ".join(related_terms or []),

        "task": {
            "version_to": version_to,
            "version_from": version_to - 1 if version_to > 1 else 0,
            "imaginary_gradient": imaginary_gradient or []
        },
        "old_content": old_content,

        # Параметры модели оставляем только для совместимости старых шаблонов
        "parameters": params.model_dump() if hasattr(params, "model_dump") else {}
    }

    # Выбор шаблона
    template_map = {
        ContentParams: "explanation_adaptive.j2",
        TestParams:    "test_generate_adaptive.j2",
        ProblemParams: "problem_example_adaptive.j2",
        TopicsParams:  "topics_adaptive.j2",
        TermsParams:   "terms_adaptive.j2"
    }
    template_name = template_map.get(type(params))
    if not template_name:
        raise HTTPException(status_code=400, detail=f"Неизвестный тип параметров: {type(params)}")

    # Рендерим промпт
    try:
        prompt_text = render_template(template_name, context)
    except Exception as e:
        logger.error(f"Ошибка рендеринга {template_name}: {e}")
        raise HTTPException(status_code=500, detail="Ошибка формирования промпта")

    # Вызов LLM
    messages = [{"role": "user", "content": prompt_text}]
    try:
        response = client.chat.completions.create(
            model="qwen/qwen3-next-80b-a3b-instruct",
            messages=messages,
            temperature=0.7,
            max_tokens=8000
        )
        raw_output = response.choices[0].message.content
    except Exception as e:
        logger.error(f"Ошибка Qwen API: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обращении к LLM")

    # Отладка: проверяем длину ответа
    logger.info(f"=== RAW OUTPUT LENGTH: {len(raw_output)} chars ===")

    # Парсинг
    try:
        json_str = extract_json_block(raw_output)
        # repair_json поддерживает multiline строки по умолчанию
        repaired = repair_json(json_str, return_objects=True)

        # repair_json может вернуть список или None — нормализуем в словарь
        if isinstance(repaired, list):
            # Если вернулся список, пытаемся найти в нём словарь с данными
            data = next((item for item in repaired if isinstance(item, dict)), {})
        elif isinstance(repaired, dict):
            data = repaired
        else:
            data = {}

        model_map = {
            ContentParams: ExplanationContent,
            TestParams: TestContent,
            ProblemParams: ProblemContent,
            TopicsParams: TopicContent,
            TermsParams: TermContent
        }

        # Отладочный вывод
        logger.info(f"=== PARSED DATA KEYS (до фильтрации): {list(data.keys()) if data else 'EMPTY'} ===")
        logger.info(f"=== RAW JSON (first 500): {json_str[:500]} ===")

        # Извлекаем reasoning ДО фильтрации (он в родительской модели LLMGeneratedContent)
        reasoning = data.get("reasoning", "")

        # Фильтруем только ожидаемые ключи модели контента
        target_model = model_map[type(params)]
        expected_keys = set(target_model.model_fields.keys())
        filtered_data = {k: v for k, v in data.items() if k in expected_keys}

        # Логируем лишние ключи если есть
        extra_keys = set(data.keys()) - expected_keys
        if extra_keys:
            logger.info(f"=== ОТБРОШЕНЫ ЛИШНИЕ КЛЮЧИ (ожидаемо reasoning): {extra_keys} ===")

        data = filtered_data

        # Отладка: проверяем что в explanation_body
        if "explanation_body" in data:
            # Если explanation_body — объект (dict), сериализуем в JSON строку
            if isinstance(data["explanation_body"], dict):
                data["explanation_body"] = json.dumps(data["explanation_body"], ensure_ascii=False)
            logger.info(f"=== explanation_body type: {type(data['explanation_body']).__name__} ===")
        else:
            logger.error("=== НЕТ explanation_body В ДАННЫХ! ===")

        # Гарантируем наличие всех обязательных полей с дефолтами
        for field_name, field_info in target_model.model_fields.items():
            if field_name not in data and field_info.default is not None:
                data[field_name] = field_info.default

        parsed_content = target_model.model_validate(data)

    except Exception as e:
        logger.error("Ошибка парсинга JSON")
        print("=== СЫРОЙ ОТВЕТ (первые 1500 символов) ===")
        print(raw_output[:1500])
        print("\n=== ПОСЛЕДНИЕ 500 СИМВОЛОВ ===")
        print(raw_output[-500:])
        raise HTTPException(status_code=500, detail=f"Неверный JSON: {str(e)}")

    return LLMGeneratedContent(
        reasoning=reasoning,
        content=parsed_content
    )


def extract_json_block(text: str) -> str:
    """
    Извлекает JSON из markdown-блока или сырого текста.
    Улучшенная версия с подсчётом скобок для обрезанного JSON.
    """
    # Пытаемся найти markdown-блок
    match = re.search(r"```(?:json)?\s*({)", text, re.DOTALL)
    if match:
        start = match.start(1)
        # Ищем закрывающую скобку с подсчётом вложенности
        depth = 0
        for i in range(start, len(text)):
            if text[i] == '{':
                depth += 1
            elif text[i] == '}':
                depth -= 1
                if depth == 0:
                    return text[start:i + 1]
        # Если не нашли закрывающую — берём до конца блока
        end_match = re.search(r"```", text[start:])
        if end_match:
            return text[start:start + end_match.start()]
        return text[start:]

    # Без markdown — ищем первую и последнюю скобку
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text.strip()
