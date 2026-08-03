"""CR136 M09 guard — the two Python↔Dart contracts the Health card reads across.

AT:R66 — CR136-M09 audit round 1, MAJOR M1. Both contracts were verified correct
by hand at audit time; neither had anything holding them correct over time. That
is the DEF210 shape exactly: a backend↔Dart enum parity that drifted and stayed
dark for ~10 weeks because nothing red ever appeared.

Contract 1 — the units map. `kMetricValueUnit` decides whether a metric's value
is multiplied by 100 before it is shown. The client's own guard throws only on a
metric it has never SEEN; a metric pinned to the WRONG unit renders silently at
100× or with a spurious `%`. Addition is covered, drift is not.

Contract 2 — the refusal codes. The Finding screen switches on three literal
strings. A divergence drops the user into the generic `default` panel instead of
the upgrade sheet or the daily-cap note — quieter than a wrong number, same class.

Contract 3 — the `insufficient_cause` enum (AT:R66, CR136-M04 audit round 1,
MAJOR M1). It widened 4 → 6 inside this CR with nothing holding the two sides
together, which is the DEF210 shape's SECOND occurrence and so gets a guard, not
a note. The card keys a tile's explanation off the cause; an unmatched cause used
to mean the tile silently vanished with nothing in its place. The card's branches
are now closed by construction, so this contract is no longer load-bearing for
*that* failure — it is load-bearing for the branches that still name a cause to
choose WHICH note, and for the day someone adds a seventh cause the card has
never seen. The backend side is read by introspection rather than from a
hand-listed set, so a new `INSUFFICIENT_*` constant enters this test on the
commit that mints it.

This parses the `.dart` sources rather than importing anything, the way
`test_def141_audit_pins_are_collected.py` does: the Dart side cannot be imported
from pytest, and `AMI_TRADE_BINDINGS.md`'s regression command is a pytest one, so
a guard that lives here is a guard that actually runs on every lane.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.api.portfolio import HEALTH_UNAVAILABLE_CODE
from app.services import portfolio_health_constants as health_constants
from app.services.health_gate import DAILY_CAP_CODE, GATE_CLOSED_CODE
from app.services.portfolio_health_constants import METRIC_VALUE_UNIT

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DART = REPO_ROOT / "mobile" / "lib" / "models" / "portfolio_health.dart"
FINDING_DART = (
    REPO_ROOT / "mobile" / "lib" / "screens" / "sim"
    / "portfolio_health_finding_screen.dart"
)

_ENTRY_RE = re.compile(r"'([a-z_]+)':\s*HealthMetricUnit\.([a-z]+),")
_CAUSE_CONST_RE = re.compile(r"const String (kCause\w+) = '([a-z_]+)';")
_CAUSE_MEMBER_RE = re.compile(r"\b(kCause\w+)\b")


def _dart_units() -> dict[str, str]:
    source = MODEL_DART.read_text(encoding="utf-8")
    start = source.index("const Map<String, HealthMetricUnit> kMetricValueUnit")
    body = source[start:source.index("};", start)]
    return dict(_ENTRY_RE.findall(body))


def _dart_causes() -> set[str]:
    """The wire strings reachable through `kInsufficientCauses`.

    Resolved through the named constants rather than read as literals out of the
    set, so a constant that is declared and then left OUT of the set is a
    divergence this sees. The card branches on the constants, so what is pinned
    here is what the card actually compares against."""
    source = MODEL_DART.read_text(encoding="utf-8")
    declared = dict(_CAUSE_CONST_RE.findall(source))
    start = source.index("const Set<String> kInsufficientCauses")
    body = source[start:source.index("};", start)]
    members = _CAUSE_MEMBER_RE.findall(body)
    unresolved = [m for m in members if m not in declared]
    assert not unresolved, (
        f"kInsufficientCauses names {unresolved}, which no `const String kCause…`"
        " declares — the parse would silently drop them."
    )
    return {declared[m] for m in members}


def _backend_causes() -> set[str]:
    """Every `INSUFFICIENT_*` string the constants module defines, by
    introspection. A seventh cause is in this set the moment it is minted,
    which is the point: the guard has to fail on the day of the widening."""
    return {
        v
        for k, v in vars(health_constants).items()
        if k.startswith("INSUFFICIENT_") and isinstance(v, str)
    }


def test_the_dart_source_is_where_this_guard_thinks_it_is() -> None:
    """Non-vacuity. A moved or renamed file must fail here rather than turn both
    parity assertions into comparisons against an empty map."""
    assert MODEL_DART.exists(), f"{MODEL_DART} — move the guard, do not delete it"
    assert FINDING_DART.exists(), f"{FINDING_DART} — move the guard, do not delete it"
    assert _dart_units(), "kMetricValueUnit parsed empty — the literal's shape changed"
    assert _dart_causes(), "kInsufficientCauses parsed empty — the set's shape changed"
    assert len(_backend_causes()) >= 6, (
        "the INSUFFICIENT_* introspection found fewer constants than CR136 shipped"
        " — a renamed prefix would make the set comparison vacuously true"
    )


def test_the_units_map_matches_the_backend_metric_for_metric() -> None:
    dart = _dart_units()
    assert dart == METRIC_VALUE_UNIT, (
        "kMetricValueUnit has drifted from METRIC_VALUE_UNIT.\n"
        f"  only in Dart:    {sorted(set(dart) - set(METRIC_VALUE_UNIT))}\n"
        f"  only in backend: {sorted(set(METRIC_VALUE_UNIT) - set(dart))}\n"
        "  disagreeing:     "
        + str({
            k: (dart[k], METRIC_VALUE_UNIT[k])
            for k in set(dart) & set(METRIC_VALUE_UNIT)
            if dart[k] != METRIC_VALUE_UNIT[k]
        })
        + "\nA wrong unit renders at 100× or with a spurious percent sign and"
        " throws nothing (DEF210)."
    )


def test_the_insufficient_cause_enum_matches_the_card_as_a_set() -> None:
    """A widening must fail HERE, on the commit that mints the seventh cause —
    not later, when a reader notices a tile is missing from their card."""
    dart = _dart_causes()
    backend = _backend_causes()
    assert dart == backend, (
        "kInsufficientCauses has drifted from the backend's INSUFFICIENT_*.\n"
        f"  only in Dart:    {sorted(dart - backend)}\n"
        f"  only in backend: {sorted(backend - dart)}\n"
        "A cause the card has never seen takes the generic branch, which is now"
        " safe by construction — but any branch that names a cause to pick the"
        " RIGHT copy stops matching, and nothing throws (DEF210)."
    )


def test_every_refusal_code_the_card_switches_on_still_exists() -> None:
    """The Dart side owns the `case` labels; the backend owns the strings. A
    divergence routes the user to the generic panel instead of the upgrade sheet
    or the daily-cap note."""
    source = FINDING_DART.read_text(encoding="utf-8")
    for code in (GATE_CLOSED_CODE, DAILY_CAP_CODE, HEALTH_UNAVAILABLE_CODE):
        assert f"case '{code}':" in source, (
            f"{FINDING_DART.name} has no `case '{code}':` — the backend emits it,"
            " so the card would fall through to the generic default panel."
        )
