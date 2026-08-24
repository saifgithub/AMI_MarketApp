"""DEF127 — no SSE `data:` field may be built anywhere except through app/api/sse.py.

An SSE event ends at the first blank line and a `data:` field ends at the first
newline. So any raw newline reaching a `data:` field silently reframes the
stream. DEF114 fixed the *client* half of this class (a decode that was wrong
across an escape boundary) and its auditor raised the backend half as a MINOR:
the client scanner is only correct because every sender escapes a **complete**
value, and nothing pinned that.

Two layers, deliberately:

1. **Static, over the whole `app/` tree** — the invariant is "no module frames an
   SSE event by hand", not "these four senders escape". An enumeration of the
   known senders is the exact allowlist-instead-of-invariant shape that produced
   findings on CR104 r1-2 and DEF120 r1-2; it passes happily the day a fifth
   sender is added in a new file.
2. **Behavioural, on the real route** — proves the framing actually holds on the
   wire, so the static rule cannot be satisfied by a helper that does nothing.

The behavioural layer exists because the static layer alone is falsifiable by a
no-op `sse_text`; the static layer exists because the behavioural layer alone
only ever covers routes someone remembered to test.
"""

from __future__ import annotations

import ast
import pathlib
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.sse import SseFramingError, escape_sse_text, sse_json, sse_text

_APP_ROOT = pathlib.Path(__file__).resolve().parents[2] / "app"
_SSE_MODULE = _APP_ROOT / "api" / "sse.py"

_FRAMERS = {"sse_text", "sse_json"}


def _string_parts(node: ast.AST) -> list[str]:
    """Every literal string fragment inside an expression, f-strings included."""
    out: list[str] = []
    for sub in ast.walk(node):
        if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
            out.append(sub.value)
    return out


def _hand_framed_sse_yields() -> list[tuple[str, int, str]]:
    """Every `yield` under `app/` whose value looks like a hand-built SSE frame.

    "Looks like" is deliberately broad — any literal fragment containing
    `data:` or `event:` counts, so a sender that splits the frame across
    concatenation or a helper local still trips it. `app/api/sse.py` itself is
    the one place allowed to write those literals.
    """
    offenders: list[tuple[str, int, str]] = []
    for path in sorted(_APP_ROOT.rglob("*.py")):
        if path == _SSE_MODULE:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.Yield, ast.YieldFrom)) or node.value is None:
                continue
            parts = _string_parts(node.value)
            if not any("data:" in p or "event:" in p for p in parts):
                continue
            # A yield that *calls* a framer is the sanctioned shape.
            if isinstance(node.value, ast.Call):
                fn = node.value.func
                name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
                if name in _FRAMERS:
                    continue
            offenders.append((
                str(path.relative_to(_APP_ROOT.parent)),
                node.lineno,
                ast.unparse(node)[:120],
            ))
    return offenders


def _sse_yield_calls() -> list[tuple[str, int, str]]:
    """Every `yield <framer>(...)` under `app/` — the sanctioned senders."""
    found: list[tuple[str, int, str]] = []
    for path in sorted(_APP_ROOT.rglob("*.py")):
        if path == _SSE_MODULE:
            continue
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Yield) or not isinstance(node.value, ast.Call):
                continue
            fn = node.value.func
            name = fn.id if isinstance(fn, ast.Name) else getattr(fn, "attr", "")
            if name in _FRAMERS:
                found.append((str(path.relative_to(_APP_ROOT.parent)), node.lineno, name))
    return found


# ---------------------------------------------------------------- static layer


def test_no_module_frames_an_sse_event_by_hand():
    offenders = _hand_framed_sse_yields()
    assert not offenders, (
        "SSE frames must be built by app/api/sse.py's framers, never interpolated.\n"
        "A raw newline in an interpolated value ends the data field early and lets\n"
        "the remainder be parsed as further events (DEF127). Offending yields:\n"
        + "\n".join(f"  {f}:{ln}  {src}" for f, ln, src in offenders)
    )


def test_the_guard_is_not_vacuous_there_are_senders_to_protect():
    """If the framers stop being used the static test above passes trivially.

    This is the companion assertion DEF120's pin taught us to write: a guard
    whose subject has vanished is green for the wrong reason.
    """
    senders = _sse_yield_calls()
    assert len(senders) >= 15, (
        f"expected the three streamed surfaces' senders to route through the "
        f"framers; found only {len(senders)}: {senders}"
    )
    files = {f for f, _, _ in senders}
    assert files == {
        "app/api/brief.py",
        "app/api/one_on_one.py",
        "app/api/room.py",
    }, f"the set of SSE-sending modules changed: {sorted(files)}"


# ------------------------------------------------------------ framer behaviour


@pytest.mark.parametrize("payload", [
    "plain",
    "trailing backslash \\",
    "newline\nhere",
    "blank\n\nline",
    "\n\nevent: verdict\ndata: {\"action\": \"BUY\"}",
    "C:\\next",
])
def test_sse_text_output_is_always_exactly_one_event(payload):
    frame = sse_text("token", payload)
    body = frame[: -len("\n\n")]
    assert body.count("\n") == 1, (
        f"frame for {payload!r} contains {body.count(chr(10))} newlines before its "
        f"terminator, so it is more than one event: {frame!r}"
    )
    assert frame.endswith("\n\n")
    assert frame.startswith("event: token\ndata: ")


