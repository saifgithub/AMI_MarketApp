"""def200_sync_io_census.py — enumerate sync-I/O-on-the-event-loop sites (DEF200).

DEF200 (security review N2 remainder, disclosed after SEC-BATCH1 fixed only
the OIDC pair): ~93 `async def` handlers across `app/api/*.py` do
synchronous work — DB sessions, `httpx.Client`, the `yfinance` library —
that blocks the single uvicorn worker's event loop. Any slow upstream
(Apple, Google, yfinance, Adanos, Reddit) stalls every concurrent request
and SSE stream, unauthenticated, for everyone.

The row's own prescribed fix shape: "census the sync-I/O-on-async-path
sites first and publish the list, then convert in batches — do not start
converting before it exists." This is that census, built as a re-runnable
script rather than a one-time doc so it stays honest as the codebase moves
(a static list goes stale the moment someone adds or fixes a handler; a
script re-measures).

WHY THE FIRST DRAFT OF THIS SCRIPT UNDERCOUNTED, AND WHAT CHANGED: a naive
pass only flagged handlers with a literal `get_session(` in their OWN body
— 21 of 93. But nearly all persistence in this codebase goes through
store/service classes (mandate_store, journal_store, credit_service, ...)
that call `get_session()` INTERNALLY; the handler just calls
`mandate_store.get(...)`. That first draft was measuring "handlers that
touch the DB directly," a much narrower and less useful question than
DEF200 actually asks. Fixed by building the sync-I/O module registry from
real grep evidence (`grep -rl get_session backend/app/services/*.py`, plus
the six modules already known to hold a sync `httpx.Client`/`yfinance`),
then resolving each handler's IMPORTS against that registry.

THREE SECTIONS, different confidence levels — read the label, not just the
count:

  A. Direct `get_session(` calls inside an `async def` handler's own body.
     AST-verified, exact.

  B. The registry of known sync-I/O modules this census checks handlers
     against — 19 found via `get_session(` in backend/app/services/*.py,
     plus 6 known to hold a sync `httpx.Client` or `yfinance`. Re-derived
     by grep each run, not a hand-typed list, so it can't silently rot.

  C. Async handlers whose body references a name IMPORTED FROM one of
     section B's modules — resolved via AST import analysis (handles
     `from X import name` and aliasing), not string search. This is ONE
     HOP: a handler that reaches section B only through an intermediate
     service layer (agent_runner.py, brief_engine.py, room_runner.py, sim.py,
     watchlist.py calling INTO one of the B modules, rather than the handler
     calling it directly) will NOT appear here even though it is still
     exposed. KNOWN LIMIT, stated rather than discovered: true transitive
     call-graph tracing is real future work this script does not attempt.

Usage: backend/.venv/bin/python backend/scripts/def200_sync_io_census.py
"""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
API_DIR = REPO / "backend" / "app" / "api"
SERVICES_DIR = REPO / "backend" / "app" / "services"

# Hand-verified against source, 2026-07-30 — these hold a sync httpx.Client
# or the sync `yfinance` lib and are NOT found by grepping for `get_session`
# (they're a different kind of sync I/O: outbound HTTP, not the DB).
# Calls reviewed BY HAND and found non-blocking despite resolving into a sync-I/O
# module: pure computation that merely lives beside code that touches the DB.
# Keyed (module, called name). Every entry needs a reason; a test pins that the
# named function still exists in the module, so an entry cannot outlive what it
# vouches for. Do NOT add a store/service method here to clear a handler off the
# census: wrap the call in `asyncio.to_thread` instead.
_REVIEWED_NON_BLOCKING: dict[tuple[str, str], str] = {
    ("room_runner", "_risk_tier_size_ceiling"): "pure arithmetic over a Mandate",
    ("room_runner", "_verify_and_annotate_geometry"): "pure regex/arithmetic over the reply text",
    ("room_runner", "run_was_refunded"): "reads two attributes of an already-loaded RoomRun",
    ("auth_service", "parse_scaffold_token_user_id"): "HMAC + expiry check on the token string, no DB",
    ("room_runner", "is_active"): "membership test on an in-memory dict",
    ("ticker_reference", "ticker_not_found_detail"): "builds a pydantic model from an exception",
    ("credit_service", "brief_cost"): "reads a settings value",
    ("credit_service", "one_on_one_cost"): "reads a settings value",
    ("llm_spend", "budget_http_exception"): "builds an HTTPException from the clock",
    ("sim_resting_orders", "bracket_closing_enabled"): "reads a settings flag",
    ("sector_allocation", "allocate_by_sector"): "pure given the `sector_of` resolver the caller passes (a dict lookup over the pre-resolved SectorMap)",
    ("sector_allocation", "sector_concentration_cap"): "pure arithmetic over a Mandate",
}

