from unittest.mock import patch

from langchain_core.language_models import BaseChatModel

from chat.infrastructure.graph.litellm_language_model import LiteLLMLanguageModel


class FakeChatLiteLLM(BaseChatModel):
    model: str = ""
    temperature: float = 0.0
    api_key: str | None = None
    api_base: str | None = None

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        raise NotImplementedError

    @property
    def _llm_type(self) -> str:
        return "fake-litellm"


class TestLiteLLMLanguageModel:
    def test_get_chat_model_returns_base_chat_model(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(model_name="gpt-4o")

            # Act
            result = sut.get_chat_model()

        # Assert
        assert isinstance(result, BaseChatModel)

    def test_get_chat_model_forwards_model_name(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(model_name="anthropic/claude-3-5-sonnet")

            # Act
            result = sut.get_chat_model()

        # Assert
        assert result.model == "anthropic/claude-3-5-sonnet"  # type: ignore[union-attr]

    def test_get_chat_model_forwards_temperature(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(model_name="gpt-4o", temperature=0.7)

            # Act
            result = sut.get_chat_model()

        # Assert
        assert result.temperature == 0.7  # type: ignore[union-attr]

    def test_get_chat_model_returns_distinct_instances(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(model_name="gpt-4o")

            # Act
            first = sut.get_chat_model()
            second = sut.get_chat_model()

        # Assert
        assert first is not second

    def test_get_chat_model_forwards_api_key(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(model_name="gpt-4o", api_key="sk-test-key")

            # Act
            result = sut.get_chat_model()

        # Assert
        assert result.api_key == "sk-test-key"  # type: ignore[union-attr]

    def test_get_chat_model_forwards_api_base(self) -> None:
        # Arrange
        with patch(
            "chat.infrastructure.graph.litellm_language_model.ChatLiteLLM",
            FakeChatLiteLLM,
        ):
            sut = LiteLLMLanguageModel(
                model_name="gpt-4o",
                api_base="https://opencode.ai/zen/go/v1",
            )

            # Act
            result = sut.get_chat_model()

        # Assert
        assert result.api_base == "https://opencode.ai/zen/go/v1"  # type: ignore[union-attr]
