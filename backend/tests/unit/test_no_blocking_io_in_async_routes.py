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

The Alpaca snapshot pattern DEF116 D4 flagged here (a sync `httpx.get` on
the event loop via `alpaca_snapshot_text`, from `room_runner.py` /
`agent_runner.py`) no longer exists: CR202 moved the credential to the
device, so the backend fetches nothing and the blocking call went with it.
See the note below `_YFINANCE_BLOCKING_ATTRS` for why httpx detection isn't
included here.
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
    # DEF120: SimEngine.portfolio_marks_snapshot / valuation_snapshot are
    # themselves the call-site the route must to_thread — they fan out over
    # a sync ThreadPoolExecutor internally (`_marks_with_quotes`), which
    # passes `current_quote` BY REFERENCE to `pool.map`, not as a direct
    # call. That's correct (D2) but it means `current_quote` itself is no
    # longer reachable by this walk from inside these two methods — the
    # chain breaks 1-2 hops before the actual leaf. Without these two names
    # here, a route that calls `sim.portfolio_marks_snapshot(user_id)` or
    # `sim.valuation_snapshot(user_id)` directly (mutation-proved: reverting
    # `get_portfolio`'s `to_thread` wrap left the guard green without this)
    # is invisible to the guard even though it genuinely blocks the event
    # loop — `pool.map()` still runs and blocks on the calling thread if
    # that thread is the event loop. These names are the actual observable
    # boundary now; treat them as leaves in their own right.
    #
    # DEF120 round 2 (MAJOR, auditor-reproduced): naming these two after the
    # fact was the bug, not the fix — the SAME by-reference break hides ANY
    # new SimEngine method that reaches the network through
    # `_marks_with_quotes`, no matter what it's called. Reproduced with
    # `audit_probe_snapshot`, a fresh method doing exactly that, called
    # straight from `sector_allocation` with no `to_thread`: 7 passed, green.
    # D9 (below, `test_every_network_reaching_simengine_method_is_declared`)
    # closes the mechanism instead of naming the next method: it walks
    # `SimEngine`'s own methods against each other using attribute
    # REFERENCES as edges (not just calls), so a leaf handed to `pool.map`
    # by reference is exactly as visible as one called directly, and any
    # method it finds reaching the network must be declared here or in
    # `_SIM_ENGINE_SYNC_SAFE_METHODS` — undeclared defaults to unsafe (red).
    "portfolio_marks_snapshot",
    "valuation_snapshot",
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
# out of scope for this lane. The Alpaca `httpx.get` chain DEF116 D4 named
# here was never caught by this guard — it was flagged by name in the DEF116
# hand-off instead. CR202 removed it outright; only the OAuth `httpx.post`
# remains, pinned by count below.

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
# (`room_runner.py:2001`), aliased in `room.py:76` as
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
#
# ROUND 4 adds `_build_sim_holdings_block`. It is NOT a new bug and NOT a
# regression — it is `room_runner.py:1995`, which has been blocking the loop on
# every Room convene the whole time. It became VISIBLE only in round 4, when
# `_route_walk_leaf_method_names()` fed the declared-sync-safe names into the
# transitive walk and the walk stopped breaking at `_marks_with_quotes`'
# by-reference `pool.map` fan-out. Same `room_runner.py`-is-out-of-scope
# reason as its neighbour above (D7); waived here so DEF120's own acceptance
# is not held hostage to the Room queue's file, and pinned three lines down in
# `_DEF120_KNOWN_BLOCKING_PAIRS` — which runs with an EMPTY waiver — so the
# waiver cannot hide it. Removing either name without wrapping its call site
# turns one of these two tests red.
# DEF136 emptied this. Both names are gone because both call sites in
# `room_runner.run()` are now `await asyncio.to_thread(...)`, so there is
# nothing left to waive. Re-adding a name here to make a red build green is
# the move this set exists to make expensive: it hides the whole subtree
# beneath that name from the main guard (the round-1 MAJOR), so a waiver is
# only ever correct alongside a matching entry in
# `_DEF120_KNOWN_BLOCKING_PAIRS` below, which runs with an EMPTY waiver.
_WAIVED_CALL_CHAIN_NAMES: set[str] = set()


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


