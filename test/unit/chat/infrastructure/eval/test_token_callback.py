"""Unit tests for TokenCountingCallback."""

from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from chat.infrastructure.eval.metrics import EvalCollector
from chat.infrastructure.eval.token_callback import TokenCountingCallback, _extract_tokens


def _result_with_usage(prompt: int, completion: int) -> LLMResult:
    """Build an LLMResult with token_usage in llm_output (Strategy 1)."""
    return LLMResult(
        generations=[],
        llm_output={"token_usage": {"prompt_tokens": prompt, "completion_tokens": completion}},
    )


def _result_with_metadata(input_t: int, output_t: int) -> LLMResult:
    """Build an LLMResult with usage_metadata on the AIMessage (Strategy 2)."""
    msg = AIMessage(
        content="ok",
        usage_metadata={
            "input_tokens": input_t,
            "output_tokens": output_t,
            "total_tokens": input_t + output_t,
        },
    )  # type: ignore[call-arg]
    return LLMResult(generations=[[ChatGeneration(message=msg)]])


def _result_empty() -> LLMResult:
    """Build an LLMResult with no token info."""
    return LLMResult(generations=[[]])


class TestTokenCountingCallbackInit:
    def test_recorder_is_stored(self) -> None:
        # kills __init____mutmut_1 (self._recorder = None instead of recorder)
        recorder = EvalCollector()
        cb = TokenCountingCallback(recorder)
        assert cb._recorder is recorder


class TestExtractTokensStrategy1:
    def test_returns_prompt_and_completion_from_llm_output(self) -> None:
        # kills _extract_tokens mutmut_1 (None), mutmut_3 ("token_usage" → None key)
        # and mutmut_4/5 (key name corruption)
        result = _result_with_usage(prompt=450, completion=32)
        inp, out = _extract_tokens(result)
        assert inp == 450
        assert out == 32

    def test_or_empty_dict_handles_none_usage(self) -> None:
        # kills mutmut_2 (`.get("token_usage") and {}` vs `or {}`)
        # When token_usage is None, the `or {}` gives empty dict → returns (None, None)
        result = LLMResult(generations=[], llm_output={"token_usage": None})
        inp, out = _extract_tokens(result)
        # fallback to Strategy 2 or (None, None) — not stuck with None dict
        assert (inp, out) == (None, None)

    def test_no_llm_output_falls_through_to_strategy_2(self) -> None:
        # kills mutmut_1 — if _extract_tokens(None) is called, it crashes;
        # normal case with no llm_output returns (None, None) gracefully
        result = LLMResult(generations=[[]])
        inp, out = _extract_tokens(result)
        assert (inp, out) == (None, None)


class TestExtractTokensStrategy2:
    def test_reads_input_and_output_from_usage_metadata(self) -> None:
        # kills mutmut for the Strategy 2 branch (input_tokens, output_tokens keys)
        result = _result_with_metadata(input_t=100, output_t=50)
        inp, out = _extract_tokens(result)
        assert inp == 100
        assert out == 50


class TestOnLlmEnd:
    def test_records_tokens_when_current_node_is_set(self) -> None:
        # kills on_llm_end mutmut_1 (_extract_tokens(None)) and mutmut_2 (None return)
        # and mutmut_5 (recorder.record_tokens(None, ...) — node=None)
        recorder = EvalCollector()
        recorder.set_node("generate_sql")
        cb = TokenCountingCallback(recorder)
        cb.on_llm_end(_result_with_usage(prompt=200, completion=40))
        metrics = recorder.node_metrics["generate_sql"]
        assert metrics.input_tokens == 200
        assert metrics.output_tokens == 40

    def test_skips_recording_when_current_node_is_empty(self) -> None:
        # kills on_llm_end mutmut_3 (and → or) which would record even without node
        recorder = EvalCollector()
        # current_node is "" (default) — no node set
        cb = TokenCountingCallback(recorder)
        cb.on_llm_end(_result_with_usage(prompt=200, completion=40))
        assert recorder.node_metrics == {}

    def test_skips_recording_when_tokens_are_none(self) -> None:
        # kills on_llm_end mutmut_4 (is None → is not None) — records when input_t is None
        recorder = EvalCollector()
        recorder.set_node("generate_sql")
        cb = TokenCountingCallback(recorder)
        cb.on_llm_end(_result_empty())
        # No token info → nothing recorded
        assert recorder.node_metrics.get("generate_sql") is None or (
            recorder.node_metrics["generate_sql"].input_tokens is None
        )

    def test_output_tokens_defaults_to_zero_when_none(self) -> None:
        # kills on_llm_end mutmut for `output_t or 0`
        # Build result where completion_tokens key is missing
        result = LLMResult(
            generations=[],
            llm_output={"token_usage": {"prompt_tokens": 100}},  # no completion_tokens
        )
        recorder = EvalCollector()
        recorder.set_node("gen")
        cb = TokenCountingCallback(recorder)
        cb.on_llm_end(result)
        assert recorder.node_metrics["gen"].output_tokens == 0
        assert recorder.node_metrics["gen"].input_tokens == 100
