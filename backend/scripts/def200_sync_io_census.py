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
    ("llm_spend", "compute_cost_usd"): "settings + an in-memory price table; the only lock guards a set of already-logged labels",
    ("credit_service", "room_cost_for_plan"): "dict lookup keyed by plan",
    ("sector_allocation", "allocate_by_sector"): "pure given the `sector_of` resolver the caller passes (a dict lookup over the pre-resolved SectorMap)",
    ("sector_allocation", "sector_concentration_cap"): "pure arithmetic over a Mandate",
}

# Singleton accessors: `get_x_store()` builds or returns the store OBJECT and opens
# no session, so the bare call is not blocking — the METHOD called on it is. Used by
# the SERVICE level only, which resolves `get_x_store().method(...)` to the method;
# the handler level keeps treating the accessor call itself as the proxy for it.
# Same rule as above: a reason per entry, and a test that the function exists.
_SINGLETON_ACCESSORS: dict[tuple[str, str], str] = {
    ("mandate_store", "get_mandate_store"): "returns the MandateStore singleton, opens no session",
    ("sim_engine", "get_sim_engine"): "returns the SimEngine singleton, opens no session",
    ("journal_store", "get_journal_store"): "returns the JournalStore singleton, opens no session",
    ("market_data", "get_market_data_provider"): "returns the provider singleton (quote/history are the blocking calls)",
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


# ── SERVICE LEVEL (DEF200 part 2, 2026-11-22) ────────────────────────────────
#
# The handler census above is one hop: a handler that `await`s a service method
# is exempt (an async callable cannot block in ITS OWN body), so the sync I/O
# inside that method was never traced. This level reads every `async def` under
# app/services/ — a superset of "those handlers await", since any async service
# function can be awaited from a handler directly or through another service —
# and flags a blocking call made directly in its own body:
#
#   - a `get_session(` call, or a call into a section-B module (resolved through
#     imports, through a parameter / `self.<attr>` / local variable typed as a
#     section-B class, or through a sync helper in the same file that itself
#     blocks — followed to a fixpoint, because a sync helper chain blocks
#     whatever its depth);
#   - `time.sleep`, builtin `open`, `os.*` filesystem calls, `shutil`,
#     `subprocess`, `requests`, sync `httpx` (but not `httpx.AsyncClient`),
#     `sqlite3.connect`, and the unambiguous `pathlib` I/O methods.
#
# Same exemptions as the handler level: a directly awaited call / `async for`
# iterable is async by construction; a REFERENCE handed to `asyncio.to_thread` /
# `run_in_threadpool` is not a call; nested defs are not part of the enclosing
# body (a nested `async def` is scanned in its own right). A bare call to a
# CapWords name is a constructor and is not treated as I/O. The hand-reviewed
# `_REVIEWED_NON_BLOCKING` allowlist is shared.
#
# KNOWN LIMIT, stated rather than discovered: attribute chains rooted in an
# untyped value (`obj.method()` where nothing says what `obj` is) are invisible,
# and method calls on a file object (`f.write(chunk)`) are caught only through
# the `open(...)` / `os.fdopen(...)` that produced it.

_BLOCKING_BARE_CALLS = {"open", "get_session"}
_BLOCKING_MODULE_FUNCS: dict[str, set[str] | None] = {
    "time": {"sleep"},
    "os": {
        "makedirs", "mkdir", "remove", "unlink", "rename", "replace", "fsync",
        "listdir", "scandir", "stat", "walk", "open", "fdopen", "rmdir",
        "utime", "chmod", "write", "read", "truncate", "ftruncate",
    },
    "shutil": None,
    "subprocess": None,
    "requests": None,
    "sqlite3": {"connect"},
    "urllib": None,
    "httpx": {"Client", "get", "post", "put", "patch", "delete", "request", "stream", "head"},
}
_BLOCKING_OS_PATH = {"exists", "isfile", "isdir", "getsize", "getmtime"}
_BLOCKING_PATH_METHODS = {
    "read_text", "write_text", "read_bytes", "write_bytes", "mkdir", "unlink",
    "iterdir", "rglob", "touch", "rmdir", "samefile",
}


def _call_chain(f: ast.expr) -> tuple[str | None, list[str]]:
    """(root_name, attrs_from_root_outward) for a call target: `a.b.c` -> (a, [b, c])."""
    attrs: list[str] = []
    node = f
    while isinstance(node, ast.Attribute):
        attrs.append(node.attr)
        node = node.value
    attrs.reverse()
    return (node.id if isinstance(node, ast.Name) else None), attrs


def _primitive_blocker(call: ast.Call) -> str | None:
    """Why this call is blocking in its own right, or None."""
    root, attrs = _call_chain(call.func)
    if not attrs:
        return root if root in _BLOCKING_BARE_CALLS else None
    if root in _BLOCKING_MODULE_FUNCS:
        allowed = _BLOCKING_MODULE_FUNCS[root]
        if allowed is None or attrs[0] in allowed:
            return f"{root}.{attrs[0]}"
        if root == "os" and attrs[0] == "path" and len(attrs) > 1 and attrs[1] in _BLOCKING_OS_PATH:
            return f"os.path.{attrs[1]}"
    if attrs[-1] == "get_session":
        return "get_session"
    if attrs[-1] in _BLOCKING_PATH_METHODS:
        return f".{attrs[-1]}"
    return None


def _annotation_module(ann: ast.expr | None, bindings: dict[str, str]) -> str | None:
    """The section-B module a parameter annotation names (`OverlayStore | None`,
    `Optional[OverlayStore]` and a plain `OverlayStore` all resolve)."""
    if ann is None:
        return None
    for node in ast.walk(ann):
        if isinstance(node, ast.Name) and node.id in bindings:
            return bindings[node.id]
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value in bindings:
            return bindings[node.value]
    return None


def _expr_module(expr: ast.expr | None, typed: dict[str, str], bindings: dict[str, str]) -> str | None:
    """The section-B module an expression's VALUE belongs to, if knowable."""
    if expr is None:
        return None
    if isinstance(expr, ast.Name):
        return typed.get(expr.id)
    if isinstance(expr, ast.Call):
        root, _ = _call_chain(expr.func)
        return bindings.get(root) if root else None
    if isinstance(expr, ast.BoolOp):
        for v in expr.values:
            m = _expr_module(v, typed, bindings)
            if m:
                return m
    if isinstance(expr, ast.IfExp):
        return _expr_module(expr.body, typed, bindings) or _expr_module(expr.orelse, typed, bindings)
    return None


def _param_types(fn: ast.AST, bindings: dict[str, str]) -> dict[str, str]:
    out: dict[str, str] = {}
    a = fn.args  # type: ignore[attr-defined]
    for arg in [*a.posonlyargs, *a.args, *a.kwonlyargs]:
        m = _annotation_module(arg.annotation, bindings)
        if m:
            out[arg.arg] = m
    return out


def _own_nodes(fn: ast.AST):
    """Every node in a function's own body, not descending into nested defs or lambdas."""
    stack = list(ast.iter_child_nodes(fn))
    skip = {id(n) for n in getattr(fn, "decorator_list", [])}
    a = getattr(fn, "args", None)
    if a is not None:
        skip |= {id(d) for d in [*a.defaults, *a.kw_defaults] if d is not None}
    while stack:
        node = stack.pop()
        if id(node) in skip:
            continue
        yield node
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)):
            continue
        stack.extend(ast.iter_child_nodes(node))


