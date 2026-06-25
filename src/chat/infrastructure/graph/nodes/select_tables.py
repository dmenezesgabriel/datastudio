from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState

_SYSTEM_PROMPT = (
    "You are a SQL expert. Given a list of available table names and a question, "
    "return only the names of tables needed to answer the question. "
    "Return names exactly as given."
)


class _TableSelectionOutput(BaseModel):
    tables: list[str]


class SelectTables:
    """Node that selects only the tables relevant to the question before schema fetching.

    Reduces generate_sql input tokens by filtering out irrelevant tables before
    get_schema fetches full DDL.

    Example:
        node = SelectTables(chat_model)
        result = node({"tables": ["movies", "cars", "nyc_taxi"], "question": "How many films?"})
        # result == {"tables": ["movies"]}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._model: Runnable[LanguageModelInput, _TableSelectionOutput] = cast(
            Runnable[LanguageModelInput, _TableSelectionOutput],
            chat_model.with_structured_output(_TableSelectionOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, list[str]]:
        human_content = f"Tables: {state['tables']}\n\nQuestion: {state['question']}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=human_content),
        ]
        result: _TableSelectionOutput = self._model.invoke(messages)
        valid = [t for t in result.tables if t in state["tables"]]
        # fallback: if model hallucinated all names, use the full list
        return {"tables": valid or state["tables"]}
