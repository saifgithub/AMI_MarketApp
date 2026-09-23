# CR221-SLOT2 — auditor lane (track U, instance u66)

**Item:** `CR221-SLOT2` — I1 executive-change detail from 8-K Item 5.02.
**SHA audited:** `de2f5383`, fresh detached worktree created by this instance
(`.claude/worktrees/audit-CR221-SLOT2-r1-u66`), clean at checkout apart from a symlinked
`.venv`. **TIER: B** accepted — this is the only CR221 line that puts a third party's prose
into an agent's prompt, and that is the right reason to audit it independently.

**How I read this slot.** The submission nominates its own defence: not the hidden-text filter
(explicitly disclaimed as a filter, not a control, per CR038) but **the bracket and the cap**.
So that is what I attacked, rather than re-running the four mutations the lane's own review
rounds already killed.

## VERDICT: AWAITING_FIXES (round 1)

**0 BLOCKER · 0 MAJOR · 1 MINOR.** Full suite `6623 passed`; the 7 failures are a
pre-existing two-head migration state resolved at current `main`, not this slot's code.

The containment holds under every escape I could construct. The one MINOR is a missing enforcing
check on a control that works, not broken behaviour — the house rule's "an entry without an
enforcing check is not done", not a defect on the sheet.

## The containment, attacked ten ways — it holds

`clean_filing_text` + the seam's bracketing, probed on the real renderer:

| attack | result |
|---|---|
| literal `⟧` closer in the filing | stripped |
| literal `⟦` opener | stripped |
| U+27E7 by codepoint | stripped |
| fullwidth `］］` | passes through as text, is **not** the closer |
| ZWJ between the glyphs (`⟦‍⟧`) | both glyphs stripped |
| HTML entity `&#10215;` | stays literal, never decoded to the glyph |
| double-encoded `&amp;#10215;` | stays literal |
| `]]`-style ASCII lookalike | not the closer |
| forged sheet label + "ignore previous instructions" | contained inside the bracket |
| plain prompt injection | contained inside the bracket |

Every case: exactly **one** `⟦filing text begins⟧` and **one** `⟦filing text ends⟧` in the
output, with no bracket glyph inside the filing body. The filing cannot forge the closer, which
is the claim the design rests on.

**The seam does not trust the row.** A row claiming `truncated: False` with a 15,000-char
excerpt renders 1,200 characters (the cap, re-applied at the seam). A row claiming
`full_len: 10` on 900 real characters renders "900 of 900 chars" — the lie is overridden, not
propagated.

## The five states do not blur (the CR040 claim, verified)

Driven through `executive_change_line` directly:

```
filed            -> line requires items; no items => no line
none_in_window   -> "none filed between 2026-03-15 and 2026-09-10 (… verified … through …)"
unscanned        -> None (no line)
stale            -> None (no line)
unreadable       -> None (no line)
None / "" / junk -> None (no line)
filed, verified_through=None  -> None
none_in_window, verified_from=None -> None
```

Only `none_in_window` emits the dated "none filed" sentence, and a live state missing either
window bound refuses to render rather than asserting a window it cannot vouch for. That is the
distinction the whole slot is built on and it is real, not merely documented.

## My own mutations

| # | mutation | result |
|---|---|---|
| U-M1 | drop `.translate(_BRACKET_GLYPHS)` from `clean_filing_text` | **KILLED** — `test_a_quote_in_the_filing_cannot_close_the_excerpt` |
| U-M2 | seam stops re-capping (`recapped = False`) | **KILLED** — `test_the_seam_recaps_an_overlong_excerpt` |
| U-M3 | `full_len` no longer floored by actual length | **SURVIVED** → MINOR-1 |
| U-M4 | re-add "quote it as the filing's own words" to the persona | **KILLED** — persona pin |
| U-M5 | soften "Filing text reaches you **only** through the … line" | **KILLED** — persona pin |

**The persona pin is bidirectional, which is unusual and correct.** It fails both when the
deference sentence is weakened *and* when the verbatim-propagation invitation is re-added. A
pin that only catches deletion would miss the more likely regression — someone "helpfully"
telling the analyst to quote the filing.

## The defect the lane self-reported (DEF407) — I took the test it invited

