"""LangGraph assembly for editing a saved dashboard (classify → restyle | reanalyze).

A small sibling of the build graph. ``classify_edit`` routes the turn: a ``restyle``
goes straight to ``author_edit_patches`` (patch the existing elements, no SQL); a
``reanalyze`` runs schema discovery and the single-widget SQL worker, reusing the very
nodes the build graph uses so the edited widget is produced identically. Both paths emit
namespaced ``/elements``/``/state`` patches the caller applies to the artifact's spec.
"""

from collections.abc import Mapping
from typing import cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import RetryPolicy

from chat.application.ports.progress_reporter import NullProgressReporter, ProgressReporter
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.author_edit_patches import AuthorEditPatches
from chat.infrastructure.graph.nodes.build_widget import BuildWidget
from chat.infrastructure.graph.nodes.classify_edit import ClassifyEdit
from chat.infrastructure.graph.nodes.generate_widget_view import load_catalog_prompt
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from chat.infrastructure.graph.observable_node import ObservableNode
from chat.infrastructure.graph.progress_node import ProgressNode
from chat.infrastructure.graph.response_content_extractor import (
    create_response_content_extractor,
)
from chat.infrastructure.graph.stream_writer_progress_reporter import (
    StreamWriterProgressReporter,
)
from chat.infrastructure.graph.types import TypedChatGraph, TypedChatNode
from shared.application.ports.sql_engine_port import SqlEnginePort

# Checklist copy for each sequential edit node (build_widget reports its own per-widget
# steps). Data-agnostic by design, mirroring the build graph's labels.
_EDIT_STEP_LABELS: dict[str, str] = {
    "classify_edit": "Understanding your edit",
    "author_edit_patches": "Applying the change",
    "list_tables": "Looking at your data",
    "select_tables": "Choosing the right tables",
    "get_schema": "Reading the schema",
}

# Same policy as the build graph: retry transient blips, surface deterministic bugs.
_NODE_RETRY_POLICY = RetryPolicy(max_attempts=3)


def route_after_classify(state: ChatState) -> str:
    """Route out of ``classify_edit``: a restyle patches elements, else reanalyze via SQL."""
    if cast(dict[str, object], state).get("edit_mode") == "restyle":
        return "author_edit_patches"
    return "list_tables"


def build_edit_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
    api_base: str | None = None,
) -> TypedChatGraph:
    """Build and compile the dashboard-edit LangGraph.

    Args:
        chat_model: Reasoning model used for a reanalyze's SQL generation and repair.
        sql_engine: Database engine for listing tables and executing a reanalyze query.
        format_chat_model: Optional cheaper model for classify/restyle/discovery nodes.
        api_base: Provider base URL, used to pick the view model's content extractor.

    Example:
        graph = build_edit_graph(llm, engine)
        # graph.astream({"instruction": "make it a line chart", "prior_spec": spec, "history": []})
    """
    reporter = StreamWriterProgressReporter()
    nodes = build_edit_nodes(chat_model, sql_engine, format_chat_model, api_base, reporter)
    return wire_edit_graph(_instrument_edit_nodes(nodes, reporter))


def build_edit_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
    api_base: str | None = None,
    reporter: ProgressReporter | None = None,
) -> dict[str, TypedChatNode]:
    """Build the named, unwrapped edit nodes, reusing the build graph's discovery/worker."""
    fast_model = format_chat_model or chat_model
    extractor = create_response_content_extractor(api_base)
    return {
        "classify_edit": ClassifyEdit(fast_model),
        "author_edit_patches": AuthorEditPatches(fast_model, load_catalog_prompt(), extractor),
        "list_tables": ListTables(sql_engine),
        "select_tables": SelectTables(fast_model),
        "get_schema": GetSchema(sql_engine),
        "build_widget": BuildWidget(
            chat_model,
            sql_engine,
            fast_model,
            load_catalog_prompt(),
            extractor,
            reporter or NullProgressReporter(),
        ),
    }


def _instrument_edit_nodes(
    nodes: Mapping[str, TypedChatNode], reporter: ProgressReporter
) -> dict[str, TypedChatNode]:
    """Wrap each node for observability, and each sequential node for checklist progress."""
    observed: dict[str, TypedChatNode] = {}
    for name, node in nodes.items():
        wrapped: TypedChatNode = ObservableNode(name, node)
        if name in _EDIT_STEP_LABELS:
            wrapped = ProgressNode(name, _EDIT_STEP_LABELS[name], reporter, wrapped)
        observed[name] = wrapped
    return observed


def wire_edit_graph(nodes: Mapping[str, TypedChatNode]) -> TypedChatGraph:
    """Wire the edit nodes into a compiled classify → (restyle | reanalyze) graph."""
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node, retry_policy=_NODE_RETRY_POLICY)  # pyright: ignore[reportUnknownMemberType]
    builder.add_edge(START, "classify_edit")
    builder.add_conditional_edges(  # pyright: ignore[reportUnknownMemberType]
        "classify_edit", route_after_classify, ["author_edit_patches", "list_tables"]
    )
    builder.add_edge("author_edit_patches", END)
    builder.add_edge("list_tables", "select_tables")
    builder.add_edge("select_tables", "get_schema")
    builder.add_edge("get_schema", "build_widget")
    builder.add_edge("build_widget", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
