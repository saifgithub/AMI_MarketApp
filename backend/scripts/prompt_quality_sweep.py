"""CR143 Phase 3b — do the prompts get twelve agents to do twelve jobs?

Every other measurement in this audit grades honesty or machine-legibility: does
the prompt claim data it has, does the reply parse, does the stance envelope
survive. None of them asks whether the debate is any GOOD — and that is what the
prompts exist for. AMI is a training simulator; the Room's product is a legible
worked example of how a professional process reasons. Four analysts who all say
the same thing still parse perfectly.

So this measures structure, not prose quality, because structure has a defensible
bad direction and a computable null baseline. Six metrics:

  M1 role identifiability   — strip the stance line; can the author be recovered?
                              At chance, the twelve roles are cosmetic.
  M2 role vs ticker         — THE decisive contrast. Compare two similarities:
                              different agents on the SAME ticker, versus the same
                              agent on DIFFERENT tickers. If turns cluster by
                              ticker rather than by agent, the role prompts are
                              losing to the fact sheet.
  M3 number provenance      — every numeric token classed grounded / inherited /
                              novel. Novel-high is the CR037/CR038 fabrication
                              class that has never had a detector; grounded-only
                              near 100% is readback, not analysis.
  M4 risk spread            — the sizes aggressive/conservative/neutral propose.
                              Zero spread means that phase is costume.
  M5 PM groundedness        — does verdict.reason trace to any voice other than
                              the Trader's? If not, the debate never reached the
                              verdict it exists to inform.
  M6 stance entropy         — for/against/neutral per convene. Near zero is a
                              room with no friction.
  M7 date accuracy          — CR169's gate. Every reply that states BOTH a date
                              and a distance to it ("by 2026-11-03 (88 days)")
                              is self-checking against the fact sheet's as-of
                              anchor. Deterministic, so unlike M1-M6 it can gate
                              a commit — the CR143 §7 gap an LLM judge cannot
                              fill.

P16 compliance: every extraction prints samples of what it matched AND what it
did not, for hand-reading. A count nobody read is not a measurement.

Input is a JSON dump of `llm_audit` (system_prompt + response_text per turn) and
`room_runs` (verdict + transcript) for ONE prompt epoch — pooling across a prompt
change makes every number here meaningless.

Usage (from backend/):
    .venv/bin/python -m scripts.prompt_quality_sweep --corpus <dir>
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from datetime import date
from itertools import combinations
from pathlib import Path
from typing import Any

# Production patterns, imported rather than retyped so a drift in either shows up
# here as a changed number instead of a silent divergence.
from app.services.room_runner import _LEVEL_PATTERNS

_PROSE_AGENTS = (
    "fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst",
    "bull_researcher", "bear_researcher", "research_manager", "trader",
    "aggressive_debator", "conservative_debator", "neutral_debator",
)
_ANALYSTS = _PROSE_AGENTS[:4]
_RISK = ("aggressive_debator", "conservative_debator", "neutral_debator")

# Words that carry no role signal. Deliberately short: an aggressive stoplist
# would launder the very redundancy M2 exists to detect.
_STOP = frozenset("""
about above after again against because been before being below between both
could does doing down during each from further having here into itself more
most only other over same some such than that their them then there these they
this those through under until very were what when where which while will with
would your this that have has had not but for are was its
""".split())

_NUM_RE = re.compile(r"-?\$?\d[\d,]*(?:\.\d+)?%?")
_STANCE_LINE_RE = re.compile(r"^\s*\[?\s*STANCE\s*:.*?(?:\]|$)", re.IGNORECASE | re.MULTILINE)


# ── text helpers ────────────────────────────────────────────────────────────

def _strip_envelope(text: str) -> str:
    return _STANCE_LINE_RE.sub("", text or "", count=1)


def _tokens(text: str, drop: set[str]) -> Counter:
    """Content tokens: alphabetic, >=4 chars, minus stopwords and minus the
    ticker symbols of the convene (so similarity measures what an agent SAYS,
    not which name it was handed)."""
    out = Counter()
    for w in re.findall(r"[A-Za-z][A-Za-z'-]+", (text or "").lower()):
        if len(w) >= 4 and w not in _STOP and w not in drop:
            out[w] += 1
    return out


def _cosine(a: Counter, b: Counter) -> float:
    if not a or not b:
        return 0.0
    common = set(a) & set(b)
    num = sum(a[t] * b[t] for t in common)
    da = math.sqrt(sum(v * v for v in a.values()))
    db = math.sqrt(sum(v * v for v in b.values()))
    return num / (da * db) if da and db else 0.0


def _norm_num(tok: str) -> str | None:
    """Canonical form of a numeric token: '$1,073.46' -> '1073.46', '16%' -> '16'.

    DEF234 is why the thousands separator is stripped BEFORE the float parse —
    the shipped level parser stopped at the comma and read $1,073.46 as $1.00.
    """
    t = tok.strip().lstrip("$").rstrip("%").replace(",", "").lstrip("-")
    if not t or not re.fullmatch(r"\d+(?:\.\d+)?", t):
        return None
    try:
        f = float(t)
    except ValueError:
        return None
    return f"{f:g}"


def _numbers(text: str) -> list[tuple[str, str]]:
    """(raw token, canonical) for every number in `text`."""
    out = []
    for m in _NUM_RE.finditer(text or ""):
        c = _norm_num(m.group(0))
        if c is not None:
            out.append((m.group(0), c))
    return out


# ── M8 domain vocabulary ────────────────────────────────────────────────────
# CR179 Leg 0. The lane matrix is IMPORTED, not retyped, on the same rule as
# `_LEVEL_PATTERNS` above: if someone re-lanes an agent, this metric changes its
# number instead of quietly measuring the old matrix.
#
# PRECISION OVER RECALL, deliberately. DEF279 is the standing warning — M7's
# first form reported a 13.4% error rate on a corpus whose true rate was 0%,
# because a plausible-looking pattern matched three things it had no business
# matching. A cross-lane metric has the same failure mode and a worse
# consequence: it is the acceptance gate for the lane firewall, so a false
# positive argues for tightening a firewall that is already working.
#
# The known collisions, each one a term that belongs to two desks depending on
# what it is attached to. These are not hypothetical: CR145's original filing
# put `social_media_analyst` at "technicals 13/18", and the re-derivation found
# 6 of those were "mention volume" — the Social Analyst's OWN input, counted
# against it because "volume" reads as technicals in isolation.
_M8_COLLISIONS = (
    # "volume" is technicals; "mention volume" / "volume of mentions" is social.
    (re.compile(r"\b(?:mention|post|comment|chatter)\s+volume\b", re.I), "social"),
    (re.compile(r"\bvolume\s+of\s+(?:mentions|posts|comments|chatter)\b", re.I), "social"),
    # "trend" is technicals; "sentiment trend" is social.
    (re.compile(r"\bsentiment\s+trend\b", re.I), "social"),
    # An earnings DATE rides the news lane and the fundamentals lane both
    # (`room_prompts.py` renders `next_earnings` into either), so neither desk
    # is trespassing by naming it. Only earnings as a FIGURE is fundamentals.
    (re.compile(r"\bearnings\s+(?:date|day|call|is\s+on|on\s+\d)", re.I), None),
    (re.compile(r"\bnext\s+earnings\b", re.I), None),
)

_M8_DOMAIN_TERMS: dict[str, re.Pattern] = {
    "fundamentals": re.compile(
        r"\b(?:P/E|PE\s+ratio|forward\s+P/E|EV/EBITDA|P/S|price[- ]to[- ]sales|PEG|"
        # `margin` is qualified: the Social Analyst's "inside the sampling error
        # margin" is a statistics word, not a profit margin, and bare `margin`
        # scored it as trespass.
        r"valuation|multiple[sd]?\b|(?:profit|gross|operating|net|EBITDA)\s+margin[s]?|"
        r"margin[s]?\s+of\s+\d|revenue|EPS|earnings\s+per\s+share|"
        r"free\s+cash\s+flow|FCF|cash\s+flow|balance\s+sheet|net\s+(?:cash|debt)|"
        r"total\s+debt|debt[- ]to[- ]equity|market\s+cap|ROE|ROA|return\s+on\s+"
        r"(?:equity|assets)|current\s+ratio|quick\s+ratio|dividend|payout|"
        r"analyst\s+(?:target|consensus|rating)|book\s+value|profitab)\b",
        re.I,
    ),
    # `support`, `momentum` and `chart` are QUALIFIED here, not bare, and the
    # qualification was earned by hand-reading — bare forms produced 100% false
    # positives on the 2026-08-13 epoch:
    #   * "support" was the VERB in every single hit: "a 122.6x P/E supported by
    #     a 16% profit margin", "cash to support the dividend yield", "analyst
    #     support for the business model". Not one was a price level.
    #   * "momentum" was "top-line momentum … TTM revenue growth" (fundamentals)
    #     and "broad sector momentum" describing a headline cluster (news).
    #   * "chart" caught the News Analyst writing "No trade ideas or chart
    #     analysis are provided" — being scored as trespassing for COMPLYING
    #     with the firewall, which would have argued for tightening a control
    #     that was working.
    # Recall is spent to buy that precision, and the cost is stated in the
    # result rather than hidden: see `overall_rate_pct` history in the CR.
    "technicals": re.compile(
        r"\b(?:RSI|SMA|EMA|moving\s+average|50-day|20-day|200-day|52-week|"
        r"support\s+(?:level|zone|line|at\b)|support/resistance|"
        r"resistance\s+(?:level|zone|line|at\b)|"
        r"breakout|oversold|overbought|price\s+momentum|chart\s+pattern|"
        r"downtrend|uptrend|volume\s+ratio|relative\s+volume|range\s+(?:low|high)|"
        r"technical\s+(?:setup|picture|analysis|indicator)|price\s+action)\b",
        re.I,
    ),
    "news": re.compile(
        r"\b(?:headline[s]?|catalyst[s]?|press\s+release|announced|announcement|"
        r"reported\s+(?:that|on)|news\s+flow|FOMC|Fed\s+(?:meeting|decision)|"
        # An ANALYST upgrade is news; an EARNINGS upgrade is a fundamentals
        # revision. Bare `upgrades` scored the Fundamentals Analyst's
        # "implies significant earnings upgrades via consensus EPS est." as
        # trespass into news.
        r"guidance\s+(?:cut|raise)|(?:analyst|rating|broker)\s+(?:down|up)grade[ds]?|"
        r"(?:down|up)graded\s+(?:to|by)\b)",
        re.I,
    ),
    "social": re.compile(
        r"\b(?:Reddit|r/[A-Za-z]+|subreddit|wallstreetbets|retail\s+(?:sentiment|"
        r"investor|chatter|crowd)|social\s+sentiment|buzz|upvote[s]?|meme|"
        r"community\s+(?:sentiment|read)|mentions?\b)\b",
        re.I,
    ),
}


def _m8_domains_cited(text: str) -> dict[str, list[str]]:
    """Which desks' subject matter this turn speaks to, and the phrase that says so.

    Collisions are resolved FIRST and their spans masked, so a term that has
    already been claimed by the phrase it sits in cannot be double-counted by
    the generic vocabulary. A `None` owner means the phrase is legitimately
    shared and belongs to nobody's trespass count.
    """
    hits: dict[str, list[str]] = defaultdict(list)
    masked = text or ""
    for pattern, owner in _M8_COLLISIONS:
        for m in pattern.finditer(masked):
            if owner is not None:
                hits[owner].append(m.group(0))
        masked = pattern.sub(lambda m: " " * len(m.group(0)), masked)
    for domain, pattern in _M8_DOMAIN_TERMS.items():
        for m in pattern.finditer(masked):
            hits[domain].append(m.group(0))
    return dict(hits)


def _section(prompt: str, start: str, end: str) -> str:
    i = prompt.find(start)
    j = prompt.find(end, i + 1) if i >= 0 else -1
    return prompt[i:j] if i >= 0 and j > i else ""


def _ticker_of(prompt: str) -> str:
    m = re.search(r"^Ticker:\s*([A-Z.\-]+)\s*$", prompt or "", re.MULTILINE)
    return m.group(1) if m else ""


# ── metrics ─────────────────────────────────────────────────────────────────

def m1_identifiability(turns: list[dict]) -> dict[str, Any]:
    """Leave-one-out nearest-centroid over agent classes."""
    vecs = [(t["agent_id"], t["_vec"]) for t in turns if t["_vec"]]
    by_agent: dict[str, list[Counter]] = defaultdict(list)
    for a, v in vecs:
        by_agent[a].append(v)

    correct = 0
    confusion: Counter = Counter()
    for agent, vec in vecs:
        best, best_sim = None, -1.0
        for other, group in by_agent.items():
            pool = [v for v in group if v is not vec]
            if not pool:
                continue
            centroid: Counter = Counter()
            for v in pool:
                centroid.update(v)
            sim = _cosine(vec, centroid)
            if sim > best_sim:
                best, best_sim = other, sim
        correct += best == agent
        if best != agent:
            confusion[f"{agent} -> {best}"] += 1
    n = len(vecs)
    chance = 1.0 / len(by_agent) if by_agent else 0.0
    return {
        "n": n,
        "accuracy": round(correct / n, 3) if n else 0.0,
        "chance": round(chance, 3),
        "lift_over_chance": round((correct / n) / chance, 2) if n and chance else 0.0,
        "top_confusions": confusion.most_common(8),
    }


def m2_role_vs_ticker(turns: list[dict]) -> dict[str, Any]:
    """The decisive contrast: does a turn resemble its PHASE-MATES on the same
    ticker, or its OWN ROLE on other tickers?"""
    by_convene: dict[str, dict[str, Counter]] = defaultdict(dict)
    for t in turns:
        if t["_vec"]:
            by_convene[t["run_key"]][t["agent_id"]] = t["_vec"]

    same_ticker_cross_agent, same_agent_cross_ticker = [], []
    analyst_pairs = []
    for _, agents in by_convene.items():
        for a, b in combinations(sorted(agents), 2):
            s = _cosine(agents[a], agents[b])
            same_ticker_cross_agent.append(s)
            if a in _ANALYSTS and b in _ANALYSTS:
                analyst_pairs.append(s)

    by_agent: dict[str, list[Counter]] = defaultdict(list)
    for t in turns:
        if t["_vec"]:
            by_agent[t["agent_id"]].append(t["_vec"])
    for _, vs in by_agent.items():
        for x, y in combinations(vs, 2):
            same_agent_cross_ticker.append(_cosine(x, y))

    mean = lambda xs: round(sum(xs) / len(xs), 3) if xs else 0.0
    role, ticker = mean(same_agent_cross_ticker), mean(same_ticker_cross_agent)
    return {
        "same_agent_cross_ticker": {"mean": role, "n": len(same_agent_cross_ticker)},
        "same_ticker_cross_agent": {"mean": ticker, "n": len(same_ticker_cross_agent)},
        "analyst_pairs_same_convene": {"mean": mean(analyst_pairs), "n": len(analyst_pairs)},
        "role_signal_exceeds_ticker_signal": role > ticker,
        "margin": round(role - ticker, 3),
    }


def m3_number_provenance(turns: list[dict]) -> dict[str, Any]:
    """Class every number an agent states: grounded (in its own fact sheet),
    inherited (already in the transcript it was handed), or novel."""
    totals = Counter()
    per_agent: dict[str, Counter] = defaultdict(Counter)
    novel_samples, grounded_samples = [], []

    for t in turns:
        prompt = t["system_prompt"] or ""
        facts = _section(prompt, "Fact sheet as of", "Transcript so far")
        transcript = _section(prompt, "Transcript so far", "\nYour turn.")
        fact_nums = {c for _, c in _numbers(facts)}
        tr_nums = {c for _, c in _numbers(transcript)}
        body = _strip_envelope(t["response_text"] or "")
        for raw, canon in _numbers(body):
            if canon in fact_nums:
                kind = "grounded"
            elif canon in tr_nums:
                kind = "inherited"
            else:
                kind = "novel"
            totals[kind] += 1
            per_agent[t["agent_id"]][kind] += 1
            ctx = _context(body, raw)
            if kind == "novel" and len(novel_samples) < 40:
                novel_samples.append({"agent": t["agent_id"], "num": raw, "ctx": ctx})
            elif kind == "grounded" and len(grounded_samples) < 10:
                grounded_samples.append({"agent": t["agent_id"], "num": raw, "ctx": ctx})

    total = sum(totals.values()) or 1
    return {
        "totals": dict(totals),
        "pct": {k: round(100.0 * v / total, 1) for k, v in totals.items()},
        "per_agent_novel_pct": {
            a: round(100.0 * c["novel"] / max(sum(c.values()), 1), 1)
            for a, c in sorted(per_agent.items())
        },
        "novel_samples": novel_samples,
        "grounded_samples": grounded_samples,
    }


# Verbatim the expression DEF235 (e319ba49) removed from `_LEVEL_PATTERNS`. See
# m4_risk_spread's docstring for why measuring the prose is still legitimate
# after production stopped trusting it.
_PROPOSED_SIZE = re.compile(
    r"\bsize\b[^\n$0-9]{0,15}\$?\s*(\d+(?:\.\d+)?)\s*%?", re.IGNORECASE)


def _context(text: str, token: str, width: int = 60) -> str:
    i = text.find(token)
    if i < 0:
        return ""
    a, b = max(0, i - width), min(len(text), i + len(token) + width)
    return " ".join(text[a:b].split())


def m4_risk_spread(runs: list[dict]) -> dict[str, Any]:
    """Do the three risk personas propose three different sizes? UNRELIABLE — read on.

    DEF271. This metric imported `_LEVEL_PATTERNS["size"]`, which DEF235 deleted
    from production on 2026-08-08 for cause: reading a position size out of prose
    is how an entry price got spent as a size. The import kept the whole sweep
    crashing on `KeyError: 'size'` from that day until 2026-08-12, which is how a
    dead instrument goes unnoticed — nobody ran it.

    Restoring the pattern makes the script run and does NOT make the metric true.
    Hand-read, all 11 matches on the 2026-08-07 epoch: **3 correct, 8 wrong** —
    two of the eight are literal entry prices ($188.62, $1212.21), DEF235's exact
    defect reproduced verbatim; the rest are stop percentages and upside targets
    sitting near the word "size". Precision 27%.

    Two alternatives were measured and both fail. The CR106 stance envelope
    carries a size in **1 of 54** risk turns (2%), so the contracted surface is
    empty. No structured size field exists on the transcript entry at all.

    CR197 built that field. `argued_size_pct` is parsed from a SIZE slot in the
    RISK phase's stance envelope, so on any epoch recorded after it this metric
    reads a declared number instead of guessing at prose, and `source` says which.

    What the number means also changed, and this is the more important half. The
    spread itself was never evidence of anything: `risk_debator_sizes()` computes
    trader+2 / trader−1.5 / trader in code and HANDS each debator the figure to
    argue, so a "spread" of 3.5 pt is arithmetic, not debate. A declared spread
    near 3.5 therefore means the agents recited their brief; what carries
    information is deviation from it. `declaration_rate` is reported alongside,
    because this is a prompt-level instruction and P2 forbids assuming compliance.
    """
    rows: list[dict] = []
    declared = structured = prose = 0
    risk_turns = 0
    for run in runs:
        sizes: dict[str, float] = {}
        srcs: dict[str, str] = {}
        for entry in run.get("transcript") or []:
            aid = entry.get("agent_id")
            if aid not in _RISK:
                continue
            risk_turns += 1
            declared_size = entry.get("argued_size_pct")
            if isinstance(declared_size, (int, float)):
                sizes[aid] = float(declared_size)
                srcs[aid] = "envelope"
                declared += 1
                structured += 1
                continue
            m = _PROPOSED_SIZE.search(entry.get("content") or "")
            if m:
                try:
                    sizes[aid] = float(m.group(1))
                    srcs[aid] = "prose (27% precise — DEF271)"
                    prose += 1
                except ValueError:
                    pass
        if len(sizes) >= 2:
            rows.append({"ticker": run.get("ticker"), "sizes": sizes, "sources": srcs,
                         "spread_pts": round(max(sizes.values()) - min(sizes.values()), 2)})

    all_structured = prose == 0 and structured > 0
    spreads = [r["spread_pts"] for r in rows]
    return {
        "status": (
            "OK — sizes read from the CR197 envelope field"
            if all_structured
            else "UNRELIABLE — one or more sizes came from prose, 27% precise "
                 "(3/11 hand-read, 2026-08-07 epoch). See DEF271."
        ),
        "source": "envelope" if all_structured else ("mixed" if structured else "prose"),
        "risk_turns": risk_turns,
        "declaration_rate": round(declared / risk_turns, 3) if risk_turns else None,
        "convenes_with_2plus_sizes": len(rows),
        "convenes_total": len(runs),
        # Only computed when nothing was guessed from prose: a mean built from
        # 27%-precision inputs reads as a finding and is worse than no number.
        "mean_spread_pts": (
            round(sum(spreads) / len(spreads), 2) if all_structured and spreads else None
        ),
        "zero_spread_convenes": (
            sum(1 for s in spreads if s == 0) if all_structured else None
        ),
        "reference_spread_pts": 3.5,
        "reference_note": (
            "The handed spread is 3.5 pt by construction (risk_debator_sizes: "
            "+2 / -1.5 / +0). A declared spread at 3.5 is the brief recited; "
            "deviation from it is the only part that carries information."
        ),
        "rows_for_hand_reading": rows,
    }


def m5_pm_groundedness(runs: list[dict]) -> dict[str, Any]:
    """Which voice does the PM's reason actually echo?"""
    attribution, rows = Counter(), []
    for run in runs:
        verdict = run.get("verdict") or {}
        reason = verdict.get("reason") or ""
        if not reason.strip():
            attribution["<empty reason>"] += 1
            continue
        rvec = _tokens(reason, {(run.get("ticker") or "").lower()})
        best, best_sim = None, 0.0
        sims = {}
        for entry in run.get("transcript") or []:
            aid = entry.get("agent_id")
            if aid not in _PROSE_AGENTS:
                continue
            s = _cosine(rvec, _tokens(entry.get("content") or "",
                                      {(run.get("ticker") or "").lower()}))
            sims[aid] = round(s, 3)
            if s > best_sim:
                best, best_sim = aid, s
        attribution[best or "<no match>"] += 1
        rows.append({"ticker": run.get("ticker"), "action": verdict.get("action"),
                     "reason_chars": len(reason), "closest": best,
                     "sim": round(best_sim, 3), "all_sims": sims})
    return {"closest_voice_counts": attribution.most_common(), "rows": rows}