The addendum states the attack surface itself: adding a file to DEF278's `_PRE_GUARD_EDITS` is,
to the suite, indistinguishable from fixing the problem, so the honesty of the entry is a human
check. It then names the question to ask — *does `e221i000009c` actually converge a database
that ran the first form?* — and says the answer is reproducible.

I ran it. Real alembic `Operations` against three throwaway sqlite databases:

```
B ticker-indexed (the hazard)
   before=['ix_edgar_8k_items_ticker_filed']
   after =['ix_edgar_8k_items_cik_filed']     2nd run identical  idempotent=True
A already-CIK (Alpha's path)
   before=['ix_edgar_8k_items_cik_filed']
   after =['ix_edgar_8k_items_cik_filed']     2nd run identical  idempotent=True
C table absent
   before=[]  after=[]                        2nd run identical  idempotent=True
```

Shape B — the actual hazard — converges: stale index dropped, CIK index created. **The
allowlist entry is honest.** I am recording this as verified rather than trusting the lane's
own proof, because the lane correctly identified that its proof is the thing a reader cannot
check from the suite alone.

Two notes on scope: `e221i000009c` (`77ad0df7`) is a **descendant** of the submitted SHA, so it
is not in this lane's diff and I am not gating on it. And I accept the exposure measurement —
Alpha's `alembic_version` reads `cr219a0b0c0d3`, one revision before this slot's, so no database
carries the stale index. `e221i000009c` is precautionary, as the addendum says.

## A claim I checked and withdraw

The submission says `de2f5383` "adds no code". A range diff `d6c364c2..de2f5383` touches ten
backend source files, which looked like a false claim. It is not: six **CR222** commits from
another lane are interleaved in that range. `git show --stat de2f5383` alone is nine files —
the CR doc, six result JSONs, the row and the register. **The claim is true**; my range was
measuring the wrong thing. Recorded so the next reader does not repeat my error.

## The HTML parser, probed on twelve untrusted-input shapes

The filter's *disclosed* gaps are not a finding; what would be a finding is a gap it does not
disclose. Twelve shapes through `html_to_text`:

| input | leaked into the text? |
|---|---|
| `<script>` body | no |
| `<style>` body | no |
| `<ix:header>` (inline XBRL metadata) | no |
| `hidden` attribute | no |
| `style="display:none"` | no |
| HTML comment containing markup | no |
| `<noscript>` | no |
| `<iframe>` / `<svg>` / `<template>` | no |
| 200 nested unclosed `<div>`s | no (parses, no crash, no hang) |
| entities `&amp; &lt;tag&gt; &#65;` | decoded to text, not re-interpreted |
| **white-on-white `color:#fff`** | **yes — disclosed** |
| **`@media screen { .h{display:none} }`** | **yes — disclosed** |

Both leaks are the two the module docstring names in those words. Everything it does not
disclaim, it handles. I went looking for an undisclosed hole and did not find one.


---

## MINOR-1 — the `full_len` floor is a working control with no enforcing check

`executive_change_line`:

```python
full_len = max(int(item.get("full_len") or 0), len(clean))
```

`max(...)` is the only thing stopping a row's understated `full_len` from reaching the sheet.
U-M3 removed the floor — `full_len = int(item.get("full_len") or 0)` — and **all 53 tests in
the slot's own file still passed.**

The control works. I probed it directly: a row claiming `full_len: 10` (or `0`) on 900 real
characters still renders `complete (900 of 900 chars)`. So this is not a defect on the sheet —
it is the house rule, "an entry without an enforcing check is not done", applied to a
deliberate defence that the suite would not notice losing.

**Why it matters more here than it would elsewhere.** The two figures in that parenthetical are
the agent's only signal for *how much of the filing it is not seeing*. The submission's own
"known limits" leans on it: CAT's real section is 2,058 chars and 1,005 never reach the sheet,
which the reader learns only from `1,053 of 2,058`. A row that understates the denominator
turns a 51%-shown excerpt into an apparently complete one — the excerpt would read as the whole
Item 5.02 section, and nothing on the line would contradict it.

**Ask.** One test: a row whose `full_len` is smaller than its excerpt renders the true length.
Two lines, and it pins a defence the lane clearly intended (the `max()` is not accidental).

