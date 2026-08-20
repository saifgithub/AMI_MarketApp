"""CR199 — do the Bull and Bear Researchers carry information into the decision?

CR197 asked this of the three Risk Debators, who speak at positions 9-11 of 12 and
are read by the Portfolio Manager alone. The Researchers sit at 5-6: the Research
Manager, the Trader, all three Debators and the PM read them. So the same question
("constants dressed as judgements?") has a much longer causal reach here, and the
observational answer needs one measurement CR197 did not need — PROVENANCE.

Four channels, measured separately because they disagree:

  1. stance / conviction      — is the position a per-ticker judgement or a costume?
  2. minted numbers           — does a researcher DERIVE quantities, or re-cite ones
                                already in its own prompt? (the prompt carries the fact
                                sheet AND the four analyst turns, so "not in the
                                transcript" is not the same as "new")
  3. downstream provenance    — of the numbers the Research Manager / Trader / PM cite,
                                which appear ONLY in a researcher turn and nowhere in
                                that reader's own prompt? Those are quantities the
                                researchers put into the decision.
  4. attribution + engagement — who names whom, and does the Bear (who speaks second)
                                actually answer the Bull?

Channel 3 is the closest an offline read gets to influence: a number that reaches the
PM's narration and exists nowhere else in the PM's window came through a researcher.
It is still association — the researcher and the reader share upstream inputs — but
unlike a cosine echo it is checkable per token.

Usage (from backend/):
    .venv/bin/python -m scripts.researcher_signal_report
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.services.llm_json import extract_json_object  # noqa: E402

RESEARCHERS = ("bull_researcher", "bear_researcher")
ANALYSTS = (
    "fundamentals_analyst",
    "market_analyst",
    "news_analyst",
    "social_media_analyst",
)
READERS = ("research_manager", "trader", "aggressive_debator", "portfolio_manager")
ALL_VOICES = ANALYSTS + RESEARCHERS + (
    "research_manager",
    "trader",
    "aggressive_debator",
    "conservative_debator",
    "neutral_debator",
)
DEFAULT_EPOCHS = ("2026-08-07", "2026-08-13", "2026-08-14", "2026-08-14b")

# A number as an agent writes one. Bare 1-2 digit integers are dropped: "2 quarters",
# "3 risks" and a list marker are not evidence, and keeping them floods every set with
# spurious matches in both directions.
_NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*")


def entropy(counts: Counter) -> float:
    n = sum(counts.values())
    if n == 0:
        return 0.0
    h = -sum((c / n) * math.log2(c / n) for c in counts.values() if c)
    return abs(h)


def mutual_information(pairs: list[tuple[Any, Any]]) -> float:
    n = len(pairs)
    if n == 0:
        return 0.0
    jx, jy, jxy = Counter(), Counter(), Counter()
    for x, y in pairs:
        jx[x] += 1
        jy[y] += 1
        jxy[(x, y)] += 1
    mi = 0.0
    for (x, y), c in jxy.items():
        pxy, px, py = c / n, jx[x] / n, jy[y] / n
        mi += pxy * math.log2(pxy / (px * py))
    return max(0.0, mi)


def numbers_in(text: str, *, min_len: int = 3) -> set[str]:
    """Cited quantities, normalised. Short bare integers are excluded as noise."""
    out = set()
    for m in _NUM_RE.finditer(text or ""):
        tok = m.group(0).replace(",", "").rstrip(".")
        if not tok or tok in {"-", ""}:
            continue
        digits = tok.lstrip("-").replace(".", "")
        if len(digits) < min_len and "." not in tok:
            continue
        out.add(tok)
    return out


def jaccard(a: set[str], b: set[str]) -> float:
    if not a and not b:
        return 1.0
    return len(a & b) / len(a | b) if (a | b) else 0.0


# ── corpus ───────────────────────────────────────────────────────────────


def load_epoch(corpus: Path, epoch: str) -> tuple[list[dict], list[dict]]:
    with (corpus / f"llm_audit_{epoch}-epoch.json").open() as fh:
        audit = json.load(fh)
    with (corpus / f"room_runs_{epoch}-epoch.json").open() as fh:
        runs = json.load(fh)
    return audit, runs


def join_prompts(epoch: str, audit: list[dict], runs: list[dict]) -> list[dict]:
    """Attach each run's per-agent recorded prompt, joined on a verbatim upstream turn.

    Timestamps cannot join these (parallel batches, two ISO formats across epochs). Every
    sequential agent's prompt reproduces the turns before it byte-for-byte, so a slice of
    the FIRST analyst's turn is an exact key for every downstream agent's prompt; the
    analysts themselves are joined on the PM row that the same key already resolved,
    which is asserted unique rather than assumed.
    """
    by_agent: dict[str, list[dict]] = defaultdict(list)
    for row in audit:
        aid = row.get("agent_id") or (
            "portfolio_manager" if row.get("flow") == "room_pm" else None
        )
        if aid:
            by_agent[aid].append(row)

    joined: list[dict] = []
    for run in runs:
        transcript = run.get("transcript") or []
        turns = {t["agent_id"]: t for t in transcript}
        anchor = turns.get("fundamentals_analyst") or turns.get("market_analyst")
        if not anchor or not (anchor.get("content") or "").strip():
            continue
        key = (anchor["content"] or "")[:120]
        prompts: dict[str, str] = {}
        ok = True
        for agent in ("bull_researcher", "bear_researcher", "research_manager",
                      "trader", "portfolio_manager"):
            matches = [r for r in by_agent.get(agent, []) if key in (r.get("system_prompt") or "")]
            if len(matches) != 1:
                ok = False
                break
            prompts[agent] = matches[0].get("system_prompt") or ""
            if agent == "portfolio_manager":
                prompts["_pm_response"] = matches[0].get("response_text") or ""
        if not ok:
            continue
        joined.append({
            "epoch": epoch,
            "run_id": run.get("id"),
            "ticker": run.get("ticker"),
            "turns": turns,
            "verdict": run.get("verdict") or {},
            "prompts": prompts,
        })
    return joined


def pm_narration(text: str) -> str:
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    return str((parsed or {}).get("narration") or "")


def pm_action(text: str) -> str | None:
    parsed = extract_json_object(text) or extract_json_object(text, repair_truncated=True)
    a = (parsed or {}).get("action")
    if not isinstance(a, str):
        return None
    a = a.strip().upper()
    return "APPROVE" if a.startswith("MODIFY") else a


# ── report ───────────────────────────────────────────────────────────────


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    ap = argparse.ArgumentParser(description="CR199 deterministic researcher-signal report")
    ap.add_argument("--corpus", type=Path,
                    default=repo / "docs/forward_planning/CR143_agent_prompt_audit/corpus")
    ap.add_argument("--out", type=Path,
                    default=repo / "docs/forward_planning/CR199_bull_bear_researcher_effectiveness/RESEARCHER_SIGNAL.md")
    ap.add_argument("--epochs", nargs="+", default=list(DEFAULT_EPOCHS))
    args = ap.parse_args()

    convenes: list[dict] = []
    unjoined = 0
    for ep in args.epochs:
        audit, runs = load_epoch(args.corpus, ep)
        j = join_prompts(ep, audit, runs)
        unjoined += len(runs) - len(j)
        convenes.extend(j)

    L: list[str] = []
    add = L.append
    add("# CR199 — what the Bull and Bear Researchers actually carry\n")
    tickers = Counter(c["ticker"] for c in convenes)
    add(
        f"Deterministic read of **{len(convenes)} committed convenes** "
        f"({', '.join(args.epochs)}), no LLM involved, every agent joined to its own "
        f"verbatim recorded prompt ({unjoined} convene(s) dropped for an ambiguous join). "
        f"{len(tickers)} distinct tickers "
        f"({', '.join(f'{t}x{n}' for t, n in tickers.most_common(6))}"
        f"{'...' if len(tickers) > 6 else ''}). Clustered, not independent. "
        "Reproduce with `scripts/researcher_signal_report.py`.\n"
    )

    turns_by_agent: dict[str, list[dict]] = defaultdict(list)
    for c in convenes:
        for aid, t in c["turns"].items():
            turns_by_agent[aid].append(t)

    # ── 1. stance ──
    add("## 1. Stance: judgement or costume?\n")
    add("| agent | for | against | neutral | none | H(stance) bits |")
    add("|---|---|---|---|---|---|")
    for agent in RESEARCHERS + ("research_manager", "trader"):
        cc = Counter(t.get("stance") for t in turns_by_agent.get(agent, []))
        h = entropy(Counter({k: v for k, v in cc.items() if k}))
        add(f"| {agent} | {cc.get('for',0)} | {cc.get('against',0)} | {cc.get('neutral',0)} "
            f"| {cc.get(None,0)} | **{h:.3f}** |")
    add("")

    add("## 2. Conviction: the channel that is free to vary\n")
    add("| agent | low | medium | high | none | H bits |")
    add("|---|---|---|---|---|---|")
    for agent in RESEARCHERS + ("research_manager",):
        cc = Counter(t.get("conviction") for t in turns_by_agent.get(agent, []))
        h = entropy(Counter({k: v for k, v in cc.items() if k}))
        add(f"| {agent} | {cc.get('low',0)} | {cc.get('medium',0)} | {cc.get('high',0)} "
            f"| {cc.get(None,0)} | **{h:.3f}** |")
    add("")

    # ── 3. mutual information ──
    add("## 3. Mutual information with the decision\n")
    add("Two targets: the PM's OWN action parsed from its reply, and the shipped "
        "`verdict.action` (which the safety floor can overwrite).\n")
    add("| channel | I(.;PM reply) | I(.;shipped verdict) |")
    add("|---|---|---|")
    rows = []
    for agent in RESEARCHERS + ("research_manager", "trader"):
        for field in ("stance", "conviction"):
            p_reply, p_verdict = [], []
            for c in convenes:
                t = c["turns"].get(agent)
                if not t:
                    continue
                a_reply = pm_action(c["prompts"].get("_pm_response", ""))
                a_verdict = (c["verdict"] or {}).get("action")
                if a_reply:
                    p_reply.append((t.get(field), a_reply))
                if a_verdict:
                    p_verdict.append((t.get(field), a_verdict))
            rows.append((f"{agent}.{field}", mutual_information(p_reply),
                         mutual_information(p_verdict)))
    for name, a, b in sorted(rows, key=lambda x: -x[1]):
        add(f"| {name} | {a:.4f} | {b:.4f} |")
    add("")

    # ── 4. minted numbers ──
    add("## 4. Do the researchers DERIVE numbers, or re-cite them?\n")
    add("Each agent's own recorded prompt carries the fact sheet plus every prior turn. "
        "A cited number absent from that prompt was minted by the agent — arithmetic, or "
        "invention.\n")
    add("| agent | mean numbers cited | mean minted (absent from own prompt) | minted share |")
    add("|---|---|---|---|")
    for agent in RESEARCHERS + ("research_manager", "trader"):
        cited_tot, minted_tot, n = 0, 0, 0
        for c in convenes:
            t = c["turns"].get(agent)
            p = c["prompts"].get(agent)
            if not t or p is None:
                continue
            cited = numbers_in(t.get("content", ""))
            minted = cited - numbers_in(p)
            cited_tot += len(cited)
            minted_tot += len(minted)
            n += 1
        if n:
            add(f"| {agent} | {cited_tot/n:.1f} | {minted_tot/n:.1f} | "
                f"{(minted_tot/cited_tot if cited_tot else 0):.0%} |")
    add("")

    # ── 5. provenance: what the readers inherit ──
    add("## 5. Provenance: numbers that reach a reader ONLY through a researcher\n")
    add("For each reader, of the numbers it cites, how many appear in a researcher's turn "
        "**and nowhere else in that reader's own prompt** (fact sheet, analyst turns, "
        "everything). Those are quantities the researchers introduced into the decision.\n")
    add("| reader | mean numbers cited | via Bull only | via Bear only | via either | share via researchers |")
    add("|---|---|---|---|---|---|")
    for reader in ("research_manager", "trader", "portfolio_manager"):
        tot = bull_only = bear_only = either = 0
        n = 0
        for c in convenes:
            prompt = c["prompts"].get(reader)
            if prompt is None:
                continue
            if reader == "portfolio_manager":
                text = pm_narration(c["prompts"].get("_pm_response", ""))
            else:
                text = (c["turns"].get(reader) or {}).get("content", "")
            if not text:
                continue
            cited = numbers_in(text)
            if not cited:
                continue
            bull_t = numbers_in((c["turns"].get("bull_researcher") or {}).get("content", ""))
            bear_t = numbers_in((c["turns"].get("bear_researcher") or {}).get("content", ""))
            # The reader's prompt MINUS the researcher blocks = everything it could have
            # cited without them. Blocks are removed verbatim, exactly as the ablation does.
            stripped = prompt
            for aid in RESEARCHERS:
                turn = (c["turns"].get(aid) or {}).get("content", "")
                if turn:
                    stripped = stripped.replace(f"\n[{aid}] {turn}", "", 1)
            elsewhere = numbers_in(stripped)
            only_via = cited - elsewhere
            tot += len(cited)
            bull_only += len(only_via & bull_t - bear_t)
            bear_only += len(only_via & bear_t - bull_t)
            either += len(only_via & (bull_t | bear_t))
            n += 1
        if n:
            add(f"| {reader} | {tot/n:.1f} | {bull_only/n:.2f} | {bear_only/n:.2f} | "
                f"{either/n:.2f} | {(either/tot if tot else 0):.1%} |")
    add("")

    # ── 6. attribution ──
    add("## 6. Attribution: who names whom\n")
    add("| reader | names 'Bull' | names 'Bear' | names both | n |")
    add("|---|---|---|---|---|")
    for reader in ("bear_researcher", "research_manager", "trader",
                   "aggressive_debator", "conservative_debator", "neutral_debator",
                   "portfolio_manager"):
        nb = nr = both = n = 0
        for c in convenes:
            if reader == "portfolio_manager":
                text = pm_narration(c["prompts"].get("_pm_response", ""))
            else:
                text = (c["turns"].get(reader) or {}).get("content", "")
            if not text:
                continue
            low = text.lower()
            b = "bull" in low
            r = "bear" in low
            nb += b
            nr += r
            both += b and r
            n += 1
        if n:
            add(f"| {reader} | {nb} ({nb/n:.0%}) | {nr} ({nr/n:.0%}) | {both} ({both/n:.0%}) | {n} |")
    add("")
    add("The Bear speaks immediately after the Bull and is the only voice with a live "
        "opportunity to rebut it inside the same phase.\n")

    # ── 7. content differentiation ──
    add("## 7. Do Bull and Bear say different things?\n")
    add("| pair | mean Jaccard over cited numbers |")
    add("|---|---|")
    pairs = [("bull_researcher", "bear_researcher"),
             ("bull_researcher", "research_manager"),
             ("bear_researcher", "research_manager")]
    for a, b in pairs:
        vals = []
        for c in convenes:
            ta = (c["turns"].get(a) or {}).get("content", "")
            tb = (c["turns"].get(b) or {}).get("content", "")
            if ta and tb:
                vals.append(jaccard(numbers_in(ta), numbers_in(tb)))
        if vals:
            add(f"| {a.split('_')[0]} vs {b.split('_')[0]} | {sum(vals)/len(vals):.3f} |")
    add("")

    # ── 8. contingency ──
    add("## 8. Researcher conviction vs the PM's own action\n")
    for agent in RESEARCHERS:
        add(f"\n**{agent}**\n")
        table: dict[str, Counter] = defaultdict(Counter)
        for c in convenes:
            t = c["turns"].get(agent)
            a = pm_action(c["prompts"].get("_pm_response", ""))
            if t and a:
                table[str(t.get("conviction"))][a] += 1
        acts = sorted({a for row in table.values() for a in row})
        add("| conviction | " + " | ".join(acts) + " | n |")
        add("|---" * (len(acts) + 2) + "|")
        for k in sorted(table):
            row = table[k]
            add(f"| {k} | " + " | ".join(str(row.get(a, 0)) for a in acts)
                + f" | {sum(row.values())} |")
    add("")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(L) + "\n")
    print(f"wrote {args.out} ({len(convenes)} convenes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
