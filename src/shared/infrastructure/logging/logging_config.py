import logging
import sys

from shared.infrastructure.logging.json_formatter import JsonFormatter


def configure_logging(log_level: str) -> None:
    """Wires the root logger with JSON output to stderr at the given level.

    Must be called once at application startup before any logging occurs.
    Idempotent: a second call updates the level but does not add duplicate handlers.

    Example:
        settings = AppSettings()
        configure_logging(settings.log_level)
    """
    root = logging.getLogger()
    root.setLevel(log_level)
    already_configured = any(
        isinstance(h.formatter, JsonFormatter) for h in root.handlers
    )
    if not already_configured:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)
