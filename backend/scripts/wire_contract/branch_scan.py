"""ISS002/CR208 — does the server have ANY branch that emits this key?

**This module is the Dilemma's one mandatory correction, and it exists because
the winning prototype's single reported FAIL was a false positive.**

`SimSubmitResult` reads `j['order']`. Across 21 observed `/v1/sim/submit`
responses, `order` never appeared, so the prototype reported a FAIL. Verified by
hand at judging: `backend/app/api/sim.py` **does** send `order` — on the
`resting: True` branch only, and none of the 21 captured submissions rested.
Both sides were correct.

The general defect: **observation proves presence, never absence.** A key that
is absent from every capture is indistinguishable from a key the server never
sends at all. Left unfixed, the guard's very first output is a false alarm, and
a guard that cries wolf gets ignored — the exact end-state ISS002 exists to
prevent.

So a missing key becomes a `FAIL` only when the server source shows no branch
emitting it anywhere. Where a branch does exist, the honest answer is
`UNVERIFIED` — the same third state the pipeline already uses well elsewhere,
and the one DEF169/DEF190 require instead of a silent pass.

**What this deliberately is not.** It does not attempt to prove the branch is
reachable, or that it is the branch the client expects. It answers exactly one
question — *is there a place in the server that could emit this key?* — and a
`yes` downgrades the finding rather than clearing it. Claiming more from a
lexical scan than that would be manufacturing the same certainty this module
exists to withdraw.
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
API_DIR = REPO / "backend" / "app" / "api"
SCHEMA_DIRS = (
    REPO / "backend" / "app" / "schemas",
    REPO / "backend" / "app" / "models",
    REPO / "backend" / "app" / "services",
)


def _emit_patterns(key: str) -> list[re.Pattern[str]]:
    """Every way this codebase spells "this response carries `key`".

    Kept explicit rather than one catch-all regex so each pattern can be read
    and argued with. A `key` appearing merely as a local variable name is NOT
    an emission and must not match — that would make the downgrade fire for
    anything, which is worse than no correction at all.
    """
    k = re.escape(key)
    return [
        re.compile(rf"""["']{k}["']\s*:"""),        # dict literal:  "order": ...
        re.compile(rf"""\b{k}\s*=\s*[^=]"""),        # pydantic field / kwarg: order=...
        re.compile(rf"""^\s*{k}\s*:\s*\w""", re.M),  # model attribute decl: order: Order
        re.compile(rf"""\[["']{k}["']\]\s*="""),    # payload["order"] = ...
        re.compile(rf"""\.update\(\s*\{{[^}}]*["']{k}["']"""),
    ]


@lru_cache(maxsize=1)
def _server_text() -> str:
    """One concatenated blob of everything that could shape a response body.

    Routes alone are not enough: most bodies are pydantic models declared
    elsewhere, so a key emitted only as a model field would look absent and the
    correction would fail to correct anything.
    """
    chunks: list[str] = []
    for d in (API_DIR, *SCHEMA_DIRS):
        if not d.exists():
            continue
        for p in sorted(d.rglob("*.py")):
            try:
                chunks.append(p.read_text(encoding="utf-8"))
            except OSError:
                continue
    return "\n".join(chunks)


def server_may_emit(key: str) -> bool:
    """Is there any branch, model field or literal that could put `key` on the wire?"""
    if not key:
        return False
    text = _server_text()
    return any(p.search(text) for p in _emit_patterns(key))


def classify_missing(keys: list[str]) -> tuple[list[str], list[str]]:
    """Split absent keys into (genuinely_absent, branch_conditional).

    `genuinely_absent` is what may be reported as a FAIL. `branch_conditional`
    is what must be reported as UNVERIFIED — the server can emit it, this run
    simply never took that path.
    """
    absent: list[str] = []
    conditional: list[str] = []
    for key in keys:
        (conditional if server_may_emit(key) else absent).append(key)
    return sorted(absent), sorted(conditional)
