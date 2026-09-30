"""CR247 Phase 6 (D20) — the standing prompt-evolution digest.

The periodic measurement half of the prompt-evolution loop: what
`weekly_room_retro.py` (CR157) does for verdict quality against forward
returns, this digest does for PROMPT quality against its own aggregates —
per-agent envelope parse rates, truncation vs `_AGENT_MAX_TOKENS`,
stance/conviction distributions, the GAPS want-list, a citation-grounding
proxy, and verdict-outcome ledger movement — computed over a trailing
window (default 7 days) and compared against the previous digest's
baselines.

Builds ON the existing loop, never beside it (SPEC Phase 6): GAPS and
envelope tallies are imported from `scripts.aggregate_data_gaps`
(CR219 R53/R57), final-stance extraction and the outage/fail-safe verdict
vocabulary from `scripts.weekly_room_retro` / `app.services.room_runner`,
and the outcome-ledger movement reads `app.services.verdict_outcomes` —
the exact module `scripts/score_verdict_outcomes.py` is the CLI for. The
digest's read-only contract forbids calling `score_pending` (it flips
pending rows to scored); it reuses the same status/reason vocabulary and
the read-only `aggregates()` instead. There is no second pipeline.

Serving-model keying (SPEC: "keyed to serving-model identity, never the
`ami-llm` alias"): the digest fetches the vLLM `/v1/models` root at run
time (5s timeout, the `backtest_cutoff_probe.py` precedent — the alias was
REUSED across the CR211 swap, so the requested id cannot be trusted) and
stamps every digest with what the server says it is actually serving.
CAVEAT, load-bearing: `llm_audit` rows carry `provider` only (vllm /
kimi / glm / …), never a model id — so every per-row aggregate is keyed
by provider, and the serving identity is the digest-level stamp that says
which model those provider rows actually were. A baseline recorded under
a different identity is flagged as a cross-model comparison, not silently
diffed. When the fetch fails the header says so loudly and names which
keying degraded to provider-only (CR040).

An anomaly never produces an action. A flag appends a dated PROPOSAL
block (to the report and to `proposals.md` in --out) written in the shape
of a CR draft: the anomaly, a candidate prompt-change HYPOTHESIS, and a
pre-registered measurement plan (which harness benchmark, which metric,
what passes). The machine measures and proposes; the Architect mints CRs;
nothing here edits personas, flags, or config — there is no write path to
any of them, and the unit tests assert both the import surface and the
SQL stream prove it.

Cadence: a `--days 7` run prints "weekly digest"; a run with
`--days >= CONCLUSION_MIN_DAYS` or `>= CONCLUSION_MIN_CONVENES` convenes
in the window prints "monthly conclusion" and tallies the window's
proposal blocks into a per-kind trend verdict (SPEC: concludes monthly or
per-N-convenes, the CR197 statistical-power constraint).

Thresholds are the module constants below, documented with their reason:
small windows on Alpha volumes are noisy, so every rate flag is gated on
`MIN_BASELINE_N` observations on BOTH sides (the weekly retro's
small-n-honesty convention).

READ-ONLY on product tables by contract: pure SELECT + the three files
this digest owns under --out (`digest_<stamp>.md`, `baseline.json`,
`proposals.md`). An empty window is a legitimate state: a loud
"nothing measured", exit 0, and the baseline is NOT overwritten with
empty aggregates.

Scheduling — the CR157 pattern, melehost user crontab (the repo does not
carry it; melehost ops installs it, same as score_verdict_outcomes'
docstring states). Suggested line, weekly an hour before the retro so the
digest's proposals ride the same review:

    30 8 * * 6 docker exec ami_api_alpha python -m scripts.prompt_evolution_digest \
        --out /backtest_results/prompt_evolution \
        >> /home/saiful/ami_trade/reports/prompt_evolution_digest.log 2>&1

Usage (inside the alpha container, where PYTHONPATH=/app resolves app.*):
    python -m scripts.prompt_evolution_digest --out /backtest_results/prompt_evolution
    python -m scripts.prompt_evolution_digest --days 30   # monthly conclusion
    python -m scripts.prompt_evolution_digest --dry-run   # print, write nothing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from sqlalchemy import select

from app.core.config import settings
from app.db import get_session
from app.db.models import LLMAuditRow, RoomRunRow, VerdictOutcomeRow
from app.schemas.agents import AgentId
from app.services import verdict_outcomes as vo
from app.services.room_prompts import _DEFAULT_AGENT_MAX_TOKENS, max_tokens_for
from app.services.room_runner import (
    is_llm_outage_verdict,
    parse_stance_envelope,
    room_verdict_is_incomplete,
)
from scripts.aggregate_data_gaps import (
    select_scoreable_runs,
    tally_data_gaps,
    tally_envelope_emission,
)
from scripts.weekly_room_retro import final_stances

# ── Thresholds (SPEC Phase 6: "thresholds as module constants, documented") ──
# A weekly window on Alpha volumes is tens of convenes; below MIN_BASELINE_N
# observations on BOTH sides of a comparison the noise band exceeds every
# threshold below, so the flag is suppressed rather than printed at a width
# that means nothing (weekly_room_retro's Wilson-CI small-n honesty, applied
# as a gate).
MIN_BASELINE_N = 20
# Parse-rate drop flag: a real prompt regression moves an agent's stance
# extraction by more than a few points; 5pp is above the run-to-run wobble
# measured on the DEF147/CR247 corpora while still catching a drift early.
PARSE_RATE_DROP_PP = 5.0
# The truncation heuristic has no finish_reason (llm_audit does not capture
# it — same documented limitation as scoring.py's SUSPECT_TRUNCATION), so a
# single suspect is weak evidence; a DOUBLING of the suspect share is the
# first run-to-run signal that is unlikely to be one long honest answer.
TRUNCATION_SUSPECT_MULTIPLIER = 2.0
# Stance/conviction/verdict-action category share moves >10pp between two
# windows gated at n>=20 imply a prompt- or population-level change, not
# sampling noise on a quiet week.
DISTRIBUTION_SHIFT_PP = 10.0
# The PM JSON envelope is the binding verdict surface (DEF058/DEF236);
# its parse rate gets the same drop bar as the prose envelope.
PM_JSON_PARSE_DROP_PP = 5.0
# A GAPS bucket entering the top-N asks (or doubling its ask count) is the
# want-list movement signal the SPEC asks the digest to surface — it routes
# to a data-sourcing CR (CR221 line), never a prompt change.
GAPS_TOP_N = 3
# Conclusion cadence (SPEC: monthly or per-N-convenes — the N is the CR197
# statistical-power constraint, not a calendar convenience).
CONCLUSION_MIN_DAYS = 30
CONCLUSION_MIN_CONVENES = 100
# Pre-registered pass bar every proposal's measurement plan uses: the metric
# recovers to within this of the recorded baseline, with no regression on
# the paired guard metrics.
PROPOSAL_PASS_RECOVERY_PP = 2.0
IDENTITY_FETCH_TIMEOUT_S = 5.0

# llm_audit.flow values the Room owns (room / room_pm / room_pm_reformat /
# room_risk_officer). Everything else (one_on_one, concierge, translate,
# replays) is a different surface and would contaminate Room aggregates.
ROOM_FLOW_PREFIX = "room"
REPLAY_FLOW = "admin_prompt_replay"

PM_AGENT = AgentId.PORTFOLIO_MANAGER.value
STANCE_CATEGORIES = ("for", "against", "neutral")
CONVICTION_CATEGORIES = ("low", "medium", "high")

BASELINE_FILENAME = "baseline.json"
PROPOSALS_FILENAME = "proposals.md"
BASELINE_SCHEMA = "prompt-evolution-baseline/v1"

# Spec-pinned numeric token shape (anchoring.py:61 — prices/percents/ratios).
# Used by the citation-grounding proxy: the share of an agent's response
# numbers that appear in its own system prompt (the fact sheet for the four
# analysts; the sheet plus the upstream transcript for downstream desks).
_NUMBER_RE = re.compile(r"\$?\d[\d,.]*%?x?")


def _as_utc(dt: datetime | None) -> datetime | None:
    """Naive stamps (sqlite storage convention) are UTC — the helper
    weekly_room_retro.py and verdict_outcomes.py each already carry."""
    if dt is None:
        return None
    return dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt.astimezone(UTC)


# ── Serving-model identity ───────────────────────────────────────────────────


def fetch_serving_identity(base_url: str | None) -> dict[str, Any]:
    """Ask the serving vLLM what it actually is (never the `ami-llm` alias —
    backtest_cutoff_probe.py:210 documents why the requested id cannot be
    trusted). Any failure degrades loudly in the returned block; the caller
    stamps it into the digest header and names which keying is provider-only
    this run (CR040)."""
    if not base_url:
        return {
            "identity": None,
            "fetched_at": datetime.now(UTC).isoformat(),
            "source": None,
            "error": "no vLLM base url configured — keying is provider-only",
        }
    url = base_url.rstrip("/") + "/v1/models"
    try:
        root = httpx.get(url, timeout=IDENTITY_FETCH_TIMEOUT_S).json()["data"][0]
        identity = root.get("root") or root.get("id")
        if not identity:
            raise ValueError("/v1/models data[0] carries neither root nor id")
        return {
            "identity": identity,
            "fetched_at": datetime.now(UTC).isoformat(),
            "source": url,
            "error": None,
        }
    except Exception as exc:  # noqa: BLE001 — an unidentifiable server is reportable, not fatal
        return {
            "identity": None,
            "fetched_at": datetime.now(UTC).isoformat(),
            "source": url,
            "error": f"{type(exc).__name__}: {exc}",
        }


# ── Truncation ceiling (the harness heuristic, per-agent) ────────────────────


def _provider_floor(provider: str) -> int:
    """The CR211 decode-budget floor the gateway applies AFTER the Room's
    per-agent cap (llm_gateway.py:696 — effective = max(cap, floor)). The
    floor that silently rewrites every caller's max_tokens has to be part of
    the ceiling the truncation heuristic compares against, or a raised floor
    would manufacture suspect-free weeks."""
    return {
        "vllm": settings.vllm_max_tokens_floor,
        "kimi": settings.kimi_max_tokens_floor,
        "glm": settings.glm_max_tokens_floor,
    }.get(provider, 0) or 0


def effective_ceiling(agent_id: str, provider: str) -> int:
    try:
        cap = max_tokens_for(AgentId(agent_id))
    except ValueError:
        cap = _DEFAULT_AGENT_MAX_TOKENS
    return max(cap, _provider_floor(provider))


def is_truncation_suspect(agent_id: str, provider: str, output_tokens: int | None) -> bool:
    """HEURISTIC, same documented limitation as scoring.py's
    SUSPECT_TRUNCATION: llm_audit has no finish_reason column, so a natural
    long answer that lands at the cap false-positives. `>= ceiling` is the
    harness's own test; the suspect count, never a verdict."""
    if output_tokens is None:
        return False
    return output_tokens >= effective_ceiling(agent_id, provider)


