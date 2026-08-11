<!--
R68-BATCH8.auditor.md — audit lane. State derives from round numbers here vs
R68-BATCH8.architect.md.
-->

# R68-BATCH8 — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

2 MAJOR, 0 BLOCKER, 4 MINOR.

Audited `e7efd472` extracted with `git archive` into a scratch tree (DEF159) —
never the shared checkout. Run report:
[`../runs/2026-08-11_run-02/run_report.md`](../runs/2026-08-11_run-02/run_report.md).

**The headline question the lane was framed on — does DEF255's note cross into
investment advice — is answered NO.** It recommends nothing, sanctions nothing,
and states no rule about how long anyone should hold; it critiques the internal
coherence of the simulator's own output against evidence AMI itself supplied.
Zero hits against the banned lists the codebase already uses for this class
(`test_def240_loud_concentration.py:57-64`). Not a BLOCKER. What it does do is
assert a categorical classification and a predicted outcome that are *independent
of the stop distance they name* — MAJOR 1.

**`SCOPE: chunk`** — no Definition-of-Done table owed (PROTOCOL step 4; gap-fill 7
waives enforcement regardless). Recorded, not scored.

**`depends-on: R68-BATCH4`** — that lane's own round-1 verdict landed on origin
while this audit was running (`cee6c124`) and reads `AWAITING_FIXES`, so the
dependency is not COMPLETE. Under guardrail 3 even a clean pass here could only
have been PROVISIONAL. Moot at 2 MAJOR; recorded.

---

## MAJOR 1 — DEF255: the stop clause classifies and predicts independent of the number it names

`backend/app/services/room_runner.py:1156-1162`. The guard is
`if entry and stop and entry > 0 and stop > 0 and stop < entry:` — **no bound on
`stop_pct`.** So the identical sentence is emitted for a 1.9% stop and a 90% stop:

```
$ python -c "from app.services.room_runner import _horizon_coherence_note as n; \
             print(n(400, 100.0, 99.9)); print(n(400, 100.0, 55.0))"
… the 0.1%-below-entry stop is a weeks-to-months instrument — over that horizon
  ordinary volatility would take the position out long before the thesis could be judged.)
… the 45.0%-below-entry stop is a weeks-to-months instrument — over that horizon
  ordinary volatility would take the position out long before the thesis could be judged.)
```

This is not adversarial-only. Reproduced on the **real live rows** from melehost
`room_runs` (2026-08-09 → 2026-08-11, `verdict->>'action' = 'APPROVE'`,
`time_horizon_days > 365`):

```
GIS    h= 900  entry 46.13  stop 45.26   1.9%  -> "the 1.9%-below-entry stop is a weeks-to-months instrument"
MCHP   h=1095  entry 62.66  stop 61.00   2.6%  -> "the 2.6%-below-entry stop is a weeks-to-months instrument"
XPEV   h=1095  entry 23.73  stop 22.31   6.0%
STZ    h=1095  entry 170.44 stop 160.21  6.0%
NVDA   h=2520  entry 223.96 stop 200.00 10.7%
CRM    h=1095  entry 265.18 stop 227.35 14.3%
M      h= 730  entry 12.06  stop 10.16  15.8%
```

A 1.9%-below-entry stop is not a weeks-to-months instrument. Nor is a 2.6% one.
The clause states it anyway, in `verdict.reason` — the field CR106 renders on the
Verdict Board as the decision's justification.

**Blast radius, measured:** 7 of 25 APPROVE verdicts in that window carry
`time_horizon_days > 365` — **28% of approvals**. This is not an edge path.

**The standard is already set in this codebase, in the sibling function's own
docstring.** `room_runner.py:736-754` (`_concentration_note`) records the DEF240
round-1 audit MAJOR: the note first shipped as *"…so the safety floor permits
it"*, and the ruling was that a disclosure must **state what happened**, never an
evaluative outcome — *"Both are true; only one is a disclosure."* Here the
evaluative clause is not even true. `_horizon_coherence_note` also has no
equivalent of `test_def240_loud_concentration.py:44
test_the_note_is_factual_not_advisory`.

**Nothing in the suite constrains that clause — proven by mutation.** MUT-5:
hardcoded `stop_pct = 6.0` at `room_runner.py:1157`, so the note prints
"6.0%-below-entry" for a stop that is 45% below entry.

