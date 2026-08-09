"""DEF244 + DEF245 — the Bull stops sizing, and the Bear stops shipping a literal.

**DEF244.** `bull_researcher.md` ended with *"End with a sizing suggestion based
on conviction × user's risk tolerance"* — a portfolio-level sizing conclusion
demanded at RESEARCHERS phase, before any trade has been proposed to size. With
no entry, stop or target yet, the Bull invents a downside price and does the
arithmetic in prose. On SNDK it wrote *"a move to $41.0 would trigger a 66% loss…
resulting in a 33% portfolio drawdown… which stays within the 50% portfolio-level
safety floor"*. The move from its own prompt's $1,212.21 to $41.00 is **−96.6%**,
so the true contribution is **48.3 of a 50 pt cap** — the sentence asserting
compliance asserts the opposite of the truth.

DEF241 could not reach it: `_PHASE_FOR_AGENT` puts this agent in RESEARCHERS and
the computed-figure block is gated on `phase in ("RISK", "VERDICT")`. And a naive
widening would not have helped — the Conservative's error is misapplying a formula
to a size it was never given (supplying the size fixes it); the Bull's is
arithmetic on two prices it already had (supplying a size does not).

So the demand is cut rather than supplied. **The precedent is already in the
codebase**: `market_analyst.md` says *"Recommend final position sizing. That's the
Trader."* Four sizing stages follow the Bull — Trader proposes, three Risk
Debators argue, PM decides, safety floor clamps.

**DEF245.** `bear_researcher.md` carried a worked example containing a literal
number — *"we're looking at -25%"* — three lines above a grounding directive
forbidding exactly that. Measured against the frozen 811-row PM verdict corpus:
**22 verdicts (2.7%) contain `-25%`, 12 attributing it to the Bear**, and it is
the single most frequent downside magnitude in the population. An example only
leaks into the slot its instruction cannot otherwise fill (CR149) — the Bull's
`32% gross margins` example appears 0 times, because that slot has data.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_CONTENT = Path(__file__).resolve().parents[3] / "content" / "agents"


# ── DEF244 ────────────────────────────────────────────────────────────────────


def test_the_bull_no_longer_concludes_with_a_position_size():
    """RED before: the file contained the sizing-suggestion instruction."""
    text = (_CONTENT / "bull_researcher.md").read_text(encoding="utf-8")
    assert "sizing suggestion" not in text
    assert "End with your CONVICTION" in text


def test_the_bull_is_told_where_sizing_actually_belongs():
    """Cutting a demand without naming its owner invites the model to fill the
    gap anyway. The replacement names the four stages that follow."""
    text = (_CONTENT / "bull_researcher.md").read_text(encoding="utf-8")
    for owner in ("Trader", "Risk Debators", "Portfolio\n  Manager"):
        assert owner in text, f"the replacement does not name the {owner}"


def test_the_researchers_output_style_is_pinned_to_a_reviewed_snapshot():
    """DEF244's guard, round 3 — and the reason this one converges.

    Rounds 1 and 2 both matched a PATTERN and both fell to ordinary paraphrase:
    first a verb list (`suggest|propose|recommend`), then a lexical root (`siz`),
    which the auditor defeated with *"Recommend an allocation percentage"*,
    *"State how many shares to buy"*, *"End with a portfolio weight"*,
    *"Conclude with an exposure level"*. A third pattern would fall the same way —
    "position size" has unbounded synonyms and no lexical anchor.

    So this stops matching and starts ENUMERATING. The two researchers' output
    style is ten bullets; it is pinned verbatim. **Any** edit fails, including
    every paraphrase above, because the check no longer cares what the words mean.

    A change here is not a defect — it is a REVIEW PROMPT, the same device
    `_EXPECTED_EXTRACTIONS` uses in `test_p16_prose_pattern_corpus_parity.py`.
    Update the snapshot in the same commit, and answer one question while you do:
    **does this bullet ask a RESEARCHERS-phase agent to output a position size?**
    Sizing is the Trader's proposal, the Risk Debators' argument, the PM's
    decision and the safety floor's clamp — four stages, all after this one.

    What this does NOT do: understand English. It cannot tell a sizing demand
    from a typo fix. It guarantees only that no edit to these bullets reaches
    `main` unread, which is precisely how DEF244 got in.
    """
    import hashlib

    expected = {
        "bull_researcher.md": "923a5c0c7124",
        "bear_researcher.md": "efd014741751",
    }
    actual = {}
    for name in expected:
        section = []
        inside = False
        for line in (_CONTENT / name).read_text(encoding="utf-8").splitlines():
            if line.startswith("## Output style"):
                inside = True
                continue
            if inside and line.startswith("## "):
                break
            if inside and line.strip():
                section.append(line.rstrip())
        assert section, f"{name} has no '## Output style' section"
        actual[name] = hashlib.sha256(
            "\n".join(section).encode("utf-8")
        ).hexdigest()[:12]

    assert actual == expected, (
        "A researcher's output-style bullets changed. This is a REVIEW PROMPT, "
        "not a failure — read the diff and answer: does any bullet ask a "
        "RESEARCHERS-phase agent to output a position size? Sizing belongs to the "
        f"Trader, the Risk Debators, the PM and the floor (DEF244). Then update "
        f"the snapshot in this commit. expected={expected} actual={actual}"
    )


def test_the_bears_dead_short_clause_is_gone():
    """Shorts are rejected end-to-end — `sim_engine` returns
    `blocked_by="long_only"` unconditionally (CR150) — so "if short selling is
    allowed" was never true. It fired 0/18 in the epoch: dead text, not a leak,
    but dead text in a prompt is instruction weight spent on nothing."""
    text = (_CONTENT / "bear_researcher.md").read_text(encoding="utf-8")
    assert "If short selling is allowed" not in text


def test_the_research_manager_may_not_launder_another_agents_number():
    """CR151: the RM promoted the Bull's wrong 44% upside (true +60.5%) into
    "Both acknowledge… the 44% upside" — a wrong number turned into a point of
    agreement.

    This half is a PROMPT INSTRUCTION and therefore a weak control (~30%
    compliance, CLAUDE.md). It is worth having and it is not worth trusting; the
    measurable half of DEF244 is the Bull's cut demand.
    """
    text = (_CONTENT / "research_manager.md").read_text(encoding="utf-8")
    assert "Restate another agent's NUMBER as an agreed fact" in text
    assert "Agreement is about the" in text


# ── DEF245 ────────────────────────────────────────────────────────────────────


def test_the_bear_carries_no_literal_downside_percentage():
    """RED before: `-25%` sat inside the worked example and became the most
    frequent downside magnitude in 811 real verdicts."""
    text = (_CONTENT / "bear_researcher.md").read_text(encoding="utf-8")
    assert "-25%" not in text
    assert "never\n  carry a figure over from this instruction" in text


@pytest.mark.parametrize("filename", sorted(p.name for p in _CONTENT.glob("*.md")))
def test_no_agent_prompt_contains_a_literal_percentage_anywhere(filename):
    """DEF245's guard, round 3 — complete, because it enumerates rather than matches.

    Round 1 required a downside NOUN near the number and fell to *correction,
    decline, retracement, pullback, slump, plunge, haircut*. Round 2 required the
    number to sit inside ASCII double quotes and fell to an unquoted worked
    example, single quotes, and curly quotes. Each time the anchor was a surface
    feature, and each time ordinary English walked around it.

    There is no anchor here. **After DEF245, the twelve prompts contain ZERO
    literal percentages** — measured, not assumed — so the invariant is simply
    that it stays zero. Every bypass the auditor built contains a `%` and is
    caught, whatever surrounds it, because nothing about the surroundings is
    consulted.

    Legitimate percentages do not live in these files: mandate values (caps,
    ceilings, drawdown limits) are injected at runtime by `overlay_generator`,
    and length guides are counts of sentences. Placeholders like `N%` and `X%`
    pass — they carry no figure for a model to reuse, which is the entire point.

    If a real one is ever needed, add it to `_ALLOWED` with a reason. That is a
    deliberate, reviewed act; today the list is empty and should stay that way.
    """
    if filename == "README.md":
        pytest.skip("documentation, not a prompt")
    import re

    _ALLOWED: set[str] = set()

    hits = [
        m.group(0).strip()
        for m in re.finditer(
            r"[^\n]{0,40}\d+(?:\.\d+)?%[^\n]{0,25}",
            (_CONTENT / filename).read_text(encoding="utf-8"),
        )
        if m.group(0).strip() not in _ALLOWED
    ]
    assert not hits, (
        f"{filename} contains a literal percentage. A model reuses the figures it "
        f"is shown — `-25%` reached 22 of 811 real verdicts and became the most "
        f"common downside magnitude AMI produced (DEF245). Use a placeholder (N%, "
        f"X%) or take the number from the fact sheet at runtime: {hits}"
    )
