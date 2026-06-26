"""CLI entrypoint for the Text-to-SQL LangGraph pipeline."""

import argparse

from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.graph.text2sql_engine_adapter import Text2SqlEngineAdapter
from chat.infrastructure.graph.text2sql_graph import build_text2sql_graph
from chat.infrastructure.graph.types import TypedChatGraph
from shared.infrastructure.config.settings import AppSettings
from shared.infrastructure.sql_engine.duckdb.duckdb_sql_engine import DuckDbSqlEngine


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser for graph invocation testing.

    Example:
        parser = build_arg_parser()
        args = parser.parse_args(["-m", "hello"])
    """
    parser = argparse.ArgumentParser(
        prog="datastudio",
        description="Text2SQL: ask questions about your data in natural language.",
    )
    model_group = parser.add_argument_group("model overrides")
    model_group.add_argument(
        "--model",
        default=None,
        metavar="NAME",
        help="LiteLLM model name (default: from settings)",
    )
    model_group.add_argument(
        "--temperature",
        type=float,
        default=None,
        metavar="FLOAT",
        help="Sampling temperature 0.0-1.0 (default: from settings)",
    )
    model_group.add_argument(
        "--api-key",
        default=None,
        metavar="KEY",
        help="API key (default: from settings)",
    )
    model_group.add_argument(
        "--api-base",
        default=None,
        metavar="URL",
        help="API base URL (default: from settings)",
    )
    # kept for backwards-compatibility, no longer forwarded
    parser.add_argument("--system-prompt", default=None, metavar="TEXT", help=argparse.SUPPRESS)
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument(
        "--message",
        "-m",
        default=None,
        metavar="TEXT",
        help="Send a single message and exit",
    )
    mode_group.add_argument(
        "--interactive",
        "-i",
        action="store_true",
        help="Start an interactive REPL loop",
    )
    return parser


def resolve_model_config(
    args: argparse.Namespace,
    settings: AppSettings,
) -> tuple[str, float, str | None, str | None]:
    """Merges CLI args with AppSettings defaults; CLI wins when not None.

    Example:
        model, temp, key, base = resolve_model_config(args, AppSettings())
    """
    model_name = settings.language_model_name
    if args.model is not None:
        model_name = args.model
    temperature = settings.language_model_temperature
    if args.temperature is not None:
        temperature = args.temperature
    api_key = settings.openai_api_key
    if args.api_key is not None:
        api_key = args.api_key
    api_base = settings.openai_base_url
    if args.api_base is not None:
        api_base = args.api_base
    return model_name, temperature, api_key, api_base


def invoke_graph(graph: TypedChatGraph, message: str, *, timeout_s: float | None = None) -> str:
    """Invokes the compiled LangGraph with a user question and returns the response.

    Delegates to Text2SqlEngineAdapter so the timeout/fallback logic lives in one
    place shared with the API.

    Example:
        response = invoke_graph(graph, "How many trips were there?", timeout_s=120.0)
    """
    return Text2SqlEngineAdapter(graph, timeout_s=timeout_s).answer(message).response


def run_non_interactive(
    message: str, graph: TypedChatGraph, timeout_s: float | None = None
) -> None:
    """Sends a single message, prints the response, and returns.

    Example:
        run_non_interactive("How many trips?", graph, timeout_s=120.0)
    """
    print(invoke_graph(graph, message, timeout_s=timeout_s))


def run_interactive(graph: TypedChatGraph, timeout_s: float | None = None) -> None:
    """Runs a REPL loop until EOF or empty input.

    Example:
        run_interactive(graph, timeout_s=120.0)
    """
    while True:
        try:
            message = input("> ")
        except EOFError:
            break
        except KeyboardInterrupt:
            print()  # newline after ^C so the next shell prompt starts cleanly
            break
        if not message:
            break
        print(invoke_graph(graph, message, timeout_s=timeout_s))


def main() -> None:
    """Entry point: parse args, wire infrastructure, dispatch to mode.

    Example:
        # python main.py -m "How many trips had fare > $20?"
        # python main.py -i
    """
    args = build_arg_parser().parse_args()
    settings = AppSettings()  # type: ignore[call-arg]
    model_name, temperature, api_key, api_base = resolve_model_config(args, settings)
    chat_model = LiteLLMLanguageModel(
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
    ).get_chat_model()
    format_chat_model = LiteLLMLanguageModel(
        model_name=settings.format_model_name,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
    ).get_chat_model()
    sql_engine = DuckDbSqlEngine(settings.duckdb_path)
    graph = build_text2sql_graph(chat_model, sql_engine, format_chat_model=format_chat_model)
    if args.interactive:
        run_interactive(graph, timeout_s=settings.query_timeout_s)
        return
    run_non_interactive(args.message, graph, timeout_s=settings.query_timeout_s)