```
$ pytest tests/unit/test_cr156_def239_def255_pm_verdict.py \
         tests/unit/test_def240_loud_concentration.py \
         tests/unit/test_def231_pm_direction_coherence.py -q -p no:randomly
142 passed in 115.59s
```

**The mutation SURVIVED.** The note's stop figure is tied to nothing — not to the
verdict's own stop, not to any range. The only assertion touching it
(`test_a_horizon_beyond_every_input_is_flagged:114`) pins the literal string
`"6.0%-below-entry stop"` produced by a 100/94 fixture, which the mutation
satisfies by construction.

**The first half of the note is sound and should survive** — the horizon claim,
the `_MAX_EVIDENCED_HORIZON_DAYS = 365` derivation, and the flag-not-veto
behaviour are all confirmed below, each proven load-bearing by its own mutation.
It is the adjectival second half that asserts past its own input. Stating the two
numbers and stopping — the sibling disclosures' shape — would carry the same
warning with none of the overclaim.

**Owed with the fix:** a pin under `backend/tests/unit/` per BINDINGS/DEF141
(auditor pins must live on the collection path), registered in
`test_def141_audit_pins_are_collected.py`'s `MIGRATED_PINS` in the same commit.
I did not write it: the note text changes under the fix, so a pin authored now
would pin the broken string, and source paths are outside auditor path discipline.

## MAJOR 2 — CR156 D: the retracted ordering claim survives verbatim in the code, pointing at the doc that now contradicts it

`backend/app/services/agent_prompts.py:77-78`, the docstring of
`build_agent_prompt` — the function that appends the floor:

```
    The safety floor is appended LAST so it always dominates instruction
    ordering for the PM (see docs/initial_specs/02_agents/safety_floor.md).
```

That is the sentence CR156 D exists to retract, still asserted, still citing the
document that now says the opposite. And it is asserted in the file whose return
value `room_prompts.py:577` takes and `room_prompts.py:739` appends 4,647 chars
after — measured:

```
floor starts at char 4979 / 11023 (45% through the assembled Room PM prompt)
chars rendered AFTER the floor block                : 4647
text after the floor contains _PM_VERDICT_FORMAT    : True
text after the floor contains the CONVENE block     : True
```

Reproduction:

```
$ grep -n "appended LAST so it always dominates" backend/app/services/agent_prompts.py
77:    The safety floor is appended LAST so it always dominates instruction
```

The lane states: *"`enforce_safety_floor()` is the enforcement point and both the
doc and the code now say so."* Half true — `room_prompts.py:728-737` says so;
`agent_prompts.py:77` says the opposite. The pin
`test_the_docs_no_longer_claim_the_floor_is_last_in_the_room` reads
`safety_floor.md` only, so nothing catches this.

Graded MAJOR rather than MINOR because it is a **false claim in the submission
about a file the item covers**, and because a docstring in the prompt-composition
module is read by more people, more often, than the spec doc — it is the exact
propagation path CR156 D was filed to close. The fix is one sentence plus a
widened assertion.

---

## MINOR 1 — DEF255: "every input" / "Nothing on the fact sheet" enumerate three of the inputs

`room_runner.py:1150-1155` asserts the horizon *"reaches beyond **every** input
this decision had — 3 months of price history, TTM fundamentals and a 52-week
range. **Nothing** on the fact sheet supports a thesis that long."*

The Room fact sheet also carries forward-looking fields the enumeration omits:
forward P/E (`room_prompts.py:1018-1023`), analyst consensus rating + target price
(`room_prompts.py:1230-1244`, `_analyst_line`), and the next-earnings date with a
consensus EPS estimate (`room_prompts.py:1111-1131`). The substantive conclusion
survives — a ~12-month Street target does not support 1,095 days — which is why
this is MINOR and not MAJOR. But the sentence claims to enumerate the input set
and does not.

## MINOR 2 — DEF255: on the no-stop path the note criticises a stop AMI itself minted

`room_runner.py:1240-1245` sets `stop = round(entry * 0.94, 2)` when the PM stated
none; `room_runner.py:1250` then hands that AMI-minted value to
`_horizon_coherence_note`. Reproduced:

```
in : {"action":"APPROVE","size_pct":2.0,"entry":100.0,"horizon_days":1095,"narration":"Multi-year compounding thesis."}
out: … (stop/target not stated by the PM — defaulted to a ~6%/13%-from-entry protective level,
       not a PM-chosen price.) (AMI: … and the 6.0%-below-entry stop is a weeks-to-months
       instrument — over that horizon ordinary volatility would take the position out …)
     level_provenance = {'entry': 'pm', 'stop': 'ami_default', 'target': 'ami_default'}
```

