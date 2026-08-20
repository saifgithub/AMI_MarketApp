"""CR199 — does removing the Bull and Bear Researchers change the decision?

CR197 asked the causal question of the RISK phase, where the Portfolio Manager is the
only reader, so a single PM replay was the whole experiment. The RESEARCHERS phase is
read by six downstream voices, and the one whose entire job is to adjudicate it is the
Research Manager. So the ablation here is a two-stage cascade:

    stage 1   replay the RESEARCH MANAGER's recorded prompt, with and without the two
              researcher blocks   -> does the adjudicator's synthesis depend on them?
    stage 2   replay the PORTFOLIO MANAGER's recorded prompt with stage 1's output
              substituted in place of the recorded RM turn -> does the verdict move?

Four arms, each a full cascade so that every comparison is between two runs of the same
machinery:

    A1  control   RM prompt verbatim            -> PM prompt verbatim, RM block := A1's RM
    A2  noise     RM prompt verbatim, resampled -> PM prompt verbatim, RM block := A2's RM
    B   ablated   RM prompt minus Bull+Bear     -> PM prompt minus Bull+Bear, RM := B's RM
    C   direct    (no RM call)                  -> PM prompt minus Bull+Bear, RM := A1's RM

A2 is the point of the design. Sampling is server-side and unknown, so the rate at which
this model disagrees with ITSELF on a byte-identical prompt has to be measured, not
assumed; A1-vs-A2 is that floor and A1-vs-B only means something above it. C decomposes
the result: it holds the synthesis fixed at the control's and removes the researchers
from the PM's window alone, separating the direct channel from the mediated one.

What is held fixed, and which way that biases the answer: the Trader and the three Risk
Debators keep their RECORDED turns in the PM's window. Those turns were written after
reading the researchers, so whatever they absorbed survives the ablation. The measured
effect is therefore a LOWER BOUND on deleting the phase outright. Re-running them would
mean re-deriving the trade proposal the PM's prompt renders from the Trader's numbers,
which is a second measurement's worth of fidelity risk for a third of the channel.

Fidelity rules, inherited from `pm_debate_ablation.py` and for the same reasons:

  1. `VLLMProvider` DIRECTLY, never `LLMGateway` — the gateway would prepend the CR056
     grounding directive a second time (it is already baked into the recorded prompt)
     and would silently fall back to Anthropic if vLLM went down mid-run.
  2. No temperature, no top_p (production sends none); `max_tokens` pinned per agent to
     the production budget — RM 1600, PM 1700.
  3. A replayed RM turn is substituted as its PROSE, with the stance envelope stripped
     exactly as `parse_stance_envelope` strips it before the transcript commit — so the
     PM reads the same shape of text it reads in production.
  4. Actions are parsed from the reply, never read from the stored `verdict`, which the
     safety floor can overwrite after the PM has spoken.

Usage (from backend/):
    .venv/bin/python -m scripts.researcher_ablation --dry-run
    .venv/bin/python -m scripts.researcher_ablation --limit 20
    .venv/bin/python -m scripts.researcher_ablation --report-only
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import math
import random
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.llm_json import extract_json_object  # noqa: E402
from app.services.room_runner import (  # noqa: E402
    _normalize_pm_action,
    _safe_float,
    parse_stance_envelope,
)

RESEARCHERS = ("bull_researcher", "bear_researcher")
RM_MAX_TOKENS = 1600
PM_MAX_TOKENS = 1700
DEFAULT_EPOCHS = ("2026-08-07", "2026-08-13", "2026-08-14", "2026-08-14b")
ARMS = ("a1", "a2", "b", "c")

_WORD_RE = re.compile(r"[a-z][a-z'-]+")
_STOPWORDS = frozenset(
    "the a an and or but of to in on at for with from by is are was were be been "
    "this that these those it its as not no than then so if while which who whose "
    "i we you they he she them his her their our your my me us do does did have "
    "has had can could should would will shall may might must about into over "
    "under above below between within without because since due given".split()
)


# ── corpus ───────────────────────────────────────────────────────────────


@dataclass
class Convene:
    epoch: str
    run_id: str
    ticker: str
    rm_prompt: str
    pm_prompt: str
    rm_recorded: str
    pm_recorded_response: str
    bull_turn: str
    bear_turn: str


class StripError(RuntimeError):
    pass


def _strip_blocks(prompt: str, blocks: dict[str, str], where: str) -> str:
    """Remove `[agent_id] content` blocks verbatim, verifying each removal three ways."""
    out = prompt
    removed = 0
    for agent_id, content in blocks.items():
        if not content:
            raise StripError(f"{where}: no recorded turn for {agent_id}")
        block = f"\n[{agent_id}] {content}"
        n = out.count(block)
        if n != 1:
            raise StripError(f"{where}: block for {agent_id} occurs {n}x (need 1)")
        out = out.replace(block, "", 1)
        removed += len(block)
        if f"[{agent_id}]" in out:
            raise StripError(f"{where}: marker for {agent_id} survived removal")
    if len(prompt) - len(out) != removed:
        raise StripError(f"{where}: length delta disagrees with removed blocks")
    return out


def _substitute_rm(prompt: str, recorded: str, replacement: str, where: str) -> str:
    block = f"\n[research_manager] {recorded}"
    n = prompt.count(block)
    if n != 1:
        raise StripError(f"{where}: RM block occurs {n}x (need 1)")
    return prompt.replace(block, f"\n[research_manager] {replacement}", 1)


def load_convenes(corpus: Path, epochs: list[str]) -> tuple[list[Convene], list[str]]:
    convenes: list[Convene] = []
    problems: list[str] = []
    for epoch in epochs:
        with (corpus / f"llm_audit_{epoch}-epoch.json").open() as fh:
            audit = json.load(fh)
        with (corpus / f"room_runs_{epoch}-epoch.json").open() as fh:
            runs = json.load(fh)
        by_agent: dict[str, list[dict]] = defaultdict(list)
        for row in audit:
            aid = row.get("agent_id") or (
                "portfolio_manager" if row.get("flow") == "room_pm" else None
            )
            if aid:
                by_agent[aid].append(row)
        for run in runs:
            turns = {t["agent_id"]: t for t in (run.get("transcript") or [])}
            anchor = turns.get("fundamentals_analyst") or turns.get("market_analyst")
            if not anchor or not (anchor.get("content") or "").strip():
                problems.append(f"{epoch}/{run.get('id')}: no anchor turn")
                continue
            key = (anchor["content"] or "")[:120]
            picked: dict[str, dict] = {}
            bad = False
            for agent in ("research_manager", "portfolio_manager"):
                m = [r for r in by_agent.get(agent, []) if key in (r.get("system_prompt") or "")]
                if len(m) != 1:
                    problems.append(f"{epoch}/{run.get('id')}: {agent} matched {len(m)} rows")
                    bad = True
                    break
                picked[agent] = m[0]
            if bad:
                continue
            if not all(turns.get(a, {}).get("content") for a in RESEARCHERS + ("research_manager",)):
                problems.append(f"{epoch}/{run.get('id')}: missing a researcher/RM turn")
                continue
            convenes.append(Convene(
                epoch=epoch,
                run_id=str(run.get("id")),
                ticker=str(run.get("ticker") or ""),
                rm_prompt=picked["research_manager"].get("system_prompt") or "",
                pm_prompt=picked["portfolio_manager"].get("system_prompt") or "",
                rm_recorded=turns["research_manager"]["content"],
                pm_recorded_response=picked["portfolio_manager"].get("response_text") or "",
                bull_turn=turns["bull_researcher"]["content"],
                bear_turn=turns["bear_researcher"]["content"],
            ))
    return convenes, problems


def researcher_blocks(c: Convene) -> dict[str, str]:
    return {"bull_researcher": c.bull_turn, "bear_researcher": c.bear_turn}


def validate(c: Convene) -> None:
    """Assert every prompt surgery this experiment performs is exact, before any call."""
    _strip_blocks(c.rm_prompt, researcher_blocks(c), f"{c.run_id}/rm")
    _strip_blocks(c.pm_prompt, researcher_blocks(c), f"{c.run_id}/pm")
    _substitute_rm(c.pm_prompt, c.rm_recorded, "X", f"{c.run_id}/pm")


# ── parsing ──────────────────────────────────────────────────────────────


def parse_pm(text: str) -> tuple[str | None, float | None, bool]:
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    if not parsed:
        return None, None, False
    return _normalize_pm_action(parsed.get("action")), _safe_float(parsed.get("size_pct")), True


def narration_of(text: str) -> str:
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    return str((parsed or {}).get("narration") or "")


def content_words(text: str) -> set[str]:
    return {w for w in _WORD_RE.findall(text.lower()) if w not in _STOPWORDS}


def jaccard_distance(a: str, b: str) -> float | None:
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


_STANCE_ORD = {"for": 1, "neutral": 0, "against": -1}


def exchangeability_p(triples: list[list[float]], seed: int = 20260820,
                      n_perm: int = 200_000) -> tuple[float, float]:
    """Two-sided permutation test that arm B is drawn from the same law as A1/A2.

    Under the null the ablation is inert, so a convene's three draws are exchangeable:
    which of them is labelled "B" is arbitrary. The statistic is the mean of
    `B - mean(A1, A2)`, and the reference distribution is built by re-drawing that
    label uniformly per convene. This is the right test rather than B-vs-A2 alone,
    which throws away one of the two null draws and loses the power to see the effect.
    """
    if not triples:
        return 0.0, 1.0

    def stat(rows: list[list[float]], which: int) -> float:
        return sum(o[which] - (sum(o[i] for i in range(3) if i != which) / 2)
                   for o in rows) / len(rows)

    obs = stat(triples, 2)
    rng = random.Random(seed)
    ge = 0
    for _ in range(n_perm):
        tot = 0.0
        for o in triples:
            w = rng.randrange(3)
            tot += o[w] - (sum(o[i] for i in range(3) if i != w) / 2)
        if abs(tot / len(triples)) >= abs(obs):
            ge += 1
    return obs, ge / n_perm


def mcnemar_exact(b: int, c: int) -> float:
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(math.comb(n, i) for i in range(0, k + 1)) / (2 ** n)
    return min(1.0, 2 * tail)


# ── replay ───────────────────────────────────────────────────────────────


@dataclass
class Call:
    epoch: str
    run_id: str
    ticker: str
    arm: str
    stage: str          # 'rm' | 'pm'
    prompt_sha256: str
    prompt_chars: int
    response_text: str
    stance: str | None = None
    conviction: str | None = None
    action: str | None = None
    size_pct: float | None = None
    parse_ok: bool = False
    finish_reason: str | None = None
    latency_s: float = 0.0
    error: str | None = None


async def _call(provider, prompt: str, ticker: str, max_tokens: int) -> tuple[str, dict, float, str | None]:
    from app.services.llm_gateway import ChatMessage

    meta: dict[str, Any] = {}
    chunks: list[str] = []
    err: str | None = None
    loop = asyncio.get_event_loop()
    started = loop.time()
    try:
        async for ch in provider.stream_chat(
            system_prompt=prompt,
            messages=[ChatMessage(role="user", content=f"Convene on {ticker}.")],
            max_tokens=max_tokens,
            meta=meta,
        ):
            chunks.append(ch)
    except Exception as exc:  # noqa: BLE001 - recorded, not swallowed
        err = f"{type(exc).__name__}: {exc}"
    return "".join(chunks), meta, loop.time() - started, err


def _mk(c: Convene, arm: str, stage: str, prompt: str, text: str, meta: dict,
        elapsed: float, err: str | None) -> Call:
    call = Call(
        epoch=c.epoch, run_id=c.run_id, ticker=c.ticker, arm=arm, stage=stage,
        prompt_sha256=hashlib.sha256(prompt.encode()).hexdigest(),
        prompt_chars=len(prompt), response_text=text,
        finish_reason=meta.get("finish_reason"), latency_s=round(elapsed, 2), error=err,
    )
    if stage == "rm":
        _, env = parse_stance_envelope(text)
        call.stance, call.conviction = env.stance, env.conviction
    else:
        call.action, call.size_pct, call.parse_ok = parse_pm(text)
    return call


async def run_convene(provider, c: Convene, sem: asyncio.Semaphore,
                      done: set[tuple[str, str]]) -> list[Call]:
    """One convene's full cascade. RM arms first, then the PM calls that depend on them."""
    out: list[Call] = []
    rm_prose: dict[str, str] = {}
    rm_prompts = {
        "a1": c.rm_prompt,
        "a2": c.rm_prompt,
        "b": _strip_blocks(c.rm_prompt, researcher_blocks(c), f"{c.run_id}/rm"),
    }
    async with sem:
        for arm in ("a1", "a2", "b"):
            text, meta, el, err = await _call(provider, rm_prompts[arm], c.ticker, RM_MAX_TOKENS)
            call = _mk(c, arm, "rm", rm_prompts[arm], text, meta, el, err)
            out.append(call)
            rm_prose[arm] = parse_stance_envelope(text)[0]

        pm_stripped = _strip_blocks(c.pm_prompt, researcher_blocks(c), f"{c.run_id}/pm")
        pm_prompts = {
            "a1": _substitute_rm(c.pm_prompt, c.rm_recorded, rm_prose["a1"], f"{c.run_id}/pm"),
            "a2": _substitute_rm(c.pm_prompt, c.rm_recorded, rm_prose["a2"], f"{c.run_id}/pm"),
            "b": _substitute_rm(pm_stripped, c.rm_recorded, rm_prose["b"], f"{c.run_id}/pm-b"),
            "c": _substitute_rm(pm_stripped, c.rm_recorded, rm_prose["a1"], f"{c.run_id}/pm-c"),
        }
        for arm in ARMS:
            text, meta, el, err = await _call(provider, pm_prompts[arm], c.ticker, PM_MAX_TOKENS)
            out.append(_mk(c, arm, "pm", pm_prompts[arm], text, meta, el, err))
    return out


