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

# DEF120 (closed): the 9 chains below this comment used to be waived here —
# SimEngine's trade-execution / portfolio-valuation methods called
# `self.current_quote` synchronously *internally* (via `_marks_with_quotes` /
# `current_marks` / `current_price`), reached directly (no `to_thread`) from
# `get_portfolio`, `reset_portfolio`, `preview_trade`, `submit_trade`,
# `evaluate_trades`, `close_trade`, `audit_holdings`, `sector_allocation`.
# Fixed two ways: (1) `_marks_with_quotes` now fans out over a
# `concurrent.futures.ThreadPoolExecutor` instead of calling `current_quote`
# directly in a loop, so the leaf is passed by reference, not called — same
# by-reference exemption `asyncio.to_thread` gets (see
# `_blocking_call_sites`'s docstring); (2) every route above now wraps its
# whole sync call in `await asyncio.to_thread(...)`, which is the actual
# fix — (1) alone still blocks the event loop for the `pool.map()` wait if
# the route calls it inline, unwrapped. All 9 names deleted from this set.
#
# `_build_room_sector_context` is the ONE surviving waiver (DEF120 D7):
# reached from `stream_room` via `room_runner.py:1435`'s
# `build_journal_entry_for_run(...)` → `_build_room_sector_context(user_id)`
# (`room_runner.py:1912`), aliased in `room.py:76` as
# `_build_journal_entry = build_journal_entry_for_run` and called by that
# alias — which is genuinely still a blocking `current_quote` reach, but
# `room_runner.py` was explicitly out of scope for this lane (CR104-ROOM
# owns it concurrently) and must NOT be touched here. Flagged for the
# Architect to lane against the Room queue.
#
# Note for whoever picks that up: the alias means this specific chain is
# ALSO invisible to `_offending_routes(waived=set())` below — `_called_names`
# resolves by literal call-site name, and the call site uses `_build_journal_entry`
# (room.py:76's alias target), not `build_journal_entry_for_run`, so the walk
# never finds a module function named `_build_journal_entry` to recurse into.
# `_DEF120_KNOWN_BLOCKING_PAIRS` is therefore genuinely empty (not merely
# "waived") — the walker can't see this pair even with zero waivers. That is
# a guard blind spot, not evidence the bug is fixed; don't let an empty pin
# set read as "nothing left". `_build_room_sector_context` staying in this
# waiver set is what keeps that fact visible (grep this set).
_WAIVED_CALL_CHAIN_NAMES = {
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


def _blocking_call_sites(fn: ast.AST) -> list[str]:
    """Direct (un-deferred) calls to a known blocking leaf inside fn.

    NOTE — there is deliberately NO exemption for a leaf appearing as
    `asyncio.to_thread`'s first positional argument. An earlier revision
    exempted that shape as "correctly deferred"; the round-1 auditor proved
    the exemption inverted with probe P-E: `asyncio.to_thread(sim.current_quote(t))`
    passed the guard while genuinely blocking the event loop (the leaf is
    called inline, *then* its result is handed to `to_thread`) and raising
    `TypeError` in the worker because a `Quote` is not callable. Passing a
    *called* leaf to `to_thread` is never correct, so it must be flagged, not
    waived. The correct shape passes the leaf by reference —
    `asyncio.to_thread(sim.current_quote, t)` — where the leaf is an
    `ast.Name`/`ast.Attribute` argument and never an `ast.Call`, so it is
    invisible to this walk anyway.
    """
    hits: list[str] = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
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
    fn: ast.AST, modules: list[_ModuleInfo], seen: set[int], waived: set[str]
) -> list[str]:
    if id(fn) in seen:
        return []
    seen.add(id(fn))

    offenders = _blocking_call_sites(fn)
    for called_name in _called_names(fn):
        if called_name in waived:
            continue
        for mod in modules:
            target = mod.functions.get(called_name)
            if target is not None and target is not fn:
                offenders += [
                    f"{o} (via {called_name} in {mod.path.relative_to(_REPO_ROOT)})"
                    for o in _find_blocking_reachable(target, modules, seen, waived)
                ]
    return offenders


