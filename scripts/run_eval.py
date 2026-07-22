"""Eval runner CLI: runs the text2sql eval suite and writes a JSON report.

Usage:
    python scripts/run_eval.py
    python scripts/run_eval.py --cases test/eval/cases.json --reports-dir reports
    python scripts/run_eval.py --judge-model openai/glm-4
"""

import argparse
import datetime
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

from chat.infrastructure.eval.checks import deserialize_check
from chat.infrastructure.eval.graph_builder import build_edit_eval_graph, build_eval_graph
from chat.infrastructure.eval.runner import EvalCase, EvalReport, EvalRunner, EvalTurn
from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from shared.application.ports.sql_engine_port import SqlEnginePort
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def _run_epoch(report: EvalReport) -> int:
    """The run's own timestamp as an epoch — the name both of its files are built from.

    Taken from ``report.run_at`` rather than a separate ``time.time()`` so the names stay
    reproducible from file content, and so the pair a run writes always agrees.
    """
    return int(datetime.datetime.fromisoformat(report.run_at).timestamp())


def _report_path(reports_dir: Path, report: EvalReport) -> Path:
    """Canonical path of the run's full report.

    Example: ``_report_path(Path("reports"), report)`` ->
    ``reports/eval_report_1782962765.json``.
    """
    return reports_dir / f"eval_report_{_run_epoch(report)}.json"


def _summary_path(reports_dir: Path, report: EvalReport) -> Path:
    """Canonical path of the run's summary, sharing its report's epoch.

    The pair is written together, so a directory listing keeps them side by side. Example:
    ``_summary_path(Path("reports"), report)`` -> ``reports/eval_summary_1782962765.json``.
    """
    return reports_dir / f"eval_summary_{_run_epoch(report)}.json"


def _trend_summary(report: EvalReport) -> dict[str, object]:
    """The run reduced to what the trend table reads: how it went, not what happened.

    A full report grew to megabytes once the suite ran every case several times over, past
    what the repository accepts per file. This is the part worth keeping for every run
    forever; the per-case detail stays on the machine that produced it.

    Example:
        _trend_summary(report)  # {"run_at": ..., "model": ..., "summary": {...}}
    """
    return {"run_at": report.run_at, "model": report.model, "summary": report.summary}


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
        "--reports-dir",
        default="reports",
        metavar="PATH",
        help="Directory to write the JSON report into (default: reports). "
        "The filename is always eval_report_<epoch>.json.",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        metavar="NAME",
        help="LiteLLM model name for rubric evaluation (default: same as chat model)",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=None,
        metavar="N",
        help="Run each case N times and report per-case consistency (default: eval_repeats)",
    )
    return parser


def _load_cases(cases_path: Path, judge_model: object, sql_engine: SqlEnginePort) -> list[EvalCase]:
    """Load EvalCases (including edit/follow-up turns) from a JSON fixture file."""
    from langchain_core.language_models import BaseChatModel

    assert isinstance(judge_model, BaseChatModel)

    def checks_for(specs: list[dict[str, str]]) -> list[object]:
        return [deserialize_check(spec, judge_model, sql_engine) for spec in specs]

    raw = json.loads(cases_path.read_text())
    return [
        EvalCase(
            id=case_spec["id"],
            question=case_spec["question"],
            checks=cast(Any, checks_for(case_spec.get("checks", []))),
            tags=case_spec.get("tags", []),
            follow_ups=[
                EvalTurn(
                    question=turn.get("question", ""),
                    checks=cast(Any, checks_for(turn.get("checks", []))),
                    instruction=turn.get("instruction"),
                )
                for turn in case_spec.get("follow_ups", [])
            ],
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
    _print_consistency(s)
    _print_by_tag(s)
    print()
    _print_cases(report)


def _print_consistency(summary: dict[str, object]) -> None:
    """Print the pass@k reliability block when cases were repeated."""
    consistency = summary.get("consistency")
    if not isinstance(consistency, dict):
        return
    c = cast(dict[str, object], consistency)
    print(
        f"Consist. : mean {c['mean_consistency']} "
        f"({c['reliable']} reliable / {c['flaky']} flaky / {c['failing']} failing "
        f"of {c['cases']} cases)"
    )


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
    repeats = args.repeats if args.repeats is not None else settings.eval_repeats
    runner = EvalRunner(
        graph_factory=lambda recorder: build_eval_graph(
            chat_model, sql_engine, recorder, format_chat_model, settings.openai_base_url
        ),
        edit_graph_factory=lambda recorder: build_edit_eval_graph(
            chat_model, sql_engine, recorder, format_chat_model, settings.openai_base_url
        ),
        model_name=settings.language_model_name,
        input_price_per_m=settings.input_token_price_per_million,
        output_price_per_m=settings.output_token_price_per_million,
        max_workers=settings.eval_max_workers,
        repeats=repeats,
    )
    report = runner.run(cases)

    output_path = _report_path(Path(args.reports_dir), report)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(report), indent=2))
    summary_path = _summary_path(Path(args.reports_dir), report)
    # Trailing newline because this one is committed: without it the end-of-file hook
    # rewrites every summary a run produces.
    summary_path.write_text(json.dumps(_trend_summary(report), indent=2) + "\n")

    _print_summary(report)
    print(f"Full report → {output_path}")
    print(f"Summary → {summary_path}")


if __name__ == "__main__":
    main()
