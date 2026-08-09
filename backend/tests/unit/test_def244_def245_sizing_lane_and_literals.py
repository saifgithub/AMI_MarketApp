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


def test_no_researcher_is_asked_for_a_position_size():
    """The scope, asserted rather than assumed. Sizing belongs to EXECUTION, RISK
    and VERDICT phases; a RESEARCHERS-phase agent sizing a trade that does not yet
    exist is the defect. If either researcher regrows the demand, this is red."""
    # A line that hands sizing to another agent by name is a DEFERRAL, not a
    # demand, and cannot be an offender however many demand-words it contains.
    # (My own replacement text — "no trade has been proposed to size" — tripped
    # the first version of this check, which is a fair warning about heuristics
    # that read words instead of meaning.)
    # ROUND-1 AUDIT MAJOR — the verb list is GONE. It required one of
    # suggest|propose|recommend|"output specific", and the auditor defeated it
    # with four ordinary bullets that reintroduce the defect exactly:
    #   "Quantify your ideal position size given conviction."
    #   "State the position size you would take."
    #   "Give a specific sizing figure based on conviction."
    #   "End with a sizing conclusion."
    # A synonym list cannot enumerate English. The structural rule is simpler and
    # strictly stronger: a RESEARCHERS-phase prompt has no business mentioning
    # position size AT ALL unless it is handing it to the agent that owns it, so
    # any "siz" that does not name an owner is a finding regardless of the verb.
    OWNERS = ("trader", "portfolio manager", "risk debators")

    def _bullets(text: str) -> list[str]:
        """Group wrapped continuation lines back into their bullet. Scanning raw
        lines splits a multi-line instruction and strips the context that makes
        it a deferral — which is exactly how the first version of this check
        flagged the fix as the defect."""
        out: list[str] = []
        for line in text.splitlines():
            if line.lstrip().startswith(("-", "*")) or not out:
                out.append(line.strip())
            else:
                out[-1] += " " + line.strip()
        return out

    offenders = []
    for name in ("bull_researcher.md", "bear_researcher.md"):
        for bullet in _bullets((_CONTENT / name).read_text(encoding="utf-8")):
            low = bullet.lower()
            if "siz" not in low:
                continue
            if any(o in low for o in OWNERS):
                continue
            offenders.append(f"{name}: {bullet}")
    assert not offenders, offenders


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
def test_no_agent_prompt_quotes_an_example_containing_a_literal_percentage(filename):
    """The class, tested STRUCTURALLY — round-1 audit MAJOR.

    The first version required a noun from `downside|drawdown|loss|fall|drop`
    near the number. The auditor defeated it with ordinary synonyms —
    *correction, decline, retracement, pullback, slump, plunge, haircut* — and,
    decisively, with **the original defect text minus the word "downside"**:

        "if X happens, we're looking at -25%, and that is more likely than
         consensus thinks"

    which is the DEF245 bullet almost verbatim and does not match. A word list
    cannot enumerate the ways English says "it goes down".

    So the rule stops describing the number and describes **where it sits**: a
    literal percentage inside a QUOTED example. That is what makes an example
    leakable — the model is being shown a finished utterance with a figure in it,
    and CR149 measured that it reuses exactly those figures (`-25%` reached 22 of
    811 real verdicts and became the most frequent downside magnitude in the
    corpus). Percentages OUTSIDE quotes are mandate values and length guides —
    configuration, not modelled speech — and are untouched.

    Four prompts had to change to satisfy this, one of them a line added by
    DEF244's own fix an hour earlier (`"the Bull's 44%"`). That is the argument
    for the structural form: the vocabulary guard passed all four.
    """
    if filename == "README.md":
        pytest.skip("documentation, not a prompt")
    import re

    hits = [
        m.group(0)
        for m in re.finditer(
            r'"[^"\n]*?\d+(?:\.\d+)?%[^"\n]*?"',
            (_CONTENT / filename).read_text(encoding="utf-8"),
        )
    ]
    assert not hits, (
        f"{filename} quotes an example containing a literal percentage; the model "
        f"reuses the figure as a fact (DEF245): {hits}"
    )
