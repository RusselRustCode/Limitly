import logging
import re
from json_repair import repair_json
from typing import Union, Any
from fastapi import HTTPException
from langchain_core.messages import HumanMessage
from langchain_gigachat.chat_models import GigaChat
from langchain_core.output_parsers import PydanticOutputParser
from src.core.models import (
    ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams,
    LLMGeneratedContent,
    ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent
)
from src.llm.templates import (
    get_explanation_long_content,
    get_test_prompt,
    get_topic_prompt,
    get_term_prompt,
    get_problem_example_prompt
)

from src.core.models import *

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


try: 
    chat = GigaChat(
        credentials="MDFlNjcwMzctNDIzOS00YWIyLTljNzUtOTZlMjI5NjJlZTM3OjlkOWY3ZGExLTIzNmUtNDViYS1hNTJjLTNjMzRlN2ZkZDg5NQ==",
        verify_ssl_certs=False,
        timeout=30
    )
    logger.info("GigaChat инициализирован")
except Exception as e:
    raise logger.error(f"Error: {e}")


ValidParams = Union[ContentParams, TestParams, TopicsParams, TermsParams, ProblemParams]

ValidContents = Union[ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent]


PROMPT_AND_PARSER_MAP = {
    ContentParams: (get_explanation_long_content, PydanticOutputParser(pydantic_object=ExplanationContent)),
    TestParams: (get_test_prompt, PydanticOutputParser(pydantic_object=TestContent)),
    TopicsParams: (get_topic_prompt, PydanticOutputParser(pydantic_object=TopicContent)),
    TermsParams: (get_term_prompt, PydanticOutputParser(pydantic_object=TermContent)),
    ProblemParams: (get_problem_example_prompt, PydanticOutputParser(pydantic_object=ProblemContent)),
}

PARAMS_TO_CONTENT_MODEL = {
    ContentParams: ExplanationContent,
    TestParams: TestContent,
    TopicsParams: TopicContent,
    TermsParams: TermContent,
    ProblemParams: ProblemContent,
}


def extract_json_block(text: str) -> str:
    match = re.search(r"```(?:json)?\s*({.*})\s*```", text, re.DOTALL)
    if match:
        return match.group(1)
    # Если нет markdown — ищем первый { ... }
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end > start:
        return text[start:end + 1]
    return text.strip()

def extract_input_vars(params: ValidParams) -> Dict[str, Any]:
    if isinstance(params, ContentParams):
        return {
            "term_name": params.term_name,
            "subject_specialization": params.subject_specialization,
            "target_audience": params.target_audience.value,
            "language_style": params.language_style.value,
            "explanation_len": params.explanation_len.value,
            "example_type": params.example_type.value,
            "usage_toggle": params.usage_toggle.value,
            "historical_content": params.historical_content.value
        }
    elif isinstance(params, TestParams):
        if params.question_format == QuestionFormat.MULTIPLE_CHOICE:
            choice_description = f"{params.number_of_choices} вариантов (несколько могут быть правильными)"
        elif params.question_format == QuestionFormat.SINGLE_CHOICE:
            choice_description = f"{params.number_of_choices} вариантов (1 правильный, {params.number_of_choices - 1} дистракторов)"
        else:  #открытый вопрос
            choice_description = "Открытый вопрос — без вариантов ответа"
        return {
            "term_name": params.term_name,
            "question_format": params.question_format.value,
            "cognitive_level": params.cognitive_level.value,
            "distractor_error_type": params.distractor_error_type.value,
            "number_of_choices": choice_description,
            "difficulty_level": params.difficulty_level.value,
            "context_requirement": params.context_requirement.value
        }
    elif isinstance(params, TopicsParams):
        return {
            "subject_name": params.subject_name,
            "number_of_topics": str(params.number_of_topics)
        }
    elif isinstance(params, TermsParams):
        return {
            "topic_title": params.topic_title,
            "number_of_terms": str(params.number_of_terms)         
        }    
    elif isinstance(params, ProblemParams):
        return {
            "term_name": params.term_name,
            "subject_specialization": params.subject_specialization,
            #explanation_body???
        }
    else:
        raise ValueError(f"Неизвестные тип параметров: {type(params)}")

