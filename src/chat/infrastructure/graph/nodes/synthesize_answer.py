from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.sub_query_result import SubQueryResult

_SYSTEM_PROMPT = (
    "You are a helpful data analyst. Given a question and a set of sub-questions with their "
    "SQL results, compute the final answer. Perform any arithmetic needed (e.g., differences, "
    "percentages) and provide a concise natural language response."
)


class _AnswerOutput(BaseModel):
    answer: str


class SynthesizeAnswer:
    """Node that combines sub-query results into a final natural language answer.

    Receives sub_results populated by DecomposeQuery and produces the response
    field, bypassing the standard format_response node.

    Example:
        node = SynthesizeAnswer(chat_model)
        result = node({"question": "How much did MPG improve?", "sub_results": [...]})
        # result == {"response": "Fuel efficiency improved by 10.6 MPG."}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._model: Runnable[LanguageModelInput, _AnswerOutput] = cast(
            Runnable[LanguageModelInput, _AnswerOutput],
            chat_model.with_structured_output(_AnswerOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, str]:
        parts = [f"Original question: {state['question']}\n"]
        sub_results: list[SubQueryResult] = state["sub_results"]
        for sub in sub_results:
            parts.append(f"Sub-question: {sub.question}")
            parts.append(f"SQL: {sub.sql}")
            parts.append(f"Result:\n{sub.result.to_markdown_table()}")
        human_content = "\n".join(parts)
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        result: _AnswerOutput = self._model.invoke(messages)
        return {"response": result.answer}
