"""DEF385 — the backtest's look-ahead window must be tied to the model answering.

`--window-start` was a number a human typed from the cutoff probe. When CR211
swapped the served model (and reused the `ami-llm` alias) the guard kept
enforcing a boundary five months too early and the sweep would have reported
itself leakage-clean on contaminated dates. The reference value the guard
compares against is now the probe's recorded model `root` versus the `root`
the server reports now, and a refusal is code with no override.

Also pins the half that must NOT regress: a real look-ahead leak (a row dated
past the as-of, a pair dated before the window) still fails closed.
"""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import scripts.backtest_model_guard as guard
import scripts.backtest_sweep as sweep
from scripts.backtest_report import _model_line

OLD = "/models/qwen36-35b-a3b-nvfp4"
NEW = "/models/qwen38-flash-next-abliterated-nvfp4"


def _probe(tmp_path, *, identity=NEW, window_start="2025-08-01") -> Path:
    path = tmp_path / "cutoff_probe.json"
    body = {"window_start": window_start}
    if identity is not None:
        body["served_identity"] = identity
    path.write_text(json.dumps(body))
    return path


def _args(probe: Path, *, window_start=date(2025, 8, 1), plan_only=False, url="http://x"):
    return Namespace(
        cutoff_probe=probe, window_start=window_start,
        plan_only=plan_only, llm_base_url=url,
    )


def _serve(monkeypatch, root: str) -> None:
    monkeypatch.setattr(guard, "served_identity", lambda base_url, **kw: root)


def test_a_probe_measured_on_another_model_is_refused(tmp_path, monkeypatch):
    """The DEF385 scenario: window from the old model, new model answering."""
    _serve(monkeypatch, NEW)
    probe = _probe(tmp_path, identity=OLD, window_start="2025-02-28")
    with pytest.raises(SystemExit) as e:
        sweep.verify_window_model(_args(probe, window_start=date(2025, 2, 28)))
    assert "REFUSING" in str(e.value)
    assert OLD in str(e.value) and NEW in str(e.value)


def test_a_matching_probe_passes(tmp_path, monkeypatch):
    _serve(monkeypatch, NEW)
    assert sweep.verify_window_model(_args(_probe(tmp_path))) == (NEW, NEW)


def test_the_number_is_taken_from_the_probe_not_the_typed_flag(tmp_path, monkeypatch):
    """The old stale 2025-02-28 typed against a fresh probe is refused."""
    _serve(monkeypatch, NEW)
    with pytest.raises(SystemExit) as e:
        sweep.verify_window_model(_args(_probe(tmp_path), window_start=date(2025, 2, 28)))
    assert "earlier than the probe" in str(e.value)


def test_a_later_window_start_is_more_conservative_and_allowed(tmp_path, monkeypatch):
    _serve(monkeypatch, NEW)
    sweep.verify_window_model(_args(_probe(tmp_path), window_start=date(2025, 9, 5)))


@pytest.mark.parametrize("identity", [None, "", "UNIDENTIFIED (ConnectError)"])
def test_a_probe_that_does_not_name_its_model_is_refused(tmp_path, monkeypatch, identity):
    """Every probe report written before DEF385 lacks the field."""
    _serve(monkeypatch, NEW)
    with pytest.raises(SystemExit):
        sweep.verify_window_model(_args(_probe(tmp_path, identity=identity)))


def test_a_probe_with_no_window_is_refused(tmp_path, monkeypatch):
    _serve(monkeypatch, NEW)
    with pytest.raises(SystemExit):
        sweep.verify_window_model(_args(_probe(tmp_path, window_start=None)))


def test_a_missing_probe_file_is_refused(tmp_path, monkeypatch):
    _serve(monkeypatch, NEW)
    with pytest.raises(SystemExit):
        sweep.verify_window_model(_args(tmp_path / "nope.json"))


def test_an_unidentifiable_server_is_refused(tmp_path, monkeypatch):
    def boom(base_url, **kw):
        raise guard.ModelGuardError("connection refused")

    monkeypatch.setattr(guard, "served_identity", boom)
    with pytest.raises(SystemExit) as e:
        sweep.verify_window_model(_args(_probe(tmp_path)))
    assert "REFUSING" in str(e.value)


def test_no_llm_base_url_is_refused_not_skipped(tmp_path, monkeypatch):
    _serve(monkeypatch, NEW)
    with pytest.raises(SystemExit):
        sweep.verify_window_model(_args(_probe(tmp_path), url=None))


