from typing import TypedDict

from shared.domain.value_objects.query_result import QueryResult


class ChatState(TypedDict):
    """Graph state shared across all nodes in the chat LangGraph.

    Fields are populated progressively as the graph executes. The flow is a
    single path: list_tables → select_tables → get_schema → generate_sql →
    execute_sql → (repair_sql loop on failure) → format_response.
    """

    question: str
    tables: list[str]
    schema: str
    sql_query: str
    sql_error: str  # message from the last failed execution; "" when successful
    repair_attempts: int  # number of times repair_sql has regenerated the query
    query_result: QueryResult
    response: str
