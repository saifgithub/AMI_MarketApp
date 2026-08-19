"""vLLM prefix-cache rate, sampled from the server's own `/metrics` (CR192).

WHY THIS EXISTS
---------------
CR141 wired per-call usage capture into `llm_audit`, and it works — except for
the one number CR017 §2.4 actually wanted. `usage.prompt_tokens_details` is
present in the response shape and `None` in value on our vLLM build (an upstream
V1-engine bug: issues 44961 / 16162 / 18062), so `cache_read_tokens` is NULL on
every row from the provider that serves 100% of Alpha's traffic. CR040 forbids
filling that with a zero — a fabricated "measured, no hits" is worse than an
honest unmeasured — so the per-call field stays NULL and stays correct.

The rate is not unobtainable, though. vLLM publishes it on `/metrics` as two
lifetime counters, and DEF226's claim that it was *"still unobtainable on the
provider we actually use"* was measured false LAN-direct on 2026-08-16. This
module reads them.

WHAT IT DELIBERATELY DOES NOT DO
--------------------------------
It does not compute or store a rate. The counters are cumulative since the vLLM
process started, so a stored rate can never be windowed afterwards and a stored
pair always can. Every rate here is derived at read time from two raw samples.

THE RESET, WHICH IS THE PART THAT BITES
---------------------------------------
Counters restart at zero when the vLLM process does. Measured 2026-08-19:
1,064,911 queries against 59,681,175 three days earlier — Δ = −58,616,264. A
naive `Δhits / Δqueries` across that boundary returns a negative or nonsensical
number, and nothing in it distinguishes "the server restarted" from "the cache
collapsed". Both are well-formed 200s with plausible numbers, which makes this
harder to see than an unreachable host, not easier.

So a descent is reported as a reset, never as a window. The honest read across a
restart is *no measurement* — the same answer an unreachable host gets, and for
the same CR040 reason.
"""

from __future__ import annotations

import re
import urllib.error
import urllib.request
from datetime import datetime, timezone
from typing import NamedTuple, Optional

from sqlalchemy import select

from app.core.config import settings
from app.core.logging import logger
from app.db import get_session
from app.db.models import VllmCacheSampleRow

#: vLLM publishes these as Prometheus counters. The label set (engine, model_name)
#: varies by build and by whether multiple engines are running, so the value is
#: matched positionally at end-of-line rather than by an exact label match.
_QUERIES_METRIC = "vllm:prefix_cache_queries_total"
_HITS_METRIC = "vllm:prefix_cache_hits_total"

#: Prometheus renders counters as floats (`612032.0`, `1.064911e+06`), so the
#: value is parsed as a float and then narrowed — `int("1.064911e+06")` raises.
_SAMPLE_RE = r'^{metric}(?:\{{(?P<labels>[^}}]*)\}})?\s+(?P<value>[0-9.eE+-]+)\s*$'

_MODEL_LABEL_RE = re.compile(r'model_name="([^"]*)"')


class CacheCounters(NamedTuple):
    queries_total: int
    hits_total: int
    model_name: Optional[str]


class WindowedRate(NamedTuple):
    """A rate derived from two samples, or an explicit reason there isn't one.

    `rate` is None whenever `status` is not "ok". That is not a convenience —
    it is the CR040 contract: this type cannot express "0.0 because we could not
    tell", which is the value a caller would otherwise plot as a cache collapse.
    """

    status: str  # ok | reset | insufficient_samples | no_queries_in_window
    rate: Optional[float]
    queries_delta: Optional[int]
    hits_delta: Optional[int]
    window_start: Optional[datetime]
    window_end: Optional[datetime]


def parse_prefix_cache_counters(body: str) -> Optional[CacheCounters]:
    """Pull the two counters out of a Prometheus exposition body.

    Returns None when either counter is absent — a vLLM built without prefix
    caching, or a future rename. None means "this build does not report it",
    which is a different fact from "it reported zero", and the caller must not
    be able to confuse them.
    """
    found: dict[str, float] = {}
    model_name: Optional[str] = None

    for metric in (_QUERIES_METRIC, _HITS_METRIC):
        pattern = re.compile(_SAMPLE_RE.format(metric=re.escape(metric)), re.M)
        best: Optional[float] = None
        for m in pattern.finditer(body):
            try:
                value = float(m.group("value"))
            except ValueError:
                continue
            # Multiple engines expose one line each. They are counters over the
            # same cache from the operator's point of view, so they sum.
            best = value if best is None else best + value
            labels = m.group("labels") or ""
            if model_name is None:
                label_match = _MODEL_LABEL_RE.search(labels)
                if label_match:
                    model_name = label_match.group(1)
        if best is None:
            return None
        found[metric] = best

    return CacheCounters(
        queries_total=int(found[_QUERIES_METRIC]),
        hits_total=int(found[_HITS_METRIC]),
        model_name=model_name,
    )


