import logging
import sys
from collections.abc import Generator

import pytest

from shared.infrastructure.logging.json_formatter import JsonFormatter
from shared.infrastructure.logging.logging_config import configure_logging


@pytest.fixture(autouse=True)
def _restore_root_logger() -> Generator[None, None, None]:
    root = logging.getLogger()
    original_level = root.level
    original_handlers = list(root.handlers)
    yield
    root.handlers = original_handlers
    root.setLevel(original_level)


class TestConfigureLogging:
    def test_sets_root_logger_to_given_level(self) -> None:
        # Arrange / Act
        configure_logging("WARNING")

        # Assert
        assert logging.getLogger().level == logging.WARNING

    def test_adds_stream_handler_to_root(self) -> None:
        # Arrange / Act
        configure_logging("INFO")

        # Assert
        assert any(
            isinstance(h, logging.StreamHandler) for h in logging.getLogger().handlers
        )

    def test_handler_formatter_is_json_formatter(self) -> None:
        # Arrange / Act
        configure_logging("INFO")

        # Assert
        root = logging.getLogger()
        stream_handlers = [
            h for h in root.handlers if isinstance(h, logging.StreamHandler)
        ]
        assert any(isinstance(h.formatter, JsonFormatter) for h in stream_handlers)

    def test_handler_writes_to_stderr(self) -> None:
        # Arrange / Act
        configure_logging("INFO")

        # Assert
        root = logging.getLogger()
        assert any(
            isinstance(h, logging.StreamHandler) and h.stream is sys.stderr
            for h in root.handlers
        )

    def test_second_call_updates_level_without_adding_handler(self) -> None:
        # Arrange
        configure_logging("DEBUG")
        handler_count_after_first = len(logging.getLogger().handlers)

        # Act
        configure_logging("WARNING")

        # Assert
        root = logging.getLogger()
        assert root.level == logging.WARNING
        assert len(root.handlers) == handler_count_after_first
