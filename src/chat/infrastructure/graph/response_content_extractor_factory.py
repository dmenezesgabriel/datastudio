from chat.infrastructure.graph.plain_text_extractor import PlainTextExtractor
from chat.infrastructure.graph.response_content_extractor import (
    ResponseContentExtractor,
)
from chat.infrastructure.graph.thinking_blocks_extractor import ThinkingBlocksExtractor

_THINKING_BLOCK_PROVIDERS = ("opencode.ai",)


def create_response_content_extractor(api_base: str | None) -> ResponseContentExtractor:
    """Returns the appropriate extractor for the given provider base URL.

    Example:
        extractor = create_response_content_extractor("https://opencode.ai/zen/go/v1")
        text = extractor.extract(message)
    """
    if api_base and any(p in api_base for p in _THINKING_BLOCK_PROVIDERS):
        return ThinkingBlocksExtractor()
    return PlainTextExtractor()