# ── PM JSON envelope (mirror of the harness strict parse) ────────────────────


def pm_json_action(text: str | None) -> str | None:
    """Strict PM-verdict parse: first balanced {...} span, json.loads, an
    "action" key. Mirrors scoring.py's extract_decision(json_key="action")
    exactly — the harness lives under docs/tools and is not importable from
    backend/scripts, so this is a deliberate mirror, not a fork of scoring
    LOGIC; the tolerant production parser (_parse_pm_verdict) is unusable
    here because it fails SAFE to PASS and would report a 100% parse rate."""
    if not text:
        return None
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                try:
                    value = json.loads(text[start:i + 1]).get("action")
                except json.JSONDecodeError:
                    return None
                return str(value) if value is not None else None
    return None


# ── Aggregation: llm_audit room rows ─────────────────────────────────────────


@dataclass
class AgentLLMStats:
    n_calls: int = 0
    n_empty: int = 0                # null/blank response_text — a real provider state, counted apart
    n_parsed: int = 0               # stance extracted from response_text
    stances: Counter = field(default_factory=Counter)
    convictions: Counter = field(default_factory=Counter)
    n_truncation_suspects: int = 0
    suspect_examples: list = field(default_factory=list)
    output_tokens: list = field(default_factory=list)
    providers: Counter = field(default_factory=Counter)
    prompt_versions: Counter = field(default_factory=Counter)
    # PM-only
    n_pm_draws: int = 0
    n_pm_json_ok: int = 0
    pm_actions: Counter = field(default_factory=Counter)
    constraint_status: Counter = field(default_factory=Counter)
    # citation-grounding proxy
    n_response_numbers: int = 0
    n_grounded_numbers: int = 0

    def parse_rate(self) -> float | None:
        return self.n_parsed / self.n_calls if self.n_calls else None

    def truncation_suspect_rate(self) -> float | None:
        return self.n_truncation_suspects / self.n_calls if self.n_calls else None

    def grounding_rate(self) -> float | None:
        return self.n_grounded_numbers / self.n_response_numbers if self.n_response_numbers else None

    def pm_json_parse_rate(self) -> float | None:
        return self.n_pm_json_ok / self.n_pm_draws if self.n_pm_draws else None


def _numeric_tokens(text: str) -> set[str]:
    return set(_NUMBER_RE.findall(re.sub(r"\s+", " ", text)))


