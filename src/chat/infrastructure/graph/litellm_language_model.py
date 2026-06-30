"""LiteLLM-backed language model factory for LangChain."""

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
        """Configure the LiteLLM model connection parameters."""
        self._model_name = model_name
        self._temperature = temperature
        self._api_key = api_key
        self._api_base = api_base

    def get_chat_model(self) -> BaseChatModel:
        """Build and return a configured ChatLiteLLM instance.

        Token-level ``streaming`` is intentionally left off: the API streams at the
        LangGraph node-update granularity (``astream(stream_mode="updates")``),
        which does not need the model to stream, and every graph node uses
        structured output. Forcing ``streaming=True`` adds nothing here and, on
        reasoning models, makes raw ``.invoke()`` return only thinking blocks with
        empty text — so we keep model calls non-streaming for reliable extraction.
        """
        return ChatLiteLLM(
            model=self._model_name,
            temperature=self._temperature,
            api_key=self._api_key,
            api_base=self._api_base,
        )
