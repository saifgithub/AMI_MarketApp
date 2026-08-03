# Audit run 2026-08-03 run-08 — CR136-M06, round 3

Auditor track U. Answers round 2's `AWAITING_FIXES` (2 MAJOR — run-06). Audited at
**`44c5032a`** in `.claude/worktrees/audit-CR136-m06-r3`, detached and clean at
checkout.

Verdict: **AWAITING_FIXES** — M3 and M4 both closed, 1 BLOCKER + 1 MAJOR.
Findings in `orchestration/audit/cr/CR136-M06.auditor.md`.

## The correction that shapes this round

Round 2 said the re-injection design made mis-attribution *unrepresentable*. That was
my error. Re-injection makes **fabrication** unrepresentable — the model cannot
invent or type a value. Attribution is untouched: the model still writes the sentence
and still picks which slot goes in it. I graded the words-instead-of-digits residual
(M3) and did not probe the larger one sitting a line above it.

## B2 — measured end to end, published

Real `compute_health` payload, fake gateway, real prompt path, real validator, real
register check:

```
TRUE risk share of the top name : 38%      TRUE annualised volatility : 19.0%
TRUE invested weight of it      : 33%      TRUE beta                  : 1.19

realistic swap   PUBLISHED  -> - CCC drives 33% of your risk.
loud swap        PUBLISHED  -> - Your portfolio volatility has been 1.19 a year.
correct          PUBLISHED  -> - CCC drives 38% of your risk.
```

`top_risk_share_pct` and `top_risk_weight_pct` are adjacent in the slot map,
near-identical in name, and each carries a plausible value for the other's sentence.
Nothing in the published line lets a reader detect it. Neither downstream check
helps: `validate_sections` asks only whether a figure is in the payload — both are —
and `register_check` looks at lexicon, headline length and speech act.

BLOCKER on the same test that made B1 one: it defeats the module's sole purpose, the
path is on by default, and the artefact is permanent. It also falsifies
`PORTFOLIO_REVIEW_METHODOLOGY.md` `:42-44`, `:60` and `:437` — the third consecutive
round in which that document's central guarantee is published wider than the code
delivers.

Fix directions proposed, both avoiding the sentence→metric matcher this lane has
twice been told not to build: self-labelling slots (the metric's name and value
become one inseparable token, so misplacement degrades into nonsense rather than into
a false claim), or letting the model select which metrics to headline while the
system phrases §F1.

## M5 — the multiplier family

`\b` cannot see inside a compound. `twofold threefold fourfold fivefold tenfold
hundredfold quintuple sextuple septuple octuple decuple unity score naught umpteen`
all accepted. `twofold` is "roughly double" — the M3 example — in the one form the
M3 fix does not see. Correctly handled in the other direction: `twenty-five`,
`two-thirds`, `one-and-a-half` all reject, and `percentage` stays legal.

## M3 and M4 — closed

All eight round-2 narrations reject as `number_word`; `½` rejects as a numeral. Two
parts better than what I asked for: the Unicode **numeric-value property** rather
than the Nd category (which is the right generalisation of my own round-2
observation, and reaches `½`/`²`/`Ⅻ`), and banning the percent unit words, which
kills `'XX percent'` in the same rule — a case no number-word set would catch.

All four malformed-brace forms and the `{{vol_ann_pct2}}` near-miss reject as
`malformed_slot`. The architect's own second-order find is the better half: with the
checks in their natural order `{{vol-ann-pct}}` rejected as `number_word`, because
hyphens are word boundaries and the screen matched `pct` inside the malformed slot's
name — right outcome, wrong reason code, and reason codes are what promotion
checklist 2.12 reads.

Availability measured rather than assumed — six narrations written the way the prompt
asks all pass. The screens are blunt, not indiscriminate.

## Reproduced

| Check | Submission | Auditor | Result |
|---|---|---|---|
| validator + renderer suites | 72 passed | **72 passed, 3.05 s** | match |
| QA-F number-word screen disabled | 8 failed, 64 passed | **8 failed, 64 passed** | exact |
| QA-G residual-brace check disabled | 5 failed, 67 passed | **5 failed, 67 passed** | exact |
| QA-H numeric property → `\d` | 3 failed, 69 passed | **3 failed, 69 passed** (`½`, `²`, `Ⅻ`) | exact |
| restored | 72 passed | **72 passed**, `git diff --stat` empty | match |
| full `tests/unit/` | 2269 passed, 13 warnings, 325.83s | **2266 passed, 13 warnings, 413.34s** | see below |

The full-suite count is 3 short and the submission's own arithmetic explains it: it
attributes +3 of the +22 to "M09's new parity guard, which lands in this same suite",
and that file arrives in `8179f659` — a **child** of the `44c5032a` this lane is
headed at. 2266 + 3 = 2269. Correct number, measured in a tree one commit ahead of
the header. Zero regressions either way. Third time this session a lane header and
its measurements have named different commits; measuring in a worktree of the header
SHA is DEF159's whole point.

Unclaimed mutations of mine, both killed: brace check moved back after the
number-word screen (5 failed — the ordering is held by tests, not luck), percent unit
words dropped from the set (1 failed).

My first QA-H run reported 9 failures against the claimed 3. That was my shell
escaping producing a pattern that matched nothing — disabling the screen rather than
narrowing it. Re-run correctly, the submission's number is exact.

## Round 4 scope

B2 and M5. Everything else in rounds 1–3 stands as audited.