def _offending_routes(waived: set[str]) -> tuple[list[str], set[str]]:
    """(full offender chains, set of `<route> -> <leaf>` pairs) for a waiver.

    The second element deliberately drops the `(via …)` chain suffix: the
    intermediate hop list is unstable under harmless refactors, while the
    `route -> leaf` pair is the thing that actually characterises a violation.
    """
    modules = [_ModuleInfo(p, ast.parse(p.read_text())) for p in _iter_py(_APP)]
    handlers = _route_handlers(modules)
    assert handlers, "no async route handlers found under backend/app/api — guard is not exercising anything"

    offenders: list[str] = []
    pairs: set[str] = set()
    for mod, fn in handlers:
        hits = _find_blocking_reachable(fn, modules, seen=set(), waived=waived)
        root = f"{mod.path.relative_to(_REPO_ROOT)}:{fn.name}"
        for h in hits:
            offenders.append(f"{root} -> {h}")
            pairs.add(f"{root} -> {h.split(' (via ')[0]}")
    return offenders, pairs


# DEF120 (closed): empty. The 9 known blocking pairs (mandate.py:audit_holdings,
# portfolio.py:sector_allocation, room.py:stream_room, and 6 sim.py handlers,
# all `-> <obj>.current_quote`) are gone — every route now wraps its call in
# `await asyncio.to_thread(...)`. Genuinely empty, not "waived down to
# empty": see the `_build_room_sector_context` note above
# `_WAIVED_CALL_CHAIN_NAMES` for the one real remaining offender this
# empty-waiver walk still cannot see (a call-site alias, not a fix).
_DEF120_KNOWN_BLOCKING_PAIRS: set[str] = set()


def test_waived_chains_still_pin_the_known_offender_set():
    """The waiver must hide DEF120 and NOTHING ELSE.

    Round-1 audit finding (MAJOR): `_WAIVED_CALL_CHAIN_NAMES` prunes the whole
    subtree by bare function name, so a blocking call added *inside* a waived
    function is invisible to the main guard. Mutation-proved by the auditor — a
    fresh `self.current_news(...)` in `SimEngine.submit`, reachable from
    `POST /sim/trade`, left the main guard green. A guard that goes green on a
    genuinely new regression is worse than no guard (this project's
    DEF038/DEF063 lesson in a different costume).

    This companion runs the same walk with an EMPTY waiver and pins the result
    to exactly the known DEF120 pairs. DEF120 stays waived in the main guard,
    while any new `route -> leaf` pair turns this red. Closing DEF120 means
    deleting the waiver names AND shrinking this set to empty.
    """
    _, pairs = _offending_routes(waived=set())

    unexpected = pairs - _DEF120_KNOWN_BLOCKING_PAIRS
    assert not unexpected, (
        "NEW blocking route/leaf pair(s) not covered by DEF120 — a synchronous, "
        "network-bound leaf is reachable from an async route through one of the "
        "waived call chains, where the main guard cannot see it. Fix the call "
        "site with `await asyncio.to_thread(<leaf>, ...)`:\n"
        + "\n".join(sorted(unexpected))
    )

    fixed = _DEF120_KNOWN_BLOCKING_PAIRS - pairs
    assert not fixed, (
        "pair(s) listed as known-blocking under DEF120 are no longer blocking — "
        "good news, but this set is now stale and must shrink to match, or it "
        "will keep masking a future regression on them:\n" + "\n".join(sorted(fixed))
    )