def _route_walk_leaf_method_names() -> set[str]:
    """Every SimEngine method the route walk treats as a blocking leaf.

    Round-3 audit finding (MAJOR): D10 walks only an `async def` route's OWN
    body, so one hop of ordinary indirection restored the bug — the identical
    `sim.current_marks([...])` moved into a module-level sync helper in the
    same file and called from the route shipped GREEN past all four guards.
    Each missed it for its own reason: D10 because a module-level `def` is not
    nested inside an `ast.AsyncFunctionDef`; D9 because `current_marks` IS
    declared (sync-safe); this route walk because it only recognised
    `_BLOCKING_LEAF_METHOD_NAMES` and broke at `_marks_with_quotes`'
    by-reference `pool.map(self.current_quote, …)` fan-out.

    The declared-sync-safe names are network-reaching by construction — that
    is the entire content of the D9 declaration. Feeding them into the walk
    that already follows calls transitively across modules closes the hop
    without a new mechanism, and SUBSUMES D10 (which is kept for its sharper
    error message, no longer load-bearing).

    Deliberately non-mutating, deviating from the audit's literal
    `_BLOCKING_LEAF_METHOD_NAMES |= _SIM_ENGINE_SYNC_SAFE_METHODS`: an
    import-time `|=` would collapse the two declaration buckets D9 exists to
    keep distinct, so D9's "add it to X or Y" diagnostic would name a set that
    already contains every sync-safe method. Same walk behaviour, no global
    mutation, no import-order dependency.

    A correctly-wrapped `await asyncio.to_thread(sim.<name>, …)` stays
    invisible: the leaf is an `ast.Attribute` ARGUMENT, never an `ast.Call`.
    """
    return _BLOCKING_LEAF_METHOD_NAMES | _SIM_ENGINE_SYNC_SAFE_METHODS


def _is_to_thread(func: ast.AST) -> bool:
    """`asyncio.to_thread` / `to_thread`, however it was imported."""
    if isinstance(func, ast.Attribute):
        return func.attr == "to_thread"
    return isinstance(func, ast.Name) and func.id == "to_thread"


def _deferred_lambda_ids(fn: ast.AST) -> set[int]:
    """`id()`s of Lambda nodes handed directly to `asyncio.to_thread(...)`.

    `await asyncio.to_thread(lambda: sim.current_marks(t))` defers correctly — the
    lambda body runs on the worker thread — but the leaf `ast.Call` still sits
    lexically inside the async body, so an `ast.walk` flags it identically to a raw
    blocking call (DEF133, raised as MINOR 1 by the DEF120 round-4 audit).

    Scoped deliberately to lambdas that are ARGUMENTS OF a `to_thread` call, never to
    "any lambda". The naive form — skip every `Call` under any `Lambda` — is FAIL-OPEN:
    a lambda that is never handed to `to_thread` (a callback, a `sorted(key=…)`, a
    default factory) would then hide a genuine blocking call. Widening
    `_WAIVED_CALL_CHAIN_NAMES` to silence the false positive is the same trap and is the
    reason this earned its own id: it converts a precision complaint into a real hole.
    """
    out: set[int] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call) or not _is_to_thread(node.func):
            continue
        for arg in [*node.args, *(kw.value for kw in node.keywords)]:
            if isinstance(arg, ast.Lambda):
                out.add(id(arg))
    return out


