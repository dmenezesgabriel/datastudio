"""Unit tests for TokenCountingCallback."""

from uuid import UUID, uuid4

from langchain_core.language_models.fake_chat_models import GenericFakeChatModel
from langchain_core.messages import AIMessage, HumanMessage
from langchain_core.outputs import ChatGeneration, LLMResult

from chat.infrastructure.eval.metrics import EvalCollector
from chat.infrastructure.eval.token_callback import TokenCountingCallback, _extract_tokens
from chat.infrastructure.graph.observability import step_tag


def _result_with_usage(prompt: int, completion: int, cached: int | None = None) -> LLMResult:
    """Build an LLMResult with token_usage in llm_output (Strategy 1).

    When ``cached`` is given, it is nested under ``prompt_tokens_details.cached_tokens`` —
    the OpenAI/LiteLLM shape other providers use to report prompt-cache reads.
    """
    usage: dict[str, object] = {"prompt_tokens": prompt, "completion_tokens": completion}
    if cached is not None:
        usage["prompt_tokens_details"] = {"cached_tokens": cached}
    return LLMResult(generations=[], llm_output={"token_usage": usage})


def _result_with_metadata(input_t: int, output_t: int, cache_read: int | None = None) -> LLMResult:
    """Build an LLMResult with usage_metadata on the AIMessage (Strategy 2).

    When ``cache_read`` is given, it is nested under ``input_token_details`` — the
    field the GLM provider populates for prompt-prefix cache hits.
    """
    usage: dict[str, object] = {
        "input_tokens": input_t,
        "output_tokens": output_t,
        "total_tokens": input_t + output_t,
    }
    if cache_read is not None:
        usage["input_token_details"] = {"cache_read": cache_read}
    msg = AIMessage(content="ok", usage_metadata=usage)  # type: ignore[call-arg]
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
        inp, out, cached = _extract_tokens(result)
        assert inp == 450
        assert out == 32
        assert cached is None

    def test_or_empty_dict_handles_none_usage(self) -> None:
        # kills mutmut_2 (`.get("token_usage") and {}` vs `or {}`)
        # When token_usage is None, the `or {}` gives empty dict → returns (None, None)
        result = LLMResult(generations=[], llm_output={"token_usage": None})
        inp, out, cached = _extract_tokens(result)
        # fallback to Strategy 2 or (None, None, None) — not stuck with None dict
        assert (inp, out, cached) == (None, None, None)

    def test_reads_cached_tokens_from_prompt_tokens_details(self) -> None:
        # OpenAI/LiteLLM providers report cache hits under prompt_tokens_details.cached_tokens
        result = _result_with_usage(prompt=450, completion=32, cached=400)
        inp, out, cached = _extract_tokens(result)
        assert inp == 450
        assert out == 32
        assert cached == 400

    def test_no_llm_output_falls_through_to_strategy_2(self) -> None:
        # kills mutmut_1 — if _extract_tokens(None) is called, it crashes;
        # normal case with no llm_output returns (None, None) gracefully
        result = LLMResult(generations=[[]])
        inp, out, cached = _extract_tokens(result)
        assert (inp, out, cached) == (None, None, None)


class TestExtractTokensStrategy2:
    def test_reads_input_and_output_from_usage_metadata(self) -> None:
        # kills mutmut for the Strategy 2 branch (input_tokens, output_tokens keys)
        result = _result_with_metadata(input_t=100, output_t=50)
        inp, out, cached = _extract_tokens(result)
        assert inp == 100
        assert out == 50
        assert cached is None

    def test_reads_cache_read_from_input_token_details(self) -> None:
        # the GLM provider reports prompt-cache hits under input_token_details.cache_read
        result = _result_with_metadata(input_t=604, output_t=20, cache_read=581)
        inp, out, cached = _extract_tokens(result)
        assert inp == 604
        assert out == 20
        assert cached == 581


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

    def test_records_cached_input_tokens_against_the_node(self) -> None:
        # cache-read count from usage_metadata must land on the node's cached_input_tokens
        recorder = EvalCollector()
        recorder.set_node("generate_widget_view")
        cb = TokenCountingCallback(recorder)
        cb.on_llm_end(_result_with_metadata(input_t=604, output_t=20, cache_read=581))
        metrics = recorder.node_metrics["generate_widget_view"]
        assert metrics.input_tokens == 604
        assert metrics.cached_input_tokens == 581

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


