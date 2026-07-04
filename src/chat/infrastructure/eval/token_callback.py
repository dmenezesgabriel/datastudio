"""LangChain callback for counting LLM token usage per pipeline step/node."""

from typing import cast
from uuid import UUID

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import ChatGeneration, LLMResult

from chat.infrastructure.eval.metrics import MetricsRecorder
from chat.infrastructure.graph.step_tags import step_from_tags


class TokenCountingCallback(BaseCallbackHandler):
    """LangChain callback that extracts LLM token usage and records it per step.

    Attribution prefers the ``step:<name>`` run tag carried by the call (see
    ``graph.step_tags.step_tag``), captured at run start and keyed by run id so it
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
        input_t, output_t, cached_t = _extract_tokens(response)
        if input_t is not None and node:
            self._recorder.record_tokens(node, input_t, output_t or 0, cached_t or 0)

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


def _extract_tokens(response: LLMResult) -> tuple[int | None, int | None, int | None]:
    """Return (input, output, cached_input) token counts, or Nones when unavailable.

    ``cached_input`` is the prompt-prefix portion the provider served from its cache —
    a subset of ``input`` (see prompt caching), reported separately so effective/fresh
    input cost is visible without changing what ``input`` means.
    """
    # Strategy 1: llm_output["token_usage"] — most LiteLLM providers
    if response.llm_output:
        usage: dict[str, object] = response.llm_output.get("token_usage") or {}  # pyright: ignore[reportAssignmentType]
        if usage:
            return (
                _as_int(usage.get("prompt_tokens")),
                _as_int(usage.get("completion_tokens")),
                _cached_from_prompt_details(usage.get("prompt_tokens_details")),
            )

    # Strategy 2: AIMessage.usage_metadata — newer LangChain / our GLM provider
    for gen_list in response.generations:
        for gen in gen_list:
            if isinstance(gen, ChatGeneration):
                meta = getattr(gen.message, "usage_metadata", None)
                if meta:
                    typed_meta = cast(dict[str, object], meta)
                    details = cast(dict[str, object], typed_meta.get("input_token_details") or {})
                    return (
                        _as_int(typed_meta.get("input_tokens")),
                        _as_int(typed_meta.get("output_tokens")),
                        _as_int(details.get("cache_read")),
                    )

    return None, None, None


def _as_int(value: object) -> int | None:
    """Return value when it is an int, else None (bools are not treated as ints)."""
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _cached_from_prompt_details(details: object) -> int | None:
    """Read cached-prompt tokens from a litellm ``prompt_tokens_details`` dict or object."""
    if isinstance(details, dict):
        return _as_int(cast(dict[str, object], details).get("cached_tokens"))
    return _as_int(getattr(details, "cached_tokens", None))
