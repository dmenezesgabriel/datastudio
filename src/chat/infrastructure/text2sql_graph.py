from langchain_core.language_models import BaseChatModel
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from chat.application.ports.language_model_port import LanguageModelPort
from chat.application.ports.sql_engine_port import SqlEnginePort
from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.nodes.execute_sql import ExecuteSql
from chat.infrastructure.nodes.format_response import FormatResponse
from chat.infrastructure.nodes.generate_sql import GenerateSql
from chat.infrastructure.nodes.get_schema import GetSchema
from chat.infrastructure.nodes.list_tables import ListTables


def build_text2sql_graph(
    language_model: LanguageModelPort,
    sql_engine: SqlEnginePort,
) -> CompiledStateGraph:
    """Builds and compiles the text2sql LangGraph.

    Example:
        graph = build_text2sql_graph(llm, engine)
        result = graph.invoke({"question": "How many trips in April?"})
        print(result["response"])
    """
    chat_model = language_model.get_chat_model()
    nodes = _build_nodes(chat_model, sql_engine)
    return _wire_graph(nodes)


def _build_nodes(
    chat_model: BaseChatModel,
    sql_engine: SqlEnginePort,
) -> dict[str, object]:
    return {
        "list_tables": ListTables(sql_engine),
        "get_schema": GetSchema(sql_engine),
        "generate_sql": GenerateSql(chat_model),
        "execute_sql": ExecuteSql(sql_engine),
        "format_response": FormatResponse(chat_model),
    }


def _wire_graph(nodes: dict[str, object]) -> CompiledStateGraph:
    builder: StateGraph = StateGraph(ChatState)
    for name, node in nodes.items():
        builder.add_node(name, node)  # type: ignore[arg-type]
    builder.add_edge(START, "list_tables")
    builder.add_edge("list_tables", "get_schema")
    builder.add_edge("get_schema", "generate_sql")
    builder.add_edge("generate_sql", "execute_sql")
    builder.add_edge("execute_sql", "format_response")
    builder.add_edge("format_response", END)
    return builder.compile()
