"""CR276 (CR267 WP-30) — account closure, restore, post-grace erasure and export.

Acceptance, each pinned here against the sqlite fixture:
  - a deleted account cannot sign in after the grace period and its personal
    data is gone (delete) or scrubbed (anonymise);
  - restore works inside the grace period, and only when explicitly asked for;
  - the export holds trades, rooms, mandate and progress, and nothing of anyone
    else's, and no secret;
  - archive is refused without counsel's approval;
  - revoked sessions fail on their very next use.

Plus the guard that makes the registry a contract: a table that gains a user-id
column must be added to `account_erasure.RULES` (or explained in
`NOT_USER_DATA`), or this file fails.
"""

from __future__ import annotations

import base64
import importlib.util
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import sqlalchemy as sa
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import func, select

from app.api.account import router as account_router
from app.api.auth import router as auth_router
from app.core.config import Settings, settings
from app.db import get_session
from app.db.models import (
    AdminAuditRow,
    AuthChallengeRow,
    Base,
    BugReportRow,
    GameDuelRow,
    GameEntryRow,
    GameFieldRow,
    HTTPAuditRow,
    JournalEntryRow,
    LessonProgressRow,
    LLMAuditRow,
    MandateRow,
    NotificationRow,
    RoomRunRow,
    SimHoldingRow,
    SimPortfolioRow,
    SimTradeRow,
    SimWatchlistRow,
    SubscriptionEventRow,
    User,
    UserDeviceRow,
)
from app.services import account_erasure as ae
from app.services import auth_service
from app.services.auth_service import AuthService
from app.services.oidc_verifier import OIDCVerificationError

_BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION = _BACKEND / "alembic" / "versions" / "cr276a0b0c0d1_users_account_closure.py"


# ── helpers ──────────────────────────────────────────────────────────────────


def _google_jwt(sub: str, email: str | None = None) -> str:
    seg = lambda b: base64.urlsafe_b64encode(b).rstrip(b"=").decode()  # noqa: E731
    payload: dict = {"sub": sub, "email_verified": True}
    if email:
        payload["email"] = email
    return f"{seg(b'{}')}.{seg(json.dumps(payload).encode())}.{seg(b'sig')}"


class _FakeGoogleVerifier:
    def verify(self, identity_token: str) -> dict:
        try:
            _h, body, _s = identity_token.split(".")
            return json.loads(base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)))
        except Exception as e:  # noqa: BLE001
            raise OIDCVerificationError(str(e)) from e


@pytest.fixture
def client(monkeypatch) -> TestClient:
    monkeypatch.setattr(
        auth_service, "_service", AuthService(google_verifier=_FakeGoogleVerifier()),
    )
    a = FastAPI()
    a.include_router(auth_router)
    a.include_router(account_router)
    return TestClient(a)


def _anon(client: TestClient) -> tuple[UUID, dict]:
    r = client.post("/v1/auth/anon", json={"locale": "en", "timezone": "UTC"})
    assert r.status_code == 200, r.text
    body = r.json()
    return UUID(body["user"]["id"]), {"Authorization": f"Bearer {body['token']}"}


def _claim_google(client: TestClient, headers: dict, sub: str, *, email: str | None = None,
                  restore: bool = False):
    return client.post(
        "/v1/auth/google", headers=headers,
        json={"identity_token": _google_jwt(sub, email), "restore_account": restore},
    )


def _claimed_user(client: TestClient, sub: str = "g-sub-1", email: str = "p@example.com"):
    uid, headers = _anon(client)
    r = _claim_google(client, headers, sub, email=email)
    assert r.status_code == 200, r.text
    return uid, {"Authorization": f"Bearer {r.json()['token']}"}