_KNOWN_SYNC_HTTP_MODULES: dict[str, str] = {
    "market_data": "YahooQuoteProvider: sync httpx.Client; "
                    "YfinanceProvider: yfinance lib (sync requests underneath)",
    "news_context": "_AlphaVantageSource: sync httpx.Client",
    "social_context": "_AdanosSource: sync httpx.Client",
    "sharia_universe": "_network_snapshot_fetch: sync httpx.Client",
    "sharia_divergence": "_default_fetcher: sync httpx.Client",
    "oidc_verifier": "sync httpx.Client — MITIGATED (DEF183): "
                      "AuthService.sign_in_with_apple/_google wrap it in run_in_threadpool",
}


def _sync_db_modules() -> dict[str, str]:
    """Modules under app/services/ whose OWN source calls get_session() —
    re-derived by grep every run rather than hand-maintained, so a module
    that stops (or starts) touching the DB directly is reflected next run,
    not silently stale."""
    out = subprocess.run(
        ["grep", "-rl", "get_session(", "--include=*.py", str(SERVICES_DIR)],
        capture_output=True, text=True,
    ).stdout
    mods = {}
    for line in out.splitlines():
        name = Path(line).stem
        mods[name] = "sync DB session (get_session) inside this module"
    return mods


def _iter_async_handlers(tree: ast.Module):
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            yield node


def _calls_get_session(fn: ast.AsyncFunctionDef) -> bool:
    for node in ast.walk(fn):
        if isinstance(node, ast.Call):
            f = node.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if name == "get_session":
                return True
    return False


def _names_imported_from(tree: ast.Module, target_modules: set[str]) -> dict[str, str]:
    """{local_name: source_module} for every `from app...<mod> import X [as Y]`
    or `import app...<mod> as Y`, where <mod>'s last path segment is in
    target_modules. Handles aliasing so a renamed import still resolves."""
    bindings: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            mod_leaf = node.module.rsplit(".", 1)[-1]
            if mod_leaf in target_modules:
                for alias in node.names:
                    local = alias.asname or alias.name
                    bindings[local] = mod_leaf
        elif isinstance(node, ast.Import):
            for alias in node.names:
                mod_leaf = alias.name.rsplit(".", 1)[-1]
                if mod_leaf in target_modules:
                    local = alias.asname or mod_leaf
                    bindings[local] = mod_leaf
    return bindings


def _call_root(node: ast.expr) -> str | None:
    """The root name of a call target: `f(...)` -> f, `a.b.c(...)` -> a."""
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else None


def _skipped_subtrees(fn: ast.AsyncFunctionDef) -> list[ast.AST]:
    """The parts of a handler that can hold a CALL which does not run per request.

    Only two exist, and the list is deliberately not longer than that. Since
    [_fn_called_names] collects call *targets* rather than every name, an
    annotation or an `except` clause cannot contribute one — naming a class is
    not calling it — so skipping them would be inert code dressed as a guard.
    Measured: adding them changes nothing against this codebase.

    - **Decorators** (`@router.get(...)`) are the route registration, run once
      at import.
    - **Parameter defaults**, including `Depends(...)`, are evaluated once at
      import. If the dependency itself blocks, that is the DEPENDENCY's row on
      this census, not the handler's.

    Annotations are NOT skipped here — [_param_bindings] reads them, because the
    annotation is the only thing that says what a parameter is.
    """
    args = fn.args
    skip: list[ast.AST] = list(fn.decorator_list)
    skip.extend(d for d in [*args.defaults, *args.kw_defaults] if d is not None)
    return skip