def _is_self_attr(t: ast.expr) -> bool:
    return isinstance(t, ast.Attribute) and isinstance(t.value, ast.Name) and t.value.id == "self"


def _class_attr_types(cls: ast.ClassDef, bindings: dict[str, str]) -> dict[str, str]:
    """{attr: module} for `self.<attr> = <value typed as a section-B class>` anywhere
    in the class (an annotated constructor parameter, or a call into a section-B
    module such as `get_overlay_store()`)."""
    out: dict[str, str] = {}
    for m in cls.body:
        if not isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        typed = _param_types(m, bindings)
        for node in ast.walk(m):
            if isinstance(node, ast.AnnAssign) and _is_self_attr(node.target):
                mod = _annotation_module(node.annotation, bindings) or _expr_module(node.value, typed, bindings)
                if mod:
                    out[node.target.attr] = mod
            elif isinstance(node, ast.Assign):
                mod = _expr_module(node.value, typed, bindings)
                if mod:
                    for t in node.targets:
                        if _is_self_attr(t):
                            out[t.attr] = mod
    return out


def _function_blockers(
    fn: ast.AST,
    bindings: dict[str, str],
    attr_types: dict[str, str],
    local_fn_blockers: dict[str, str],
    local_method_blockers: dict[str, str],
) -> dict[str, list[int]]:
    """Reasons `fn` blocks in its own body (empty = clean). Used for async
    functions (to flag them) and for sync helpers (to learn which local callees
    block)."""
    typed = _param_types(fn, bindings)
    own = list(_own_nodes(fn))
    for node in own:
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            m = _expr_module(node.value, typed, bindings)
            if m:
                typed[node.targets[0].id] = m
    exempt: set[int] = set()
    for node in own:
        if isinstance(node, ast.Await) and isinstance(node.value, ast.Call):
            exempt.add(id(node.value))
        elif isinstance(node, ast.AsyncFor) and isinstance(node.iter, ast.Call):
            exempt.add(id(node.iter))
    reasons: dict[str, list[int]] = {}
    for node in own:
        if not isinstance(node, ast.Call) or id(node) in exempt:
            continue
        prim = _primitive_blocker(node)
        if prim:
            reasons.setdefault(prim, []).append(node.lineno)
            continue
        root, attrs = _call_chain(node.func)
        if root is None:
            f = node.func
            if isinstance(f, ast.Attribute) and isinstance(f.value, ast.Call):
                inner, inner_attrs = _call_chain(f.value.func)
                if inner in bindings and not inner_attrs and (bindings[inner], f.attr) not in _REVIEWED_NON_BLOCKING:
                    reasons.setdefault(bindings[inner], []).append(node.lineno)
            continue
        if not attrs:
            if root[:1].isupper():
                continue
            if root in local_fn_blockers:
                reasons.setdefault(f"local:{root}", []).append(node.lineno)
            elif (
                root in bindings
                and (bindings[root], root) not in _REVIEWED_NON_BLOCKING
                and (bindings[root], root) not in _SINGLETON_ACCESSORS
            ):
                reasons.setdefault(bindings[root], []).append(node.lineno)
            continue
        if root == "self":
            if len(attrs) == 1 and attrs[0] in local_method_blockers:
                reasons.setdefault(f"local:{attrs[0]}", []).append(node.lineno)
            elif len(attrs) >= 2 and attrs[0] in attr_types:
                mod = attr_types[attrs[0]]
                if (mod, attrs[1]) not in _REVIEWED_NON_BLOCKING:
                    reasons.setdefault(mod, []).append(node.lineno)
            continue
        mod = typed.get(root) or bindings.get(root)
        if mod and (mod, attrs[0]) not in _REVIEWED_NON_BLOCKING:
            reasons.setdefault(mod, []).append(node.lineno)
    return reasons