# Every synchronous `httpx.<verb>(` call site under backend/app, pinned by
# inventory rather than by reachability. Round-1 audit finding (MINOR): the
# live Alpaca pair is the identical blocking-I/O class but was held only by a
# docstring comment. The auditor independently confirmed WHY it cannot ride the
# call-graph walk — adding `httpx.<verb>` detection to the traversal produced
# 85 offender chains, all bogus, because name-based resolution of bare
# `.get`/`.post` collides with `Session.get`, `*_store.get`, `_resolve_url`,
# etc. So this is a non-graph inventory pin instead: a NEW sync httpx call
# anywhere under backend/app turns it red, no reachability needed.
#
# Keyed by FILE and COUNT, not file:line (DEF122). The first revision pinned
# `file:lineno`, which made the guard fire on any unrelated edit *above* a
# pinned site: CR098-ROOM added ~146 lines to room_runner.py and the same
# untouched `httpx.get` moved :2618 -> :2764, reporting a "NEW" call that did
# not exist. A guard that cries wolf on line drift is one people learn to skip,
# which is worse than no guard. File+count still turns red on a genuinely new
# call (count rises, or an unlisted file appears) and stays quiet on movement.
_KNOWN_SYNC_HTTPX_COUNTS = {
    # DEF116 D4: identical class, out of scope, gated on urow.alpaca_access_token
    # so it fires only for linked users. Needs its own decision.
    "app/services/alpaca_service.py": 2,
    # RevenueCat: reached only from a sync `def` route, which FastAPI runs in a
    # threadpool, so it never parks the event loop — the CR049 distinction.
    "app/services/revenuecat_client.py": 1,
    # room_runner's `log_prefix_cache_status()` httpx.get IS on the event loop —
    # `main.py:132` awaits `resume_pending_retries()` inside `async def lifespan`,
    # not through a threadpooled Depends. It is safe for a DIFFERENT reason:
    # it fires at most once per process during lifespan startup, before uvicorn
    # serves any traffic, guarded by `_PREFIX_CACHE_STATUS_LOGGED`
    # (room_runner.py:2554). A SECOND httpx call in this module would NOT
    # inherit that reasoning. (The first version of this comment reused the
    # threadpool justification here and was simply wrong — DEF116 round-3 audit.
    # A pin with a wrong reason is worse than a pin with none: it invites the
    # next reader to add a call on a false premise.)
    "app/services/room_runner.py": 1,
}


def test_sync_httpx_call_site_inventory_is_pinned():
    counts: dict[str, int] = {}
    where: dict[str, list[int]] = {}
    for path in _iter_py(_APP):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            f = node.func
            if (
                isinstance(f, ast.Attribute)
                and isinstance(f.value, ast.Name)
                and f.value.id == "httpx"
                and f.attr in {"get", "post", "put", "patch", "delete", "request", "stream"}
            ):
                key = str(path.relative_to(_APP.parent))
                counts[key] = counts.get(key, 0) + 1
                where.setdefault(key, []).append(node.lineno)

    added = {
        f"{k} ({counts[k]} sync httpx calls, expected {_KNOWN_SYNC_HTTPX_COUNTS.get(k, 0)}; "
        f"lines {sorted(where[k])})"
        for k in counts
        if counts[k] > _KNOWN_SYNC_HTTPX_COUNTS.get(k, 0)
    }
    removed = {
        f"{k} ({counts.get(k, 0)} sync httpx calls, expected {v})"
        for k, v in _KNOWN_SYNC_HTTPX_COUNTS.items()
        if counts.get(k, 0) < v
    }
    assert not added, (
        "NEW synchronous `httpx.<verb>(` call(s) under backend/app. If any async "
        "route can reach one, it parks the single event loop for the whole "
        "round-trip (DEF116, same class as CR049's MAJOR). Use `httpx.AsyncClient` "
        "with `await`, or wrap the call in `await asyncio.to_thread(...)`. If it is "
        "genuinely only reachable from a sync `def` route, raise the count here "
        "with that reason:\n" + "\n".join(sorted(added))
    )

    assert not removed, (
        "pinned sync httpx call(s) no longer present (fixed or deleted) — lower "
        "the count here so the pin keeps catching new ones:\n"
        + "\n".join(sorted(removed))
    )


def test_no_blocking_leaf_call_reachable_from_async_route():
    offenders, _ = _offending_routes(waived=_WAIVED_CALL_CHAIN_NAMES)

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