def m6_stance_entropy(runs: list[dict]) -> dict[str, Any]:
    """Friction: how spread are the eleven stances within a convene?"""
    rows, ents = [], []
    overall = Counter()
    for run in runs:
        c = Counter()
        for entry in run.get("transcript") or []:
            if entry.get("agent_id") in _PROSE_AGENTS:
                c[(entry.get("stance") or "none").lower()] += 1
                overall[(entry.get("stance") or "none").lower()] += 1
        n = sum(c.values())
        if not n:
            continue
        ent = -sum((v / n) * math.log2(v / n) for v in c.values() if v)
        ents.append(ent)
        rows.append({"ticker": run.get("ticker"), "stances": dict(c),
                     "entropy_bits": round(ent, 2)})
    return {
        "overall_stance_mix": dict(overall),
        "mean_entropy_bits": round(sum(ents) / len(ents), 2) if ents else None,
        "max_possible_bits": round(math.log2(3), 2),
        "unanimous_convenes": sum(1 for r in rows if r["entropy_bits"] == 0.0),
        "rows": rows,
    }


_ASOF_RE = re.compile(r"Fact sheet as of (\d{4}-\d{2}-\d{2})")
_ISO_DATE = re.compile(r"\b(\d{4})-(\d{2})-(\d{2})\b")
# "in 88 days", "88 days", "(88 days)", "88-day" — the horizon forms the corpus
# actually uses. Deliberately NOT matching "50-day low"/"20-day SMA": those are
# indicator window names, not offsets from the as-of date, and counting them as
# date claims would swamp the metric with false positives.
_DAYCOUNT = re.compile(
    r"(?<![\w-])(?:in\s+|within\s+|over\s+the\s+next\s+|~)?(\d{1,4})[\s-]*(?:calendar\s+)?days?\b",
    re.IGNORECASE)
