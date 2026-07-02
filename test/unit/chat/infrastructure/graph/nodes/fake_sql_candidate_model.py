from types import SimpleNamespace
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import PrivateAttr


class _SequencedRunnable:
    """Returns successive ``sql`` values across invocations, clamping to the last."""

    def __init__(self, sqls: list[str]) -> None:
        self._sqls = sqls or [""]
        self._calls = 0
        self.all_messages: list[list[Any]] = []

    def with_config(self, *args: Any, **kwargs: Any) -> "_SequencedRunnable":
        """Honor the Runnable surface (tags/config are irrelevant to scripted replay)."""
        return self

    def invoke(self, messages: list[Any], *args: Any, **kwargs: Any) -> SimpleNamespace:
        self.all_messages.append(messages)
        index = min(self._calls, len(self._sqls) - 1)
        self._calls += 1
        return SimpleNamespace(sql=self._sqls[index])


class FakeSqlCandidateModel(BaseChatModel):
    """Fake chat model that yields a preset sequence of SQL strings.

    Use when a node calls the model multiple times and each call must return a
    different query (e.g. the multi-candidate repair fallback).

    Usage:
        model = FakeSqlCandidateModel(["BAD SQL", "GOOD SQL"])
        RepairSql(model, engine)(state)
    """

    _runnable: _SequencedRunnable = PrivateAttr()

    def __init__(self, sqls: list[str]) -> None:
        super().__init__()
        self._runnable = _SequencedRunnable(sqls)

    @property
    def runnable(self) -> _SequencedRunnable:
        return self._runnable

    def with_structured_output(self, schema: Any, **kwargs: Any) -> _SequencedRunnable:
        return self._runnable

    def _generate(
        self, messages: Any, stop: Any = None, run_manager: Any = None, **kwargs: Any
    ) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=""))])

    @property
    def _llm_type(self) -> str:
        return "fake-sql-candidate"
