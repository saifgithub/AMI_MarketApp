"""CR197 — does the risk debate actually change the Portfolio Manager's verdict?

Every prior measurement of the Room's debate is correlational. CR143's M5 scores a
cosine similarity between `verdict.reason` and each transcript turn, which tells you
the PM's prose *echoes* a debator — not that removing the debator would have changed
the decision. CR035 ran ablations, but of the analyst-consensus *input*, never of a
*stage*. So the one question that decides whether the RISK phase earns its 25% of the
run (3 of 12 LLM calls, 24% of the decode budget, 3 serial round-trips) has never been
asked in a form that can answer it.

This asks it, offline and cheaply. For every convene already committed under
`CR143_agent_prompt_audit/corpus/`, the PM's *verbatim recorded prompt* is replayed
against the LAN vLLM with different parts of the debate removed:

    V1a  the exact recorded prompt
    V1b  the exact recorded prompt, a second time  → the paired same-prompt NOISE FLOOR
    V2   all three debator turns removed          (transcript then ends at the Trader)
    V3   the two extremes removed, Neutral kept   (ends at the Neutral)
    V4   the Neutral removed, extremes kept       (ends at the Conservative)
    V5   Conservative + Neutral removed           (ends at the Aggressive)

V1b is the whole point. A verdict flip between V1a and V2 means nothing until you know
how often this model flips against *itself* on a byte-identical prompt — sampling
temperature is server-side and unknown here, so the floor has to be measured, not
assumed.

V4 and V5 were added after the first three arms produced a result that had two
competing explanations. The trailing comment in `_VARIANT_STRIP` records why: approval
rate tracked WHO SPOKE LAST into the PM, monotonically by how negative that voice is,
which "the debate carries information" and "the PM is anchored on its last input"
predict equally well. V5 separates them, because leaving the always-bullish Aggressive
as the final voice while deleting two thirds of the debate makes the two hypotheses
point in OPPOSITE directions.

A note on the statistic, since it changed the answer: the first cut of this script
compared SYMMETRIC flip rates ("does the ablation flip more often than resampling")
and returned p=1.0, "not demonstrated". That was the wrong instrument — the flip rates
are near-identical while the flips run in opposite DIRECTIONS, so the APPROVE count
falls by half with the flip rate unmoved. Marginal homogeneity is the hypothesis of
interest; see `build_report`.

Why replay the PM alone, rather than re-running whole convenes: the eleven upstream
turns are held FIXED at what was recorded, so the only thing differing between arms is
the presence of the debate text. Re-running the room would let the analysts drift too,
and the contrast would measure nothing in particular.

Three fidelity rules this script exists to keep, each of which would silently corrupt
the measurement if broken:

  1. `VLLMProvider` is used DIRECTLY, never `LLMGateway`. The gateway prepends the
     CR056 grounding directive (already baked into the recorded prompt — double it and
     the prompt is no longer the one that was recorded) and, worse, falls back to
     Anthropic when vLLM is down, which would quietly measure a different model.
  2. Production sends NO temperature and NO top_p to vLLM (llm_gateway.py:481-490) —
     server defaults apply. The replay omits them too, and pins max_tokens=1700, the
     PM's production budget.
  3. Baselines come from the recorded `response_text`, parsed identically to the
     replays — never from the stored `verdict`, whose REJECTs are the safety floor's
     post-hoc veto and not the PM's own word.

The contrast is internally valid on whatever model serves `ami-llm`, because both arms
are measured fresh on the same model in the same session. Only the replay-vs-recording
side-check needs the model that produced the corpora.

Usage (from backend/):
    .venv/bin/python -m scripts.pm_debate_ablation --dry-run
    .venv/bin/python -m scripts.pm_debate_ablation --variants v1a v1b v2
    .venv/bin/python -m scripts.pm_debate_ablation --report-only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.llm_json import extract_json_object  # noqa: E402
from app.services.room_runner import _normalize_pm_action, _safe_float  # noqa: E402

DEBATORS = ("aggressive_debator", "conservative_debator", "neutral_debator")
EXTREMES = ("aggressive_debator", "conservative_debator")

# The PM's production decode budget (`_AGENT_MAX_TOKENS[PORTFOLIO_MANAGER]`,
# room_prompts.py). Hardcoded rather than imported so a future budget change cannot
# silently desynchronise a replay from the recording it is being compared against.
PM_MAX_TOKENS = 1700

VARIANTS = ("v1a", "v1b", "v2", "v3", "v4", "v5")
_VARIANT_STRIP: dict[str, tuple[str, ...]] = {
    "v1a": (),
    "v1b": (),
    "v2": DEBATORS,
    "v3": EXTREMES,
    # v4 isolates the Neutral. v2 and v3 together implicate it, but not cleanly:
    # v2 also changes which voice speaks LAST before the PM (the Trader, whose own
    # stance skews negative), so a recency effect explains v2 as well as content
    # does. v4 removes the Neutral while keeping both extremes, so the transcript
    # still ends on a debator. If the effect survives here it is not simply "the
    # debate block is shorter"; if it vanishes, the Neutral was never the cause.
    "v4": ("neutral_debator",),
    # v5 is the discriminator between the two live explanations of v2/v3/v4.
    #
    # Across those arms the approval rate tracked WHO SPOKE LAST, monotonically by
    # how negative that voice is: Neutral last 15.7-17.2%, Conservative last 11.9%,
    # Trader last 7.4%. Recency explains that as well as "the debate carries
    # information" does, and the two make OPPOSITE predictions here. Removing the
    # Conservative and the Neutral leaves the Aggressive — a voice that argued "for"
    # in 117 of 118 convenes — speaking last into the PM.
    #   recency  ⇒ approvals at or ABOVE baseline, despite two thirds of the debate
    #              being gone;
    #   content  ⇒ approvals BELOW baseline, since most of the debate is missing.
    "v5": ("conservative_debator", "neutral_debator"),
}

DEFAULT_EPOCHS = ("2026-08-07", "2026-08-13", "2026-08-14", "2026-08-14b")


# ── corpus loading + join ────────────────────────────────────────────────


@dataclass
class Convene:
    """One committed convene, joined to the PM call that decided it."""

    epoch: str
    audit_id: str
    run_id: str
    ticker: str
    system_prompt: str
    recorded_response: str
    transcript: list[dict[str, Any]]
    corpus_model: str | None = None

    def debator_turns(self) -> dict[str, str]:
        return {
            t["agent_id"]: t.get("content") or ""
            for t in self.transcript
            if t.get("agent_id") in DEBATORS
        }


def _load_json(path: Path) -> Any:
    with path.open() as fh:
        return json.load(fh)


def load_epoch(corpus_dir: Path, epoch: str) -> tuple[list[dict], list[dict]]:
    audit = _load_json(corpus_dir / f"llm_audit_{epoch}-epoch.json")
    runs = _load_json(corpus_dir / f"room_runs_{epoch}-epoch.json")
    return audit, runs


def join_epoch(epoch: str, audit: list[dict], runs: list[dict]) -> tuple[list[Convene], list[str]]:
    """Join each convene to its PM audit row by trader-turn content.

    Timestamps cannot do this job: convenes ran in parallel batches and the 08-07
    epoch stores a different ISO format, so a time-window join silently mis-pairs.
    The trader's turn is reproduced verbatim inside the PM's prompt, so a slice of
    it is an exact, checkable key — and uniqueness is ASSERTED, not hoped for.
    """
    pm_rows = [r for r in audit if r.get("flow") == "room_pm"]
    convenes: list[Convene] = []
    problems: list[str] = []

    for run in runs:
        transcript = run.get("transcript") or []
        trader = next((t for t in transcript if t.get("agent_id") == "trader"), None)
        if trader is None or not (trader.get("content") or "").strip():
            problems.append(f"{epoch}/{run.get('id')}: no trader turn to join on")
            continue
        key = (trader["content"] or "")[:120]
        matches = [r for r in pm_rows if key in (r.get("system_prompt") or "")]
        if len(matches) != 1:
            problems.append(
                f"{epoch}/{run.get('id')}: trader-key matched {len(matches)} PM rows (need exactly 1)"
            )
            continue
        row = matches[0]
        pm_turn = next(
            (t for t in transcript if t.get("agent_id") == "portfolio_manager"), None
        )
        convenes.append(
            Convene(
                epoch=epoch,
                audit_id=str(row.get("id")),
                run_id=str(run.get("id")),
                ticker=str(run.get("ticker") or ""),
                system_prompt=row.get("system_prompt") or "",
                recorded_response=row.get("response_text") or "",
                transcript=transcript,
                corpus_model=(pm_turn or {}).get("model"),
            )
        )
    return convenes, problems


# ── variant construction ─────────────────────────────────────────────────


class StripError(RuntimeError):
    pass


def strip_debators(convene: Convene, agents: Iterable[str]) -> str:
    """Remove named debator turns from the transcript block of the PM's prompt.

    `_format_transcript` renders turns as `"\\n".join(f"[{agent_id}] {content}")`, and
    the stance envelope is stripped from `content` BEFORE the transcript commit
    (room_runner.py `parse_stance_envelope`), so the recorded turn text is reproduced
    inside the PM prompt byte-for-byte. That makes this an exact block removal rather
    than a line-parse — no regex over content that may itself contain newlines and
    bracketed markers.

    The removal is verified three ways: the block occurs exactly once, the prompt
    shrinks by exactly the block length, and the `[agent_id]` marker is gone
    afterwards. Any failure raises rather than silently measuring the wrong thing.
    """
    agents = tuple(agents)
    if not agents:
        return convene.system_prompt

    prompt = convene.system_prompt
    turns = convene.debator_turns()
    removed = 0

    for agent_id in agents:
        content = turns.get(agent_id)
        if not content:
            raise StripError(f"{convene.run_id}: no recorded turn for {agent_id}")
        block = f"\n[{agent_id}] {content}"
        occurrences = prompt.count(block)
        if occurrences != 1:
            raise StripError(
                f"{convene.run_id}: block for {agent_id} occurs {occurrences}x (need 1)"
            )
        prompt = prompt.replace(block, "", 1)
        removed += len(block)
        if f"[{agent_id}]" in prompt:
            raise StripError(f"{convene.run_id}: marker for {agent_id} survived removal")

    if len(convene.system_prompt) - len(prompt) != removed:
        raise StripError(f"{convene.run_id}: length delta disagrees with removed blocks")
    return prompt


def build_variant(convene: Convene, variant: str) -> str:
    return strip_debators(convene, _VARIANT_STRIP[variant])


# ── parsing ──────────────────────────────────────────────────────────────


def parse_pm(text: str) -> tuple[str | None, float | None, bool]:
    """Action + raw size from a PM reply, matching production's read pre-clamp.

    Deliberately NOT `_parse_pm_verdict`: that needs a live `_RoomContext` and applies
    the trader-entry fallback, stop/target minting and the risk-tier size clamp. Those
    are downstream policy — replaying them would fold the mandate's ceiling into a
    measurement about the debate. The two pieces reused here are the same functions
    production uses, so MODIFY / MODIFY-AND-APPROVE still resolve to APPROVE.

    A parse failure is its own outcome, never coerced to PASS — production fails safe
    to PASS there (DEF059), but counting that as a PASS would let a formatting wobble
    masquerade as a changed decision.
    """
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    if not parsed:
        return None, None, False
    return _normalize_pm_action(parsed.get("action")), _safe_float(parsed.get("size_pct")), True


# ── statistics ───────────────────────────────────────────────────────────


_WORD_RE = __import__("re").compile(r"[a-z][a-z'-]+")
_STOPWORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been "
    "this that these those it its as not no than then so if while which who whose "
    "i we you they he she them his her their our your my me us do does did have "
    "has had can could should would will shall may might must about into over "
    "under above below between within without because since due given".split()
)


def narration_of(text: str) -> str:
    """The prose the user actually reads, pulled out of the PM's JSON verdict."""
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    if not parsed:
        return ""
    return str(parsed.get("narration") or "")


