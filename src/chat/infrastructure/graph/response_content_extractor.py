"""Extract plain text from a LangChain message, per response-content shape.

One cohesive concern: turning a model's ``BaseMessage`` into a plain string. The
``ResponseContentExtractor`` Protocol is the strategy interface; the two concrete
strategies cover the shapes we see (a plain string vs. a list of typed content
blocks), and ``create_response_content_extractor`` selects one by provider base
URL. Kept in one module because these pieces are meaningless apart.
"""

from typing import Protocol

from langchain_core.messages import BaseMessage

_THINKING_BLOCK_PROVIDERS = ("opencode.ai",)


class ResponseContentExtractor(Protocol):
    """Contract for extracting plain text from a LangChain message response.

    Example:
        extractor: ResponseContentExtractor = PlainTextExtractor()
        text = extractor.extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        """Extract plain text from a LangChain message."""
        ...


class PlainTextExtractor:
    """Extracts content from models that return a plain string response.

    Example:
        text = PlainTextExtractor().extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        """Return the message content cast to string."""
        return str(message.content)


class ThinkingBlocksExtractor:
    """Extracts text from models that return content as a list of typed blocks.

    Handles responses from providers like OpenCode Go that include thinking
    blocks alongside text blocks.

    Example:
        text = ThinkingBlocksExtractor().extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        """Extract text blocks, joining multiple blocks with a space."""
        content = message.content
        if isinstance(content, list):
            texts = [b["text"] for b in content if isinstance(b, dict) and b.get("text")]
            return " ".join(texts)
        return str(content)


def create_response_content_extractor(api_base: str | None) -> ResponseContentExtractor:
    """Returns the appropriate extractor for the given provider base URL.

    Example:
        extractor = create_response_content_extractor("https://opencode.ai/zen/go/v1")
        text = extractor.extract(message)
    """
    if api_base and any(p in api_base for p in _THINKING_BLOCK_PROVIDERS):
        return ThinkingBlocksExtractor()
    return PlainTextExtractor()