This commit's own message names this class as the reason DEF241 stays open:
*"any figure would be minted from an invented stop and read as a measurement — the
DEF235 class."* Same standard, applied here.

Held at MINOR, not MAJOR, on evidence: **live incidence is zero** — all 25 APPROVE
verdicts 2026-08-09 → 2026-08-11 have `level_provenance->>'stop' = 'pm'`, none
`ami_default` — and the defaulting is disclosed in the immediately preceding
clause. Likely resolves for free with MAJOR 1's fix if the clause is keyed on
`stop_raw` rather than `stop`.

## MINOR 3 — CR156 B: the vocabulary sweep is not exhaustive

`backend/app/agents/safety_floor.py:129` still opens the violation clause with
`YOU MUST REJECT any trade that:`, and it renders into the assembled Room PM
prompt (verified at L123 of 11,023 chars). The widened REPLACES sentence names
only *"your profile and mandate overlay"* — the floor is neither, and it asserts
primacy over prior instructions in its own header.

MINOR, not MAJOR, for two reasons: the floor's own output contract three lines
later already specifies `{"action": "PASS", "narration": "<state the specific
mandate rule violated…>"}`, so the action-value contradiction CR156 B is about
does not exist there; and editing the uncoachable block's bytes deserves its own
governed item, not a fold-in — declining to touch it was the right call. Recorded
as remaining CR156 scope (the CR correctly stays `in_progress`).

Related: `test_no_layer_tells_the_pm_to_issue_a_reject` (new test file, line 170)
is a negative assertion over four exact literals — it cannot catch a REJECT
instruction phrased any other way, including the floor's. Its docstring says
*"Three layers carried REJECT"*; the lane says two.

## MINOR 4 — the 1-on-1 PM still offers REJECT with no reconciling sentence

Verified: `build_agent_prompt(PORTFOLIO_MANAGER, …)` contains
`APPROVE | REJECT | MODIFY-AND-APPROVE` and does **not** contain
`_PM_VERDICT_FORMAT`. Correctly outside CR156 B's scope — the 1-on-1 surface is
not parsed into a `Verdict`, so there is no PASS-coloured card for the prose to
contradict. Recorded because it is *why* the `## Output format` block had to be
kept, and it means the REJECT vocabulary is reconciled on the Room surface only.

---

## CONFIRMED — independently verified, not taken on the architect's word

1. **DEF239 is an allowlist, not a scrape, and holds both directions.** Nine
   scrape-bait payloads (`{"ticker":"AAPL"}`, `{"sector":…,"exchange":…}`,
   off-allowlist prose keys `note`/`summary`, empty/whitespace/null/int/list/dict
   narration) all fall through to `_PM_NO_RATIONALE`. All six allowlisted keys
   surface prose. Precedence: `{"reason":"B","narration":"A"}` → `"A"`. Keys are
   case-sensitive, which is correct. DEF232's disclosure survives intact.
2. **`_normalize_pm_action("REJECT") == "PASS"`** still holds defensively.
3. **The MODIFY canary is genuinely UNEDITED.**
   `git show --stat --format="" e7efd472 | grep -i parity` → no output;
   `git diff e7efd472^ e7efd472 -- backend/tests/unit/test_room_prompt_parity.py`
   → empty. The canary at `:68` is untouched and green. CR105 Amendment-1 trap
   avoided, not paid.
4. **The `## Output format` block is kept and pinned**, and it really is the
   1-on-1 PM's only format instruction (`_PM_VERDICT_FORMAT` absent from that
   prompt — checked, not assumed).
5. **DEF255 flags and never vetoes.** A 1,095-day APPROVE returns
   `VerdictAction.APPROVE` with `time_horizon_days=1095` preserved; the note lands
   on `verdict.reason` only, not on the transcript display. DEF059's sole-vetoer
   property intact.
6. **`_MAX_EVIDENCED_HORIZON_DAYS = 365` is derived, not chosen**
   (`technicals.py:42 _HISTORY_PERIOD = "3m"`, TTM fundamentals, the 52-week range
   as the widest window) and is never rendered as a holding rule. Boundary is
   inclusive at 365; `None`/`0`/negative/1e9/string/float horizons all handled
   without crash.