def _seed_everything(uid: UUID) -> dict:
    """One row of personal data in every family of table, for `uid`."""
    now = datetime.now(timezone.utc)
    pid, rid, fid, eid, other_eid = uuid4(), uuid4(), uuid4(), uuid4(), uuid4()
    other = uuid4()
    with get_session() as s:
        s.add(User(id=other, email="other@example.com", is_anonymous=False, handle="other-h"))
        s.add(SimPortfolioRow(id=pid, user_id=uid, starting_capital=10000, current_cash=9000))
        s.flush()
        s.add(SimHoldingRow(portfolio_id=pid, ticker="AAPL", quantity=1, avg_cost=100))
        s.add(SimTradeRow(user_id=uid, portfolio_id=pid, ticker="AAPL", side="buy",
                          quantity=1, entry_price=100))
        s.add(MandateRow(user_id=uid, version=1, snapshot={"risk_score": 3}))
        s.add(JournalEntryRow(user_id=uid, entry_type="note", title="why I bought",
                              user_note="my private note"))
        s.add(LessonProgressRow(user_id=uid, lesson_id="L1"))
        s.add(SimWatchlistRow(user_id=uid, ticker="MSFT", notes="secret thesis"))
        s.add(UserDeviceRow(user_id=uid, device_install_id=uuid4()))
        s.add(NotificationRow(user_id=uid, type="x", title="t", body="b"))
        s.add(RoomRunRow(
            id=rid, user_id=uid, ticker="AAPL", mandate_version=1, model_tier="t",
            transcript=[{"agent": "cio", "text": "holdings: ..."}],
            verdict={"action": "APPROVE"}, cio_context_snapshot={"holdings": ["AAPL"]},
        ))
        s.add(LLMAuditRow(user_id=uid, tier="t", provider="p", system_prompt="SECRET PROMPT",
                          messages=[{"role": "user", "content": "hi"}], response_text="reply",
                          input_tokens=10, output_tokens=5, cost_usd=0.01))
        s.add(HTTPAuditRow(user_id=uid, method="POST", path="/v1/x", status_code=200,
                           latency_ms=3, client_ip="203.0.113.9"))
        s.add(BugReportRow(user_id=uid, category="bug", title="it broke",
                           app_version="1", platform="ios", attachment_path="shot.png"))
        s.add(SubscriptionEventRow(user_id=uid, event_type="plan_change", source="admin",
                                   note="called from 0123"))
        s.add(AuthChallengeRow(kind="magic_link", target="p@example.com", code_hash="h",
                               expires_at=now + timedelta(minutes=5)))
        s.add(GameFieldRow(id=fid, cadence="weekly", entry_opens_at=now, locks_at=now,
                           starts_on=now.date(), ends_on=now.date(),
                           owner_user_id=uid, champion_entry_id=eid))
        s.flush()
        s.add(GameEntryRow(id=eid, field_id=fid, user_id=uid, run_id=uuid4()))
        s.add(GameEntryRow(id=other_eid, field_id=fid, user_id=other, run_id=uuid4()))
        s.add(GameDuelRow(field_id=fid, cadence="weekly", user_a_id=uid, run_a_id=uuid4(),
                          user_b_id=other, run_b_id=uuid4()))
        s.add(LessonProgressRow(user_id=other, lesson_id="L1"))
        s.add(SimWatchlistRow(user_id=other, ticker="NVDA", notes="not yours"))
    return {"other": other, "field": fid, "pid": pid}


def _count(model, **where) -> int:
    with get_session() as s:
        q = select(func.count()).select_from(model)
        for k, v in where.items():
            q = q.where(getattr(model, k) == v)
        return s.execute(q).scalar_one()


def _age_closure(uid: UUID, days: int) -> None:
    with get_session() as s:
        s.get(User, uid).closure_requested_at = datetime.now(timezone.utc) - timedelta(days=days)


@pytest.fixture(autouse=True)
def _no_network_externals(monkeypatch):
    """Processors are asked via httpx in production; the suite never does."""
    monkeypatch.setattr(ae, "erase_external", lambda uid: {"onesignal": "ok", "revenuecat": "ok"})


# ── the registry is a contract ───────────────────────────────────────────────


def test_every_table_with_a_user_column_is_in_the_registry_or_explained():
    covered = set(ae.rules_by_table()) | set(ae.NOT_USER_DATA)
    missing = []
    for table in Base.metadata.sorted_tables:
        cols = {c.name for c in table.columns}
        if (cols & ae.USER_ID_COLUMN_NAMES) and table.name not in covered:
            missing.append(table.name)
    assert not missing, (
        f"tables with a user-id column and no deletion rule: {missing}. Add a "
        "TableRule to account_erasure.RULES (what do delete and anonymise do to it, "
        "and why) or explain it in NOT_USER_DATA."
    )


def test_every_rule_names_real_columns_and_scrubs_real_columns():
    for rule in ae.RULES:
        cols = {c.name for c in rule.model.__table__.columns}
        assert set(rule.columns) <= cols, rule.table
        assert set(rule.scrub) <= cols, rule.table
        if rule.delete in (ae.Act.SCRUB, ae.Act.SCRUB_DETACH) or rule.anonymise in (
            ae.Act.SCRUB, ae.Act.SCRUB_DETACH,
        ):
            assert rule.scrub, f"{rule.table}: a scrub rule with nothing to scrub"


