"""CR289 — the Bursa batch driver's desk-model pin and risk-score flags.

Network is never touched: `convene` / `poll_run` are faked and `main` is driven with
a fake httpx client. These pin what keeps two arms from getting confused:

1. `--risk-score` and `--desk-provider` parse, and reach the mandate and the body.
2. Every record carries the `desk_provider` and `risk_score` it ran under.
3. A refused pin (403, or a 422 naming `desk_provider`) stops the WHOLE batch with
   exit 2 and records nothing for that ticker; a 422 about a ticker does not.
4. A pinned Room that was refunded as a provider outage is retried, never a result.
5. A batch file holds one arm: resuming it under another pin or risk refuses.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx
import pytest

from scripts import bursa_batch


def _status_error(code: int, text: str = "body"):
    req = httpx.Request("POST", "http://x/v1/room/stream")
    return httpx.HTTPStatusError(
        "e", request=req, response=httpx.Response(code, request=req, text=text)
    )


class _Args:
    batch_id = "b"
    base_url = "http://h"
    max_attempts = 3
    retry_backoff = 1.0
    credit_grant = 2000
    poll_interval = 0.0
    run_timeout = 1.0
    no_snapshot = True
    desk_provider = "deepseek"
    risk_score = 4


USER = {"user_id": "u", "token": "t"}


# ---- 1. flags ---------------------------------------------------------------


def test_build_mandate_sets_the_risk_score_and_keeps_every_filter_off():
    m = bursa_batch.build_mandate(4)
    assert m["risk_score"] == 4
    assert m["compliance"] == bursa_batch.BURSA_MANDATE_OVERRIDE["compliance"]
    assert bursa_batch.build_mandate()["risk_score"] == 5
    assert bursa_batch.BURSA_MANDATE_OVERRIDE["risk_score"] == 5, "the module constant is untouched"


def _argv(monkeypatch, tmp_path, *extra):
    sample = tmp_path / "s.csv"
    sample.write_text("symbol,short_name\n1155.KL,MAYBANK\n0166.KL,INARI\n")
    monkeypatch.setattr(sys, "argv", [
        "bursa_batch", str(sample), "--batch-id", "t1", "--out-dir", str(tmp_path / "out"),
        *extra,
    ])


def test_dry_run_prints_the_pin_and_risk_score(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(httpx.Client, "__init__", lambda *a, **k: pytest.fail("network used"))
    _argv(monkeypatch, tmp_path, "--dry-run", "--risk-score", "4", "--desk-provider", "vllm_fallback")
    assert bursa_batch.main() == 0
    text = capsys.readouterr().out
    assert "risk score      : 4" in text
    assert "PINNED to provider slot 'vllm_fallback'" in text
    assert '"risk_score": 4' in text


def test_dry_run_default_is_risk_5_and_no_pin(tmp_path, monkeypatch, capsys):
    _argv(monkeypatch, tmp_path, "--dry-run")
    assert bursa_batch.main() == 0
    text = capsys.readouterr().out
    assert "risk score      : 5" in text and "backend default (no pin)" in text


@pytest.mark.parametrize("flags", [
    ("--risk-score", "0"), ("--risk-score", "6"), ("--desk-provider", "vllm"),
    ("--desk-provider", "anthropic"),
])
def test_out_of_range_flags_are_refused_by_the_parser(tmp_path, monkeypatch, flags):
    _argv(monkeypatch, tmp_path, "--dry-run", *flags)
    with pytest.raises(SystemExit) as e:
        bursa_batch.main()
    assert e.value.code == 2


def test_the_full_universe_csv_loads_with_its_symbol_column():
    csv_path = (
        Path(__file__).resolve().parents[3]
        / "docs/forward_planning/CR282_bursa_malaysia/bursa_batch/universe_2026-11-25.csv"
    )
    tickers = bursa_batch.load_tickers(csv_path)
    assert len(tickers) == len(set(tickers)) > 1000
    assert all(t.endswith(".KL") for t in tickers)


# ---- 1b. the request body -----------------------------------------------------


class _FakeStream:
    def __init__(self, sink: list):
        self.sink = sink

    def stream(self, method, url, json, headers):
        self.sink.append(json)
        return self

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    status_code = 200
    headers = {"X-Room-Run-Id": "r1"}

    def raise_for_status(self):
        pass


def test_convene_sends_desk_provider_only_when_set():
    sent: list[dict] = []
    fake = _FakeStream(sent)
    out = bursa_batch.convene(fake, "http://h", "t", "u", "1155.KL", {"risk_score": 4}, "deepseek")
    bursa_batch.convene(fake, "http://h", "t", "u", "1155.KL", {"risk_score": 4})
    assert out == ("r1", False, False)
    assert sent[0]["desk_provider"] == "deepseek"
    assert "desk_provider" not in sent[1]
    assert sent[0]["mandate_override"] == {"risk_score": 4}


# ---- 2. record stamping -------------------------------------------------------


def _ok_poll(**extra):
    return lambda *a, **k: {"status": "completed", "verdict": {"action": "PASS"}, **extra}


def test_record_is_stamped_with_the_pin_and_risk(monkeypatch):
    seen = []
    monkeypatch.setattr(
        bursa_batch, "convene",
        lambda *a, **k: seen.append(a[-1]) or ("r1", False, False),
    )
    monkeypatch.setattr(bursa_batch.rb, "poll_run", _ok_poll())
    rec = bursa_batch.run_ticker(
        None, _Args, USER, "1155.KL", bursa_batch.build_mandate(4), sleep=lambda s: None,
    )
    assert rec["status"] == "completed"
    assert rec["desk_provider"] == "deepseek" and rec["risk_score"] == 4
    assert seen == ["deepseek"], "the pin is passed to convene"


def test_unpinned_record_carries_desk_provider_none(monkeypatch):
    class Unpinned(_Args):
        desk_provider = None

    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: ("r1", False, False))
    monkeypatch.setattr(bursa_batch.rb, "poll_run", _ok_poll())
    rec = bursa_batch.run_ticker(
        None, Unpinned, USER, "1155.KL", bursa_batch.build_mandate(5), sleep=lambda s: None,
    )
    assert rec["desk_provider"] is None and rec["risk_score"] == 5


def test_a_completed_record_carries_the_scripted_turn_counts(monkeypatch):
    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: ("r1", False, False))
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {
        "status": "completed", "refunded": False,
        "verdict": {"action": "PASS", "scripted_turns": 2, "scripted_agents": ["social_analyst"]},
    })
    rec = bursa_batch.run_ticker(None, _Args, USER, "1155.KL", {}, sleep=lambda s: None)
    assert rec["scripted_turns"] == 2 and rec["scripted_agents"] == ["social_analyst"]


# ---- 3. a refused pin stops the batch -----------------------------------------


@pytest.mark.parametrize("exc", [
    _status_error(403, '{"detail": "desk_provider is not available to this account"}'),
    _status_error(422, '{"detail": "desk_provider \'deepseek\' is not registered on this backend"}'),
])
def test_a_refused_pin_raises_pin_refused_and_is_not_retried(monkeypatch, exc):
    calls = []
    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: calls.append(1) or (_ for _ in ()).throw(exc))
    with pytest.raises(bursa_batch.PinRefused):
        bursa_batch.run_ticker(None, _Args, USER, "1155.KL", {}, sleep=lambda s: None)
    assert len(calls) == 1


def test_a_ticker_422_is_still_a_per_ticker_permanent_failure(monkeypatch):
    monkeypatch.setattr(
        bursa_batch, "convene",
        lambda *a, **k: (_ for _ in ()).throw(_status_error(422, "unknown ticker 9999.KL")),
    )
    rec = bursa_batch.run_ticker(None, _Args, USER, "9999.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "permanent_failure"


def test_a_403_without_a_pin_is_not_a_pin_refusal(monkeypatch):
    class Unpinned(_Args):
        desk_provider = None

    monkeypatch.setattr(
        bursa_batch, "convene", lambda *a, **k: (_ for _ in ()).throw(_status_error(403)),
    )
    rec = bursa_batch.run_ticker(None, Unpinned, USER, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "permanent_failure"


class _HealthyClient:
    def __init__(self, *a, **k):
        pass

    def get(self, url):
        return httpx.Response(200, json={"ok": True}, request=httpx.Request("GET", url))


def test_main_stops_the_whole_batch_on_a_refused_pin_and_records_nothing_for_it(
    tmp_path, monkeypatch, capsys,
):
    sample = tmp_path / "s.txt"
    sample.write_text("1111.KL\n2222.KL\n3333.KL\n")
    out = tmp_path / "out"
    ran = []

    def fake_run_ticker(client, args, user, ticker, mandate, **k):
        ran.append(ticker)
        if ticker == "2222.KL":
            raise bursa_batch.PinRefused("2222.KL: backend refused desk_provider='deepseek'")
        return {"status": "completed", "ticker": ticker, "attempts": [{}],
                "verdict": {"action": "PASS"}, "desk_provider": args.desk_provider}

    monkeypatch.setattr(bursa_batch.httpx, "Client", _HealthyClient)
    monkeypatch.setattr(bursa_batch, "worker_user",
                        lambda *a, **k: {"user_id": "u", "token": "t", "plan": "trader"})
    monkeypatch.setattr(bursa_batch, "run_ticker", fake_run_ticker)
    monkeypatch.setattr(sys, "argv", [
        "bursa_batch", str(sample), "--batch-id", "t1", "--out-dir", str(out),
        "--desk-provider", "deepseek", "--risk-score", "4", "--post-spacing", "0",
    ])

    assert bursa_batch.main() == 2

    assert ran == ["1111.KL", "2222.KL"], "3333.KL must never start"
    lines = [json.loads(x) for x in (out / "runs_t1.jsonl").read_text().splitlines()]
    assert [r["ticker"] for r in lines] == ["1111.KL"]
    text = capsys.readouterr().out
    assert "PIN REFUSED - STOPPING THE BATCH" in text and "STOPPED" in text


# ---- 4. pinned outage is retried ------------------------------------------------


def test_a_pinned_room_refunded_as_an_outage_is_retried_not_recorded_as_a_result(monkeypatch):
    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: ("r1", False, False))
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {
        "status": "completed", "refunded": True, "verdict": {"action": "PASS"},
    })
    rec = bursa_batch.run_ticker(None, _Args, USER, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "failed_after_retries" and len(rec["attempts"]) == 3
    assert rec.get("verdict") is None
    assert "pinned provider failed" in rec["error_message"]


def test_an_unpinned_refunded_room_keeps_todays_behaviour(monkeypatch):
    class Unpinned(_Args):
        desk_provider = None

    monkeypatch.setattr(bursa_batch, "convene", lambda *a, **k: ("r1", False, False))
    monkeypatch.setattr(bursa_batch.rb, "poll_run", lambda *a, **k: {
        "status": "completed", "refunded": True, "verdict": {"action": "PASS"},
    })
    rec = bursa_batch.run_ticker(None, Unpinned, USER, "1155.KL", {}, sleep=lambda s: None)
    assert rec["status"] == "completed"


# ---- 5. one arm per batch file --------------------------------------------------


def test_resume_under_a_different_pin_refuses():
    latest = {"1155.KL": {"desk_provider": "deepseek", "risk_score": 4}}
    bursa_batch.check_resume_consistency(latest, "deepseek", 4)
    with pytest.raises(SystemExit, match="new --batch-id per arm"):
        bursa_batch.check_resume_consistency(latest, "vllm_fallback", 4)
    with pytest.raises(SystemExit):
        bursa_batch.check_resume_consistency(latest, None, 4)
    with pytest.raises(SystemExit):
        bursa_batch.check_resume_consistency(latest, "deepseek", 5)


def test_resume_of_an_older_unpinned_batch_is_still_allowed():
    latest = {"1155.KL": {"risk_score": 5, "status": "completed"}}
    bursa_batch.check_resume_consistency(latest, None, 5)
    with pytest.raises(SystemExit):
        bursa_batch.check_resume_consistency(latest, "deepseek", 5)
