"""Shared pytest fixtures.

The `_isolated_db` autouse fixture gives every test a fresh sqlite database
(file under /tmp, wiped between tests). It also clears all the in-memory
store/service singletons so a store doesn't accidentally carry rows or
caches across test cases. Tests that exercise persistence get clean tables;
tests that don't touch persistence pay almost no cost.

ISS002/CR208 also hooks in here: every JSON response any test's `TestClient`
receives is recorded to `backend/tests/_wire_capture.jsonl` and compared, after
the run, against the keys the Flutter client actually reads
(`backend/scripts/wire_contract/`). Starlette funnels every verb through
`TestClient.request`, so one patch catches all ~92 test files that use it with
zero changes to any of them — which is the point: the check must not need a
human to declare anything per-surface, because per-surface declaration is the
mechanism that already failed three times (DEF357, DEF363, DEF365).
"""

import atexit
import json
import os
import shutil
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path as _Path
from uuid import uuid4

import pytest

from app.schemas import (
    AgentId,
    Compliance,
    Horizon,
    LearningStyle,
    Mandate,
    Path,
    Plan,
    PrimaryGoal,
    RiskComponents,
)
from app.schemas.trade import OrderType, ProposedTrade, Side

# CR128: tickers the existing test suite already posts through the three
# now-guarded routes (Room convene, trade preview/submit, watchlist add).
# Seeded into every fresh test DB so pre-existing tests keep passing without
# each one needing its own `ticker_reference` setup. CR128's own tests cover
# the not-found/suggestion behavior explicitly against this same seeded set
# (or an unseeded DB). Two groups:
#   - Real tickers (also convene_sheet.dart's own hardcoded suggestion chips,
#     plus XOM/GOOG used by the Sharia/classification "PASS on a real name"
#     fixtures).
#   - Synthetic fixture tickers (JPMX, NEVR) that pre-date CR128 — the Sharia/
#     classification wire-format tests (DEF094/DEF112) use these specifically
#     BECAUSE they're outside those universes (SCREENED_OUT / UNKNOWN verdict
#     paths), a concern orthogonal to CR128's existence check. Seeding them
#     here only affects test-only data, never production.
_COMMON_TEST_TICKERS = {
    "AAPL": ("Apple Inc.", "NASDAQ"),
    "MSFT": ("Microsoft Corporation", "NASDAQ"),
    "GOOGL": ("Alphabet Inc.", "NASDAQ"),
    "GOOG": ("Alphabet Inc.", "NASDAQ"),
    "META": ("Meta Platforms, Inc.", "NASDAQ"),
    "TSLA": ("Tesla, Inc.", "NASDAQ"),
    "AMZN": ("Amazon.com, Inc.", "NASDAQ"),
    "NVDA": ("NVIDIA Corporation", "NASDAQ"),
    "NFLX": ("Netflix, Inc.", "NASDAQ"),
    "XOM": ("Exxon Mobil Corporation", "NYSE"),
    "JPMX": ("Synthetic Sharia-screened-out test fixture", "TEST"),
    "NEVR": ("Synthetic sharia/classification-unknown test fixture", "TEST"),
}


def _seed_common_test_tickers() -> None:
    from app.db import get_session
    from app.db.models import TickerReferenceRow

    now = datetime.now(timezone.utc)
    with get_session() as s:
        for symbol, (name, exchange) in _COMMON_TEST_TICKERS.items():
            s.add(TickerReferenceRow(
                symbol=symbol, company_name=name, exchange=exchange,
                is_etf=False, is_active=True, last_seen_at=now,
            ))


