from langchain_core.prompts import PromptTemplate
import os


def _load_prompt(filename: str) -> str:
    path = os.path.join(os.path.dirname(__file__), "prompts", filename)
    with open(path, "r", encoding="utf-8") as f:
        return f.read().strip()


async def get_explanation_long_content() -> PromptTemplate:
    return PromptTemplate(
        template=_load_prompt("explanation_long.txt"),
        input_variables=[
            "term_name", "target_audience", "language_style", "explanation_len",
            "example_type", "usage_toggle", "historical_content"
        ]
    )
    
async def get_test_prompt() -> PromptTemplate:
    return PromptTemplate(
        template=_load_prompt("test_generate.txt"),
        input_variables=["term_name", "question_format",
            "cognitive_level", "distractor_error_type", "number_of_choices",
            "difficulty_level", "context_requirement"]
    )
    
    
async def get_topic_prompt() -> PromptTemplate:
    return PromptTemplate(
        template=_load_prompt("topics.txt"),
        input_variables=["subject_name", "number_of_topics"]
    )
    
async def get_term_prompt() -> PromptTemplate:
    return PromptTemplate(
        template=_load_prompt("terms.txt"),
        input_variables=["topic_title", "number_of_terms"]
    )
    
async def get_problem_example_prompt() -> PromptTemplate:
    return PromptTemplate(
        template=_load_prompt("problem_example.txt"),
        input_variables=["term_name", "subject_specialization"]
    )