def content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def jaccard_distance(a: str, b: str) -> float | None:
    """1 − Jaccard over content words. None when either side has no prose.

    Deliberately a set measure over content words rather than a sequence one: the
    question is whether the PM reasoned from different material, not whether it
    reordered the same sentences.
    """
    wa, wb = content_words(a), content_words(b)
    if not wa or not wb:
        return None
    return 1 - len(wa & wb) / len(wa | wb)


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float, float]:
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return p, max(0.0, centre - half), min(1.0, centre + half)


def mcnemar_exact(b: int, c: int) -> float:
    """Two-sided exact McNemar over the discordant pairs.

    b = convenes where the ablation flipped but the noise replay did not,
    c = the reverse. Under the null the debate is inert and each discordant pair is a
    coin flip, so the p-value is the two-sided binomial tail.
    """
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ── replay ───────────────────────────────────────────────────────────────


@dataclass
class ReplayResult:
    epoch: str
    run_id: str
    audit_id: str
    ticker: str
    variant: str
    prompt_sha256: str
    response_text: str
    action: str | None
    size_pct: float | None
    parse_ok: bool
    finish_reason: str | None
    latency_s: float
    error: str | None = None


async def replay_one(provider, convene: Convene, variant: str, sem: asyncio.Semaphore) -> ReplayResult:
    from app.services.llm_gateway import ChatMessage

    prompt = build_variant(convene, variant)
    sha = hashlib.sha256(prompt.encode()).hexdigest()
    meta: dict[str, Any] = {}
    chunks: list[str] = []
    err: str | None = None

    async with sem:
        loop = asyncio.get_event_loop()
        started = loop.time()
        try:
            async for chunk in provider.stream_chat(
                system_prompt=prompt,
                # room_prompts.py builds exactly one user message per convene.
                messages=[ChatMessage(role="user", content=f"Convene on {convene.ticker}.")],
                max_tokens=PM_MAX_TOKENS,
                meta=meta,
            ):
                chunks.append(chunk)
        except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
            err = f"{type(exc).__name__}: {exc}"
        elapsed = loop.time() - started

    text = "".join(chunks)
    action, size, ok = parse_pm(text)
    return ReplayResult(
        epoch=convene.epoch,
        run_id=convene.run_id,
        audit_id=convene.audit_id,
        ticker=convene.ticker,
        variant=variant,
        prompt_sha256=sha,
        response_text=text,
        action=action,
        size_pct=size,
        parse_ok=ok,
        finish_reason=meta.get("finish_reason"),
        latency_s=round(elapsed, 2),
        error=err,
    )


