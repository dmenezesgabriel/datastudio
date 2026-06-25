"""LangGraph assembly for the text-to-SQL pipeline."""

from collections.abc import Mapping
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.eval.timed_node import TimedNode
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.repair_sql import MAX_REPAIR_ATTEMPTS, RepairSql
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from chat.infrastructure.graph.types import TypedChatGraph
from shared.application.ports.sql_engine_port import SqlEnginePort


class ChatNode(Protocol):
    """Structural contract for a callable that accepts ChatState and returns a partial state dict.

    Each graph node implements this protocol.
    """

    def __call__(self, state: ChatState) -> Mapping[str, object]:
        """Process state and return a partial update dict."""
        ...


def _route_after_execution(state: ChatState) -> str:
    """Send successful queries to formatting; failed ones to repair until exhausted."""
    data = cast(dict[str, object], state)
    if data.get("query_result") is not None:
        return "format_response"
    attempts = data.get("repair_attempts")
    count = attempts if isinstance(attempts, int) else 0
    if count < MAX_REPAIR_ATTEMPTS:
        return "repair_sql"
    return "format_response"


def build_text2sql_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
    recorder: MetricsRecorder | None = None,
) -> TypedChatGraph:
    """Builds and compiles the text2sql LangGraph.

    Args:
        chat_model: Reasoning model used for SQL generation and repair.
        sql_engine: Database engine for listing tables and executing queries.
        format_chat_model: Optional cheaper/faster model for the trivial nodes
            (table selection and response formatting). Defaults to chat_model.
        recorder: When provided, every node is wrapped in TimedNode so latency
            and token usage are attributed per node. Pass EvalCollector for eval
            runs; omit for production.

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "How many trips in April?"})
        print(result["response"])
    """
    nodes = _build_nodes(chat_model, sql_engine, format_chat_model)
    if recorder is not None:
        nodes = {name: TimedNode(name, node, recorder) for name, node in nodes.items()}
    return wire_text2sql_graph(nodes)


def _build_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
) -> dict[str, ChatNode]:
    fast_model = format_chat_model or chat_model
    return {
        "list_tables": ListTables(sql_engine),
        "select_tables": SelectTables(fast_model),
        "get_schema": GetSchema(sql_engine),
        "generate_sql": GenerateSql(chat_model),
        "execute_sql": ExecuteSql(sql_engine),
        "repair_sql": RepairSql(chat_model, sql_engine),
        "format_response": FormatResponse(fast_model),
    }


def wire_text2sql_graph(nodes: dict[str, ChatNode]) -> TypedChatGraph:
    """Wires a set of named ChatNode callables into a compiled LangGraph.

    The flow is a single path with a repair loop: a failed execution routes to
    repair_sql (which regenerates the query) and back to execute_sql, up to
    MAX_REPAIR_ATTEMPTS, before giving up and formatting a failure message.

    Example:
        graph = wire_text2sql_graph({"list_tables": ListTables(engine), ...})
    """
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node)  # pyright: ignore[reportUnknownMemberType]
    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "select_tables")
    builder.add_edge("select_tables", "get_schema")
    builder.add_edge("get_schema", "generate_sql")
    builder.add_edge("generate_sql", "execute_sql")
    builder.add_conditional_edges(  # pyright: ignore[reportUnknownMemberType]
        "execute_sql",
        _route_after_execution,
        {"repair_sql": "repair_sql", "format_response": "format_response"},
    )
    builder.add_edge("repair_sql", "execute_sql")
    builder.add_edge("format_response", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
