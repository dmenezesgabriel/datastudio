import argparse
from dataclasses import dataclass

import pytest
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_core.outputs import ChatGeneration, ChatResult

from chat.infrastructure.cli import (
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


class FakePlainExtractor:
    def extract(self, message: BaseMessage) -> str:
        return str(message.content)


class FakeChatModel(BaseChatModel):
    canned_response: str = "fake response"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        generation = ChatGeneration(message=AIMessage(content=self.canned_response))
        return ChatResult(generations=[generation])

    @property
    def _llm_type(self) -> str:
        return "fake-chat-model"


class TestBuildArgParser:
    def test_message_flag_sets_message(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["-m", "hello"])

        # Assert
        assert args.message == "hello"

    def test_interactive_flag_sets_interactive(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["-i"])

        # Assert
        assert args.interactive is True

    def test_message_and_interactive_are_mutually_exclusive(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args(["-m", "hello", "-i"])

    def test_mode_is_required(self) -> None:
        with pytest.raises(SystemExit):
            build_arg_parser().parse_args([])

    def test_model_override_parsed(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["--model", "openai/gpt-4o", "-i"])

        # Assert
        assert args.model == "openai/gpt-4o"

    def test_temperature_override_parsed(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["--temperature", "0.7", "-i"])

        # Assert
        assert args.temperature == 0.7

    def test_system_prompt_parsed(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["--system-prompt", "Be concise", "-i"])

        # Assert
        assert args.system_prompt == "Be concise"

    def test_optional_args_default_to_none(self) -> None:
        # Act
        args = build_arg_parser().parse_args(["-i"])

        # Assert
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
        # Arrange
        settings = FakeSettings()
        args = self._make_namespace()

        # Act
        result = resolve_model_config(args, settings)  # type: ignore[arg-type]

        # Assert
        assert result == ("settings/model", 0.5, "settings-key", "https://settings.base")

    def test_model_arg_overrides_settings(self) -> None:
        # Arrange
        args = self._make_namespace(model="override/model")

        # Act
        name, *_ = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]

        # Assert
        assert name == "override/model"

    def test_temperature_arg_overrides_settings(self) -> None:
        # Arrange
        args = self._make_namespace(temperature=0.9)

        # Act
        _, temp, *_ = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]

        # Assert
        assert temp == 0.9

    def test_api_key_arg_overrides_settings(self) -> None:
        # Arrange
        args = self._make_namespace(api_key="cli-key")

        # Act
        _, _, key, _ = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]

        # Assert
        assert key == "cli-key"

    def test_api_base_arg_overrides_settings(self) -> None:
        # Arrange
        args = self._make_namespace(api_base="https://cli.base")

        # Act
        _, _, _, base = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]

        # Assert
        assert base == "https://cli.base"

    def test_all_args_override_settings(self) -> None:
        # Arrange
        args = self._make_namespace(
            model="cli/model",
            temperature=0.1,
            api_key="cli-key",
            api_base="https://cli.base",
        )

        # Act
        result = resolve_model_config(args, FakeSettings())  # type: ignore[arg-type]

        # Assert
        assert result == ("cli/model", 0.1, "cli-key", "https://cli.base")


class TestInvokeGraph:
    def test_returns_extracted_response(self) -> None:
        # Arrange
        fake_model = FakeChatModel(canned_response="hello there")

        # Act
        result = invoke_graph("hi", fake_model, FakePlainExtractor(), None)

        # Assert
        assert result == "hello there"

    def test_includes_system_message_when_provided(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        captured: list[BaseMessage] = []
        original = FakeChatModel._generate

        def capturing_generate(self_model, messages, stop=None, run_manager=None, **kwargs):
            captured.extend(messages)
            return original(self_model, messages, stop=stop, run_manager=run_manager, **kwargs)

        monkeypatch.setattr(FakeChatModel, "_generate", capturing_generate)

        # Act
        invoke_graph("hello", FakeChatModel(), FakePlainExtractor(), "Be concise")

        # Assert
        assert isinstance(captured[0], SystemMessage)
        assert captured[0].content == "Be concise"

    def test_omits_system_message_when_none(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        captured: list[BaseMessage] = []
        original = FakeChatModel._generate

        def capturing_generate(self_model, messages, stop=None, run_manager=None, **kwargs):
            captured.extend(messages)
            return original(self_model, messages, stop=stop, run_manager=run_manager, **kwargs)

        monkeypatch.setattr(FakeChatModel, "_generate", capturing_generate)

        # Act
        invoke_graph("hello", FakeChatModel(), FakePlainExtractor(), None)

        # Assert
        assert not any(isinstance(m, SystemMessage) for m in captured)

    def test_human_message_contains_input(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        captured: list[BaseMessage] = []
        original = FakeChatModel._generate

        def capturing_generate(self_model, messages, stop=None, run_manager=None, **kwargs):
            captured.extend(messages)
            return original(self_model, messages, stop=stop, run_manager=run_manager, **kwargs)

        monkeypatch.setattr(FakeChatModel, "_generate", capturing_generate)

        # Act
        invoke_graph("what is 2+2?", FakeChatModel(), FakePlainExtractor(), None)

        # Assert
        human_messages = [m for m in captured if isinstance(m, HumanMessage)]
        assert len(human_messages) == 1
        assert human_messages[0].content == "what is 2+2?"


class TestRunNonInteractive:
    def test_prints_response_to_stdout(self, capsys: pytest.CaptureFixture[str]) -> None:
        # Arrange
        fake_model = FakeChatModel(canned_response="the answer")

        # Act
        run_non_interactive("hi", fake_model, FakePlainExtractor(), None)

        # Assert
        assert capsys.readouterr().out == "the answer\n"


class TestRunInteractive:
    def test_exits_on_eof(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setattr("builtins.input", lambda _: (_ for _ in ()).throw(EOFError()))

        # Act / Assert (no exception raised)
        run_interactive(FakeChatModel(), FakePlainExtractor(), None)

    def test_exits_on_empty_line(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Arrange
        monkeypatch.setattr("builtins.input", lambda _: "")

        # Act / Assert (no exception raised)
        run_interactive(FakeChatModel(), FakePlainExtractor(), None)

    def test_prints_response_for_each_message(
        self,
        monkeypatch: pytest.MonkeyPatch,
        capsys: pytest.CaptureFixture[str],
    ) -> None:
        # Arrange
        responses = iter(["hello", EOFError()])

        def fake_input(_):
            value = next(responses)
            if isinstance(value, EOFError):
                raise value
            return value

        monkeypatch.setattr("builtins.input", fake_input)
        fake_model = FakeChatModel(canned_response="world")

        # Act
        run_interactive(fake_model, FakePlainExtractor(), None)

        # Assert
        assert capsys.readouterr().out == "world\n"