def _param_bindings(fn: ast.AsyncFunctionDef, bindings: dict[str, str]) -> dict[str, str]:
    """{param_name: sync_io_module} for parameters TYPED as a sync-I/O class.

    `sim: SimEngine = Depends(get_sim_engine)` is how a service object reaches
    a handler, so the annotation is not noise — it is the only thing that says
    what `sim` is. Skipping annotations wholesale (the first attempt at this
    fix) silently dropped real blocking calls: `sim.py::get_holding_lots` awaits
    a threadpooled quote and then calls `sim.holding_lots(...)` straight on the
    loop, and `auth.py::magic_link_verify` calls `auth.verify_magic_link(...)`
    the same way. Both went unflagged.

    So the annotation is used to TYPE the parameter, and the body decides:
    calling `sim.holding_lots(...)` counts, handing `sim.current_quote` to
    `asyncio.to_thread(...)` does not. That is the distinction the census was
    missing in both directions.
    """
    out: dict[str, str] = {}
    args = fn.args
    for a in [*args.posonlyargs, *args.args, *args.kwonlyargs, args.vararg, args.kwarg]:
        if a is None or a.annotation is None:
            continue
        root = _call_root(a.annotation)
        if root is not None and root in bindings:
            out[a.arg] = bindings[root]
    return out


def _fn_called_names(fn: ast.AsyncFunctionDef) -> set[str]:
    """Root names this handler actually CALLS, on the event loop. See
    [_skipped_subtrees] for what is excluded and why.

    A name counts when it is the root of a call target: `store.get(...)` ->
    `store`, because that is how every service object on this census is used.
    It does not count when it is merely mentioned, passed as a reference, or
    named in an annotation.
    """
    return {root for root, _name in _fn_called_targets(fn)}


def _fn_called_targets(fn: ast.AsyncFunctionDef) -> set[tuple[str, str]]:
    """`(root, name)` for every call the handler makes directly on the loop:
    `f(...)` -> (f, f); `a.b.c(...)` -> (a, b).

    One exemption, about what a call IS rather than what it is named: a call
    that is directly **awaited**, or is the iterable of an **async for**, is an
    async callable. It runs on the loop by design and cannot be sync I/O in its
    own body; anything blocking inside it is a SECOND hop, which this census
    states it does not trace.

    There is deliberately NO "this handler already uses run_in_threadpool"
    exemption. That check was per-function, so one threadpooled call masked
    every raw call beside it (brief.py's own comments describe exactly that).
    A call written as an argument of another call is still visited, so
    `await asyncio.to_thread(store.get, ...)` (a reference) is clean while
    `await asyncio.to_thread(f, store.get(...))` is not.
    """
    skip_ids = {id(n) for n in _skipped_subtrees(fn)}
    exempt: set[int] = set()
    for node in ast.walk(fn):
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            exempt.add(id(node.value))
        elif isinstance(node, ast.AsyncFor) and isinstance(node.iter, ast.Call):
            exempt.add(id(node.iter))
    targets: set[tuple[str, str]] = set()

    def visit(node: ast.AST) -> None:
        if id(node) in skip_ids:
            return
        if isinstance(node, ast.Call) and id(node) not in exempt:
            root = _call_root(node.func)
            if root is not None:
                f = node.func
                if isinstance(f, ast.Attribute):
                    chain = f
                    while isinstance(chain.value, ast.Attribute):
                        chain = chain.value
                    targets.add((root, chain.attr))
                else:
                    targets.add((root, root))
        for child in ast.iter_child_nodes(node):
            visit(child)

    for child in ast.iter_child_nodes(fn):
        visit(child)
    return targets