_INDICATOR_WINDOW = re.compile(
    r"\b\d{1,4}[\s-]*day\s+(?:sma|ema|ma|moving|average|low|high|rsi|atr|vol|volume|range)",
    re.IGNORECASE)
# A date and a day-count only describe the SAME event if no clause boundary sits
# between them. Without this the scorer paired an earnings date with an FOMC
# countdown 60 characters later and called a correct reply wrong — the only
# "mismatch" in the whole 2026-08-07 baseline, and it was the instrument's error.
# Sentence end or line end only. An earlier draft also treated "* " as a bullet
# marker, which matched the trailing asterisk of every markdown **bold** span and
# silently cut the scored population from 29 pairs to 3 — a guard that looked
# like precision and was actually blindness.
_CLAUSE_BREAK = re.compile(r"[.;:]\s|\n")
_EMPHASIS = re.compile(r"\*\*|__")

# DEF279 — three false-positive classes the 2026-08-07 baseline (n=30) was too
# small to expose and the 2026-08-13 corpus (n=82) showed at 11/82 = 13.4%. All
# eleven were hand-read; **none was a model error.** M7 is the only deterministic
# scorer that could gate a commit, and a gate that is wrong 13.4% of the time
# blocks correct work — the same "a check whose failing state is its normal
# state" pathology CR175 F5 is about, arriving in the instrument instead of the
# pipeline.
#
# (a) TWO EVENTS, ONE CLAUSE. "the FOMC decision in 34 days and Q4 earnings on
#     2026-11-03" — the count belongs to the FOMC, the date to earnings, and
#     `_CLAUSE_BREAK` cannot see it because "and" is not a clause break. 7 of 11.
#     Fixed by refusing a pair whose span contains a SECOND event noun: if two
#     event words sit between the number and the date, they are not one claim.
_EVENT_NOUN = re.compile(
    r"\b(fomc|earnings|cpi|ppi|fed|jackson\s+hole|guidance|dividend|ex-div"
    r"|expiry|expiration|split|ipo|lockup|catalyst)\b", re.IGNORECASE)
