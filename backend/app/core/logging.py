"""Structured JSON logging via structlog."""

import logging
import sys

import structlog

REQUEST_URL_LOGGERS = ("httpx", "httpcore")


def configure_logging() -> None:
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=logging.INFO)
    # DEF491: httpx/httpcore log every request URL at INFO, and several data
    # providers take their API key as a query parameter (Alpha Vantage
    # `apikey=`), so the key was written to the container log on every call.
    for name in REQUEST_URL_LOGGERS:
        logging.getLogger(name).setLevel(logging.WARNING)

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


logger = structlog.get_logger()