@pytest.fixture(autouse=True)
def _isolated_db(tmp_path: _Path) -> None:
    """Per-test sqlite database + singleton reset for every store/service.

    Runs autouse so every existing test gets a clean slate without changes.
    """
    db_file = tmp_path / "ami_trade_test.db"
    url = f"sqlite:///{db_file}"
    os.environ["AMI_TEST_DATABASE_URL"] = url

    from app.db import reset_for_tests
    from app.db.session import set_ambient_test_url
    # DEF324 — record which tempfile THIS test owns before building it, so a
    # nested fixture's bare `reset_for_tests()` teardown returns here instead of
    # falling through to the gitignored `backend/.local.db`.
    set_ambient_test_url(url)
    reset_for_tests(url)
    _seed_common_test_tickers()

    # Reset module-level singletons so cached pre-DB instances don't leak.
    from app.services import mandate_store as _ms
    from app.services import overlay_store as _os
    from app.services import journal_store as _js
    from app.services import lessons_service as _ls
    from app.services import sim_engine as _sim
    from app.services import room_runner as _rr
    from app.services import market_data as _md
    from app.services import news_context as _nc
    from app.services import social_context as _sc
    from app.services import watchlist_store as _ws
    from app.services import price_alert_store as _pas
    from app.services import feedback_store as _fb
    from app.services import inbox_store as _ib
    from app.services import daily_challenge_service as _dc
    from app.services import ai_coach_service as _ac
    from app.services import reputation_service as _rep
    from app.services import league_service as _lg
    _lg._service = None
    _ms._store = None
    _os._store = None
    _js._store = None
    _ls._service = None
    _sim._engine = None
    _rr._runner = None
    _ws._store = None
    _pas._store = None
    _fb._store = None
    _ib._store = None
    _dc._service = None
    _ac._service = None
    _rep._service = None
    # CR026: the sector-map provider caches the stored snapshot's ticker→sector map;
    # clear it so a seeded map from one test doesn't leak into the next.
    from app.services import sector_allocation as _sec
    _sec.reset_sector_map_provider(None)
    # CR145 Tier D: the quarterly-statements cache is keyed by TICKER and lives
    # for 6h, so without this the first test to fetch "AAPL" decides what every
    # later test sees for "AAPL" — including caching a None from a fake yfinance
    # that has no statement frames. Cleared here rather than per-test so no
    # future test has to remember, which is the only version of this that holds.
    from app.services import fundamentals as _fund
    _fund.clear_statement_cache()
    # Pin tests to the deterministic mock walk regardless of USE_REAL_MARKET_DATA.
    _md.set_market_data_provider(_md.MockWalkProvider())
    _nc.set_alpha_vantage_source(None)
    _sc.set_adanos_source(None)
    # B-tier audit (AT:R37): the rate-limit module holds module-level
    # singletons too; flush their sliding windows between tests so the
    # 4th `/v1/auth/magic_link/start` call in test_auth_phase1_5_audit_fixes
    # doesn't trip the 3/min IP limit.
    from app.services import rate_limit as _rl
    _rl.anon_rate_limit.reset()
    _rl.magic_link_start_rate_limit.reset()
    _rl.room_stream_rate_limit.reset()
    # CR027: notify()'s per-user push limiters — flush between tests so a
    # limit tripped in one test doesn't bleed into the next.
    from app.services import notification_service as _notif
    _notif._push_per_minute.reset()
    _notif._push_per_hour.reset()
    # CR128: the ticker reference module holds an in-process active-symbols
    # cache + a refresh-failure counter as module globals — clear both so a
    # cached symbol list (or a raised failure count) from one test's seeded
    # DB doesn't leak into the next.
    from app.services import ticker_reference as _tr
    _tr._invalidate_active_symbol_cache()
    _tr.reset_refresh_failures()
    # CR136 M01: the price-history store holds its own leaf provider (never the
    # fallback stack — see its module docstring) plus an in-process
    # failed-fetch throttle. Reset both so a fake injected by one test cannot
    # serve another, and a throttle tripped in one cannot suppress a fetch in
    # the next. (What keeps tests off live yfinance is USE_REAL_MARKET_DATA
    # defaulting to False, which resolves the leaf to the mock walk; a test that
    # flips it to True must inject a fake itself.)
    from app.services import price_history as _ph
    _ph.set_history_provider(None)