7. **CR156 D's composition claim is TRUE and documented-not-reordered is right.**
   Reordering would put the JSON output contract ahead of the transcript it must
   summarise, and ordering was never the control — CR038 measured prompt-level
   instructions at ~30%. See MAJOR 2 for the one place the correction did not land.
8. **The advice question — NOT a BLOCKER.** Reasoning at the top of this file.

## Mutation proof — mine, on a second `git archive` copy of `e7efd472`

The submission carries no mutation section. Ran four against the file the items
changed, plus MUT-5 under MAJOR 1. Baseline on that copy: `20 passed in 31.65s`.

| # | Mutation | Result |
|---|---|---|
| MUT-1 | `_PM_NARRATION_KEYS` shrunk back to `("narration",)` — the DEF239 regression | **6 failed, 14 passed** |
| MUT-2 | added a free-text-scrape fallback to `_pm_narration` — *the wrong fix* | **1 failed, 19 passed** — caught by `test_the_no_rationale_disclosure_still_fires_when_nothing_carries_prose` |
| MUT-3 | `_horizon_coherence_note` turned into a veto (`return PASS` when it fires) | **caught** by `test_an_incoherent_horizon_flags_but_never_vetoes` |
| MUT-4 | `_MAX_EVIDENCED_HORIZON_DAYS` drifted 365 → 1000 | **caught** by `test_the_boundary_is_derived_from_the_widest_window_on_the_sheet` |
| MUT-5 | printed stop distance hardcoded to `6.0` regardless of the real stop | **SURVIVED — 142 passed** (see MAJOR 1) |

MUT-2 is the one that matters most and it lands: the "allowlist, not scrape"
property is genuinely guarded, not merely asserted in a comment. MUT-5 is the
gap.

## Live measurement — reproduced on melehost, not read off the submission

The audited code IS deployed (`ami_api_alpha` restarted `2026-08-11T15:35:16Z`;
`_MAX_EVIDENCED_HORIZON_DAYS` and `_PM_NARRATION_KEYS` both present in the
container). Queried `room_runs` read-only.

- **CR156 B's "4 of 14 (28.6%)" — REPRODUCED, with a correction worth recording.**
  The 10:46–11:49 batch is exactly 14 verdicts. `reason LIKE '%REJECT%'`
  (case-sensitive) hits 3: 11:02 NVDA, 11:10 AMZN, 11:23 WMT. The 4th is
  **11:27 SLB** — the DEF239 verdict itself, whose "REJECT:" prose was suppressed
  into `_PM_NO_RATIONALE` and therefore cannot appear in the stored column. The
  cited timestamp (`2026-08-11 11:27:36Z`, SLB) matches a real row exactly. The
  figure stands; that the column can only show 3 of the 4 *is* DEF239.
- **DEF255's "4 of 13 approvals" at 1095 — PARTIALLY reproduced.** Four `1095`
  rows exist across 08-09 → 08-11 approvals (1 on 08-10, 3 on 08-11). I could not
  reconstruct the exact 13-approval denominator. Recorded, not scored.
- **DEF255's control has had ZERO live firings.** Seven runs since the restart;
  the one APPROVE among them carries `horizon_days=180`. `0 of 149` 2026-08-11
  verdicts contain "reaches beyond every input". Deployed, unexercised — which is
  precisely why MAJOR 1 matters now rather than after it has shipped 28% of
  approvals.

## The omissions the lane declares — checked, and they are honest

- **`pm_verdict_corpus.txt` (811 rows).** The fixture is FROZEN
  (`test_p16_prose_pattern_corpus_parity.py:27-31` — Alpha `reason` strings from
  2026-08-08 carrying a `$`). Neither it nor `_DIRECTIONAL_CLAIM_RES` changed at
  `e7efd472`; `_EXPECTED_EXTRACTIONS = 364` still passes. No re-run is forced.
- **DEF231's live direction-signal rate genuinely does need re-measuring**, and
  the stated reason is correct: verdicts whose prose used to store as
  `_PM_NO_RATIONALE` (no `$`, so excluded by the fixture's own selection
  criterion) will now store real prose carrying `$` levels. That is a real
  enlargement of the input population.
- **The new note cannot contaminate that pipeline** — own check: zero
  `_DIRECTIONAL_CLAIM_RES` matches at horizons 1095/2520/900, and the note carries
  no `$` figure, so it adds neither corpus rows nor extractions.