def aggregate_llm_rows(rows: list[LLMAuditRow]) -> dict[str, AgentLLMStats]:
    """Per-agent aggregates over the window's Room llm_audit rows. Parse
    rate is over ALL calls in scope (an empty response is a parse failure
    AND its own counted state — never silently excluded from the
    denominator); stance/conviction distributions are over parsed rows."""
    out: dict[str, AgentLLMStats] = {}
    for row in rows:
        agent = row.agent_id
        if not agent:
            continue
        st = out.setdefault(agent, AgentLLMStats())
        st.n_calls += 1
        st.providers[row.provider or "?"] += 1
        st.prompt_versions[row.prompt_version or "unversioned"] += 1
        if row.output_tokens is not None:
            st.output_tokens.append(row.output_tokens)
        if is_truncation_suspect(agent, row.provider, row.output_tokens):
            st.n_truncation_suspects += 1
            if len(st.suspect_examples) < 3:
                st.suspect_examples.append({
                    "output_tokens": row.output_tokens,
                    "ceiling": effective_ceiling(agent, row.provider),
                    "provider": row.provider,
                })
        text = row.response_text
        if not (text or "").strip():
            st.n_empty += 1
        else:
            _, env = parse_stance_envelope(text)
            if env.stance is not None:
                st.n_parsed += 1
                st.stances[env.stance] += 1
            if env.conviction is not None:
                st.convictions[env.conviction] += 1
            numbers = _numeric_tokens(text)
            st.n_response_numbers += len(numbers)
            haystack = re.sub(r"\s+", " ", row.system_prompt or "")
            st.n_grounded_numbers += sum(1 for t in numbers if t in haystack)
        if agent == PM_AGENT:
            st.n_pm_draws += 1
            action = pm_json_action(text)
            if action is None:
                st.pm_actions["UNPARSEABLE"] += 1
            else:
                st.n_pm_json_ok += 1
                st.pm_actions[action] += 1
            if row.constraint_status:
                st.constraint_status[row.constraint_status] += 1
    return out


# ── Aggregation: room_runs ───────────────────────────────────────────────────


@dataclass
class RunsStats:
    n_runs: int = 0
    status: Counter = field(default_factory=Counter)
    actions: Counter = field(default_factory=Counter)
    n_outage_failsafe: int = 0      # DEF336 — uptime, not judgement; excluded from the distribution
    n_no_verdict_incomplete: int = 0  # CR219 R51 thin-Room discard
    scripted_runs: int = 0
    scripted_agents: Counter = field(default_factory=Counter)
    n_retried: int = 0
    final_stances: dict = field(default_factory=dict)   # agent -> Counter of final stated stances
    final_convictions: dict = field(default_factory=dict)

    def scripted_share(self) -> float | None:
        return self.scripted_runs / self.n_runs if self.n_runs else None


def aggregate_runs(runs: list[RoomRunRow]) -> RunsStats:
    """Verdict action distribution, scripted-fallback accounting, and
    per-convene final stance/conviction distributions (one observation per
    agent per convene — the scoreboard unit, via weekly_room_retro's own
    final_stances, imported not copied)."""
    out = RunsStats(n_runs=len(runs))
    for run in runs:
        out.status[run.status or "?"] += 1
        if run.retry_count:
            out.n_retried += 1
        verdict = run.verdict
        if run.status == "completed" and isinstance(verdict, dict):
            if is_llm_outage_verdict(verdict):
                out.n_outage_failsafe += 1
            else:
                out.actions[verdict.get("action") or "?"] += 1
                if room_verdict_is_incomplete(verdict):
                    out.n_no_verdict_incomplete += 1
                scripted = verdict.get("scripted_agents") or []
                if verdict.get("scripted_turns"):
                    out.scripted_runs += 1
                for a in scripted:
                    out.scripted_agents[a] += 1
        stances = final_stances(run.transcript)
        for agent, st in stances.items():
            stance = st.get("stance")
            if stance is not None:
                out.final_stances.setdefault(agent, Counter())[stance] += 1
            conviction = st.get("conviction")
            if conviction is not None:
                out.final_convictions.setdefault(agent, Counter())[conviction] += 1
    return out


# ── Aggregation: verdict_outcome ledger movement (read-only) ─────────────────


def outcome_movement(rows: list[VerdictOutcomeRow], cutoff: datetime) -> dict[str, Any]:
    """Scored-set movement over the window, in score_verdict_outcomes' own
    vocabulary (imported from app.services.verdict_outcomes — the module the
    CLI is a thin wrapper over). score_pending itself is never called: it
    MUTATES (pending -> scored), which this digest's read-only contract
    forbids; the daily scorer remains the only writer. All-time floor shape
    comes from vo.aggregates() (direct reuse), window movement from
    scored_at filtering."""
    decided = [r for r in rows if _as_utc(r.scored_at) is not None and _as_utc(r.scored_at) >= cutoff]
    scored = [r for r in decided if r.status == vo.STATUS_SCORED]
    by_action: dict[str, list[float]] = {}
    for r in scored:
        if r.forward_return is not None:
            by_action.setdefault(str(r.verdict_action), []).append(float(r.forward_return))
    return {
        "pending_total": sum(1 for r in rows if r.status == vo.STATUS_PENDING),
        "window_decided": len(decided),
        "window_scored": len(scored),
        "window_unscorable_by_reason": dict(Counter(
            str(r.exclusion_reason) for r in decided if r.status == vo.STATUS_UNSCORABLE
        )),
        "window_scored_hit_rate": {
            action: {
                "n": len(values),
                "hit_rate": (sum(1 for v in values if v > 0) / len(values)) if values else None,
                "mean_forward_return": (sum(values) / len(values)) if values else None,
            }
            for action, values in sorted(by_action.items())
        },
        "vocabulary": {
            "scored": vo.STATUS_SCORED,
            "pending": vo.STATUS_PENDING,
            "unscorable": vo.STATUS_UNSCORABLE,
        },
    }


# ── Baseline compare ─────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Flag:
    kind: str
    subject: str
    baseline: Any
    current: Any
    detail: str


def _shares(counter: dict, categories) -> dict[str, float]:
    total = sum(counter.get(c, 0) for c in categories)
    return {c: (counter.get(c, 0) / total if total else 0.0) for c in categories}