# (b) THE DATE IS THE ANCHOR, NOT THE TARGET. "34 days from the reference date
#     of 2026-08-13", "2026-08-13 + 34 days", "anchored at 2026-08-13". The
#     distance is measured FROM the date, so `date - as_of` is 0 by construction
#     and every such sentence scores as a 34-day error. 3 of 11.
#     Modifiers stack ("the current anchor date of"), so the qualifier group
#     repeats — a single optional word missed two of the three real cases.
#     Handled in BOTH orders: "34 days from <date>" and "<date> + 34 days".
_ANCHOR_PHRASE = re.compile(
    r"(?:from|since|relative\s+to|as\s+of|after|before)\s+(?:the\s+)?"
    r"(?:(?:reference|anchor|current|as[- ]of|fact\s+sheet|sheet|prompt)\s+)*"
    r"date\s*(?:of\s*)?",
    re.IGNORECASE)
#     "<date> + 34 days" reads as arithmetic ON the anchor. Checked in the few
#     characters immediately before the count rather than anywhere in the span,
#     so an ordinary hyphen elsewhere in the sentence cannot suppress a real pair.
_ANCHOR_ARITHMETIC = re.compile(r"[+]|\bplus\b|\bminus\b", re.IGNORECASE)
# (c) LOOKBACK WINDOW, NOT AN OFFSET. "Reddit snapshot from 2026-08-07 shows 10
#     mentions over 7 days" — "over N days" is a window, exactly like the
#     "20-day average" case `_INDICATOR_WINDOW` already masks, but phrased after
#     the number instead of before it. 1 of 11.
_LOOKBACK = re.compile(
    r"\b(?:over|across|during|in\s+the\s+(?:last|past|prior|trailing))\s+(?:the\s+)?"
    r"(?:last\s+|past\s+|prior\s+|trailing\s+)?\d{1,4}[\s-]*days?\b",
    re.IGNORECASE)