def test_plan_only_checks_the_probe_offline(tmp_path, monkeypatch):
    def boom(base_url, **kw):
        raise AssertionError("plan-only must not touch the network")

    monkeypatch.setattr(guard, "served_identity", boom)
    assert sweep.verify_window_model(_args(_probe(tmp_path), plan_only=True)) == (NEW, None)
    with pytest.raises(SystemExit):
        sweep.verify_window_model(
            _args(_probe(tmp_path, identity=None), plan_only=True)
        )


def test_the_real_served_identity_prefers_root_over_the_reusable_alias(monkeypatch):
    class Resp:
        def raise_for_status(self): ...

        def json(self):
            return {"data": [{"id": "ami-llm", "root": NEW}]}

    monkeypatch.setattr(guard.httpx, "get", lambda *a, **k: Resp())
    assert guard.served_identity("http://x") == NEW


def test_a_mid_batch_model_swap_aborts(monkeypatch, capsys):
    args = Namespace(llm_base_url="http://x")
    _serve(monkeypatch, NEW)
    assert sweep._model_unchanged(args, NEW) is True
    _serve(monkeypatch, OLD)
    assert sweep._model_unchanged(args, NEW) is False
    assert "changed mid-batch" in capsys.readouterr().out


def test_a_mixed_model_resume_is_refused(tmp_path):
    kw = dict(probe_source="p.json", probe_window_start="2025-08-01",
              window_start=date(2025, 8, 1))
    guard.write_stamp(tmp_path, "b1", served=NEW, **kw)
    guard.write_stamp(tmp_path, "b1", served=NEW, **kw)
    with pytest.raises(guard.ModelGuardError):
        guard.write_stamp(tmp_path, "b1", served=OLD, **kw)
    assert guard.read_stamp(tmp_path, "b1")["served_model"] == NEW


def test_the_report_stamps_the_model_and_flags_an_unstamped_batch(tmp_path):
    guard.write_stamp(
        tmp_path, "b1", served=NEW, probe_source="p.json",
        probe_window_start="2025-08-01", window_start=date(2025, 8, 1),
    )
    assert NEW in _model_line(guard.read_stamp(tmp_path, "b1"))
    unstamped = _model_line(guard.read_stamp(tmp_path, "nope"))
    assert "NOT RECORDED" in unstamped and "leakage-clean" in unstamped


# ── The window guard itself must still fail closed on a real leak ───────────


def test_a_replayed_pair_before_the_window_is_refused(tmp_path, monkeypatch):
    """A planted pre-window as_of in a replayed batch aborts the sweep."""
    _serve(monkeypatch, NEW)
    pairs = tmp_path / "pairs.jsonl"
    pairs.write_text(
        json.dumps({"ticker": "AAPL", "as_of": "2025-03-07", "status": "completed"}) + "\n"
        + json.dumps({"ticker": "MSFT", "as_of": "2025-09-05", "status": "completed"}) + "\n"
    )
    universe = tmp_path / "u.txt"
    universe.write_text("AAPL\nMSFT\n")
    monkeypatch.setattr(sys, "argv", [
        "backtest_sweep", "--batch-id", "t", "--plan-only",
        "--window-start", "2025-08-01", "--window-end", "2025-12-31",
        "--cutoff-probe", str(_probe(tmp_path)),
        "--n-pairs", "2", "--seed", "1",
        "--pairs-file", str(pairs), "--universe-file", str(universe),
    ])
    with pytest.raises(SystemExit) as e:
        sweep.main()
    assert "before window-start" in str(e.value)


def test_a_planted_future_dated_row_still_raises():
    from app.services.asof_context import AsOfLeakageError, assert_dates_within

    as_of = date(2025, 9, 5)
    with pytest.raises(AsOfLeakageError):
        assert_dates_within([date(2025, 9, 4), date(2025, 9, 8)], as_of, origin="planted")


def test_a_planted_future_bar_is_not_served_by_the_asof_read():
    from app.db import get_session
    from app.db.models import PriceHistoryDailyRow
    from app.services.price_history import get_asof_daily_rows

    now = datetime(2026, 8, 10, tzinfo=timezone.utc)
    with get_session() as session:
        for d in (date(2025, 9, 4), date(2025, 9, 5), date(2025, 9, 8)):
            session.add(PriceHistoryDailyRow(
                ticker="DEF385", date=d, close=10.0, adj_close=10.0, open=9.5,
                high=10.5, low=9.0, volume=1, source="yfinance", fetched_at=now,
            ))
    rows = get_asof_daily_rows("DEF385", date(2025, 9, 5))
    assert [r[0] for r in rows] == [date(2025, 9, 4), date(2025, 9, 5)]
