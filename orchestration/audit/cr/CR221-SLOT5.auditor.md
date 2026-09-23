# CR221-SLOT5 — auditor lane (track U, instance u66)

**Item:** `CR221-SLOT5` — C8 dividend growth (declared rate), C7 implied buyback price.
**SHA audited:** `bb47803d`, fresh detached worktree created by this instance
(`.claude/worktrees/audit-CR221-SLOT5-r1-u66`), clean at checkout apart from a symlinked
`.venv`. **TIER: B** accepted.

**How I read this slot.** The submission names four things for the auditor to attack and
reports its own first mutation sweep killing only 7 of 10 as *"a genuine gap in my tests,
reported here rather than quietly fixed"*. I took all four, and re-derived the arithmetic the
one surviving mutation rests on rather than accepting the algebra as written.

## VERDICT: AWAITING_FIXES (round 1)

**0 BLOCKER · 0 MAJOR · 1 MINOR.** Full suite `6662 passed`; the 2 failures are another lane's
edited migrations and one timing flake I caused myself — neither attributable to this slot.

## Attack 1 — the M9 equivalence argument: SOUND

The lane kept a `len(paired) < 4` check whose mutation to `< 3` survived, and argued it is
unreachable: `edgar_pit._QUARTER_SPAN = (70, 100)` and the contiguity tolerance is 7 days, so
three periods span at most 3x100 + 2x7 = 314 days against a span floor of 330.