# ── close + revoke ───────────────────────────────────────────────────────────


def test_close_requires_explicit_confirm(client):
    _uid, h = _anon(client)
    assert client.post("/v1/account/close", headers=h, json={}).status_code == 400
    assert client.get("/v1/auth/me", headers=h).status_code == 200


def test_close_revokes_every_session_immediately(client):
    uid, h1 = _claimed_user(client)
    # a second session for the same user (another device)
    r = client.post("/v1/auth/anon", headers=h1,
                    json={"device_user_id": str(uid), "locale": "en", "timezone": "UTC"})
    h2 = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/v1/auth/me", headers=h2).status_code == 200

    r = client.post("/v1/account/close", headers=h1, json={"confirm": True})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["closed"] is True and body["mode"] == "delete"
    assert body["grace_days"] == 30

    for h in (h1, h2):
        assert client.get("/v1/auth/me", headers=h).status_code == 401
        assert client.get("/v1/account/export", headers=h).status_code == 401
    with get_session() as s:
        assert s.get(User, uid).closure_requested_at is not None


def test_close_is_idempotent_and_keeps_the_first_timestamp(client):
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    first = _count(User, id=uid)
    with get_session() as s:
        ts = s.get(User, uid).closure_requested_at
        version = s.get(User, uid).token_version
    again = ae.request_closure(uid)
    assert again.already_closed is True and first == 1
    with get_session() as s:
        row = s.get(User, uid)
        assert row.closure_requested_at == ts and row.token_version == version


def test_a_closed_anonymous_device_gets_a_fresh_account_not_the_old_one(client):
    uid, h = _anon(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    r = client.post("/v1/auth/anon", headers=h,
                    json={"device_user_id": str(uid), "locale": "en", "timezone": "UTC"})
    assert r.status_code == 200
    assert r.json()["is_new"] is True and r.json()["user"]["id"] != str(uid)


def test_policy_says_delete_in_beta():
    app = FastAPI()
    app.include_router(account_router)
    p = TestClient(app).get("/v1/account/policy").json()
    assert p == {"mode": "delete", "wording": "delete", "grace_days": 30,
                 "export_available": True}


# ── restore ──────────────────────────────────────────────────────────────────


def test_signing_in_inside_grace_offers_restore_and_changes_nothing(client):
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com")
    assert r.status_code == 409
    d = r.json()["detail"]
    assert d["code"] == "account_pending_deletion" and d["restorable_until"]
    with get_session() as s:
        assert s.get(User, uid).closure_requested_at is not None


def test_restore_inside_grace_brings_the_account_and_its_data_back(client):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com", restore=True)
    assert r.status_code == 200, r.text
    assert r.json()["user"]["id"] == str(uid)
    fresh = {"Authorization": f"Bearer {r.json()['token']}"}
    assert client.get("/v1/auth/me", headers=fresh).status_code == 200
    assert _count(JournalEntryRow, user_id=uid) == 1
    assert client.get("/v1/auth/me", headers=h).status_code == 401  # the old token stays dead


def test_magic_link_to_a_closed_email_is_held_for_restore(client):
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _new, anon_h = _anon(client)
    start = client.post("/v1/auth/magic_link/start", headers=anon_h,
                        json={"email": "p@example.com"})
    code = start.json()["debug_code"]
    r = client.post("/v1/auth/magic_link/verify", headers=anon_h,
                    json={"email": "p@example.com", "code": code})
    assert r.status_code == 409 and r.json()["detail"]["code"] == "account_pending_deletion"
    r = client.post("/v1/auth/magic_link/verify", headers=anon_h,
                    json={"email": "p@example.com", "code": code, "restore_account": True})
    assert r.status_code == 200 and r.json()["user"]["id"] == str(uid)


def test_past_grace_the_account_cannot_be_restored_or_signed_into(client):
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)  # grace over, job has not run yet
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com", restore=True)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_closed"


# ── post-grace erasure ───────────────────────────────────────────────────────


def test_tick_leaves_an_account_alone_until_grace_ends(client):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 29)
    stats = ae.run_erasure_tick()
    assert stats["due"] == 0 and _count(User, id=uid) == 1
    assert _count(JournalEntryRow, user_id=uid) == 1


