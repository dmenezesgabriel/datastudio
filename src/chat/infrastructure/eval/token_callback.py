"""LangChain callback for counting LLM token usage per pipeline step/node."""

from typing import cast
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import ChatGeneration, LLMResult

from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.graph.observability import step_from_tags


class TokenCountingCallback(BaseCallbackHandler):
    """LangChain callback that extracts LLM token usage and records it per step.

    Attribution prefers the ``step:<name>`` run tag carried by the call (see
    ``graph.observability.step_tag``), captured at run start and keyed by run id so it
    survives parallel ``build_widget`` workers. Untagged calls fall back to
    ``MetricsRecorder.current_node`` (set by TimedNode) — unchanged for the nodes that
    already map one-to-one to an LLM call.

    Example:
        collector = EvalCollector()
        cb = TokenCountingCallback(collector)
        graph.invoke(state, config={"callbacks": [cb]})
    """

    def __init__(self, recorder: MetricsRecorder) -> None:
        """Attach the metrics recorder to this callback."""
        super().__init__()
        self._recorder = recorder
        self._step_by_run: dict[UUID, str] = {}

    def on_chat_model_start(self, *args: object, run_id: UUID, **kwargs: object) -> None:
        """Remember this chat-model run's step tag so its tokens attribute correctly."""
        self._remember_step(run_id, kwargs.get("tags"))

    def on_llm_start(self, *args: object, run_id: UUID, **kwargs: object) -> None:
        """Same as on_chat_model_start, for non-chat completion models."""
        self._remember_step(run_id, kwargs.get("tags"))

    def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        """Extract token counts and record them against the run's step (else current node)."""
        run_id = kwargs.get("run_id")
        step = self._step_by_run.pop(run_id, None) if isinstance(run_id, UUID) else None
        node = step or self._recorder.current_node
        input_t, output_t = _extract_tokens(response)
        if input_t is not None and node:
            self._recorder.record_tokens(node, input_t, output_t or 0)

    def _remember_step(self, run_id: UUID, tags: object) -> None:
        """Record the step tag for a run id when the call carries a string tag list."""
        if not isinstance(tags, list):
            return
        typed = cast(list[object], tags)
        if not all(isinstance(tag, str) for tag in typed):
            return
        step = step_from_tags(cast(list[str], typed))
        if step:
            self._step_by_run[run_id] = step


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