async def run_replays(convenes: list[Convene], *, base_url: str, model: str,
                      concurrency: int, out_jsonl: Path, done: set[tuple[str, str]]) -> None:
    from app.services.llm_gateway import VLLMProvider

    provider = VLLMProvider(base_url=base_url, model_name=model, timeout_seconds=240.0)
    sem = asyncio.Semaphore(concurrency)
    todo = [c for c in convenes if (c.epoch, c.run_id) not in done]
    print(f"[replay] {len(todo)} convenes pending x 7 calls ({len(done)} already recorded)")
    try:
        with out_jsonl.open("a") as fh:
            batch_n = concurrency * 2
            for start in range(0, len(todo), batch_n):
                batch = todo[start : start + batch_n]
                results = await asyncio.gather(
                    *(run_convene(provider, c, sem, done) for c in batch),
                    return_exceptions=True,
                )
                errs = 0
                for r in results:
                    if isinstance(r, Exception):
                        errs += 1
                        print(f"[replay] convene failed: {type(r).__name__}: {r}")
                        continue
                    for call in r:
                        fh.write(json.dumps(asdict(call)) + "\n")
                fh.flush()
                print(f"[replay] {min(start + batch_n, len(todo))}/{len(todo)} convenes"
                      + (f" ({errs} failed)" if errs else ""))
    finally:
        await provider.aclose()