def test_delete_mode_removes_the_person_and_cannot_sign_in(client):
    uid, h = _claimed_user(client)
    seeded = _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)

    stats = ae.run_erasure_tick()
    assert stats["erased"] == 1

    assert _count(User, id=uid) == 0
    for model in (JournalEntryRow, MandateRow, SimTradeRow, SimPortfolioRow, RoomRunRow,
                  SimWatchlistRow, UserDeviceRow, NotificationRow, HTTPAuditRow,
                  BugReportRow, LessonProgressRow, GameEntryRow):
        assert _count(model, user_id=uid) == 0, model.__tablename__
    with get_session() as s:
        assert s.execute(select(func.count()).select_from(SimHoldingRow)).scalar_one() == 0
        assert s.execute(select(func.count()).select_from(GameDuelRow)).scalar_one() == 0
        assert s.execute(select(func.count()).select_from(AuthChallengeRow)).scalar_one() == 0
        field = s.get(GameFieldRow, seeded["field"])
        assert field.owner_user_id is None and field.champion_entry_id is None
        # LLM audit: the row stays for cost accounting, the content and the id are gone.
        llm = s.execute(select(LLMAuditRow)).scalar_one()
        assert llm.user_id is None and llm.system_prompt == "" and llm.messages == []
        assert llm.response_text is None and llm.input_tokens == 10
        # Billing ledger: kept (accounting), free-text note blanked.
        sub = s.execute(select(SubscriptionEventRow)).scalar_one()
        assert sub.note is None and sub.user_id == uid
        audit = s.execute(
            select(AdminAuditRow).where(AdminAuditRow.action == "account_erased_delete")
        ).scalar_one()
        assert audit.target == str(uid)
        # Someone else's data is untouched.
        other = seeded["other"]
        assert s.get(User, other).email == "other@example.com"
        assert _count(LessonProgressRow, user_id=other) == 1
        assert _count(SimWatchlistRow, user_id=other) == 1
        assert _count(GameEntryRow, user_id=other) == 1

    # Same Google identity afterwards: a brand-new account, nothing carried over.
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com")
    assert r.status_code == 200 and r.json()["user"]["id"] != str(uid)
    assert client.get("/v1/auth/me", headers=h).status_code == 401


def test_anonymise_mode_keeps_a_scrubbed_tombstone(client, monkeypatch):
    monkeypatch.setattr(settings, "account_erasure_mode", "anonymise")
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    assert ae.run_erasure_tick()["erased"] == 1

    with get_session() as s:
        u = s.get(User, uid)
        assert u is not None and u.erased_at is not None and u.erased_mode == "anonymise"
        for col in ("email", "apple_id", "google_id", "display_name", "handle",
                    "device_user_id", "device_model", "phone", "alpaca_linked_at"):
            assert getattr(u, col) is None, col
        # Free text / device data: gone.
        assert _count(JournalEntryRow, user_id=uid) == 0
        assert _count(MandateRow, user_id=uid) == 0
        assert _count(UserDeviceRow, user_id=uid) == 0
        assert _count(HTTPAuditRow, user_id=uid) == 0
        # De-identified simulated activity: kept.
        assert _count(SimTradeRow, user_id=uid) == 1
        assert _count(LessonProgressRow, user_id=uid) == 1
        run = s.execute(select(RoomRunRow).where(RoomRunRow.user_id == uid)).scalar_one()
        assert run.transcript == [] and run.cio_context_snapshot is None
        assert run.verdict == {"action": "APPROVE"}
    # Provider id is gone from the row, so the same identity starts fresh.
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com")
    assert r.status_code == 200 and r.json()["user"]["id"] != str(uid)


def test_erasure_is_idempotent(client):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    assert ae.erase_account(uid).outcome == "erased"
    assert ae.erase_account(uid).outcome == "absent"
    assert ae.run_erasure_tick()["due"] == 0


def test_anonymise_twice_does_not_redo_or_fail(client, monkeypatch):
    monkeypatch.setattr(settings, "account_erasure_mode", "anonymise")
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    assert ae.erase_account(uid).outcome == "erased"
    assert ae.erase_account(uid).outcome == "already_erased"


