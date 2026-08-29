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
    _fn_called_names,
    _param_bindings,
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


def test_called_names_includes_attribute_receivers():
    fn = _parse_fn("async def h():\n    mandate_store.get(x)\n")
    assert "mandate_store" in _fn_called_names(fn)


# ── a CALL is not a MENTION (DEF200, 2026-08-28) ──────────────────────────────
#
# Section C used to collect every Name anywhere in a handler, so a parameter
# annotation, a `Depends()` factory and an `except` clause all read as blocking
# I/O. That is what kept 38 handlers on a list a hand-audit then cleared. The
# first attempt at the fix skipped annotations outright and silently dropped two
# genuinely blocking handlers, so both directions are pinned here.

def test_a_reference_handed_to_a_threadpool_is_not_a_call():
    """`asyncio.to_thread(sim.current_quote, t)` calls `asyncio`, not `sim` —
    this is `sim.py::quote`, the worked false positive in DEF200's own row."""
    fn = _parse_fn(
        "async def h(sim: SimEngine = Depends(get_sim_engine)):\n"
        "    return await asyncio.to_thread(sim.current_quote, 'AAPL')\n"
    )
    assert "sim" not in _fn_called_names(fn)


def test_a_call_on_a_threadpooled_object_still_counts():
    """`sim.py::get_holding_lots` awaits a threadpooled quote and THEN calls
    `sim.holding_lots(...)` straight on the loop. Being partly correct does not
    clear a handler."""
    fn = _parse_fn(
        "async def h(sim: SimEngine = Depends(get_sim_engine)):\n"
        "    q = await asyncio.to_thread(sim.current_quote, 'AAPL')\n"
        "    return sim.holding_lots(u, 't', current_price=q.price)\n"
    )
    assert "sim" in _fn_called_names(fn)


def test_an_annotation_types_the_parameter_rather_than_being_ignored():
    """The annotation is the only thing that says what `sim` IS. Dropping
    annotations wholesale is what lost the two handlers above."""
    fn = _parse_fn(
        "async def h(sim: SimEngine = Depends(get_sim_engine)):\n"
        "    return sim.holding_lots(u)\n"
    )
    assert _param_bindings(fn, {"SimEngine": "sim_engine"}) == {"sim": "sim_engine"}


def test_an_exception_class_is_not_io():
    """Naming a class is not calling it, so this needs no skip-list entry —
    which is why the skip list does not have one. Pinned so a future "be
    thorough" edit does not re-add inert entries."""
    fn = _parse_fn(
        "async def h():\n"
        "    try:\n        pass\n"
        "    except MandateStoreError:\n        raise\n"
    )
    assert "MandateStoreError" not in _fn_called_names(fn)


def test_a_call_in_a_parameter_default_runs_at_import_not_per_request():
    """`Depends(...)` and friends are evaluated once when the module loads. A
    blocking dependency is the dependency's row on this census, not the
    handler's."""
    fn = _parse_fn(
        "async def h(x = mandate_store.default_for(user)):\n    return x\n"
    )
    assert "mandate_store" not in _fn_called_names(fn)


def test_a_call_in_a_decorator_runs_at_import_not_per_request():
    fn = _parse_fn(
        "@journal_store.cached()\nasync def h():\n    return 1\n"
    )
    assert "journal_store" not in _fn_called_names(fn)


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
