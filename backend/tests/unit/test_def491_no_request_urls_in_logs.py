"""DEF491 — no outbound request URL (which can carry a provider API key) is logged.

httpx logs `HTTP Request: GET <full url>` at INFO. Alpha Vantage takes its key as
`apikey=` in the query string, so every call wrote the key to the container log.
`configure_logging` now holds the request-URL loggers at WARNING.
"""

import io
import logging

import httpx
import pytest

from app.core.logging import REQUEST_URL_LOGGERS, configure_logging


@pytest.fixture
def production_like_root():
    """Root at INFO with a handler, as in the container; httpx loggers reset."""
    root = logging.getLogger()
    saved_level = root.level
    saved = {n: logging.getLogger(n).level for n in REQUEST_URL_LOGGERS}
    for n in REQUEST_URL_LOGGERS:
        logging.getLogger(n).setLevel(logging.NOTSET)
    buf = io.StringIO()
    handler = logging.StreamHandler(buf)
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    yield buf
    root.removeHandler(handler)
    root.setLevel(saved_level)
    for n, lvl in saved.items():
        logging.getLogger(n).setLevel(lvl)


def test_request_url_loggers_are_held_at_warning(production_like_root):
    configure_logging()
    for name in REQUEST_URL_LOGGERS:
        assert logging.getLogger(name).getEffectiveLevel() >= logging.WARNING, name


def test_a_keyed_request_url_never_reaches_the_log(production_like_root):
    configure_logging()
    transport = httpx.MockTransport(lambda request: httpx.Response(200, json={}))
    with httpx.Client(transport=transport) as client:
        client.get("https://www.alphavantage.co/query", params={"apikey": "SENTINEL-KEY-491"})
    assert "SENTINEL-KEY-491" not in production_like_root.getvalue()