def _local_blockers(tree: ast.Module, bindings: dict[str, str]) -> dict[str, str]:
    """{name: why} for module-level plain `def`s in this file that themselves open
    a DB session or call into a sync-I/O module.

    A handler calling `_require_ticker_or_422(...)` straight on the loop blocks
    exactly as if it had written the `get_session()` itself, and no import
    resolves it: the helper is local. That is the shape that kept
    `sim.py`'s ticker guard and `games.py`'s copy of it off this census for as
    long as it existed. One level only, same as section C.
    """
    out: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef):
            continue
        for call in ast.walk(node):
            if not isinstance(call, ast.Call):
                continue
            f = call.func
            name = f.id if isinstance(f, ast.Name) else getattr(f, "attr", None)
            if name == "get_session":
                out[node.name] = "get_session"
                break
            root = _call_root(f)
            if root in bindings:
                callee = f.attr if isinstance(f, ast.Attribute) else root
                if (bindings[root], callee) not in _REVIEWED_NON_BLOCKING:
                    out[node.name] = bindings[root]
                    break
    return out


def flag_handlers(tree: ast.Module, bindings: dict[str, str]) -> tuple[list[str], list[str], int]:
    """(section_a, section_c, async_handler_count) for one parsed module, keyed
    by bare handler name. Split out of [census] so the detection logic can be
    pinned on synthetic source, independent of what the real codebase flags."""
    section_a: list[str] = []
    section_c: list[str] = []
    total = 0
    local = _local_blockers(tree, bindings)
    for fn in _iter_async_handlers(tree):
        total += 1
        if _calls_get_session(fn):
            section_a.append(fn.name)
        resolvable = {**bindings, **_param_bindings(fn, bindings), **local}
        hit_modules = {
            resolvable[root]
            for root, name in _fn_called_targets(fn)
            if root in resolvable
            and (resolvable[root], name) not in _REVIEWED_NON_BLOCKING
        }
        if hit_modules:
            section_c.append(f"{fn.name} (via: {', '.join(sorted(hit_modules))})")
    return section_a, section_c, total


def census() -> dict:
    sync_db_modules = _sync_db_modules()
    registry = {**sync_db_modules, **_KNOWN_SYNC_HTTP_MODULES}
    target_modules = set(registry)

    section_a: list[str] = []
    section_c: list[str] = []
    total_async = 0

    for path in sorted(API_DIR.glob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:  # pragma: no cover
            print(f"SKIP {path.name}: {e}", file=sys.stderr)
            continue

        bindings = _names_imported_from(tree, target_modules)

        a, c, n = flag_handlers(tree, bindings)
        total_async += n
        section_a.extend(f"{path.name}::{x}" for x in a)
        section_c.extend(f"{path.name}::{x}" for x in c)

    return {
        "total_async_handlers": total_async,
        "section_a_direct_sync_db": section_a,
        "section_b_registry": registry,
        "section_c_onehop_reachable": section_c,
    }


def main() -> int:
    result = census()
    n_files = len(list(API_DIR.glob("*.py")))
    print(f"DEF200 sync-I/O census — {n_files} files in app/api/, "
          f"{result['total_async_handlers']} async def handlers total\n")

    print(f"── A. Direct sync DB session in an async handler's own body ({len(result['section_a_direct_sync_db'])}) ──")
    for site in result["section_a_direct_sync_db"]:
        print(f"  {site}")

    reg = result["section_b_registry"]
    print(f"\n── B. Sync-I/O module registry, re-derived by grep every run ({len(reg)}) ──")
    for mod, why in sorted(reg.items()):
        print(f"  {mod}.py — {why}")

    c = result["section_c_onehop_reachable"]
    print(f"\n── C. Async handlers ONE HOP from a section-B module (import-resolved) ({len(c)}) ──")
    print("    (NOT transitive — see the module docstring's KNOWN LIMIT)")
    for site in c:
        print(f"  {site}")

    covered = len({s.split(" ")[0] for s in c} | set(result["section_a_direct_sync_db"]))
    print(f"\n{covered}/{result['total_async_handlers']} async handlers flagged by A or C "
          f"(the remainder either do no I/O, or reach section B only through an "
          f"intermediate service layer this one-hop pass doesn't trace).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
