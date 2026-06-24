import logging


def get_logger(name: str) -> logging.Logger:
    """Returns the named logger. Requires configure_logging to be called at startup.

    Named loggers propagate to the root logger, which holds the JSON handler
    and level configured by configure_logging.

    Example:
        _logger = get_logger(__name__)
        _logger.info("query executed", extra={"table": "orders", "rows": 42})
    """
    return logging.getLogger(name)