@pytest.fixture
def base_mandate() -> Mandate:
    """A vanilla 'risk_score=3, long-only, US English' mandate."""
    return Mandate(
        user_id=uuid4(),
        version=1,
        display_name="Test User",
        locale="en",
        timezone="UTC",
        primary_goal=PrimaryGoal.LONG_TERM_WEALTH,
        horizon=Horizon.LONG,
        target_outcome=None,
        path=Path.LONG_HORIZON,
        risk_score=3,
        risk_components=RiskComponents(
            drawdown_response=3, regret_asymmetry=0, concentration_tolerance=3
        ),
        risk_quotes=[],
        max_drawdown_pct=30,
        compliance=Compliance(long_only=True, liquid_only=True),
        learning_style=LearningStyle.QUICK,
        plan=Plan.TRADER,
        trial_expires_at=None,
        credit_balance=150,
        created_at=datetime(2026, 5, 11),
        updated_at=datetime(2026, 5, 11),
    )


@pytest.fixture
def halal_mandate(base_mandate: Mandate) -> Mandate:
    """A halal-compliant mandate (otherwise identical to base)."""
    return base_mandate.model_copy(
        update={
            "compliance": Compliance(
                halal=True, no_tobacco_alcohol_gambling=True, long_only=True, liquid_only=True
            ),
            "locale": "ar",
            "timezone": "Asia/Riyadh",
        }
    )


@pytest.fixture
def conservative_mandate(base_mandate: Mandate) -> Mandate:
    """risk_score=1, max_drawdown=10%."""
    return base_mandate.model_copy(
        update={
            "risk_score": 1,
            "max_drawdown_pct": 10,
            "risk_components": RiskComponents(
                drawdown_response=1, regret_asymmetry=-1, concentration_tolerance=1
            ),
        }
    )


@pytest.fixture
def aggressive_mandate(base_mandate: Mandate) -> Mandate:
    """risk_score=5, max_drawdown=50%, NOT long-only."""
    return base_mandate.model_copy(
        update={
            "risk_score": 5,
            "max_drawdown_pct": 50,
            "risk_components": RiskComponents(
                drawdown_response=5, regret_asymmetry=1, concentration_tolerance=5
            ),
            "compliance": Compliance(long_only=False, liquid_only=False),
            "path": Path.ACTIVE,
        }
    )


@pytest.fixture
def proposed_buy_nvda() -> ProposedTrade:
    return ProposedTrade(
        ticker="NVDA",
        side=Side.BUY,
        quantity=10,
        order_type=OrderType.LIMIT,
        limit_price=152.0,
    )


@pytest.fixture
def all_agents() -> tuple[AgentId, ...]:
    """The twelve display agents — the ones with a base prompt and an overlay
    builder. The internal compute identities are excluded: the Concierge (its
    own surface) and CR201's RISK_OFFICER (prompt assembled in code by
    `build_risk_officer_messages`; no content file, no overlay, by design)."""
    return tuple(
        a for a in AgentId if a not in (AgentId.CONCIERGE, AgentId.RISK_OFFICER)
    )


# ── The ledger invariant, enforced on every test (CR189 / DEF316 / DEF318) ──


@pytest.hookimpl(hookwrapper=True, tryfirst=True)
def pytest_runtest_makereport(item, call):
    """Record each phase's outcome so the ledger check can skip an already-failed
    test — an assertion in teardown would otherwise bury the real failure."""
    outcome = yield
    setattr(item, f"_rep_{call.when}", outcome.get_result())


