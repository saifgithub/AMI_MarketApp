"""CR220 guards — the onboarding-set settings are user-changeable, and the
entitlement boundary that says which ones are NOT stays where DEF179 put it.

Three things are pinned here:

1. **The boundary.** Every field CR220 makes editable must be absent from
   `CLIENT_UNWRITABLE_MANDATE_FIELDS`, and every entitlement field must still
   be in it. This is the "settings set by payment status are not a user
   self-change" line from the CR's own brief, asserted rather than assumed.

2. **The journal describes the change.** A PATCH to a newly-editable field has
   to produce a diff line naming that field. Falling through to the bare
   "Mandate updated." is the DEF197 shape — a real change the history cannot
   describe — and it is what every one of these fields did before CR220.

3. **The ticker lists degrade loudly.** `safety_floor.py` enforces both lists,
   so an unresolvable symbol is a safety control that silently does nothing
   (the CR040 class), and an EMPTY allowlist means "nothing is tradable" while
   `None` means "no allowlist" — the two must never collapse together.
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from datetime import datetime, timezone

from app.api.mandate import router as mandate_router
from app.db import get_session
from app.db.models import TickerReferenceRow
from app.schemas.mandate import CLIENT_UNWRITABLE_MANDATE_FIELDS
from app.services.auth_service import AuthService
from app.services.journal_store import get_journal_store
from app.schemas.journal import EntryType

# The fields CR220 makes user-editable in Settings.
CR220_EDITABLE_FIELDS = (
    "primary_goal",
    "horizon",
    "path",
    "display_name",
    "timezone",
    "learning_style",
    "risk_quotes",
)

# The entitlement/derived fields that must stay server-owned.
ENTITLEMENT_FIELDS = (
    "plan",
    "credit_balance",
    "credit_allowance",
    "trial_expires_at",
    "trial_started_at",
)


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(mandate_router)
    return TestClient(app, raise_server_exceptions=False)


def _new_user():
    auth = AuthService()
    user, token, _ = auth.ensure_anonymous(device_user_id=None)
    return user.id, {"Authorization": f"Bearer {token}"}


@pytest.fixture
def known_ticker() -> str:
    """The unit fixture's `ticker_reference` table is EMPTY, so a "reject the
    unknown symbol" test would pass even if validation were deleted — every
    symbol is unknown. Seeding one real row is what makes the refusal tests
    mean something and lets the accept path be tested at all."""
    with get_session() as s:
        # Idempotent: the sqlite fixture persists across tests in a session, so
        # a bare add() collides on the primary key for the second consumer.
        if s.get(TickerReferenceRow, "AAPL") is None:
            s.add(TickerReferenceRow(
                symbol="AAPL", company_name="Apple Inc.", exchange="NASDAQ",
                is_etf=False, is_active=True, last_seen_at=datetime.now(timezone.utc),
            ))
    from app.services.ticker_reference import _invalidate_active_symbol_cache
    _invalidate_active_symbol_cache()
    return "AAPL"


def _latest_mandate_summary(user_id) -> str:
    entries, _, _ = get_journal_store().list_for_user(
        user_id, entry_type=EntryType.MANDATE_EDIT, limit=1
    )
    assert entries, "the PATCH wrote no mandate_edit journal entry at all"
    return entries[0].summary or ""


# ── 1. The boundary ─────────────────────────────────────────────────────────


def test_cr220_editable_fields_are_not_in_the_unwritable_set():
    """If a future change adds one of these to the unwritable set, the Settings
    control silently becomes a no-op — a PATCH that 200s and drops the value,
    which is exactly the DEF195 failure the user cannot see."""
    overlap = set(CR220_EDITABLE_FIELDS) & CLIENT_UNWRITABLE_MANDATE_FIELDS
    assert not overlap, (
        f"{sorted(overlap)} are editable in Settings but stripped by the store — "
        f"the control would silently do nothing"
    )


def test_cr220_entitlement_fields_stay_unwritable():
    """The other half of the same boundary: payment-derived state is never a
    user self-change (DEF179). CR220 reuses this set rather than inventing a
    second one, so it must not erode."""
    for field in ENTITLEMENT_FIELDS:
        assert field in CLIENT_UNWRITABLE_MANDATE_FIELDS, (
            f"{field} left the unwritable set — that is a paywall bypass"
        )


# ── 2. The journal describes the change ─────────────────────────────────────


@pytest.mark.parametrize(
    ("field", "value", "expected_fragment"),
    [
        ("primary_goal", "income_now", "primary goal"),
        ("horizon", "short", "horizon"),
        ("path", "both", "path"),
        ("learning_style", "story", "learning style"),
        ("display_name", "Ada", "display name"),
        ("timezone", "Asia/Riyadh", "timezone"),
    ],
)
def test_cr220_patch_is_described_in_the_journal(
    client: TestClient, field: str, value: str, expected_fragment: str
):
    """Each newly-editable field must name itself in the mandate history.
    Before CR220 every one of these produced the bare "Mandate updated."."""
    user_id, headers = _new_user()
    resp = client.patch(f"/v1/mandate/{user_id}", json={field: value}, headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()[field] == value

    summary = _latest_mandate_summary(user_id)
    assert summary != "Mandate updated.", (
        f"a {field} change fell through to the generic summary (DEF197 shape)"
    )
    assert expected_fragment in summary.lower(), (
        f"journal summary {summary!r} does not name {field}"
    )


def test_cr220_enum_values_are_humanised_not_raw(client: TestClient):
    """`long_term_wealth` in a history entry a user reads is a leaked
    identifier, not plain English."""
    user_id, headers = _new_user()
    # Move OFF the default first: a PATCH to the value already held is not a
    # change, so it produces no diff line and would make this vacuous.
    client.patch(f"/v1/mandate/{user_id}", json={"primary_goal": "income_now"}, headers=headers)
    client.patch(
        f"/v1/mandate/{user_id}", json={"primary_goal": "long_term_wealth"}, headers=headers
    )
    summary = _latest_mandate_summary(user_id)
    assert "long_term_wealth" not in summary
    assert "Long Term Wealth" in summary


# ── 3. The ticker lists degrade loudly ──────────────────────────────────────


def test_cr220_unknown_ticker_is_refused(client: TestClient):
    """A symbol the universe cannot resolve must not be storable: it would sit
    in an ENFORCED list matching nothing, which is a safety control that
    silently does nothing (CR040)."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": ["NOTAREALTICKER"]}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "NOTAREALTICKER" in resp.text


