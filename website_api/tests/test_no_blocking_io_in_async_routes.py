"""Structural guard: no blocking HTTP call reachable from an `async def` route.

website_api runs `uvicorn` with no `--workers` flag (single event loop, single
process — see docker-compose.yml's `api-website` service and the Dockerfile
CMD). A synchronous `httpx.get/post/...` call made directly from an `async def`
route handler parks that one event loop for the entire network round-trip,
stalling *every* concurrent request on the process. Under the bot flood
Turnstile exists to absorb, that is self-inflicted DoS amplification.

This was found independently by audit (CR049 round 1, MAJOR) in
`turnstile.py`/`email_service.py` and is the SAME CLASS already flagged as an
MVP show-stopper in CR036 for the app backend. Per CLAUDE.md, a second
occurrence of a failure class earns a guard, not just a fix: this test walks
the static call graph from every `async def` route handler and fails the
build if it can reach a synchronous `httpx` call.

Deliberately does NOT flag the backend's `magic_link_start` pattern
(`backend/app/api/auth.py`) — that route is a sync `def`, so FastAPI runs it
in a threadpool and the event loop is never blocked. Only `async def` routes
calling sync HTTP are the bug.
"""

from __future__ import annotations

import ast
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_APP = _REPO_ROOT / "website_api" / "app"

# Module-level httpx calls that block the event loop when awaited from nothing
# (i.e. called directly, not through AsyncClient).
_BLOCKING_HTTPX_FUNCS = {"get", "post", "put", "patch", "delete", "request", "stream"}


def _iter_py(root: Path) -> list[Path]:
    return [p for p in root.rglob("*.py") if "__pycache__" not in p.parts]


class _ModuleInfo:
    """One module's function defs + which module-level names they call."""

    def __init__(self, path: Path, tree: ast.Module):
        self.path = path
        self.functions: dict[str, ast.AsyncFunctionDef | ast.FunctionDef] = {}
        self.imported_names: dict[str, str] = {}  # local name -> "module.attr" or module

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    self.imported_names[alias.asname or alias.name] = (
                        f"{node.module}.{alias.name}"
                    )
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    self.imported_names[alias.asname or alias.name.split('.')[0]] = alias.name


def _blocking_httpx_call_sites(fn: ast.AST) -> list[str]:
    """Direct `httpx.<blocking-verb>(...)` calls inside fn, e.g. 'httpx.post'."""
    hits = []
    for node in ast.walk(fn):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if (
            isinstance(f, ast.Attribute)
            and f.attr in _BLOCKING_HTTPX_FUNCS
            and isinstance(f.value, ast.Name)
            and f.value.id == "httpx"
        ):
            hits.append(f"httpx.{f.attr}")
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
        if "routes" not in mod.path.parts:
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

    offenders = _blocking_httpx_call_sites(fn)
    for called_name in _called_names(fn):
        for mod in modules:
            target = mod.functions.get(called_name)
            if target is not None and target is not fn:
                offenders += [
                    f"{o} (via {called_name} in {mod.path.relative_to(_REPO_ROOT)})"
                    for o in _find_blocking_reachable(target, modules, seen)
                ]
    return offenders


def test_no_blocking_httpx_call_reachable_from_async_route():
    modules = [_ModuleInfo(p, ast.parse(p.read_text())) for p in _iter_py(_APP)]
    handlers = _route_handlers(modules)
    assert handlers, "no async route handlers found — guard is not exercising anything"

    offenders: list[str] = []
    for mod, fn in handlers:
        hits = _find_blocking_reachable(fn, modules, seen=set())
        offenders += [
            f"{mod.path.relative_to(_REPO_ROOT)}:{fn.name} -> {h}" for h in hits
        ]

    assert not offenders, (
        "async def route handler(s) can reach a synchronous httpx call — this "
        "blocks the single event loop for the whole network round-trip on a "
        "no-`--workers` uvicorn process (CR049 round-1 MAJOR, same class as "
        "CR036). Use `httpx.AsyncClient` + `await`, or make the route handler "
        "a sync `def` so FastAPI runs it in a threadpool:\n" + "\n".join(offenders)
    )