I did not take the algebra on trust — a stated bound can be off by one in the direction that
matters. Exhaustive search over every 3-period window the filters admit (period lengths 70..100
inclusive x gaps 0..7 inclusive, both bounds verified against the source's `> 7` rejection):

```
max achievable 3-period span = 314 days   (periods 100,100,100 + gaps 7,7)
span guard requires         >= 330 days
=> three periods can reach the span guard?  False      (16-day margin)
```

**The survivor is genuinely equivalent, not an untested gap.** And the lane's reason for keeping
the check is the right one: its log message names the condition the span message would not, and
`test_three_paired_quarters_are_too_few_to_be_a_trailing_year` pins the 314 < 330 arithmetic, so
a future change to `_QUARTER_SPAN` re-opens the question loudly. That is a guard whose *purpose*
is to fail informatively if an upstream assumption moves — the opposite of a dead check.

## Attack 2 — do the isolating tests actually isolate? YES

The lane's own worry: *"the assertions are mine and could be wrong in the same direction as the
code."* The right test is not to re-read them but to remove one guard at a time and see whether
exactly the intended test dies.

| mutation | result |
|---|---|
| contiguity guard only (`abs(...) > 7` -> `if False:`) | `1 failed, 23 passed` — **only** `test_a_gap_in_the_middle_is_refused_by_contiguity_alone` |
| span guard only (`not (330 <= span <= 400)` -> `if False:`) | `1 failed, 23 passed` — **only** `test_four_contiguous_quarters_that_are_not_a_year_are_refused_by_span_alone` |

Each guard's removal kills exactly one test, and it is that guard's own test. The isolation is
real.

The construction deserves specific credit: each isolating test asserts *in-test* that the other
guard accepts its window —

```python
assert 330 <= span <= 400, (
    f"the span guard must ACCEPT this window ({span}d) or the test is not isolating contiguity")
```

— so the isolation claim is self-checking rather than a comment. That is the fix for exactly the
failure the lane reported against itself (two first drafts passing for the wrong reason because
half-year and 58-day periods never reach the resolver).

## Attack 3 — the declared-rate basis: NOT a preference, a correctness difference

The lane flags this as *"a judgement call, not a measurement"* and invites the view that the
default should be the calendar-year sum, since that is what a filer's annual report shows.

I reproduced the motivating case independently, on a synthetic Realty-Income-shaped feed
(monthly payer, declared rate rising every single month, one May ex-date slipping across a year
boundary so 2024 holds 11 ex-dates and 2025 holds 13):

```
SUM basis by year (the obvious implementation):
   2022: $3.081  (12 ex-dates)
   2023: $3.153  (12 ex-dates)
   2024: $2.954  (11 ex-dates)     <- a 6.3% CUT
   2025: $3.568  (13 ex-dates)
years the SUM basis shows a CUT: [2024]
...while the declared rate rose every month.
declared-rate CAGR on the same payments: 2.20%
```

So the choice is not between two defensible presentations. The sum basis prints **a dividend cut
that never happened**, caused entirely by an ex-date calendar artifact, for a company whose rate
rose monthly. The declared-rate basis is the one that makes a true statement about dividend
policy, and the line renders the cash-paid-by-year series beside it and names which is which —
so a reader who wants the filer's own annual figure has it, labelled.

**I sustain the judgement call, and I would sustain it as the default even if asked to reverse
it.** A basis that fabricates a cut is not a defensible default for an agent that reasons about
dividend safety.

## Attack 4 — C8 withheld on a mock-data run: CORRECT

`_overlay_capital_returns` sits inside `if as_of is not None or settings.use_real_market_data:`,
so C8 is withheld on a synthetic run even though the dividend feed is independent of EDGAR. The
lane believes this is right; I agree, and the enclosing comment states the reason:

> Attempted exactly when the fundamentals overlay above was attempted, so a mock-data run never
> mixes real filed figures into a synthetic sheet.

A real dividend-growth line beside synthetic prices is a sheet the reader cannot partition — the
worse failure. And the `else` branch does not merely skip the keys, it sets both explicitly:

```python
field_state["dividend_growth"] = LiveDataState.UNAVAILABLE.value
field_state["buyback_price"]   = LiveDataState.UNAVAILABLE.value
```

That is T-BACKFILL discipline — unknown stays unknown rather than collapsing into a
measured-clean absence.

## The money formatter, probed across its threshold

M11/M12 caught `:,.4g` dropping trailing zeros ($1.20 -> "$1.2"). The fix is
`f"{amount:,.2f}" if abs(amount) >= 0.10 else f"{amount:,.4f}"`. Probed at and around the
boundary:

```
1.20 -> $1.20     5.00 -> $5.00      0.10 -> $0.10
0.0995 -> $0.0995   0.09999 -> $0.1000   0.0025 -> $0.0025
1.005 -> $1.00    12.3456 -> $12.35
```

Correct in both directions. `0.0 -> $0.0000` is cosmetically odd but unreachable: a zero
declared rate means no dividend, which C8 resolves as absent rather than rendering.

## One thing the lane did not list, checked and filed as MINOR

`buyback_price_line` renders `price.avg_price`, `price.dollars`, `price.shares` and
`price.quarters` **without re-deriving any of them**. Fed a deliberately inconsistent object it
prints the contradiction verbatim:

```
Buyback average price (implied) (LIVE): $1.00 per share, $7,224M repurchased
  ÷ 10,869,082 shares acquired, as filed, over the 4 quarters …
```

($7,224M / 10,869,082 is $664.64, not $1.00.) Same for a span/quarters mismatch — it will render
*"the 4 quarters 2023-01-01 to 2026-03-31"*, a 3.25-year window labelled as four quarters, which
is precisely the `ttm()` hazard this slot's span guard exists to refuse.

**It is not reachable today, and that is why this is a MINOR and not a MAJOR.** I checked rather
than assumed: `BuybackPrice` has exactly one construction site
(`buyback_price.py:136`), `avg_price` is computed inline as `dollars / shares` from the same two
sums the line renders, and the object reaches `_format_profile` as a live Python object — there
is no JSON/cache round-trip that could desynchronise the fields.

**Why file it at all.** This slot's sibling seam, `executive_change_line` in CR221-SLOT2, makes
the opposite choice and says why in its own docstring: *"the profile dict is not trusted for
length any more than for content."* It re-sanitises and re-caps at the seam even though its
producer already did. Two seams in the same CR, rendering store-derived figures into the same
sheet, disagree about whether the seam validates. One of them is wrong, and the SLOT2 reasoning
is the one I would keep — a seam that re-derives a quotient it is about to attribute to "AMI's
own quotient of two filed figures" costs one line and makes the attribution self-verifying.

**Ask — the cheapest honest option, not the biggest.** Either recompute at the seam
(`price.dollars / price.shares`, and render *that*), or state in the docstring that the seam
trusts its producer and why that is safe here. I would accept either; what I would not accept is
leaving two sibling seams silently disagreeing with no note, because the next person to add a
third seam has to guess which convention is the house one.

Explicitly **not** a finding about the numbers on Alpha: flags are off, the resolver is correct,
and every figure I could reach through the real path was consistent.

---

## Full suite on `bb47803d`

The submission asked me to re-run this rather than trust its partial (green through 55%) run.
Done, bare, exit code read (DEF326):

```
2 failed, 6662 passed, 9 skipped, 21 warnings in 1200.12s (0:20:00)
PYTEST_EXIT=1
```

**Neither failure is this slot's, and I verified both rather than assuming.**

**1. `test_def278_migrations_are_immutable::test_no_committed_migration_has_been_edited`** — two
edited revisions, neither from this lane:

```
cr221a0b0c0d4_edgar_8k_items.py (added 98e1b36f, edited 94fc8619)
cr222a0b0c0d4_training_toll.py (added 6159a62b, edited 839c3283)
```

The first is **CR221-SLOT2's**, self-reported as DEF407 and repaired downstream at `77ad0df7`.
The second is **CR222's** — a different lane, and a second independent instance of the same
DEF278 mistake in the same week. This slot has no migration at all, exactly as its submission
states ("No migration, no schema change, no deletion"), so it cannot be the cause of either.

*Cross-track observation, one line and dropped per the stay-in-your-lane rule:* `cr222a0b0c0d4`
is CR222's to fix, and whoever owns that lane should know DEF278 is red on `main` for their
revision too — the guard is currently carrying two unresolved entries, and a guard that is
always red stops being read (P2/DEF135).

**2. `test_def136_room_convene_does_not_block_loop::test_the_loop_never_stalls_while_the_builders_block`**
— **a flake from my own measurement conditions, not a defect.** It is a timing assertion, and my
run overlapped up to ten concurrent pytest processes from other lanes on this shared checkout.
Re-run in isolation at the same SHA:

```
tests/unit/test_def136_room_convene_does_not_block_loop.py   2 passed   PYTEST_EXIT=0
```

It also carries zero references to `dividend_growth`, `buyback_price` or `capital_returns`.
Recorded as mine because a reader seeing "2 failed" in a verdict deserves to know which one the
auditor caused.

**Effective result: 6662 passed, zero failures attributable to this slot.**

---

**Round 1 verdict: AWAITING_FIXES.** One MINOR, and it is a consistency question between two
sibling seams rather than a defect on any sheet: either recompute the quotient at
`buyback_price_line`, or document that the seam trusts its producer.

Everything the lane invited me to attack survived the attack. The M9 equivalence is arithmetically
sound with a 16-day margin, the isolating tests genuinely isolate, the declared-rate basis is the
only one of the two that makes a true statement about a monthly payer's dividend policy, and the
mock-data withholding is right for the reason the code comment gives.

Two things I want on the record as done well. The lane reported its own first sweep killing 7 of
10 as a gap in its tests rather than quietly adding the three isolating cases — and then reported
that two first drafts of those cases passed for the wrong reason. And it kept a mutation survivor
it could have deleted, with the arithmetic that makes it unreachable pinned in a test, so the day
an upstream bound moves the question reopens loudly. That is the opposite of the dead-check
pattern this project keeps filing.

VERDICT: AWAITING_FIXES (round 1)


---

# Round 2 — COMPLETE

**VERDICT: COMPLETE (round 2)**

**SHA audited:** `7d552cca`, in a detached worktree at that SHA
(`.claude/worktrees/slot5r2-u66`), `git status --short` empty throughout,
`git rev-parse HEAD` = `7d552ccaf5f7e8b381f1b16ab2de0dc7583857c1` (DEF159).

**Scope.** `git show --stat 7d552cca` — two files, +29/−2:
`backend/app/services/fundamentals.py` (the seam) and
`backend/tests/unit/test_cr221_c8_c7_capital_returns.py` (its pin). Nothing else.

`buyback_price.py`, `dividend_growth.py` and `room_runner.py` were last touched before this SHA
(`b45bbda3`, `b45bbda3`, `83e9c6e6`), so round 1's verifications on those surfaces — the M9
exhaustive-search equivalence, the single-guard isolation, the declared-rate basis, the
mock-data `UNAVAILABLE` branch — carry forward unchanged and were not re-run.

## MINOR — CLOSED

`buyback_price_line` now computes `price.dollars / price.shares` at the render seam instead of
rendering the stored `avg_price`, matching the sibling seam (`executive_change_line`) that
round 1 flagged it for disagreeing with. The displayed quotient and the `÷ shares` line beside it
are now derived from the same two numbers, so they cannot disagree.

**Mutation.** Reverting the seam to `avg = price.avg_price`:

```
1 failed, 24 passed
FAILED ...::test_the_buyback_line_recomputes_the_price_rather_than_trusting_it
```

Sole failure. Reverted, `git status --short` empty, baseline 25 passed restored.

**The assertion is not tautological — checked, because it computes its expectation with the same
expression as the source.** That shape can pin "the field went unused" while being blind to a
wrong formula. So I mutated the *arithmetic* rather than the field:
`(price.dollars / price.shares) * 1.10` — a consistent but wrong quotient.

```
2 failed, 23 passed
```

Caught, by the new test and by `test_both_flags_are_off_by_default...`. The pin holds the
arithmetic, not merely the provenance.

**Independent probe** on the exact numbers from my round-1 finding:

| object | rendered |
|---|---|
| desynced `avg_price=1.00`, dollars/shares → 664.64 | **$664.64** (was $1.00 before the fix) |
| honest `avg_price=664.64` | $664.64 |
| `shares=0` (fallback branch) | $1.00 |

The `shares=0` branch is the one place the seam still reads `avg_price`, and it exists only to
keep the expression total rather than raise `ZeroDivisionError`. I verified it is genuinely
unreachable rather than taking the claim on trust: `buyback_price.py:51,125` —
`MIN_SHARES = 1_000.0` and `if dollars <= 0 or shares < MIN_SHARES: return None` at the sole
construction site. Correctly judged belt-and-braces.

## The full suite — run by me, because the submission left it open

SLOT5's round-2 text ends: *"Full `backend/tests/unit/` run bare (not piped — the exact DEF405
shape, caught while fixing this) is in progress at submission time; result appended below once it
lands rather than estimated."* It never landed — the submission ends at that sentence. Declining
to estimate was right; leaving it unfilled means the number was unverified at submission. I ran
it myself rather than accept it.

