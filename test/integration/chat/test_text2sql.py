import re

import pytest
from langgraph.graph.state import CompiledStateGraph
from pytest_bdd import given, scenario, then, when

from chat.infrastructure.duckdb_sql_engine import DuckDbSqlEngine
from chat.infrastructure.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.text2sql_graph import build_text2sql_graph
from shared.infrastructure.settings import AppSettings


@pytest.mark.integration
@scenario("text2sql.feature", "Query the NYC taxi dataset")
def test_text2sql_graph_answers_nyc_taxi_question() -> None:
    pass


@given("a DuckDB engine seeded with dev data", target_fixture="sql_engine")
def sql_engine_fixture(app_settings: AppSettings) -> DuckDbSqlEngine:
    return DuckDbSqlEngine(app_settings.duckdb_path)


@given("a text2sql graph configured with OpenCode Go settings", target_fixture="text2sql_graph")
def text2sql_graph_fixture(
    app_settings: AppSettings,
    sql_engine: DuckDbSqlEngine,
) -> CompiledStateGraph:
    language_model = LiteLLMLanguageModel(
        model_name=app_settings.language_model_name,
        temperature=app_settings.language_model_temperature,
        api_key=app_settings.openai_api_key,
        api_base=app_settings.openai_base_url,
    )
    return build_text2sql_graph(language_model, sql_engine)


@when('I ask "How many taxi trips are in the dataset?"', target_fixture="answer")
def ask_question(text2sql_graph: CompiledStateGraph) -> str:
    result = text2sql_graph.invoke({"question": "How many taxi trips are in the dataset?"})
    return result["response"]


@then("I receive a non-empty natural language answer")
def check_non_empty(answer: str) -> None:
    assert answer and answer.strip()


@then("the answer contains a number")
def check_contains_number(answer: str) -> None:
    assert re.search(r"\d", answer), f"Expected a number in: {answer!r}"