def _deferred_call_ids(fn: ast.AST) -> set[int]:
    """`id()`s of every Call lexically inside a `to_thread`-deferred lambda.

    Ancestry, not "is my direct parent a Lambda": the leaf can sit arbitrarily deep
    inside the lambda body. Computed once per fn and shared by both walks below so the
    two guards cannot drift into disagreeing about what "deferred" means.
    """
    deferred_lambdas = _deferred_lambda_ids(fn)
    if not deferred_lambdas:
        return set()
    parent: dict[int, ast.AST] = {}
    for node in ast.walk(fn):
        for child in ast.iter_child_nodes(node):
            parent[id(child)] = node

    out: set[int] = set()
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        cur = parent.get(id(node))
        while cur is not None:
            if isinstance(cur, ast.Lambda) and id(cur) in deferred_lambdas:
                out.add(id(node))
                break
            cur = parent.get(id(cur))
    return out


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
    leaf_methods = _route_walk_leaf_method_names()
    deferred = _deferred_call_ids(fn)
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        if id(node) in deferred:
            continue
        f = node.func
        if isinstance(f, ast.Name) and f.id in _BLOCKING_LEAF_FUNC_NAMES:
            hits.append(f.id)
        elif isinstance(f, ast.Attribute) and f.attr in leaf_methods:
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


# DEF120's own 9 pairs (mandate.py:audit_holdings, portfolio.py:sector_allocation,
# room.py:stream_room, and 6 sim.py handlers, all `-> <obj>.current_quote`) ARE
# gone — every route wraps its call in `await asyncio.to_thread(...)`.
#
# This set was empty until round 4. It is no longer, and that is the point:
# once `_route_walk_leaf_method_names()` fed the declared-sync-safe names into
# the transitive walk, the walk could finally SEE into the Room's chain instead
# of breaking at `_marks_with_quotes`' by-reference `pool.map` fan-out. The 3
# pairs below are real, they block the event loop on every Room convene over
# every holding, and they are NOT DEF120's to fix — `room_runner.py` is out of
# scope by D7 (the Room queue owns it).
#
# All 3 are one call site: `room_runner.py:1995` calls
# `_build_sim_holdings_block(user_id, ticker)` directly, un-`to_thread`'d, from
# inside `async def run()` (`:1837`) — the async generator awaited on the loop
# by `_pump`'s `async for ev in self.run(...)` (`:1778`). That builder calls
# `sim.total_value(user_id)` (`:663`) and `sim.current_marks(list(agg))`
# (`:672`), the full `_marks_with_quotes` yfinance fan-out.
#
# `:1995` is a SECOND, distinct blocking call, six lines before the `:2001`
# `_build_room_sector_context` that earlier rounds called "the one remaining
# offender" — and unlike `:2001` it is not waived. Anyone closing the Room
# remainder per that prose alone would leave `:1995` running. Pinning the pairs
# here is this round's own principle applied one level up: assert it, don't
# comment it. A paragraph explaining an empty set does not go red; this does.
#
# Closing the Room remainder means wrapping `:1995` (and `:2001`) and shrinking
# this set to empty — the second assertion below fails until it is shrunk.
#
# LINE NUMBERS ABOVE ARE A COURTESY, NOT A CONTRACT — re-derive them by name
# before quoting them anywhere. Round 4 shipped six of them wrong: they were
# inherited from the round-3 audit, which measured a tree from BEFORE DEF124
# landed in `room_runner.py` and shifted every one by ~+89. Nothing asserted
# broke (the waiver, the pin set and the walk are all name-based, which is why
# it went unnoticed) but the numbers were headed into the Room lane's assign,
# where a worker greps `:1906` and finds unrelated logging. Grep the FUNCTION
# NAMES; they are unambiguous and they do not drift.
# DEF136 shrank this to empty. The three pairs were all `stream_room` reaching
# `SimEngine` through `room_runner.run()`'s two unwrapped builders; wrapping
# both call sites removed every one of them. Empty is now the correct state and
# the second assertion below makes it self-maintaining: the moment a pinned pair
# stops blocking, the set is stale and the test says so.
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
    # CR202 dropped this from 2 to 1. DEF116 D4 flagged two sync httpx calls
    # here — the account read (`_paper_get`) and the OAuth exchange — as the
    # same event-loop-parking class, pending their own decision. The decision
    # landed sideways: the read is gone entirely, because the credential it
    # needed is gone. The user's Alpaca key lives on their device now, so the
    # only call left is the OAuth token exchange, which is reached from a sync
    # `def` route (FastAPI threadpools it, the CR049 distinction) and is
    # unreachable today regardless.
    "app/services/alpaca_service.py": 1,
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
    # CR027: notification_service.notify()'s OneSignal push attempt. Not
    # reachable from any async route today — its only callers are
    # scripts/send_notification.py (a standalone CLI, no event loop) and
    # price_alert_evaluator.py's background tick, which wraps the call in
    # `await asyncio.to_thread(notify, ...)`. A future consumer (CR095/
    # CR109/BL11/Room-verdict) calling notify() straight from an async
    # route MUST wrap it the same way — that isn't enforced here.
    "app/services/notification_service.py": 1,
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


