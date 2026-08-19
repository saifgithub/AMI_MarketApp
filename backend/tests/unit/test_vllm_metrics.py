"""CR192 — the vLLM prefix-cache sampler.

Grouped by the fact each test defends, because most of them are about the ways
this measurement can lie rather than about arithmetic:

  1. The parser reads the real wire format, including the scientific notation
     Prometheus actually emits and the case where the counters are absent.
  2. A rate is only ever DERIVED, never stored, and never fabricated. Every
     not-a-measurement is its own status with `rate=None` — a reset, an idle
     window and a missing sample are three different facts and none of them is
     zero.

(2) is the whole reason the table stores raw counters. It is also the part that
was not in the original CR: the counters were found reset between 2026-08-16 and
2026-08-19 (1,064,911 against 59,681,175), which a naive delta reports as a
catastrophic negative and a `max(0, ...)` reports as a total cache collapse.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from app.services.vllm_metrics import (
    CacheCounters,
    _metrics_url,
    _rate_between,
    parse_prefix_cache_counters,
)

# Captured verbatim from http://192.168.20.74:8000/metrics on 2026-08-19.
_REAL_BODY = """\
# HELP vllm:prefix_cache_queries_total Prefix cache queries.
# TYPE vllm:prefix_cache_queries_total counter
vllm:prefix_cache_queries_total{engine="0",model_name="ami-llm"} 1.064911e+06
# HELP vllm:prefix_cache_hits_total Prefix cache hits.
# TYPE vllm:prefix_cache_hits_total counter
vllm:prefix_cache_hits_total{engine="0",model_name="ami-llm"} 612032.0
vllm:num_requests_running{model_name="ami-llm"} 0.0
"""


class _Sample:
    """Stands in for a stored row — `_rate_between` only reads three fields."""

    def __init__(self, queries: int, hits: int, at: datetime):
        self.queries_total = queries
        self.hits_total = hits
        self.sampled_at = at


_T0 = datetime(2026, 8, 19, 9, 0, tzinfo=timezone.utc)
_T1 = _T0 + timedelta(hours=1)


# ── 1. the parser, against the format the server really emits ──────────────


def test_parses_the_real_captured_body():
    c = parse_prefix_cache_counters(_REAL_BODY)
    assert c == CacheCounters(queries_total=1064911, hits_total=612032, model_name="ami-llm")


def test_scientific_notation_is_not_truncated_or_crashed_on():
    """`int("1.064911e+06")` raises, and a naive int() cast here would have made
    every reading above ~1e6 a hard failure — which is every reading."""
    c = parse_prefix_cache_counters(_REAL_BODY)
    assert c.queries_total == 1_064_911


def test_absent_counters_are_none_not_zero():
    """Acceptance 4. A vLLM build without prefix caching reports neither
    counter. That is "this build does not measure it", which must not arrive as
    "it measured zero" — the distinction the whole feature turns on."""
    body = 'vllm:num_requests_running{model_name="ami-llm"} 0.0\n'
    assert parse_prefix_cache_counters(body) is None


def test_one_counter_without_the_other_is_also_none():
    body = 'vllm:prefix_cache_queries_total{engine="0"} 100.0\n'
    assert parse_prefix_cache_counters(body) is None


def test_multiple_engines_sum():
    body = (
        'vllm:prefix_cache_queries_total{engine="0",model_name="m"} 100.0\n'
        'vllm:prefix_cache_queries_total{engine="1",model_name="m"} 50.0\n'
        'vllm:prefix_cache_hits_total{engine="0",model_name="m"} 40.0\n'
        'vllm:prefix_cache_hits_total{engine="1",model_name="m"} 10.0\n'
    )
    c = parse_prefix_cache_counters(body)
    assert (c.queries_total, c.hits_total) == (150, 50)


@pytest.mark.parametrize(
    "base,expected",
    [
        ("http://h:8000", "http://h:8000/metrics"),
        ("http://h:8000/", "http://h:8000/metrics"),
        ("http://h:8000/v1", "http://h:8000/metrics"),
        ("http://h:8000/v1/", "http://h:8000/metrics"),
    ],
)
def test_metrics_url_is_derived_off_the_openai_base(base, expected):
    """`vllm_base_url` is configured for the OpenAI-compatible API, which may or
    may not carry the `/v1` suffix; `/metrics` hangs off the root either way."""
    assert _metrics_url(base) == expected


# ── 2. the rate is derived, and never invented ─────────────────────────────


def test_a_normal_window_gives_a_windowed_rate_not_the_lifetime_rate():
    """Acceptance 2. Lifetime is 612032/1064911 = 57.5%; this window is 50%,
    and the point is that they differ — a sampler that re-derived the lifetime
    figure forever would pass a naive test and measure nothing."""
    w = _rate_between(
        _Sample(1_064_911, 612_032, _T0),
        _Sample(1_074_911, 617_032, _T1),
    )
    assert w.status == "ok"
    assert w.rate == pytest.approx(0.5)
    assert (w.queries_delta, w.hits_delta) == (10_000, 5_000)
    assert w.rate != pytest.approx(612_032 / 1_064_911)


def test_a_counter_reset_is_a_reset_not_a_cache_collapse():
    """The 2026-08-19 measurement, as it actually happened: 1,064,911 read
    against 59,681,175 three days earlier because vLLM restarted. Δ is
    −58,616,264. Reported as `reset` with rate None — a naive delta gives a
    negative rate and a `max(0, …)` gives 0.0, which reads as the cache having
    stopped working entirely."""
    w = _rate_between(
        _Sample(59_681_175, 24_623_808, _T0),
        _Sample(1_064_911, 612_032, _T1),
    )
    assert w.status == "reset"
    assert w.rate is None
    assert w.queries_delta is None


def test_an_idle_window_is_not_a_zero_percent_hit_rate():
    """No traffic between two samples. 0/0 is not 0% — nothing was asked."""
    w = _rate_between(_Sample(100, 40, _T0), _Sample(100, 40, _T1))
    assert w.status == "no_queries_in_window"
    assert w.rate is None


def test_hits_descending_alone_is_still_a_reset():
    """Guards the check being written as `dq < 0` only. Hits can descend while
    queries appear to climb if the restart happened to land that way, and the
    resulting rate would be a plausible-looking lie rather than an obvious one."""
    w = _rate_between(_Sample(100, 90, _T0), _Sample(150, 10, _T1))
    assert w.status == "reset"
    assert w.rate is None


def test_a_full_hit_window_is_expressible():
    """Non-vacuity for the statuses above: a real 100% window must still come
    back as `ok`, not swept into one of the not-a-measurement branches."""
    w = _rate_between(_Sample(100, 40, _T0), _Sample(200, 140, _T1))
    assert w.status == "ok"
    assert w.rate == pytest.approx(1.0)


# ── 3. the tick: a row on success, a GAP on failure ────────────────────────


def _stored_rows():
    from sqlalchemy import select

    from app.db import get_session
    from app.db.models import VllmCacheSampleRow

    with get_session() as s:
        return list(s.execute(select(VllmCacheSampleRow)).scalars())


def test_the_tick_stores_the_counters_as_reported(monkeypatch):
    """Acceptance 1's storage half. The fetch half is measured against the live
    host, not here: `fetch_counters('http://192.168.20.74:8000')` returned
    (1085410, 626704) and a `curl` of /metrics in the same minute printed
    1.08541e+06 / 626704.0 — recorded in the CR because a fixture cannot prove
    a wire format."""
    from app.core import config as cfg
    from app.services import vllm_metrics

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://vllm.test:8000")
    monkeypatch.setattr(
        vllm_metrics, "fetch_counters",
        lambda base_url, **kw: CacheCounters(1_064_911, 612_032, "ami-llm"),
    )

    stats = vllm_metrics.run_vllm_cache_sample_tick()
    assert stats["status"] == "stored"

    rows = _stored_rows()
    assert len(rows) == 1
    # Raw, not normalised: no rate column exists to round into.
    assert (rows[0].queries_total, rows[0].hits_total) == (1_064_911, 612_032)
    assert rows[0].model_name == "ami-llm"


def test_an_unreachable_host_leaves_a_gap_not_a_zero_row(monkeypatch):
    """Acceptance 3. The failure mode this forbids is a row of zeros, which the
    next window reads as the cache having collapsed, and a repeat of the last
    reading, which it reads as the server having gone idle. Both are
    fabrications of a measurement that did not happen (CR040)."""
    from app.core import config as cfg
    from app.services import vllm_metrics

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://vllm.test:8000")
    monkeypatch.setattr(vllm_metrics, "fetch_counters", lambda base_url, **kw: None)

    stats = vllm_metrics.run_vllm_cache_sample_tick()
    assert stats["status"] == "gap"
    assert _stored_rows() == []


def test_no_vllm_configured_is_disabled_not_a_crash(monkeypatch):
    from app.core import config as cfg
    from app.services import vllm_metrics

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "")
    assert vllm_metrics.run_vllm_cache_sample_tick()["status"] == "disabled"
    assert _stored_rows() == []


def test_windowed_rate_needs_two_samples_and_says_so(monkeypatch):
    from app.core import config as cfg
    from app.services import vllm_metrics

    assert vllm_metrics.windowed_rate().status == "insufficient_samples"

    monkeypatch.setattr(cfg.settings, "vllm_base_url", "http://vllm.test:8000")
    monkeypatch.setattr(
        vllm_metrics, "fetch_counters",
        lambda base_url, **kw: CacheCounters(1_000, 400, "ami-llm"),
    )
    vllm_metrics.run_vllm_cache_sample_tick()
    assert vllm_metrics.windowed_rate().status == "insufficient_samples"

    monkeypatch.setattr(
        vllm_metrics, "fetch_counters",
        lambda base_url, **kw: CacheCounters(2_000, 900, "ami-llm"),
    )
    vllm_metrics.run_vllm_cache_sample_tick()
    w = vllm_metrics.windowed_rate()
    assert w.status == "ok"
    assert w.rate == pytest.approx(0.5)
