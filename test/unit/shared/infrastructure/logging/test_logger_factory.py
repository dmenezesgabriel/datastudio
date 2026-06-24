import logging

from shared.infrastructure.logging.logger_factory import get_logger


class TestGetLogger:
    def test_returns_logging_logger_instance(self) -> None:
        # Arrange / Act
        logger = get_logger("test.get_logger.type")

        # Assert
        assert isinstance(logger, logging.Logger)

    def test_returns_logger_with_given_name(self) -> None:
        # Arrange / Act
        logger = get_logger("my.module")

        # Assert
        assert logger.name == "my.module"

    def test_propagates_to_root_by_default(self) -> None:
        # Arrange / Act
        logger = get_logger("test.get_logger.propagate")

        # Assert
        assert logger.propagate is True
