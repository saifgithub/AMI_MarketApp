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

## Test commands and their measured results, re-run at `83e8506a`

```
"./backend/.venv/bin/python" -m pytest backend/tests/unit/ -q     → 1589 passed  (256s)
/opt/homebrew/bin/flutter test -r compact          (from mobile/) → 299 passed   (25s)
/opt/homebrew/bin/flutter analyze --no-fatal-infos (from mobile/) → exit 0, 5 pre-existing infos
```

The 5 infos, unchanged for weeks: `main.dart:69` ×2 `deprecated_member_use`,
`floor_screen.dart:74,327` `use_build_context_synchronously`,
`sign_in_email_disclosure_test.dart:27` `use_super_parameters`.

`gen_registers.py verify all` → DEF OK 156 rows, CR OK 117 rows, no drift.

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
3. **DEF147's null rate is UNVERIFIED on live traffic.** Fixed shapes measured 27% → 9% on one run's
   own fixtures. That is a fixture claim, not a production claim, and the row says so. **CR112 is
   blocked on this number.** If you can reach `llm_audit` on Alpha, a real re-measure is the single
   most valuable thing in this batch.
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

SUBMITTED: round 1
