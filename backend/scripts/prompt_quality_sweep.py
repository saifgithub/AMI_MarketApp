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

    So this returns the extractions for hand-reading and refuses to compute the
    summary statistic. `mean_spread_pts` is deliberately None: a 46.83 built from
    27%-precision inputs is worse than no number, because it reads as a finding.
    Restoring it requires the agents to declare size in the envelope — a prompt
    change, not a parser change.
    """
    rows = []
    for run in runs:
        sizes = {}
        for entry in run.get("transcript") or []:
            aid = entry.get("agent_id")
            if aid in _RISK:
                m = _PROPOSED_SIZE.search(entry.get("content") or "")
                if m:
                    try:
                        sizes[aid] = float(m.group(1))
                    except ValueError:
                        pass
        if len(sizes) >= 2:
            rows.append({"ticker": run.get("ticker"), "sizes": sizes,
                         "spread_pts": round(max(sizes.values()) - min(sizes.values()), 2)})
    return {
        "status": "UNRELIABLE — extractions are 27% precise (3/11 hand-read, "
                  "2026-08-07 epoch). Do not cite spread figures. See DEF271.",
        "convenes_with_2plus_sizes": len(rows),
        "convenes_total": len(runs),
        "mean_spread_pts": None,
        "zero_spread_convenes": None,
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

        dates = _iso_dates(masked)
        counts = [(m.group(1), int(m.group(1)), m.start())
                  for m in _DAYCOUNT.finditer(masked)]
        used_counts: set[int] = set()

        for raw_d, parsed, pos in dates:
            near = [(c, n, cp) for c, n, cp in counts
                    if abs(cp - pos) <= window and cp not in used_counts
                    and not _CLAUSE_BREAK.search(
                        masked[min(cp, pos):max(cp, pos)])]
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