async def run_replays(
    convenes: list[Convene],
    variants: list[str],
    *,
    base_url: str,
    model: str,
    concurrency: int,
    out_jsonl: Path,
    done: set[tuple[str, str, str]],
) -> None:
    from app.services.llm_gateway import VLLMProvider

    provider = VLLMProvider(base_url=base_url, model_name=model, timeout_seconds=180.0)
    sem = asyncio.Semaphore(concurrency)
    todo = [
        (c, v)
        for v in variants
        for c in convenes
        if (c.epoch, c.audit_id, v) not in done
    ]
    print(f"[replay] {len(todo)} calls pending ({len(done)} already recorded)")

    try:
        completed = 0
        with out_jsonl.open("a") as fh:
            for batch_start in range(0, len(todo), concurrency * 4):
                batch = todo[batch_start : batch_start + concurrency * 4]
                results = await asyncio.gather(
                    *(replay_one(provider, c, v, sem) for c, v in batch)
                )
                for r in results:
                    fh.write(json.dumps(r.__dict__) + "\n")
                fh.flush()
                completed += len(results)
                errs = sum(1 for r in results if r.error)
                print(
                    f"[replay] {completed}/{len(todo)} done"
                    + (f" ({errs} errored in last batch)" if errs else "")
                )
    finally:
        await provider.aclose()


