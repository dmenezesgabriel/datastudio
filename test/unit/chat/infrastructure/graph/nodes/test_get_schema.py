from chat.infrastructure.graph.nodes.get_schema import GetSchema
from test.unit.chat.infrastructure.graph.nodes.fake_sql_engine import FakeSqlEngine


class TestGetSchema:
    def test_calls_get_table_schema_for_each_table(self) -> None:
        engine = FakeSqlEngine(
            tables=["a", "b"],
            schemas={"a": "-- a\nid INT", "b": "-- b\nname VARCHAR"},
        )
        result = GetSchema(engine)({"tables": ["a", "b"]})  # type: ignore[arg-type]
        assert "-- a" in result["schema"]
        assert "-- b" in result["schema"]

    def test_combines_schemas_with_blank_line(self) -> None:
        engine = FakeSqlEngine(schemas={"x": "-- x\ncol INT"})
        result = GetSchema(engine)({"tables": ["x"]})  # type: ignore[arg-type]
        assert result["schema"] == "-- x\ncol INT"

    def test_returns_empty_string_for_no_tables(self) -> None:
        result = GetSchema(FakeSqlEngine())({"tables": []})  # type: ignore[arg-type]
        assert result == {"schema": ""}
