"""GUARD (failure pattern P16) — a pattern that reads a claim out of agent prose
is pinned against a frozen corpus of what agents really wrote.

P16 was filed after DEF231 took four audit rounds and DEF234 shipped a
`$1,073.46 → $1.00` mis-parse to live Alpha. Its stated guard was "sweep the
corpus and read every extraction, and diff the extraction set against the
previous version" — and as filed that guard was a bash snippet in a markdown
file, which is a *reminder*, not a guard. This file is the executable version,
in the shape `test_config_compose_parity.py` and `test_prompt_data_parity.py`
already use for the same class of problem: a rule that used to depend on
somebody remembering becomes a thing the build says out loud.

What it does and does NOT prove:

  * It DOES catch a **coverage** change. Any edit to `_DIRECTIONAL_CLAIM_RES`
    that makes it match more or less of what the Room's Portfolio Manager
    actually writes fails here with the diff attached. That is precisely the
    signal that found DEF234's markdown hole (126 → 119), which was invisible
    in either extraction set read alone.
  * It does NOT catch a **false-positive class** the corpus has not produced.
    None of DEF231's three audit MAJORs appears once in 949 real verdicts —
    they were all found by adversarial construction, which lives in
    `test_def231_pm_direction_coherence.py`. The two instruments are
    complementary and neither substitutes for the other; that is the whole
    point of P16 and this file only implements half of it.

The fixture is every real `room_runs.verdict->>'reason'` string on Alpha
(2026-08-08) that carries a `$` figure — 811 rows, deduplicated. Simulation-only
content, model-authored, no user text and no identifiers. Refreshing it is a
deliberate act: re-export, re-read the diff, and update `_EXPECTED` in the same
commit.

**The selection criterion is deliberately independent of the verb set.** The
first version of this fixture selected rows carrying a `$` figure AND a
directional verb stem, which quietly made the guard's own population a function
of the thing it guards: broadening the verb set would have pulled in rows the
fixture did not contain, so the count would have moved for two reasons at once
and the diff would have been unreadable. Worse, a *narrowing* of the verb set
would have shrunk the population in lockstep and hidden its own coverage loss —
the exact failure this file exists to make impossible. A `$` is the only
property a row needs to be capable of exercising a level pattern, so that is
the whole criterion now.
"""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from app.services.room_runner import _DIRECTIONAL_CLAIM_RES

_CORPUS = Path(__file__).parent / "fixtures" / "pm_verdict_corpus.txt"

# A change to this number is not a failure — it is a REVIEW PROMPT. Update it
# only with the diff in front of you.
#
#   121  round-4 MINOR fix (`4b7faee8`), fixture = 603 verb-stem-selected rows
#   365  the offline LLM verb-gap sweep (AT:R66), fixture = 811 `$`-carrying rows
#
# The jump is two changes at once and they are separable. Re-selecting the
# fixture on `$` alone added 208 rows; the three verb families the sweep found
# — `breakout above|to` (159 extractions), `close above|below` (73), `clears`
# (12) — account for the rest. `breakout` alone yields more than the entire
# previous verb set did, because "wait for a confirmed breakout above $X" is the
# PM's single most common way of stating a level, and every one of those 365 was
# read before this number was changed.
_EXPECTED_EXTRACTIONS = 365

# Levels the corpus is known to contain that have historically been mis-parsed.
# Each is a defect that reached (or nearly reached) users.
_MUST_PARSE = {
    1073.46: "DEF234 — thousands separator; parsed as $1.00 and shipped to Alpha",
    27.65: "DEF234 — markdown emphasis; the round-2 whitelist silently dropped it",
    51.40: "round-4 MINOR — a preposition adjacent to a prepositionless verb",
}


def _extractions() -> list[tuple[str, float]]:
    lines = [ln for ln in _CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    out: list[tuple[str, float]] = []
    for line in lines:
        for pattern, _side in _DIRECTIONAL_CLAIM_RES:
            for m in pattern.finditer(line):
                out.append((m.group(0).strip(), float(m.group(1).replace(",", ""))))
    return out


def test_the_corpus_fixture_is_present_and_substantial():
    """A fixture silently emptied or truncated would make every check below
    pass vacuously — the failure mode this whole pattern is about."""
    lines = [ln for ln in _CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    assert len(lines) > 500, f"corpus fixture looks truncated: {len(lines)} rows"


def test_the_extraction_set_over_real_prose_has_not_moved():
    """The guard. If this fails, your change altered what the pattern matches in
    real Portfolio Manager output — read the diff before touching the number.

    A DROP is a coverage loss: prose the Room really writes that the pattern no
    longer sees. A RISE means it now matches text it previously ignored, which
    is where a false positive would first appear.
    """
    found = _extractions()
    assert len(found) == _EXPECTED_EXTRACTIONS, (
        f"extraction set moved: {len(found)} vs expected {_EXPECTED_EXTRACTIONS}.\n"
        "This is a review prompt, not a bug: read the extractions, decide whether "
        "each new/lost one is right, then update _EXPECTED_EXTRACTIONS in the same "
        "commit that changes the pattern.\n"
        f"sample: {sorted({c for c, _ in found})[:12]}"
    )


def test_no_extraction_stops_short_of_the_number_the_sentence_wrote():
    """DEF234's exact shape, generalised: a level captured mid-number is worse
    than one not captured at all, because the arithmetic downstream is confident
    and absurd ("107900.0% ABOVE $1.00")."""
    # A trailing comma is only a thousands separator when three digits follow —
    # `$80.83, aligning with...` is a clause boundary. The first version of this
    # check flagged both, which is the same "near enough" heuristic that caused
    # the defect it guards; the tail is now matched, not glanced at.
    lines = [ln for ln in _CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    truncated = []
    for line in lines:
        for pattern, _side in _DIRECTIONAL_CLAIM_RES:
            for m in pattern.finditer(line):
                if re.match(r"\d|,\d{3}(?!\d)", line[m.end():]):
                    truncated.append((m.group(0).strip(), line[m.end():m.end() + 8]))
    assert not truncated, f"level capture stopped mid-number: {truncated}"


def test_the_levels_that_previously_broke_us_still_parse():
    """Named regressions, each one a defect that reached or nearly reached a
    user. Pinned by value so a future tightening can't quietly drop them."""
    values = {v for _, v in _extractions()}
    missing = {v: why for v, why in _MUST_PARSE.items() if v not in values}
    assert not missing, f"a previously-fixed mis-parse has returned: {missing}"


def test_no_single_verdict_dominates_the_extraction_set():
    """Sanity on the corpus itself: if one verbose verdict supplied most of the
    extractions, the count above would be tracking that row rather than the
    pattern's behaviour on the population."""
    per_line = Counter()
    lines = [ln for ln in _CORPUS.read_text(encoding="utf-8").splitlines() if ln.strip()]
    for i, line in enumerate(lines):
        for pattern, _side in _DIRECTIONAL_CLAIM_RES:
            per_line[i] += len(pattern.findall(line))
    top = per_line.most_common(1)[0][1] if per_line else 0
    assert top <= 5, f"one verdict supplies {top} extractions — the count is not population-level"