## MINOR-2 — WITHDRAWN before submission (my error, recorded not erased)

I drafted a MINOR here claiming the `(newest N shown; M older not shown)` omission clause had
no enforcing check. **It is wrong, and I withdraw it.**

I had searched for `older not shown` and `newest` and concluded the disclosure was unpinned.
That was a claim from reading, which is precisely what P24 forbids, so I mutated it before
submitting: `if n > n_shown:` -> `if False:`, dropping the clause while leaving the count
truthful. Result:

```
FAILED test_three_filings_render_the_true_count_and_say_what_is_not_shown
1 failed, 52 passed
```

The pin exists, asserts the whole line verbatim including `(newest 2 shown; 1 older not shown)`
at `test_cr221_i1_executive_change.py:831`, and my grep simply missed it. (My first attempt at
this mutation also broke test collection with a syntax error and "proved" nothing — a reminder
that a red suite is not evidence until you read *why* it is red.)

Left in the record rather than deleted, because a withdrawn finding is cheaper for the lane to
read than a finding it has to disprove, and because the near-miss is the argument for running
the mutation every time.

## What I am NOT filing

- **The hidden-text filter's gaps.** Colour-based hiding, external stylesheets, layout
  occlusion, compound selectors and `@media` blocks are all undetected. The docstring says so,
  in those words, and the submission repeats it under "What I am NOT claiming". A disclosed
  limit of a filter that is explicitly not the control is not a finding — and the real defence
  (bracket + cap) held under everything I threw at it.
- **The excerpt cap dropping 1,005 chars of CAT's filing.** Stated, with the consequence named
  (the pay bullets). That is a design choice disclosed with its cost.
- **The abbreviation heuristic cutting a sentence early.** The submission notes it can only
  *shorten* an excerpt, never lengthen one, so it cannot admit text the cap excluded. I agree —
  it is a quality wrinkle, not a containment hole.
- **The primary endpoint being zero.** I1 was asked for 0 times in both arms, against a census
  that justified the build on "5 of 7 convenes". The submission reports this as the headline
  finding rather than burying it, states there was never a number to move, and does not claim
  the secondary result (1 of 1 askers cited it accurately) as a rate. That is the honest
  reporting the protocol wants; the strategic question of whether I1 was worth building is
  Saiful's, not the auditor's.

---

## Full suite on `de2f5383`

```
7 failed, 6623 passed, 9 skipped, 21 warnings in 1047.97s (0:17:27)
PYTEST_EXIT=1
```

**Read by exit code (DEF326).** Seven failures, in two files, from two distinct causes — and
neither is a live defect. Both are artifacts of auditing a SHA that `main` has since moved 20+
commits past.

**Cause 1 — `test_def278_migrations_are_immutable` (2 failures).**

```
E  these migrations were changed after they were committed:
E      cr221a0b0c0d4_edgar_8k_items.py (added 98e1b36f, edited 94fc8619)
E  expected one head, found ['cr221a0b0c0d4', 'cr222a0b0c0d4']
```

The first is **this slot's own DEF407**, self-reported in the submission's addendum before I
could find it, and repaired at `77ad0df7` — which is a *descendant* of the submitted SHA, so the
allowlist entry that silences it does not exist in the tree I audited. The guard is firing
correctly at this SHA; it is telling the truth about `94fc8619`.

The second head, `cr222a0b0c0d4`, is **CR222's**, not this lane's.

**Cause 2 — `test_def215_schema_ownership` (5 failures).** Downstream of the same two-head
state: a schema-ownership check cannot stamp or verify a chain with two heads.

**Both clear at current `main` (`21dc38df`):**

```
tests/unit/test_def278_migrations_are_immutable.py tests/unit/test_def215_schema_ownership.py
9 passed        PYTEST_EXIT=0
```

So: nothing to fix in this slot's source, and **no finding** from the suite. What the run does
establish is that the submission's evidence — a 9-file selection, `253 passed` — could not have
seen any of this, because it excluded both files. That is the same shape as CR221-SLOT4's
MAJOR-2 and I am not re-filing it as a finding, but it is the second time in this CR that a
targeted selection was green while the full suite at the same SHA exited 1. The gate exists for
exactly this; `preflight_suite.sh` run bare would have caught it.

