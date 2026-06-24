from typing import Protocol

from langchain_core.messages import BaseMessage


class ResponseContentExtractorPort(Protocol):
    """Extracts plain text from a LangChain message response.

    Example:
        extractor: ResponseContentExtractorPort = PlainTextExtractor()
        text = extractor.extract(message)
    """

    def extract(self, message: BaseMessage) -> str: ...
