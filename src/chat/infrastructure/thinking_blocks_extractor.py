from langchain_core.messages import BaseMessage


class ThinkingBlocksExtractor:
    """Extracts text from models that return content as a list of typed blocks.

    Handles responses from providers like OpenCode Go that include thinking
    blocks alongside text blocks.

    Example:
        text = ThinkingBlocksExtractor().extract(message)
    """

    def extract(self, message: BaseMessage) -> str:
        content = message.content
        if isinstance(content, list):
            texts = [b["text"] for b in content if isinstance(b, dict) and b.get("text")]
            return " ".join(texts)
        return str(content)