async def generate_llm_content(params: ValidParams) -> LLMGeneratedContent:
    param_type = type(params)
    
    if param_type not in PROMPT_AND_PARSER_MAP:
        raise HTTPException(
            status_code=500,
            detail=f"Не поддерживаемый тип параметров: {param_type.__name__}"
        )
    
    prompt_func, parser = PROMPT_AND_PARSER_MAP[param_type] #убрать к хуям парсер, нерабочее говно!!!
    prompt_template = await prompt_func()
    
    input_vars = extract_input_vars(params)
    
    try:
        prompt_text = prompt_template.format(**input_vars)
    except KeyError as e:
        missing = e.args[0]
        logger.error(f"Отсутствует переменная в промпте: {missing}. Доступные: {list(input_vars.keys())}")
        raise HTTPException(
            status_code=500,
            detail=f"Ошибка формирования промпта: не хватает переменной '{missing}'"
        )
    
    logger.debug(f"Финальный промпт:\n{prompt_text[:500]}...")
    
    messages = [HumanMessage(content=prompt_text)]
    try:
        response = chat.invoke(messages)
        raw_output = response.content
        logger.info(f"Сырой ответ LLM (первые 300 символов): {raw_output[:300]}...")
    except Exception as e:
        logger.error(f"Ошибка вызова LLM: {e}")
        raise HTTPException(status_code=500, detail="Ошибка при обращении к LLM")
    
    try:
        json_str = extract_json_block(raw_output)

        # Парсим через json5 (терпимо к \l, \t и т.д.)
        data = repair_json(json_str, return_objects=True)
        if not isinstance(data, dict):
            raise ValueError("Результат не является объектом")
        
        reasoning = data.pop("reasoning")

        content_model = PARAMS_TO_CONTENT_MODEL[param_type]
        parsed_content = content_model.model_validate(data)

    except Exception as e:
        print("=== ОШИБКА ПАРСИНГА ===")
        print("Сырой ответ LLM:")
        print(raw_output)
        print("=== КОНЕЦ ОТВЕТА ===")
        raise HTTPException(status_code=500, detail="LLM вернул ответ в неверном формате")
    
    return LLMGeneratedContent(
        reasoning=parsed_content.reasoning,
        content=parsed_content
    )

async def main():
    #тест
    # params = TestParams(
    #     term_name="Интегрирования",
    #     question_format=QuestionFormat.MULTIPLE_CHOICE,
    #     cognitive_level=CognitiveLevel.ANALYSIS,
    #     distractor_error_type=DistractorErrorType.CONCEPTUAL,
    #     number_of_choices=NumberOfChoices.MEDIUM,
    #     context_requirement=ContextRequirement.SCENARIO,
    #     difficulty_level=DifficultyLevel.MEDIUM  
    # )
    
    topics_params = TopicsParams(
        subject_name="Матанализ 1 курс",
        number_of_topics=7
    )
    
    term_params = TermsParams(
        topic_title="Пределы",
        number_of_terms=3
    )
    
    problem = ProblemParams(
        term_name="Предел функции",
        subject_specialization="Физика",
    )
    
    content = ContentParams(
        term_name="Предел функции",
        target_audience=TargetAudience.NON_MATHEMATICIANS,
        usage_toggle=UsageToggle.YES,
        historical_content=UsageToggle.NO,
        language_style=LanguageStyle.CASUAL,
        explanation_len=ExplanationLenght.MEDIUM,
        example_type=ExampleType.REAL_CASE
    )
    result = await generate_llm_content(content)
    print("Reasoning:", result.reasoning[:200] + "...")
    print("---------------------")
    print("Question:", result.content.explanation_body)

    
    
if __name__ == "__main__":
    import asyncio
    asyncio.run(main())





