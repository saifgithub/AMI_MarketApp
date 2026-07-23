<!--
CR069-MOBILE.auditor.md — auditor lane file (track U owns). State derives from round numbers
here vs CR069-MOBILE.architect.md (see PROTOCOL.md).
-->

# CR069-MOBILE — audit lane (auditor)

**Item:** CR069-MOBILE — Phase 1b UI copy + the four-state Sharia surface. Chunk under the CR069
decomposition (chunk evidence list, not the CR-level DoD).

**Audited SHA:** `f21d7b8`, tip of `lane/CR069-MOBILE.coder.mobile` (not on main). Audited in an
isolated worktree `.claude/worktrees/audit-CR069-MOBILE/`.

## Round 1

### Reproduced independently

| Check | Command | Result |
|---|---|---|
| Untranslated counts | `flutter pub get` (regenerates l10n) | **ar: 113, ms: 114** — matches. |
| Analyze | `flutter analyze lib/` | **4 pre-existing infos**, same set as prior lanes (`main.dart:69` ×2, `floor_screen.dart:73,313`), none in touched files. Matches. |
| Full mobile test suite | `flutter test` | **60 passed, exit 0**. Matches. |
| Generated l10n freshness | `git status --short lib/generated/` after `flutter pub get` | **clean** — the committed generated files are exactly what a regen produces, not hand-edited/stale. |
| Scope | `git diff --stat 6347844..f21d7b8` | 13 files, all under `mobile/lib/**` + `mobile/test/**`. `pubspec.yaml`: zero diff — no version/build bump. |

### The blocker — independently reproduced against the LIVE backend, not the pasted transcript

Went to melehost directly (LAN-direct, `http://192.168.20.59:8000` — not the CF tunnel hostname,
per standing routing guidance), not `api-alpha.agenticmarketintel.ai`. Fresh anonymous session
(`POST /v1/auth/anon`), `PATCH /v1/mandate/{user_id}` with `compliance.halal=true`,
`POST /v1/sim/preview` for AAPL / META / JPM / ASML:

```
AAPL  -> {"accepted": true,  "compliance": {"passed": true,  "violations": [], "blocked_by": null}, ...}
ASML  -> {"accepted": true,  "compliance": {"passed": true,  "violations": [], "blocked_by": null}, ...}
META  -> {"accepted": false, "compliance": {"passed": false, "violations": ["META is in the parent
          index but does not pass the AAOIFI screen (...), so this mandate won't trade it."],
          "blocked_by": "compliance"}, ...}
JPM   -> {"accepted": false, ...same shape as META...}
```

AAPL (compliant/PASS) and ASML (outside the parent index/UNKNOWN) are **byte-identical apart from
price** — confirms the coder's central claim exactly, reproduced myself rather than trusted.