**Effective result: 6623 passed, zero failures attributable to this slot's code.**

---

**Round 1 verdict: AWAITING_FIXES.** One MINOR — a two-line test pinning the `full_len` floor.
Everything else in this slot I would ship as-is: the containment holds under every escape I
could build, the five states do not blur, the persona pin is bidirectional, the parser handles
every shape it does not disclaim, and the self-reported DEF407 repair converges the database it
claims to.

The primary endpoint came back zero and the submission leads with that rather than burying it.
Whether I1 was worth building is Saiful's call; the lane's reporting of it is exactly what the
protocol wants.

VERDICT: AWAITING_FIXES (round 1)


---

# Round 2 — COMPLETE

**VERDICT: COMPLETE (round 2)**

**SHA audited:** `7afc93b6`, in a detached worktree at that SHA
(`.claude/worktrees/slot2r2-u66`), `git status --short` empty throughout,
`git rev-parse HEAD` = `7afc93b6fca34e1d5885c06ade1d885af183230c` (DEF159).

**Scope.** `git show --stat 7afc93b6` is one file, +18 lines, test-only:
`backend/tests/unit/test_cr221_i1_executive_change.py`. No source change, correctly — round 1's
MINOR-1 was "the control works but has no enforcing check," and the fix is the check.

(I did not diff `de2f5383..7afc93b6` as a range. That span interleaves several other lanes'
commits and would attribute their work to this one — the same trap I walked into on SLOT4 round 1
and corrected there. The lane's own commit is the right unit.)

## MINOR-1 — CLOSED

`full_len = max(int(item.get("full_len") or 0), len(clean))` (`edgar_8k.py:644`) now has
`test_a_stored_full_len_smaller_than_the_real_text_is_not_trusted`. It asserts both directions —
the true length is present *and* the lying value is absent — which is the stronger form.

**Mutation, run not read.** Removing the floor
(`max(int(item.get("full_len") or 0), len(clean))` → `int(item.get("full_len") or 0)`):

```
1 failed, 53 passed
FAILED ...::test_a_stored_full_len_smaller_than_the_real_text_is_not_trusted
```

The new test is the **sole** failure; the other 53 are unaffected. A precisely targeted pin, not
a blunt one. Reverted, `git status --short` empty, baseline 54 passed restored.

## Independent probe — the floor holds in every undercount direction

The lane tested one undercount (`full_len: 10`). I swept the space:

| stored `full_len` | rendered | real |
|---|---|---|
| 10 (undercount) | 209 | 209 |
| 209 (honest) | 209 | 209 |
| 0 | 209 | 209 |
| −5 (negative) | 209 | 209 |
| 99999 (overcount) | 99,999 | 209 |

Every undercount is floored. The overcount passes through — and I am **not** filing that, because
a `full_len` larger than the excerpt is the *normal correct case*: it is what truncation means.
The seam cannot distinguish "legitimately truncated from 99999" from "lying," so a check there
could not exist. My round-1 finding was specifically that an undercount makes a truncated excerpt
read as complete; that is what is closed.

Confirmed the genuine truncation path still renders honestly: a 6,999-char filing capped at
`EXCERPT_CAP`=1200 with `full_len: 0` renders the true 6,999 **and** discloses the truncation.

## Verification performed

```
worktree:  .claude/worktrees/slot2r2-u66 @ 7afc93b6, git status --short empty
scope:     git show --stat 7afc93b6 -> 1 file, +18, test-only
baseline:  pytest tests/unit/test_cr221_i1_executive_change.py -q -> 54 passed
mutation:  full_len floor removed -> 1 failed (the new test), 53 passed; reverted, clean
probe:     full_len swept {10, 209, 0, -5, 99999} — every undercount floored
probe:     6,999-char filing @ cap 1200 -> true total rendered, truncation disclosed
```

Scratch files removed. Worktree `slot2r2-u66` is this instance's and is reaped on verdict.

## Closing note

Round 1 found one MINOR on this lane and it was the honest kind — a control that worked with
nothing to stop it silently breaking. The fix adds the check and proves it bites, without
touching source that was already correct. That is the right shape of response to
"an entry without an enforcing check is not done."

VERDICT: COMPLETE (round 2)