@pytest.fixture(autouse=True)
def _ledger_invariant(request, _isolated_db):
    """`Σ the FIFO lots' quantity_open == Σ holdings`, per portfolio, per ticker.

    **Why this is autouse rather than one more test.** Three defects in three
    days were the same fact going wrong — a trade row and the shares behind it
    disagreeing — and each was found by hand, days apart, after shipping:

      * DEF311 — a resting sell outlived the shares it was selling, and opened a
        short when it fired.
      * DEF316 — a bracket outlived the shares it protected; the exit was then
        counted twice and `expected()` went negative into false phantom shares.
      * DEF318 — a dead lot's bracket fired on a later lot's shares.

    A point test per defect only ever catches the defect it was written for.
    This makes **every existing test that touches the sim engine** a ledger test:
    whatever a future change breaks, it fails in whatever test happens to
    exercise it, immediately, instead of being found by reading a table on Alpha
    weeks later. That is the difference between a guard and a note
    (`failure_patterns.md`'s house rule: an entry without an enforcing check is
    not done).

    **This is `def110_backfill.py`'s own derivation**, which is the point. The
    detector runs offline against production and answers "did we drift"; the
    same arithmetic here answers "can this code drift" before it ships. It is
    also why a BUY row deliberately stays `open` after a ticket sell — closing
    it would subtract the same exit twice — so this fixture pins the reason that
    design exists, not just its result.

    It calls `cost_basis_lots.open_quantity` — which sums `compute_lots_fifo`'s
    `quantity_open` — rather than re-deriving `Σ open BUY − Σ open SELL`, and
    DEF319 is why: those two are NOT the same number once a lot is partially
    sold and then stops out, and the backfill's original formula was the one
    that was wrong. Writing the check as a third implementation would have made
    it agree with the bug. That it calls the same *function* as the detector,
    not merely the same rule, is the R70 audit's MINOR-1: the summing step was
    two copies, in the detector and in the guard written to protect it.

    **Shorts do not break it**, and that is load-bearing rather than lucky: a
    short open/cover writes NO `sim_trades` row (CR171 acceptance 5, so
    `expected()` is byte-identical across opening a short), and its shares live
    in `sim_short_positions`. If a short ever started writing a sell row this
    fixture would fail loudly, which is the correct response.

    Opt out with `@pytest.mark.allow_ledger_drift` — only for tests that
    deliberately construct drift, i.e. the phantom-share detector's own tests and
    the repair scripts'. Adding it anywhere else is silencing the alarm.
    """
    yield

    rep = getattr(request.node, "_rep_call", None)
    if rep is not None and rep.failed:
        return  # do not bury the real failure under a consequence of it
    if request.node.get_closest_marker("allow_ledger_drift"):
        return

    from collections import defaultdict

    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import SimHoldingRow, SimTradeRow
    from app.services.cost_basis_lots import open_quantity

    with get_session() as s:
        trades = s.execute(select(SimTradeRow)).scalars().all()
        holdings = s.execute(select(SimHoldingRow)).scalars().all()
        grouped: dict[tuple, list] = defaultdict(list)
        for t in trades:
            grouped[(t.portfolio_id, t.ticker)].append(t)

        expected: dict[tuple, float] = defaultdict(float)
        for key, rows in grouped.items():
            expected[key] = open_quantity(rows)

        held: dict[tuple, float] = defaultdict(float)
        # A split is a DECLARED divergence, not drift: `apply_split` multiplies
        # `quantity` and divides `avg_cost` in place, writing no trade row,
        # because a split changes the share count without an economic event
        # (CR109 §12). `split_adjusted_at` is the flag that says so, which is
        # why this is skipped by rule rather than by exemption. The whole PAIR
        # drops out, not the holding row — dropping only the holding leaves the
        # trade side unopposed and reports the same drift with its sign flipped.
        split_adjusted = {
            (h.portfolio_id, h.ticker) for h in holdings
            if getattr(h, "split_adjusted_at", None) is not None
        }
        for h in holdings:
            held[(h.portfolio_id, h.ticker)] += float(h.quantity)

    # Only where the ENGINE wrote the ledger. A (portfolio, ticker) with no
    # trade rows at all was hand-seeded by a fixture reaching past `submit` —
    # common, and not a claim about bookkeeping, so there is nothing here to
    # keep consistent. Scoping this way rather than exempting ~20 test files
    # keeps the guard's meaning exact: *the engine's ledger explains the
    # holdings the engine produced.* Every defect in this family (DEF311,
    # DEF316, DEF318, DEF319) has trade rows on both sides and is still caught.
    drift = [
        (key, held.get(key, 0.0), expected.get(key, 0.0))
        for key in set(expected) | set(held)
        if key in grouped
        and key not in split_adjusted
        and abs(held.get(key, 0.0) - expected.get(key, 0.0)) > 1e-6
    ]
    if drift:
        lines = "\n".join(
            f"  portfolio {pid} {ticker}: holdings={h:g} expected={e:g} "
            f"drift={h - e:+g}"
            for (pid, ticker), h, e in drift
        )
        raise AssertionError(
            "sim ledger and holdings disagree — this is the phantom-share "
            "condition `def110_backfill.py` detects on production, reached here "
            "by code rather than by data:\n" + lines
        )


