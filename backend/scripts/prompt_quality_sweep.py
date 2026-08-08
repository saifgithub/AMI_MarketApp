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


def _context(text: str, token: str, width: int = 60) -> str:
    i = text.find(token)
    if i < 0:
        return ""
    a, b = max(0, i - width), min(len(text), i + len(token) + width)
    return " ".join(text[a:b].split())


def m4_risk_spread(runs: list[dict]) -> dict[str, Any]:
    """Do the three risk personas propose three different sizes?"""
    rows, collapsed = [], 0
    for run in runs:
        sizes = {}
        for entry in run.get("transcript") or []:
            aid = entry.get("agent_id")
            if aid in _RISK:
                m = _LEVEL_PATTERNS["size"].search(entry.get("content") or "")
                if m:
                    try:
                        sizes[aid] = float(m.group(1))
                    except ValueError:
                        pass
        if len(sizes) >= 2:
            spread = max(sizes.values()) - min(sizes.values())
            collapsed += spread == 0.0
            rows.append({"ticker": run.get("ticker"), "sizes": sizes,
                         "spread_pts": round(spread, 2)})
    spreads = [r["spread_pts"] for r in rows]
    return {
        "convenes_with_2plus_sizes": len(rows),
        "convenes_total": len(runs),
        "mean_spread_pts": round(sum(spreads) / len(spreads), 2) if spreads else None,
        "zero_spread_convenes": collapsed,
        "rows": rows,
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
