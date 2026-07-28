"""CR106 B1 — `verdict.level_provenance`: where each price actually came from.

`room_runner` mints a missing stop at `entry * 0.94` and a missing target at
`entry * 1.13`, and substitutes the Trader's number for an entry the PM never
stated. Until now the ONLY disclosure of that was a sentence appended to
`reason`, which survives being read as prose but does not survive being drawn:
the CR106 Verdict Board clamps `reason` behind a `WHY` expander and promotes the
same three numbers into a to-scale risk/reward ribbon with a computed ratio.

A ribbon drawn from a minted stop, at the same weight as a stated one, is a
DEF059-shaped lie in a nicer typeface. So the ribbon is **gated** on this field
(CR106 T-PROV) and derived levels render hollow-capped.

What is pinned here:
  - the three sources are distinguished, including `trader` for a substituted
    entry — the case a two-value flag would have missed;
  - a minted level is NEVER labelled `pm`;
  - the prose disclosure the field replaces is still emitted (T-PROV again: the
    graphic must not be bought by demoting the existing honesty);
  - the field reaches the Journal payload, because that is the surface CR106
    §3.4 has to degrade per entry;
  - a verdict with no prices carries no provenance — absent means "not
    recorded", never "all from the PM" (T-BACKFILL).
"""

from __future__ import annotations

from uuid import uuid4

from app.schemas import AgentId
from app.schemas.room import VerdictAction
from app.services.coach_engine import hydrate_coach_mandate
from app.services.room_runner import RoomRunner, build_journal_entry_for_run
from tests.unit.test_room_runner import _FakeGateway, _collect


def _run_with_pm(pm_json: str):
    """Convene with a fake gateway whose PM returns `pm_json`, and hand back
    the (verdict, run) pair. The Trader's canned line fixes the numbers the
    substitution path would fall back to."""
    fake = _FakeGateway(replies={
        "trader": "Trader: BUY 3% at $150, stop $141, target $172.",
        "portfolio_manager": pm_json,
    })
    runner = RoomRunner(llm=fake)  # type: ignore[arg-type]
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    verdict = next(e.verdict for e in events if e.kind == "verdict")
    return verdict, runner.get_run(events[0].run_id)


_PM_ALL_STATED = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 150, "stop": 141, '
    '"target": 172, "horizon_days": 42, "narration": "PM: APPROVE."}'
)
_PM_NO_STOP_NO_TARGET = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": 200, "stop": null, '
    '"target": null, "horizon_days": 42, "narration": "PM: APPROVE."}'
)
_PM_NO_ENTRY = (
    '{"action": "APPROVE", "size_pct": 3.0, "entry": null, "stop": 141, '
    '"target": 172, "horizon_days": 42, "narration": "PM: APPROVE."}'
)


def test_levels_the_pm_stated_are_attributed_to_the_pm():
    verdict, _ = _run_with_pm(_PM_ALL_STATED)
    assert verdict.action == VerdictAction.APPROVE.value
    assert verdict.level_provenance == {
        "entry": "pm",
        "stop": "pm",
        "target": "pm",
    }


def test_a_minted_stop_and_target_are_never_labelled_pm():
    """`entry * 0.94` / `entry * 1.13` are AMI's protective levels, not a
    decision. The board draws them hollow on the strength of this."""
    verdict, _ = _run_with_pm(_PM_NO_STOP_NO_TARGET)
    assert verdict.level_provenance is not None
    assert verdict.level_provenance["stop"] == "ami_default"
    assert verdict.level_provenance["target"] == "ami_default"
    # Non-vacuity: the minted numbers really are the 6%/13% pair off entry 200.
    assert verdict.stop == 188.0
    assert verdict.target == 226.0
    # …and the entry itself was stated, so it is NOT swept into the same bucket.
    assert verdict.level_provenance["entry"] == "pm"


def test_an_entry_the_pm_omitted_is_attributed_to_the_trader_not_the_pm():
    """This is the case `entry` needs a THIRD value for:
    `entry = _safe_float(parsed.get("entry")) or ctx.trader_entry` substitutes
    silently, and a two-state stated/derived flag would have called the
    Trader's price a PM decision."""
    verdict, _ = _run_with_pm(_PM_NO_ENTRY)
    assert verdict.level_provenance is not None
    assert verdict.level_provenance["entry"] == "trader"
    assert verdict.level_provenance["stop"] == "pm"


def test_the_prose_disclosure_is_still_emitted_alongside_the_field():
    """T-PROV: the board clamps `reason` behind an expander. Buying the ribbon
    by deleting the sentence that used to be the only disclosure would be a net
    loss of honesty, so the field is ADDITIVE — both must be present."""
    verdict, _ = _run_with_pm(_PM_NO_STOP_NO_TARGET)
    assert "not stated by the PM" in verdict.reason
    assert "stop/target" in verdict.reason


def test_provenance_reaches_the_journal_payload():
    """CR106 §3.4 degrades the Journal board per ENTRY, off the snapshot the
    payload froze — so the field has to be in the payload, not merely on the
    live wire."""
    _, run = _run_with_pm(_PM_NO_STOP_NO_TARGET)
    entry = build_journal_entry_for_run(run, user_id=uuid4())
    payload_verdict = entry.payload["verdict"]
    assert payload_verdict["level_provenance"] == {
        "entry": "pm",
        "stop": "ami_default",
        "target": "ami_default",
    }


def test_a_verdict_with_no_prices_carries_no_provenance():
    """A PASS has nothing to attribute. `None` must read as 'not recorded' —
    the client renders the metric list and no ribbon, and never infers that an
    absent map means everything came from the PM (T-BACKFILL)."""
    verdict, _ = _run_with_pm(
        '{"action": "PASS", "size_pct": null, "entry": null, "stop": null, '
        '"target": null, "horizon_days": null, "narration": "PM: sitting out."}'
    )
    assert verdict.action == VerdictAction.PASS.value
    assert verdict.level_provenance is None


def test_the_scripted_demo_path_attributes_its_levels_to_the_trader():
    """The non-live path lifts all three levels straight off the Trader; there
    is no PM decision on that route to attribute them to."""
    runner = RoomRunner()
    events = _collect(runner.run(
        user_id=uuid4(),
        ticker="AAPL",
        mandate=hydrate_coach_mandate({"plan": "trader", "risk_score": 3}),
        char_delay_min=0.0,
        char_delay_max=0.0,
    ))
    verdict = next(e.verdict for e in events if e.kind == "verdict")
    if verdict.action == VerdictAction.APPROVE.value:
        assert verdict.level_provenance == {
            "entry": "trader",
            "stop": "trader",
            "target": "trader",
        }
    else:  # a mandate veto on the scripted path carries no prices
        assert verdict.level_provenance is None


def test_provenance_values_are_schema_constrained():
    """A typo in a source name would reach the client as an unknown token and
    render as neither stated nor derived. Pydantic refuses it here instead."""
    import pytest
    from pydantic import ValidationError

    from app.schemas.room import Verdict

    with pytest.raises(ValidationError):
        Verdict(
            action=VerdictAction.APPROVE,
            reason="x",
            level_provenance={"entry": "the_pm"},  # type: ignore[dict-item]
        )


def test_agent_id_import_is_live():
    """Vacuity guard for the module's imports — keeps a silent rename honest."""
    assert AgentId.PORTFOLIO_MANAGER.value == "portfolio_manager"