def test_cr220_empty_allowlist_is_refused(client: TestClient):
    """`None` means "no allowlist"; `[]` would mean "nothing is tradable".
    A user clearing the last row of the editor means the former every time, so
    the ambiguous value is refused rather than guessed at."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_allowlist": []}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "nothing tradable" in resp.text.lower() or "empty allowlist" in resp.text.lower()


def test_cr220_duplicate_tickers_are_collapsed(client: TestClient, known_ticker: str):
    """The same symbol twice is not an error the user needs to fix. Without a
    dedupe it also costs an extra DB lookup each and repeats itself in the
    error text ("unknown: AAPL, AAPL, AAPL")."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": [known_ticker, known_ticker.lower(), known_ticker]}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["compliance"]["ticker_blocklist"] == [known_ticker]


def test_cr220_an_absurdly_long_ticker_list_is_refused(client: TestClient):
    """Each entry costs a point lookup, so an unbounded list is an unbounded
    loop on every PATCH."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": ["AAPL"] * 201}},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "at most" in resp.text


def test_cr220_clearing_an_allowlist_with_null_is_allowed(client: TestClient):
    """The legitimate way to remove an allowlist must still work, or the
    refusal above becomes a trap with no way out."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_allowlist": None}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["compliance"]["ticker_allowlist"] is None


