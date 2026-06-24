from langchain_core.messages import AIMessage

from chat.infrastructure.graph.thinking_blocks_extractor import ThinkingBlocksExtractor


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
