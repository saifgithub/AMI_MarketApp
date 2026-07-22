# DEF083 — DEF079's positional-reference guard is too narrow; 11 quiz explanations still point at the wrong option

**Area:** content (+ one-line backend test change)
**Source:** prompt (found by the CR060 accuracy sweep, then confirmed deterministically)
**Round:** AT:R64
**Status:** open
**Relates to:** DEF065 (numeric option refs), **DEF079** (positional option refs — resolved, incompletely), CR060

---

## Summary

`DEF079` fixed 10 quiz explanations that named a distractor by position and extended the
guard to catch them. It is marked resolved with *"0 positional quiz refs remain."* That claim
is true **only under the guard's own regex**, which requires the literal word `option(s)`
after the ordinal:

```python
# backend/tests/unit/test_lesson_corpus_integrity.py:36
_OPTION_INDEX_CITATION = re.compile(
    r"\boptions?\s+\d|\b(?:first|second|third|fourth|fifth|last)\s+options?\b",
    re.IGNORECASE,
)
```

Explanations in this corpus overwhelmingly write **"the first one"**, **"the first answer"**,
or a bare **"the last — 'quoted distractor'"**. None of those contain the word `option`, so
none are caught. Verified by direct test against the live regex:

| explanation phrasing | guard |
|---|---|
| `"…is the first option"` | **CAUGHT** |
| `"…references option 2"` | **CAUGHT** |
| `"…is the first one: 'the crowd has new information'"` | **MISSED** |
| `"…is the last — 'same dollar risk, same outcome'"` | **MISSED** |
| `"The first answer fuses two unrelated signals"` | **MISSED** |
| `"The fourth one — rejecting verdicts — is also healthy"` | **MISSED** |

## Why it is a real defect, not a style nit

`scripts/shuffle_quiz_answers.py::shuffle_lessons()` reorders quiz options; `db8b558`
(2026-07-18) ran that randomisation across the corpus. Ordinal prose in the explanations was
not rewritten, so the ordinal now names a different option than it did when authored. The
reader renders **no** option labels (no A/B/C/D, no numbering), so the phrase already names
nothing the learner can see — and where it resolves at all, it resolves to the wrong distractor.
The explanation therefore teaches the error: it tells the learner the trap was option X when
the trap is option Y.

This is the DEF065/DEF079 failure class, third occurrence. Per the house rule
(`docs/initial_specs/08_tech/failure_patterns.md`), the fix must ship **with** a widened guard.

## Evidence — 11 machine-confirmed mismatches

Each row was confirmed by resolving the explanation's **own quoted distractor text** to the
option index that actually contains it, then comparing against the index the ordinal implies.
No LLM judgement involved.

| lesson | quiz | ordinal says | actually is | quoted distractor |
|---|---|---|---|---|
| `019_survival_mindset` | 1 | opt0 | **opt3** | 'press your edge after wins' |
| `019_survival_mindset` | 2 | opt3 | **opt1** | 'only the final number matters' |
| `045_greed` | 1 | opt0 | **opt3** | 'the crowd has new information' |
| `049_overconfidence` | 3 | opt3 | **opt1** | 'raise the mandate to match behaviour' |
| `103_trailing_stops` | 2 | opt0 | **opt2** | 'tighter trail = closer to peak' |
| `110_tail_risk_and_fat_tails` | 1 | opt0 | **opt1** | '5% moves are rare' |
| `110_tail_risk_and_fat_tails` | 2 | opt3 | **opt1** | 'tail events are too rare to plan for' |
| `111_gamblers_ruin_and_the_one_percent_rule` | 1 | opt0 | **opt1** | 'sizing and ruin scale linearly' |
| `200_pyramiding_into_winners` | 1 | opt0 | **opt3** | 'risk stays at 1% because the trade is working' |
| `276_spotting_hallucinated_numbers` | 1 | opt0 | **opt3** | 'twelve agents would have caught it' |
| `277_pass_is_not_buy` | 1 | opt0 | **opt3** | 'AMI has approved' |

`276` and `277` matter beyond quiz mechanics — they are the lessons that teach users **not to
over-trust AMI** ("spotting hallucinated numbers", "pass is not buy"). Their explanations
currently misidentify the trap answer.

## Evidence — 13 more positionally fragile (same class, not machine-confirmable)

These use an ordinal to name an option but quote no distractor text, so the mismatch cannot be
proven mechanically. They are fragile by construction and violate DEF079's own established fix
pattern (*name the distractor by content*). Each needs an eyeball against its `options` array:

`013` q2 · `014` q2 · `059` q1 · `075` q2 · `077` q2 · `101` q2 · `201` q3 (×2) ·
`202` q1 · `254` q1 · `274` q1 · `275` q2 · `279` q2

(`101_volatility_adjusted_sizing` q2 was independently refuted by the CR060 sweep — its
"the last — 'same dollar risk, same outcome'" points at opt3 while that content sits at opt1 —
so the true confirmed count is **at least 12**.)

## Fix

1. **Reword all 11 confirmed + the 13 fragile** to name the distractor by content, exactly the
   pattern DEF079 established (e.g. `047` → "the 'anger' answer"). Only explanation prose
   changes; question, options and `answer` index are untouched.
2. **Widen the guard** in `backend/tests/unit/test_lesson_corpus_integrity.py:36` so the ordinal
   need not be followed by the literal word `option`:
   ```python
   r"\boptions?\s+\d"
   r"|\b(?:first|second|third|fourth|fifth|last)\s+(?:options?|ones?|answers?|choices?)\b"
   r"|\bthe\s+(?:first|second|third|fourth|fifth|last)\s*[—–-]"
   ```
3. **Prove the guard bites before it passes** — revert one reworded explanation, confirm the
   corpus test goes red naming that lesson, restore. (DEF079 did this; do it again for the
   widened pattern.)
4. **`scripts/shuffle_quiz_answers.py`** already refuses on a surviving positional ref — update
   its detector to the same widened pattern, or the refusal inherits the identical blind spot.

## Routing

The guard file and `shuffle_quiz_answers.py` are the DEF079/DEF065 lane's (commit `88cd4e4`,
`AT:noncoder.edu`, 5 h before this filing). **Handing off rather than editing** — CR060's lane
verifies and reports, it does not edit another lane's content or guards. Evidence above is
apply-ready; no re-derivation needed.

## Note on how this was found

The CR060 sweep surfaced 3 of these (RISK 7/8/9) as incidental refute-pass findings. The other
8 came from a deterministic corpus scan written after noticing the pattern. **The scan is the
cheaper detector** — this class needs no LLM at all, which is the argument for making it a
guard rather than a periodic audit.
