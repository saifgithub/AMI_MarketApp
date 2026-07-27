"""Structural guard: the website stack must import ZERO code from `backend/`.

WEBSITE.md's core security decision — a website compromise must never reach
`ami_trade` data — is enforced by *porting* proven code (the vLLM streaming
client, the sliding-window rate limiter, the Resend sender) into `website_api`,
never importing it from the app backend. Prose stated the rule; this test makes
it structural (CR038: prompt instructions are not controls). Any new file under
`website_api/` or `website/` that reaches into `backend/` fails the build here.
"""

from __future__ import annotations

import re
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_WEBSITE_API = _REPO_ROOT / "website_api"
_WEBSITE = _REPO_ROOT / "website"

# `import backend...`, `from backend...`, `from backend.x import`, incl. leading dots.
_BACKEND_IMPORT_RE = re.compile(
    r"^\s*(?:from|import)\s+\.*backend(?:\.|\s|$)", re.M
)


def _python_sources(root: Path) -> list[Path]:
    return [
        p
        for p in root.rglob("*.py")
        if "__pycache__" not in p.parts
        and ".venv" not in p.parts
        and "egg-info" not in str(p)
    ]


def test_website_api_never_imports_backend():
    offenders: list[str] = []
    for src in _python_sources(_WEBSITE_API):
        text = src.read_text(encoding="utf-8")
        for m in _BACKEND_IMPORT_RE.finditer(text):
            line_no = text[: m.start()].count("\n") + 1
            offenders.append(f"{src.relative_to(_REPO_ROOT)}:{line_no}  {m.group(0).strip()}")

    assert not offenders, (
        "website_api imports from backend/ — this breaks WEBSITE.md's isolation "
        "guarantee (a website compromise must not reach ami_trade data). PORT the "
        "code into website_api instead of importing it:\n" + "\n".join(offenders)
    )


def test_website_static_has_no_backend_path_reference():
    """The static site is served as flat files; it must not reference the app
    backend's Python package or its API host either."""
    offenders: list[str] = []
    for src in _WEBSITE.rglob("*.html"):
        if "node_modules" in src.parts:
            continue
        text = src.read_text(encoding="utf-8", errors="ignore")
        # The site talks only to its own isolated api-website host.
        for m in re.finditer(r"api-alpha\.agenticmarketintel\.ai", text):
            line_no = text[: m.start()].count("\n") + 1
            offenders.append(f"{src.relative_to(_REPO_ROOT)}:{line_no}  api-alpha host")

    assert not offenders, (
        "website static files reference the app backend host (api-alpha) — the "
        "site must call only its isolated api-website service:\n" + "\n".join(offenders)
    )
