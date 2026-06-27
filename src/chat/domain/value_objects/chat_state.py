"""Chat state TypedDict shared across all LangGraph nodes."""

from typing import NotRequired, TypedDict

from chat.domain.value_objects.render_tree import RenderTree
from chat.domain.value_objects.view_spec import ViewSpec
from shared.domain.value_objects.query_result import QueryResult


class ChatState(TypedDict):
    """Graph state shared across all nodes in the chat LangGraph.

    Fields are populated progressively as the graph executes. The flow is a
    single path: list_tables → select_tables → get_schema → generate_sql →
    execute_sql → (repair_sql loop on failure) → format_response.

    ``repair_attempts`` and ``query_result`` are ``NotRequired`` because they
    are absent in the initial state and only populated once their respective
    nodes have run.  All other fields are set exactly once by an early node
    before any later node reads them.
    """

    request_id: NotRequired[str]  # UUID set by the engine adapter; absent in eval/test runs
    question: str
    tables: list[str]
    schema: str
    sql_query: str
    sql_error: str
    repair_attempts: NotRequired[int]  # absent before the first repair
    query_result: NotRequired[QueryResult]  # absent until SQL executes cleanly
    response: str
    view_spec: NotRequired[ViewSpec]  # absent until recommend_view runs
    view: NotRequired[RenderTree]  # absent until assemble_view runs