def _metrics_url(base_url: str) -> str:
    return base_url.rstrip("/").removesuffix("/v1") + "/metrics"


def fetch_counters(base_url: str, *, timeout: float = 8.0) -> Optional[CacheCounters]:
    """Read `/metrics` off the vLLM host. None on any failure, having logged it.

    None here means a GAP in the series — no row is written. It must never
    become a zero row or a repeat of the last one: the first would read as the
    cache collapsing and the second as the server idling, and both are
    fabrications of a measurement that did not happen (CR040).
    """
    url = _metrics_url(base_url)
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ami-vllm-metrics/1.0 (+CR192)"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 — our own LAN host
            body = r.read().decode("utf-8", "replace")
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        logger.warning("vllm_metrics_unreachable", url=url, error=str(exc))
        return None

    counters = parse_prefix_cache_counters(body)
    if counters is None:
        logger.warning(
            "vllm_metrics_no_prefix_cache_counters",
            url=url,
            detail="the endpoint answered but reports neither counter — a build "
                   "without prefix caching, or a metric rename",
        )
    return counters


def run_vllm_cache_sample_tick() -> dict[str, object]:
    """One sample. Returns a small stats dict for the tick's log line.

    Writes nothing when the host is unreachable or reports no counters — the
    gap IS the record of that (CR040). Nothing here is idempotent-by-date the
    way the NAV snapshots are, because the point is the series: two samples an
    hour apart are exactly what a window needs.
    """
    base_url = settings.vllm_base_url
    if not base_url:
        return {"status": "disabled"}

    counters = fetch_counters(base_url)
    if counters is None:
        return {"status": "gap"}

    with get_session() as s:
        s.add(
            VllmCacheSampleRow(
                sampled_at=datetime.now(timezone.utc),
                base_url=base_url,
                model_name=counters.model_name,
                queries_total=counters.queries_total,
                hits_total=counters.hits_total,
            )
        )

    return {
        "status": "stored",
        "queries_total": counters.queries_total,
        "hits_total": counters.hits_total,
        "model_name": counters.model_name,
    }


def _rate_between(
    older: VllmCacheSampleRow, newer: VllmCacheSampleRow
) -> WindowedRate:
    dq = newer.queries_total - older.queries_total
    dh = newer.hits_total - older.hits_total

    if dq < 0 or dh < 0:
        # The counters descended, so the vLLM process restarted between the two
        # samples. There is no window here — see the module docstring.
        return WindowedRate(
            status="reset", rate=None, queries_delta=None, hits_delta=None,
            window_start=older.sampled_at, window_end=newer.sampled_at,
        )
    if dq == 0:
        # No traffic in the window. A rate of 0.0 would read as "the cache
        # missed everything"; the truth is that nothing was asked.
        return WindowedRate(
            status="no_queries_in_window", rate=None, queries_delta=0, hits_delta=dh,
            window_start=older.sampled_at, window_end=newer.sampled_at,
        )
    return WindowedRate(
        status="ok", rate=dh / dq, queries_delta=dq, hits_delta=dh,
        window_start=older.sampled_at, window_end=newer.sampled_at,
    )


def windowed_rate(limit: int = 2) -> WindowedRate:
    """The prefix-cache hit rate over the most recent window.

    `limit` is how many recent samples to consider; the window is the oldest and
    newest of them. Defaults to the last two — the tightest honest window.
    """
    with get_session() as s:
        rows = list(
            s.execute(
                select(VllmCacheSampleRow)
                .order_by(VllmCacheSampleRow.sampled_at.desc())
                .limit(max(2, limit))
            ).scalars()
        )

    if len(rows) < 2:
        return WindowedRate(
            status="insufficient_samples", rate=None, queries_delta=None,
            hits_delta=None, window_start=None, window_end=None,
        )

    return _rate_between(rows[-1], rows[0])
