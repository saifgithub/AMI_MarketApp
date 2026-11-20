"""ISS001 Phase 1 — the control as it is wired into THIS app (engine, baseline, schema, config).

`test_iss001_claim.py` proves the mechanism on synthetic models. This file proves the mechanism
is actually attached to `get_engine()`'s engine, that the pre-control insert sites are an owned
list that cannot grow or rot silently, and that the schema's own "unique" keys are real.

"Green" here must not be able to mean "not checked": the first canary inserts a collidable row
through the REAL app engine from a frame that counts as application code, and requires a raise.
Delete the `_install_insert_tripwire(_engine)` line in `app/db/session.py` and it goes red.
"""

from __future__ import annotations

import ast
import os
import re
from pathlib import Path

import pytest

from app.core.config import Settings
from app.db import ami_claim as ac
from app.db import models
from app.db.base import Base
from app.db.insert_baseline import INSERT_BASELINE
from app.db.session import _install_insert_tripwire, get_engine, get_session

_APP = Path(ac._APP_DIR)


def _as_app_code(rel: str, src: str, ns: dict | None = None) -> dict:
    """Compile `src` as if it lived at `app/<rel>` so frames inside it count as application code."""
    scope = ns if ns is not None else {}
    exec(compile(src, str(_APP / rel), "exec"), scope)
    return scope


# ---- the hook is on the app engine, and it bites ----------------------------------------


def test_the_tripwire_is_installed_on_the_app_engine_in_raise_mode():
    assert Settings().insert_tripwire_mode == "raise", "tests/conftest.py must run the suite in raise mode"
    assert ac.tripwire_installed(get_engine())


def test_canary_unsanctioned_insert_through_the_real_engine_from_app_code_raises():
    ns = _as_app_code("services/_iss001_canary.py", (
        "from app.db import get_session\n"
        "from app.db.models import ClientReleaseFloorRow\n"
        "def make_floor_the_old_way(build):\n"
        "    with get_session() as s:\n"
        "        s.add(ClientReleaseFloorRow(min_build=build))\n"
    ))
    with pytest.raises(ac.UnclaimedInsert) as e:
        ns["make_floor_the_old_way"](910001)
    assert "services/_iss001_canary.py" in str(e.value)


def test_canary_factory_built_insert_through_the_real_engine_raises():
    """The shape the AST guard could not see: the row is built by a factory in one function and
    added in another, with no select(Model) anywhere in the frame."""
    ns = _as_app_code("services/_iss001_canary2.py", (
        "from app.db import get_session\n"
        "def build(model, **kw):\n"
        "    return model(**kw)\n"
        "def save(model, **kw):\n"
        "    with get_session() as s:\n"
        "        s.add(build(model, **kw))\n"
    ))
    with pytest.raises(ac.UnclaimedInsert):
        ns["save"](models.ClientReleaseFloorRow, min_build=910003)


def test_claim_through_the_real_engine_is_allowed_and_atomic():
    with get_session() as s:
        vals = {"headline": "h", "body_en": "b"}
        first = ac.claim(s, models.ClientReleaseFloorRow, key={"min_build": 910002}, values=vals)
        again = ac.claim(s, models.ClientReleaseFloorRow, key={"min_build": 910002}, values=vals)
    assert (first.created, again.created) == (True, False)


def test_off_is_loud_outside_tests_and_silent_inside(monkeypatch):
    from sqlalchemy import create_engine

    logged: list[str] = []
    monkeypatch.setattr("app.db.session.logger.error", lambda event, **kw: logged.append(event))
    monkeypatch.setattr("app.db.session.settings.insert_tripwire_mode", "off")
    eng = create_engine("sqlite://")
    _install_insert_tripwire(eng, under_tests=False)
    assert logged == ["insert_tripwire_off"] and not ac.tripwire_installed(eng)
    logged.clear()
    _install_insert_tripwire(eng, under_tests=True)
    assert logged == []


def test_default_mode_is_log_in_settings_and_in_compose():
    """Alpha and Beta default to `log`; the compose line is what actually reaches the container."""
    assert Settings.model_fields["insert_tripwire_mode"].default == "log"
    compose = (_APP.parent.parent / "docker-compose.yml").read_text()
    assert "INSERT_TRIPWIRE_MODE: ${INSERT_TRIPWIRE_MODE:-log}" in compose


def test_a_typoed_mode_fails_boot_instead_of_meaning_off():
    with pytest.raises(Exception):
        Settings(_env_file=None, insert_tripwire_mode="enforce")


# ---- the pre-control sites are an owned list, not a silent allowlist ---------------------


def _module_path(filename: str) -> Path:
    """DEF308's `_UNREVIEWED` names files under app/services/ (the AST guard scans only there)."""
    path = _APP / "services" / filename
    assert path.is_file(), f"app/services/{filename} not found"
    return path


def _function_names(path: Path) -> set[str]:
    return {n.name for n in ast.walk(ast.parse(path.read_text(encoding="utf-8")))
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}


def test_every_baseline_entry_names_a_real_table_and_a_real_function():
    """A converted or deleted site must leave the list: a stale entry hides the next real one."""
    tables = set(Base.metadata.tables)
    for (table, site), owner in INSERT_BASELINE.items():
        rel, _, func = site.partition("::")
        assert table in tables, f"baseline names unknown table {table!r}"
        assert owner.strip(), f"baseline entry {(table, site)} has no owner/reason"
        path = _APP / rel
        assert path.is_file(), f"baseline names a file that no longer exists: {rel}"
        assert func in _function_names(path), f"{rel} has no function {func!r}: delete the baseline entry"


