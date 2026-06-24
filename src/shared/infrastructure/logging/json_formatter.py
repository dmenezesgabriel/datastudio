import datetime
import json
import logging


class JsonFormatter(logging.Formatter):
    """Formats a LogRecord as a single-line JSON string for structured observability.

    Subclasses may override _build_payload to extend or transform fields (OCP)
    without modifying format().

    Example:
        handler = logging.StreamHandler()
        handler.setFormatter(JsonFormatter())
        logger = logging.getLogger("myapp")
        logger.addHandler(handler)
        logger.info("started", extra={"env": "prod"})
        # {"timestamp": "2026-06-24T17:00:00+00:00", "level": "INFO",
        #  "logger": "myapp", "message": "started", "env": "prod"}
    """

    # Protected: subclasses extending _build_payload may reference this (LSP/OCP).
    _STDLIB_ATTRS: frozenset[str] = frozenset(
        {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "taskName",
            "message",
        }
    )

    def format(self, record: logging.LogRecord) -> str:
        record.message = record.getMessage()
        return json.dumps(self._build_payload(record))

    def _build_payload(self, record: logging.LogRecord) -> dict[str, object]:
        payload: dict[str, object] = {
            "timestamp": self._to_iso_timestamp(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.message,
        }
        payload.update(
            {k: v for k, v in record.__dict__.items() if k not in self._STDLIB_ATTRS}
        )
        exc_info = record.exc_info
        if exc_info is not None and exc_info[0] is not None:
            payload["exception"] = self.formatException(exc_info)
        if record.stack_info:
            payload["stack_info"] = self.formatStack(record.stack_info)
        return payload

    def _to_iso_timestamp(self, created: float) -> str:
        return datetime.datetime.fromtimestamp(
            created, tz=datetime.timezone.utc
        ).isoformat()