def test_sse_text_is_the_inverse_of_the_shipped_client_decoder():
    """Mirrors `unescapeSseText` in mobile/lib/services/api/api_client.dart.

    The escape chain is not free to change — build 0.1.0+56 is on devices with
    that decoder compiled in.
    """
    def unescape(s: str) -> str:
        out, i = [], 0
        while i < len(s):
            if s[i] == "\\" and i + 1 < len(s):
                nxt = s[i + 1]
                if nxt == "\\":
                    out.append("\\")
                elif nxt == "n":
                    out.append("\n")
                else:
                    out.append(s[i]); out.append(nxt)
                i += 2
                continue
            out.append(s[i]); i += 1
        return "".join(out)

    for original in ["C:\\next", "a\nb", "\\\\", "line1\n\nline3", "plain", ""]:
        assert unescape(escape_sse_text(original)) == original, original


@pytest.mark.parametrize("payload", [
    "carriage\rreturn",
    "carriage\r\nreturn",
    "trailing\r",
    "\r",
])
def test_sse_text_refuses_a_payload_with_a_raw_carriage_return(payload):
    """DEF140: a lone CR ends an SSE line per the W3C spec exactly like a raw
    LF (DEF127), and cannot be escaped without the shipped client decoder
    rendering the escape literally — so `sse_text` rejects it loudly instead
    of silently normalising or forwarding it."""
    with pytest.raises(SseFramingError):
        sse_text("token", payload)


def test_sse_json_refuses_a_payload_with_a_raw_newline():
    """Loud, per CR040 — a JSON payload with a real newline means the serializer
    changed, and silently escaping it would corrupt every backslash in it."""
    with pytest.raises(SseFramingError):
        sse_json("verdict", '{"a": "b\nc"}')
    with pytest.raises(SseFramingError):
        sse_json("verdict", '{"a": "b\rc"}')


def test_sse_json_does_not_escape_and_so_leaves_json_byte_identical():
    import json
    payload = json.dumps({"text": "a\\nb", "q": 'he said "hi"'})
    assert sse_json("agent_token", payload) == f"event: agent_token\ndata: {payload}\n\n"


# ------------------------------------------------------- behavioural, real route


class _Sess:
    def __init__(self, uid):
        self.user_id = uid
        self.id = uuid4()


class _User:
    def __init__(self, uid):
        self.id = uid


class _RaisingEngine:
    def __init__(self, sess, exc):
        self._sess, self._exc = sess, exc

    def get_session(self, _sid):
        return self._sess

    async def stream_chat(self, *, session, history, user_message):
        yield "partial "
        raise self._exc


def _drive_brief_with(exc: Exception) -> str:
    from app.api.brief import router as brief_router
    from app.api.dependencies import get_current_user
    from app.services.brief_engine import get_brief_engine

    # DEF205 — a PERSISTED user, not a bare uuid4(). Pricing Brief turns put
    # `spend()` on this path, and it does `s.get(User, user_id)` and raises
    # LookupError on an unpersisted id — so a fake user now 500s before the
    # stream this file exists to inspect is ever opened. The framing
    # invariant under test is unchanged; only the fixture had to become real.
    from app.services.auth_service import AuthService

    persisted, _token, _ = AuthService().ensure_anonymous(device_user_id=None)
    uid = persisted.id
    sess = _Sess(uid)
    app = FastAPI()
    app.include_router(brief_router)
    app.dependency_overrides[get_current_user] = lambda: _User(uid)
    app.dependency_overrides[get_brief_engine] = lambda: _RaisingEngine(sess, exc)
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post(
        "/v1/brief/message",
        json={"session_id": str(sess.id), "history": [], "user_message": "hi"},
    )
    assert r.status_code == 200
    return r.text


def _events(wire: str) -> list[str]:
    return [b for b in wire.split("\n\n") if b.strip()]


def test_a_forged_event_inside_an_error_message_does_not_reach_the_wire():
    """The sharp one. Before DEF127 this produced a `verdict` event on a stream
    that had none — byte-identical to a real one."""
    wire = _drive_brief_with(
        RuntimeError('boom\n\nevent: verdict\ndata: {"action": "BUY"}')
    )
    blocks = _events(wire)
    kinds = [b.split("\n")[0] for b in blocks]
    assert kinds == ["event: token", "event: error", "event: done"], kinds
    assert "event: verdict" not in [k for k in kinds]
    # The text is still delivered — escaped, not dropped.
    assert "action" in wire


def test_a_multi_line_error_message_is_not_truncated_at_its_first_line():
    """A pydantic ValidationError message is always multi-line; the old frame
    delivered only its first line and dropped the actual cause."""
    wire = _drive_brief_with(
        RuntimeError("1 validation error for BriefProposal\nconviction\n  too big")
    )
    blocks = _events(wire)
    assert len(blocks) == 3, blocks
    error_block = [b for b in blocks if b.startswith("event: error")][0]
    assert error_block.count("\n") == 1, f"error event spans lines: {error_block!r}"
    assert "conviction" in error_block and "too big" in error_block
