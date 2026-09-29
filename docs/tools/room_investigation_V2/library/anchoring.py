"""anchoring — CR247 Phase 2.4 step 1: Bull/Bear second-speaker anchoring.

The question (SPEC.md Phase 2.4, D19): CR219 R58 seeds the Bull/Bear speaker
order per run_id, which would make the captured llm_audit corpus a natural
experiment — does the SECOND speaker anchor on the first speaker's argument?
This module is the measurement instrument: order classification, numeric
citation overlap, and stance/conviction outcomes BY ORDER, all deterministic
(LLMs never compute scores — CR247 house rule).

Method (all in code, no judgement calls left to the reader):
  1. Order per convene: a whitespace-normalized 300-char chunk of the Bull's
     response (chars 200-500) found inside the Bear's system_prompt means
     Bull spoke first (the second speaker's prompt embeds the full upstream
     transcript — v1 README "known constraints"). The mirror test classifies
     Bear-first. Neither or both -> unclassified, counted, excluded.
  2. Citation overlap: the set of numeric tokens (prices, percents, ratios)
     in the FIRST speaker's response; the fraction reappearing in the
     SECOND speaker's response. Reported per arm (bull-first vs bear-first),
     pooled with a binomial SE — the anchor question is the symmetric
     comparison bear-second vs bull-second overlap.
  3. Stance/conviction by order: the [STANCE: ... | CONVICTION: ...] envelope
     parsed with the same patterns the backend parses (scoring.extract_decision).
  4. Verdict: MEASURED ANCHORING when the two arms' pooled overlaps differ by
     >= 0.05 absolutely AND >= 2 pooled SEs, else NOT MEASURED. An arm with
     zero classifiable convenes cannot support a verdict at all — the report
     says so instead of comparing nothing.

Authoring-time caveat (2026-09-30, verified live against melehost): the order
split is the design's own sanity check — under working per-run_id seeding it
must be near 50/50. ROOM_DEBATE_ORDER_SEEDED is false in the live alpha
container (`docker exec ami_api_alpha env`) and in Settings' default
(`backend/app/core/config.py`), and no evaluation script sets it, so the
corpus may be 100% one order. This module reports the split it measures; it
never assumes the randomization actually happened.

Corpus hygiene (per the CR247 step-1 brief): user_ids with >5 Bear rows are
batch drivers reusing one user_id and are EXCLUDED wholesale; user_ids with
2-5 Bear rows contribute one (bull, bear) pair per nth, paired in created_at
order — one convene is exactly 1 Bull + 1 Bear call. Pairs with an empty or
null response_text are counted and excluded from overlap/stance. Read-only
against melehost; the only large pull is one row_to_json SELECT per window.
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from library.audit_db import run_psql
from library.scoring import extract_decision

BULL = "bull_researcher"
BEAR = "bear_researcher"
RESEARCHERS = (BULL, BEAR)

# Spec-pinned numeric token shape: prices/percents/ratios. Years and bare
# counts match too — symmetric noise across arms, never arm-selective.
_NUMBER_RE = re.compile(r"\$?\d[\d,.]*%?x?")
_STANCE_PATTERN = r"\[STANCE:\s*([^|]+?)\s*\|"
_CONVICTION_PATTERN = r"\bCONVICTION:\s*([A-Za-z]+)"

# A chunk below this length cannot distinguish "embedded upstream transcript"
# from coincidence -> refuse to classify rather than guess.
_MIN_CHUNK_LEN = 100

_MATERIAL_DELTA = 0.05


@dataclass(frozen=True)
class PairMeasurement:
    user_id: str
    nth: int
    order: str  # "bull_first" | "bear_first" | "unclassified"
    provider: str
    first_speaker: str
    second_speaker: str
    n_first_numbers: int | None
    n_second_numbers: int | None
    n_reappearing: int | None
    overlap: float | None
    bull_stance: str | None
    bear_stance: str | None
    bull_conviction: str | None
    bear_conviction: str | None
    excluded_reason: str | None  # None when fully measured


@dataclass(frozen=True)
class ArmStats:
    order: str
    n_pairs: int          # classified pairs in the arm
    n_overlap: int        # classified pairs with >=1 first-speaker number
    total_first_numbers: int
    total_reappearing: int
    pooled_overlap: float | None
    pooled_se: float | None
    mean_overlap: float | None
    mean_first_numbers: float | None
    mean_second_numbers: float | None
    # Overlap split by the pair's provider — the corpus mixes the vllm
    # serving model (live alpha users) with deepinfra rows (the CR240
    # evaluation), and a per-provider split is the only confound check
    # available when one arm is empty.
    by_provider: dict


@dataclass(frozen=True)
class AnchoringReport:
    window_days: int
    user_ids_seen: int
    batch_driver_user_ids: int    # bear rows > 5, excluded wholesale
    pairs_total: int
    pairs_classified: int
    pairs_unclassified: int
    pairs_missing_response: int
    pairs_mismatched_counts: int  # bull_n != bear_n inside an included user
    order_split: dict
    binomial_p_extreme: float | None  # two-sided p if the split hit 0% or 100%
    arms: dict                    # "bull_first" | "bear_first" -> ArmStats
    provider_mix: dict            # same keys -> {provider: n_pairs}
    stance_by_order: dict         # order -> {stance_pair: n}
    conviction_by_order: dict     # order -> {conviction_pair: n}
    verdict: str
    verdict_detail: str

    def render(self) -> str:
        lines = [
            f"CR247 Phase 2.4 step 1 — Bull/Bear anchoring measurement"
            f" (window: last {self.window_days} days)",
            f"corpus: {self.user_ids_seen} user_ids with Bull/Bear rows; "
            f"{self.batch_driver_user_ids} batch-driver user_ids excluded "
            f"(bear rows > 5)",
            f"pairs: {self.pairs_total} total, {self.pairs_classified} "
            f"classified, {self.pairs_unclassified} unclassified, "
            f"{self.pairs_missing_response} missing response, "
            f"{self.pairs_mismatched_counts} mismatched bull/bear counts",
            f"order split: {json.dumps(self.order_split, sort_keys=True)}"
            + (
                f"  two-sided binomial p of an extreme split: "
                f"{self.binomial_p_extreme:.3g}"
                if self.binomial_p_extreme is not None
                else ""
            ),
            "",
        ]
        for key in ("bull_first", "bear_first"):
            arm = self.arms[key]
            lines.append(f"[{key}] n={arm.n_pairs} pairs "
                         f"({arm.n_overlap} with first-speaker numbers)")
            if arm.pooled_overlap is not None:
                lines.append(
                    f"  citation overlap (second vs first speaker numbers): "
                    f"pooled {arm.pooled_overlap:.3f} "
                    f"(binomial SE {arm.pooled_se:.3f}) "
                    f"over {arm.total_first_numbers} numbers; "
                    f"mean per-pair {arm.mean_overlap:.3f}"
                )
            else:
                lines.append("  citation overlap: n/a (no first-speaker "
                             "numbers in any pair)")
            if arm.mean_first_numbers is not None:
                lines.append(
                    f"  mean numeric-token count: first speaker "
                    f"{arm.mean_first_numbers:.1f}, second speaker "
                    f"{arm.mean_second_numbers:.1f}"
                )
            if arm.by_provider:
                parts = [
                    f"{prov}: {s['pooled_overlap']:.3f}"
                    f" (SE {s['pooled_se']:.3f}, n={s['n_pairs']})"
                    for prov, s in sorted(arm.by_provider.items())
                    if s["pooled_overlap"] is not None
                ]
                lines.append(f"  overlap by provider: {'; '.join(parts)}")
            lines.append(
                f"  provider mix: {json.dumps(self.provider_mix[key], sort_keys=True)}"
            )
            lines.append(
                f"  stance pairs: {json.dumps(self.stance_by_order[key], sort_keys=True)}"
            )
            lines.append(
                f"  conviction pairs: "
                f"{json.dumps(self.conviction_by_order[key], sort_keys=True)}"
            )
            lines.append("")
        lines.append(f"verdict: {self.verdict}")
        lines.append(f"detail: {self.verdict_detail}")
        return "\n".join(lines)


def _norm_ws(text: str | None) -> str:
    return re.sub(r"\s+", " ", text or "")


def _order_chunk(text: str | None) -> str | None:
    """The spec's distinctive chunk: chars 200-500 whitespace-normalized.

    Fallback for short responses (chars 200-500 would be empty or trivially
    small): the centered 300-char window, still refused below
    _MIN_CHUNK_LEN. The measured corpus (researcher responses run ~1-3k
    chars) almost always takes the spec's window verbatim.
    """
    norm = _norm_ws(text)
    if len(norm) >= 500:
        return norm[200:500]
    mid = len(norm) // 2
    chunk = norm[max(0, mid - 150): mid + 150]
    return chunk if len(chunk) >= _MIN_CHUNK_LEN else None


def _classify_order(bull_resp: str | None, bear_resp: str | None,
                    bull_sp: str | None, bear_sp: str | None) -> str:
    bull_chunk = _order_chunk(bull_resp)
    bear_chunk = _order_chunk(bear_resp)
    if bull_chunk is None or bear_chunk is None:
        return "unclassified"
    bull_first = bull_chunk in _norm_ws(bear_sp)
    bear_first = bear_chunk in _norm_ws(bull_sp)
    if bull_first and not bear_first:
        return "bull_first"
    if bear_first and not bull_first:
        return "bear_first"
    return "unclassified"


def _numbers(text: str | None) -> set:
    return set(_NUMBER_RE.findall(_norm_ws(text)))


def _measure_pair(user_id: str, nth: int, bull: dict, bear: dict,
                  ) -> PairMeasurement:
    bull_resp = bull.get("response_text")
    bear_resp = bear.get("response_text")
    provider = bull.get("provider") or "?"
    base = dict(
        user_id=user_id, nth=nth, order="unclassified", provider=provider,
        first_speaker="?", second_speaker="?",
        n_first_numbers=None, n_second_numbers=None,
        n_reappearing=None, overlap=None,
        bull_stance=None, bear_stance=None,
        bull_conviction=None, bear_conviction=None,
        excluded_reason=None,
    )
    if not (bull_resp or "").strip() or not (bear_resp or "").strip():
        return PairMeasurement(excluded_reason="missing_response", **base)
    order = _classify_order(bull_resp, bear_resp,
                            bull.get("system_prompt"), bear.get("system_prompt"))
    # Overlap is only defined when the order is known — for an unclassified
    # pair "who anchored on whom" has no answer, so the first/second fields
    # stay None rather than picking an arbitrary direction.
    if order == "unclassified":
        base.update(order=order)
        return PairMeasurement(**base)
    first, second = (bull, bear) if order == "bull_first" else (bear, bull)
    first_speaker = first["agent_id"]
    second_speaker = second["agent_id"]
    first_nums = _numbers(first.get("response_text"))
    second_nums = _numbers(second.get("response_text"))
    n_reappearing: int | None = None
    overlap: float | None = None
    if first_nums:
        haystack = _norm_ws(second.get("response_text"))
        n_reappearing = sum(1 for t in first_nums if t in haystack)
        overlap = n_reappearing / len(first_nums)
    base.update(
        order=order, first_speaker=first_speaker, second_speaker=second_speaker,
        n_first_numbers=len(first_nums) if first_nums else None,
        n_second_numbers=len(second_nums) if second_nums else None,
        n_reappearing=n_reappearing, overlap=overlap,
        bull_stance=extract_decision(bull_resp, pattern=_STANCE_PATTERN),
        bear_stance=extract_decision(bear_resp, pattern=_STANCE_PATTERN),
        bull_conviction=extract_decision(bull_resp,
                                         pattern=_CONVICTION_PATTERN),
        bear_conviction=extract_decision(bear_resp,
                                         pattern=_CONVICTION_PATTERN),
    )
    return PairMeasurement(**base)


def _arm_stats(order: str, pairs: list) -> ArmStats:
    classified = [p for p in pairs if p.order == order]

    def pool(subset: list) -> tuple[int, int, float | None, float | None]:
        total_first = sum(p.n_first_numbers for p in subset
                          if p.n_first_numbers is not None)
        total_reappearing = sum(p.n_reappearing for p in subset
                                if p.n_reappearing is not None)
        pooled = (total_reappearing / total_first) if total_first else None
        se = (
            math.sqrt(pooled * (1 - pooled) / total_first)
            if pooled is not None and total_first else None
        )
        return total_first, total_reappearing, pooled, se

    with_numbers = [p for p in classified if p.overlap is not None]
    total_first, total_reappearing, pooled, se = pool(with_numbers)
    overlaps = [p.overlap for p in with_numbers]
    first_counts = [p.n_first_numbers for p in classified
                    if p.n_first_numbers is not None]
    second_counts = [p.n_second_numbers for p in classified
                     if p.n_second_numbers is not None]
    by_provider: dict = {}
    for provider in sorted({p.provider for p in with_numbers}):
        subset = [p for p in with_numbers if p.provider == provider]
        pf, pr, pp, pse = pool(subset)
        by_provider[provider] = {
            "n_pairs": len(subset),
            "total_first_numbers": pf,
            "pooled_overlap": pp,
            "pooled_se": pse,
        }
    return ArmStats(
        order=order,
        n_pairs=len(classified),
        n_overlap=len(with_numbers),
        total_first_numbers=total_first,
        total_reappearing=total_reappearing,
        pooled_overlap=pooled,
        pooled_se=se,
        mean_overlap=(sum(overlaps) / len(overlaps)) if overlaps else None,
        mean_first_numbers=(
            sum(first_counts) / len(first_counts) if first_counts else None),
        mean_second_numbers=(
            sum(second_counts) / len(second_counts) if second_counts else None),
        by_provider=by_provider,
    )


def _extreme_split_p(n: int, k: int) -> float | None:
    """Two-sided binomial p under p=0.5, exact for the k==0/k==n extremes.

    Returns None for interior splits (the normal-curve shortcut is not
    needed when the sanity check is about detecting a degenerate corpus).
    """
    if n == 0 or k in (0, n):
        return 2.0 ** (1 - n) if n else None
    return None


def _verdict(arms: dict) -> tuple[str, str]:
    bull_arm = arms["bull_first"]
    bear_arm = arms["bear_first"]
    if bull_arm.n_pairs == 0 or bear_arm.n_pairs == 0:
        present = "bull_first" if bull_arm.n_pairs else "bear_first"
        return (
            "NOT MEASURED — no randomized-order corpus",
            f"every classifiable convene is {present} "
            f"(n={bull_arm.n_pairs + bear_arm.n_pairs}); the other arm is "
            "empty, and an anchoring verdict needs BOTH orders present. "
            "ROOM_DEBATE_ORDER_SEEDED is off live (docker exec ami_api_alpha env on melehost, "
            "2026-09-30) so alpha serves the fixed Bull-then-Bear order; step 2 is NO-GO "
            "until the flag is enabled and a fresh mixed-order corpus accumulates.",
        )
    p1, p2 = bull_arm.pooled_overlap, bear_arm.pooled_overlap
    if p1 is None or p2 is None:
        return "NOT MEASURED", "an arm has no first-speaker numbers to compare"
    delta = p1 - p2
    se = math.sqrt(
        (bull_arm.pooled_se or 0) ** 2 + (bear_arm.pooled_se or 0) ** 2
    )
    z = abs(delta) / se if se else float("inf")
    direction = ("bear-second anchors more" if delta > 0
                 else "bull-second anchors more")
    if abs(delta) >= _MATERIAL_DELTA and z >= 2:
        return (
            f"MEASURED ANCHORING — {direction}",
            f"pooled overlap bull-first {p1:.3f} vs bear-first {p2:.3f} "
            f"(delta {delta:+.3f}, z={z:.2f}; material>={_MATERIAL_DELTA}, "
            f"significance>=2SE)",
        )
    return (
        "NOT MEASURED",
        f"pooled overlap bull-first {p1:.3f} vs bear-first {p2:.3f} "
        f"(delta {delta:+.3f}, z={z:.2f}) — below the material/significance "
        "bar",
    )


def measure(window_days: int = 3) -> AnchoringReport:
    """Run the step-1 measurement over the last `window_days` days of llm_audit."""
    counts_out = run_psql(
        "SELECT user_id, "
        "COUNT(*) FILTER (WHERE agent_id=%s) AS bull_n, "
        "COUNT(*) FILTER (WHERE agent_id=%s) AS bear_n "
        "FROM llm_audit "
        "WHERE agent_id IN (%s, %s) AND created_at >= now() - interval %s "
        "GROUP BY user_id ORDER BY user_id;",
        [BULL, BEAR, BULL, BEAR, f"{int(window_days)} days"],
    )
    users: dict[str, dict] = {}
    batch_drivers = 0
    for line in counts_out.splitlines():
        line = line.strip()
        if not line:
            continue
        uid, bull_n, bear_n = line.split("|")
        bull_n, bear_n = int(bull_n), int(bear_n)
        if bear_n > 5:
            batch_drivers += 1
            continue
        if bull_n == 0 or bear_n == 0:
            continue  # a half-convene cannot pair; not counted as a pair
        users[uid] = {"bull_n": bull_n, "bear_n": bear_n}

    rows_out = run_psql(
        "SELECT row_to_json(t) FROM ("
        "SELECT user_id, agent_id, provider, created_at, response_text, "
        "system_prompt FROM llm_audit "
        "WHERE agent_id IN (%s, %s) AND created_at >= now() - interval %s "
        "ORDER BY user_id, created_at) t;",
        [BULL, BEAR, f"{int(window_days)} days"],
    )
    by_user: dict[str, dict] = {}
    for line in rows_out.splitlines():
        line = line.strip()
        if not line:
            continue
        row = json.loads(line)
        if row["user_id"] not in users:
            continue
        by_user.setdefault(row["user_id"], {}).setdefault(
            row["agent_id"], []).append(row)

    pairs: list[PairMeasurement] = []
    mismatched = 0
    for uid, agents in sorted(by_user.items()):
        bulls = agents.get(BULL, [])
        bears = agents.get(BEAR, [])
        if len(bulls) != len(bears):
            mismatched += abs(len(bulls) - len(bears))
        for nth, (bull, bear) in enumerate(zip(bulls, bears)):
            pairs.append(_measure_pair(uid, nth, bull, bear))

    order_split = Counter(p.order for p in pairs)
    n = order_split["bull_first"] + order_split["bear_first"]
    p_extreme = _extreme_split_p(n, order_split["bull_first"])

    arms = {
        "bull_first": _arm_stats("bull_first", pairs),
        "bear_first": _arm_stats("bear_first", pairs),
    }
    provider_mix = {
        key: dict(Counter(p.provider for p in pairs if p.order == key))
        for key in ("bull_first", "bear_first")
    }
    stance_by_order = {
        key: dict(Counter(
            f"{p.bull_stance or '?'} / {p.bear_stance or '?'}"
            for p in pairs if p.order == key
        ))
        for key in ("bull_first", "bear_first")
    }
    conviction_by_order = {
        key: dict(Counter(
            f"{p.bull_conviction or '?'} / {p.bear_conviction or '?'}"
            for p in pairs if p.order == key
        ))
        for key in ("bull_first", "bear_first")
    }
    verdict, verdict_detail = _verdict(arms)
    return AnchoringReport(
        window_days=window_days,
        user_ids_seen=len(users) + batch_drivers,
        batch_driver_user_ids=batch_drivers,
        pairs_total=len(pairs),
        pairs_classified=n,
        pairs_unclassified=order_split["unclassified"],
        pairs_missing_response=sum(
            1 for p in pairs if p.excluded_reason == "missing_response"),
        pairs_mismatched_counts=mismatched,
        order_split=dict(order_split),
        binomial_p_extreme=p_extreme,
        arms=arms,
        provider_mix=provider_mix,
        stance_by_order=stance_by_order,
        conviction_by_order=conviction_by_order,
        verdict=verdict,
        verdict_detail=verdict_detail,
    )


def main(argv: list | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CR247 Phase 2.4 step 1 — Bull/Bear anchoring measurement")
    parser.add_argument("--days", type=int, default=3,
                        help="llm_audit window in days (default 3)")
    args = parser.parse_args(argv)
    print(measure(window_days=args.days).render())
    return 0


if __name__ == "__main__":
    # Same bootstrap the tools/ entry points carry: make `library` importable
    # when invoked directly (`python -m library.anchoring` from backend/).
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    raise SystemExit(main())