# ── D9 (DEF120 round 2): deny-by-default over SimEngine itself ────────────
#
# Everything above walks INTO the engine starting from a route — which is
# exactly the walk the by-reference `pool.map(self.current_quote, ...)`
# shape defeats, because `_called_names` only sees `ast.Call` nodes and a
# leaf handed over by reference is never one. D9 does not try to fix that
# walk; it adds a second, independent one that never leaves `sim_engine.py`
# and never needs to see a call at all — it asks, of `SimEngine`'s methods
# considered as a graph among themselves, "which of these can reach
# `self._provider.<quote|history|news|earnings>` by ANY attribute
# reference, called or merely passed along" — the same question a reviewer
# would ask reading the class top to bottom. A method that can is
# "network-reaching" and MUST be declared, in one of two places:
#   - `_BLOCKING_LEAF_METHOD_NAMES` — an async route may call it directly;
#     every call site must be `await asyncio.to_thread(...)`-wrapped.
#   - `_SIM_ENGINE_SYNC_SAFE_METHODS` — no async route calls it directly;
#     it is only ever reached from inside another already-`to_thread`-
#     wrapped method (verified by grep over `backend/app/api/*.py`, see the
#     comment on the set below).
# A method in neither bucket is undeclared, and undeclared means the
# assertion fails RED — there is no allowlist to silently extend, the new
# method simply isn't in either set until a human puts it there.

_SIM_ENGINE_NETWORK_PRIMITIVES = {"quote", "history", "news", "earnings"}

# Justified, not a blanket waiver: none of these is ever called directly
# from an `async def` route today — enforced by
# `test_sync_safe_simengine_method_never_called_directly_from_async_route`
# (D10, below) rather than by a comment, since a hand-run grep at authoring
# time is unasserted and rots silently (DEF120 round 2 MAJOR: a straight
# revert reinstating `sim.current_marks(...)` in async `sector_allocation`
# shipped green past D9). `current_price` / `current_marks` /
# `current_marks_with_source` / `_marks_with_quotes` / `aggregate_source` /
# `total_value` / `current_drawdown_pct` are reached only from inside other
# `SimEngine` methods; `submit` / `preview` / `evaluate_outcomes` /
# `manual_close` ARE called from routes, but the ENTIRE call is
# `to_thread`-wrapped at every site (acceptance item 6a covers reverting
# that). If any of these is ever called directly from a route body, it must
# move to `_BLOCKING_LEAF_METHOD_NAMES` and every call site wrapped — this
# set does not exempt that.
_SIM_ENGINE_SYNC_SAFE_METHODS = {
    "current_price",
    "current_marks",
    "current_marks_with_source",
    "_marks_with_quotes",
    "aggregate_source",
    "total_value",
    "current_drawdown_pct",
    "submit",
    "preview",
    "evaluate_outcomes",
    "manual_close",
    # CR109 slice 2: reached only from `games_service.submit_trade` /
    # `games_service.process_queued_orders`, both of which are themselves
    # always called from `api/games.py` / `main.py`'s queue-fill tick via
    # `await asyncio.to_thread(...)` — same shape as `submit` above.
    "submit_game_trade",
    # CR170: the compliance-input bundle `submit`, `preview` and
    # `fill_resting_order` each hand to `check_mandate_compliance`. Reaches the
    # network through `total_value` / `current_marks` / `current_drawdown_pct`,
    # all already in this set. Private, and no route calls it — the three
    # methods that do are themselves wrapped at every site.
    "_compliance_context",
    # CR170 §4: the resting book's fill entry point. Reached only from
    # `sim_resting_orders.sweep_resting_orders`, which is `to_thread`-wrapped at
    # both of its call sites — `main.py::_sim_resting_order_tick` and
    # `api/sim.py::evaluate_trades`. Same shape as `submit_game_trade` above.
    "fill_resting_order",
    # CR171 §5/§7/§4: the three short passes, reached ONLY from
    # `sim_resting_orders.sweep_resting_orders` (`_sweep_short_positions` and
    # `_accrue_borrow`), which is `to_thread`-wrapped at both of its call
    # sites — `main.py::_sim_resting_order_tick` and `api/sim.py::evaluate_trades`.
    # Each reaches the network through `current_price`, already in this set.
    "evaluate_short_brackets",
    "force_close_breached_shorts",
    "accrue_short_borrow",
    # CR171 §1: the user-initiated buy-to-cover. No route calls it directly
    # today; when one does, it must be wrapped like `submit` is.
    "cover_short",
}


