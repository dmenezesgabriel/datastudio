from collections.abc import Mapping
from typing import Protocol

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]

from shared.application.ports.sql_engine_port import SqlEnginePort
from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.nodes.classify_query import ClassifyQuery
from chat.infrastructure.graph.nodes.decompose_query import DecomposeQuery
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from chat.infrastructure.graph.nodes.synthesize_answer import SynthesizeAnswer
from chat.infrastructure.graph.types import TypedChatGraph


class ChatNode(Protocol):
    """Structural contract for a callable that accepts ChatState and returns a partial state dict."""

    def __call__(self, state: ChatState) -> Mapping[str, object]: ...


def build_text2sql_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
) -> TypedChatGraph:
    """Builds and compiles the text2sql LangGraph.

    Args:
        chat_model: Model used for table selection and SQL generation.
        sql_engine: Database engine for listing tables and executing queries.
        format_chat_model: Optional cheaper model for the format_response node.
            Defaults to chat_model when not provided.

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "How many trips in April?"})
        print(result["response"])
    """
    nodes = _build_nodes(chat_model, sql_engine, format_chat_model)
    return wire_text2sql_graph(nodes)


def _build_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
) -> dict[str, ChatNode]:
    return {
        "classify_query": ClassifyQuery(chat_model),
        "list_tables": ListTables(sql_engine),
        "select_tables": SelectTables(chat_model),
        "get_schema": GetSchema(sql_engine),
        "generate_sql": GenerateSql(chat_model),
        "execute_sql": ExecuteSql(sql_engine),
        "format_response": FormatResponse(format_chat_model or chat_model),
        "decompose_query": DecomposeQuery(chat_model, sql_engine),
        "synthesize_answer": SynthesizeAnswer(chat_model),
    }


def wire_text2sql_graph(nodes: dict[str, ChatNode]) -> TypedChatGraph:
    """Wires a set of named ChatNode callables into a compiled LangGraph.

    Example:
        graph = wire_text2sql_graph({"list_tables": ListTables(engine), ...})
    """
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node)  # pyright: ignore[reportUnknownMemberType]
    # shared prefix: classify → list → select → schema
    builder.add_edge(START, "classify_query")
    builder.add_edge("classify_query", "list_tables")
    builder.add_edge("list_tables", "select_tables")
    builder.add_edge("select_tables", "get_schema")
    # routing after schema: simple → generate SQL; complex → decompose
    builder.add_conditional_edges(  # pyright: ignore[reportUnknownMemberType,reportUnknownArgumentType,reportUnknownLambdaType]
        "get_schema",
        lambda state: state["complexity"],  # type: ignore[index]
        {"simple": "generate_sql", "complex": "decompose_query"},
    )
    # simple path
    builder.add_edge("generate_sql", "execute_sql")
    builder.add_edge("execute_sql", "format_response")
    builder.add_edge("format_response", END)
    # complex path
    builder.add_edge("decompose_query", "synthesize_answer")
    builder.add_edge("synthesize_answer", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
