from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import PydanticOutputParser
from src.core.models import ExplanationContent, TestContent, TopicContent, TermContent, ProblemContent


async def get_explanation_content() -> PromptTemplate:
    parser = PydanticOutputParser(pydantic_object=ExplanationContent)
    return PromptTemplate(
        template="",
        input_variables=[],
        partial_variables={"format_instrusctions": parser.get_format_instructions()}
    )