# --------------------------------------------------------------------------
# ISS002/CR208 — wire capture.
#
# Deliberately a session hook rather than a fixture: it must be installed
# before the first test module builds its own `TestClient(app)`, and it must
# observe every test, including those that never ask for a fixture. Writing at
# session finish rather than per-test keeps the cost to one file write.
#
# It records, and never asserts. A capture that failed an assertion mid-suite
# would turn an unrelated test red for a contract problem, which is how a
# useful signal gets deleted by whoever is trying to ship something else.
# `scripts/promotion/preflight_suite.sh` runs the comparison afterwards.
# --------------------------------------------------------------------------

_WIRE_CAPTURE_PATH = _Path(__file__).resolve().parent / "_wire_capture.jsonl"
_wire_records: list[dict] = []


def pytest_configure(config):
    # Redirect pytest's tmp_path/tmp_path_factory base to the external drive
    # when it's mounted: a 52GB backlog of abandoned pytest-of-<user> dirs
    # filled the internal disk (cleared 2026-09-03) because interrupted runs
    # skip pytest's keep-last-3 cleanup. Each invocation gets its OWN root,
    # not a shared one — pytest's numbered-dir pruning selects victims by
    # sequence number with no liveness check, so two concurrent suites
    # sharing a root delete each other's live fixtures mid-run (measured
    # 2026-09-03; see failure_patterns.md P33 for the sibling git-side class).
    # atexit reaps this run's root; the 48h sweep reaps roots whose runs were
    # killed before their atexit could — a 2-day-old root cannot be live.
    # No-op on machines without the drive (CI included) and when the caller
    # already pinned PYTEST_DEBUG_TEMPROOT itself.
    _external_drive = _Path("/Volumes/Extreme Pro")
    if _external_drive.exists() and "PYTEST_DEBUG_TEMPROOT" not in os.environ:
        _roots = _external_drive / "tmp_claude_pytest" / "roots"
        _roots.mkdir(parents=True, exist_ok=True)
        _cutoff = time.time() - 48 * 3600
        for _old in _roots.iterdir():
            try:
                if _old.stat().st_mtime < _cutoff:
                    shutil.rmtree(_old, ignore_errors=True)
            except OSError:
                pass
        _root = _roots / f"run_{os.getpid()}_{uuid4().hex[:8]}"
        _root.mkdir()
        os.environ["PYTEST_DEBUG_TEMPROOT"] = str(_root)
        atexit.register(shutil.rmtree, str(_root), True)

    from starlette.testclient import TestClient

    original_request = TestClient.request

    def _capturing_request(self, method, url, *args, **kwargs):
        response = original_request(self, method, url, *args, **kwargs)
        try:
            path = response.request.url.path
            ctype = response.headers.get("content-type", "")
            body = response.json() if "application/json" in ctype else None
        except Exception:
            # A body we cannot read is recorded as unreadable, not skipped:
            # the request still happened, and dropping it would quietly shrink
            # the denominator the coverage number is computed from.
            body, path = None, str(url)
        _wire_records.append(
            {"method": str(method).upper(), "path": path,
             "status": response.status_code, "body": body}
        )
        return response

    TestClient.request = _capturing_request
    config._wire_capture_original_request = original_request


def pytest_sessionfinish(session, exitstatus):
    try:
        with _WIRE_CAPTURE_PATH.open("w", encoding="utf-8") as fh:
            for record in _wire_records:
                fh.write(json.dumps(record) + "\n")
    except OSError:
        # Never fail a green suite because an artefact could not be written —
        # but say so, because a silently absent capture makes every surface
        # look UNVERIFIED for the wrong reason.
        print("\n[wire_capture] could not write", _WIRE_CAPTURE_PATH)
