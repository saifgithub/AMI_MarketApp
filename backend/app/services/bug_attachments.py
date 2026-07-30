"""Bug-report attachment storage — disk-backed.

Photos attached to in-app bug reports are written to a directory owned
by the api-alpha container (a named docker volume mount in alpha;
tmp_path in tests). The DB stores only the relative filename + MIME,
so a row never points at content the operator can't reach.

No public download endpoint exists in alpha — Saiful reviews
attachments by SSH'ing to melehost and reading the volume directly.
Adding a route is a deliberate future step; until then the data
boundary is "filesystem of melehost", not "the internet".
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Protocol
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.logging import logger


# Streaming chunk size — large enough to amortize syscall overhead, small
# enough that a 5MB cap is detected within one chunk's worth of buffer.
_STREAM_CHUNK_BYTES = 64 * 1024


class _AsyncReadable(Protocol):
    async def read(self, size: int = ...) -> bytes: ...


# MIME → file extension. Allowlist is photo-only at v1; expanding to
# video/PDF means raising the size cap and revisiting the SSH-only
# retrieval workflow.
_ALLOWED_MIMES: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/heic": ".heic",
    "image/heif": ".heif",
    "image/webp": ".webp",
    "image/gif": ".gif",
}


class AttachmentRejected(ValueError):
    """Raised when an upload fails validation (size, MIME, empty body)."""


def is_allowed_mime(mime: str | None) -> bool:
    return mime is not None and mime.lower() in _ALLOWED_MIMES


_ATTACHMENT_SUFFIXES = frozenset(_ALLOWED_MIMES.values())


def _current_total_bytes(target_dir: Path) -> int:
    """Sum of every attachment currently on disk in the attachments dir.

    DEF201 (H9 follow-up): the per-upload cap bounds one file; nothing
    bounded the VOLUME, so the disk filled monotonically at any sustained
    upload rate above zero regardless of the per-file cap. A plain
    `iterdir()` scan is fine at this scale — attachments are flat, no
    nested dirs, and this runs once per upload, not per chunk.

    Filtered to this module's own extensions rather than every file in the
    dir: in alpha the volume is dedicated solely to attachments, but tests
    point `bug_attachments_dir` at the same `tmp_path` the sqlite test-DB
    tempfile lives in (see test_bug_attachments.py's own note on this) — an
    unfiltered scan would count that file as attachment volume.
    """
    if not target_dir.is_dir():
        return 0
    return sum(
        f.stat().st_size for f in target_dir.iterdir()
        if f.is_file() and f.suffix in _ATTACHMENT_SUFFIXES
    )


def save_attachment(
    *,
    content: bytes,
    mime: str,
    max_bytes: int | None = None,
    total_cap_bytes: int | None = None,
) -> str:
    """Write `content` to the attachments dir, return the relative filename.

    Raises AttachmentRejected on:
      - unknown / unsupported MIME
      - empty body
      - oversized body (> max_bytes, defaults to settings.bug_attachment_max_bytes)
      - the attachments dir already at/over its total volume cap (DEF201 —
        defaults to settings.bug_attachments_total_cap_bytes)

    The relative filename is `{uuid}{ext}` — flat, no nested dirs, so
    `ls -la` on the volume is enough to audit recent uploads.
    """
    if not content:
        raise AttachmentRejected("empty upload")
    cap = max_bytes if max_bytes is not None else settings.bug_attachment_max_bytes
    if len(content) > cap:
        raise AttachmentRejected(
            f"upload exceeds {cap} bytes (got {len(content)})"
        )
    mime_lc = (mime or "").lower()
    if mime_lc not in _ALLOWED_MIMES:
        raise AttachmentRejected(f"unsupported MIME type: {mime!r}")

    ext = _ALLOWED_MIMES[mime_lc]
    rel = f"{uuid4().hex}{ext}"

    target_dir = Path(settings.bug_attachments_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        # Container hasn't mounted the volume / dir not writable. Don't
        # mask the bug report itself — caller decides whether to drop
        # the attachment and still persist the text report.
        logger.exception("bug_attachment_dir_unwritable", path=str(target_dir))
        raise AttachmentRejected("attachment storage unavailable")

    # DEF201: reject BEFORE writing — never let the write itself push the
    # volume over the ceiling.
    vcap = (
        total_cap_bytes if total_cap_bytes is not None
        else settings.bug_attachments_total_cap_bytes
    )
    existing_total = _current_total_bytes(target_dir)
    if existing_total + len(content) > vcap:
        logger.warning(
            "bug_attachment_volume_cap_hit",
            existing_total=existing_total,
            incoming=len(content),
            cap=vcap,
        )
        raise AttachmentRejected(
            f"attachment storage total exceeds {vcap} bytes "
            f"(existing {existing_total} + incoming {len(content)})"
        )

    out_path = target_dir / rel
    # Open with O_EXCL to refuse collisions (uuid4 makes this astronomical
    # but the check is cheap and turns a silent overwrite into a crash).
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(content)
    except Exception:
        # Clean up partial write so a retry can succeed.
        try:
            out_path.unlink(missing_ok=True)
        finally:
            raise
    return rel


async def save_attachment_streaming(
    *,
    upload: _AsyncReadable,
    mime: str,
    max_bytes: int | None = None,
    total_cap_bytes: int | None = None,
) -> str:
    """Stream an UploadFile (or any async .read(size)) to disk in 64KB chunks.

    B-tier audit (AT:R37). Mirrors `save_attachment` but never holds the
    full payload in memory — important once the size cap rises past the
    current 5MB, and a useful defence against memory-pressure abuse
    even at today's cap. MIME is validated up-front (no bytes written if
    the type isn't allowed); the running byte counter aborts mid-stream
    on overrun and deletes the partial file.

    Raises AttachmentRejected on:
      - unsupported MIME (no bytes written)
      - empty body (no bytes consumed from the stream)
      - oversized body (mid-stream abort + partial-file cleanup)
      - the attachments dir already at/over its total volume cap (DEF201 —
        checked against the pre-upload total, mid-stream abort + cleanup,
        same shape as the per-file cap)
    """
    cap = max_bytes if max_bytes is not None else settings.bug_attachment_max_bytes
    mime_lc = (mime or "").lower()
    if mime_lc not in _ALLOWED_MIMES:
        raise AttachmentRejected(f"unsupported MIME type: {mime!r}")

    ext = _ALLOWED_MIMES[mime_lc]
    rel = f"{uuid4().hex}{ext}"
    target_dir = Path(settings.bug_attachments_dir)
    try:
        target_dir.mkdir(parents=True, exist_ok=True)
    except PermissionError:
        logger.exception(
            "bug_attachment_dir_unwritable", path=str(target_dir)
        )
        raise AttachmentRejected("attachment storage unavailable")
    out_path = target_dir / rel

    # DEF201: snapshot the volume total ONCE before streaming — re-scanning
    # the dir every chunk would be wasteful, and this file's own bytes
    # aren't part of `existing_total` yet (it doesn't exist until the first
    # `os.open` below), so `existing_total + bytes_written` is exactly the
    # volume this upload would bring the dir to.
    vcap = (
        total_cap_bytes if total_cap_bytes is not None
        else settings.bug_attachments_total_cap_bytes
    )
    existing_total = _current_total_bytes(target_dir)

    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o640)
    bytes_written = 0
    try:
        with os.fdopen(fd, "wb") as f:
            while True:
                chunk = await upload.read(_STREAM_CHUNK_BYTES)
                if not chunk:
                    break
                bytes_written += len(chunk)
                if bytes_written > cap:
                    # Mid-stream abort. Partial file is unlinked in the
                    # except branch below.
                    raise AttachmentRejected(
                        f"upload exceeds {cap} bytes (got {bytes_written}+)"
                    )
                if existing_total + bytes_written > vcap:
                    logger.warning(
                        "bug_attachment_volume_cap_hit",
                        existing_total=existing_total,
                        bytes_written=bytes_written,
                        cap=vcap,
                    )
                    raise AttachmentRejected(
                        f"attachment storage total exceeds {vcap} bytes "
                        f"(existing {existing_total} + {bytes_written}+ this upload)"
                    )
                f.write(chunk)
        if bytes_written == 0:
            # Empty body — drop the placeholder file so a retry can reuse it.
            try:
                out_path.unlink(missing_ok=True)
            finally:
                raise AttachmentRejected("empty upload")
    except Exception:
        # On any failure (cap blown, disk full, etc.) clean up the partial
        # write so a retry can succeed and the volume doesn't accrete junk.
        try:
            out_path.unlink(missing_ok=True)
        finally:
            raise
    return rel


def read_attachment(rel: str) -> tuple[bytes, str] | None:
    """Read back an attachment by relative filename. Returns (bytes, mime)
    or None if the file is missing. Caller responsibility to authorise.

    Provided for future admin tooling; the alpha API doesn't expose this
    over HTTP yet.
    """
    target = Path(settings.bug_attachments_dir) / rel
    if not target.exists():
        return None
    ext = target.suffix.lower()
    for mime, mapped_ext in _ALLOWED_MIMES.items():
        if mapped_ext == ext:
            return target.read_bytes(), mime
    return target.read_bytes(), "application/octet-stream"


# Re-export the allowed MIMEs as a frozen set for callers that just
# want to validate without writing.
ALLOWED_MIMES: frozenset[str] = frozenset(_ALLOWED_MIMES.keys())
