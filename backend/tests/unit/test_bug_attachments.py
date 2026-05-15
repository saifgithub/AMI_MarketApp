"""Tests for bug-report attachment storage + the multipart submit API."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.config import settings
from app.services.bug_attachments import (
    ALLOWED_MIMES,
    AttachmentRejected,
    is_allowed_mime,
    read_attachment,
    save_attachment,
)


@pytest.fixture(autouse=True)
def _isolated_attachments_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point bug_attachments_dir at a tempdir per-test — no real disk writes."""
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))


# ── is_allowed_mime ─────────────────────────────────────────────────────


def test_allowed_mime_accepts_common_phone_formats():
    assert is_allowed_mime("image/jpeg")
    assert is_allowed_mime("image/png")
    assert is_allowed_mime("image/heic")
    assert is_allowed_mime("image/webp")


def test_allowed_mime_is_case_insensitive():
    assert is_allowed_mime("IMAGE/JPEG")


def test_allowed_mime_rejects_video_pdf_text():
    assert not is_allowed_mime("video/mp4")
    assert not is_allowed_mime("application/pdf")
    assert not is_allowed_mime("text/plain")
    assert not is_allowed_mime(None)


# ── save_attachment ─────────────────────────────────────────────────────


def test_save_writes_file_and_returns_relative_name(tmp_path: Path):
    rel = save_attachment(content=b"\x89PNG\r\n\x1a\n" + b"x" * 100, mime="image/png")
    assert rel.endswith(".png")
    written = tmp_path / rel
    assert written.exists()
    assert written.read_bytes().startswith(b"\x89PNG")


def test_save_picks_extension_from_mime(tmp_path: Path):
    rel_jpg = save_attachment(content=b"\xff\xd8\xff" + b"x" * 50, mime="image/jpeg")
    rel_heic = save_attachment(content=b"x" * 50, mime="image/heic")
    assert rel_jpg.endswith(".jpg")
    assert rel_heic.endswith(".heic")


def test_save_rejects_empty_body():
    with pytest.raises(AttachmentRejected, match="empty"):
        save_attachment(content=b"", mime="image/png")


def test_save_rejects_unknown_mime():
    with pytest.raises(AttachmentRejected, match="unsupported"):
        save_attachment(content=b"x" * 100, mime="application/pdf")


def test_save_rejects_oversized():
    with pytest.raises(AttachmentRejected, match="exceeds"):
        save_attachment(content=b"x" * 1024, mime="image/png", max_bytes=512)


def test_save_two_uploads_get_distinct_paths(tmp_path: Path):
    a = save_attachment(content=b"x" * 100, mime="image/png")
    b = save_attachment(content=b"x" * 100, mime="image/png")
    assert a != b
    assert (tmp_path / a).exists() and (tmp_path / b).exists()


# ── read_attachment ─────────────────────────────────────────────────────


def test_read_returns_bytes_and_mime():
    rel = save_attachment(content=b"\x89PNG" + b"x" * 50, mime="image/png")
    result = read_attachment(rel)
    assert result is not None
    data, mime = result
    assert data.startswith(b"\x89PNG")
    assert mime == "image/png"


def test_read_missing_returns_none():
    assert read_attachment("nonexistent.png") is None


# ── ALLOWED_MIMES export ────────────────────────────────────────────────


def test_allowed_mimes_export_is_frozen():
    """Callers expect a frozenset they can safely cache."""
    assert isinstance(ALLOWED_MIMES, frozenset)
    assert "image/jpeg" in ALLOWED_MIMES
