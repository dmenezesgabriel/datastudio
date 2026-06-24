from chat.infrastructure.nodes.list_tables import ListTables
from test.unit.chat.infrastructure.nodes.fake_sql_engine import FakeSqlEngine


class TestListTables:
    def test_returns_tables_from_engine(self) -> None:
        engine = FakeSqlEngine(tables=["orders", "customers"])
        result = ListTables(engine)({"question": "q"})  # type: ignore[arg-type]
        assert result == {"tables": ["orders", "customers"]}

    def test_returns_empty_list_when_no_tables(self) -> None:
        result = ListTables(FakeSqlEngine())({"question": "q"})  # type: ignore[arg-type]
        assert result == {"tables": []}
