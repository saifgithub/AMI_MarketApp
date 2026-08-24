"""Complementary check (§2D of SOLUTION.md): backend routes with NO
api_client.dart call site at all — the `OptionProposalTicket` shape (a
component shipped, tested, never called), one level up from the
key-presence diff `compare.py` runs.

Uses the same lexical `_dio.<verb>('...')` extraction as `discover_pairs.py`
but keeps every call site (109), not just the 85 that feed a `.fromJson`,
because a route consumed as a raw dict (no `.fromJson` at all) is still a
real caller and must not be flagged as an orphan.

Run from the repo's `backend/` directory with its venv:
    PYTHONPATH=<this dir> backend/.venv/bin/python find_orphan_routes.py
"""
from __future__ import annotations

import json
import re
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
API_CLIENT = REPO / "mobile" / "lib" / "services" / "api" / "api_client.dart"

_VERB_CALL = re.compile(
    r"_dio\s*\.\s*(get|post|put|patch|delete)[^(]*\(\s*['\"]([^'\"]+)['\"]"
)

# Non-mobile-facing by design — never expected to have a client call site.
_EXCLUDE_PREFIXES = ("/v1/admin",)
_EXCLUDE_EXACT = {"/docs", "/openapi.json", "/docs/oauth2-redirect", "/admin"}
_EXCLUDE_SUBSTR = ("webhook",)


def _url_to_regex(url: str) -> str:
    parts = re.split(r"\$\{[^}]+\}|\$\w+", url)
    parts = [re.escape(p) for p in parts]
    return "^" + "[^/]+".join(parts) + "$"


def all_client_calls() -> list[tuple[str, str]]:
    text = API_CLIENT.read_text()
    return [(m.group(1).upper(), m.group(2)) for m in _VERB_CALL.finditer(text)]


def find_orphans() -> list[tuple[str, str]]:
    from app.main import app  # backend on sys.path (run from backend/)

    calls = all_client_calls()
    regexes = [(v, re.compile(_url_to_regex(u))) for v, u in calls]

    routes: set[tuple[str, str]] = set()
    for r in app.router.routes:
        if hasattr(r, "path") and getattr(r, "methods", None):
            for m in r.methods:
                if m in ("GET", "POST", "PUT", "PATCH", "DELETE"):
                    routes.add((m, r.path))

    orphans = []
    for method, path in sorted(routes):
        if path in _EXCLUDE_EXACT:
            continue
        if any(path.startswith(p) for p in _EXCLUDE_PREFIXES):
            continue
        if any(s in path for s in _EXCLUDE_SUBSTR):
            continue
        concrete = re.sub(r"\{[^}]+\}", "X", path)
        if not any(method == v and rx.match(concrete) for v, rx in regexes):
            orphans.append((method, path))
    return orphans


if __name__ == "__main__":
    orphans = find_orphans()
    print(f"{len(orphans)} backend routes with zero api_client.dart call site "
          f"(any form — .fromJson or raw dict), excluding admin/docs/webhooks:\n")
    for m, p in orphans:
        print(f"  {m:6s} {p}")
    Path(__file__).with_name("orphan_routes.json").write_text(
        json.dumps([{"method": m, "path": p} for m, p in orphans], indent=2)
    )