def _nearest_event(text: str, at: int, reach: int = 55) -> str | None:
    """The event noun a claim at `at` attaches to — nearest within `reach` chars.

    DEF279 (a). Ties go to the LEFT: English puts the event before its timing
    ("the FOMC decision in 34 days", "Q4 earnings on 2026-11-03"), so when a
    noun sits equally close on both sides the left one is the referent.
    """
    left = _EVENT_NOUN.search(text[max(0, at - reach):at][::-1][::-1])
    lefts = list(_EVENT_NOUN.finditer(text[max(0, at - reach):at]))
    rights = list(_EVENT_NOUN.finditer(text[at:at + reach]))
    l = (at - (max(0, at - reach) + lefts[-1].end()), lefts[-1].group(0).lower()) if lefts else None
    r = (rights[0].start(), rights[0].group(0).lower()) if rights else None
    if l and r:
        return l[1] if l[0] <= r[0] else r[1]
    return (l or r or (None, None))[1]


def _as_of(prompt: str) -> date | None:
    m = _ASOF_RE.search(prompt or "")
    return date.fromisoformat(m.group(1)) if m else None


def _iso_dates(text: str) -> list[tuple[str, date, int]]:
    """(raw, parsed, char offset) for every well-formed ISO date in `text`."""
    out = []
    for m in _ISO_DATE.finditer(text or ""):
        try:
            out.append((m.group(0), date.fromisoformat(m.group(0)), m.start()))
        except ValueError:
            continue
    return out