def test_an_account_restored_or_re_closed_after_queueing_is_not_erased(client):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    # queued by the tick, then the user restores and closes again a moment later
    with get_session() as s:
        s.get(User, uid).closure_requested_at = datetime.now(timezone.utc)
    assert ae.erase_account(uid).outcome == "not_due"
    with get_session() as s:
        s.get(User, uid).closure_requested_at = None
    with pytest.raises(ValueError):
        ae.erase_account(uid)
    assert _count(User, id=uid) == 1 and _count(JournalEntryRow, user_id=uid) == 1


def test_never_closed_accounts_are_never_erased(client):
    uid, _h = _claimed_user(client)
    with pytest.raises(ValueError):
        ae.erase_account(uid)
    assert _count(User, id=uid) == 1


def test_a_processor_outage_defers_and_the_next_tick_finishes(client, monkeypatch):
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)

    def boom(_uid):
        raise ae.ExternalErasureFailed("onesignal: HTTP 503")

    monkeypatch.setattr(ae, "erase_external", boom)
    assert ae.run_erasure_tick()["deferred"] == 1
    assert _count(User, id=uid) == 1  # still closed, still there, will retry
    monkeypatch.setattr(ae, "erase_external", lambda u: {"onesignal": "ok", "revenuecat": "ok"})
    assert ae.run_erasure_tick()["erased"] == 1
    assert _count(User, id=uid) == 0


def test_one_failing_account_does_not_stop_the_batch(client, monkeypatch):
    a, ha = _claimed_user(client, "g-a", "a@example.com")
    b, hb = _claimed_user(client, "g-b", "b@example.com")
    for h in (ha, hb):
        client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(a, 31)
    _age_closure(b, 32)
    real = ae.erase_account

    def flaky(uid, mode=None):
        if uid == b:
            raise RuntimeError("db hiccup")
        return real(uid, mode)

    monkeypatch.setattr(ae, "erase_account", flaky)
    stats = ae.run_erasure_tick()
    assert stats["failed"] == 1 and stats["erased"] == 1
    assert _count(User, id=a) == 0 and _count(User, id=b) == 1


def test_bug_report_screenshots_are_removed_from_disk(client, monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "bug_attachments_dir", str(tmp_path))
    shot = tmp_path / "shot.png"
    shot.write_bytes(b"png")
    outside = tmp_path.parent / "keep.txt"
    outside.write_text("not ours")
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    with get_session() as s:
        s.add(BugReportRow(user_id=uid, category="bug", title="t", app_version="1",
                           platform="ios", attachment_path="../keep.txt"))
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    assert ae.run_erasure_tick()["erased"] == 1
    assert not shot.exists()
    assert outside.exists(), "a traversing attachment path must never delete outside the dir"


# ── archive ──────────────────────────────────────────────────────────────────


def test_archive_is_refused_without_counsel_approval(client, monkeypatch):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    monkeypatch.setattr(settings, "account_erasure_mode", "archive")
    monkeypatch.setattr(settings, "account_archive_counsel_approved", False)

    with pytest.raises(ae.ArchiveNotApproved):
        ae.erase_account(uid, "archive")
    stats = ae.run_erasure_tick()
    assert stats["refused"] == 1 and stats["erased"] == 0
    assert _count(User, id=uid) == 1 and _count(JournalEntryRow, user_id=uid) == 1
    with get_session() as s:
        assert s.get(User, uid).erased_at is None


def test_archive_refusal_is_logged_at_error_level(client, monkeypatch):
    seen = []
    monkeypatch.setattr(ae.logger, "error", lambda event, **kw: seen.append(event))
    monkeypatch.setattr(settings, "account_archive_counsel_approved", False)
    with pytest.raises(ae.ArchiveNotApproved):
        ae.erase_account(uuid4(), "archive")
    assert "account_erasure_archive_refused" in seen


def test_settings_refuse_to_boot_in_archive_without_approval():
    with pytest.raises(ValueError, match="counsel"):
        Settings(account_erasure_mode="archive", account_archive_counsel_approved=False)
    Settings(account_erasure_mode="archive", account_archive_counsel_approved=True)
    with pytest.raises(ValueError):
        Settings(account_erasure_mode="bury")


