from langchain_core.language_models import BaseChatModel

from shared.application.ports.sql_engine_port import SqlEnginePort
from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.eval.timed_node import TimedNode
from chat.infrastructure.graph.nodes.classify_query import ClassifyQuery
from chat.infrastructure.graph.nodes.decompose_query import DecomposeQuery
from chat.infrastructure.graph.nodes.execute_sql import ExecuteSql
from chat.infrastructure.graph.nodes.format_response import FormatResponse
from chat.infrastructure.graph.nodes.generate_sql import GenerateSql
from chat.infrastructure.graph.nodes.get_schema import GetSchema
from chat.infrastructure.graph.nodes.list_tables import ListTables
from chat.infrastructure.graph.nodes.select_tables import SelectTables
from chat.infrastructure.graph.nodes.synthesize_answer import SynthesizeAnswer
from chat.infrastructure.graph.text2sql_graph import ChatNode, wire_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph


def build_eval_graph(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
    recorder: MetricsRecorder,
    format_chat_model: BaseChatModel | None = None,
) -> TypedChatGraph:
    """Builds an instrumented text2sql graph with per-node latency timing.

    Each node is wrapped in a TimedNode that records execution time and sets
    recorder.current_node so that TokenCountingCallback can attribute tokens.

    Example:
        collector = EvalCollector()
        graph = build_eval_graph(model, engine, collector)
        graph.invoke({"question": "How many trips?"}, config={"callbacks": [cb]})
    """
    nodes: dict[str, ChatNode] = {
        "classify_query": TimedNode(
            "classify_query", ClassifyQuery(chat_model), recorder
        ),
        "list_tables": TimedNode("list_tables", ListTables(sql_engine), recorder),
        "select_tables": TimedNode("select_tables", SelectTables(chat_model), recorder),
        "get_schema": TimedNode("get_schema", GetSchema(sql_engine), recorder),
        "generate_sql": TimedNode("generate_sql", GenerateSql(chat_model), recorder),
        "execute_sql": TimedNode("execute_sql", ExecuteSql(sql_engine), recorder),
        "format_response": TimedNode(
            "format_response",
            FormatResponse(format_chat_model or chat_model),
            recorder,
        ),
        "decompose_query": TimedNode(
            "decompose_query", DecomposeQuery(chat_model, sql_engine), recorder
        ),
        "synthesize_answer": TimedNode(
            "synthesize_answer", SynthesizeAnswer(chat_model), recorder
        ),
    }
    return wire_text2sql_graph(nodes)
