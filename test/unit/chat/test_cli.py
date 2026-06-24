import argparse
from dataclasses import dataclass
from typing import cast

import pytest

from chat.domain.value_objects.chat_state import ChatState
from chat.infrastructure.graph.cli import (
    build_arg_parser,
    invoke_graph,
    resolve_model_config,
    run_interactive,
    run_non_interactive,
)


@dataclass
class FakeSettings:
    openai_api_key: str = "settings-key"
    openai_base_url: str = "https://settings.base"
    language_model_name: str = "settings/model"
    language_model_temperature: float = 0.5


class FakeGraph:
    """Minimal graph fake that satisfies the _Graph structural interface.

    Returns a canned response and records the last invocation input for
    assertion in tests.
    """

    def __init__(self, response: str = "fake answer") -> None:
        self._response = response
        self.last_input: ChatState | None = None

    def invoke(self, input: ChatState) -> ChatState:  # noqa: A002
        self.last_input = input
        return cast(ChatState, {"response": self._response})


class TestBuildArgParser:
    def test_message_flag_sets_message(self) -> None:
        args = build_arg_parser().parse_args(["-m", "hello"])
        assert args.message == "hello"

    def test_interactive_flag_sets_interactive(self) -> None:
        args = build_arg_parser().parse_args(["-i"])
        assert args.interactive is True

    def test_message_and_interactive_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["-m", "hello", "-i"])

    def test_mode_is_required(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args([])

    def test_model_override_parsed(self) -> None:
        args = build_arg_parser().parse_args(["--model", "openai/gpt-4o", "-i"])
        assert args.model == "openai/gpt-4o"

    def test_temperature_override_parsed(self) -> None:
        args = build_arg_parser().parse_args(["--temperature", "0.7", "-i"])
        assert args.temperature == 0.7

    def test_system_prompt_still_accepted(self) -> None:
        # kept as a no-op for backwards compatibility
        args = build_arg_parser().parse_args(["--system-prompt", "Be concise", "-i"])
        assert args.system_prompt == "Be concise"

    def test_optional_args_default_to_none(self) -> None:
        args = build_arg_parser().parse_args(["-i"])
        assert args.model is None
        assert args.temperature is None
        assert args.api_key is None
        assert args.api_base is None
        assert args.system_prompt is None


class TestResolveModelConfig:
    def _make_namespace(
        self,
        model: str | None = None,
        temperature: float | None = None,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> argparse.Namespace:
        return argparse.Namespace(
            model=model,
            temperature=temperature,
            api_key=api_key,
            api_base=api_base,
        )

    def test_settings_used_when_all_args_are_none(self) -> None:
        result = resolve_model_config(self._make_namespace(), FakeSettings())  # type: ignore[arg-type]
        assert result == (
            "settings/model",
            0.5,
            "settings-key",
            "https://settings.base",
        )

    def test_model_arg_overrides_settings(self) -> None:
        name, *_ = resolve_model_config(
            self._make_namespace(model="override/model"), FakeSettings()
        )  # type: ignore[arg-type]
        assert name == "override/model"

    def test_temperature_arg_overrides_settings(self) -> None:
        _, temp, *_ = resolve_model_config(
            self._make_namespace(temperature=0.9), FakeSettings()
        )  # type: ignore[arg-type]
        assert temp == 0.9

    def test_api_key_arg_overrides_settings(self) -> None:
        _, _, key, _ = resolve_model_config(
            self._make_namespace(api_key="cli-key"), FakeSettings()
        )  # type: ignore[arg-type]
        assert key == "cli-key"

    def test_api_base_arg_overrides_settings(self) -> None:
        _, _, _, base = resolve_model_config(
            self._make_namespace(api_base="https://cli.base"), FakeSettings()
        )  # type: ignore[arg-type]
        assert base == "https://cli.base"

    def test_all_args_override_settings(self) -> None:
        args = self._make_namespace(
            model="cli/model",
            temperature=0.1,
            api_key="cli-key",
            api_base="https://cli.base",
        )
        result = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]
        assert result == ("cli/model", 0.1, "cli-key", "https://cli.base")


class TestInvokeGraph:
    def test_returns_response_from_graph(self) -> None:
        # arrange
        graph = FakeGraph(response="hello there")
        # act
        result = invoke_graph(graph, "hi")  # pyright: ignore[reportArgumentType]
        # assert
        assert result == "hello there"

    def test_passes_message_as_question(self) -> None:
        # arrange
        graph = FakeGraph()
        # act
        invoke_graph(graph, "what is 2+2?")  # pyright: ignore[reportArgumentType]
        # assert
        assert graph.last_input == cast(ChatState, {"question": "what is 2+2?"})


class TestRunNonInteractive:
    def test_prints_response_to_stdout(
        self, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # arrange / act
        run_non_interactive("hi", FakeGraph(response="the answer"))  # pyright: ignore[reportArgumentType]
        # assert
        assert capsys.readouterr().out == "the answer\n"


class TestRunInteractive:
    def test_exits_on_eof(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # arrange
        monkeypatch.setattr(
            "builtins.input", lambda _: (_ for _ in ()).throw(EOFError())
        )
        # act / assert (no exception raised)
        run_interactive(FakeGraph())  # pyright: ignore[reportArgumentType]

    def test_exits_on_empty_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # arrange
        monkeypatch.setattr("builtins.input", lambda _: "")
        # act / assert (no exception raised)
        run_interactive(FakeGraph())  # pyright: ignore[reportArgumentType]

    def test_prints_response_for_each_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # arrange
        responses = iter(["hello", EOFError()])

        def fake_input(_: str) -> str:
            value = next(responses)
            if isinstance(value, EOFError):
                raise value
            return value  # type: ignore[return-value]

        monkeypatch.setattr("builtins.input", fake_input)
        # act
        run_interactive(FakeGraph(response="world"))  # pyright: ignore[reportArgumentType]
        # assert
        assert capsys.readouterr().out == "world\n"
