"""Structural guard: no blocking network-bound call reachable from an
`async def` route handler without an intervening `asyncio.to_thread`.

`backend/app` runs one uvicorn process with no `--workers` flag (single
event loop — see `backend/Dockerfile`'s CMD). A synchronous yfinance /
`SimEngine.current_*` / `build_*_block` / `_profile_for_ticker` call made
directly from an `async def` route handler (or anything it calls) parks
that one event loop for the whole network round-trip — stalling every
other user's SSE stream, LLM token relay, and unrelated API call on the
same process. This fired on every Room convene and every 1-on-1 turn
mentioning a ticker (DEF116).

This is the SAME CLASS `website_api/tests/test_no_blocking_io_in_async_routes.py`
guards against for `website_api` (found by audit, CR049 round 1, MAJOR).
Per CLAUDE.md, a second occurrence of a failure class earns a guard, not
just a fix — this test walks the static call graph from every `async def`
route handler under `backend/app/api/` and fails the build if it reaches
one of the known sync network-bound leaves via a DIRECT call (i.e. the
leaf name is called, not merely passed by reference as the first
positional argument to `asyncio.to_thread`).

Deliberately does NOT flag `sim.py`'s `quotes_batch` — that route already
farms its N-ticker fan-out out via `loop.run_in_executor`, a different
(and already-correct) pattern for a different problem (parallel fetch,
not the single-fetch blocking bug this guards against).

Does NOT cover the Alpaca snapshot pattern (`alpaca_service.py:77,113`
via `alpaca_snapshot_text`, called from `room_runner.py` /
`agent_runner.py`) — identical bug shape (sync `httpx.get`/`.post`),
found incidentally by DEF116 but out of scope pending its own decision
(DEF116 hand-off D4). See the note below `_YFINANCE_BLOCKING_ATTRS` for
why httpx detection isn't included here.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[3]
_APP = _REPO_ROOT / "backend" / "app"

# Sync, network-bound leaves per DEF116's re-derived call-site table:
# yfinance-fetching SimEngine accessors, the per-ticker context-block
# builders (each does its own yfinance/Reddit/news fetch), and the Room's
# per-ticker profile builder. Matched by call *name* only (attribute attr
# or bare name) — best-effort, consistent with the website_api guard this
# adapts; fine for this codebase's size.
_BLOCKING_LEAF_METHOD_NAMES = {
    "current_quote",
    "current_history",
    "current_news",
    "current_earnings",
}
_BLOCKING_LEAF_FUNC_NAMES = {
    "build_live_data_block",
    "build_news_context_block",
    "build_social_context_block",
    "build_technicals_context_block",
    "_profile_for_ticker",
}
_YFINANCE_MODULE_NAMES = {"yf", "yfinance"}
_YFINANCE_BLOCKING_ATTRS = {"Ticker", "download"}

# NOTE: deliberately does NOT also detect bare `httpx.get/post/...` the way
# website_api's guard does. `backend/app` is large enough that the same
# name-based cross-module resolution this guard uses (matching by bare
# call-name, e.g. `.attr`) collides with unrelated same-named methods —
# `get`/`post` are also SQLAlchemy `Session.get`, several `*_store.get`
# key-value lookups, etc. — and the walk explodes into a wall of bogus
# "chains" through totally unrelated code (verified: adding this detection
# produced 10+ false "offenders" rooted in `_resolve_url`/`get_engine`/
# `*_store.get`, none of which are actually an httpx call). A safe httpx
# detector for a call graph this size needs real type resolution, which is
# out of scope for this lane. This means the Alpaca `httpx.get/post` chain
# (`alpaca_service.py:77,113` via `alpaca_snapshot_text` — DEF116 D4) is
# NOT caught by this guard; it is flagged by name in the DEF116 hand-off
# instead, not enforced structurally here.

# NOT in DEF116's re-derived call-site table, but found by this guard the
# first time it was run against the full route surface: SimEngine's own
# trade-execution / portfolio-valuation methods call `self.current_quote`
# synchronously *internally* (via `_marks_with_quotes` / `current_marks` /
# `current_price`), and are themselves called directly (no `to_thread`)
# from `get_portfolio`, `reset_portfolio`, `preview_trade`, `submit_trade`,
# `evaluate_trades`, `close_trade`, `audit_holdings`, `sector_allocation`,
# and `stream_room`'s sector-context build (`_build_room_sector_context`).
# Same bug class as DEF116, wider blast radius than the table above —
# but the table is what this lane is scoped to fix (CLAUDE.md: don't
# silently widen scope). Flagged explicitly in the DEF116 hand-off as a
# follow-up-defect candidate; waived by name here, narrowly, so it doesn't
# block DEF116's own acceptance while staying visible (grep this set) —
# NOT silently suppressed. Removing a name here without fixing its call
# site should turn this guard red again.
_WAIVED_CALL_CHAIN_NAMES = {
    "current_marks",
    "current_marks_with_source",
    "_marks_with_quotes",
    "current_price",
    "preview",
    "submit",
    "evaluate_outcomes",
    "manual_close",
    "_build_room_sector_context",
}


def _iter_py(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


class _ModuleInfo:
    """One module's function defs (any nesting depth, name-keyed)."""

    def __init__(self, path: Path, tree: ast.Module):
        self.path = path
        self.functions: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {}
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node