def test_archive_with_approval_keeps_everything_and_blocks_sign_in(client, monkeypatch):
    monkeypatch.setattr(settings, "account_erasure_mode", "archive")
    monkeypatch.setattr(settings, "account_archive_counsel_approved", True)
    assert ae.policy()["wording"] == "close"
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    _age_closure(uid, 31)
    assert ae.run_erasure_tick()["erased"] == 1
    assert _count(JournalEntryRow, user_id=uid) == 1
    with get_session() as s:
        u = s.get(User, uid)
        assert u.erased_mode == "archive" and u.email == "p@example.com"
    _new, anon_h = _anon(client)
    r = _claim_google(client, anon_h, "g-sub-1", email="p@example.com", restore=True)
    assert r.status_code == 403 and r.json()["detail"]["code"] == "account_closed"


# ── closed accounts get no push ──────────────────────────────────────────────


def test_a_closed_account_is_not_pushed_to(client, monkeypatch):
    from app.services import notification_service as ns

    called = []
    monkeypatch.setattr(ns, "_attempt_push", lambda **kw: called.append(kw) or ("sent", None))
    uid, h = _claimed_user(client)
    client.post("/v1/account/close", headers=h, json={"confirm": True})
    r = ns.notify(uid, "daily_reminder", "t", "b", {})
    assert r.push_status == "skipped" and r.push_detail == "account_closed"
    assert called == []


# ── export ───────────────────────────────────────────────────────────────────


def test_export_holds_trades_rooms_mandate_progress_and_only_mine(client):
    uid, h = _claimed_user(client)
    seeded = _seed_everything(uid)
    r = client.get("/v1/account/export", headers=h)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert "attachment" in r.headers["content-disposition"]
    assert r.headers["cache-control"] == "no-store"
    doc = r.json()

    assert doc["schema_version"] == 1 and doc["profile"]["id"] == str(uid)
    assert len(doc["sim_trades"]) == 1 and doc["sim_trades"][0]["ticker"] == "AAPL"
    assert doc["rooms"][0]["verdict"] == {"action": "APPROVE"}
    assert "transcript" not in doc["rooms"][0]
    assert "cio_context_snapshot" not in doc["rooms"][0]
    assert doc["mandates"][0]["snapshot"] == {"risk_score": 3}
    assert doc["journal"][0]["user_note"] == "my private note"
    assert [p["lesson_id"] for p in doc["lesson_progress"]] == ["L1"]
    assert doc["settings"]["locale"] == "en"
    assert doc["sim_holdings"][0]["ticker"] == "AAPL"
    assert doc["not_included"]

    text = r.text
    assert str(seeded["other"]) not in text
    assert "not yours" not in text and "other@example.com" not in text
    assert "SECRET PROMPT" not in text and "203.0.113.9" not in text


def test_export_never_carries_a_secret_field(client):
    uid, h = _claimed_user(client)
    _seed_everything(uid)
    text = client.get("/v1/account/export", headers=h).text.lower()
    for needle in ("secret_key", "api_key", "alpaca_key", "alpaca_secret", "token_version",
                   "code_hash", "password"):
        assert needle not in text, needle


def test_export_requires_auth_and_is_rate_limited(client):
    assert client.get("/v1/account/export").status_code == 401
    _uid, h = _claimed_user(client)
    codes = [client.get("/v1/account/export", headers=h).status_code for _ in range(6)]
    assert codes[:5] == [200] * 5 and codes[5] == 429


# ── migration ────────────────────────────────────────────────────────────────


def test_migration_upgrades_and_downgrades_on_sqlite(tmp_path):
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    spec = importlib.util.spec_from_file_location("cr276_mig", _MIGRATION)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'mig.db'}")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE users (id VARCHAR PRIMARY KEY, email VARCHAR)"))
        ops = Operations(MigrationContext.configure(conn))
        with Operations.context(ops.migration_context):
            mod.upgrade()
        cols = {c["name"]: c for c in sa.inspect(conn).get_columns("users")}
        for name in ("closure_requested_at", "erased_at", "erased_mode"):
            assert name in cols and cols[name]["nullable"] is True
        with Operations.context(ops.migration_context):
            mod.downgrade()
        left = {c["name"] for c in sa.inspect(conn).get_columns("users")}
        assert not left & {"closure_requested_at", "erased_at", "erased_mode"}


def test_single_alembic_head_and_this_migration_is_in_its_chain():
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    cfg = Config(str(_BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND / "alembic"))
    script = ScriptDirectory.from_config(cfg)
    heads = script.get_heads()
    assert len(heads) == 1, heads
    chain = {r.revision for r in script.walk_revisions(base="base", head=heads[0])}
    assert "cr276a0b0c0d1" in chain
