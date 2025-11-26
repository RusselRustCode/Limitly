from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.core.models import ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent
import os


def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


async def get_explanation_long_content() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=ExplanationContent)
    return PromptTemplate(
        template=_load_prompt("explanation_long.txt"),
        input_variables=[
            "term_name", "target_audience", "language_style", "explanation_len",
            "example_type", "usage_toggle", "historical_content"
        ],
        partial_variables={"format_instrusctions": parser.get_format_instructions()}
    )
    
async def get_test_prompt() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=TestContent)
    return PromptTemplate(
        template=_load_prompt("test_generate.txt"),
        input_variables=["term_name", "question_format",
            "cognitive_level", "distractor_error_type", "number_of_choices",
            "difficulty_level", "context_requirement"],
        partial_variables={"format_instrusctions": parser.get_format_instructions()}
    )
    
    
async def get_topic_prompt() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=TopicContent)
    return PromptTemplate(
        template=_load_prompt("topcis.txt"),
        input_variables=["subjetc_t=name", "number_of_topics"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
async def get_term_prompt() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=TermContent)
    return PromptTemplate(
        template=_load_prompt("terms.txt"),
        input_variables=["topic_title", "number_of_terms"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )
    
async def get_problem_example_prompt() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=ProblemContent)
    return PromptTemplate(
        template=_load_prompt("problem_example.txt"),
        input_variables=["term_name", "subject_specialization"],
        partial_variables={"format_instructions": parser.get_format_instructions()}
    )