def test_the_nine_def308_pinned_sites_are_all_in_the_baseline():
    """DEF308's `_UNREVIEWED` is frozen (founder, 2026-08-15). Phase 1 touches none of them, so
    each must be reported by the tripwire and carried here — if one is missing, either it was
    fixed (then it must also leave the AST pin) or the tripwire cannot see it."""
    from tests.unit.test_p15_check_then_insert_guard import _UNREVIEWED

    assert len(_UNREVIEWED) == 9
    for filename, func, model in sorted(_UNREVIEWED):
        table = getattr(models, model).__table__.name
        site = f"{_module_path(filename).relative_to(_APP).as_posix()}::{func}"
        assert (table, site) in INSERT_BASELINE, f"DEF308 site {(table, site)} is not in INSERT_BASELINE"
        assert "DEF308" in INSERT_BASELINE[(table, site)]


# ---- schema_truth: the unique keys that do not deduplicate what their name says ----------

# One entry per finding, each with the lane that owns the decision. A 5th finding fails the
# build; a resolved one fails it too, forcing its removal here — never a silent allowlist.
# Resolution is either `info={"null_means_no_key": "<why>"}` on the nullable column ("NULL means
# no dedupe wanted") or a partial unique index covering the NULL rows (DEF499's fix shape).
# DEF499 resolved sim_portfolios.uq_portfolio_user_kind_run and
# portfolio_nav_daily.uq_nav_user_run_date (migration def499a0b0c0d2): they must NOT appear.
_SCHEMA_TRUTH_PINNED: dict[str, str] = {
    "journal_entries.uq_journal_dedupe": "journal lane — expected null_means_no_key (entries without a dedupe_key are not deduped)",
    "notifications.uq_notifications_dedupe": "inbox/notifications lane — expected null_means_no_key (source_ref optional)",
    "career_events.uq_career_event_stipend_period": "career/stipend lane — expected null_means_no_key (period_key only on stipends)",
    "news_archive.uq_news_archive_item": "news lane — url nullable; decide partial index vs null_means_no_key",
}


def test_schema_truth_findings_are_exactly_the_pinned_owned_list():
    found = {f.split(":", 1)[0] for f in ac.schema_truth(Base.metadata)}
    assert found - set(_SCHEMA_TRUTH_PINNED) == set(), (
        f"new composite unique key with a nullable column (vacuous for NULL rows): {sorted(found - set(_SCHEMA_TRUTH_PINNED))}. "
        "Declare Column.info['null_means_no_key'], or add a partial unique index (see DEF499)."
    )
    assert set(_SCHEMA_TRUTH_PINNED) - found == set(), (
        f"resolved finding(s) still pinned: {sorted(set(_SCHEMA_TRUTH_PINNED) - found)} — delete them from _SCHEMA_TRUTH_PINNED"
    )


def test_def499_tables_are_no_longer_vacuous():
    found = "\n".join(ac.schema_truth(Base.metadata))
    assert "sim_portfolios" not in found and "portfolio_nav_daily" not in found


def test_claim_accepts_the_def499_training_key_now_that_the_partial_index_exists():
    arb = ac._effective_arbiter(models.SimPortfolioRow.__table__, {"user_id": "u", "kind": "training", "run_id": None})
    assert arb is not None and arb.where
    arb = ac._effective_arbiter(models.PortfolioNavDailyRow.__table__, {"user_id": "u", "as_of_date": "2026-01-01", "run_id": None})
    assert arb is not None and arb.where


# ---- literal-grep pins -------------------------------------------------------------------


def _app_sources() -> list[tuple[Path, str]]:
    return [(p, p.read_text(encoding="utf-8")) for p in _APP.rglob("*.py")
            if "__pycache__" not in p.parts and p.name != "ami_claim.py"]


def test_every_unclaimed_call_carries_a_reason_and_the_count_is_pinned():
    """`unclaimed()` is the one in-code escape hatch. Count the calls from the AST (a literal
    count, not an inference), so a new one is a visible diff. Phase 1 uses none: pre-control
    sites ride INSERT_BASELINE."""
    calls = []
    for path, src in _app_sources():
        for node in ast.walk(ast.parse(src)):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            if (isinstance(fn, ast.Name) and fn.id == "unclaimed") or (isinstance(fn, ast.Attribute) and fn.attr == "unclaimed"):
                why = next((k.value for k in node.keywords if k.arg == "why"), None)
                ok = isinstance(why, ast.Constant) and isinstance(why.value, str) and why.value.strip()
                assert ok, f"{path.name}:{node.lineno}: unclaimed() without a literal non-empty why="
                calls.append((path.name, node.lineno))
    assert len(calls) == 0, f"unclaimed() count changed to {len(calls)} — update this pin deliberately: {calls}"


def test_session_merge_is_banned_in_app_code():
    """Session.merge is a SELECT-then-INSERT inside SQLAlchemy that a read-side detector cannot
    see (the tripwire still sees its INSERT). Zero uses today; keep it that way."""
    offenders = [p.name for p, src in _app_sources() if re.search(r"\.merge\(", src)]
    assert offenders == [], f"`.merge(` found in app/: {offenders}"


def test_the_tripwire_module_is_the_only_place_that_opens_the_listener_on_an_engine_class():
    """Install on the INSTANCE: alembic's own engine legitimately INSERTs data migrations."""
    offenders = [p.name for p, src in _app_sources()
                 if re.search(r"event\.listen\(\s*Engine\b", src)]
    assert offenders == []
    assert os.path.exists(_APP / "db" / "ami_claim.py")
