"""Builds an instrumented text2sql graph for use in eval runs."""

from langchain_core.language_models import BaseChatModel

from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph
from shared.application.ports.sql_engine_port import SqlEnginePort


def build_eval_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    recorder: MetricsRecorder,
    format_chat_model: BaseChatModel | None = None,
) -> TypedChatGraph:
    """Builds an instrumented text2sql graph with per-node latency timing.

    Each node is wrapped in a TimedNode that records execution time and sets
    recorder.current_node so that TokenCountingCallback can attribute tokens.
    Topology mirrors build_text2sql_graph (single path + repair loop).

    Example:
        collector = EvalCollector()
        graph = build_eval_graph(model, engine, collector)
        graph.invoke({"question": "How many trips?"}, config={"callbacks": [cb]})
    """
    return build_text2sql_graph(chat_model, sql_engine, format_chat_model, recorder=recorder)