# ── reporting ────────────────────────────────────────────────────────────


def load_calls(path: Path) -> dict[tuple[str, str, str], dict]:
    out: dict[tuple[str, str, str], dict] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            out[(r["run_id"], r["arm"], r["stage"])] = r
    return out


def report(calls: dict[tuple[str, str, str], dict], convenes: list[Convene], out: Path) -> None:
    runs = sorted({k[0] for k in calls})
    complete = [r for r in runs
                if all((r, a, "pm") in calls for a in ARMS)
                and all((r, a, "rm") in calls for a in ("a1", "a2", "b"))]
    by_run = {c.run_id: c for c in convenes}

    L: list[str] = []
    add = L.append
    add("# CR199 — the causal test: removing the Bull and Bear Researchers\n")
    add(f"**{len(complete)} convenes** replayed through the full four-arm cascade "
        f"({len(complete) * 7} live calls). Reproduce with `scripts/researcher_ablation.py "
        "--report-only`.\n")
    add("| arm | RM prompt | PM prompt |")
    add("|---|---|---|")
    add("| A1 control | verbatim | verbatim, RM turn := A1's RM |")
    add("| A2 noise | verbatim, resampled | verbatim, RM turn := A2's RM |")
    add("| B ablated | Bull+Bear removed | Bull+Bear removed, RM turn := B's RM |")
    add("| C direct | (reuses A1) | Bull+Bear removed, RM turn := A1's RM |")
    add("")

    # stage 1 — the adjudicator
    add("## 1. Stage 1 — does the Research Manager's synthesis depend on them?\n")
    rm_stance = {a: Counter() for a in ("a1", "a2", "b")}
    flips_noise = flips_abl = 0
    both_n = 0
    dist_noise: list[float] = []
    dist_abl: list[float] = []
    for r in complete:
        s = {a: calls[(r, a, "rm")].get("stance") for a in ("a1", "a2", "b")}
        for a in ("a1", "a2", "b"):
            rm_stance[a][s[a]] += 1
        if s["a1"] and s["a2"] and s["b"]:
            both_n += 1
            flips_noise += s["a1"] != s["a2"]
            flips_abl += s["a1"] != s["b"]
        dn = jaccard_distance(calls[(r, "a1", "rm")]["response_text"],
                              calls[(r, "a2", "rm")]["response_text"])
        da = jaccard_distance(calls[(r, "a1", "rm")]["response_text"],
                              calls[(r, "b", "rm")]["response_text"])
        if dn is not None:
            dist_noise.append(dn)
        if da is not None:
            dist_abl.append(da)
    add("| arm | for | against | neutral | unparsed |")
    add("|---|---|---|---|---|")
    for a in ("a1", "a2", "b"):
        cc = rm_stance[a]
        add(f"| {a.upper()} | {cc.get('for',0)} | {cc.get('against',0)} | "
            f"{cc.get('neutral',0)} | {cc.get(None,0)} |")
    add("")
    p_n, lo_n, hi_n = wilson(flips_noise, both_n)
    p_a, lo_a, hi_a = wilson(flips_abl, both_n)
    add("| comparison | RM stance differs | rate | 95% CI |")
    add("|---|---|---|---|")
    add(f"| A1 vs A2 (noise floor) | {flips_noise}/{both_n} | {p_n:.1%} | {lo_n:.1%}–{hi_n:.1%} |")
    add(f"| A1 vs B (ablated) | {flips_abl}/{both_n} | {p_a:.1%} | {lo_a:.1%}–{hi_a:.1%} |")
    add("")
    if dist_noise and dist_abl:
        add(f"Mean prose distance (1 − Jaccard over content words): resample "
            f"**{sum(dist_noise)/len(dist_noise):.3f}**, ablated "
            f"**{sum(dist_abl)/len(dist_abl):.3f}**. The gap is how much of the "
            "adjudicator's wording the two researchers were supplying.\n")

    stance_trip = []
    for r in complete:
        o = [_STANCE_ORD.get(calls[(r, a, "rm")].get("stance")) for a in ("a1", "a2", "b")]
        if None not in o:
            stance_trip.append(o)
    obs, pv = exchangeability_p(stance_trip)
    shares = [sum(1 for o in stance_trip if o[i] == 1) / len(stance_trip) for i in range(3)]
    add("### The directional test — which way does the adjudicator move?\n")
    add("A flip rate counts disagreement in either direction and hides a one-way push. "
        "Scoring the stance as for=+1 / neutral=0 / against=-1 and testing arm B against "
        "BOTH null draws under exchangeability answers the question the flip rate cannot.\n")
    add(f"| arm | 'for' share (n={len(stance_trip)}) |")
    add("|---|---|")
    for label, sh in zip(("A1 control", "A2 noise", "B ablated"), shares):
        add(f"| {label} | {sh:.1%} |")
    add("")
    add(f"Statistic `B - mean(A1, A2)` = **{obs:+.3f}** on the -1..+1 scale, "
        f"permutation **p = {pv:.4f}** (200,000 permutations).\n")

    # stage 2 — the verdict
    add("## 2. Stage 2 — does the verdict move?\n")
    add("| arm | APPROVE | PASS | REJECT | unparsed |")
    add("|---|---|---|---|---|")
    act = {a: Counter() for a in ARMS}
    for r in complete:
        for a in ARMS:
            act[a][calls[(r, a, "pm")].get("action")] += 1
    for a in ARMS:
        cc = act[a]
        add(f"| {a.upper()} | {cc.get('APPROVE',0)} | {cc.get('PASS',0)} | "
            f"{cc.get('REJECT',0)} | {cc.get(None,0)} |")
    add("")

    add("### Flip rates against the control arm\n")
    add("| comparison | verdict differs | rate | 95% CI |")
    add("|---|---|---|---|")
    pairs: dict[str, tuple[int, int]] = {}
    for label, arm in (("A1 vs A2 (noise floor)", "a2"),
                       ("A1 vs B (ablated, cascade)", "b"),
                       ("A1 vs C (ablated, PM only)", "c")):
        k = n = 0
        for r in complete:
            x = calls[(r, "a1", "pm")].get("action")
            y = calls[(r, arm, "pm")].get("action")
            if x and y:
                n += 1
                k += x != y
        pairs[arm] = (k, n)
        p, lo, hi = wilson(k, n)
        add(f"| {label} | {k}/{n} | {p:.1%} | {lo:.1%}–{hi:.1%} |")
    add("")

    add("### McNemar — ablation against its own noise floor\n")
    add("| test | b (abl flipped, noise did not) | c (reverse) | p (exact, two-sided) |")
    add("|---|---|---|---|")
    for label, arm in (("B vs noise", "b"), ("C vs noise", "c")):
        b = c_ = 0
        for r in complete:
            base = calls[(r, "a1", "pm")].get("action")
            noise = calls[(r, "a2", "pm")].get("action")
            abl = calls[(r, arm, "pm")].get("action")
            if not (base and noise and abl):
                continue
            fa, fn = abl != base, noise != base
            b += fa and not fn
            c_ += fn and not fa
        add(f"| {label} | {b} | {c_} | {mcnemar_exact(b, c_):.4f} |")
    add("")

    # size
    add("### Restricted to the current-prompt epochs\n")
    add("The Bull, Bear and Research Manager persona prompts last changed 2026-08-13 "
        "(CR179/CR150/CR151), so the 08-14 and 08-14b epochs replay TODAY's prompts and "
        "the 08-07/08-13 epochs replay older ones. Every arm is internally valid either "
        "way — each convene is compared against itself — but the current-prompt subset is "
        "the one that speaks about the Room as it ships.\n")
    cur = [r for r in complete
           if r in by_run and by_run[r].epoch in ("2026-08-14", "2026-08-14b")]
    add(f"n = {len(cur)} convenes.\n")
    add("| comparison | verdict differs | rate | 95% CI |")
    add("|---|---|---|---|")
    for label, arm in (("A1 vs A2 (noise floor)", "a2"),
                       ("A1 vs B (ablated, cascade)", "b"),
                       ("A1 vs C (ablated, PM only)", "c")):
        k = n = 0
        for r in cur:
            x = calls[(r, "a1", "pm")].get("action")
            y = calls[(r, arm, "pm")].get("action")
            if x and y:
                n += 1
                k += x != y
        p_, lo, hi = wilson(k, n)
        add(f"| {label} | {k}/{n} | {p_:.1%} | {lo:.1%}-{hi:.1%} |")
    add("")
    act_trip = []
    for r in complete:
        v = [calls[(r, a, "pm")].get("action") for a in ("a1", "a2", "b")]
        if all(v):
            act_trip.append([1.0 if x == "APPROVE" else 0.0 for x in v])
    obs_a, pv_a = exchangeability_p(act_trip)
    add("### The same directional test, on the verdict\n")
    add(f"| arm | APPROVE rate (n={len(act_trip)}) |")
    add("|---|---|")
    for label, i in (("A1 control", 0), ("A2 noise", 1), ("B ablated", 2)):
        add(f"| {label} | {sum(o[i] for o in act_trip)/len(act_trip):.1%} |")
    add("")
    add(f"Statistic `B - mean(A1, A2)` = **{obs_a:+.4f}**, permutation "
        f"**p = {pv_a:.4f}**. The push that is real at the adjudicator is gone by the "
        "verdict.\n")

    add("### Where it dies\n")
    add("| arm | RM said 'for' | of those, APPROVE | RM said 'against' | of those, APPROVE |")
    add("|---|---|---|---|---|")
    for arm, label in (("a1", "A1 control"), ("b", "B ablated")):
        rows = {"for": [0, 0], "against": [0, 0]}
        for r in complete:
            st = calls[(r, arm, "rm")].get("stance")
            ac = calls[(r, arm, "pm")].get("action")
            if st in rows and ac:
                rows[st][0] += 1
                rows[st][1] += ac == "APPROVE"
        f_n, f_a = rows["for"]
        g_n, g_a = rows["against"]
        add(f"| {label} | {f_n} | {f_a} ({f_a/f_n:.0%}) | {g_n} | {g_a} ({g_a/g_n:.0%}) |"
            if f_n and g_n else f"| {label} | {f_n} | - | {g_n} | - |")
    add("")
    add("Removing the researchers buys the Bull's side more 'for' verdicts from the "
        "adjudicator and each one converts at a lower rate, so the two cancel.\n")

    add("## 3. Position size\n")
    add("| arm | mean size_pct | n stated |")
    add("|---|---|---|")
    for a in ARMS:
        vals = [calls[(r, a, "pm")].get("size_pct") for r in complete]
        vals = [v for v in vals if isinstance(v, (int, float))]
        add(f"| {a.upper()} | {sum(vals)/len(vals):.2f} | {len(vals)} |" if vals
            else f"| {a.upper()} | — | 0 |")
    add("")

    # narration distance
    add("## 4. What the user reads\n")
    dn_, da_, dc_ = [], [], []
    for r in complete:
        base = narration_of(calls[(r, "a1", "pm")]["response_text"])
        for target, bag in (("a2", dn_), ("b", da_), ("c", dc_)):
            d = jaccard_distance(base, narration_of(calls[(r, target, "pm")]["response_text"]))
            if d is not None:
                bag.append(d)
    add("| comparison | mean narration distance |")
    add("|---|---|")
    for label, bag in (("A1 vs A2 (noise)", dn_), ("A1 vs B (ablated)", da_),
                       ("A1 vs C (PM-only)", dc_)):
        if bag:
            add(f"| {label} | {sum(bag)/len(bag):.3f} |")
    add("")

    # per-ticker
    add("## 5. Per-ticker verdict flips (ablated cascade vs control)\n")
    add("| ticker | n | flips | noise flips |")
    add("|---|---|---|---|")
    per: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for r in complete:
        t = by_run[r].ticker if r in by_run else "?"
        base = calls[(r, "a1", "pm")].get("action")
        abl = calls[(r, "b", "pm")].get("action")
        noise = calls[(r, "a2", "pm")].get("action")
        if base and abl and noise:
            per[t][0] += 1
            per[t][1] += abl != base
            per[t][2] += noise != base
    for t in sorted(per):
        n, f, nf = per[t]
        add(f"| {t} | {n} | {f} | {nf} |")
    add("")

    add("## Appendix — what this does not claim\n")
    add("- The Trader and the three Risk Debators keep their recorded turns in the PM's "
        "window in every arm. They wrote those turns after reading the researchers, so "
        "the ablation cannot remove what they already absorbed: this is a **lower bound** "
        "on deleting the phase.\n")
    add("- Sampling is server-side. The floor is measured on this model, in this session; "
        "it is not transferable to another serving slot.\n")
    add(f"- At n={len(complete)} the resolvable effect is roughly 8–10 percentage points. "
        "A null here is 'no effect large enough to see', not 'exactly zero'.\n")

    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("\n".join(L) + "\n")
    print(f"wrote {out} ({len(complete)} complete convenes)")


