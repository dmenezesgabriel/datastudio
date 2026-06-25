"""Eval runner CLI: runs the text2sql eval suite and writes a JSON report.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --cases test/eval/cases.json --output eval_report.json
    python scripts/run_eval.py --judge-model openai/glm-4
"""

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import cast

from chat.infrastructure.eval.checks import deserialize_check
from chat.infrastructure.eval.graph_builder import build_eval_graph
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def _default_output_path() -> str:
    return f"reports/eval_report_{int(time.time())}.json"


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="run_eval",
        description="Run the text2sql evaluation suite and produce a JSON report.",
    )
    parser.add_argument(
        "--cases",
        default="test/eval/cases.json",
        metavar="PATH",
        help="Path to the cases JSON file (default: test/eval/cases.json)",
    )
    parser.add_argument(
        "--output",
        default=_default_output_path(),
        metavar="PATH",
        help="Path to write the JSON report (default: reports/eval_report_<epoch>.json)",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        metavar="NAME",
        help="LiteLLM model name for rubric evaluation (default: same as chat model)",
    )
    return parser


def _load_cases(cases_path: Path, judge_model: object, sql_engine: SqlEnginePort) -> list[EvalCase]:
    """Load EvalCases from a JSON fixture file, deserialising each check spec."""
    from langchain_core.language_models import BaseChatModel

    assert isinstance(judge_model, BaseChatModel)
    raw = json.loads(cases_path.read_text())
    return [
        EvalCase(
            id=case_spec["id"],
            question=case_spec["question"],
            checks=[
                deserialize_check(spec, judge_model, sql_engine)
                for spec in case_spec.get("checks", [])
            ],
            tags=case_spec.get("tags", []),
        )
        for case_spec in raw["cases"]
    ]


def _print_summary(report: EvalReport) -> None:
    s = report.summary
    print(f"Model    : {report.model}")
    print(f"Run at   : {report.run_at}")
    print(f"Results  : {s['passed']}/{s['total']} passed ({s['failed']} failed)")
    print(f"Pass rate: {s['pass_rate']}")
    print(f"Latency  : {s['avg_latency_s']}s avg / {s['p95_latency_s']}s p95")
    print(
        f"Tokens   : {s['total_input_tokens']} in / {s['total_output_tokens']} out "
        f"({s['avg_output_tokens']}/case)"
    )
    print(f"Cost     : ${s['cost_usd']}")
    _print_by_tag(s)
    print()
    _print_cases(report)


def _print_by_tag(summary: dict[str, object]) -> None:
    by_tag = summary.get("by_tag")
    if not isinstance(by_tag, dict):
        return
    counts = cast(dict[str, dict[str, int]], by_tag)
    print("By tag   :")
    for tag in sorted(counts):
        bucket = counts[tag]
        print(f"           {tag:24} {bucket['passed']}/{bucket['total']}")


def _print_cases(report: EvalReport) -> None:
    for case in report.cases:
        status = "PASS" if case.passed else "FAIL"
        total_lat = sum(m.latency_s for m in case.nodes.values())
        print(f"  [{status}] {case.case_id} ({total_lat:.2f}s)")
        if case.error:
            print(f"         error: {case.error}")
        for cr in case.check_results:
            mark = "✓" if cr["passed"] else "✗"
            label = f"{cr['type']}={cr['value']!r}" if cr["value"] else cr["type"]
            reason = f" — {cr['reasoning']}" if cr.get("reasoning") else ""
            print(f"         {mark} {label}{reason}")


def main() -> None:
    """Parse args, run the eval suite, and write the JSON report."""
    args = _build_arg_parser().parse_args()
    settings = AppSettings()  # type: ignore[call-arg]

    chat_model = LiteLLMLanguageModel(
        model_name=settings.language_model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()
    format_chat_model = LiteLLMLanguageModel(
        model_name=settings.format_model_name,
        temperature=settings.language_model_temperature,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()

    judge_model_name = args.judge_model or settings.language_model_name
    judge_model = LiteLLMLanguageModel(
        model_name=judge_model_name,
        temperature=0.0,
        api_key=settings.openai_api_key,
        api_base=settings.openai_base_url,
    ).get_chat_model()

    sql_engine = DuckDbSqlEngine(settings.duckdb_path)
    cases = _load_cases(Path(args.cases), judge_model, sql_engine)
    runner = EvalRunner(
        graph_factory=lambda recorder: build_eval_graph(
            chat_model, sql_engine, recorder, format_chat_model
        ),
        model_name=settings.language_model_name,
        input_price_per_m=settings.input_token_price_per_million,
        output_price_per_m=settings.output_token_price_per_million,
        max_workers=settings.eval_max_workers,
    )
    report = runner.run(cases)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2))

    _print_summary(report)
    print(f"Full report → {output_path}")


if __name__ == "__main__":
    main()
