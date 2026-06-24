from langchain_core.language_models import BaseChatModel
from langgraph.graph.state import CompiledStateGraph

from chat.domain.value_objects.query_result import QueryResult
from chat.infrastructure.text2sql_graph import build_text2sql_graph
from test.unit.chat.infrastructure.nodes.fake_sql_engine import FakeSqlEngine
from test.unit.chat.infrastructure.nodes.fake_structured_chat_model import FakeStructuredChatModel


class FakeLanguageModel:
    """Fake LanguageModelPort that wraps a pre-built BaseChatModel."""

    def __init__(self, chat_model: BaseChatModel) -> None:
        self._chat_model = chat_model

    def get_chat_model(self) -> BaseChatModel:
        return self._chat_model


def _make_graph() -> CompiledStateGraph:
    chat_model = FakeStructuredChatModel(sql="SELECT 1", answer="One row.")
    language_model = FakeLanguageModel(chat_model)
    sql_engine = FakeSqlEngine(
        tables=["orders"],
        schemas={"orders": "-- orders\nid INT"},
        query_result=QueryResult(columns=["id"], rows=[(1,)], row_count=1),
    )
    return build_text2sql_graph(language_model, sql_engine)


class TestBuildText2SqlGraph:
    def test_returns_compiled_state_graph(self) -> None:
        assert isinstance(_make_graph(), CompiledStateGraph)

    def test_invoke_returns_response_key(self) -> None:
        result = _make_graph().invoke({"question": "How many?"})
        assert result["response"] == "One row."

    def test_invoke_propagates_tables_through_state(self) -> None:
        result = _make_graph().invoke({"question": "q"})
        assert result["tables"] == ["orders"]
