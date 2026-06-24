from langchain_core.language_models import BaseChatModel
from langchain_litellm import ChatLiteLLM


class LiteLLMLanguageModel:
    """LiteLLM-backed language model for use with LangChain and LangGraph.

    Example:
        model = LiteLLMLanguageModel(
            model_name="openai/deepseek-v4-flash",
            api_key="sk-...",
            api_base="https://opencode.ai/zen/go/v1",
        )
        chat_model = model.get_chat_model()
    """

    def __init__(
        self,
        model_name: str,
        temperature: float = 0.0,
        api_key: str | None = None,
        api_base: str | None = None,
    ) -> None:
        self._model_name = model_name
        self._temperature = temperature
        self._api_key = api_key
        self._api_base = api_base

    def get_chat_model(self) -> BaseChatModel:
        return ChatLiteLLM(
            model=self._model_name,
            temperature=self._temperature,
            api_key=self._api_key,
            api_base=self._api_base,
        )
