import argparse

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import BaseMessage, HumanMessage, SystemMessage

from chat.application.ports.response_content_extractor_port import ResponseContentExtractorPort
from chat.infrastructure.litellm_language_model import LiteLLMLanguageModel
from chat.infrastructure.response_content_extractor_factory import create_response_content_extractor
from shared.infrastructure.settings import AppSettings


def build_arg_parser() -> argparse.ArgumentParser:
    """Builds the CLI argument parser for graph invocation testing.

    Example:
        parser = build_arg_parser()
        args = parser.parse_args(["-m", "hello"])
    """
    parser = argparse.ArgumentParser(
        prog="datastudio",
        description="Test a LangGraph chat graph with configurable model and prompt.",
    )
    model_group = parser.add_argument_group("model overrides")
    model_group.add_argument("--model", default=None, metavar="NAME", help="LiteLLM model name (default: from settings)")
    model_group.add_argument("--temperature", type=float, default=None, metavar="FLOAT", help="Sampling temperature 0.0-1.0 (default: from settings)")
    model_group.add_argument("--api-key", default=None, metavar="KEY", help="API key (default: from settings)")
    model_group.add_argument("--api-base", default=None, metavar="URL", help="API base URL (default: from settings)")
    graph_group = parser.add_argument_group("graph configuration")
    graph_group.add_argument("--system-prompt", default=None, metavar="TEXT", help="System prompt forwarded to the graph")
    mode_group = parser.add_mutually_exclusive_group(required=True)
    mode_group.add_argument("--message", "-m", default=None, metavar="TEXT", help="Send a single message and exit")
    mode_group.add_argument("--interactive", "-i", action="store_true", help="Start an interactive REPL loop")
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


def invoke_graph(
    message: str,
    chat_model: BaseChatModel,
    extractor: ResponseContentExtractorPort,
    system_prompt: str | None,
) -> str:
    """Invokes the graph (or direct model until LangGraph is wired in).

    This is the seam — only this function changes when LangGraph replaces the body.

    Example:
        response = invoke_graph("Hello", chat_model, extractor, "Be concise")
    """
    messages: list[BaseMessage] = []
    if system_prompt is not None:
        messages.append(SystemMessage(content=system_prompt))
    messages.append(HumanMessage(content=message))
    response = chat_model.invoke(messages)
    return extractor.extract(response)


def run_non_interactive(
    message: str,
    chat_model: BaseChatModel,
    extractor: ResponseContentExtractorPort,
    system_prompt: str | None,
) -> None:
    """Sends a single message, prints the response, and returns.

    Example:
        run_non_interactive("Hello", chat_model, extractor, None)
    """
    print(invoke_graph(message, chat_model, extractor, system_prompt))


def run_interactive(
    chat_model: BaseChatModel,
    extractor: ResponseContentExtractorPort,
    system_prompt: str | None,
) -> None:
    """Runs a REPL loop until EOF or empty input.

    Example:
        run_interactive(chat_model, extractor, "You are helpful")
    """
    while True:
        try:
            message = input("> ")
        except EOFError:
            break
        if not message:
            break
        print(invoke_graph(message, chat_model, extractor, system_prompt))


def main() -> None:
    """Entry point: parse args, wire infrastructure, dispatch to mode.

    Example:
        # python main.py -m "Hello"
        # python main.py -i
    """
    args = build_arg_parser().parse_args()
    settings = AppSettings()
    model_name, temperature, api_key, api_base = resolve_model_config(args, settings)
    chat_model = LiteLLMLanguageModel(
        model_name=model_name,
        temperature=temperature,
        api_key=api_key,
        api_base=api_base,
    ).get_chat_model()
    extractor = create_response_content_extractor(api_base)
    if args.interactive:
        run_interactive(chat_model, extractor, args.system_prompt)
        return
    run_non_interactive(args.message, chat_model, extractor, args.system_prompt)