def test_cr220_a_known_ticker_is_accepted(client: TestClient, known_ticker: str):
    """The accept path. Without this the refusal tests above are vacuous — an
    empty reference table rejects everything, so they would pass against a
    validator that simply refused all input."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": [known_ticker]}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["compliance"]["ticker_blocklist"] == [known_ticker]


def test_cr220_ticker_casing_is_normalised(client: TestClient, known_ticker: str):
    """A lowercase entry must not sit in an ENFORCED list failing to match:
    `safety_floor` compares against stored symbols directly."""
    user_id, headers = _new_user()
    resp = client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": [known_ticker.lower()]}},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["compliance"]["ticker_blocklist"] == [known_ticker]


def test_cr220_ticker_list_change_is_described_in_the_journal(
    client: TestClient, known_ticker: str
):
    """The lists are lists, not bools — the generic compliance loop would
    render "compliance.ticker_blocklist: [] -> ['AAPL']"."""
    user_id, headers = _new_user()
    client.patch(
        f"/v1/mandate/{user_id}",
        json={"compliance": {"ticker_blocklist": [known_ticker]}},
        headers=headers,
    )
    summary = _latest_mandate_summary(user_id)
    assert "blocked tickers" in summary.lower(), summary
    assert "ticker_blocklist" not in summary


# ── 4. The backfill (D10) ───────────────────────────────────────────────────


def _mandate_with(**compliance_overrides):
    """A minimal valid Mandate carrying the given compliance flags."""
    from datetime import datetime, timezone as _tz
    from uuid import uuid4

    from app.schemas.mandate import Mandate

    now = datetime.now(_tz.utc)
    return Mandate.model_validate({
        "user_id": str(uuid4()),
        "version": 1,
        "display_name": "Trader",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": "long_horizon",
        "risk_score": 3,
        "risk_components": {
            "drawdown_response": 3,
            "regret_asymmetry": 0,
            "concentration_tolerance": 3,
        },
        "max_drawdown_pct": 30,
        "compliance": compliance_overrides,
        "created_at": now,
        "updated_at": now,
    })


def test_cr220_backfill_selects_the_inverted_pair():
    """The population the backfill exists for: the old parser's output."""
    from scripts.cr220_backfill_compliance_defaults import flags_to_repair

    mandate = _mandate_with(long_only=False, liquid_only=False)
    assert sorted(flags_to_repair(mandate)) == ["liquid_only", "long_only"]


def test_cr220_backfill_skips_an_already_correct_mandate():
    """Idempotence: a second run must find nothing, or every re-run writes
    another version bump and another journal entry for no change."""
    from scripts.cr220_backfill_compliance_defaults import flags_to_repair

    assert flags_to_repair(_mandate_with(long_only=True, liquid_only=True)) == []


def test_cr220_backfill_ignores_the_opt_in_flags():
    """`halal`, `esg_lite` and the two NEVER flags default False legitimately.
    Repairing those would invent restrictions the user never asked for — the
    mirror image of the defect."""
    from scripts.cr220_backfill_compliance_defaults import flags_to_repair

    mandate = _mandate_with(
        long_only=True, liquid_only=True,
        halal=False, esg_lite=False,
        no_fossil_fuels=False, no_tobacco_alcohol_gambling=False,
    )
    assert flags_to_repair(mandate) == []


def test_cr220_backfill_disclosure_names_the_flag_and_the_remedy():
    """CR040: this tightens a live safety control, so the user must be able to
    find out what changed and how to undo it."""
    from scripts.cr220_backfill_compliance_defaults import disclosure_summary

    summary = disclosure_summary(["long_only"])
    assert "long-only" in summary.lower()
    assert "settings" in summary.lower()


# ── 5. Path.BOTH is a real value, not a synonym for LONG_HORIZON (D11) ──────


_PATH_BRANCH_AGENTS = ("market_analyst", "news_analyst", "social_media_analyst")


def _overlay_for_path(path: str, agent_id: str) -> str:
    from app.agents.overlay_generator import generate_overlay

    return generate_overlay(agent_id, _mandate_with_path(path))


def _mandate_with_path(path: str):
    from datetime import datetime, timezone as _tz
    from uuid import uuid4

    from app.schemas.mandate import Mandate

    now = datetime.now(_tz.utc)
    return Mandate.model_validate({
        "user_id": str(uuid4()),
        "version": 1,
        "display_name": "Trader",
        "primary_goal": "long_term_wealth",
        "horizon": "long",
        "path": path,
        "risk_score": 3,
        "risk_components": {
            "drawdown_response": 3,
            "regret_asymmetry": 0,
            "concentration_tolerance": 3,
        },
        "max_drawdown_pct": 30,
        "compliance": {},
        "created_at": now,
        "updated_at": now,
    })


