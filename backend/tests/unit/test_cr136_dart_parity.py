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

This parses the `.dart` sources rather than importing anything, the way
`test_def141_audit_pins_are_collected.py` does: the Dart side cannot be imported
from pytest, and `AMI_TRADE_BINDINGS.md`'s regression command is a pytest one, so
a guard that lives here is a guard that actually runs on every lane.
"""

from __future__ import annotations

import re
from pathlib import Path

from app.api.portfolio import HEALTH_UNAVAILABLE_CODE
from app.services.health_gate import DAILY_CAP_CODE, GATE_CLOSED_CODE
from app.services.portfolio_health_constants import METRIC_VALUE_UNIT

REPO_ROOT = Path(__file__).resolve().parents[3]
MODEL_DART = REPO_ROOT / "mobile" / "lib" / "models" / "portfolio_health.dart"
FINDING_DART = (
    REPO_ROOT / "mobile" / "lib" / "screens" / "sim"
    / "portfolio_health_finding_screen.dart"
)

_ENTRY_RE = re.compile(r"'([a-z_]+)':\s*HealthMetricUnit\.([a-z]+),")


def _dart_units() -> dict[str, str]:
    source = MODEL_DART.read_text(encoding="utf-8")
    start = source.index("const Map<String, HealthMetricUnit> kMetricValueUnit")
    body = source[start:source.index("};", start)]
    return dict(_ENTRY_RE.findall(body))


def test_the_dart_source_is_where_this_guard_thinks_it_is() -> None:
    """Non-vacuity. A moved or renamed file must fail here rather than turn both
    parity assertions into comparisons against an empty map."""
    assert MODEL_DART.exists(), f"{MODEL_DART} — move the guard, do not delete it"
    assert FINDING_DART.exists(), f"{FINDING_DART} — move the guard, do not delete it"
    assert _dart_units(), "kMetricValueUnit parsed empty — the literal's shape changed"


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
