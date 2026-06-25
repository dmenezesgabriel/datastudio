from typing import Literal, cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState

_SYSTEM_PROMPT = (
    "Classify the question as 'simple' or 'complex'.\n\n"
    "'simple': Any question answerable with a SINGLE SQL query, no matter how intricate. "
    "This includes multi-period comparisons (use CASE WHEN or subqueries within one statement), "
    "conditional aggregations, percentage calculations, JOINs, GROUP BY, and year-over-year "
    "differences computed inside SQL.\n\n"
    "'complex': ONLY questions that genuinely require querying two or more INDEPENDENT datasets "
    "(different databases or systems) that cannot be joined, and then combining results "
    "with arithmetic outside of SQL. Extremely rare.\n\n"
    "Default to 'simple'. Almost every analytical question over a single database is 'simple'."
)


class _ComplexityOutput(BaseModel):
    complexity: Literal["simple", "complex"]


class ClassifyQuery:
    """Node that classifies a question as simple or complex before routing.

    Simple questions use the standard pipeline. Complex questions are routed to
    the decomposition path (decompose_query → synthesize_answer).

    Example:
        node = ClassifyQuery(chat_model)
        result = node({"question": "How many trips?"})
        # result == {"complexity": "simple"}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._model: Runnable[LanguageModelInput, _ComplexityOutput] = cast(
            Runnable[LanguageModelInput, _ComplexityOutput],
            chat_model.with_structured_output(_ComplexityOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=state["question"]),
        ]
        result: _ComplexityOutput = self._model.invoke(messages)
        return {"complexity": result.complexity}