Source-level confirmation, read directly (not from the hand-off's line citations alone):
- `backend/app/schemas/trade.py:91` — `ComplianceResult.sharia_verdict: ShariaVerdict | None` —
  the field genuinely exists and is genuinely populated upstream (verified in the CR069-BE audit).
- `backend/app/api/sim.py:187` (preview) and `:233` (submit's rejected branch) — both hand-build a
  3-key `{"passed", "violations", "blocked_by"}` dict; `sharia_verdict` is not among them. Neither
  handler declares a `response_model`, so there is no type-level contract that would have caught
  the drop — confirmed via the deployed `openapi.json`: `/v1/sim/preview`'s 200 response schema is
  `{"type": "object", "additionalProperties": true}`, not a named schema.
- `openapi.json` (fetched live from melehost): **102 paths total** (matches the hand-off's count),
  `ShariaVerdict`/`sharia_verdict` appear **zero times** anywhere in the document — not in
  `components.schemas`, not in any path.
- **Went one step further than the hand-off**: `submit_trade`'s *accepted* branch (line ~257)
  returns `{"ok": True, "trade": trade.to_json()}` — no `compliance` key **at all**, and
  `Trade.to_json()` carries no Sharia field either. So a live `/v1/sim/submit` success is even
  further from carrying the verdict than `/v1/sim/preview`'s response, which at least has a
  `compliance` object (just missing the one field). Consistent with, and slightly stronger than,
  the hand-off's own claim — not a contradiction.

**This is a real, live, production-facing gap** — Alpha is running `SHARIA_SCREEN_ENABLED=true`
right now (confirmed in the CR069-BE/DIVERGE audits), so any real user with a halal mandate who
trades an unscreened name today receives a permitted trade with **zero disclosure** that the
screen has no ruling on it — the exact G3 requirement this whole CR exists to satisfy is currently
unreachable in production, not because of anything wrong in the mobile app, but because the API
never puts the field on the wire.

### Source re-read — the mobile-side implementation itself

- `models/sharia.dart` — `ShariaStatus._wire` map values (`pass`/`screened_out`/`unknown`/
  `unavailable`) match `backend/app/schemas/sharia.py::ShariaStatus` exactly.
  `ShariaStatus.fromWire`/`ShariaVerdict.fromJson` return `null` on anything unrecognised or
  missing — no `?? default` anywhere in the file. `isBlocking` mirrors `ShariaVerdict.is_blocking`
  exactly (SCREENED_OUT/UNAVAILABLE block; PASS/UNKNOWN don't).
- `widgets/sharia_verdict_banner.dart` — confirmed `unknown` maps to `AmiColors.slate600` (neutral),
  distinct from `screenedOut`/`unavailable`'s `AmiColors.hexAmber` — the color choice the hand-off
  claims is real, not asserted-and-unverified.
- `screens/sim/trade_ticket_sheet.dart` — `permittedVerdict`/`blockingVerdict` wiring is correct:
  reads `state.lastSubmit!.shariaVerdict` on both the accepted and refused branches, gates the new
  banner on non-null, and `_visibleViolations` only strips the English sentence when a
  ticker+standard match is found (never blind-strips). Since `shariaVerdict` is null against the
  live backend today (confirmed above), the code correctly no-ops rather than misbehaving.
- `test/sharia_verdict_test.dart` — read in full, not sampled. The "unknown is not screened-out"
  group asserts absence of the screened-out sentence's load-bearing clauses, not just presence of
  the unknown copy — a real anti-confusion guard (mirrors CR069-ROOM's own guard-widening lesson).
  The "LIVE FIXTURE" tests use response bodies captured from the real backend, not hand-shaped
  JSON — the null-`shariaVerdict` assertions in those tests are themselves independent proof of
  the blocker, authored before I ever hit the API myself.

### Finding — MINOR, precision of the hand-off's own disclosure

The hand-off's "Could not verify" list names **"pass, unknown and the localized paused banner"**
as never rendered live, and its state table marks **"Trade rejection (screened-out): ✅ renders
live today."** Read literally, that checkmark could be taken to mean this lane's *new* code for
that state — `ShariaVerdictBanner` plus `_visibleViolations`'s dedup — has been exercised against
real data. It has not: the lane's own `LIVE FIXTURE — a screened-out rejection parses` test
asserts `r.shariaVerdict` is **null** for that fixture too (same root cause, same blocker). What
actually renders live for screened-out today is the **pre-existing, unchanged** raw English
`violations[]` sentence — correct and compliant with constraint 1, but not this lane's new banner
or dedup path, which is exactly as dark as pass/unknown/paused. The user-facing outcome is fine
(nothing wrong is shown); the gap is that the "Could not verify" list, if read as exhaustive,
underclaims by one state. Given how carefully this hand-off discloses everything else — this reads
as an omission, not a soft-pedal. Not a BLOCKER or MAJOR: nothing renders incorrectly, and the
existing fallback already satisfies the disclosure requirement for that one state. Worth a
one-line addition to the "Could not verify" list so a future reader doesn't credit the new banner
code with live verification it hasn't had.

### Findings summary

Zero BLOCKER, zero MAJOR against this lane's own acceptance and scope. One MINOR (above, hand-off
precision, not a code defect). The wire-contract gap is real and severe, but is explicitly outside
this lane's HOT-FILES (backend paths are forbidden to this lane by its own assign) — not a defect
in CR069-MOBILE's own delivery. Recommending the architect answer the coder's own Q1
(CR069-BE follow-up lane vs. widening this one) promptly, given it is live in production today —
not minting an ID myself; per AMI_TRADE_BINDINGS, a product-code gap outside the audited chunk's
own scope is the architect's/coder.api's call, not the auditor's.

### Verdict

Every claim in the hand-off independently reproduced: test counts (60/60), analyze (4/4 identical
pre-existing infos), untranslated counts (113/114), scope (13 files, mobile-only, no version bump),
and — most importantly — the wire-contract gap itself, reproduced live against the real backend
from a fresh session I built myself, not copied from the transcript. The mobile-side
implementation (wire mirror, four-state rendering, colour semantics, AR/MS placeholder removal,
the constraint-2 guard) is correct, tested, and ready to light up the moment the field ships.

**VERDICT: COMPLETE (round 1)**

Run report: [`../runs/2026-07-23_run-40/run_report.md`](../runs/2026-07-23_run-40/run_report.md)
