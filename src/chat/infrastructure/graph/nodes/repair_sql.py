"""LangGraph node that repairs failed SQL queries with LLM assistance."""

from collections.abc import Mapping
from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.observability import step_tag
from shared.application.ports.sql_engine_port import SqlEnginePort

MAX_REPAIR_ATTEMPTS = 2
"""Number of times repair_sql may regenerate a query before the graph gives up."""

_SYSTEM_PROMPT = (
    "You are a SQL expert fixing a failed DuckDB query. Given the schema, the "
    "question, the previous SQL, and the database error, return a corrected "
    "single DuckDB-compatible SELECT query that resolves the specific error."
)

_CANDIDATE_HINTS = (
    "Use the most direct correction of the previous query.",
    "Reconsider the approach: use CASE expressions or a subquery if it helps.",
    "Re-check every column name and type against the schema before answering.",
)


class _SqlOutput(BaseModel):
    sql: str


class RepairSql:
    """Recovers from a failed SQL execution by regenerating the query.

    Each attempt rewrites the query from the schema, question, previous SQL and
    error message. On the final allowed attempt it generates several candidates
    and keeps the first that executes — extra effort spent only on hard cases,
    since the happy path never enters this node.

    Example:
        node = RepairSql(chat_model, sql_engine)
        node({"sql_error": "Binder Error: ...", "repair_attempts": 0, ...})
        # → {"sql_query": "<corrected>", "repair_attempts": 1}
    """

    def __init__(
        self,
        chat_model: BaseChatModel,
        sql_engine: SqlEnginePort,
        max_attempts: int = MAX_REPAIR_ATTEMPTS,
        candidate_count: int = 3,
    ) -> None:
        """Wire the model, engine, and repair parameters."""
        self._model: Runnable[LanguageModelInput, _SqlOutput] = cast(
            Runnable[LanguageModelInput, _SqlOutput],
            chat_model.with_structured_output(_SqlOutput).with_config(
                {"tags": [step_tag("repair_sql")]}
            ),
        )
        self._engine = sql_engine
        self._max_attempts = max_attempts
        self._candidate_count = candidate_count

    def __call__(self, state: ChatState) -> Mapping[str, object]:
        """Attempt to fix the failed SQL and return the corrected query."""
        attempt = self._current_attempts(state) + 1
        if attempt < self._max_attempts:
            sql = self._repair_once(state, _CANDIDATE_HINTS[0])
            return {"sql_query": sql, "repair_attempts": attempt}
        return {"sql_query": self._best_candidate(state), "repair_attempts": attempt}

    def _best_candidate(self, state: ChatState) -> str:
        """Generate candidates one at a time and return the first that executes cleanly.

        Stops early on success so failing cases pay for at most one extra LLM call
        beyond what already executed successfully.
        """
        first: str | None = None
        for hint in self._hints():
            sql = self._repair_once(state, hint)
            if first is None:
                first = sql
            if self._executes(sql):
                return sql
        return first or ""

    def _repair_once(self, state: ChatState, hint: str) -> str:
        return self._model.invoke(self._build_messages(state, hint)).sql

    def _hints(self) -> tuple[str, ...]:
        return _CANDIDATE_HINTS[: self._candidate_count]

    def _executes(self, sql: str) -> bool:
        try:
            self._engine.execute_query(sql)
            return True
        except Exception:  # noqa: BLE001 — a failing candidate is simply rejected
            return False

    @staticmethod
    def _current_attempts(state: ChatState) -> int:
        attempts = cast(dict[str, object], state).get("repair_attempts")
        return attempts if isinstance(attempts, int) else 0

    @staticmethod
    def _build_messages(state: ChatState, hint: str) -> list[BaseMessage]:
        state_dict = cast(dict[str, object], state)
        human = (
            f"Schema:\n{state_dict.get('schema', '')}\n\n"
            f"Question: {state_dict.get('question', '')}\n\n"
            f"Previous SQL:\n{state_dict.get('sql_query', '')}\n\n"
            f"Error: {state_dict.get('sql_error', '')}\n\n{hint}"
        )
        return [SystemMessage(content=_SYSTEM_PROMPT), HumanMessage(content=human)]
