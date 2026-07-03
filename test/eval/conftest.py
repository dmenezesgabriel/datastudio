"""Session-scoped pytest fixtures for the eval test suite."""

import json
import time
from dataclasses import asdict
from pathlib import Path

import pytest

from chat.infrastructure.eval.checks import Check, deserialize_check
from chat.infrastructure.eval.graph_builder import build_eval_graph
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner, EvalTurn
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine

_CASES_PATH = Path(__file__).parent / "cases.json"
_REPORTS_DIR = Path("reports")


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    """Load AppSettings once per session from the project .env file."""
    return AppSettings()  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def eval_cases(request: pytest.FixtureRequest, app_settings: AppSettings) -> list[EvalCase]:
    """Load and deserialise only the cases selected by pytest (respects -k).

    Example:
        uv run pytest test/eval/ -m eval -k "olist_total_gmv or olist_avg_review_score"
    """
    selected_ids = {
        item.callspec.params["case_id"]  # type: ignore[attr-defined]
        for item in request.session.items
        if hasattr(item, "callspec") and "case_id" in item.callspec.params
    }

    judge_model = LiteLLMLanguageModel(
        model_name=app_settings.language_model_name,
        temperature=0.0,
        api_key=app_settings.openai_api_key,
        api_base=app_settings.openai_base_url,
    ).get_chat_model()
    sql_engine = DuckDbSqlEngine(app_settings.duckdb_path)

    def checks_for(specs: list[dict[str, str]]) -> list[Check]:
        return [deserialize_check(c, judge_model, sql_engine) for c in specs]

    raw = json.loads(_CASES_PATH.read_text())
    return [
        EvalCase(
            id=spec["id"],
            question=spec["question"],
            checks=checks_for(spec.get("checks", [])),
            tags=spec.get("tags", []),
            follow_ups=[
                EvalTurn(question=turn["question"], checks=checks_for(turn.get("checks", [])))
                for turn in spec.get("follow_ups", [])
            ],
        )
        for spec in raw["cases"]
        if spec["id"] in selected_ids
    ]


@pytest.fixture(scope="session")
def eval_report(app_settings: AppSettings, eval_cases: list[EvalCase]) -> EvalReport:
    """Run all eval cases once and write a timestamped JSON report."""
    chat_model = LiteLLMLanguageModel(
        model_name=app_settings.language_model_name,
        temperature=app_settings.language_model_temperature,
        api_key=app_settings.openai_api_key,
        api_base=app_settings.openai_base_url,
    ).get_chat_model()
    format_chat_model = LiteLLMLanguageModel(
        model_name=app_settings.format_model_name,
        temperature=app_settings.language_model_temperature,
        api_key=app_settings.openai_api_key,
        api_base=app_settings.openai_base_url,
    ).get_chat_model()

    sql_engine = DuckDbSqlEngine(app_settings.duckdb_path)
    runner = EvalRunner(
        graph_factory=lambda recorder: build_eval_graph(
            chat_model, sql_engine, recorder, format_chat_model, app_settings.openai_base_url
        ),
        model_name=app_settings.language_model_name,
        input_price_per_m=app_settings.input_token_price_per_million,
        output_price_per_m=app_settings.output_token_price_per_million,
        max_workers=app_settings.eval_max_workers,
    )
    report = runner.run(eval_cases)

    output_path = _REPORTS_DIR / f"eval_report_{int(time.time())}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2))

    return report
