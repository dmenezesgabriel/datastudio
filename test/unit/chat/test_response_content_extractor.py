from langchain_core.messages import AIMessage

from chat.infrastructure.graph.response_content_extractor import (
    PlainTextExtractor,
    ThinkingBlocksExtractor,
    create_response_content_extractor,
)


class TestPlainTextExtractor:
    def test_extract_returns_string_content(self) -> None:
        # Arrange
        message = AIMessage(content="Hello")
        sut = PlainTextExtractor()

        # Act
        result = sut.extract(message)

        # Assert
        assert result == "Hello"


class TestThinkingBlocksExtractor:
    def test_extract_returns_text_block_content(self) -> None:
        # Arrange
        message = AIMessage(
            content=[
                {"type": "thinking", "thinking": "Let me think..."},
                {"type": "text", "text": "Hello"},
            ]
        )

        # Act
        result = ThinkingBlocksExtractor().extract(message)

        # Assert
        assert result == "Hello"

    def test_extract_joins_multiple_text_blocks(self) -> None:
        # Arrange
        message = AIMessage(
            content=[
                {"type": "text", "text": "Hello"},
                {"type": "text", "text": "World"},
            ]
        )

        # Act
        result = ThinkingBlocksExtractor().extract(message)

        # Assert
        assert result == "Hello World"

    def test_extract_ignores_thinking_blocks(self) -> None:
        # Arrange
        message = AIMessage(content=[{"type": "thinking", "thinking": "thoughts"}])

        # Act
        result = ThinkingBlocksExtractor().extract(message)

        # Assert
        assert result == ""

    def test_extract_falls_back_for_plain_string_content(self) -> None:
        # Arrange
        message = AIMessage(content="Hello")

        # Act
        result = ThinkingBlocksExtractor().extract(message)

        # Assert
        assert result == "Hello"


class TestCreateResponseContentExtractor:
    def test_returns_thinking_blocks_extractor_for_opencode(self) -> None:
        # Act
        result = create_response_content_extractor("https://opencode.ai/zen/go/v1")

        # Assert
        assert isinstance(result, ThinkingBlocksExtractor)

    def test_returns_plain_text_extractor_for_openai(self) -> None:
        # Act
        result = create_response_content_extractor("https://api.openai.com/v1")

        # Assert
        assert isinstance(result, PlainTextExtractor)

    def test_returns_plain_text_extractor_for_none(self) -> None:
        # Act
        result = create_response_content_extractor(None)

        # Assert
        assert isinstance(result, PlainTextExtractor)
