"""WP-38 (CR267) / CR239 - a trace id on EVERY error response, in the log, and on bug reports.

CR239 Leg A already minted one id per request in `HTTPAuditMiddleware`
(`X-Request-Id`, `request_id` in `HTTPException`/500 bodies). This file pins the
WP-38 closure of what Leg A left out - validation 422s, 404/405s, the 413
body cap, the health-check skip path, the version-gate 426, in-stream SSE
`error` events - and the three properties the work package asks for:

1. every error kind carries the SAME id in header and body;
2. the log lines of that request carry that same id (structlog contextvars);
3. a client-supplied id is never adopted (it is `http_audit.id`, a primary key).

Plus the bug-report leg: `trace_ids` on `POST /v1/feedback/bug` is validated,
stored, and shown to the admin console.
"""

from __future__ import annotations

from contextlib import contextmanager
from unittest.mock import patch
from uuid import UUID, uuid4

import pytest
import structlog
from fastapi import FastAPI, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import StreamingResponse

from app.api.sse import sse_text
from app.main import (
    _http_exception_with_request_id,
    _unhandled_exception_with_request_id,
    _validation_error_json_safe,
)
from app.middleware.http_audit import MAX_REQUEST_BODY_BYTES, HTTPAuditMiddleware


class _Payload(BaseModel):
    n: int


def _make_app() -> FastAPI:
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, _http_exception_with_request_id)
    app.add_exception_handler(RequestValidationError, _validation_error_json_safe)
    app.add_exception_handler(Exception, _unhandled_exception_with_request_id)

    @app.get("/rejected")
    async def _rejected():
        structlog.get_logger().info("handler_ran", marker="rejected")
        raise HTTPException(status_code=409, detail="that request wasn't accepted")

    @app.post("/validated")
    async def _validated(payload: _Payload):
        return {"n": payload.n}

    @app.get("/boom")
    async def _boom():
        raise RuntimeError("unhandled")

    @app.get("/v1/health")
    async def _health():
        raise HTTPException(status_code=503, detail="db down")

    @app.get("/stream-error")
    async def _stream_error():
        async def gen():
            yield sse_text("token", "hello")
            yield sse_text("error", "stream broke")

        return StreamingResponse(gen(), media_type="text/event-stream")

    app.add_middleware(HTTPAuditMiddleware)
    return app


def _client() -> TestClient:
    return TestClient(_make_app(), raise_server_exceptions=False)


@pytest.fixture(autouse=True)
def _no_audit_db():
    with patch("app.middleware.http_audit.record_http"):
        yield


def _assert_same_id(r) -> str:
    header_id = r.headers.get("x-request-id")
    assert header_id is not None, "error response has no X-Request-Id header"
    assert r.json()["request_id"] == header_id, "body request_id != header"
    UUID(header_id)
    return header_id


# -- every error kind carries the id in header AND body ------------------------


def test_http_exception_4xx():
    r = _client().get("/rejected")
    assert r.status_code == 409
    _assert_same_id(r)
    assert r.json()["detail"] == "that request wasn't accepted"


def test_validation_422_keeps_detail_and_adds_request_id():
    r = _client().post("/validated", json={"n": "not-an-int"})
    assert r.status_code == 422
    _assert_same_id(r)
    detail = r.json()["detail"]
    assert isinstance(detail, list) and detail[0]["loc"][-1] == "n"


def test_unknown_route_404():
    r = _client().get("/no/such/route")
    assert r.status_code == 404
    _assert_same_id(r)
    assert r.json()["detail"] == "Not Found"


def test_wrong_method_405():
    r = _client().delete("/rejected")
    assert r.status_code == 405
    _assert_same_id(r)


def test_unhandled_exception_500():
    r = _client().get("/boom")
    assert r.status_code == 500
    _assert_same_id(r)
    assert r.json()["detail"] == "internal server error"


def test_health_skip_path_error_still_traceable():
    r = _client().get("/v1/health")
    assert r.status_code == 503
    _assert_same_id(r)