def compare_to_baseline(current: dict, baseline: dict | None) -> list[Flag]:
    """Every delta against the stored baseline, flagged when it crosses a
    module-constant threshold on BOTH sides of n >= MIN_BASELINE_N. A
    serving-identity mismatch is flagged FIRST and marks the comparison
    cross-model — the metric flags still print (a human may want them) but
    the report says they were measured across a model generation."""
    if baseline is None:
        return []
    flags: list[Flag] = []
    cur_aggs = current["aggregates"]
    base_aggs = baseline.get("aggregates") or {}

    base_id = (baseline.get("serving_identity") or {}).get("identity")
    cur_id = (current.get("serving_identity") or {}).get("identity")
    if base_id and cur_id and base_id != cur_id:
        flags.append(Flag(
            kind="MODEL_IDENTITY_MISMATCH",
            subject="serving model",
            baseline=base_id,
            current=cur_id,
            detail="the serving model changed between baseline and this window — "
                   "every delta below is a CROSS-MODEL comparison; re-baseline "
                   "before reading any metric flag as a prompt regression",
        ))

    base_agents = base_aggs.get("per_agent_llm") or {}
    for agent, cur in (cur_aggs.get("per_agent_llm") or {}).items():
        base = base_agents.get(agent)
        if not base or base.get("n_calls", 0) < MIN_BASELINE_N or cur.get("n_calls", 0) < MIN_BASELINE_N:
            continue
        base_rate = base.get("parse_rate")
        cur_rate = cur.get("parse_rate")
        if base_rate is not None and cur_rate is not None and (
                (base_rate - cur_rate) * 100) > PARSE_RATE_DROP_PP:
            flags.append(Flag(
                kind="PARSE_RATE_DROP", subject=agent,
                baseline=round(base_rate * 100, 1), current=round(cur_rate * 100, 1),
                detail=f"stance parse rate fell {100 * (base_rate - cur_rate):.1f}pp "
                       f"(>{PARSE_RATE_DROP_PP}pp threshold, n>={MIN_BASELINE_N} both sides)",
            ))
        base_tr = base.get("truncation_suspect_rate") or 0.0
        cur_tr = cur.get("truncation_suspect_rate") or 0.0
        # Doubling bar. From a ZERO baseline any binding is new information,
        # but one suspect is the heuristic's noise floor — require 2+ before
        # firing (n>=MIN_BASELINE_N already gates the denominator).
        base_zero = base.get("n_truncation_suspects", 0) == 0
        cur_n = cur.get("n_truncation_suspects", 0)
        if cur_tr > 0 and cur_tr >= TRUNCATION_SUSPECT_MULTIPLIER * base_tr and (
                not base_zero or cur_n >= 2):
            ratio = f"{cur_tr / base_tr:.1f}x baseline" if base_tr > 0 else (
                f"new this window (baseline 0 suspects, now {cur_n})")
            flags.append(Flag(
                kind="TRUNCATION_SUSPECT_SURGE", subject=agent,
                baseline=round(base_tr * 100, 1), current=round(cur_tr * 100, 1),
                detail=f"truncation-suspect share {ratio} "
                       f"(doubling bar) — heuristic only: no finish_reason in "
                       f"llm_audit, a natural long answer at the cap false-positives",
            ))

    # Stance/conviction distributions are compared at CONVENE level (the
    # scoreboard unit — one final stated position per agent per convene via
    # weekly_room_retro.final_stances), not per call: the PM's self-
    # consistency fan-out would otherwise weight the PM's own week by how
    # many draws it happened to take.
    base_conv = base_aggs.get("convenes") or 0
    cur_conv = cur_aggs.get("convenes") or 0
    if base_conv >= MIN_BASELINE_N and cur_conv >= MIN_BASELINE_N:
        agents = (set(base_aggs.get("final_stances") or {})
                  | set(cur_aggs.get("final_stances") or {})
                  | set(base_aggs.get("final_convictions") or {})
                  | set(cur_aggs.get("final_convictions") or {}))
        for agent in sorted(agents):
            base_c = (base_aggs.get("final_stances") or {}).get(agent) or {}
            cur_c = (cur_aggs.get("final_stances") or {}).get(agent) or {}
            for cat in STANCE_CATEGORIES:
                bs = _shares(base_c, STANCE_CATEGORIES)[cat]
                cs = _shares(cur_c, STANCE_CATEGORIES)[cat]
                if abs(cs - bs) * 100 > DISTRIBUTION_SHIFT_PP:
                    flags.append(Flag(
                        kind="STANCE_DISTRIBUTION_SHIFT", subject=f"{agent}:{cat}",
                        baseline=round(bs * 100, 1), current=round(cs * 100, 1),
                        detail=f"final-stance share for '{cat}' moved "
                               f"{100 * (cs - bs):+.1f}pp "
                               f"(>{DISTRIBUTION_SHIFT_PP}pp) — check mandate-mix "
                               f"drift before blaming the prompt",
                    ))
            base_v = (base_aggs.get("final_convictions") or {}).get(agent) or {}
            cur_v = (cur_aggs.get("final_convictions") or {}).get(agent) or {}
            for cat in CONVICTION_CATEGORIES:
                bs = _shares(base_v, CONVICTION_CATEGORIES)[cat]
                cs = _shares(cur_v, CONVICTION_CATEGORIES)[cat]
                if abs(cs - bs) * 100 > DISTRIBUTION_SHIFT_PP:
                    flags.append(Flag(
                        kind="CONVICTION_DISTRIBUTION_SHIFT",
                        subject=f"{agent}:{cat}",
                        baseline=round(bs * 100, 1), current=round(cs * 100, 1),
                        detail=f"final stated conviction share for '{cat}' moved "
                               f"{100 * (cs - bs):+.1f}pp "
                               f"(>{DISTRIBUTION_SHIFT_PP}pp)",
                    ))

    base_pm = base_agents.get(PM_AGENT) or {}
    cur_pm = (cur_aggs.get("per_agent_llm") or {}).get(PM_AGENT) or {}
    if base_pm.get("n_pm_draws", 0) >= MIN_BASELINE_N and cur_pm.get("n_pm_draws", 0) >= MIN_BASELINE_N:
        base_pm_rate = base_pm.get("pm_json_parse_rate")
        cur_pm_rate = cur_pm.get("pm_json_parse_rate")
        if base_pm_rate is not None and cur_pm_rate is not None and (
                (base_pm_rate - cur_pm_rate) * 100) > PM_JSON_PARSE_DROP_PP:
            flags.append(Flag(
                kind="PM_JSON_PARSE_DROP", subject=PM_AGENT,
                baseline=round(base_pm_rate * 100, 1), current=round(cur_pm_rate * 100, 1),
                detail=f"PM JSON-envelope parse rate fell "
                       f"{100 * (base_pm_rate - cur_pm_rate):.1f}pp "
                       f"(>{PM_JSON_PARSE_DROP_PP}pp) — check constraint_status "
                       f"mix and narration-ask length vs the 1700 budget (DEF236)",
            ))

    if base_conv >= MIN_BASELINE_N and cur_conv >= MIN_BASELINE_N:
        base_actions = base_aggs.get("verdict_actions") or {}
        cur_actions = cur_aggs.get("verdict_actions") or {}
        cats = sorted(set(base_actions) | set(cur_actions))
        base_total = sum(base_actions.values()) or 1
        cur_total = sum(cur_actions.values()) or 1
        for cat in cats:
            bs = base_actions.get(cat, 0) / base_total
            cs = cur_actions.get(cat, 0) / cur_total
            if abs(cs - bs) * 100 > DISTRIBUTION_SHIFT_PP:
                flags.append(Flag(
                    kind="VERDICT_ACTION_SHIFT", subject=cat,
                    baseline=round(bs * 100, 1), current=round(cs * 100, 1),
                    detail=f"verdict action share '{cat}' moved {100 * (cs - bs):+.1f}pp "
                           f"(>{DISTRIBUTION_SHIFT_PP}pp) over {cur_conv} convenes",
                ))
        base_scripted = base_aggs.get("scripted_share")
        cur_scripted = cur_aggs.get("scripted_share")
        # Doubling bar, with the same zero-baseline floor as the truncation
        # bar: one scripted convene from a clean baseline is not a surge.
        if (cur_scripted and cur_scripted > 0 and base_scripted is not None
                and cur_scripted >= TRUNCATION_SUSPECT_MULTIPLIER * base_scripted
                and (base_scripted > 0 or cur_aggs.get("scripted_runs", 0) >= 2)):
            flags.append(Flag(
                kind="SCRIPTED_TURNS_SURGE", subject="room_runs",
                baseline=round(base_scripted * 100, 1),
                current=round(cur_scripted * 100, 1),
                detail="scripted-fallback share of convenes doubled — a provider/"
                       "timeout degradation signal, NOT a prompt question; route to "
                       "infra review, never a persona change",
            ))

    base_gaps = base_aggs.get("gaps_buckets") or {}
    cur_gaps = cur_aggs.get("gaps_buckets") or {}
    base_top = {b for b, _ in sorted(base_gaps.items(), key=lambda kv: -kv[1])[:GAPS_TOP_N]}
    cur_top = {b for b, _ in sorted(cur_gaps.items(), key=lambda kv: -kv[1])[:GAPS_TOP_N]}
    for bucket in sorted(cur_top - base_top):
        flags.append(Flag(
            kind="GAPS_WANTLIST_MOVEMENT", subject=bucket,
            baseline=base_gaps.get(bucket, 0), current=cur_gaps.get(bucket, 0),
            detail=f"GAPS bucket entered the top-{GAPS_TOP_N} want-list asks — a "
                   f"data-sourcing CR candidate (CR221 line), never a prompt change",
        ))
    for bucket in sorted(set(base_gaps) & set(cur_gaps)):
        if cur_gaps[bucket] >= TRUNCATION_SUSPECT_MULTIPLIER * base_gaps[bucket] and cur_gaps[bucket] >= 2:
            flags.append(Flag(
                kind="GAPS_WANTLIST_SURGE", subject=bucket,
                baseline=base_gaps[bucket], current=cur_gaps[bucket],
                detail="GAPS bucket ask count doubled week-over-week — analysts "
                       "keep lacking this field; route to the data roadmap",
            ))
    return flags