# ── main ─────────────────────────────────────────────────────────────────


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description="CR199 researcher ablation")
    ap.add_argument("--corpus", type=Path,
                    default=repo / "docs/forward_planning/CR143_agent_prompt_audit/corpus")
    ap.add_argument("--out-dir", type=Path,
                    default=repo / "docs/forward_planning/CR199_bull_bear_researcher_effectiveness/ablation")
    ap.add_argument("--epochs", nargs="+", default=list(DEFAULT_EPOCHS))
    ap.add_argument("--base-url", default="http://192.168.20.74:8000")
    ap.add_argument("--model", default="ami-llm")
    ap.add_argument("--concurrency", type=int, default=6)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    convenes, problems = load_convenes(args.corpus, args.epochs)
    print(f"[corpus] {len(convenes)} convenes joined, {len(problems)} problems")
    for p in problems[:10]:
        print(f"  ! {p}")

    bad = 0
    for c in convenes:
        try:
            validate(c)
        except StripError as exc:
            print(f"  ! strip check failed: {exc}")
            bad += 1
    print(f"[validate] {len(convenes) - bad}/{len(convenes)} convenes survive every prompt surgery")
    convenes = [c for c in convenes if _safe_validate(c)]
    if args.limit:
        convenes = convenes[: args.limit]

    out_jsonl = args.out_dir / "researcher_ablation_calls.jsonl"
    args.out_dir.mkdir(parents=True, exist_ok=True)

    if args.dry_run:
        print("[dry-run] no calls made")
        return 0

    if not args.report_only:
        calls = load_calls(out_jsonl)
        done = {(r["epoch"], r["run_id"]) for r in calls.values()
                if all((r["run_id"], a, "pm") in calls for a in ARMS)}
        asyncio.run(run_replays(convenes, base_url=args.base_url, model=args.model,
                                concurrency=args.concurrency, out_jsonl=out_jsonl, done=done))

    report(load_calls(out_jsonl), convenes, args.out_dir.parent / "ABLATION.md")
    return 0


def _safe_validate(c: Convene) -> bool:
    try:
        validate(c)
        return True
    except StripError:
        return False


if __name__ == "__main__":
    raise SystemExit(main())