def test_oversized_body_413_carries_the_id():
    r = _client().post(
        "/validated",
        content=b"{}",
        headers={
            "content-type": "application/json",
            "content-length": str(MAX_REQUEST_BODY_BYTES + 1),
        },
    )
    assert r.status_code == 413
    _assert_same_id(r)


def test_sse_error_event_carries_the_short_ref():
    r = _client().get("/stream-error")
    assert r.status_code == 200
    rid = r.headers["x-request-id"]
    assert f"event: error\ndata: stream broke Ref: {rid[:8]}.\n\n" in r.text
    assert "event: token\ndata: hello\n\n" in r.text  # non-error events untouched


def test_sse_error_without_request_context_is_unchanged():
    assert sse_text("error", "x") == "event: error\ndata: x\n\n"
    assert sse_text("token", "x") == "event: token\ndata: x\n\n"


# -- a client-supplied id is never adopted -------------------------------------


@pytest.mark.parametrize("hdr", ["X-Request-Id", "X-Trace-Id", "X-Correlation-Id"])
def test_client_supplied_id_is_ignored(hdr):
    forged = str(uuid4())
    r = _client().get("/rejected", headers={hdr: forged})
    rid = _assert_same_id(r)
    assert rid != forged
    assert forged not in r.text


def test_client_supplied_garbage_cannot_reach_the_response_or_logs():
    evil = "x\nINJECTED " + "A" * 5000
    with _captured_logs() as logs:
        r = _client().get("/rejected", headers={"X-Request-Id": "x" * 4000})
    rid = _assert_same_id(r)
    assert "x" * 100 not in r.text and evil not in r.text
    assert all(e.get("request_id") == rid for e in logs if e["event"] == "handler_ran")


# -- the log line for the request carries the same id --------------------------


@contextmanager
def _captured_logs():
    """Capture structlog output WITH contextvars merged in.

    `structlog.testing.capture_logs()` replaces the whole processor chain, which
    drops `merge_contextvars` - the exact processor that makes the id appear -
    so it cannot test this. Same chain as `core/logging.py`, minus rendering.
    """
    saved = structlog.get_config()
    cap = structlog.testing.LogCapture()
    structlog.configure(
        processors=[structlog.contextvars.merge_contextvars, cap],
        cache_logger_on_first_use=False,
    )
    try:
        yield cap.entries
    finally:
        structlog.configure(**saved)


def test_handler_log_line_carries_the_responses_request_id():
    with _captured_logs() as logs:
        r = _client().get("/rejected")
    rid = _assert_same_id(r)
    ran = [e for e in logs if e["event"] == "handler_ran"]
    assert len(ran) == 1
    assert ran[0]["request_id"] == rid


def test_unhandled_exception_log_line_carries_the_responses_request_id():
    # app.main.logger was bound (and cached) under the production processor
    # chain; hand the handler a fresh one that goes through the capture chain.
    with _captured_logs() as logs, patch("app.main.logger", structlog.get_logger()):
        r = _client().get("/boom")
    rid = _assert_same_id(r)
    crashed = [e for e in logs if e["event"] == "unhandled_exception"]
    assert len(crashed) == 1
    assert crashed[0]["request_id"] == rid


def test_request_id_does_not_leak_into_the_next_requests_logs():
    client = _client()
    with _captured_logs() as logs:
        r1 = client.get("/rejected")
        r2 = client.get("/rejected")
    ids = [e["request_id"] for e in logs if e["event"] == "handler_ran"]
    assert ids == [r1.headers["x-request-id"], r2.headers["x-request-id"]]
    assert ids[0] != ids[1]


# -- the version gate's 426 mints its own id -----------------------------------


