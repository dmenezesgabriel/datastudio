from chat.infrastructure.graph.response_content_extractor import (
    PlainTextExtractor,
    ThinkingBlocksExtractor,
    create_response_content_extractor,
)


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
