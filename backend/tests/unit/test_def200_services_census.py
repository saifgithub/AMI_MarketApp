"""DEF200 part 2 — the SERVICE-level census, pinned on synthetic source.

`census_services()` (backend/scripts/def200_sync_io_census.py) reads every
`async def` under app/services/ and flags a blocking call made directly in its
own body. The real services now flag nothing, so "it still detects the known
shapes" can only be asserted on source written for the purpose — otherwise the
census could quietly stop detecting while the real count sits at zero (the
vacuity this suite exists to prevent). The shapes below are the ones the
2026-11-22 sweep actually found.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from def200_sync_io_census import census_services, flag_service_functions  # noqa: E402

_SB = {"OverlayStore": "overlay_store", "get_overlay_store": "overlay_store"}


def _svc(src: str, bindings: dict[str, str] | None = None) -> list[str]:
    flagged, _n = flag_service_functions(ast.parse(src), bindings if bindings is not None else _SB)
    return flagged


def test_a_self_attribute_typed_by_an_annotated_ctor_param_is_flagged():
    """BriefEngine.stream_chat: `self._store = store` with `store: OverlayStore`."""
    src = (
        "class E:\n"
        "    def __init__(self, store: OverlayStore):\n"
        "        self._store = store\n"
        "    async def chat(self):\n"
        "        return self._store.get_active(u)\n"
    )
    assert _svc(src) == ["E.chat (via: overlay_store)"]


def test_a_self_attribute_built_by_a_section_b_call_is_flagged():
    src = (
        "class E:\n"
        "    def __init__(self):\n"
        "        self._store = get_overlay_store()\n"
        "    async def chat(self):\n"
        "        return self._store.get_active(u)\n"
    )
    assert _svc(src) == ["E.chat (via: overlay_store)"]


def test_a_threadpooled_reference_is_clean():
    src = (
        "class E:\n"
        "    def __init__(self, store: OverlayStore):\n"
        "        self._store = store\n"
        "    async def chat(self):\n"
        "        return await asyncio.to_thread(self._store.get_active, u)\n"
    )
    assert _svc(src) == []


def test_a_local_sync_helper_that_blocks_is_flagged_through_a_chain():
    """`BriefEngine.propose` calls `self._compose_full_overlay`, which reads the
    store. A chain of sync helpers blocks whatever its depth."""
    src = (
        "class E:\n"
        "    def __init__(self, store: OverlayStore):\n"
        "        self._store = store\n"
        "    def _inner(self):\n"
        "        return self._store.get_active(u)\n"
        "    def _outer(self):\n"
        "        return self._inner()\n"
        "    async def propose(self):\n"
        "        return self._outer()\n"
    )
    assert _svc(src) == ["E.propose (via: local:_outer)"]


def test_a_module_level_sync_helper_that_opens_a_session_is_flagged():
    src = (
        "def _total(d):\n"
        "    with get_session() as s:\n"
        "        return 1\n"
        "async def go(d):\n"
        "    return _total(d)\n"
    )
    assert _svc(src) == ["go (via: local:_total)"]


def test_file_io_in_an_async_body_is_flagged():
    """save_attachment_streaming: mkdir, os.open, os.fdopen, unlink in the body."""
    src = (
        "async def save(d, out):\n"
        "    d.mkdir(parents=True)\n"
        "    fd = os.open(out, 0)\n"
        "    with os.fdopen(fd, 'wb') as f:\n"
        "        pass\n"
        "    out.unlink()\n"
    )
    [one] = _svc(src, {})
    assert one.startswith("save (via: ")
    for reason in (".mkdir", "os.open", "os.fdopen", ".unlink"):
        assert reason in one


def test_builtin_open_and_time_sleep_are_flagged_and_asyncio_sleep_is_not():
    assert _svc("async def a():\n    open('x')\n", {}) == ["a (via: open)"]
    assert _svc("async def a():\n    time.sleep(1)\n", {}) == ["a (via: time.sleep)"]
    assert _svc("async def a():\n    await asyncio.sleep(1)\n", {}) == []


def test_sync_http_is_flagged_and_the_async_client_is_not():
    assert _svc("async def a():\n    httpx.Client()\n", {}) == ["a (via: httpx.Client)"]
    assert _svc(
        "async def a():\n    async with httpx.AsyncClient() as c:\n        await c.get(u)\n", {}
    ) == []


def test_a_file_op_handed_to_to_thread_is_clean():
    src = (
        "async def save(d, out):\n"
        "    await asyncio.to_thread(d.mkdir, parents=True)\n"
        "    await asyncio.to_thread(out.unlink, missing_ok=True)\n"
    )
    assert _svc(src, {}) == []


def test_an_awaited_call_and_async_for_are_exempt():
    src = (
        "async def go(store: OverlayStore):\n"
        "    await store.aget(u)\n"
        "    async for x in store.stream(u):\n"
        "        pass\n"
    )
    assert _svc(src) == []


def test_a_nested_sync_def_is_not_part_of_the_enclosing_body():
    """A closure handed to `to_thread` runs off-loop; its body must not flag the
    async function that merely defines it."""
    src = (
        "async def go(u):\n"
        "    def _work():\n"
        "        with get_session() as s:\n"
        "            return 1\n"
        "    return await asyncio.to_thread(_work)\n"
    )
    assert _svc(src, {}) == []


def test_a_nested_async_function_is_scanned_in_its_own_right():
    """RoomRunner._respawn_run_from_row._pump."""
    src = (
        "async def outer():\n"
        "    async def _pump():\n"
        "        with get_session() as s:\n"
        "            pass\n"
        "    await _pump()\n"
    )
    assert _svc(src, {}) == ["outer._pump (via: get_session)"]


def test_a_constructor_call_is_not_io():
    assert _svc("async def a():\n    raise OverlayStore('x')\n") == []


def test_a_reviewed_non_blocking_call_is_not_flagged():
    b = {"room_cost_for_plan": "credit_service", "spend": "credit_service"}
    assert _svc("async def a(p):\n    return room_cost_for_plan(p)\n", b) == []
    assert _svc("async def a(p):\n    return spend(p)\n", b) == ["a (via: credit_service)"]


def test_a_blocking_call_in_a_decorator_or_default_is_not_the_bodys():
    src = "@cache(open('x'))\nasync def a(x=open('y')):\n    return 1\n"
    assert _svc(src, {}) == []


def test_a_method_called_on_a_singleton_accessor_is_flagged_not_the_accessor():
    """`get_journal_store().append(x)` blocks because of `.append`; the accessor
    alone (`store = get_journal_store()`) opens no session."""
    b = {"get_journal_store": "journal_store"}
    assert _svc("async def a(x):\n    get_journal_store().append(x)\n", b) == ["a (via: journal_store)"]
    assert _svc("async def a(x):\n    s = get_journal_store()\n    return 1\n", b) == []
    assert _svc("async def a(x):\n    await asyncio.to_thread(get_journal_store().append, x)\n", b) == []


def test_a_call_on_a_local_typed_by_an_accessor_is_flagged():
    """`provider = get_market_data_provider(); provider.get_price(t)` on the loop."""
    b = {"get_market_data_provider": "market_data"}
    assert _svc("async def a(t):\n    p = get_market_data_provider()\n    return p.get_price(t)\n", b) == [
        "a (via: market_data)"
    ]
    assert _svc("async def a(t):\n    p = get_market_data_provider()\n    return await asyncio.to_thread(p.get_price, t)\n", b) == []


def test_every_singleton_accessor_entry_still_names_a_real_function():
    from def200_sync_io_census import _SINGLETON_ACCESSORS, REPO

    for (module, name), reason in _SINGLETON_ACCESSORS.items():
        assert reason.strip(), f"({module}, {name}) has no reason"
        src = (REPO / "backend" / "app" / "services" / f"{module}.py").read_text(encoding="utf-8")
        assert f"def {name}(" in src, f"{module}.{name} no longer exists; drop the entry"


def test_the_service_census_sees_the_real_codebase():
    result = census_services()
    assert result["total_async_service_functions"] >= 40