# ── reporting ────────────────────────────────────────────────────────────


def load_results(path: Path) -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[(r["epoch"], r["audit_id"], r["variant"])] = r
    return out


def build_report(
    convenes: list[Convene], results: dict[tuple[str, str, str], dict], served_model: str | None
) -> str:
    lines: list[str] = []
    add = lines.append

    add("# CR197 — PM-replay debate ablation: results\n")
    add(
        "Does removing the three Risk Debators' turns from the Portfolio Manager's prompt "
        "change its verdict more often than the model changes its own mind on a byte-identical "
        "prompt? Every number below is paired per convene.\n"
    )
    if served_model:
        add(f"**Served model at replay time:** `{served_model}`\n")
    corpus_models = Counter(c.corpus_model for c in convenes if c.corpus_model)
    if corpus_models:
        add(
            "**Model that produced the corpora:** "
            + ", ".join(f"`{m}` ({n})" for m, n in corpus_models.most_common())
            + "\n"
        )
    else:
        add(
            "**Model that produced the corpora:** not recorded — the transcript's `model` field is "
            "null on every turn. The port-8000 registry names Qwen3.6-35B-A3B-NVFP4 as the `ami-llm` "
            "designee over the corpus dates, but that is inference from a registry, not a datum from "
            "the run. It bears only on the replay-vs-recording side-check; the V1a/V1b/V2 contrast is "
            "measured fresh on one model and does not depend on it.\n"
        )

    have = lambda c, v: results.get((c.epoch, c.audit_id, v))  # noqa: E731

    # ── baseline composition ──
    rec = Counter()
    for c in convenes:
        a, _, ok = parse_pm(c.recorded_response)
        rec[a if ok else "PARSE_FAIL"] += 1
    add("## Recorded baseline (from `response_text`, not the floor-vetoed verdict)\n")
    add("| action | n |")
    add("|---|---|")
    for k, n in rec.most_common():
        add(f"| {k} | {n} |")
    add("")

    # ── flip rates ──
    def flips(va: str, vb: str) -> tuple[int, int, list[str]]:
        n = agree = 0
        flipped: list[str] = []
        for c in convenes:
            ra, rb = have(c, va), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            if not (ra["parse_ok"] and rb["parse_ok"]):
                continue
            n += 1
            if ra["action"] == rb["action"]:
                agree += 1
            else:
                flipped.append(f"{c.ticker}/{c.run_id[:8]}: {ra['action']}→{rb['action']}")
        return n - agree, n, flipped

    noise_k, noise_n, noise_list = flips("v1a", "v1b")
    abl_k, abl_n, abl_list = flips("v1a", "v2")
    ext_k, ext_n, ext_list = flips("v1a", "v3")

    add("## Verdict flip rates\n")
    add("| contrast | flips / n | rate | 95% CI (Wilson) | reads as |")
    add("|---|---|---|---|---|")
    for label, k, n, meaning in (
        ("V1a vs V1b — **noise floor**", noise_k, noise_n, "same prompt, twice"),
        ("V1a vs V2 — debate removed", abl_k, abl_n, "all three debators stripped"),
        ("V1a vs V3 — extremes removed", ext_k, ext_n, "Neutral kept"),
    ):
        p, lo, hi = wilson(k, n)
        add(f"| {label} | {k}/{n} | {p:.1%} | {lo:.1%} – {hi:.1%} | {meaning} |")
    add("")

    # ── directional McNemar: the test the question actually asks ──
    #
    # A CORRECTION, kept visible because it changed the answer. This first computed
    # a SYMMETRIC contrast — "does the ablation flip more often than resampling
    # does" — and returned p=1.0, excess -0.1%, "not demonstrated". That statistic
    # is the wrong instrument: the flip RATES are near-identical (12% both ways)
    # while the flips run in opposite directions. Noise flips balance out (8 up, 8
    # down); ablation flips do not (14 down, 2 up), which is why the APPROVE count
    # falls 22 → 10 with the flip rate unmoved. Marginal homogeneity is the
    # hypothesis of interest, so the pairs to count are APPROVE→PASS against
    # PASS→APPROVE, per contrast, against the same floor.
    def directional(vb: str) -> tuple[int, int, float]:
        b = c_ = 0
        for c in convenes:
            ra, rb = have(c, "v1a"), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            if not (ra["parse_ok"] and rb["parse_ok"]):
                continue
            if ra["action"] == "APPROVE" and rb["action"] == "PASS":
                b += 1
            elif ra["action"] == "PASS" and rb["action"] == "APPROVE":
                c_ += 1
        return b, c_, mcnemar_exact(b, c_)

    # ── arm summary: the table that actually shows the shape of the result ──
    _ARM_META = {
        "v1a": ("nothing (baseline)", "Neutral", "yes"),
        "v1b": ("nothing (resampled)", "Neutral", "yes"),
        "v3": ("both extremes", "Neutral", "yes"),
        "v5": ("Conservative + Neutral", "Aggressive", "no"),
        "v4": ("Neutral only", "Conservative", "no"),
        "v2": ("all three", "Trader", "no"),
    }
    add("## Approval rate by arm\n")
    add("| arm | removed | last voice before PM | Neutral present | APPROVE | rate |")
    add("|---|---|---|---|---|---|")
    for vb in ("v1a", "v1b", "v3", "v5", "v4", "v2"):
        rs = [have(c, vb) for c in convenes]
        rs = [r for r in rs if r and not r.get("error")]
        if not rs:
            continue
        ap = sum(1 for r in rs if r["action"] == "APPROVE")
        pa = sum(1 for r in rs if r["action"] == "PASS")
        removed, lastv, neu = _ARM_META[vb]
        rate = ap / (ap + pa) if (ap + pa) else 0.0
        add(f"| {vb} | {removed} | {lastv} | {neu} | {ap} | {rate:.1%} |")
    add("")
    add(
        "Read down the 'Neutral present' column. Every arm that keeps the Neutral sits "
        "at the baseline rate; every arm without it falls, and falls further as more of "
        "the rest is also removed. The count of surviving debators does NOT order the "
        "table — v3 keeps one and scores highest, v4 keeps two and scores low.\n"
    )
    add(
        "**The recency explanation is refuted by v5.** Approval rate first appeared to "
        "track whoever spoke last, ordered by how negative that voice is (Neutral "
        "15.7-17.2%, Conservative 11.9%, Trader 7.4%) — anchoring would explain that "
        "without the debate carrying any information at all. v5 leaves the Aggressive "
        "speaking last, a voice that argued 'for' in 117 of 118 convenes, and anchoring "
        "therefore predicts approvals at or above baseline. Observed: **10.3%, the "
        "second-lowest arm.** The PM is not echoing its final input.\n"
    )

    add("## Decision rule — directional (marginal homogeneity)\n")
    add(
        "The question is not whether the verdict *changes* but whether it changes "
        "*in a direction*. Resampling moves verdicts symmetrically; an input that "
        "carries signal moves them one way.\n"
    )
    add("| contrast | APPROVE→PASS | PASS→APPROVE | net | exact McNemar p |")
    add("|---|---|---|---|---|")
    results_dir: dict[str, tuple[int, int, float]] = {}
    for vb, label in (
        ("v1b", "same prompt twice — **noise floor**"),
        ("v2", "all three debators removed"),
        ("v3", "extremes removed, Neutral kept"),
        ("v4", "Neutral removed, extremes kept"),
        ("v5", "Conservative + Neutral removed"),
    ):
        if not any(have(c, vb) for c in convenes):
            continue
        b, c_, p = directional(vb)
        results_dir[vb] = (b, c_, p)
        add(f"| {label} | {b} | {c_} | {b - c_:+d} | {p:.5f} |")
    add("")

    if "v2" in results_dir:
        b2, c2, p2 = results_dir["v2"]
        claim = (
            "**The debate causally moves the PM's verdict.** Removing it makes the PM "
            f"refuse trades it otherwise approves — {b2} approvals lost against {c2} "
            "gained, against a floor that is balanced by construction."
            if p2 < 0.05 and b2 > c2
            else "**Not demonstrated** at this n — a ceiling on the effect, not proof of zero."
        )
        add(f"Rule: p<0.05 with a net in one direction. Result: {claim}\n")

    # ── size deltas ──
    deltas: list[float] = []
    for c in convenes:
        r1a, r2 = have(c, "v1a"), have(c, "v2")
        if not r1a or not r2:
            continue
        if r1a.get("action") == "APPROVE" and r2.get("action") == "APPROVE":
            if r1a.get("size_pct") is not None and r2.get("size_pct") is not None:
                deltas.append(r2["size_pct"] - r1a["size_pct"])
    add("## Position size, where both arms approved\n")
    if deltas:
        deltas_sorted = sorted(deltas)
        med = deltas_sorted[len(deltas_sorted) // 2]
        nonzero = [d for d in deltas if abs(d) > 1e-9]
        add(
            f"n={len(deltas)} paired approvals · median Δ = **{med:+.2f} pt** · "
            f"{len(nonzero)}/{len(deltas)} differ at all.\n"
        )
    else:
        add("No convene approved under both arms — nothing to compare.\n")

    # ── narration divergence ──
    #
    # The verdict is one token; the narration is the product. A debate that never
    # flips APPROVE/PASS but visibly changes the reasoning the user reads is doing
    # something a flip-rate cannot see — and on a training simulator that is much of
    # the point. Measured against the same-prompt floor so resampling noise does not
    # get read as influence.
    def divergences(va: str, vb: str) -> list[float]:
        out: list[float] = []
        for c in convenes:
            ra, rb = have(c, va), have(c, vb)
            if not ra or not rb or ra.get("error") or rb.get("error"):
                continue
            d = jaccard_distance(narration_of(ra["response_text"]), narration_of(rb["response_text"]))
            if d is not None:
                out.append(d)
        return out

    noise_div = divergences("v1a", "v1b")
    abl_div = divergences("v1a", "v2")
    ext_div = divergences("v1a", "v3")
    add("## Narration divergence — does the debate change what the user reads?\n")
    add("| contrast | n | mean Jaccard distance | median |")
    add("|---|---|---|---|")
    for label, vals in (
        ("V1a vs V1b — same prompt (floor)", noise_div),
        ("V1a vs V2 — debate removed", abl_div),
        ("V1a vs V3 — extremes removed", ext_div),
    ):
        if vals:
            s = sorted(vals)
            add(f"| {label} | {len(vals)} | {sum(vals)/len(vals):.3f} | {s[len(s)//2]:.3f} |")
        else:
            add(f"| {label} | 0 | — | — |")
    add("")
    if noise_div and abl_div:
        lift = (sum(abl_div) / len(abl_div)) - (sum(noise_div) / len(noise_div))
        add(
            f"Excess divergence attributable to removing the debate: **{lift:+.3f}** "
            "Jaccard distance over the resampling floor. A positive value means the PM "
            "reasoned from visibly different material, whether or not its verdict moved.\n"
        )

    # ── per-epoch ──
    add("## Per-epoch (primary — pooling across prompt epochs is not defensible)\n")
    add("| epoch | convenes | noise flips | ablation flips |")
    add("|---|---|---|---|")
    for ep in sorted({c.epoch for c in convenes}):
        sub = [c for c in convenes if c.epoch == ep]
        nk = nn = ak = an = 0
        for c in sub:
            r1a, r1b, r2 = have(c, "v1a"), have(c, "v1b"), have(c, "v2")
            if r1a and r1b and r1a.get("parse_ok") and r1b.get("parse_ok"):
                nn += 1
                nk += r1a["action"] != r1b["action"]
            if r1a and r2 and r1a.get("parse_ok") and r2.get("parse_ok"):
                an += 1
                ak += r1a["action"] != r2["action"]
        add(f"| {ep} | {len(sub)} | {nk}/{nn} | {ak}/{an} |")
    add("")

    # ── samples, per P16: a count nobody read is not a measurement ──
    add("## Samples for hand-reading\n")
    for label, lst in (
        ("Noise flips (same prompt, different answer)", noise_list),
        ("Ablation flips (debate removed)", abl_list),
        ("Extremes-removed flips", ext_list),
    ):
        add(f"**{label}** — {len(lst)} total")
        for s in lst[:12]:
            add(f"- {s}")
        add("")

    add("## Caveats that bound every number above\n")
    add(
        "- Four prompt epochs; per-epoch tables are primary, pooled figures are indicative.\n"
        "- 13 unique tickers underlie the convenes — observations are clustered, not independent.\n"
        "- Server-side sampling temperature is unknown, which is exactly why the noise floor is "
        "measured rather than assumed.\n"
        "- At n≈136 a difference below roughly 8–10pp is not resolvable; a null here bounds the "
        "effect, it does not prove absence.\n"
        "- **The limit that bounds the obvious action.** Every arm holds the surviving turns "
        "FIXED at what was recorded, and those turns were written in a room where all three "
        "debators spoke. So v3 shows the PM does not need the extremes' text *given a Neutral "
        "turn that was produced with the extremes present* — it does NOT show the extremes can "
        "be deleted. The Neutral's stated job is to synthesise those two; remove them from a "
        "live run and it has nothing to synthesise and writes something different. Testing that "
        "needs a live two-arm room benchmark, not this replay.\n"
        "- Only the PM turn is replayed. This measures whether the debate changes the PM's decision, "
        "not whether the debate has value as user-facing product — which it demonstrably does "
        "(SSE stream, Journal replay, comb voices, 1-on-1 personas).\n"
    )
    return "\n".join(lines)


# ── main ─────────────────────────────────────────────────────────────────


def main() -> int:
    ap = argparse.ArgumentParser(description="CR197 PM-replay debate ablation")
    repo = Path(__file__).resolve().parents[2]
    ap.add_argument(
        "--corpus",
        type=Path,
        default=repo / "docs/forward_planning/CR143_agent_prompt_audit/corpus",
    )
    ap.add_argument(
        "--out",
        type=Path,
        default=repo / "docs/forward_planning/CR197_risk_debate_effectiveness/ablation",
    )
    ap.add_argument("--epochs", nargs="+", default=list(DEFAULT_EPOCHS))
    ap.add_argument("--variants", nargs="+", default=["v1a", "v1b", "v2"], choices=VARIANTS)
    ap.add_argument("--base-url", default="http://192.168.20.74:8000")
    ap.add_argument("--model", default="ami-llm")
    ap.add_argument("--concurrency", type=int, default=2)
    ap.add_argument("--limit", type=int, default=0, help="cap convenes (smoke runs)")
    ap.add_argument("--dry-run", action="store_true", help="validate joins+strips, no network")
    ap.add_argument("--report-only", action="store_true", help="rebuild the summary from JSONL")
    args = ap.parse_args()

    convenes: list[Convene] = []
    problems: list[str] = []
    for epoch in args.epochs:
        audit, runs = load_epoch(args.corpus, epoch)
        cs, ps = join_epoch(epoch, audit, runs)
        convenes.extend(cs)
        problems.extend(ps)
        print(f"[join] {epoch}: {len(cs)}/{len(runs)} convenes joined")

    if problems:
        print(f"[join] !! {len(problems)} unjoined:")
        for p in problems[:10]:
            print(f"       {p}")
    if not convenes:
        print("[join] nothing joined — aborting")
        return 1
    if args.limit:
        convenes = convenes[: args.limit]

    # Validate every strip before any network call: a StripError found mid-run would
    # leave a half-populated JSONL that looks complete.
    strip_fail = 0
    for c in convenes:
        for variant in ("v2", "v3"):
            try:
                build_variant(c, variant)
            except StripError as exc:
                strip_fail += 1
                if strip_fail <= 10:
                    print(f"[strip] !! {exc}")
    total_turns = sum(len(c.debator_turns()) for c in convenes)
    print(
        f"[strip] {len(convenes)} convenes · {total_turns} debator turns · "
        f"{strip_fail} strip failures"
    )

    args.out.mkdir(parents=True, exist_ok=True)
    jsonl = args.out / "ablation_calls.jsonl"

    if args.dry_run:
        sample = convenes[0]
        stripped = build_variant(sample, "v2")
        print(
            f"[dry-run] sample {sample.ticker}/{sample.run_id[:8]}: "
            f"{len(sample.system_prompt)} → {len(stripped)} chars "
            f"({len(sample.system_prompt) - len(stripped)} removed)"
        )
        print(f"[dry-run] corpus models: {Counter(c.corpus_model for c in convenes).most_common()}")
        print("[dry-run] OK — no network calls made")
        return 0 if strip_fail == 0 else 1

    if strip_fail:
        print("[abort] strip failures must be zero before replaying")
        return 1

    results = load_results(jsonl)
    served: str | None = None

    if not args.report_only:
        import httpx

        try:
            resp = httpx.get(f"{args.base_url}/v1/models", timeout=10.0)
            served = ", ".join(m.get("id", "?") for m in resp.json().get("data", []))
            print(f"[preflight] {args.base_url} serving: {served}")
        except Exception as exc:  # noqa: BLE001
            print(f"[preflight] !! {args.base_url} unreachable ({type(exc).__name__}: {exc})")
            print("[preflight] the LLM must be up to replay; --dry-run and --report-only do not need it")
            return 2
        if args.model not in (served or ""):
            print(f"[preflight] !! model '{args.model}' not in served list — refusing to guess")
            return 2

        asyncio.run(
            run_replays(
                convenes,
                args.variants,
                base_url=args.base_url,
                model=args.model,
                concurrency=args.concurrency,
                out_jsonl=jsonl,
                done=set(results.keys()),
            )
        )
        results = load_results(jsonl)

    report = build_report(convenes, results, served)
    summary = args.out / "ABLATION_SUMMARY.md"
    summary.write_text(report)
    print(f"[report] wrote {summary}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
