"""CR136 M11 A1 — the live cross-check's exit code must mean "compared everything", not "found nothing to disagree with".

M11 §4 argued this deliverable "has no test that can be made to fail". The
auditor wrote one anyway — two module-level stubs and a call to `main()` — and
it found a MAJOR on first contact: an unpublished metric was printed and then
dropped from the exit code, so the gate returned 0 having compared four of seven
and still printed *"PASS — every published metric agrees to 2 dp."*

Checklist 2.9's acceptance criterion is literally that exit code. CR038's rule
in this repo is that an instruction is not a control; this is the same rule
applied to a gate — the `checked: N` line was prose, and prose is not what the
promotion protocol reads.

These tests stub the harness's two I/O seams — `_fetch_health` and
`_load_closes` — and drive `main()` end to end. The control payload is built
from the harness's OWN helpers over the same stubbed closes, so it genuinely
agrees; a gate that simply failed on everything would satisfy every negative
test here and prove nothing.
"""

from __future__ import annotations

import math
from datetime import date, timedelta

import numpy as np
import pytest

crosscheck = pytest.importorskip(
    "scripts.cr136_live_crosscheck",
    reason="the harness imports numpy directly, not through the app",
)


_TICKERS = ("AAA", "BBB")
_BENCH = "SPY"


def _closes(n: int = 400) -> dict[str, dict[date, float]]:
    """Deterministic, mutually correlated closes, in `_load_closes`'s own shape.

    The price path is arbitrary — what these tests exercise is the gate's
    DECISION, not the arithmetic, which M02's known-answer fixtures already pin
    against an independent numpy implementation."""
    start = date(2024, 1, 2)
    out: dict[str, dict[date, float]] = {}
    for k, ticker in enumerate((*_TICKERS, _BENCH)):
        px, series = 100.0, {}
        for i in range(n):
            px *= 1.0 + 0.004 * math.sin(0.11 * i + k) + 0.0002 * k
            series[start + timedelta(days=i)] = px
        out[ticker] = series
    return out


def _agreeing_payload(**overrides) -> dict:
    """An `ok` envelope whose numbers the harness will AGREE with.

    Built by running the harness's own helpers over the same stubbed closes, so
    the control case genuinely passes. If the payload numbers were invented, a
    gate that failed on everything would satisfy every negative test here and
    the suite would prove nothing."""
    closes = _closes()
    tickers = list(_TICKERS)
    returns, _days = crosscheck._joined_returns(closes, [*tickers, _BENCH])
    n_risky = len(tickers)
    b_index = n_risky

    weights = np.array([0.5, 0.5])
    cov_joint = crosscheck.ewma_covariance(returns)
    cov_risky = cov_joint[:n_risky, :n_risky]
    cov_full = crosscheck.append_cash_row(cov_joint)

    w_full = np.zeros(n_risky + 2)
    w_full[:n_risky] = weights
    sigma_ann = math.sqrt(crosscheck.variance(w_full, cov_full)) * math.sqrt(252.0)
    beta, r_squared = crosscheck.beta_r2(w_full, cov_full, b_index)
    sigma_b_ann = math.sqrt(cov_joint[b_index, b_index] * 252.0)
    te_ann = crosscheck.tracking_error(sigma_ann, sigma_b_ann, beta)
    shares = crosscheck.risk_shares(weights, cov_risky)

    blocks = {
        "portfolio_volatility": {
            "sufficient": True, "value": sigma_ann,
            "n_observations": returns.shape[1],
        },
        "beta": {"sufficient": True, "value": beta, "r_squared": r_squared},
        "tracking_error": {"sufficient": True, "value": te_ann},
        "effective_bets": {
            "sufficient": True,
            "value": crosscheck.dr_squared(weights, cov_risky),
        },
        "risk_contribution": {
            "sufficient": True,
            "per_holding": [
                {
                    "ticker": t, "invested_weight": 0.5,
                    "risk_share": float(shares[i]),
                }
                for i, t in enumerate(tickers)
            ],
        },
    }
    blocks.update(overrides.pop("blocks", {}))
    metrics = {
        "status": "ok", "engine_version": "test", "as_of": "2026-08-05",
        "blocks": blocks, "covered_invested_value": 1000.0,
        "total_value": 1000.0, "cash_fraction": 0.0,
        "dropped_holdings": [], "partial": False,
    }
    metrics.update(overrides)
    return {"metrics": metrics}


def _run(monkeypatch, envelope: dict, *argv: str) -> int:
    monkeypatch.setattr(
        crosscheck, "_fetch_health", lambda *_a, **_k: envelope,
    )
    monkeypatch.setattr(
        crosscheck, "_load_closes", lambda _tickers: (_closes(), {}),
    )
    return crosscheck.main([
        "--user-id", "00000000-0000-0000-0000-000000000001",
        "--token", "t", *argv,
    ])


def test_an_unpublished_metric_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """A1's reachable route, no unusual book required: a bad print in stored SPY
    makes the engine drop the benchmark, three level metrics come back null, the
    joined window still matches, and the old gate printed PASS."""
    envelope = _agreeing_payload(blocks={
        "beta": {"sufficient": False, "value": None, "r_squared": None},
        "tracking_error": {"sufficient": False, "value": None},
    })
    assert _run(monkeypatch, envelope) == 1

    out = capsys.readouterr().out
    assert "FAIL" in out
    for metric in ("beta", "r_squared", "tracking_error"):
        assert metric in out