class TestStepTagAttribution:
    def test_tagged_run_attributes_to_step_not_current_node(self) -> None:
        # A build_widget sub-step call carries a step tag; its tokens must land on the
        # step, not on whatever node TimedNode marked current.
        recorder = EvalCollector()
        recorder.set_node("build_widget")
        cb = TokenCountingCallback(recorder)
        run_id = uuid4()
        cb.on_chat_model_start({}, [], run_id=run_id, tags=[step_tag("generate_sql")])
        cb.on_llm_end(_result_with_usage(prompt=300, completion=20), run_id=run_id)
        assert recorder.node_metrics["generate_sql"].input_tokens == 300
        # the node entry exists (set_node created it) but carries no LLM tokens
        assert recorder.node_metrics["build_widget"].input_tokens is None

    def test_untagged_run_falls_back_to_current_node(self) -> None:
        recorder = EvalCollector()
        recorder.set_node("select_tables")
        cb = TokenCountingCallback(recorder)
        run_id = uuid4()
        cb.on_chat_model_start({}, [], run_id=run_id, tags=[])
        cb.on_llm_end(_result_with_usage(prompt=90, completion=8), run_id=run_id)
        assert recorder.node_metrics["select_tables"].input_tokens == 90

    def test_concurrent_runs_attribute_independently(self) -> None:
        # Parallel build_widget workers: two runs in flight; each attributes to its own step.
        recorder = EvalCollector()
        recorder.set_node("build_widget")
        cb = TokenCountingCallback(recorder)
        sql_run, view_run = uuid4(), uuid4()
        cb.on_chat_model_start({}, [], run_id=sql_run, tags=[step_tag("generate_sql")])
        cb.on_chat_model_start({}, [], run_id=view_run, tags=[step_tag("generate_widget_view")])
        cb.on_llm_end(_result_with_usage(prompt=300, completion=20), run_id=view_run)
        cb.on_llm_end(_result_with_usage(prompt=500, completion=40), run_id=sql_run)
        assert recorder.node_metrics["generate_sql"].input_tokens == 500
        assert recorder.node_metrics["generate_widget_view"].input_tokens == 300

    def test_on_llm_start_also_captures_step_tag(self) -> None:
        # Non-chat completion models dispatch to on_llm_start, not on_chat_model_start.
        recorder = EvalCollector()
        cb = TokenCountingCallback(recorder)
        run_id = uuid4()
        cb.on_llm_start({}, [], run_id=run_id, tags=[step_tag("repair_sql")])
        cb.on_llm_end(_result_with_usage(prompt=120, completion=10), run_id=run_id)
        assert recorder.node_metrics["repair_sql"].input_tokens == 120

    def test_run_id_is_consumed_after_end(self) -> None:
        # The run→step map must not leak entries across the run's lifecycle.
        recorder = EvalCollector()
        cb = TokenCountingCallback(recorder)
        run_id: UUID = uuid4()
        cb.on_chat_model_start({}, [], run_id=run_id, tags=[step_tag("generate_sql")])
        cb.on_llm_end(_result_with_usage(prompt=10, completion=1), run_id=run_id)
        assert run_id not in cb._step_by_run


class TestStepTagPropagatesThroughLangChain:
    """End-to-end: a real BaseChatModel routed through LangChain's callback machinery.

    Guards against a LangChain upgrade silently changing how ``with_config`` tags reach
    callbacks — which would collapse sub-step attribution back to the node level.
    """

    def test_with_config_tag_attributes_tokens_to_the_step(self) -> None:
        # arrange — a tagged model whose message carries usage metadata
        message = AIMessage(
            content="ok",
            usage_metadata={"input_tokens": 11, "output_tokens": 3, "total_tokens": 14},
        )  # type: ignore[call-arg]
        tagged = GenericFakeChatModel(messages=iter([message])).with_config(
            {"tags": [step_tag("generate_sql")]}
        )
        recorder = EvalCollector()
        recorder.set_node("build_widget")  # the node TimedNode would mark current
        # act
        tagged.invoke(
            [HumanMessage(content="q")],
            config={"callbacks": [TokenCountingCallback(recorder)]},
        )
        # assert — tokens land on the step, not the current node
        assert recorder.node_metrics["generate_sql"].input_tokens == 11
        assert recorder.node_metrics["generate_sql"].output_tokens == 3
        assert recorder.node_metrics["build_widget"].input_tokens is None
