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
    save_attachment_streaming,
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


# ── save_attachment_streaming (B-tier audit, AT:R37) ────────────────────


class _FakeUpload:
    """Mimics FastAPI's UploadFile.read(size) async interface from an
    in-memory blob — gives us deterministic chunk replay without spinning
    a TestClient."""

    def __init__(self, payload: bytes):
        self._buf = payload
        self._pos = 0

    async def read(self, size: int = -1) -> bytes:
        if self._pos >= len(self._buf):
            return b""
        if size is None or size < 0:
            chunk = self._buf[self._pos :]
            self._pos = len(self._buf)
            return chunk
        chunk = self._buf[self._pos : self._pos + size]
        self._pos += len(chunk)
        return chunk


async def test_streaming_writes_full_payload(tmp_path: Path):
    payload = b"\x89PNG\r\n\x1a\n" + b"x" * 200_000  # ~200 KB — multiple chunks
    rel = await save_attachment_streaming(
        upload=_FakeUpload(payload), mime="image/png",
    )
    on_disk = (tmp_path / rel).read_bytes()
    assert on_disk == payload


async def test_streaming_rejects_oversized_mid_stream(tmp_path: Path):
    """Cap is 256 bytes; payload is 1 KB. The function must abort partway
    through (not after reading the whole thing) and leave no file behind."""
    payload = b"x" * 1024
    with pytest.raises(AttachmentRejected, match="exceeds"):
        await save_attachment_streaming(
            upload=_FakeUpload(payload),
            mime="image/png",
            max_bytes=256,
        )
    # No partial attachment should remain (the sqlite DB file from conftest
    # also lives in tmp_path; filter to attachment extensions only).
    leftovers = [p for p in tmp_path.iterdir() if p.suffix in {".png", ".jpg", ".heic", ".heif", ".webp", ".gif"}]
    assert leftovers == []


async def test_streaming_rejects_empty_body(tmp_path: Path):
    with pytest.raises(AttachmentRejected, match="empty"):
        await save_attachment_streaming(
            upload=_FakeUpload(b""), mime="image/png",
        )
    leftovers = [p for p in tmp_path.iterdir() if p.suffix in {".png", ".jpg", ".heic", ".heif", ".webp", ".gif"}]
    assert leftovers == []


async def test_streaming_rejects_unsupported_mime_without_touching_disk(
    tmp_path: Path,
):
    with pytest.raises(AttachmentRejected, match="unsupported"):
        await save_attachment_streaming(
            upload=_FakeUpload(b"x" * 100), mime="application/pdf",
        )
    leftovers = [p for p in tmp_path.iterdir() if p.suffix in {".png", ".jpg", ".heic", ".heif", ".webp", ".gif"}]
    assert leftovers == []


async def test_streaming_picks_extension_from_mime(tmp_path: Path):
    rel = await save_attachment_streaming(
        upload=_FakeUpload(b"\xff\xd8\xff" + b"y" * 50), mime="image/jpeg",
    )
    assert rel.endswith(".jpg")
