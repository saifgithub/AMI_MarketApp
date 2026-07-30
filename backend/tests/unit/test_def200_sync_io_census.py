"""DEF200 census — pins the AST logic backend/scripts/def200_sync_io_census.py
uses, and guards against it silently going vacuous (finding nothing) as this
codebase moves. Not a pass/fail gate on the underlying defect (DEF200 itself
stays open until the actual conversion work lands) — a measurement tool that
under-reports quietly is worse than one that's simply absent, which is why
this exists at all, mirroring this project's vacuity-leg convention
elsewhere (bug_attachments' scrape check, DEF167's scanner test).
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from def200_sync_io_census import (  # noqa: E402
    _already_threadpooled,
    _calls_get_session,
    _fn_referenced_names,
    _names_imported_from,
    census,
)


def _parse_fn(src: str) -> ast.AsyncFunctionDef:
    tree = ast.parse(src)
    fn = tree.body[0]
    assert isinstance(fn, ast.AsyncFunctionDef)
    return fn


def test_calls_get_session_detects_a_direct_call():
    fn = _parse_fn("async def h():\n    with get_session() as s:\n        pass\n")
    assert _calls_get_session(fn) is True


def test_calls_get_session_is_false_when_absent():
    fn = _parse_fn("async def h():\n    return 1\n")
    assert _calls_get_session(fn) is False


def test_calls_get_session_detects_attribute_form():
    """A call reached as `store.get_session()` (attribute access), not just
    a bare name — the census must not miss the more common real shape."""
    fn = _parse_fn("async def h():\n    store.get_session()\n")
    assert _calls_get_session(fn) is True


def test_already_threadpooled_suppresses_detection():
    fn = _parse_fn(
        "async def h():\n"
        "    await run_in_threadpool(do_the_sync_thing)\n"
    )
    assert _already_threadpooled(fn) is True


def test_names_imported_from_resolves_plain_from_import():
    tree = ast.parse("from app.services.mandate_store import get_mandate_store\n")
    bindings = _names_imported_from(tree, {"mandate_store"})
    assert bindings == {"get_mandate_store": "mandate_store"}


def test_names_imported_from_resolves_aliased_import():
    tree = ast.parse("from app.services.mandate_store import get_mandate_store as gms\n")
    bindings = _names_imported_from(tree, {"mandate_store"})
    assert bindings == {"gms": "mandate_store"}


def test_names_imported_from_ignores_modules_outside_the_target_set():
    tree = ast.parse("from app.services.unrelated_thing import whatever\n")
    bindings = _names_imported_from(tree, {"mandate_store"})
    assert bindings == {}


def test_fn_referenced_names_includes_attribute_receivers():
    fn = _parse_fn("async def h():\n    mandate_store.get(x)\n")
    assert "mandate_store" in _fn_referenced_names(fn)


def test_census_vacuity_guard_against_the_real_codebase():
    """If this ever returns empty sections, the census is broken, not the
    codebase suddenly clean — DEF200 is still open."""
    result = census()
    assert result["total_async_handlers"] > 50, (
        "async-handler count collapsed — is API_DIR still pointing at "
        "backend/app/api/?"
    )
    assert result["section_a_direct_sync_db"], "section A went vacuous"
    assert result["section_c_onehop_reachable"], "section C went vacuous"
    assert len(result["section_b_registry"]) >= 10, "registry shrank a lot — re-check the grep"


def test_census_known_direct_site_still_flagged():
    """A specific, hand-verified-true site as of 2026-07-30 — if this stops
    appearing, either it was genuinely fixed (update this test) or the
    detector regressed (fix the detector)."""
    result = census()
    assert "room.py::stream_room" in result["section_a_direct_sync_db"]


def test_census_known_onehop_site_still_flagged():
    result = census()
    sites = {s.split(" ")[0] for s in result["section_c_onehop_reachable"]}
    assert "sim.py::submit_trade" in sites
