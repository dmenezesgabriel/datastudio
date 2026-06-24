from collections.abc import Mapping
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]

from shared.application.ports.sql_engine_port import SqlEnginePort
from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.types import TypedChatGraph


class _ChatNode(Protocol):
    """Structural contract for a callable that accepts ChatState and returns a partial state dict."""

    def __call__(self, state: ChatState) -> Mapping[str, object]: ...


def build_text2sql_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
) -> TypedChatGraph:
    """Builds and compiles the text2sql LangGraph.

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "How many trips in April?"})
        print(result["response"])
    """
    nodes = _build_nodes(chat_model, sql_engine)
    return _wire_graph(nodes)


def _build_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
) -> dict[str, _ChatNode]:
    return {
        "list_tables": ListTables(sql_engine),
        "get_schema": GetSchema(sql_engine),
        "generate_sql": GenerateSql(chat_model),
        "execute_sql": ExecuteSql(sql_engine),
        "format_response": FormatResponse(chat_model),
    }


def _wire_graph(nodes: dict[str, _ChatNode]) -> TypedChatGraph:
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node)  # pyright: ignore[reportUnknownMemberType]
    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "get_schema")
    builder.add_edge("get_schema", "generate_sql")
    builder.add_edge("generate_sql", "execute_sql")
    builder.add_edge("execute_sql", "format_response")
    builder.add_edge("format_response", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
