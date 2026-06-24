from langchain_core.messages import AIMessage

from chat.infrastructure.graph.plain_text_extractor import PlainTextExtractor


class TestPlainTextExtractor:
    def test_extract_returns_string_content(self) -> None:
        # Arrange
        message = AIMessage(content="Hello")
        sut = PlainTextExtractor()

        # Act
        result = sut.extract(message)

        # Assert
        assert result == "Hello"
