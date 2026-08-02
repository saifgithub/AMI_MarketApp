"""CR136 M08 — journal integration: enum member, Finding-entry shape, store reads for gating/hysteresis."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.schemas.journal import EntryType, JournalEntryCreate
from app.services.journal_store import get_journal_store
from app.services.portfolio_health_journal import (
    FINDING_TAGS,
    SECTION_KEYS,
    build_finding_entry,
    finding_dedupe_key,
)


def _sections(**overrides) -> dict[str, str]:
    base = {key: f"{key.upper()} content" for key in SECTION_KEYS}
    base.update(overrides)
    return base


def _entry(**overrides) -> JournalEntryCreate:
    kwargs = {
        "user_id": uuid4(),
        "portfolio_id": uuid4(),
        "as_of": date(2026, 8, 2),
        "sections": _sections(),
        "context": {"metrics": [{"metric": "portfolio_volatility", "value": 0.19}]},
        "fired_rules": [{"rule_id": "R1", "slots": {"risk_share": 45.3}, "based_on": []}],
        "rule_states": {"R1": "fired", "R2": "cleared"},
        "engine_version": "cr136.v1",
    }
    kwargs.update(overrides)
    return build_finding_entry(**kwargs)


@pytest.fixture(autouse=True)
def _clean():
    get_journal_store().clear()
    yield
    get_journal_store().clear()


# ── Enum + wire ─────────────────────────────────────────────────────────────


def test_the_entry_type_member_exists_with_the_pinned_wire_value() -> None:
    assert EntryType.PORTFOLIO_HEALTH_ANALYSIS.value == "portfolio_health_analysis"


def test_a_raw_wire_string_coerces_and_an_unknown_one_still_raises() -> None:
    """`JournalStore.append` coerces str → EntryType, which is why the member
    has to exist before any write — and why the guard must stay sharp."""
    assert EntryType("portfolio_health_analysis") is EntryType.PORTFOLIO_HEALTH_ANALYSIS
    with pytest.raises(ValueError):
        EntryType("portfolio_health_analysis_v2")


# ── Entry shape ─────────────────────────────────────────────────────────────


def test_the_entry_shape_is_pinned() -> None:
    portfolio_id = uuid4()
    draft = _entry(portfolio_id=portfolio_id)

    assert draft.entry_type == EntryType.PORTFOLIO_HEALTH_ANALYSIS
    assert draft.title == "Portfolio Health — Finding 2026-08-02"
    assert draft.ticker is None, (
        "the Bull/Bear lookback fetches by ticker — a null keeps Findings out "
        "of single-ticker Room prompts structurally"
    )
    assert draft.agents_involved == []
    assert draft.tags == FINDING_TAGS
    assert draft.outcome is None
    # The seam register pins reference_id = portfolio_id, overriding M08's own
    # doc: M07 reads Findings by portfolio, and a null would make that a scan.
    assert draft.reference_id == portfolio_id
    assert draft.dedupe_key == f"{portfolio_id}:2026-08-02"
    assert set(draft.payload) == {
        "engine_version", "portfolio_id", "as_of", "sections", "context",
        "rules_fired", "rule_states", "llm_used", "llm_rejected_reason",
    }
    assert set(draft.payload["sections"]) == set(SECTION_KEYS)


def test_an_iso_string_as_of_is_accepted_as_well_as_a_date() -> None:
    """M06 carries `as_of` as an ISO string end to end; the doc typed it as a
    `date`. Both produce the same stored value rather than one silently
    rendering `datetime.date(2026, 8, 2)` into a title."""
    assert _entry(as_of="2026-08-02").title == _entry(as_of=date(2026, 8, 2)).title
    assert _entry(as_of="2026-08-02").payload["as_of"] == "2026-08-02"


# ── Validation: degrade loudly ──────────────────────────────────────────────


def test_a_missing_section_raises_rather_than_storing_a_hole() -> None:
    sections = _sections()
    del sections["f3"]
    with pytest.raises(ValueError, match="missing"):
        _entry(sections=sections)


@pytest.mark.parametrize("blank", ["", "   ", "\n"])
def test_an_empty_disclosure_never_reaches_storage(blank: str) -> None:
    """F19: the archived artefact carries its own disclosures forever. A
    Finding stored without them outlives every caveat that was true when it
    was written."""
    with pytest.raises(ValueError, match="empty"):
        _entry(sections=_sections(head=blank))


def test_an_unrecognised_rule_state_raises() -> None:
    """It would read as 'cleared' on the next run — silently dropping a fired
    rule's hysteresis memory, which is the flap the bands exist to stop."""
    with pytest.raises(ValueError, match="rule_states"):
        _entry(rule_states={"R1": "armed"})