def m7_date_accuracy(turns: list[dict], window: int = 90,
                     tolerance: int = 1) -> dict[str, Any]:
    """CR169's gate: are stated dates and day-counts arithmetically right?

    Deterministic by construction — no LLM judge — so it can gate a commit, which
    is the CR143 §7 gap M1–M6 cannot fill (a judge cannot sit in CI).

    Scores ONE construct, the pairing CR169 quotes: an ISO date and a day-count
    within `window` characters of each other. That pair is self-checking — the
    reply states both the destination and the distance, so the as-of date decides
    whether they agree, and no interpretation is needed. `tolerance` absorbs the
    inclusive/exclusive off-by-one that both conventions license.

    Unpaired dates and unpaired day-counts are counted and sampled but NOT
    scored: a bare date has no claim to check, and a bare day-count usually
    refers to an indicator window rather than an offset from now. P16 — the
    unscored population is printed so the gap is read, not assumed.
    """
    scored = ok = bad = 0
    lone_dates = lone_counts = 0
    no_asof = 0
    failures: list[dict] = []
    samples: list[dict] = []
    unscored: list[dict] = []

    for t in turns:
        as_of = _as_of(t.get("system_prompt") or "")
        if as_of is None:
            no_asof += 1
            continue
        # Emphasis markers are stripped BEFORE any matching. The agents write
        # "**88** days" and "**20-day** average", and the `**` between the number
        # and its unit defeated both the day-count matcher and the
        # indicator-window mask — so real pairs went unscored while "20-day
        # average" leaked into the unscored pile looking like a date claim.
        # Replaced with spaces, not deleted, so every offset stays valid.
        reply = _EMPHASIS.sub(lambda m: " " * len(m.group(0)),
                              t.get("response_text") or "")
        masked = _INDICATOR_WINDOW.sub(lambda m: "#" * len(m.group(0)), reply)
        # DEF279 (c): "over 7 days" is a lookback window, same category as the
        # "20-day average" the mask above already removes — just phrased after
        # the number rather than before it.
        masked = _LOOKBACK.sub(lambda m: "#" * len(m.group(0)), masked)

        dates = _iso_dates(masked)
        counts = [(m.group(1), int(m.group(1)), m.start())
                  for m in _DAYCOUNT.finditer(masked)]
        used_counts: set[int] = set()

        for raw_d, parsed, pos in dates:
            near = []
            for c, n, cp in counts:
                if abs(cp - pos) > window or cp in used_counts:
                    continue
                span = masked[min(cp, pos):max(cp, pos)]
                if _CLAUSE_BREAK.search(span):
                    continue
                # DEF279 (b): the date is the ANCHOR the count is measured
                # from ("34 days from the current anchor date of 2026-08-13",
                # "2026-08-13 + 34 days"), so `date - as_of` is 0 by
                # construction and the pair is vacuous in both orders.
                between = masked[min(cp, pos):max(cp, pos)]
                if _ANCHOR_PHRASE.search(between) or (
                        pos < cp
                        and _ANCHOR_ARITHMETIC.search(masked[max(0, cp - 8):cp])):
                    continue
                # DEF279 (a): a count and a date describe the same event only if
                # they attach to the SAME event noun. The first cut looked only
                # BETWEEN them and missed 6 of 7 real cases, because the nouns
                # sit outside: "FOMC decision in 34 days, aiming to hold through
                # the 2026-11-03 earnings report" has FOMC before the count and
                # earnings after the date, with nothing in between. So: find the
                # nearest event noun to each end, and refuse the pair when they
                # are different words.
                if _nearest_event(masked, cp) and _nearest_event(masked, pos) \
                        and _nearest_event(masked, cp) != _nearest_event(masked, pos):
                    continue
                near.append((c, n, cp))
            if not near:
                lone_dates += 1
                if len(unscored) < 30:
                    unscored.append({
                        "kind": "lone_date", "agent_id": t.get("agent_id"),
                        "as_of": as_of.isoformat(), "date": raw_d,
                        "days_from_asof": (parsed - as_of).days,
                        "quote": masked[max(0, pos - 70):pos + 70].replace("\n", " ")})
                continue
            c_raw, stated, cpos = min(near, key=lambda x: abs(x[2] - pos))
            used_counts.add(cpos)
            actual = (parsed - as_of).days
            scored += 1
            row = {"agent_id": t.get("agent_id"), "as_of": as_of.isoformat(),
                   "date": raw_d, "stated_days": stated, "actual_days": actual,
                   "delta": actual - stated,
                   "quote": masked[max(0, min(pos, cpos) - 40):
                                   max(pos, cpos) + 60].replace("\n", " ")}
            if abs(actual - stated) <= tolerance:
                ok += 1
                if len(samples) < 8:
                    samples.append(row)
            else:
                bad += 1
                failures.append(row)

        for c_raw, stated, cp in counts:
            if cp in used_counts:
                continue
            lone_counts += 1
            if len(unscored) < 60:
                unscored.append({
                    "kind": "lone_daycount", "agent_id": t.get("agent_id"),
                    "as_of": as_of.isoformat(), "stated_days": stated,
                    "quote": masked[max(0, cp - 70):cp + 70].replace("\n", " ")})

    return {
        "turns_scored": len(turns) - no_asof,
        "turns_without_asof_anchor": no_asof,
        "pairs_scored": scored,
        "pairs_consistent": ok,
        "pairs_mismatched": bad,
        "mismatch_rate_pct": round(100 * bad / scored, 1) if scored else None,
        "tolerance_days": tolerance,
        "pair_window_chars": window,
        "unscored_lone_dates": lone_dates,
        "unscored_lone_daycounts": lone_counts,
        "mismatches": failures[:40],
        "consistent_samples": samples,
        "unscored_samples": unscored,
    }