def _to_thread_wrapped_call_ids(fn: ast.AST) -> set[int]:
    """id() of every `ast.Call` node that is itself the first positional
    argument of an `asyncio.to_thread(...)` call — i.e. correctly deferred,
    not a violation even though it shares a name with a blocking leaf.

    In practice a leaf is passed by *reference* (`asyncio.to_thread(fn, x)`),
    not called (`asyncio.to_thread(fn(x))`), so this rarely fires — it's a
    defensive no-op for a shape this guard doesn't expect to see rather than
    dead code: cheap insurance against a future refactor changing the call
    shape and silently going green.
    """
    wrapped: set[int] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        is_to_thread = (
            isinstance(f, ast.Attribute)
            and f.attr == "to_thread"
            and isinstance(f.value, ast.Name)
            and f.value.id == "asyncio"
        )
        if is_to_thread and node.args and isinstance(node.args[0], ast.Call):
            wrapped.add(id(node.args[0]))
    return wrapped


def _blocking_call_sites(fn: ast.AST) -> list[str]:
    """Direct (un-deferred) calls to a known blocking leaf inside fn."""
    hits: list[str] = []
    wrapped = _to_thread_wrapped_call_ids(fn)
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or id(node) in wrapped:
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in _BLOCKING_LEAF_FUNC_NAMES:
            hits.append(f.id)
        elif isinstance(f, ast.Attribute) and f.attr in _BLOCKING_LEAF_METHOD_NAMES:
            hits.append(f"<obj>.{f.attr}")
        elif (
            isinstance(f, ast.Attribute)
            and f.attr in _YFINANCE_BLOCKING_ATTRS
            and isinstance(f.value, ast.Name)
            and f.value.id in _YFINANCE_MODULE_NAMES
        ):
            hits.append(f"{f.value.id}.{f.attr}")
    return hits


def _called_names(fn: ast.AST) -> set[str]:
    """Bare names and attribute-call tails invoked inside fn (best-effort,
    name-based resolution across modules — fine for this codebase's size)."""
    names: set[str] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if isinstance(f, ast.Name):
            names.add(f.id)
        elif isinstance(f, ast.Attribute):
            names.add(f.attr)
    return names


def _route_handlers(modules: list[_ModuleInfo]) -> list[tuple[_ModuleInfo, ast.AsyncFunctionDef]]:
    handlers = []
    for mod in modules:
        if "api" not in mod.path.parts:
            continue
        for name, fn in mod.functions.items():
            if not isinstance(fn, ast.AsyncFunctionDef):
                continue
            is_route = any(
                isinstance(d, ast.Call)
                and isinstance(d.func, ast.Attribute)
                and d.func.attr in {"get", "post", "put", "patch", "delete"}
                for d in fn.decorator_list
            )
            if is_route:
                handlers.append((mod, fn))
    return handlers


def _find_blocking_reachable(
    fn: ast.AST, modules: list[_ModuleInfo], seen: set[int]
) -> list[str]:
    if id(fn) in seen:
        return []
    seen.add(id(fn))

    offenders = _blocking_call_sites(fn)
    for called_name in _called_names(fn):
        if called_name in _WAIVED_CALL_CHAIN_NAMES:
            continue
        for mod in modules:
            target = mod.functions.get(called_name)
            if target is not None and target is not fn:
                offenders += [
                    f"{o} (via {called_name} in {mod.path.relative_to(_REPO_ROOT)})"
                    for o in _find_blocking_reachable(target, modules, seen)
                ]
    return offenders


def test_no_blocking_leaf_call_reachable_from_async_route():
    modules = [_ModuleInfo(p, ast.parse(p.read_text())) for p in _iter_py(_APP)]
    handlers = _route_handlers(modules)
    assert handlers, "no async route handlers found under backend/app/api — guard is not exercising anything"

    offenders: list[str] = []
    for mod, fn in handlers:
        hits = _find_blocking_reachable(fn, modules, seen=set())
        offenders += [
            f"{mod.path.relative_to(_REPO_ROOT)}:{fn.name} -> {h}" for h in hits
        ]

    assert not offenders, (
        "async def route handler(s) can reach a synchronous, network-bound "
        "leaf call (yfinance / SimEngine.current_* / build_*_block / "
        "_profile_for_ticker) with no intervening `asyncio.to_thread` — this "
        "blocks the single event loop for the whole network round-trip on a "
        "no-`--workers` uvicorn process (DEF116, same class as CR049). Wrap "
        "the call site: `await asyncio.to_thread(<leaf>, ...)`, never make "
        "the leaf itself `async def` (breaks its monkeypatch.setattr unit "
        "tests):\n" + "\n".join(offenders)
    )