# ── Proposals: the machine proposes, governance disposes ─────────────────────


def _proposal_plan(kind: str) -> tuple[str, str, str]:
    """(candidate prompt-change hypothesis, benchmark, pass criterion) per
    flag kind. Every hypothesis is a HYPOTHESIS — the Architect mints the CR
    and decides; nothing here edits anything."""
    bench = "backend/scripts/pm_debate_ablation.py (CR247 harness) before/after on the serving model"
    guard = (
        f"the flagged metric recovers to within "
        f"{PROPOSAL_PASS_RECOVERY_PP}pp of the recorded baseline AND the paired "
        f"guard metrics do not regress (truncation-suspect share, stance "
        f"distribution) over a pre-registered convene count (CR197 power rule)"
    )
    if kind == "PARSE_RATE_DROP":
        return (
            "the agent's envelope instruction is being missed or its tail is "
            "being clipped: restate the STANCE envelope slot (lead position) "
            "and re-check the _LENGTH_GUIDE/_AGENT_MAX_TOKENS pairing "
            "(DEF125/DEF236) before any wording change", bench, guard)
    if kind == "TRUNCATION_SUSPECT_SURGE":
        return (
            "the ask outgrew the decode budget: re-derive _AGENT_MAX_TOKENS "
            "for this agent from the measured worst case (CR179's rule, 1.5x "
            "on a censored observation) or shorten the ask (_LENGTH_GUIDE); "
            "never raise the cap without the length guide moving with it",
            bench, guard)
    if kind == "STANCE_DISTRIBUTION_SHIFT":
        return (
            "the agent's position moved before its prompt did: first exclude "
            "mandate-mix drift (compare the window's mandate horizon/risk "
            "distribution against baseline), then audit the scoreboard/"
            "overlay inputs feeding this agent; a wording change is the LAST "
            "hypothesis, not the first", bench, guard)
    if kind == "CONVICTION_DISTRIBUTION_SHIFT":
        return (
            "conviction semantics may have drifted from the role definitions "
            "(SPEC item 2.2): re-read the scoreboard column label for this "
            "role family before touching text; measure with the conviction "
            "audit tooling (scoring.conviction_audit) on a fresh corpus", bench, guard)
    if kind == "PM_JSON_PARSE_DROP":
        return (
            "the PM envelope is degrading: check the constraint_status mix "
            "(grammar enforcement on the wire?), the narration ask length vs "
            "the 1700 budget (DEF236), and the recovery-reformat path's share "
            "of draws; the tolerant parser must remain the untouched consumer",
            bench, guard)
    if kind == "VERDICT_ACTION_SHIFT":
        return (
            "the room's collective decision moved: exclude ticker mix and "
            "mandate-mix drift first, then run the CR197 replay arm on a "
            "fixed convene corpus to separate prompt shape from market regime",
            bench, guard)
    if kind == "SCRIPTED_TURNS_SURGE":
        return (
            "NOT a prompt hypothesis: scripted fallback is a provider/"
            "timeout-degradation signal — investigate the gateway transport "
            "budgets (vllm_request_timeout_s vs room_agent_timeout_s, "
            "DEF389/DEF392) and provider health", "infra review, not a prompt benchmark",
            "the scripted share returns to the baseline band and the "
            "outage fail-safe count stays zero",
        )
    if kind in ("GAPS_WANTLIST_MOVEMENT", "GAPS_WANTLIST_SURGE"):
        return (
            "NOT a prompt hypothesis: the analysts keep lacking this field — "
            "a data-sourcing CR candidate on the CR221 roadmap; the persona "
            "sentence naming the field ships only when the field is live",
            "re-run scripts/aggregate_data_gaps.py after the field lands; "
            "want-list share for the bucket must fall, not move",
            f"the bucket leaves the top-{GAPS_TOP_N} asks over the next window",
        )
    if kind == "MODEL_IDENTITY_MISMATCH":
        return (
            "the serving model changed: treat this window as a NEW baseline "
            "epoch (CR247 standing rule — CR197's numbers do not transfer "
            "across models), re-run the Phase 0 baselines on the new model "
            "before any prompt comparison is read",
            "CR197 replay on the new serving model (fresh baseline)", guard)
    return ("no templated hypothesis for this flag kind — Architect decides",
            bench, guard)


