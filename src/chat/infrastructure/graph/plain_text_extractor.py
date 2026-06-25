"""Response content extractor for plain-text model outputs."""

from langchain_core.messages import BaseMessage


class PlainTextExtractor:
    """Extracts content from models that return a plain string response.

    Example:
        text = PlainTextExtractor().extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        """Return the message content cast to string."""
        return str(message.content)
