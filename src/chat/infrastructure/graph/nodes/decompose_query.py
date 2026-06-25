from typing import cast

from langchain_core.language_models import BaseChatModel
from langchain_core.language_models.base import LanguageModelInput
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import Runnable
from pydantic import BaseModel

from chat.domain.value_objects.chat_state import ChatState
from chat.domain.value_objects.sub_query_result import SubQueryResult
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from shared.application.ports.sql_engine_port import SqlEnginePort

_DECOMPOSE_PROMPT = (
    "You are a SQL expert. Break the question into 2–3 simpler sub-questions "
    "that can each be answered with a single SQL aggregation. "
    "Return only the sub-questions as a list."
)


class _DecompositionOutput(BaseModel):
    sub_questions: list[str]


class DecomposeQuery:
    """Node that breaks a complex question into sub-questions and executes each.

    Runs SQL generation + execution internally for each sub-question and collects
    SubQueryResult objects into state for SynthesizeAnswer to combine.

    Example:
        node = DecomposeQuery(chat_model, sql_engine)
        result = node({"question": "By how many MPG did US cars improve 1970–1980?", "schema": ...})
        # result == {"sub_results": [SubQueryResult(...), SubQueryResult(...)]}
    """

    def __init__(self, chat_model: BaseChatModel, sql_engine: SqlEnginePort) -> None:
        self._plan_model: Runnable[LanguageModelInput, _DecompositionOutput] = cast(
            Runnable[LanguageModelInput, _DecompositionOutput],
            chat_model.with_structured_output(_DecompositionOutput),
        )
        self._sql_generator = GenerateSql(chat_model)
        self._engine = sql_engine

    def __call__(self, state: ChatState) -> dict[str, list[SubQueryResult]]:
        human_content = f"Schema:\n{state['schema']}\n\nQuestion: {state['question']}"
        messages = [
            SystemMessage(content=_DECOMPOSE_PROMPT),
            HumanMessage(content=human_content),
        ]
        decomposition: _DecompositionOutput = self._plan_model.invoke(messages)

        sub_results: list[SubQueryResult] = []
        for sub_q in decomposition.sub_questions:
            sub_state = cast(ChatState, {"schema": state["schema"], "question": sub_q})
            sql = self._sql_generator(sub_state)["sql_query"]
            query_result = self._engine.execute_query(sql)
            sub_results.append(
                SubQueryResult(question=sub_q, sql=sql, result=query_result)
            )

        return {"sub_results": sub_results}