def m8_cross_lane_citation(turns: list[dict]) -> dict[str, Any]:
    """CR145 Tier C's acceptance, which has never had an instrument.

    The lane firewall (Batch 5) stopped SUPPLYING each analyst its neighbours'
    data. Whether that stopped them SPEAKING to it is a different question, and
    the only number anyone has for it is the pre-firewall filing — news
    valuation 18/18, fundamentals technicals 11/18, social 11/18, market 5/18.
    `POSTBATCH9_REMEASUREMENT` states the gap plainly: *"needs a per-turn
    domain-citation count, which no current metric computes."* This is it.

    Scored ONLY for the four laned analysts. The eight full-sheet agents hold
    every domain by design, so "cross-lane" is meaningless for them — counting
    them would produce a large, meaningless denominator and make the metric
    look precise while measuring nothing.

    M1 is NOT a substitute, and the memo says so: role-identifiability rose to
    97.5%, but an agent can be perfectly identifiable by vocabulary while still
    borrowing another desk's facts. Distinguishability is not lane discipline.

    TRESPASS IS JUDGED AGAINST THE FACT SHEET, NOT THE VOCABULARY, AND NOT THE
    PROMPT. Two earlier forms of this metric were wrong, both caught by
    hand-reading the matches before reporting a rate (P16, and DEF279's whole
    lesson):

      1. *Vocabulary alone.* `52-week` swamped the Fundamentals Analyst's count
         — but `week52` is DUAL-LANE (`room_prompts.py` renders it into the
         fundamentals lane as well as technicals), so citing it is quoting
         supplied data, not trespass. 15 of that agent's 19 flagged turns were
         this one false class.
      2. *Presence in the system prompt.* `EPS`, `P/E` and `catalyst` appear in
         ALL FOUR analysts' prompts on 40/40 turns — as the anti-fabrication
         INSTRUCTION and the out-of-lane notice, not as data. The firewall's own
         design guarantees this: `_out_of_lane_line` names every withheld domain
         by label, so the words are present precisely BECAUSE the data is not.

    So the test is the same slice M3 grounds numbers against — the rendered fact
    sheet between "Fact sheet as of" and "Transcript so far". A phrase found
    there was supplied to this agent and is dropped from the trespass count;
    those drops are reported in `supplied_not_trespass` so the exclusion is
    auditable rather than silent.

    MEASURED BASELINE, both epochs, this instrument (CR179 Leg 0):

        agent                  08-07 (pre-firewall)   08-13 (post)
        fundamentals_analyst        0/18   0.0%        0/40   0.0%
        market_analyst              0/18   0.0%        0/40   0.0%
        news_analyst                3/18  16.7%        3/40   7.5%
        social_media_analyst        0/18   0.0%        1/40   2.5%
        OVERALL                     3/72   4.2%        4/160  2.5%

    **THIS DOES NOT CONFIRM THE FIREWALL WORKED, and must not be quoted as if it
    did.** Three events against four is no movement at these n. By this measure
    there was little trespass to remove even before the firewall shipped.

    That is not a contradiction of CR145's filing (news valuation 18/18) — it is
    a different question. CR145 counted turns MENTIONING a valuation term; this
    counts turns citing one their own fact sheet did not supply. Re-derived on
    the 08-13 corpus, 27 of 40 news turns mention a fundamentals word and only
    **4 phrases in 3 turns** are unsupplied: the rest are consensus EPS (the
    next-earnings line rides the news lane), or the word sitting inside a
    headline the sheet quoted. Both counts are honest; only one of them is
    evidence about the firewall.

    So M8's value is forward, as the regression guard on any batch that widens a
    lane — CR179 Legs 1 and 3 add fields, and re-supplying a desk with its
    neighbour's data is exactly how trespass would return.

    What this does NOT measure: whether the citation was CORRECT. A News Analyst
    naming a P/E it was never given is out of lane whether the P/E is right or
    wrong. Nor can it separate an agent reasoning from training memory from one
    reading the transcript — the four analysts run in parallel with an empty
    transcript, so for THEM the distinction collapses, which is why only they
    are scored. One known residual false positive is kept rather than patched
    away: an analyst writing "no estimates for revenue are provided in the
    current snapshot" is naming an absence, not trespassing — it is a real
    violation of `_out_of_lane_line` ("do not tell the Room they are
    unavailable") but not of the lane, and 1 of the 4 hits is this shape.
    """
    from app.services.room_prompts import _AGENT_LANES

    lanes = {a.value: set(d) for a, d in _AGENT_LANES.items()}
    per_agent: dict[str, dict[str, Any]] = {}
    samples: list[dict[str, Any]] = []
    clean_samples: list[dict[str, Any]] = []
    supplied_drops: list[dict[str, Any]] = []

    for agent, lane in sorted(lanes.items()):
        rows = [t for t in turns if t["agent_id"] == agent]
        out_of_lane_turns = 0
        domain_counts: Counter = Counter()
        for t in rows:
            prompt = t["system_prompt"] or ""
            # The FACT SHEET, not the prompt — the same slice M3 grounds numbers
            # against. See the docstring: prompt-presence is not supply.
            facts = _section(prompt, "Fact sheet as of", "Transcript so far")
            text = _strip_envelope(t["response_text"] or "")
            cited = _m8_domains_cited(text)
            foreign, supplied = {}, {}
            for d, phrases in cited.items():
                if d in lane:
                    continue
                unsupplied = [p for p in phrases if p.lower() not in facts.lower()]
                if unsupplied:
                    foreign[d] = unsupplied
                if len(unsupplied) < len(phrases):
                    supplied[d] = [p for p in phrases if p.lower() in facts.lower()]
            if supplied and len(supplied_drops) < 15:
                supplied_drops.append({
                    "agent": agent, "ticker": _ticker_of(prompt), "supplied": supplied,
                })
            if foreign:
                out_of_lane_turns += 1
                for d in foreign:
                    domain_counts[d] += 1
                if len(samples) < 30:
                    samples.append({
                        "agent": agent, "ticker": _ticker_of(prompt),
                        "foreign": {d: ph[:4] for d, ph in foreign.items()},
                    })
            elif len(clean_samples) < 10:
                clean_samples.append({
                    "agent": agent, "ticker": _ticker_of(prompt),
                    "in_lane_hits": {d: ph[:4] for d, ph in cited.items()},
                    "excerpt": text[:180],
                })
        per_agent[agent] = {
            "lane": sorted(lane),
            "turns": len(rows),
            "turns_citing_another_lane": out_of_lane_turns,
            "rate_pct": round(100 * out_of_lane_turns / len(rows), 1) if rows else None,
            "by_foreign_domain": dict(domain_counts.most_common()),
        }

    scored = sum(v["turns"] for v in per_agent.values())
    trespassing = sum(v["turns_citing_another_lane"] for v in per_agent.values())
    return {
        "scored_agents": sorted(lanes),
        "note": (
            "laned analysts only; the 8 full-sheet agents hold every domain by "
            "design and are not scored. Rate is turns citing >=1 foreign domain."
        ),
        "turns_scored": scored,
        "turns_citing_another_lane": trespassing,
        "overall_rate_pct": round(100 * trespassing / scored, 1) if scored else None,
        "per_agent": per_agent,
        # P16 — the matches AND the non-matches, both hand-readable. A rate with
        # no readable population is the shape DEF279 shipped in.
        "trespass_samples": samples,
        "in_lane_samples": clean_samples,
        # The exclusions, shown rather than assumed. Every entry is a phrase from
        # another desk's domain that this agent's OWN fact sheet supplied — a
        # dual-lane field, almost always `52-week`. If this list ever grows a
        # class that is not genuinely on the sheet, the metric is over-forgiving
        # and the lane matrix is what to check first.
        "supplied_not_trespass": supplied_drops,
    }


