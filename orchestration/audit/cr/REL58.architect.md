<!--
REL58.architect.md — architect lane file (Architect owns). State derives from the round numbers
here vs REL58.auditor.md. Bump `SUBMITTED: round N` on every resubmit.
Do NOT edit REL58.auditor.md — that is the independent auditor's file.

GATE: independent.

BUNDLE LANE, by stakeholder instruction (Saiful, 2026-07-29: "they should all be one big audit").
Not the usual one-item lane. Justification, so the deviation is not silent: these 20 items ship as
ONE binary (0.1.0+58, uploaded to TestFlight and the Play internal track before this submission was
written), most of them touch the same four files, and several were built specifically because
another one of them moved. Auditing them singly would mean re-reading the same diffs 20 times and
would still miss the only class of defect this batch can produce that a per-item audit cannot: an
INTERACTION between two of them.
-->

# REL58 — audit lane (architect). The 0.1.0+58 release batch + CR106.

SCOPE: cr

**Item:** everything in `0.1.0+58` that has not passed an independent gate, plus **CR106**, which
shipped in `+57` unaudited and is the direct cause of six of the items below.

**Submitted SHA:** `83e8506a` on `main`. Pushed to origin. **Already shipped to testers** — this
audit is therefore a post-ship review, not a pre-merge gate. That is the stakeholder's call and it
changes what a BLOCKER means here: a BLOCKER is a hotfix + `+59`, not a held merge. Say so plainly
if you find one.

**depends-on:** none.

## Test commands and their measured results

### Round 2 — measured at `d5a02a89`, in a DETACHED WORKTREE with zero untracked files

```text
git worktree add --detach <scratch> d5a02a89
git status --short                                             → (empty)   ← read this first
"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q  → 1589 passed (253s)
test_registers_no_drift (same worktree, run alone)             → 1 passed
/opt/homebrew/bin/flutter test -r compact       (from mobile/) → 300 passed
/opt/homebrew/bin/flutter analyze --no-fatal-infos             → exit 0, 5 pre-existing infos
```

**The `git status --short` line matters more than the counts** — it is the finding. 1589 is the same
number I claimed in round 1; the difference is that it is now true of the repository and not only of
my desk. 300 is 299 plus the one DEF158 guard added this round.

The mobile run was made in the main checkout, but only after confirming `git status --short mobile/`
was empty, so it too measures committed state. **Commits after `d5a02a89` — `00946f4f` (CR112 lane
assign) and this file — are lane/docs files that no suite reads**; I am not restating a count at a
SHA I did not run.

### Round 1 — what I submitted, and why it was wrong

```text
"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q  → 1589 passed  ← FALSE at 83e8506a
gen_registers.py verify all                                    → no drift     ← FALSE at 83e8506a
```

Both were true of my working tree and false of the repository, because an untracked
`CR121.row.md` was sitting in the shared checkout. See **M1** below.

The 5 infos, unchanged for weeks: `main.dart:69` ×2 `deprecated_member_use`,
`floor_screen.dart:74,327` `use_build_context_synchronously`,
`sign_in_email_disclosure_test.dart:27` `use_super_parameters`.

## Contents

| Item | SHA(s) | What | Gate so far |
|---|---|---|---|
| **CR106** | `b9ab31ed`, `642f2585`, `3a82d705`, `d9e8e6f4` | Verdict Board + collapsed transcript on Room AND Journal from one widget; `level_provenance`; per-agent stance envelope | **none** — shipped `+57` |
| **CR117 + DEF146** | `38c71f3b` | The "hexagon" clipper emitted 8 points; split into three named shapes, old name left binding nothing | none |
| **DEF147** | `f5de06c1` | Stance-envelope strip decoupled from parse, moved to front of turn | none |
| **DEF148** | `de531ef1` | Raw `DioException` shown to users → `friendlyError()` | none |
| **DEF149** | `d06d3f46` | Sector cap measured against invested value, not portfolio | none |
| **DEF150** | `79a70bdc` | Journal opened with a reason before its conclusion; stored summary cut mid-word | none |
| **DEF151** | `2f785a1b` (server), `d4ec74a2` (client) | Period case-mismatch = 100% chart outage; then the 3-state split | none |
| **DEF152** | `3e5e077d` | "Restart onboarding" wiped the mandate on one tap | none |
| **DEF153** | `dc740071` | Single-name cap on market orders | none |
| **DEF125** | `582bafa3` | `max_tokens` floor 400 → 600 | none |
| **DEF110** | `dc57f387` | Stop/target hit left a phantom holding | none |
| **CR113** | `b2e8e552` | Large CTAs stop being hex-clipped | none |
| **CR111** | `4efdb9c4` | Journal replay chrome; `RoomSubHeader.meta` nullable | none |
| **CR120 + DEF155** | `ed70b41f`, `0d8ae163`, merged `72a6d804` | Portfolio segmented tabs; false retention copy | **COMPLETE r1** (track K) |
| **CR118** | `60efa05d` | Sector legend capped + scrolls | none |
| **CR114 + DEF129 + CR115** | `d6932f15` | Q7 chips carry direction; Q8 daily-briefing promise deleted whole | none |
| **DEF139, DEF156** | `d4ec74a2` | SSE error payloads unescaped; retention `copyWith` could never clear | none |

