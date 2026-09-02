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
    """RED before: the file contained the sizing-suggestion instruction.

    CR219 R16 (2026-09-02): the literal anchor this test pinned, "End with your
    CONVICTION", was itself a collision — that word is the machine-parsed stance
    envelope's own field name (`room_prompts.py:679/:756`,
    `room_runner.py:_CONVICTION_FIELD_RE`), and the persona's OWN "end with your
    CONVICTION" instruction told the model to repeat it at the end, contradicting
    the envelope format's "write it ONCE, at the top only." Register ruling:
    disambiguate the persona's own term (renamed to "case strength"), leave the
    envelope's CONVICTION alone — this test's anchor updates to match, and the
    load-bearing assertion (no sizing demand at RESEARCHERS phase) is unchanged.
    """
    text = (_CONTENT / "bull_researcher.md").read_text(encoding="utf-8")
    assert "sizing suggestion" not in text
    assert "End with your case strength" in text
    assert "CONVICTION" not in text, (
        "CR219 R16: the persona must not use the envelope's own field name for "
        "its own case-strength instruction — that is the collision this row fixed"
    )


def test_the_bull_is_told_where_sizing_actually_belongs():
    """Cutting a demand without naming its owner invites the model to fill the
    gap anyway. The replacement names the four stages that follow.

    CR219 R16 rewrapped the paragraph this line lives in (shortening "your
    CONVICTION" to "your case strength" shifted every wrap point after it), so
    the check now looks for "Chief Investment Officer" as a plain substring
    rather than pinning the specific line break the old wrap happened to put
    inside it — the wrap point was never the thing being verified."""
    text = (_CONTENT / "bull_researcher.md").read_text(encoding="utf-8")
    for owner in ("Execution Desk", "Risk Officers", "Chief Investment Officer"):
        assert owner in " ".join(text.split()), f"the replacement does not name the {owner}"


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
    Sizing is the Execution Desk's proposal, the Risk Officers' argument, the
    CIO's decision and the safety floor's clamp — four stages, all after this one.

    What this does NOT do: understand English. It cannot tell a sizing demand
    from a typo fix. It guarantees only that no edit to these bullets reaches
    `main` unread, which is precisely how DEF244 got in.
    """
    import hashlib

    # ROUND-3 MINOR 1 — the pin covered "## Output style" only, and the auditor
    # put "Always close by recommending an allocation percentage" in "## Role"
    # instead. Invisible. Sectioning was a leftover from the pattern-matching
    # mindset: it assumed the defect knows where to live. The set is the FILE.
    # Reviewed 2026-08-11 (AT:R68, CR149 Tier A, Batch 3 of the CR143 remediation
    # programme). `bull_researcher.md` 63deed87ac60 → 7518a15c30d1.
    #
    # The guard's question, answered rather than bypassed: **does any bullet ask a
    # RESEARCHERS-phase agent to output a position size? No.** Three bullets
    # changed and one was added:
    #   * the citation ask (was "Cite 3–5 specific analyst points", 14/18
    #     zero-compliance) now asks the agent to NAME the analyst each piece of
    #     evidence came from, and to say so when a figure came from the fact sheet
    #     instead — attribution, no quantity of anything;
    #   * "Lead with the thesis in one paragraph" is deleted (it lost to the shared
    #     format contract 15/18; DEF236 made that contract satisfiable in Batch 1);
    #   * a falsifier bullet is ADDED — "state the level or figure that would BREAK
    #     this thesis, taken from the block above… not a caveat, a number". The
    #     "number" is a PRICE LEVEL scoped to the data block, and it sits directly
    #     above the bullet that forbids sizing;
    #   * the upside bullet gains the consensus target's missing-horizon disclosure.
    # The "not a position size" bullet naming the Trader, the Risk Debators, the PM
    # and the floor is **unchanged and still present** — verified by reading, not
    # by the hash.
    #
    # `bear_researcher.md` is untouched this round and its hash is unchanged, which
    # is itself the check that this edit stayed in its lane.
    # CR160 review (AT:R73, 2026-08-20): the six-agent rename touched three
    # lines in bull_researcher.md (Trader→Execution Desk twice, Risk Debators/
    # Portfolio Manager→Risk Officers/Chief Investment Officer once) and zero
    # bullets' semantics; bear_researcher.md changed one redirect line. The
    # guard's question, answered by reading the diff: does any bullet ask a
    # RESEARCHERS-phase agent to output a position size? **No** — labels moved,
    # demands did not. bull 7518a15c30d1 → 8ae050f9662e, bear 1eef572f0cdc →
    # aea7af1e0f8e.
    #
    # CR219 R16 review (2026-09-02, WP03): one word changed in bull_researcher.md
    # — the "end with your CONVICTION" bullet's own term, renamed to "case
    # strength" (the "## Voice" section's "Conviction without hyperbole" opener
    # renamed the same way, for the same reason). Ruled disambiguation, not a
    # sizing change: CONVICTION is the machine-parsed stance envelope's field
    # name (`room_prompts.py`, `room_runner.py:_CONVICTION_FIELD_RE`); the
    # persona instructing the model to write it again at the end of its own
    # prose collided with the envelope's "write it ONCE, at the top only." The
    # guard's question, answered by reading the diff: does any bullet ask a
    # RESEARCHERS-phase agent to output a position size? **No** — the
    # not-a-position-size bullet naming the four downstream stages is unchanged
    # in substance, only its own label moved. bear_researcher.md is untouched
    # this round (it never carried the collision — grepped, zero hits) and its
    # hash is unchanged. bull 8ae050f9662e → fbc32f36b800.
    #
    # CR219 R17 review (2026-09-02, WP03, same commit): the "You DO NOT
    # Speculate beyond the data" bullet is reworded to scope the ban to
    # FACTUAL claims (a number, level or date the data does not support) and
    # explicitly exempt dating your own inference — which the "Frame upside
    # numerically" bullet two above it explicitly asks for ("if you pair it
    # with a date, the date is yours and you must say so"). Before this reword
    # the two bullets contradicted each other on exactly that instruction. The
    # guard's question, answered by reading the diff: does any bullet ask a
    # RESEARCHERS-phase agent to output a position size? **No** — the edit is
    # entirely inside the speculation ban's own scope, not the sizing bullet.
    # bull fbc32f36b800 → 275a868123c5.
    expected = {
        "bull_researcher.md": "275a868123c5",
        "bear_researcher.md": "aea7af1e0f8e",
    }
    actual = {
        name: hashlib.sha256(
            (_CONTENT / name).read_bytes()
        ).hexdigest()[:12]
        for name in expected
    }

    assert actual == expected, (
        "A researcher's output-style bullets changed. This is a REVIEW PROMPT, "
        "not a failure — read the diff and answer: does any bullet ask a "
        "RESEARCHERS-phase agent to output a position size? Sizing belongs to the "
        f"Execution Desk, the Risk Officers, the CIO and the floor (DEF244). Then update "
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

    # CR219 R18 (2026-09-02, WP03): trader.md's WAIT/HOLD carve-out states
    # "Size: 0.00% of portfolio" verbatim, matching the CR210 decoding grammar
    # (trader_block_regex, room_prompts.py: `Size: +0\.0{1,2}% of portfolio`)
    # exactly. This is NOT a modelled outcome magnitude in DEF245's sense (a
    # figure the model reasons its way to and might reuse elsewhere) — it is a
    # fixed FORMAT-CONTRACT constant: the one and only value the machine-parsed
    # grammar accepts on a no-position turn, there to keep the persona's prose
    # in sync with what the parser already enforces. A deliberate, reviewed
    # addition per this test's own rule.
    _ALLOWED: set[str] = {
        "Size:           0.00% of portfolio",
        "out of — state Size: 0.00% and stop there, rather t",
    }

    # ROUND-3 MINOR 2 — `\d+` misses "twenty-five percent". Adding number WORDS is
    # not a return to the word lists that failed twice: English number words are a
    # CLOSED set (one…twenty, the tens, hundred), so enumerating them is complete
    # in a way that enumerating synonyms for "decline" never was. Bare "percent"
    # is deliberately allowed — `bear_researcher.md` says "derive the percentage
    # from two prices", which is the instruction, not a figure.
    _NUM_WORD = (
        r"(?:one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|"
        r"thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty|"
        r"thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred)"
    )
    text = (_CONTENT / filename).read_text(encoding="utf-8")
    hits = [
        m.group(0).strip()
        for m in re.finditer(
            rf"[^\n]{{0,40}}(?:\d+(?:\.\d+)?%|{_NUM_WORD}(?:[\s-]+{_NUM_WORD})*"
            rf"[\s-]+per\s?cent)[^\n]{{0,25}}",
            text, re.IGNORECASE,
        )
        if m.group(0).strip() not in _ALLOWED
    ]
    assert not hits, (
        f"{filename} contains a literal percentage. A model reuses the figures it "
        f"is shown — `-25%` reached 22 of 811 real verdicts and became the most "
        f"common downside magnitude AMI produced (DEF245). Use a placeholder (N%, "
        f"X%) or take the number from the fact sheet at runtime: {hits}"
    )
