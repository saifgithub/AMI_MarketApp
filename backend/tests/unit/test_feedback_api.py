"""End-to-end tests for POST /v1/feedback/bug — multipart submit + attachment."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.feedback import router as feedback_router
from app.core.config import settings
from app.services.rate_limit import bug_upload_rate_limit


@pytest.fixture(autouse=True)
def _reset_bug_upload_rate_limit():
    # DEF186: /v1/feedback/bug is now rate-limited (5/hour/IP) — without a
    # reset, tests in this module would share one IP's budget and later
    # tests would flake with 429 instead of exercising their own scenario.
    bug_upload_rate_limit.reset()
    yield
    bug_upload_rate_limit.reset()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    app = FastAPI()
    app.include_router(feedback_router)
    return TestClient(app)


_BASE_FORM: dict = {
    "category": "ui_glitch",
    "title": "Badge overlaps price",
    "app_version": "0.1.0+5",
    "platform": "ios",
}


def test_submit_text_only_still_works(client: TestClient):
    """Backwards compatibility: the form-only submit (no file) still creates
    a row and returns 201 with attachment_path=None."""
    r = client.post("/v1/feedback/bug", data=_BASE_FORM)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "open"
    assert body["attachment_path"] is None


def test_submit_with_photo_returns_attachment_path(
    client: TestClient, tmp_path: Path,
):
    files = {"file": ("screenshot.png", b"\x89PNG\r\n\x1a\n" + b"x" * 100, "image/png")}
    r = client.post("/v1/feedback/bug", data=_BASE_FORM, files=files)
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["attachment_path"] is not None
    assert body["attachment_path"].endswith(".png")
    # File is actually on disk under the tempdir.
    assert (tmp_path / body["attachment_path"]).exists()


def test_submit_with_empty_file_is_treated_as_no_attachment(client: TestClient):
    """Some pickers return an empty file when the user cancels — don't
    reject the whole report over that."""
    files = {"file": ("empty.png", b"", "image/png")}
    r = client.post("/v1/feedback/bug", data=_BASE_FORM, files=files)
    assert r.status_code == 201, r.text
    assert r.json()["attachment_path"] is None


def test_submit_rejects_unsupported_mime(client: TestClient):
    files = {"file": ("doc.pdf", b"%PDF-1.4" + b"x" * 100, "application/pdf")}
    r = client.post("/v1/feedback/bug", data=_BASE_FORM, files=files)
    assert r.status_code == 415, r.text


def test_submit_rejects_oversized(
    client: TestClient, monkeypatch: pytest.MonkeyPatch,
):
    monkeypatch.setattr(settings, "bug_attachment_max_bytes", 512)
    files = {"file": ("big.png", b"x" * 2048, "image/png")}
    r = client.post("/v1/feedback/bug", data=_BASE_FORM, files=files)
    assert r.status_code == 413, r.text


def test_submit_rejects_missing_required_form_field(client: TestClient):
    form = dict(_BASE_FORM)
    del form["title"]
    r = client.post("/v1/feedback/bug", data=form)
    assert r.status_code == 422
