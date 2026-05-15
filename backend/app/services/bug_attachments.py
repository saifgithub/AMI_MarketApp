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
from uuid import UUID, uuid4

from app.core.config import settings
from app.core.logging import logger


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


def save_attachment(
    *,
    content: bytes,
    mime: str,
    max_bytes: int | None = None,
) -> str:
    """Write `content` to the attachments dir, return the relative filename.

    Raises AttachmentRejected on:
      - unknown / unsupported MIME
      - empty body
      - oversized body (> max_bytes, defaults to settings.bug_attachment_max_bytes)

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