def _instruction_lines(overlay: str) -> set[str]:
    """The behavioural instructions only.

    The overlay also carries a `- Path: <value>` NARRATION line, which differs
    between paths whatever the branches do. Comparing whole overlays therefore
    passes even when every BOTH branch is deleted — the first version of this
    test did exactly that and survived its own mutation. Dropping the narration
    line is what makes the comparison about behaviour."""
    return {
        line for line in overlay.splitlines()
        if line.startswith("- ") and not line.startswith("- Path:")
    }


@pytest.mark.parametrize("agent_id", _PATH_BRANCH_AGENTS)
def test_cr220_path_both_is_not_a_synonym_for_long_horizon(agent_id: str):
    """Before CR220, `Path.BOTH` fell through the `else` of all three branches,
    so a user selecting it silently got the LONG_HORIZON prompt. Exposing a
    value in the Settings picker that means something other than its name is
    the CR040 class, so `BOTH` must instruct differently.

    Mutation-proven: deleting any one `elif m.path == Path.BOTH` branch turns
    the matching parametrisation red."""
    both = _instruction_lines(_overlay_for_path("both", agent_id))
    long_horizon = _instruction_lines(_overlay_for_path("long_horizon", agent_id))
    active = _instruction_lines(_overlay_for_path("active", agent_id))
    assert both != long_horizon, (
        f"{agent_id}: BOTH gives the same instructions as LONG_HORIZON — the "
        f"picker would offer a value that silently means something else"
    )
    assert both != active, f"{agent_id}: BOTH gives the same instructions as ACTIVE"


def test_cr220_path_both_keeps_the_cr147_no_macro_feed_warning():
    """CR147 Tier A.5 softened the LONG_HORIZON news branch because the agent
    has no macro feed — asking it to weigh the cycle invites it to supply one
    from training memory. The BOTH branch asks for structural reads too, so it
    must carry the same warning; dropping it would reopen that surface."""
    overlay = _overlay_for_path("both", "news_analyst")
    assert "FOMC countdown" in overlay
    assert "your framing, not data" in overlay


# ── 6. The backfill actually runs (D10) ─────────────────────────────────────
#
# The helper tests above cover selection and wording. These drive `main()`
# itself, because a backfill that is only ever tested through its helpers is a
# script nobody has run — and this one WRITES to every affected user's mandate.

from uuid import uuid4
from datetime import datetime, timezone

from app.services.mandate_store import MandateStore
from app.schemas.mandate import Mandate
from scripts.cr220_backfill_compliance_defaults import main


def _seed_inverted_user():
    uid = uuid4()
    now = datetime.now(timezone.utc)
    m = Mandate.model_validate({
        "user_id": str(uid), "version": 1, "display_name": "Trader",
        "primary_goal": "long_term_wealth", "horizon": "long", "path": "long_horizon",
        "risk_score": 3,
        "risk_components": {"drawdown_response": 3, "regret_asymmetry": 0,
                            "concentration_tolerance": 3},
        "max_drawdown_pct": 30,
        # the exact shape the old _parse_constraints produced
        "compliance": {"long_only": False, "liquid_only": False},
        "created_at": now, "updated_at": now,
    })
    MandateStore().upsert(uid, m)
    return uid


def test_dry_run_reports_but_writes_nothing(capsys):
    uid = _seed_inverted_user()
    rc = main([])
    assert rc == 0
    out = capsys.readouterr().out
    assert "DRY RUN" in out
    assert str(uid) in out
    after = MandateStore().get(uid)
    assert after.compliance.long_only is False, "dry run must not write"
    assert after.version == 1


def test_apply_repairs_and_bumps_the_version(capsys):
    uid = _seed_inverted_user()
    rc = main(["--apply"])
    assert rc == 0
    after = MandateStore().get(uid)
    assert after.compliance.long_only is True
    assert after.compliance.liquid_only is True
    assert after.version == 2, "the repair must be a real, visible version"


def test_rerunning_after_apply_finds_nothing(capsys):
    _seed_inverted_user()
    main(["--apply"])
    capsys.readouterr()
    main([])
    out = capsys.readouterr().out
    assert "affected users     : 0" in out, out
