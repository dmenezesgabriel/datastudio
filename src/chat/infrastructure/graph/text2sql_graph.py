"""LangGraph assembly for the text-to-SQL dashboard pipeline (orchestrator–workers)."""

from collections.abc import Mapping
from typing import cast

from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph  # pyright: ignore[reportMissingTypeStubs]
from langgraph.types import RetryPolicy, Send

from chat.application.ports.progress_reporter import NullProgressReporter, ProgressReporter
from chat.domain.value_objects.widget import WidgetSpec
from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.nodes.answer_text import AnswerText
from chat.infrastructure.graph.nodes.build_widget import BuildWidget
from chat.infrastructure.graph.nodes.compose_narrative import ComposeNarrative
from chat.infrastructure.graph.nodes.generate_widget_view import load_catalog_prompt
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.plan_widgets import PlanWidgets
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from chat.infrastructure.graph.observable_node import ObservableNode
from chat.infrastructure.graph.progress_node import ProgressNode
from chat.infrastructure.graph.response_content_extractor_factory import (
    create_response_content_extractor,
)
from chat.infrastructure.graph.stream_writer_progress_reporter import (
    StreamWriterProgressReporter,
)
from chat.infrastructure.graph.types import TypedChatGraph, TypedChatNode
from shared.application.ports.sql_engine_port import SqlEnginePort

# User-facing checklist copy for each sequential pipeline node (the parallel
# build_widget workers report their own per-widget steps). Data-agnostic by design.
_STEP_LABELS: dict[str, str] = {
    "list_tables": "Looking at your data",
    "select_tables": "Choosing the right tables",
    "get_schema": "Reading the schema",
    "plan_widgets": "Planning the dashboard",
    "answer_text": "Answering",
    "compose_narrative": "Writing the summary",
}


def fan_out_widgets(state: ChatState) -> list[Send]:
    """Fan out one parallel ``build_widget`` worker per planned widget (map step).

    Returned from a conditional edge after ``plan_widgets``; each ``Send`` carries the
    single widget plus the shared schema/tables as that worker's input state.
    """
    data = cast(dict[str, object], state)
    specs = [
        s for s in cast(list[object], data.get("widget_specs", [])) if isinstance(s, WidgetSpec)
    ]
    schema = data.get("schema", "")
    tables = data.get("tables", [])
    return [
        Send("build_widget", {"widget": spec, "schema": schema, "tables": tables}) for spec in specs
    ]


def route_after_plan(state: ChatState) -> str | list[Send]:
    """Route out of ``plan_widgets``: a text answer, or the widget fan-out.

    Returned from a conditional edge. A ``"text"`` classification goes to the single
    ``answer_text`` node; otherwise it fans out one ``build_widget`` worker per widget.
    """
    if cast(dict[str, object], state).get("answer_kind") == "text":
        return "answer_text"
    return fan_out_widgets(state)


def build_text2sql_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
    api_base: str | None = None,
) -> TypedChatGraph:
    """Builds and compiles the text2sql dashboard LangGraph.

    Args:
        chat_model: Reasoning model used for per-widget SQL generation and repair.
        sql_engine: Database engine for listing tables and executing queries.
        format_chat_model: Optional cheaper/faster model for the planning, view, and
            summary nodes. Defaults to chat_model.
        api_base: Provider base URL, used to pick the response-content extractor for
            the view-authoring model (reasoning providers return typed blocks).

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "Overview", "history": []})
        print(result["response"])
    """
    reporter = StreamWriterProgressReporter()
    nodes = build_text2sql_nodes(chat_model, sql_engine, format_chat_model, api_base, reporter)
    return wire_text2sql_graph(_instrument_nodes(nodes, reporter))


def _instrument_nodes(
    nodes: Mapping[str, TypedChatNode], reporter: ProgressReporter
) -> dict[str, TypedChatNode]:
    """Wrap each node for observability, and each sequential node for checklist progress.

    ``build_widget`` is excluded from ProgressNode: its N parallel workers would each
    report the same step id, so they report their own per-widget steps instead.
    """
    observed: dict[str, TypedChatNode] = {}
    for name, node in nodes.items():
        wrapped: TypedChatNode = ObservableNode(name, node)
        if name in _STEP_LABELS:
            wrapped = ProgressNode(name, _STEP_LABELS[name], reporter, wrapped)
        observed[name] = wrapped
    return observed


def build_text2sql_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    format_chat_model: BaseChatModel | None = None,
    api_base: str | None = None,
    reporter: ProgressReporter | None = None,
) -> dict[str, TypedChatNode]:
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
        "plan_widgets": PlanWidgets(fast_model),
        "build_widget": BuildWidget(
            chat_model,
            sql_engine,
            fast_model,
            load_catalog_prompt(),
            create_response_content_extractor(api_base),
            reporter or NullProgressReporter(),
        ),
        "answer_text": AnswerText(),
        "compose_narrative": ComposeNarrative(fast_model),
    }


# Transient failures (connection blips, 5xx from the LLM/DB) should not sink a whole
# run; deterministic bugs (ValueError/TypeError, etc.) must surface at once.
# default_retry_on already retries ConnectionError + 5xx and skips those bugs.
_NODE_RETRY_POLICY = RetryPolicy(max_attempts=3)


def wire_text2sql_graph(nodes: Mapping[str, TypedChatNode]) -> TypedChatGraph:
    """Wires the named TypedChatNode callables into a compiled orchestrator–workers graph.

    Discover the schema once, then ``plan_widgets`` classifies the turn. A ``"text"``
    question routes to ``answer_text`` and ends. Otherwise it plans 1..N widgets and
    fans out one parallel ``build_widget`` worker per widget (via ``Send``); each
    worker runs its own SQL pipeline and authors its widget bound to ``$state``. The
    workers' outputs aggregate (reducer channels) and ``compose_narrative`` writes the
    summary once they all finish. Every node carries a RetryPolicy for transient errors.

    Example:
        graph = wire_text2sql_graph({"list_tables": ListTables(engine), ...})
    """
    builder: StateGraph[ChatState, None, ChatState, ChatState] = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node, retry_policy=_NODE_RETRY_POLICY)  # pyright: ignore[reportUnknownMemberType]
    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "select_tables")
    builder.add_edge("select_tables", "get_schema")
    builder.add_edge("get_schema", "plan_widgets")
    builder.add_conditional_edges(  # pyright: ignore[reportUnknownMemberType]
        "plan_widgets", route_after_plan, ["build_widget", "answer_text"]
    )
    builder.add_edge("build_widget", "compose_narrative")
    builder.add_edge("answer_text", END)
    builder.add_edge("compose_narrative", END)
    return builder.compile()  # pyright: ignore[reportUnknownMemberType]
