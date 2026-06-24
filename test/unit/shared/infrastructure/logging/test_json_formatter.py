import logging
import sys


from shared.infrastructure.logging.json_formatter import JsonFormatter

import json


def make_record(
    name: str = "test.logger",
    level: int = logging.INFO,
    msg: str = "test message",
    args: tuple[object, ...] = (),
    extra: dict[str, object] | None = None,
) -> logging.LogRecord:
    record = logging.LogRecord(name, level, "", 0, msg, args, None)
    if extra:
        for k, v in extra.items():
            setattr(record, k, v)
    return record


class TestJsonFormatterRequiredFields:
    def test_output_is_valid_json(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act / Assert
        json.loads(formatter.format(record))  # must not raise

    def test_timestamp_is_iso8601_utc(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["timestamp"].endswith("+00:00")

    def test_level_key_contains_level_name(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(level=logging.INFO)

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["level"] == "INFO"

    def test_logger_key_contains_logger_name(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(name="test.logger")

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["logger"] == "test.logger"

    def test_message_key_matches_log_message(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(msg="test message")

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["message"] == "test message"


class TestJsonFormatterMessageInterpolation:
    def test_format_args_are_interpolated(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(msg="user %s", args=("alice",))

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["message"] == "user alice"


class TestJsonFormatterExtraFields:
    def test_extra_string_field_appears_in_output(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(extra={"request_id": "abc"})

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["request_id"] == "abc"

    def test_extra_integer_field_appears_in_output(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record(extra={"count": 7})

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert parsed["count"] == 7

    def test_stdlib_attrs_do_not_appear_as_extras(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        for attr in ("lineno", "filename", "module", "threadName", "processName"):
            assert attr not in parsed


class TestJsonFormatterExceptionHandling:
    def test_no_exception_key_without_exc_info(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert "exception" not in parsed

    def test_exception_key_present_with_exc_info(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        try:
            raise ValueError("boom")
        except ValueError:
            exc_info = sys.exc_info()
        record = logging.LogRecord("t", logging.ERROR, "", 0, "err", (), exc_info)

        # Act
        parsed = json.loads(formatter.format(record))

        # Assert
        assert "exception" in parsed
        assert "ValueError" in parsed["exception"]


class TestJsonFormatterOutputShape:
    def test_output_is_single_line(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act
        output = formatter.format(record)

        # Assert
        assert "\n" not in output

    def test_timestamp_is_first_key(self) -> None:
        # Arrange
        formatter = JsonFormatter()
        record = make_record()

        # Act
        output = formatter.format(record)

        # Assert
        assert output.startswith('{"timestamp"')
