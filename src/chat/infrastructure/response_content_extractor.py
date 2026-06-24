from typing import Protocol

from langchain_core.messages import BaseMessage


class ResponseContentExtractor(Protocol):
    """Contract for extracting plain text from a LangChain message response.

    Example:
        extractor: ResponseContentExtractor = PlainTextExtractor()
        text = extractor.extract(message)
    """

    def extract(self, message: BaseMessage) -> str: ...
