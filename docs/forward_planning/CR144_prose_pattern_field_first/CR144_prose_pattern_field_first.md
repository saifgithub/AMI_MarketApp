# CR144 — Before a pattern reads agent prose, name the field it could have read instead

**Status:** done · **Filed:** 2026-08-08 (AT:R66) · **Owner:** architect (track R)

---

## Why

DEF231 took **six audit rounds and one live defect** to close a check that
compares two numbers. Its own row had specified the correct design in the
sentence that justified filing it:

> the referenced level is already a structured number the verdict carries
> (`entry`/`stop`/`target`/the profile's support/breakout), so a comparison is
> available without parsing free text — which removes the objection that killed
> the general version.

What was built instead compared the price against **any `$` figure a directional
verb governed**. Every single defect that followed came from that gap between
the specified design and the built one:

| finding | captured figure | a structured level of that run? |
|---|---|---|
| r1 MAJOR | `we'd pay $52.30` | no |
| r2 MAJOR | a second sentence's level | yes — but not the verb's |
| **DEF234 — reached live Alpha** | `$1.00`, truncated out of `$1,073.46` | no |
| r4 MINOR | `break above near the recent low of $X` | no |

Three of the four are unreachable once the figure has to match a level the run
actually holds. The fourth is the one that genuinely needs grammar — which is
the real lesson: **the structured answer and the prose answer are usually both
needed, and the prose half should only ever cover what the structured half
cannot.** Building the prose half first means it covers everything, and its
false-positive surface is proportional to how much wider than the structured
answer it is.

This is not a one-off. **DEF235**, filed by another track the same week, is the
identical shape one function over: `_LEVEL_PATTERNS["size"]` matched `\bsize\b`
followed by a number, so *"a MEDIUM size entry at $188.62"* yielded a position
size of 188.62 and AMI published a drawdown contribution **63× too large**,
under the words "These are the figures of record." **CR106 B1** is the same
lesson learned once already and not generalised: level provenance used to be
disclosed by appending a sentence to `reason`, and the fix was to move it into a
typed field. Every prose checker is a missing field until proven otherwise.

There was no rule requiring anyone to ask the question. This CR adds one.

## What

### 1. A convention rule (`docs/initial_specs/08_tech/coding_conventions.md`)

A new **"Reading a claim out of agent prose"** section under *Python backend*.
Its operative requirement is one line of evidence at the pattern's definition
site:

> Any regex or parser that reads a value or a claim out of LLM-authored text
> must carry a comment naming **the structured field that was considered
> instead, and why it lost**. If no such field exists, say that — and say
> whether making one is cheaper than the parser.

Deliberately a **comment**, not a lint rule. The failure mode is not that people
write patterns; it is that nobody asks the question. A comment forces the
question at the only moment the answer is cheap, and it is reviewable — an
auditor can ask "is that really why it lost?" and the answer is in front of both
of them. A lint rule would be satisfied by boilerplate.

### 2. Two amendments to failure pattern P16

- **The generality law**, with DEF231's four-row table as evidence: a prose
  pattern's false-positive surface is proportional to how much wider than the
  structured answer it is, so the structured half is built first and the prose
  half covers only the residual.
- **Do not select the guard's corpus with the thing it guards.** The P16 fixture
  originally selected rows carrying a `$` *and a directional verb stem*, which
  made the guard's own population a function of the pattern under test. A
  broadening moved the count for two reasons at once; far worse, a **narrowing**
  would have shrunk the population in lockstep and hidden its own coverage loss
  — the exact failure the fixture exists to prevent. Selection must depend only
  on the raw property that makes a row *capable* of exercising the pattern.

Also recorded: two more measurement-harness bugs from this session's coverage
work (`auto_adjust=False` against an app using yfinance's default, and omitting
the 52-week range entirely, which understated retention by 26 points). Both were
caught by the *shape* of the unmatched list, not by any number looking wrong.

## Scope

Documentation and conventions only. No code, no schema, no behaviour change.
The code this CR generalises from already shipped under DEF231.

## Acceptance

1. `coding_conventions.md` carries the rule, with DEF231/DEF235/CR106 B1 named
   as the instances that motivated it. ✅
2. P16 carries both amendments. ✅
3. The two live prose patterns are brought into compliance — `_DIRECTIONAL_CLAIMS`
   (DEF231) and `_LEVEL_PATTERNS` (DEF235's site) each carry the required
   comment. `_DIRECTIONAL_CLAIMS` already does in substance; `_LEVEL_PATTERNS`
   gets the comment **as a question, not an answer** — DEF235 is open and owned
   elsewhere, so this CR records what must be asked and does not pre-empt the
   fix. ✅

## What this CR deliberately does NOT do

**It does not fix DEF235.** That defect is open, filed by the CR143 track, and
its fix direction (require the `size` label to be followed by a percentage;
exclude a match whose number is also captured by `entry`/`stop`/`target`) is
already written into its row. Adding the compliance comment at its definition
site is not a fix and is not claimed as one.

**It does not add a lint rule or a CI check.** See above — the check that would
be mechanical is the one that would be satisfied mechanically.
