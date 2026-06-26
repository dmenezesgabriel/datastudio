"""LangGraph assembly for the text-to-SQL pipeline."""

from collections.abc import Mapping
from typing import Protocol, cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import RetryPolicy

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.assemble_view import AssembleView
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.recommend_view import RecommendView
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
) -> TypedChatGraph:
    """Builds and compiles the text2sql LangGraph.

    Args:
        chat_model: Reasoning model used for SQL generation and repair.
        sql_engine: Database engine for listing tables and executing queries.
        format_chat_model: Optional cheaper/faster model for the trivial nodes
            (table selection and response formatting). Defaults to chat_model.

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "How many trips in April?"})
        print(result["response"])
    """
    return wire_text2sql_graph(build_text2sql_nodes(chat_model, sql_engine, format_chat_model))


def build_text2sql_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
) -> dict[str, ChatNode]:
    """Builds the named, unwrapped pipeline nodes for the text2sql graph.

    Exposed so the eval harness can wrap these nodes (e.g. in TimedNode) before
    wiring, keeping instrumentation out of the production builder.

    Example:
        nodes = build_text2sql_nodes(llm, engine)
        graph = wire_text2sql_graph(nodes)
    """
    fast_model = format_chat_model or chat_model
    return {
        "list_tables": ListTables(sql_engine),
        "select_tables": SelectTables(fast_model),
        "get_schema": GetSchema(sql_engine),
        "generate_sql": GenerateSql(chat_model),
        "execute_sql": ExecuteSql(sql_engine),
        "repair_sql": RepairSql(chat_model, sql_engine),
        "format_response": FormatResponse(fast_model),
        "recommend_view": RecommendView(fast_model),
        "assemble_view": AssembleView(),
    }


# Transient failures (connection blips, 5xx from the LLM/DB) should not sink a
# whole run; deterministic bugs (ValueError/TypeError, etc.) must surface at once.
# default_retry_on already retries ConnectionError + 5xx and skips those bugs.
# execute_sql swallows its own errors into state for the repair loop, so retry is
# a no-op there — the real win is on the LLM-backed nodes.
_NODE_RETRY_POLICY = RetryPolicy(max_attempts=3)


def wire_text2sql_graph(nodes: dict[str, ChatNode]) -> TypedChatGraph:
    """Wires a set of named ChatNode callables into a compiled LangGraph.

    The flow is a single path with a repair loop: a failed execution routes to
    repair_sql (which regenerates the query) and back to execute_sql, up to
    MAX_REPAIR_ATTEMPTS, before giving up and formatting a failure message. The
    tail then runs the presentation stage (recommend_view -> assemble_view) to
    produce a renderable json-render tree from the result.
    Every node carries a RetryPolicy so transient infrastructure errors are
    retried with backoff instead of failing the run.

    Example:
        graph = wire_text2sql_graph({"list_tables": ListTables(engine), ...})
    """
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node, retry_policy=_NODE_RETRY_POLICY)  # pyright: ignore[reportUnknownMemberType]
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
    builder.add_edge("format_response", "recommend_view")
    builder.add_edge("recommend_view", "assemble_view")
    builder.add_edge("assemble_view", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