# ── driver ──────────────────────────────────────────────────────────────────

def run(corpus_dir: Path) -> dict[str, Any]:
    turns_raw = json.loads((corpus_dir / "corpus.json").read_text())
    runs = json.loads((corpus_dir / "runs.json").read_text())

    tickers = {(r.get("ticker") or "").lower() for r in runs}
    turns = []
    for t in turns_raw:
        if t["flow"] != "room" or t["agent_id"] not in _PROSE_AGENTS:
            continue
        tk = _ticker_of(t["system_prompt"] or "")
        t["run_key"] = f"{tk}|{(t['created_at'] or '')[:13]}"
        t["_vec"] = _tokens(_strip_envelope(t["response_text"] or ""),
                            tickers | {tk.lower()})
        turns.append(t)

    return {
        "epoch_turns": len(turns),
        "epoch_convenes": len(runs),
        "m1_identifiability": m1_identifiability(turns),
        "m2_role_vs_ticker": m2_role_vs_ticker(turns),
        "m3_number_provenance": m3_number_provenance(turns),
        "m4_risk_spread": m4_risk_spread(runs),
        "m5_pm_groundedness": m5_pm_groundedness(runs),
        "m6_stance_entropy": m6_stance_entropy(runs),
        "m7_date_accuracy": m7_date_accuracy(turns),
        "m8_cross_lane_citation": m8_cross_lane_citation(turns),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--corpus", type=Path, required=True,
                   help="dir holding corpus.json (llm_audit) + runs.json (room_runs)")
    p.add_argument("--out", type=Path, default=None)
    args = p.parse_args()

    res = run(args.corpus)
    text = json.dumps(res, indent=2)
    if args.out:
        args.out.write_text(text)
        print(f"wrote {args.out}")
    else:
        print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
