"""DEF430 MINOR-4 — nothing pinned that the DEF430 sweep is wired into the
FastAPI lifespan.

`policy_notice.notify_policy_update_v2_1`'s own tests
(`test_def430_policy_notice.py`) call the function directly, so they stay
green even if the boot-time call in `app/main.py`'s `lifespan()` is deleted
or never wired up in the first place — the failure mode `failure_patterns.md`
names: a feature that ships, runs dead, and is only discovered months later
because nothing goes red. The only production signal today is a missing
`policy_update_notice_v2_1_complete` log line, which nothing watches.

This enters the REAL app's REAL lifespan (`app.main.app`, as a `TestClient`
context manager — that is what actually runs `async def lifespan`) with
`notify_policy_update_v2_1` monkeypatched to a recorder, per the DEF430
architect brief's stated preference. Every other lifespan startup step
(room-run resume, vLLM prefix-cache check, prompt-version warm cache, the
Sharia/classification/ticker refreshes) is already wrapped in its own
try/except-and-log in `main.py` and is a no-op or fast in the sqlite test
env (no `VLLM_BASE_URL` registers no vLLM provider; no rows means no room
runs to resume) — confirmed empirically: this test runs in a few seconds,
same order of magnitude as any other TestClient-based test in this suite.

Mutation-check: comment out (or monkeypatch away) the
`await asyncio.to_thread(notify_policy_update_v2_1)` call in `main.py`'s
lifespan and this test fails; every other DEF430 test stays green because
they all call the function directly, never through a boot.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import app


def test_lifespan_calls_notify_policy_update_v2_1(monkeypatch) -> None:
    calls: list[bool] = []

    def _recorder() -> dict[str, int]:
        calls.append(True)
        return {"eligible": 0, "notified": 0, "already_notified": 0, "errors": 0}

    # Patched where it is DEFINED, not where main.py imports it: main.py's
    # lifespan does `from app.services.policy_notice import
    # notify_policy_update_v2_1` INSIDE the function body (a late/local
    # import, same style as the other lifespan steps), so it re-resolves the
    # name from the module at call time on every boot rather than binding it
    # once at import time — patching the module attribute is what that late
    # import actually sees.
    monkeypatch.setattr(
        "app.services.policy_notice.notify_policy_update_v2_1", _recorder
    )

    with TestClient(app, raise_server_exceptions=False):
        pass

    assert calls, (
        "app.main's lifespan did not call notify_policy_update_v2_1 — the "
        "DEF430 one-time Privacy Policy v2.1 notice would never be sent on "
        "any real boot, and nothing else in the suite would catch that "
        "(policy_notice's own tests call the function directly, not through "
        "the lifespan)"
    )