def build_proposal_blocks(flags: list[Flag], *, stamp: str, window_days: int,
                          window_start: str, cadence: str) -> list[str]:
    """One dated block per flag, in the shape of a CR draft for the
    Architect to mint. Contains exactly: the anomaly, the candidate change
    hypothesis, the pre-registered measurement plan. Contains NO action."""
    blocks = []
    for i, fl in enumerate(flags, 1):
        hypothesis, benchmark, passes = _proposal_plan(fl.kind)
        blocks.append("\n".join([
            f"### PED-{stamp}-{i} — {cadence} — {fl.kind}: {fl.subject}",
            f"- raised: {stamp} (window {window_start} .. {stamp}, {window_days}d)",
            f"- anomaly: {fl.subject} — baseline {fl.baseline} → current {fl.current}. {fl.detail}",
            f"- candidate prompt change (HYPOTHESIS, not a decision): {hypothesis}",
            "- pre-registered measurement plan:",
            f"  - benchmark: {benchmark}",
            f"  - metric: {fl.subject} ({fl.kind})",
            f"  - passes when: {passes}",
            "- governance: PROPOSAL ONLY. The Architect mints the CR; nothing "
            "in this digest edits personas, flags, or config.",
        ]))
    return blocks


def conclusion_trend(proposals_path: Path, window_start: str) -> dict[str, int]:
    """Monthly-conclusion tally: proposal blocks raised within the window,
    counted by flag kind. The proposals file is the digest's own memory of
    what the weekly runs flagged; two occurrences of one kind inside the
    window is the RECURRING bar printed by the conclusion."""
    counts: Counter = Counter()
    if not proposals_path.exists():
        return {}
    current_kind: str | None = None
    for line in proposals_path.read_text().splitlines():
        if line.startswith("### PED-"):
            parts = line.split("—")
            current_kind = parts[2].split(":")[0].strip() if len(parts) >= 3 else "?"
        elif line.startswith("- raised:") and current_kind:
            date = line.split(":", 1)[1].strip().split(" ")[0]
            if date >= window_start:
                counts[current_kind] += 1
            current_kind = None
    return dict(counts)


# ── Baseline serialization ───────────────────────────────────────────────────


def build_baseline(*, stamp: str, window_days: int, window_start: str,
                   serving_identity: dict, aggregates: dict) -> dict:
    return {
        "schema": BASELINE_SCHEMA,
        "generated_at": stamp,
        "window_days": window_days,
        "window_start": window_start,
        "serving_identity": serving_identity,
        "aggregates": aggregates,
    }


