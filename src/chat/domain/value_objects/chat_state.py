from typing import TypedDict

from shared.domain.value_objects.query_result import QueryResult


class ChatState(TypedDict):
    """Graph state shared across all nodes in the chat LangGraph.

    Fields are populated progressively as the graph executes.
    """

    question: str
    tables: list[str]
    schema: str
    sql_query: str
    query_result: QueryResult
    response: str