def test_a_renamed_payload_field_fails_the_gate(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """DEF210's shape one layer further out, sitting in the ship gate: the
    harness reads `blocks["beta"]["r_squared"]` with no schema pin, and M07 owns
    that payload in a different lane. Rename the field and every OTHER metric
    still agrees — which is exactly why the old gate said PASS."""
    envelope = _agreeing_payload()
    beta_block = envelope["metrics"]["blocks"]["beta"]
    beta_block["rsq"] = beta_block.pop("r_squared")

    # Only the FIELD NAME changes — beta's own value still agrees, and so does
    # every other metric. Isolating it this way is the point: replacing the
    # whole beta block would make the run fail on a numeric disagreement and
    # the test would pass without the gate ever noticing the rename.
    assert _run(monkeypatch, envelope) == 1
    assert "r_squared" in capsys.readouterr().out


def test_an_expected_absence_can_be_waived_by_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """The waiver has to name them, so the operator states the subset rather
    than the gate silently choosing one."""
    envelope = _agreeing_payload(blocks={
        "beta": {"sufficient": False, "value": None, "r_squared": None},
        "tracking_error": {"sufficient": False, "value": None},
    })
    code = _run(
        monkeypatch, envelope, "--allow-unchecked", "beta,r_squared,tracking_error",
    )
    assert code == 0

    out = capsys.readouterr().out
    assert "PASS" in out
    assert "waived" in out
    assert "4 of 7" in out, "5 named metrics + one risk_share row per holding"


def test_a_partial_waiver_still_fails_on_the_absence_it_did_not_name(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """M11 r2 m5. This is the property that makes `--allow-unchecked` a WAIVER
    rather than a `--force`, and it was stated only in prose — the auditor's
    AUD-1 turned any waiver into a blanket one and all six tests still passed,
    because the test above waives ALL of the absences.

    That is the same shape as the MAJOR this flag fixes, one level down: a
    control whose load-bearing property lives in a sentence. The flag will be
    typed at a ship gate by an operator who wants a green result."""
    envelope = _agreeing_payload(blocks={
        "beta": {"sufficient": False, "value": None, "r_squared": None},
        "tracking_error": {"sufficient": False, "value": None},
    })
    # Three metrics go unpublished; only two are named.
    code = _run(monkeypatch, envelope, "--allow-unchecked", "beta,r_squared")
    assert code == 1, "an unnamed absence must still fail the run"

    out = capsys.readouterr().out
    assert "FAIL" in out
    assert "tracking_error" in out


def test_a_waiver_cannot_launder_a_published_disagreement(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """The waiver covers ABSENCE only. A metric that is published and disagrees
    is compared and fails whatever the flag names — otherwise `--allow-unchecked`
    would be a way to make a wrong number green."""
    envelope = _agreeing_payload(blocks={
        "effective_bets": {"sufficient": True, "value": 99.0},
    })
    code = _run(monkeypatch, envelope, "--allow-unchecked", "effective_bets")
    assert code == 1
    assert "disagree beyond 2 dp" in capsys.readouterr().out


def test_a_waiver_for_a_published_metric_is_reported_as_stale(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """AUD-3 — deleting this line survived the auditor's pass. Cosmetic in
    consequence, but it is the only thing that stops a waiver quietly outliving
    the reason it was added, which is how a subset becomes permanent."""
    assert _run(monkeypatch, _agreeing_payload(), "--allow-unchecked", "beta") == 0

    out = capsys.readouterr().out
    assert "but PUBLISHED" in out
    assert "beta" in out


def test_a_full_payload_passes_and_says_how_many(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """The vacuity guard on all of the above: when everything is published and
    agrees, the gate must still pass — and now says N, because "PASS" alone was
    what could not be distinguished from a subset."""
    assert _run(monkeypatch, _agreeing_payload()) == 0

    out = capsys.readouterr().out
    assert "PASS" in out
    assert "all 7 metrics" in out
    assert "not checked" not in out


def test_a_real_disagreement_still_fails(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture,
) -> None:
    """The control the auditor ran: when the harness DOES compare, it works.
    Without this, a gate that failed on everything would pass the tests above."""
    envelope = _agreeing_payload(blocks={
        "effective_bets": {"sufficient": True, "value": 99.0},
    })
    assert _run(monkeypatch, envelope) == 1
    assert "disagree beyond 2 dp" in capsys.readouterr().out


def test_the_harness_imports_no_application_module() -> None:
    """M11's independence claim, asserted in prose and never guarded — the
    cross-check is only evidence if it does not recompute using the code it is
    checking. Same shape as `test_cr136_dart_parity.py`: read the boundary
    rather than trust a sentence about it.

    Read from source rather than `sys.modules`, because pytest has the whole
    app imported already and a runtime check would pass no matter what this
    file did."""
    with open(crosscheck.__file__, encoding="utf-8") as handle:
        lines = [ln.strip() for ln in handle if ln.strip().startswith(("import ", "from "))]

    # The claim is about the ARITHMETIC. `settings`, `get_session`,
    # `PriceHistoryDailyRow` and `_MOCK_SOURCE` are imported on purpose and
    # documented as such — reading the stored prices is not recomputing them.
    # `app.trading_math` is the module under test, and importing it (directly
    # or via `portfolio_health_constants`, which routes through it) would make
    # the cross-check compare the engine against itself.
    offenders = [ln for ln in lines if "trading_math" in ln or "health_constants" in ln]
    assert offenders == [], offenders