# ── Round trip through the real store ───────────────────────────────────────


def test_the_payload_survives_the_jsonb_round_trip() -> None:
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()
    draft = _entry(user_id=user_id, portfolio_id=portfolio_id)
    store.append(draft)

    entries, _total, _retention = store.list_for_user(
        user_id, entry_type=EntryType.PORTFOLIO_HEALTH_ANALYSIS,
    )
    assert len(entries) == 1
    stored = entries[0]
    assert stored.payload == draft.payload
    assert stored.payload["sections"]["head"] == draft.payload["sections"]["head"]
    assert stored.payload["rule_states"] == {"R1": "fired", "R2": "cleared"}


def test_the_dedupe_key_is_spelled_in_exactly_one_place() -> None:
    portfolio_id = uuid4()
    assert finding_dedupe_key(portfolio_id, "2026-08-02") == f"{portfolio_id}:2026-08-02"
    assert _entry(portfolio_id=portfolio_id).dedupe_key == finding_dedupe_key(
        portfolio_id, "2026-08-02",
    )


def test_a_second_finding_for_the_same_day_loses_to_the_first() -> None:
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()
    first, created_first = store.append_unique(
        _entry(user_id=user_id, portfolio_id=portfolio_id),
    )
    second, created_second = store.append_unique(
        _entry(user_id=user_id, portfolio_id=portfolio_id),
    )
    assert created_first is True and created_second is False
    assert second.id == first.id


# ── The two reads M07 depends on ────────────────────────────────────────────


def test_latest_entry_is_scoped_to_the_portfolio_and_ignores_retention() -> None:
    """No plan filter and no 30-day window: a Floor Pass user idle for a month
    must not have their rule hysteresis silently reset to cleared because the
    entry holding it aged out of their own view."""
    store = get_journal_store()
    user_id = uuid4()
    mine, theirs = uuid4(), uuid4()

    store.append(_entry(user_id=user_id, portfolio_id=theirs, as_of="2026-08-01"))
    assert store.latest_portfolio_health_entry(user_id, mine) is None

    old = store.append(_entry(user_id=user_id, portfolio_id=mine, as_of="2026-06-01"))
    store._backdate_for_test(
        user_id, old.id, datetime.now(timezone.utc) - timedelta(days=31),
    )
    found = store.latest_portfolio_health_entry(user_id, mine)
    assert found is not None and found.id == old.id


def test_the_stats_read_counts_soft_deleted_rows() -> None:
    """Delete-to-reset-trial must not work: the counter is the row, and the row
    survives the delete."""
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()
    now = datetime.now(timezone.utc)

    assert store.portfolio_health_stats(user_id, portfolio_id, now=now) == (0, None, 0)

    first = store.append(_entry(user_id=user_id, portfolio_id=portfolio_id,
                                as_of="2026-08-01"))
    store.append(_entry(user_id=user_id, portfolio_id=portfolio_id, as_of="2026-08-02"))
    store._backdate_for_test(user_id, first.id, now - timedelta(days=5))
    store.soft_delete(user_id, first.id)

    used, first_at, daily = store.portfolio_health_stats(
        user_id, portfolio_id, now=now,
    )
    assert used == 2, "the soft-deleted row still counts against the trial budget"
    assert first_at is not None
    assert abs((first_at - (now - timedelta(days=5))).total_seconds()) < 2
    assert daily == 1, "only the row created today counts against the daily cap"


def test_the_hysteresis_state_survives_a_delete() -> None:
    store = get_journal_store()
    user_id, portfolio_id = uuid4(), uuid4()
    entry = store.append(_entry(user_id=user_id, portfolio_id=portfolio_id))
    store.soft_delete(user_id, entry.id)

    found = store.latest_portfolio_health_entry(user_id, portfolio_id)
    assert found is not None, "a deleted Finding is still something that happened"
    assert found.deleted_at is not None, (
        "...and the caller must be able to tell, so a deleted entry is never "
        "replayed to the client as a live one"
    )
    assert found.payload["rule_states"] == {"R1": "fired", "R2": "cleared"}
