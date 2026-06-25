from typing import Literal, TypedDict

from chat.domain.value_objects.sub_query_result import SubQueryResult
from shared.domain.value_objects.query_result import QueryResult


class ChatState(TypedDict):
    """Graph state shared across all nodes in the chat LangGraph.

    Fields are populated progressively as the graph executes.
    """

    question: str
    complexity: Literal["simple", "complex"]
    tables: list[str]
    schema: str
    sql_query: str
    query_result: QueryResult
    sub_results: list[SubQueryResult]
    response: str