def test_426_from_the_version_gate_carries_an_id_in_header_body_and_log():
    from app.middleware.version_gate import VersionGateMiddleware

    class _Floor:
        min_build = 100
        recommended_build = None
        headline = "Update now"

    app = FastAPI()
    app.add_middleware(VersionGateMiddleware)

    @app.get("/v1/x")
    def _x():
        return {"ok": True}

    with patch(
        "app.middleware.version_gate.get_active_floor", return_value=_Floor()
    ), patch("app.middleware.version_gate.resolve_body", return_value="old"), _captured_logs() as logs, patch(
        "app.middleware.version_gate.logger", structlog.get_logger()
    ):
        r = TestClient(app).get("/v1/x", headers={"X-App-Version": "0.1.0+50"})
    assert r.status_code == 426
    rid = r.headers["x-request-id"]
    assert r.json()["request_id"] == rid
    assert r.json()["detail"]["action"] == "block"  # existing shape untouched
    blocked = [e for e in logs if e["event"] == "version_gate_blocked_request"]
    assert blocked and blocked[0]["request_id"] == rid


# -- bug report: trace_ids ------------------------------------------------------


def _req(**kw):
    from app.schemas.feedback import BugReportRequest

    base = dict(
        category="ui_glitch", title="t", app_version="0.1.0+1", platform="ios"
    )
    base.update(kw)
    return BugReportRequest(**base)


def test_trace_ids_parse_normalise_and_dedupe_nothing():
    a, b = str(uuid4()), str(uuid4()).upper()
    req = _req(trace_ids=f" {a} , {b} ,")
    assert req.trace_ids == [a, str(UUID(b))]


def test_trace_ids_absent_or_blank_is_none():
    assert _req().trace_ids is None
    assert _req(trace_ids="").trace_ids is None
    assert _req(trace_ids=" , ").trace_ids is None


@pytest.mark.parametrize(
    "bad", ["not-a-uuid", f"{uuid4()},zzz", "x" * 500, ",".join(str(uuid4()) for _ in range(6))]
)
def test_trace_ids_reject_non_uuid_and_too_many(bad):
    with pytest.raises(Exception):
        _req(trace_ids=bad)


def test_trace_ids_round_trip_through_the_store():
    from app.db import get_session
    from app.db.models import BugReportRow
    from app.services.feedback_store import get_feedback_store

    ids = [str(uuid4()), str(uuid4())]
    resp = get_feedback_store().submit_bug(_req(trace_ids=",".join(ids)), user_id=None)
    with get_session() as s:
        row = s.get(BugReportRow, resp.id)
        assert row.trace_ids == ",".join(ids)
    resp2 = get_feedback_store().submit_bug(_req(), user_id=None)
    with get_session() as s:
        assert s.get(BugReportRow, resp2.id).trace_ids is None


def test_bug_endpoint_accepts_trace_ids_and_422s_a_bad_one(tmp_path, monkeypatch):
    from app.api.feedback import router
    from app.core.config import settings
    from app.db import get_session
    from app.db.models import BugReportRow
    from app.services.rate_limit import bug_upload_rate_limit

    bug_upload_rate_limit.reset()
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    app = FastAPI()
    app.add_exception_handler(StarletteHTTPException, _http_exception_with_request_id)
    app.include_router(router)
    app.add_middleware(HTTPAuditMiddleware)
    client = TestClient(app)
    form = {"category": "crash", "title": "t", "app_version": "0.1.0+1", "platform": "ios"}

    tid = str(uuid4())
    ok = client.post("/v1/feedback/bug", data={**form, "trace_ids": tid})
    assert ok.status_code == 201, ok.text
    with get_session() as s:
        assert s.get(BugReportRow, UUID(ok.json()["id"])).trace_ids == tid

    bad = client.post("/v1/feedback/bug", data={**form, "trace_ids": "nope"})
    assert bad.status_code == 422
    assert bad.json()["request_id"] == bad.headers["x-request-id"]
    bug_upload_rate_limit.reset()


def test_the_real_app_registers_the_handler_for_starlettes_base_exception():
    """Live Alpha, 2026-11-19: an unmatched route's 404 came back as
    `{"detail":"Not Found"}` with no `request_id`. `main.py` registered the
    handler for FastAPI's HTTPException *subclass*, but Starlette's router raises
    the base class for an unmatched route, so the default handler ran. The test
    app above registers the right class itself, so it could not see this."""
    from app.main import app, _http_exception_with_request_id

    assert app.exception_handlers.get(StarletteHTTPException) is _http_exception_with_request_id