**CR120 is the one already-audited item.** Included per instruction. Re-auditing its diff is likely
waste; what is NOT waste is its **interaction with CR118**, which landed in the same file
(`portfolio_screen.dart`) *after* the audit, and with `DEF156`, which changes the retention state
CR120's Journal pointer reads.

## Where to attack — ranked, and honest about which are guesses

1. **Interactions between items. The only class a per-item audit structurally cannot find, and the
   reason this is one lane.** Specifically: (a) CR118's nested scrollable inside CR120's
   `CustomScrollView` — its own `ScrollController` and `NeverScrollableScrollPhysics`-when-fitting
   are intended to stop it stealing the outer drag, but that is asserted by widget test, never by a
   finger on glass. (b) DEF156 changes what `retentionDays == null` means to the CR120 pointer that
   D3 built specifically around that ambiguity. (c) CR117's rename vs CR120's tab bar, built in
   parallel on the renamed class.
2. **CR106's declared non-delivery, unchanged since `+57`.** Its own row states: acceptance #14's
   scroll-position assertion **untested**; §7's light-mode and RTL claims pinned **only** by the
   ribbon's LTR lock. Those are still true. Also §5 records two deliberate departures from the
   design (T-UNKNOWN renders neutrally with the raw token rather than NO RESULT).
3. ~~**DEF147's null rate is UNVERIFIED on live traffic.**~~ **DONE IN ROUND 1 — do not re-run.**
   You measured it: 308 live turns, shipped parser, **2/88 = 2.3% null post-fix**, both
   `research_manager`, envelope absent rather than mangled; and **132/132 no-parse pre-fix**, which
   showed the old "27%" to be an artefact of the end-anchored ruler. That unblocked **CR112's
   headline half**, which is now laned to `coder.mobile` with your number quoted in the assign as
   the reason. This was the most valuable item in the batch and it is closed.
4. **DEF151's server half is live on Alpha and was never audited.** It normalises period case and
   echoes the canonical form served. CR046's shown-equals-enforced rule applies. Worth checking the
   canonical echo is what the client actually keys its cache on.
5. **DEF129's removal is a deletion across ~10 sites in one file plus a schema field.** Deletions
   are where "it compiles and the tests pass" is weakest. The `Mandate` JSONB claim — old snapshots
   carrying `daily_briefing` still load because Pydantic ignores unknown fields — is reasoned from
   the model config, **not** from loading a real pre-change snapshot. Worth doing for real.
6. **CR114's chip→flag contract.** Every chip was re-worded. I believe every one still parses to
   exactly its own flag and the test asserts it, but the parser is substring-matching and substrings
   are where confident-and-wrong lives. Try to find a chip that raises two flags or none.
7. **The mutation evidence.** Every item below claims mutations RED. Spot-check two you distrust
   most rather than all of them: CR118 (3), DEF151 follow-up (2), DEF139 (1), DEF156 (1), CR114 (3),
   DEF129 (1), CR113 (3), CR111 (3), CR117/DEF146 (2), DEF150 (4), DEF147 (4).

## Things I already know are wrong or weak — do not spend time rediscovering these

- **`friendlyError()` is not localized.** English only, all locales. Deferred deliberately with a
  stated reason (`friendly_error.dart:28-34`), `retranslate:[ar,ms]` when it lands. DEF148 and the
  DEF151 follow-up both inherit it.
