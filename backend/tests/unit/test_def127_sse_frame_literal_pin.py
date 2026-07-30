"""Auditor pin (DEF127) — broader than the lane's static guard: no string
literal ANYWHERE under `app/` may look like an SSE frame fragment, docstrings
excepted. The lane's `test_no_module_frames_an_sse_event_by_hand` inspects only
`yield` expressions, and an auditor probe (M6) proved a hand-framed sender that
builds the frame into a local and yields it bare passes the whole suite green:

    frame = f"event: error\\ndata: {text}\\n\\n"
    yield frame

This pin closes that shape: a frame under construction must contain a newline
AND a field marker (`data:` / `event:`) in the same literal, so flagging any
non-docstring string constant with both catches inline yields, helper-variable
frames, and frames assembled in a return — independent of where the value ends
up. Parsers are unaffected: `llm_gateway.py`'s `"data: "` literals contain no
newline.

Residual, honestly: a sender concatenating single-line fragments
(`"event: x" + "\\n" + "data: " + msg`) still evades — no literal holds both
markers. That shape is unnatural next to the f-string idiom every historical
violation used; the behavioural layer and the choke-point convention cover what
AST literals cannot.

Run (needs the backend venv + rootdir; not on the tests/unit auto-run path):
  cp orchestration/audit/regression/test_def127_sse_frame_literal_pin.py \
     backend/tests/unit/ && cd backend && \
  "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" \
    -m pytest tests/unit/test_def127_sse_frame_literal_pin.py -q
Verified: PASS at f644b5c (DEF127 fix merged); RED with the M6 helper-variable
sender in room.py; RED at pre-fix 8199f63^ (the three interpolated error
senders the fix removed).
"""
from __future__ import annotations

import ast
import pathlib

_APP_ROOT = pathlib.Path(__file__).resolve().parents[2] / "app"
_SSE_MODULE = _APP_ROOT / "api" / "sse.py"


def _docstring_ids(tree: ast.AST) -> set[int]:
    """id() of every docstring constant — prose may quote frame shapes."""
    ids: set[int] = set()
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if (
            isinstance(body, list)
            and body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            ids.add(id(body[0].value))
    return ids


def test_no_string_literal_under_app_looks_like_an_sse_frame():
    offenders: list[str] = []
    for path in sorted(_APP_ROOT.rglob("*.py")):
        if path == _SSE_MODULE:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        docstrings = _docstring_ids(tree)
        for node in ast.walk(tree):
            if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
                continue
            if id(node) in docstrings:
                continue
            v = node.value
            if "\n" in v and ("data:" in v or "event:" in v):
                offenders.append(
                    f"  {path.relative_to(_APP_ROOT.parent)}:{node.lineno}  {v[:60]!r}"
                )
    assert not offenders, (
        "A string literal under app/ holds a newline AND an SSE field marker — "
        "a frame being built outside app/api/sse.py (DEF127, auditor M6 probe "
        "shape). Route it through sse_text/sse_json. Offenders:\n"
        + "\n".join(offenders)
    )


def test_the_pin_is_not_vacuous_it_scans_modules():
    """A pin that scanned nothing is green for the wrong reason (DEF120)."""
    scanned = [p for p in _APP_ROOT.rglob("*.py") if p != _SSE_MODULE]
    assert len(scanned) >= 50, f"expected to scan the app tree, found {len(scanned)}"