Honest omissions, not quiet failures.

## The shared commit — justified, and it obscured nothing for Batch 8

`e7efd472` carries Batch 7 as well. Batch 8's four items are cleanly separable by
hunk — `room_runner.py:1104-1173`, `:1200`, `:1247-1250`, `:1280`;
`room_prompts.py:237-272` and `:728-737`; `overlay_generator.py:520-527`;
`content/agents/portfolio_manager.md:27,32`;
`docs/initial_specs/02_agents/safety_floor.md:78-86`. Batch 7's hunks
(`_stop_clause`, `_risk_state_block`, the two `build_room_messages` kwarg
threadings) touch none of them. Stating the sharing rather than minting two SHAs
that would not mean what they appear to was the right call.

One real cost: `3408 passed, 1 skipped` is a **joint** figure, so a Batch-7
regression and a Batch-8 regression are indistinguishable in that one line. I ran
the suite independently and attributed per-file, which closes it for this round.

## Independent suite

```
$ cd <scratch tree>/backend && "/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2 failed, 3405 passed, 2 skipped, 13 warnings in 3379.39s (0:56:19)

FAILED tests/unit/test_def120_blocking_io_fix.py::test_marks_fetch_is_fast_warm_cache
FAILED tests/unit/test_def136_room_convene_does_not_block_loop.py::test_the_loop_never_stalls_while_the_builders_block
```

**Both failures are pre-existing load-induced timing flakes, NOT caused by
`e7efd472` — proven by A/B against the parent, not asserted.** Both are wall-clock
assertions ("is fast", "never stalls"), and the shared Mac was carrying 19–25
concurrent `pytest` processes from sibling audit sessions throughout. Ran both
files 5× at each commit:

```
PARENT 4746e124 : 6 passed / 6 passed / 1 failed,5 passed / 6 passed / 6 passed
AUDITED e7efd472: 6 passed / 6 passed / 6 passed / 6 passed / 1 failed,5 passed
```

Identical 1-in-5 flake rate either side of the commit. Both also pass in isolation
on re-run. Collection total matches the submission exactly: mine 3405+2+2 = 3409,
the submission's 3408+1 = 3409. Recorded under `OUT-OF-SCOPE`.

Earlier partial run at the same SHA (killed by the harness at 88%) carried **zero**
`F`/`E` markers, consistent with load-dependence.

Targeted:

```
$ pytest tests/unit/test_cr156_def239_def255_pm_verdict.py tests/unit/test_room_prompt_parity.py \
         tests/unit/test_p16_prose_pattern_corpus_parity.py tests/unit/test_def141_audit_pins_are_collected.py -q -p no:randomly
30 passed in 29.16s
$ pytest tests/unit/test_cr156_def239_def255_pm_verdict.py --collect-only -q
20 tests collected
```

20 tests — matches the submission.

## Not verified

- **The live `_PM_NO_RATIONALE` at 15:41:16Z (STZ, post-deploy).** The raw LLM
  object is not persisted — only display text — so I could not confirm whether an
  off-allowlist key carried prose in that verdict. If the PM is emitting rationale
  under a seventh key, this corpus cannot show it. `NEEDS-LOGGING` rather than
  `NEEDS-DEVICE-CHECK`: logging the raw parsed key set on a `room_pm_no_rationale`
  warning would make the allowlist's coverage measurable instead of assumed.
- **DEF255's "4 of 13 approvals" denominator** (see above).
- **No device check was owed** — this lane is backend-only, no Dart surface
  changed.

## OUT-OF-SCOPE

Every *finding* above is inside one of the four items. One pre-existing condition
for the architect to decide on (I never mint an ID):

- **Two wall-clock assertions are load-flaky and will fail any suite run made
  while another track is testing on the same Mac.**
  `test_def120_blocking_io_fix.py::test_marks_fetch_is_fast_warm_cache` and
  `test_def136_room_convene_does_not_block_loop.py::test_the_loop_never_stalls_while_the_builders_block`
  each failed once in five runs at BOTH `e7efd472` and its parent `4746e124`.
  This is now a live cost, not a theory: the CR143 batch programme runs several
  audit lanes concurrently on one workstation, and a green suite is the gate every
  one of them reports against. A run that reports `2 failed` for reasons unrelated
  to the change is a gate that trains its readers to ignore it.

---

VERDICT: AWAITING_FIXES (round 1)
ROUND: 1
