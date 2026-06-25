"""LangChain callback for counting LLM token usage per graph node."""

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import ChatGeneration, LLMResult

from chat.infrastructure.eval.metrics import MetricsRecorder


class TokenCountingCallback(BaseCallbackHandler):
    """LangChain callback that extracts LLM token usage and records it per node.

    Relies on MetricsRecorder.current_node being set by TimedNode before each
    inner node call, ensuring tokens are attributed to the correct node.

    Example:
        collector = EvalCollector()
        cb = TokenCountingCallback(collector)
        graph.invoke(state, config={"callbacks": [cb]})
    """

    def __init__(self, recorder: MetricsRecorder) -> None:
        """Attach the metrics recorder to this callback."""
        super().__init__()
        self._recorder = recorder

    def on_llm_end(self, response: LLMResult, **_kwargs: object) -> None:
        """Extract token counts from the LLM response and record them."""
        input_t, output_t = _extract_tokens(response)
        if input_t is not None and self._recorder.current_node:
            self._recorder.record_tokens(self._recorder.current_node, input_t, output_t or 0)


def _extract_tokens(response: LLMResult) -> tuple[int | None, int | None]:
    # Strategy 1: llm_output["token_usage"] — most LiteLLM providers
    if response.llm_output:
        usage: dict[str, int] = response.llm_output.get("token_usage") or {}  # pyright: ignore[reportAssignmentType]
        if usage:
            return usage.get("prompt_tokens"), usage.get("completion_tokens")

    # Strategy 2: AIMessage.usage_metadata — newer LangChain / some providers
    for gen_list in response.generations:
        for gen in gen_list:
            if isinstance(gen, ChatGeneration):
                meta = getattr(gen.message, "usage_metadata", None)
                if meta:
                    return meta.get("input_tokens"), meta.get("output_tokens")

    return None, None