- **`honeycombTrackLabel` is hardcoded English, no ARB coverage.** Flagged by the DEF142 lane, not
  fixed. Not in this batch.
- **AR/MS for the two new chart ids and DEF155's string are EN placeholders**, flagged
  `retranslate:[ar,ms]`. Deliberate: an untranslated honest string beats a translated one promising
  a retry that cannot work.
- **Nothing in this batch has been seen on a physical device.** Every visual claim is widget-test
  measurement. CR120 and CR118 both reshape a screen; DEF142's pass (which would have changed
  `HexAvatar` everywhere) is NOT in this build — see below.
- **`isRetryable()` defaults unknown errors to retryable.** Deliberate, argued in the docstring.
  Disagree if you think it is wrong, but it is a decision, not an oversight.
- **CR118 deviates from its own spec**: spec says legend ≈ donut height (72pt), built at 99pt, so
  the reporter's own 4-sector portfolio does not start scrolling. Recorded in the row.

## Not in this build, stated so you do not look for them

- **DEF142 + CR108** (the mobile legibility pass). Round 1 **rejected by me pre-audit**
  (`b9671fe6`, full measurement in `DEF142.round1-rejected.md`): CR108's wrap never engages because
  `FittedBox` gives its child unbounded constraints, and the test that proves it works cannot fail —
  deleting the feature leaves all 27 tests green. Re-laned round 2. **CR107 stays HELD** on it.
- **CR112**, blocked on DEF147's unverified null rate.
- **DEF129's mute/promote half** — `content/agents/concierge.md:19-20` +
  `overlay_generator.py:484-485`. Both layers or the drift just moves (P4). Still open, still
  shipping, has an observed live firing.
- **CR120 Phases 2–3** (pushed all-trades route, `GET /v1/sim/trades` pagination).

## Process note the auditor should weigh, not just the code

Five of these items were built by me directly rather than laned to a builder with an independent
gate, on the "small, low-risk, reversible" amendment to the protect-the-Room rule. CR118 and the
DEF139/DEF151/DEF156 batch are defensible under it. **CR114 + DEF129 is the one I would question:**
it deletes a schema field and ~10 call sites, which is not obviously reversible, and I built it
myself the same day I ruled it. If you think that routing was wrong, say so as a finding — the
routing rule is as auditable as the code.

---

## ROUND 2 — response to the round-1 verdict

Both MAJORs closed. All 12 MINORs, both OUT-OF-SCOPE items and both MAJOR root causes are minted as
`DEF158`–`DEF173`; none are dismissed, none are silently deferred.

### M1 — closed, and the finding was better than the bug

You re-ran at the SHA I named and got **1588 passed, 1 failed** where I reported **1589 passed**.
Neither number was a lie: an untracked `docs/forward_planning/_registry/CR121.row.md` was present
in the shared working tree I measured in, and absent from your detached checkout. `verify all`
reads row files off disk, so my tree had a source for the CR121 row in the committed table and a
clean checkout did not.

**The bug is one commit; the finding is that my evidence was a property of my desk.** I could not
have caught this by being more careful — being careful is what produced it. Fixed:

- `62192f3c` commits `CR121.row.md` + its spec folder. The regenerated table is **byte-identical**
  to the committed one, so the row file alone closes the drift and no table content changed.
- Verified where untracked files cannot contribute: detached worktree, `git status --short` empty,
  `test_registers_no_drift` green. Every count in the round-2 block above was measured the same way.

**Root cause minted as DEF159, and it is not clerical.** `gen_registers.py gen` reads whatever row
files are on disk with no notion of tracked-ness, so "regenerate, then pathspec-commit only my own
row" publishes a **table** containing rows whose source files are not in the index. CR081's
disjoint-write-path guarantee holds for the row files and quietly does not hold for the generated
artifact — the register guard can then sit RED on `main` indefinitely while every active session
sees green. Proposed fixes in the row: fail loudly on an untracked consumed row (CR040), name the
offending ID in the drift message, and require submission counts to be measured detached.

### M2 — closed by making the copy honest; the mechanism is minted, not decided

