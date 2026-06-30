"""Proxy node that emits structured logs for every graph node without modifying them."""

import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Protocol, cast

from chat.domain.value_objects.chat_state import ChatState
from shared.domain.value_objects.query_result import QueryResult
from shared.infrastructure.logging.logger_factory import get_logger

_logger = get_logger(__name__)

_SKIP_FIELDS: frozenset[str] = frozenset({"schema"})
_RESPONSE_TRUNCATE_LEN = 500


class _ChatNode(Protocol):
    def __call__(self, state: ChatState) -> Mapping[str, object]: ...


def _extract_log_safe_fields(result: Mapping[str, object]) -> dict[str, object]:
    """Return a log-safe summary of a node result dict.

    Skips large fields (schema), extracts scalar summaries from complex values
    (QueryResult → row_count, view_lines → patch count), and truncates long strings.

    Example:
        _extract_log_safe_fields({"query_result": QueryResult(...), "sql_error": ""})
        # → {"row_count": 5, "sql_error": ""}
    """
    out: dict[str, object] = {}
    for key, value in result.items():
        if key in _SKIP_FIELDS:
            continue
        if isinstance(value, QueryResult):
            out["row_count"] = value.row_count
        elif key == "view_lines" and isinstance(value, list):
            out["view_patch_count"] = len(cast(list[object], value))
        elif isinstance(value, str) and len(value) > _RESPONSE_TRUNCATE_LEN:
            out[key] = value[:_RESPONSE_TRUNCATE_LEN]
        else:
            out[key] = value
    return out


class ObservableNode:
    """Proxy that wraps any ChatNode and emits one structured log event per call.

    Records wall-clock duration, propagates ``request_id`` from ChatState, and
    emits WARNING when the result contains a non-empty ``sql_error`` so log
    queries can filter failures without parsing message text.

    Example:
        node = ObservableNode("generate_sql", GenerateSql(model))
        result = node(state)
        # → logs generate_sql.complete with request_id and duration_ms
    """

    def __init__(self, name: str, inner: _ChatNode) -> None:
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
