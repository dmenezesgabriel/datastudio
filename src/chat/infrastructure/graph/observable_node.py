"""Proxy node that emits structured logs for every graph node without modifying them."""

import logging
from collections.abc import Mapping
from time import perf_counter
from typing import cast

from chat.infrastructure.graph.chat_state import ChatState
from chat.infrastructure.graph.types import TypedChatNode
from shared.domain.value_objects.query_result import QueryResult
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_SKIP_FIELDS: frozenset[str] = frozenset({"schema"})
_RESPONSE_TRUNCATE_LEN = 500

# Orchestrator–workers aggregation channels: each holds non-JSON-native value
# objects (WidgetResult/WidgetSpec) or verbose patch lists, so they are reduced to
# a scalar count under a summary key rather than logged verbatim.
_CHANNEL_COUNT_KEYS: dict[str, str] = {
    "widget_results": "widget_count",
    "widget_views": "view_patch_count",
    "widget_specs": "planned_widget_count",
}


def _summarize_field(key: str, value: object) -> tuple[str, object]:
    """Reduce one node-result field to a log-safe ``(key, value)`` pair.

    QueryResult collapses to its row_count, an aggregation channel to its length,
    and a long string is truncated; anything else passes through unchanged.
    """
    if isinstance(value, QueryResult):
        return "row_count", value.row_count
    count_key = _CHANNEL_COUNT_KEYS.get(key)
    if count_key is not None and isinstance(value, list):
        return count_key, len(cast(list[object], value))
    if isinstance(value, str) and len(value) > _RESPONSE_TRUNCATE_LEN:
        return key, value[:_RESPONSE_TRUNCATE_LEN]
    return key, value


def _extract_log_safe_fields(result: Mapping[str, object]) -> dict[str, object]:
    """Return a log-safe summary of a node result dict.

    Keeps non-JSON-native value objects (QueryResult, and the WidgetResult/WidgetSpec
    aggregation channels) out of the JSON log formatter by summarizing each field via
    ``_summarize_field``, and skips large fields (schema).

    Example:
        _extract_log_safe_fields({"widget_results": [WidgetResult(...)], "response": "hi"})
        # → {"widget_count": 1, "response": "hi"}
    """
    out: dict[str, object] = {}
    for key, value in result.items():
        if key in _SKIP_FIELDS:
            continue
        out_key, out_value = _summarize_field(key, value)
        out[out_key] = out_value
    return out


class ObservableNode:
    """Proxy that wraps any ``TypedChatNode`` and emits one structured log event per call.

    Records wall-clock duration, propagates ``request_id`` from ChatState, and
    emits WARNING when the result contains a non-empty ``sql_error`` so log
    queries can filter failures without parsing message text.

    Example:
        node = ObservableNode("generate_sql", GenerateSql(model))
        result = node(state)
        # → logs generate_sql.complete with request_id and duration_ms
    """

    def __init__(self, name: str, inner: TypedChatNode) -> None:
        """Wire the node name and the inner callable."""
        self._name = name
        self._inner = inner

    def __call__(self, state: ChatState) -> Mapping[str, object]:
        """Delegate to the inner node and emit a structured completion event."""
        request_id = cast(dict[str, object], state).get("request_id", "")
        t0 = perf_counter()
        result = self._inner(state)
        duration_ms = round((perf_counter() - t0) * 1000)

        fields = _extract_log_safe_fields(result)
        is_error = bool(result.get("sql_error"))
        level = logging.WARNING if is_error else logging.INFO
        _logger.log(
            level,
            f"{self._name}.complete",
            extra={"request_id": request_id, "duration_ms": duration_ms, **fields},
        )
        return result