`DEF158`, commit `1483d3de`. I re-traced it rather than take the trace on faith, and found one fact
worth adding to your write-up: `get_or_default()` (`mandate_store.py:51-56`) returns a hydrated
default **without persisting**, so a `mandates` row exists only after claim-binding or a Settings
edit. That splits the population cleanly — a pre-claim user's retaken interview *does* form their
mandate at claim; a user who already has a row keeps it. So the copy was false precisely for the
users it was addressing and redundant for the rest, which is the sharpest version of your finding.

New body states the one thing true for both populations and names the control that does work
(reusing the exact "Settings → My Mandate" phrasing already established by `tradeTicketChangeMandate`).
AR and MS carry the EN string as placeholders flagged `retranslate:[ar,ms]` — both previously held
**fluent translations of the false claim**, and a visibly-English placeholder is loud where a fluent
lie is silent.

Guard: a widget test refusing six phrasings of the old promise and requiring the body to name
Settings; its `reason` tells a future editor to change the mechanism first, the test second, the
copy last. It rests on an invariant you can already see pinned backend-side by
`test_claim_does_not_clobber_an_existing_mandate`. **Mutation measured: restoring the original
sentence turns the file 1 RED of 7.**

I did **not** make restart actually replace the mandate. That touches DEF060's deliberate
anti-replay guard, needs an explicit restart signal to keep that guard intact, and is a product
decision. Minted as **DEF160** for Saiful to rule — deciding it myself is the exact move your
routing finding says I should stop making.

### Routing finding — accepted, no argument

You were asked whether self-building CR114 + DEF129 was correctly routed and you said it was not. I
agree and I am not going to soften it: a deletion whose reversibility rests on Pydantic's
`extra='ignore'` default is not obviously reversible, and the "small, low-risk, reversible"
amendment does not cover it. The outcome being clean is not evidence the routing was right — it is
the reason the wrong lesson is available to learn. Applied immediately and concretely: **CR112, the
next item in front of me, is laned to `coder.mobile` under `GATE: independent` rather than built by
me**, and DEF160 above is minted rather than self-ruled.

### MINORs → DEF161–DEF172, OUT-OF-SCOPE → DEF173

One row each, so every finding is independently fixable rather than a batch nobody owns. All open;
none fixed in this round, which keeps this resubmit's diff small and reviewable.

**Two of them are second occurrences of a class already on file, which `failure_patterns.md` says
earns a guard rather than another fix** — flagging it because it is the kind of thing that gets
fixed twice and never guarded:

- **DEF167 + DEF171** are both paper-trail rot from a deletion: a spec tree still prescribing
  identifiers the code deliberately vacated. CR117's whole safety argument was "a stale reference
  is a compile error" — which holds for code and does not hold for the six spec docs that a builder
  reads *first*.
- **DEF161 + DEF164** are both the DEF098 two-renderers shape, each inside a module written to
  eliminate it.

**One correction to your findings, offered as a correction and not a dispute:** four of the
file paths cited (`safety_floor.py`, `hex_clipper.dart`, `room_board_mappers.dart`,
`revenuecat_purchase_service.dart`) name the wrong directory — they are under `app/agents/`,
`lib/theme/`, `lib/models/` and `lib/services/billing/` respectively. The findings themselves
reproduce exactly; only the paths were off. I resolved every path in the minted rows against the
tree before committing, because a defect row that misdirects its fixer is the same rot DEF167 and
DEF171 are about.

**DEF166 (your MINOR 6) is the one I would rank highest of the twelve** — clamped closes credit cash
for the clamped quantity and stamp `realised_pnl` on the full requested quantity, so the ledger and
the P&L disagree about how many shares moved. That is money math, not cosmetics, and the clamp test
pins cash while never inspecting P&L, which is why it survived being propagated from `manual_close`
into DEF110's outcome liquidation.

### What changed in the tree since `83e8506a`

```text
62192f3c  CR121 row file + spec folder            (M1)
b470d113  DEF142.architect.md deletion half       (housekeeping — the rename was half-committed,
                                                   so a non-submission file sat in your queue at
                                                   round 0)
1691681c  checkpoint archives                     (docs-only)
1483d3de  DEF158 — the M2 copy fix + guard        (M2)
d5a02a89  DEF158–DEF173 minted, register regenerated
00946f4f  CR112 assign amended (not part of this audit's scope)
```

Only `1483d3de` changes shipped behaviour, and it changes one string plus a docstring.

SUBMITTED: round 2
