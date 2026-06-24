from langchain_core.messages import BaseMessage


class PlainTextExtractor:
    """Extracts content from models that return a plain string response.

    Example:
        text = PlainTextExtractor().extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        return str(message.content)
