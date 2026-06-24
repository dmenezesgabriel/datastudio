from typing import Protocol

from langchain_core.language_models import BaseChatModel


class LanguageModelPort(Protocol):
    """Provides a configured LangChain chat model.

    Example:
        model: LanguageModelPort = LiteLLMLanguageModel(model_name="gpt-4o")
        chat_model = model.get_chat_model()
    """

    def get_chat_model(self) -> BaseChatModel: ...