def _sim_engine_class_node() -> ast.ClassDef:
    tree = ast.parse((_APP / "services" / "sim_engine.py").read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "SimEngine":
            return node
    raise AssertionError("class SimEngine not found in sim_engine.py — has it moved?")


def _sim_engine_methods(cls: ast.ClassDef) -> dict[str, ast.AST]:
    return {
        n.name: n
        for n in cls.body
        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _referenced_attrs(fn: ast.AST) -> set[str]:
    """Every attribute name touched inside fn — CALLED or merely
    REFERENCED (e.g. handed to `pool.map`/`map` by name, never invoked at
    the call site itself). This is the one difference from `_called_names`
    above, which only sees `ast.Call` nodes — and that difference is
    exactly the gap D9 closes."""
    return {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}


def _reaches_network(name: str, methods: dict[str, ast.AST], seen: set[str]) -> bool:
    if name in seen:
        return False
    seen.add(name)
    fn = methods.get(name)
    if fn is None:
        return False
    attrs = _referenced_attrs(fn)
    if attrs & _SIM_ENGINE_NETWORK_PRIMITIVES:
        return True
    return any(
        attr in methods and _reaches_network(attr, methods, seen)
        for attr in attrs
        if attr != name
    )


def test_every_network_reaching_simengine_method_is_declared():
    """D9 (DEF120 round 2, deny-by-default) — see the block comment above.

    Round-2 audit finding (MAJOR, reproduced): a new `SimEngine` method
    reaching the network through `_marks_with_quotes` — a by-reference
    fan-out — was invisible to `test_no_blocking_leaf_call_reachable_from_
    async_route` above even when called directly from an async route, no
    `to_thread`. This test doesn't walk from routes at all; it asks
    `SimEngine`'s own methods which of them can reach
    `self._provider.<quote|history|news|earnings>`, by reference or by
    call, and fails if any such method isn't declared safe or a leaf.
    """
    cls = _sim_engine_class_node()
    methods = _sim_engine_methods(cls)
    network_reaching = {
        name for name in methods if _reaches_network(name, methods, seen=set())
    }
    declared = _BLOCKING_LEAF_METHOD_NAMES | _SIM_ENGINE_SYNC_SAFE_METHODS
    undeclared = network_reaching - declared

    assert not undeclared, (
        "SimEngine method(s) reach the network — directly or via a "
        "by-reference fan-out such as `pool.map(self.current_quote, ...)` "
        "— but are declared neither a blocking leaf nor sync-safe. A new "
        "method defaults to UNSAFE: add it to `_BLOCKING_LEAF_METHOD_NAMES` "
        "(an async route may call it directly — wrap every call site in "
        "`await asyncio.to_thread(...)`) or to `_SIM_ENGINE_SYNC_SAFE_"
        "METHODS` (only ever reached from inside an already-to_thread-"
        "wrapped method — name which one in a comment):\n"
        + "\n".join(sorted(undeclared))
    )


# ── D10 (DEF120 round 3): assert the sync-safe declaration, don't comment it ─
#
# D9 governs WHAT may exist: a `SimEngine` method that reaches the network
# must be declared in `_BLOCKING_LEAF_METHOD_NAMES` or
# `_SIM_ENGINE_SYNC_SAFE_METHODS`. Neither D9 nor the route-walking guard
# above governs HOW a declared-sync-safe method is actually called — that
# was left to a comment ("checked by grep"), run once by hand at authoring
# time. Nothing asserted it, so a straight revert of this lane's own fix —
# `marks = sim.current_marks(["AAPL"])` back in async `sector_allocation`,
# the verbatim pre-DEF120 bug — shipped green through both guards
# (round-2 audit MAJOR, probe P4).
#
# D10 closes that: for every name in `_SIM_ENGINE_SYNC_SAFE_METHODS`, walk
# every `async def` under `backend/app/api/` and fail if it contains a
# direct `<obj>.<name>(...)` call. The correctly-deferred shape —
# `await asyncio.to_thread(sim.current_marks, tickers)` — passes the method
# by reference (an `ast.Attribute`, never invoked at the call site), so it
# is not an `ast.Call` at all and is structurally invisible to this check;
# no exemption needs to be carved out for it.
def _direct_sync_safe_calls(fn: ast.AST) -> list[str]:
    # Shares `_deferred_call_ids` with the route walk above: the lambda idiom defers here
    # for exactly the same reason, and two guards with two notions of "deferred" is how a
    # fix passes one and is bounced by the other (DEF133).
    deferred = _deferred_call_ids(fn)
    return [
        f"<obj>.{node.func.attr}"
        for node in ast.walk(fn)
        if isinstance(node, ast.Call)
        and id(node) not in deferred
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in _SIM_ENGINE_SYNC_SAFE_METHODS
    ]


def test_sync_safe_simengine_method_never_called_directly_from_async_route():
    """D10 (DEF120 round 3) — see the block comment above.

    Round-2 audit finding (MAJOR, reproduced): `_SIM_ENGINE_SYNC_SAFE_METHODS`
    membership was a comment, not a control — a revert reinstating the
    pre-DEF120 direct call went green. This test makes the claim structural:
    it fails if any declared-sync-safe method is called directly (not merely
    referenced) from inside an `async def` anywhere under `backend/app/api/`.
    """
    offenders: list[str] = []
    for path in _iter_py(_APP / "api"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, ast.AsyncFunctionDef):
                continue
            offenders += [
                f"{path.relative_to(_REPO_ROOT)}:{node.name} -> {hit}"
                for hit in _direct_sync_safe_calls(node)
            ]

    assert not offenders, (
        "async def under backend/app/api/ calls a declared-sync-safe "
        "SimEngine method directly. These names are declared sync-safe on "
        "the premise that they are ONLY ever reached from inside another "
        "already-`to_thread`-wrapped method, never called straight from an "
        "async route body. Either wrap the whole call in "
        "`await asyncio.to_thread(...)`, or if the method itself does "
        "network I/O reachable this way, move it to "
        "`_BLOCKING_LEAF_METHOD_NAMES` instead:\n" + "\n".join(offenders)
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


# ── DEF133: the `to_thread(lambda: …)` deferral, proved in BOTH directions ────
#
# The false positive is easy to silence and easy to silence WRONGLY. Skipping
# every `Call` under any `Lambda` makes the guard fail-open, and widening
# `_WAIVED_CALL_CHAIN_NAMES` to quiet the complaint does the same thing one level
# up. Neither shortcut is caught by asserting only that the correct idiom passes
# — that is why every case below comes in pairs: the shape that must pass, beside
# the shape that must still fail for the same edit.
def _sites(src: str) -> list[str]:
    """Blocking sites the route walk reports inside the first function in `src`."""
    return _blocking_call_sites(ast.parse(src).body[0])


def _leaf() -> str:
    """A real blocking leaf method, read from the set rather than hardcoded so this
    proof follows the declaration instead of drifting away from it."""
    return sorted(_BLOCKING_LEAF_METHOD_NAMES)[0]


def test_to_thread_lambda_is_recognised_as_deferred():
    """The reported false positive: correct code, flagged identically to a raw call."""
    src = f"async def r():\n    return await asyncio.to_thread(lambda: sim.{_leaf()}('AAPL'))\n"
    assert _sites(src) == [], (
        "`to_thread(lambda: <leaf>(...))` defers correctly — the lambda body runs on "
        "the worker thread — but the guard still reports it as blocking."
    )


def test_lambda_not_handed_to_to_thread_is_still_flagged():
    """The fail-OPEN direction, and the whole reason this needed more than a one-liner.
    A lambda is not deferral; being handed to `to_thread` is. If this ever passes, the
    guard has been widened into a hole and DEF116's class ships green."""
    src = f"async def r():\n    return sorted(xs, key=lambda x: sim.{_leaf()}(x))\n"
    assert _sites(src), (
        "a blocking call inside a lambda that is NEVER handed to `to_thread` went "
        "unreported — the naive 'skip anything under a Lambda' fix, which hides real "
        "blocking calls in callbacks, sort keys and default factories."
    )


def test_raw_blocking_call_is_still_flagged():
    src = f"async def r():\n    return sim.{_leaf()}('AAPL')\n"
    assert _sites(src), "the plain DEF116 bug must still be caught"


def test_by_reference_to_thread_remains_invisible():
    """Unchanged behaviour, pinned so the new ancestry walk cannot disturb it."""
    src = f"async def r():\n    return await asyncio.to_thread(sim.{_leaf()}, 'AAPL')\n"
    assert _sites(src) == []


def test_called_leaf_passed_to_to_thread_is_still_flagged():
    """Probe P-E from the round-1 audit: `to_thread(<leaf>(t))` calls the leaf INLINE and
    hands `to_thread` its result, so it blocks the loop and then raises in the worker.
    The lambda exemption must not resurrect the exemption that probe killed — the
    difference is one `lambda:`, and only one of the two shapes defers."""
    src = f"async def r():\n    return await asyncio.to_thread(sim.{_leaf()}('AAPL'))\n"
    assert _sites(src), (
        "a leaf CALLED inline and handed to `to_thread` is never correct and must stay "
        "flagged; the new exemption covers `lambda:` only."
    )


def test_deferral_is_recognised_arbitrarily_deep_inside_the_lambda():
    src = (
        f"async def r():\n"
        f"    return await asyncio.to_thread(lambda: [sim.{_leaf()}(t) for t in ts])\n"
    )
    assert _sites(src) == [], "the leaf can sit anywhere in the lambda body, not just at its root"


def test_sync_safe_guard_agrees_with_the_route_walk_on_deferral():
    """D10 walks separately, so it needs the same notion of deferred or a correct fix
    passes one guard and is bounced by the other."""
    name = sorted(_SIM_ENGINE_SYNC_SAFE_METHODS)[0]
    deferred = f"async def r():\n    return await asyncio.to_thread(lambda: sim.{name}(t))\n"
    bare = f"async def r():\n    return sorted(xs, key=lambda x: sim.{name}(x))\n"

    assert _direct_sync_safe_calls(ast.parse(deferred).body[0]) == []
    assert _direct_sync_safe_calls(ast.parse(bare).body[0]), (
        "D10 must stay fail-closed on a lambda that is not handed to `to_thread`"
    )
