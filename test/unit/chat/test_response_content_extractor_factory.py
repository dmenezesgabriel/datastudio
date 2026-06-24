from chat.infrastructure.plain_text_extractor import PlainTextExtractor
from chat.infrastructure.response_content_extractor_factory import (
    create_response_content_extractor,
)
from chat.infrastructure.thinking_blocks_extractor import ThinkingBlocksExtractor


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