def load_baseline(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError:
        return None
    return data if data.get("schema") == BASELINE_SCHEMA else None


def current_aggregates(per_agent: dict[str, AgentLLMStats], runs: RunsStats,
                       gaps_buckets: dict, gaps_emission: dict,
                       outcome: dict) -> dict:
    """The JSON-serializable snapshot this digest stores as the next
    baseline and diffs against the last one."""
    per_agent_json = {}
    for agent, st in sorted(per_agent.items()):
        per_agent_json[agent] = {
            "n_calls": st.n_calls,
            "n_empty": st.n_empty,
            "n_parsed": st.n_parsed,
            "parse_rate": st.parse_rate(),
            "stance_shares": _shares(dict(st.stances), STANCE_CATEGORIES),
            "conviction_shares": _shares(dict(st.convictions), CONVICTION_CATEGORIES),
            "n_truncation_suspects": st.n_truncation_suspects,
            "truncation_suspect_rate": st.truncation_suspect_rate(),
            "mean_output_tokens": (
                sum(st.output_tokens) / len(st.output_tokens) if st.output_tokens else None),
            "grounding_rate": st.grounding_rate(),
            "n_response_numbers": st.n_response_numbers,
            "providers": dict(st.providers),
            "prompt_versions": dict(st.prompt_versions),
            "n_pm_draws": st.n_pm_draws,
            "n_pm_json_ok": st.n_pm_json_ok,
            "pm_json_parse_rate": st.pm_json_parse_rate(),
            "pm_actions": dict(st.pm_actions),
            "constraint_status": dict(st.constraint_status),
        }
    return {
        "convenes": runs.n_runs,
        "per_agent_llm": per_agent_json,
        "verdict_actions": dict(runs.actions),
        "outage_failsafe": runs.n_outage_failsafe,
        "no_verdict_incomplete": runs.n_no_verdict_incomplete,
        "scripted_runs": runs.scripted_runs,
        "scripted_share": runs.scripted_share(),
        "scripted_agents": dict(runs.scripted_agents),
        "final_stances": {a: dict(c) for a, c in runs.final_stances.items()},
        "final_convictions": {a: dict(c) for a, c in runs.final_convictions.items()},
        "gaps_buckets": gaps_buckets,
        "gaps_emission": gaps_emission,
        "outcome_movement": outcome,
    }


# ── Render ───────────────────────────────────────────────────────────────────


def _pct(value: float | None) -> str:
    return "—" if value is None else f"{100 * value:.1f}%"


def render_report(*, stamp: str, cadence: str, window_days: int, window_start: str,
                  serving_identity: dict, accounting: str, per_agent: dict,
                  runs: RunsStats, gaps_buckets: Counter, gaps_agent_counts: Counter,
                  gaps_emission: dict,
                  outcome: dict, flags: list[Flag], proposals: list[str],
                  baseline: dict | None, trend: dict[str, int]) -> str:
    lines: list[str] = [
        f"# CR247 Phase 6 prompt-evolution digest — {stamp}",
        "",
        f"**{cadence}** · window {window_days}d ({window_start} .. {stamp}) · "
        f"{runs.n_runs} convenes.",
        "",
        "INTERNAL quality signal only — never user-facing. The machine measures "
        "and proposes; governance disposes; nothing in this digest edits "
        "personas, flags, or config.",
        "",
        "## Serving-model keying",
        "",
    ]
    if serving_identity.get("identity"):
        lines += [
            f"- serving model (live /v1/models root, {serving_identity['source']}): "
            f"`{serving_identity['identity']}` fetched {serving_identity['fetched_at']}",
        ]
    else:
        lines += [
            f"- serving model: UNIDENTIFIED ({serving_identity.get('error')}) — "
            f"the header degrades loudly: ALL keying this window is "
            f"provider-only, and deltas against the baseline carry "
            f"model-drift risk the digest cannot rule out (CR040).",
        ]
    lines += [
        "- caveat: `llm_audit` rows carry `provider` only, never a model id — "
        "per-row aggregates are keyed by provider, and the identity above is "
        "the digest-level stamp of which model those provider rows actually "
        "were. The `ami-llm` alias is never used as an identity (it was "
        "reused across the CR211 model swap).",
    ]
    if baseline and (baseline.get("serving_identity") or {}).get("identity"):
        lines.append(
            f"- baseline identity: `{baseline['serving_identity']['identity']}` "
            f"({baseline.get('generated_at', '?')})"
            + (" — **MISMATCH, see flags**"
               if any(f.kind == "MODEL_IDENTITY_MISMATCH" for f in flags) else " — matches"),
        )
    lines += ["", "## Convene accounting", "", f"- {accounting}", ""]

    if per_agent:
        lines += [
            "## Per-agent LLM aggregates (llm_audit, Room flows)",
            "",
            "parse rate = stance extracted / ALL calls in scope (empty responses "
            "count as failures and are counted apart). truncation suspects use "
            "the harness heuristic `output_tokens >= effective ceiling` "
            "(max(_AGENT_MAX_TOKENS[agent], provider floor)); llm_audit has no "
            "finish_reason, so a natural long answer at the cap "
            "false-positives. grounding = share of response numeric tokens "
            "present in the system prompt — a PROXY for citation accuracy "
            "(derived/computed numbers and general-knowledge figures are "
            "legitimate and unverifiable here, so read movement, not levels).",
            "",
            "| agent | calls | empty | parse rate | suspects | mean out tok | "
            "grounding | providers | prompt versions |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for agent, st in sorted(per_agent.items()):
            versions = ", ".join(
                f"{v}:{c}" for v, c in sorted(st.prompt_versions.items()))
            lines.append(
                f"| {agent} | {st.n_calls} | {st.n_empty} | "
                f"{st.n_parsed}/{st.n_calls} ({_pct(st.parse_rate())}) | "
                f"{st.n_truncation_suspects} ({_pct(st.truncation_suspect_rate())}) | "
                f"{(sum(st.output_tokens) / len(st.output_tokens)) if st.output_tokens else 0:.0f} | "
                f"{_pct(st.grounding_rate())} "
                f"({st.n_grounded_numbers}/{st.n_response_numbers}) | "
                f"{', '.join(f'{p}:{c}' for p, c in sorted(st.providers.items()))} "
                f"| {versions} |"
            )
        lines.append(
            "`portfolio_manager` and `risk_officer` speak JSON envelopes, not "
            "STANCE prose — a 0% parse cell is BY CONSTRUCTION for them, not a "
            "regression; the PM's real metric is the JSON parse rate below."
        )
        pm = per_agent.get(PM_AGENT)
        if pm:
            lines += [
                "",
                "### PM envelope",
                "",
                f"- draws {pm.n_pm_draws}, JSON-parseable "
                f"{pm.n_pm_json_ok} ({_pct(pm.n_pm_json_ok / pm.n_pm_draws if pm.n_pm_draws else None)}), "
                f"actions: {dict(pm.pm_actions)}",
                f"- constraint_status: {dict(pm.constraint_status) or '—'}",
                f"- truncation suspects: {pm.n_truncation_suspects} "
                f"(ceiling {effective_ceiling(PM_AGENT, 'vllm')} on vllm)",
            ]

    lines += [
        "",
        "## Verdicts and scripted fallbacks (room_runs)",
        "",
        f"- actions (completed, outage fail-safe excluded): {dict(runs.actions)}",
        f"- DEF336 outage fail-safes excluded from the distribution: "
        f"{runs.n_outage_failsafe}",
        f"- thin-Room NO_VERDICT discards (CR219 R51): {runs.n_no_verdict_incomplete}",
        f"- scripted-fallback convenes: {runs.scripted_runs}/{runs.n_runs} "
        f"({_pct(runs.scripted_share())}); desks: {dict(runs.scripted_agents) or '—'}",
        f"- retried runs (startup sweep): {runs.n_retried}",
        "",
        "## Final stance / conviction per convene (transcript, one per agent)",
        "",
    ]
    if runs.final_stances:
        lines += ["| agent | for | against | neutral | conviction (h/m/l) |",
              "|---|---|---|---|---|"]
        for agent in sorted(runs.final_stances):
            c = runs.final_stances[agent]
            conv = runs.final_convictions.get(agent, Counter())
            lines.append(
                f"| {agent} | {c.get('for', 0)} | {c.get('against', 0)} "
                f"| {c.get('neutral', 0)} | {conv.get('high', 0)}/"
                f"{conv.get('medium', 0)}/{conv.get('low', 0)} |")
    else:
        lines.append("No final stances recorded in the window.")

    total_gaps = sum(gaps_buckets.values())
    lines += [
        "",
        "## GAPS want-list (CR219 R53/R57 telemetry)",
        "",
        f"- ask items: {total_gaps} across {len(gaps_buckets)} buckets; "
        f"envelope emission: {json.dumps(gaps_emission, sort_keys=True)}",
    ]
    for bucket, n in gaps_buckets.most_common():
        lines.append(f"  - {n}x {bucket}")
    analyst_rows = [f"{agent}: asked {gaps_agent_counts[(agent, 'asked')]}, "
                    f"answered {gaps_agent_counts[(agent, 'answered')]}, "
                    f"opted_out_none {gaps_agent_counts[(agent, 'opted_out')]}"
                    for agent in sorted({a for (a, _k) in gaps_agent_counts})]
    if analyst_rows:
        lines.append("- analyst emission (asked / answered / explicit 'GAPS: none'): "
                 + "; ".join(analyst_rows))

    lines += [
        "",
        "## Verdict-outcome ledger movement (score_verdict_outcomes' vocabulary)",
        "",
        f"- pending (not yet due): {outcome['pending_total']}",
        f"- decided this window: {outcome['window_decided']} "
        f"({outcome['window_scored']} scored, unscorable by reason: "
        f"{outcome['window_unscorable_by_reason'] or '—'})",
    ]
    for action, s in (outcome["window_scored_hit_rate"] or {"": {}}).items():
        if action:
            lines.append(
                f"- {action}: n={s['n']} hit_rate "
                f"{_pct(s['hit_rate'])} mean fwd {s['mean_forward_return']}")
    lines += [
        "",
        vo.aggregates()["interpretation"],
        "",
        "## Flags vs baseline",
        "",
    ]
    if baseline is None:
        lines.append("No baseline on record — this run establishes one; no deltas.")
    elif not flags:
        lines.append("No threshold crossings.")
    else:
        for fl in flags:
            lines.append(f"- **{fl.kind}** [{fl.subject}] baseline {fl.baseline} → "
                     f"current {fl.current} — {fl.detail}")
    if proposals:
        lines += ["", "## Proposals (drafted for the Architect — nothing auto-ships)", ""]
        lines += proposals
    if cadence == "monthly conclusion":
        lines += ["", "## Monthly conclusion — flag trend over the window", ""]
        if not trend:
            lines.append("No proposal blocks raised inside the window.")
        for kind, n in sorted(trend.items()):
            verdict = (f"RECURRING ({n}x) — strong candidate for the Architect "
                       f"to mint a CR") if n >= 2 else f"isolated ({n}x)"
            lines.append(f"- {kind}: {verdict}")
    lines += [
        "",
        "---",
        "Baseline file: `baseline.json` (schema "
        f"{BASELINE_SCHEMA}); proposals: `{PROPOSALS_FILENAME}`. Both are "
        "rewritten/append-only by this digest only.",
    ]
    return "\n".join(lines) + "\n"


# ── Main ─────────────────────────────────────────────────────────────────────


def classify_cadence(days: int, n_convenes: int) -> str:
    if days >= CONCLUSION_MIN_DAYS or n_convenes >= CONCLUSION_MIN_CONVENES:
        return "monthly conclusion"
    return "weekly digest"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=int, default=7,
                    help="trailing window in days (default 7; >= "
                         f"{CONCLUSION_MIN_DAYS} forces the monthly conclusion)")
    ap.add_argument("--out", type=Path, default=Path("./prompt_evolution_reports"),
                    help="output dir; on melehost pass "
                         "/backtest_results/prompt_evolution (the rw mount) — "
                         "the default is NOT repo-gitignored")
    ap.add_argument("--stamp", default=date_today_iso(),
                    help="digest date (ISO); keys the digest filename")
    ap.add_argument("--model-base-url", default=None,
                    help="vLLM base url for the identity fetch "
                         "(default: settings.vllm_base_url)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print the report without writing anything")
    args = ap.parse_args(argv)

    try:
        stamp_date = datetime.fromisoformat(args.stamp).date()
    except ValueError:
        raise SystemExit(
            f"FATAL: --stamp must be an ISO date, got {args.stamp!r}"
        ) from None
    stamp = stamp_date.isoformat()
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=args.days)
    window_start = cutoff.date().isoformat()

    base_url = args.model_base_url if args.model_base_url is not None else settings.vllm_base_url
    serving_identity = fetch_serving_identity(base_url)

    excluded = vo.excluded_user_ids()
    with get_session() as session:
        llm_rows = list(session.execute(
            select(LLMAuditRow)
            .where(LLMAuditRow.created_at >= cutoff)
            .where(LLMAuditRow.flow.like(f"{ROOM_FLOW_PREFIX}%"))
            .where(LLMAuditRow.flow != REPLAY_FLOW)
        ).scalars().all())
        before = len(llm_rows)
        llm_rows = [r for r in llm_rows if r.user_id is not None and r.user_id not in excluded]
        n_llm_no_user = before - len(llm_rows)

        all_runs = list(session.execute(select(RoomRunRow)).scalars().all())
        scoreable, run_counts = select_scoreable_runs(
            all_runs, excluded, tickers=None, since=cutoff,
        )
        outcome_rows = list(session.execute(select(VerdictOutcomeRow)).scalars().all())

    per_agent = aggregate_llm_rows(llm_rows)
    runs = aggregate_runs(scoreable)
    bucket_counts, _examples, _by_triple, gaps_agent_counts = tally_data_gaps(scoreable)
    gaps_emission = tally_envelope_emission(scoreable)
    outcome = outcome_movement(outcome_rows, cutoff)
    aggregates = current_aggregates(
        per_agent, runs, dict(bucket_counts), gaps_emission, outcome)
    n_agentless = sum(1 for r in llm_rows if not r.agent_id)

    cadence = classify_cadence(args.days, runs.n_runs)
    accounting = (
        f"room runs seen: {len(all_runs)} — excluded: "
        f"excluded_user {run_counts['excluded_user']}, "
        f"too_old {run_counts['too_old']} — measured: {runs.n_runs}; "
        f"llm_audit room rows in window: {before} — excluded: "
        f"no_or_synthetic_user {n_llm_no_user}, no_agent_id {n_agentless} "
        f"— measured: {len(llm_rows) - n_agentless}"
    )

    baseline_path = args.out / BASELINE_FILENAME
    baseline = load_baseline(baseline_path)
    flags = compare_to_baseline(
        {"aggregates": aggregates, "serving_identity": serving_identity}, baseline)
    proposals = build_proposal_blocks(
        flags, stamp=stamp, window_days=args.days, window_start=window_start,
        cadence=cadence)
    trend = (conclusion_trend(args.out / PROPOSALS_FILENAME, window_start)
             if cadence == "monthly conclusion" else {})

    if runs.n_runs == 0 and not llm_rows:
        print(f"[digest {stamp}] NOTHING MEASURED — no real-user room runs or "
              f"room llm_audit rows in the {args.days}d window. A quiet alpha "
              f"week is a legitimate state; the baseline is left untouched. "
              f"(exit 0)", flush=True)
        return 0

    report = render_report(
        stamp=stamp, cadence=cadence, window_days=args.days,
        window_start=window_start, serving_identity=serving_identity,
        accounting=accounting, per_agent=per_agent, runs=runs,
        gaps_buckets=bucket_counts, gaps_agent_counts=gaps_agent_counts,
        gaps_emission=gaps_emission,
        outcome=outcome, flags=flags, proposals=proposals,
        baseline=baseline, trend=trend,
    )
    print(report, flush=True)

    if args.dry_run:
        print(f"[digest {stamp}] --dry-run: {len(flags)} flag(s), "
              f"{len(proposals)} proposal block(s) — nothing written.", flush=True)
        return 0

    args.out.mkdir(parents=True, exist_ok=True)
    digest_path = args.out / f"digest_{stamp}.md"
    digest_path.write_text(report)
    if baseline is not None:
        backup = args.out / f"baseline_{baseline.get('generated_at', 'prev')}.json"
        backup.write_text(json.dumps(baseline, indent=2, sort_keys=True))
    baseline_path.write_text(json.dumps(build_baseline(
        stamp=stamp, window_days=args.days, window_start=window_start,
        serving_identity=serving_identity, aggregates=aggregates,
    ), indent=2, sort_keys=True))
    proposals_path = args.out / PROPOSALS_FILENAME
    if proposals:
        with proposals_path.open("a") as fh:
            for block in proposals:
                fh.write(block + "\n\n")

    print(f"[digest {stamp}] {cadence}: {len(flags)} flag(s), "
          f"{len(proposals)} proposal(s) → {digest_path}", flush=True)
    return 0


def date_today_iso() -> str:
    return datetime.now(UTC).date().isoformat()


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        print(f"prompt_evolution_digest failed: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc
