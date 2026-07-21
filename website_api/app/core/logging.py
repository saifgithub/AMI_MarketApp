"""Minimal structured logger for the website API.

The app backend has a richer structlog setup; website_api is deliberately
standalone, so this is a tiny stdlib wrapper that accepts the same
`logger.info("event", key=value)` call shape the ported modules use.
Never log full message bodies / PII at info level (CR049).
"""

from __future__ import annotations

import logging

_base = logging.getLogger("ami_website")
if not _base.handlers:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    _base.addHandler(_handler)
    _base.setLevel(logging.INFO)


class _Logger:
    def _fmt(self, event: str, **kw: object) -> str:
        if not kw:
            return event
        parts = " ".join(f"{k}={v}" for k, v in kw.items())
        return f"{event} {parts}"

    def info(self, event: str, **kw: object) -> None:
        _base.info(self._fmt(event, **kw))

    def warning(self, event: str, **kw: object) -> None:
        _base.warning(self._fmt(event, **kw))

    # alias used by some ported code
    warn = warning

    def error(self, event: str, **kw: object) -> None:
        _base.error(self._fmt(event, **kw))


logger = _Logger()
