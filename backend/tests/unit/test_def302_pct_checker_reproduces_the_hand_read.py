"""DEF302 — the derived-% checker must produce the number the record quotes.

Filed out of the R68-CR179 audit, MINOR-2. `cr179_leg5_pct_check.py` v2 called
itself "PRECISION-corrected" while still scoring `"N% below entry"` against the
last close, so running it gave **6/40 and 4/29** where every document citing it
said 3/40 and 1–2/29. The corrected figures were right; they came from a
hand-read that was never written down. The artefact and the record disagreed
for a day and only an independent auditor re-running the script noticed.

That is the failure this file exists to make impossible: **a published
measurement whose own instrument cannot reproduce it.** The rates below are
therefore asserted against the committed corpora, so the script and the CR doc
can never drift again without something going red.

What is deliberately NOT asserted:

  - No trend between the two epochs. Fisher exact on 3/40 vs 2/29 is p = 1.000
    (the audit ran it), and "flat" is itself a positive claim these n cannot
    support. The two numbers are pinned individually and never compared.
  - Nothing about whether the model's behaviour improved. This measures where a
    percentage's referent is, which is a property of prose, not of reasoning.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[3]
_CORPUS = _ROOT / "docs/forward_planning/CR143_agent_prompt_audit/corpus"
_LEG5 = _CORPUS / "llm_audit_2026-08-14-epoch.json"
_BASELINE = _CORPUS / "llm_audit_2026-08-13-epoch.json"
_SCRIPT = _ROOT / "backend/scripts/cr179_leg5_pct_check.py"


def _checker():
    """Import the script without running its `sys.argv` tail.

    It is a script, not a module — it ends in three bare `run(...)` calls that
    read `sys.argv`. Loading it normally would execute those at import time and
    fail on a missing argv, which is why this goes through a spec and stops at
    the functions it needs.
    """
    if not _SCRIPT.exists():  # pragma: no cover
        pytest.skip(f"checker not present: {_SCRIPT}")
    src = _SCRIPT.read_text().split("rows = run(")[0]
    spec = importlib.util.spec_from_loader("_pct_check_v3", loader=None)
    mod = importlib.util.module_from_spec(spec)
    exec(compile(src, str(_SCRIPT), "exec"), mod.__dict__)
    return mod


@pytest.fixture(scope="module")
def checker():
    for p in (_LEG5, _BASELINE):
        if not p.exists():
            pytest.skip(f"committed corpus not present: {p}")
    return _checker()


def _tally(mod, path: Path) -> tuple[int, int]:
    import collections
    import json

    corpus = json.loads(path.read_text())
    scored = 0
    bad = 0
    for t in corpus:
        p = t["system_prompt"] or ""
        m = mod.CLOSE.search(mod._section(p, "Fact sheet as of", "Transcript so far"))
        if not m:
            continue
        close = mod.f(m.group(1))
        body = mod._strip_envelope(t["response_text"] or "")
        for mm in mod.PAIR.finditer(body):
            tail = body[mm.end():mm.end() + 55]
            if not mod.REF_CLOSE.search(tail):
                continue
            if mod.REF_OTHER.search(body[mm.end():mm.end() + 30]):
                continue
            lvl, pct = mod.f(mm.group(1)), float(mm.group(2))
            if lvl <= 0 or close <= 0:
                continue
            entry_ref = bool(mod.REF_ENTRY.search(tail)) and not mod.REF_CLOSE_ONLY.search(tail)
            entry = mod._entry_in(body, mm.start()) if entry_ref else None
            scored += 1
            if not mod._is_consistent(lvl, pct, close, entry, entry_ref):
                bad += 1
    assert collections  # keeps the import honest if the body above is edited
    return scored, bad


def test_the_leg5_rate_is_the_one_every_document_quotes(checker):
    scored, bad = _tally(checker, _LEG5)
    assert (scored, bad) == (40, 3), (
        f"Leg 5 gives {bad}/{scored}; the CR doc, DEF302's row and the audit "
        f"verdict all say 3/40. Whichever is wrong, they must not disagree — "
        f"that disagreement IS this defect."
    )


def test_the_baseline_rate_is_the_one_every_document_quotes(checker):
    scored, bad = _tally(checker, _BASELINE)
    assert (scored, bad) == (29, 2), (
        f"baseline gives {bad}/{scored}; the hand-read reported 1–2 of 29 and "
        f"this instrument resolves it to 2"
    )


def test_the_fix_changed_the_verdict_and_not_the_scored_population(checker):
    """The correction must be a change of judgement, not of sample.

    A 'fix' that reached 3/40 by scoring fewer pairs would be indistinguishable
    from one that reached it by judging them correctly — and the first is how a
    metric quietly stops measuring. The denominators v2 produced (40 and 29) are
    pinned here so any future loosening of the *exclusion* rules shows up as a
    separate failure from a change in the *consistency* rules.
    """
    assert _tally(checker, _LEG5)[0] == 40
    assert _tally(checker, _BASELINE)[0] == 29


def test_the_limit_entry_case_is_scored_against_the_entry_it_names(checker):
    """The exact turn that got DEF302 filed against the wrong agent.

    `Stop: $164.70 (-5% below entry)` under `Entry: $173.40 (limit buy at the
    50-day SMA)`, against a $203.62 close. 164.70/173.40 − 1 = −5.02%, correct.
    v2 scored it against the close, called it wrong, and the defect named the
    Trader — the agent whose stop-distance claims were right in both epochs.
    """
    assert checker._is_consistent(164.70, -5.0, 203.62, 173.40, True)
    # ...and with no entry stated there is nothing to score it against but the
    # close, which is what makes the entry lookup load-bearing rather than a
    # blanket amnesty.
    assert not checker._is_consistent(164.70, -5.0, 203.62, None, True)


def test_a_dollar_figure_that_is_a_distance_is_not_read_as_a_level(checker):
    """`$18.99 (8.4% below entry)` with entry $225.30 — 18.99/225.30 = 8.43%."""
    assert checker._is_consistent(18.99, 8.4, 203.62, 225.30, True)


def test_a_claim_that_names_the_close_cannot_be_rescued_by_an_entry(checker):
    """The asymmetry that keeps the genuine hits genuine.

    KTOS: `"waiting for a pullback to $43.09 (53.1% below current price)"`
    against a $62.79 close is −31.4%, and it is one of the three real
    misattributions. If the entry referents applied to every claim regardless of
    wording, a stated entry anywhere in the turn could explain this away — the
    check would converge on zero and stop being able to fail.
    """
    assert not checker._is_consistent(43.09, 53.1, 62.79, 45.0, False)


def test_the_three_survivors_are_still_flagged(checker):
    """The DEF302 class itself, pinned turn by turn.

    A future widening of the consistency rules that silently absorbed one of
    these would drop the measured rate and look like an improvement.
    """
    assert not checker._is_consistent(895.91, 70.6, 1528.11, None, False)
    assert not checker._is_consistent(1.03, 6.0, 1.34, None, True)
    assert not checker._is_consistent(43.09, 53.1, 62.79, None, False)
