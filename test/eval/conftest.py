import json
import time
from dataclasses import asdict
from pathlib import Path

import pytest

from chat.infrastructure.eval.checks import deserialize_check
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine

_CASES_PATH = Path(__file__).parent / "cases.json"
_REPORTS_DIR = Path("reports")


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()  # type: ignore[call-arg]


@pytest.fixture(scope="session")
def eval_cases(
    request: pytest.FixtureRequest, app_settings: AppSettings
) -> list[EvalCase]:
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

    raw = json.loads(_CASES_PATH.read_text())
    return [
        EvalCase(
            id=spec["id"],
            question=spec["question"],
            checks=[deserialize_check(c, judge_model) for c in spec.get("checks", [])],
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

    sql_engine = DuckDbSqlEngine(app_settings.duckdb_path)
    runner = EvalRunner(chat_model, sql_engine, app_settings.language_model_name)
    report = runner.run(eval_cases)

    output_path = _REPORTS_DIR / f"eval_report_{int(time.time())}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2))

    return report