def flag_service_functions(
    tree: ast.Module, bindings: dict[str, str], details: dict[str, dict[str, list[int]]] | None = None
) -> tuple[list[str], int]:
    """([qualified async function name (via: ...)], async_function_count) for one
    parsed service module. Split out of [census_services] so the detection can be
    pinned on synthetic source."""
    flagged: list[str] = []
    total = 0

    classes = [n for n in tree.body if isinstance(n, ast.ClassDef)]
    sync_fns = [n for n in tree.body if isinstance(n, ast.FunctionDef)]
    class_attrs = {c.name: _class_attr_types(c, bindings) for c in classes}

    units: list[tuple[str | None, ast.FunctionDef]] = [(None, f) for f in sync_fns]
    for c in classes:
        units += [(c.name, m) for m in c.body if isinstance(m, ast.FunctionDef)]
    fn_block: dict[str, str] = {}
    meth_block: dict[str, dict[str, str]] = {c.name: {} for c in classes}
    changed = True
    while changed:
        changed = False
        for cname, f in units:
            table = fn_block if cname is None else meth_block[cname]
            if f.name in table:
                continue
            why = _function_blockers(
                f, bindings, class_attrs.get(cname, {}) if cname else {},
                fn_block, meth_block.get(cname, {}) if cname else {},
            )
            if why:
                table[f.name] = ",".join(sorted(why))
                changed = True

    def visit(node: ast.AST, cname: str | None, qual: str) -> None:
        nonlocal total
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.ClassDef):
                visit(child, child.name, f"{qual}{child.name}.")
            elif isinstance(child, ast.AsyncFunctionDef):
                total += 1
                why = _function_blockers(
                    child, bindings, class_attrs.get(cname, {}) if cname else {},
                    fn_block, meth_block.get(cname, {}) if cname else {},
                )
                if why:
                    flagged.append(f"{qual}{child.name} (via: {', '.join(sorted(why))})")
                    if details is not None:
                        details[f"{qual}{child.name}"] = why
                visit(child, cname, f"{qual}{child.name}.")
            elif isinstance(child, ast.FunctionDef):
                visit(child, cname, f"{qual}{child.name}.")
            else:
                visit(child, cname, qual)

    visit(tree, None, "")
    return flagged, total


def census_services(details: dict[str, dict[str, list[int]]] | None = None) -> dict:
    registry = {**_sync_db_modules(), **_KNOWN_SYNC_HTTP_MODULES}
    flagged: list[str] = []
    total = 0
    for path in sorted(SERVICES_DIR.rglob("*.py")):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except SyntaxError as e:  # pragma: no cover
            print(f"SKIP {path.name}: {e}", file=sys.stderr)
            continue
        bindings = _names_imported_from(tree, set(registry) - {path.stem})
        per_file: dict[str, dict[str, list[int]]] = {}
        f, n = flag_service_functions(tree, bindings, per_file)
        total += n
        if details is not None:
            details.update({f"{path.relative_to(SERVICES_DIR).as_posix()}::{k}": v for k, v in per_file.items()})
        rel = path.relative_to(SERVICES_DIR).as_posix()
        flagged.extend(f"{rel}::{x}" for x in f)
    return {"total_async_service_functions": total, "service_level_flagged": flagged}


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

    detail: dict[str, dict[str, list[int]]] = {}
    svc = census_services(detail)
    sf = svc["service_level_flagged"]
    print(f"\n── D. Async SERVICE functions with a blocking call in their own body "
          f"({len(sf)} of {svc['total_async_service_functions']}) ──")
    for site in sf:
        print(f"  {site}")
        if "--lines" in sys.argv:
            for reason, lines in detail[site.split(" (via:")[0]].items():
                print(f"      {reason}: lines {sorted(set(lines))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