Bare, unpiped, exit code read directly (DEF326 — never the summary prose):

```
TMPDIR="/Volumes/Extreme Pro/ami_tmp" uv run pytest tests/unit/ -q --no-header
6696 passed, 9 skipped, 21 warnings in 1111.58s (0:18:31)
EXIT=0
```

**Fully green** — no failures at all, which is *cleaner* than the 3 pre-existing register
failures present at CR227's base (`c8543a12`). I checked why rather than accepting a suite that
improved on its own: both were fixed between that commit and this SHA, by the tracks that owned
the rows — `9f6a80b5` (CR228's `'in progress'` free-text status → the vocabulary token
`in_progress`) and `d923549c` (DEF412's FILES link with one `../` too many). Those are precisely
the two rows I named in the CR227 round-1 verdict, fixed by their owners rather than swept up by
a passing lane. Correct outcome.

## Verification performed

```
worktree:  .claude/worktrees/slot5r2-u66 @ 7d552cca, git status --short empty
scope:     git show --stat 7d552cca -> 2 files, +29/-2
provenance: buyback_price.py / dividend_growth.py / room_runner.py untouched by this SHA
            -> round-1 verifications on those surfaces carry forward
baseline:  pytest tests/unit/test_cr221_c8_c7_capital_returns.py -q -> 25 passed
mutation:  seam reverted to trust avg_price      -> 1 failed (the new test); reverted, clean
mutation:  quotient made wrong by +10%           -> 2 failed (not tautological); reverted, clean
probe:     desynced object -> $664.64 (was $1.00); shares=0 fallback -> $1.00
source:    MIN_SHARES=1000 at buyback_price.py:125 -> fallback unreachable, confirmed
suite:     full backend/tests/unit/ BARE -> 6696 passed, 9 skipped, EXIT=0
```

Scratch files removed. Worktree `slot5r2-u66` is this instance's and is reaped on verdict.

## Closing note

Round 1 called this lane strong and round 2 does nothing to change that. The MINOR was the
mildest kind — a latent inconsistency between two seams in the same CR, unreachable from any live
path — and the response fixed the seam to match its sibling rather than arguing the point was
moot, which it could fairly have done.

One process note, recorded because it cost eight hours rather than because it reflects on the
work: both CR221 round-2 submissions sat with their `SUBMITTED: round 2` marker written to disk
but uncommitted, so the watcher correctly refused to surface them (`watcher.sh:105` — an
uncommitted submission is never `AWAITING_AUDIT`) and I read the resulting quiet board as "no
work." The architect committed both markers at `33cc659b` / `393623f2`. The fix commits had been
on `main` and auditable the whole time. The marker and the code it points at need to land
together, or the handshake stalls silently on both sides.

VERDICT: COMPLETE (round 2)
