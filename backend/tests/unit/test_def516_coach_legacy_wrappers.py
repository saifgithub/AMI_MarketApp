"""DEF516: the deprecated /v1/coach/* aliases must match the sync-ness of the Brief handlers they wrap.

The DEF200 ratchet moved several `app.api.brief` handlers from `async def` to plain `def`, so
FastAPI would run them in its threadpool. The legacy wrappers in `app.api.coach` still did
`return await brief_x(...)`, and every one of those routes returned 500 ("object
BriefStartResponse can't be used in 'await' expression"). The check here pairs each wrapper with
the handler it calls, so either side changing alone fails the suite.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

import app.api.brief as brief
import app.api.coach as coach

_COACH_SRC = Path(coach.__file__).read_text()


def _wrapper_calls() -> dict[str, tuple[bool, str, bool]]:
    """wrapper name -> (wrapper is async, brief handler it returns, whether it awaits it)."""
    out: dict[str, tuple[bool, str, bool]] = {}
    for node in ast.parse(_COACH_SRC).body:
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.endswith("_legacy"):
            continue
        for stmt in ast.walk(node):
            if isinstance(stmt, ast.Return) and stmt.value is not None:
                value = stmt.value
                awaited = isinstance(value, ast.Await)
                call = value.value if awaited else value
                if isinstance(call, ast.Call) and isinstance(call.func, ast.Name):
                    out[node.name] = (
                        isinstance(node, ast.AsyncFunctionDef),
                        call.func.id,
                        awaited,
                    )
    return out


def test_every_legacy_wrapper_was_found():
    calls = _wrapper_calls()
    assert len(calls) >= 7, calls


def test_wrapper_awaits_exactly_the_async_handlers():
    for wrapper, (is_async, callee, awaited) in _wrapper_calls().items():
        handler = getattr(brief, callee)
        handler_is_async = inspect.iscoroutinefunction(handler)
        assert awaited == handler_is_async, (
            f"{wrapper} {'awaits' if awaited else 'does not await'} {callee}, "
            f"which is {'async' if handler_is_async else 'sync'}"
        )
        if awaited:
            assert is_async, f"{wrapper} awaits {callee} so it must be async def"
        else:
            assert not is_async, (
                f"{wrapper} wraps sync {callee}; keep it plain def so FastAPI runs it in "
                "the threadpool (DEF200)"
            )
