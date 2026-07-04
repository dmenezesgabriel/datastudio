"""LangGraph node that selects only the tables relevant to the user's question."""

from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes._structured_output import invoke_structured

_SYSTEM_PROMPT = (
    "You are a SQL expert. Given a list of available table names and a question, "
    "return only the names of tables needed to answer the question. "
    "Return names exactly as given. "
    "Earlier conversation turns, when present, are context for resolving references — "
    "select tables for the CURRENT question."
)


class _TableSelectionOutput(BaseModel):
    tables: list[str]


class SelectTables:
    """Node that selects only the tables relevant to the question before schema fetching.

    This is the schema-linking stage and the pipeline's main scalability lever:
    get_schema and generate_sql only ever see the selected tables, so the prompt
    size stays flat as the catalog grows from a handful of tables to the many a
    warehouse like AWS Athena holds. It always runs — table count is exactly when
    pruning matters, so it is never skipped.

    Example:
        node = SelectTables(chat_model)
        result = node({"tables": ["events", "customers"], "question": "How many events?"})
        # result == {"tables": ["events"]}
    """

    def __init__(self, chat_model: BaseChatModel) -> None:
        """Wire the chat model as a structured-output runnable."""
        self._model: Runnable[LanguageModelInput, _TableSelectionOutput] = cast(
            Runnable[LanguageModelInput, _TableSelectionOutput],
            chat_model.with_structured_output(_TableSelectionOutput),
        )

    def __call__(self, state: ChatState) -> dict[str, list[str]]:
        """Select the tables relevant to the question in state."""
        human_content = f"Tables: {state['tables']}\n\nQuestion: {state['question']}"
        messages = [
            SystemMessage(content=_SYSTEM_PROMPT),
            *state["history"],
            HumanMessage(content=human_content),
        ]
        result = invoke_structured(self._model, messages, "select_tables")
        if result is None:
            # Malformed output: keep every table (safe superset) so get_schema still runs.
            return {"tables": state["tables"]}
        valid = [t for t in result.tables if t in state["tables"]]
        # fallback: if model hallucinated all names, use the full list
        return {"tables": valid or state["tables"]}
