## CR231 — Stabilisation programme

## What

An Architect-led records-cleanup + retroactive-audit programme that brings six weeks
of largely-unaudited work back under control before AMI Trade opens to an external
beta. Saiful was away for three days and returned unable to account for 2026-08-13 →
09-24: 966 commits, 92 checkpoint memos, ~20 sessions. His concern was not any one
defect — it was that work had not been finished or validated properly, and he could
no longer tell which parts had been. This CR is the Architect's response: a read-only
sweep of what shipped, what it did and did not have independent audit coverage,
followed by a sequenced plan to close the gap and reach a shippable external beta.

## Why

Saiful, on return: he had lost track of six weeks of work and needed it brought back
under control. A read-only sweep found:

- **Built:** 43 CRs and 132 DEFs closed in the window. Register totals: 182 of 227 CRs
  done, 10 DEFs open.
- **Audited by track U (COMPLETE):** only about 25 IDs — CR109, CR175, CR179, the
  ledger family (DEF316–320, CR188, CR189), DEF182, DEF397, CR220, CR221 slots 2/4/5,
  CR227, CR230, CR200/R001, CR228.
- **Not audited (about 175 IDs), including risky ones:** the options/sim engine
  (CR172 plus ~20 DEFs), PM/Room verdict logic (CR219's 50 code commits, CR201,
  DEF384), security/credits (DEF369–373, DEF361), and the migration chain.
- **Alpha:** `alpha-2026-09-24-1` holds all backend work; nothing is waiting to
  promote. Stores: build +108, internal tracks only.
- **Dropped without an ID:** `DIVERSIFICATION_FLOOR` never enforced at runtime;
  `liquid_only` not enforced in `safety_floor.py`; OIDC IDs have no unique
  constraint; `q6_text` collapses risk tiers 4 and 5 into one suggestion; the Day
  Trader preset has no `max_drawdown_pct`.
- **At risk of loss:** the revenue/payments research lived only in a claude.ai
  artifact and `/tmp` — no durable home in the repo.
- **Stale records:** the daily review log (last entry 09-10), `project_plan.md`
  status (last updated 07-12), CR036 text, CR200 and CR228 rows still reading
  `in_progress` after later work, audit-ledger rows for CR124/CR131/CR132, and 34 old
  worktrees.

Taking this on as a CR rather than folding it into ordinary session work matters
because the finding itself is the point: a gap this size needs a record that it was
found, sized, and closed — not another silent pass.

## Scope

**Go-to-market target:** external TestFlight + Play closed testing, on the current
melehost Alpha stack. Payments stay parked. The GCP/Supabase Beta move comes later —
this CR does not touch that migration.

**Audit scope:** the six risky lanes named below only. Trivial UI, copy and content
fixes already shipped are accepted as-is — this is not a full re-audit of the 966
commits, it is a targeted pass over the load-bearing logic that was never
independently checked.

**Freeze order:** finish CR221, CR222 and CR228 first (all three already
`in_progress`), then freeze new features. Requests filed after the freeze starts are
filed as `proposed`, not built immediately.

**Auditor:** the existing track U session (u66), using the standing
`orchestration/audit/` handshake. The one-shot `dispatch_audit.sh` path is retired —
it gave CR227 a false COMPLETE and is not trusted for this pass.

### Phase 0 — Records cleanup (Architect does this directly; small and reversible)

1. Back-fill the missing daily-review-log rulings (09-22, 09-23, 09-24) and record
   D-072/D-073 in the decision log.
2. Preserve the revenue/payments and ad-placement research into the repo
   (`docs/forward_planning/CR231_stabilisation_programme/`) so it survives outside
   `/tmp` and a claude.ai artifact.
3. File DEFs for the five dropped items the sweep found (DEF416–418 filed here; the
   remaining two — `DIVERSIFICATION_FLOOR` runtime enforcement and the Day Trader
   preset's missing `max_drawdown_pct` — are tracked for a follow-up filing pass, not
   invented against unverified line numbers in this CR).
4. Prune stale worktrees: only those confirmed merged into `main`, dirty ones
   checked first. (Not executed as part of this documentation pass — flagged for a
   dedicated pass so a merged-but-uncommitted worktree is never swept.)

### Phase 1 — Retroactive audit of risky unaudited work (track U handshake, Tier A)

Six lanes, highest risk first:

1. **SIM-OPTIONS** — CR172, CR204–206, DEF353/354/356/357/363–365/368,
   DEF305/309–313/323/377.
2. **PM-FLOOR** — CR219, CR201, DEF384, DEF383, DEF352, DEF398, CR210.
3. **SECURITY-CREDITS** — DEF369–373, DEF361, DEF328, DEF381, CR202.
4. **MIGRATIONS** — single alembic head, plus a fresh-DB upgrade from base to head.
   Covers DEF337, DEF406, DEF411 and the CR219/CR222 migrations.
5. **CR221 slots 1 and 3**, plus the CR170/CR171 backend halves.
6. **CR222 slice C.**

Every audit finding goes through the normal CR/DEF flow. Pass bar: goal-level probes
on real payloads, not just green tests (per CLAUDE.md's "audit against the goals, not
just the states").

### Phase 1b — Close the CRs already in flight (then the freeze starts)

- **CR228:** Saiful sets the success target, then close.
- **CR222:** slice C, audited in lane 6 above.
- **CR221:** decide the five flags that are built but off, and decide slots 6 and 7
  or split them out.

### Phase 2 — External beta go-to-market (items needing Saiful marked [S])

- **External TestFlight:** beta review, tester group, "what to test" notes.
- **Play:** closed-testing track.
- **E5 device matrix** [S].
- **DEF375:** coach-mark tours block the iOS gate tests.
- **DEF178:** key rotation [S].
- **Support inbox** (M9) and **email DNS** (A3).
- **Push** (A15/A16): confirm working, update the plan document.
- **Legal:** lawyer review (A22) [S].
- **Deferred:** ads (CR225/CR226), store production listing, payments.

## Acceptance

- [ ] All six audit lanes (SIM-OPTIONS, PM-FLOOR, SECURITY-CREDITS, MIGRATIONS,
  CR221 slots 1/3 + CR170/CR171 backend, CR222 slice C) carry a COMPLETE verdict in
  `orchestration/audit/cr/`, plus a row in the audit-trail ledger.
- [ ] CR221, CR222 and CR228 are closed (row status flipped, not just built).
- [ ] Feature freeze is in effect: new requests filed as `proposed`, none built ahead
  of the freeze without Saiful's explicit go.
- [ ] External TestFlight beta is live (beta review passed, tester group invited).
- [ ] Play closed-testing track is live.
- [ ] `pytest backend/tests/unit/ -q` passes; the preflight suite runs bare (not
  piped) with `VERDICT` read, per CLAUDE.md's gate-exit-code rule.
- [ ] `/promote-to-alpha` run after any audit-driven fix; public health check green.

## Non-goals

- The GCP/Supabase Beta cutover — stays a later, separate move.
- Payments/RevenueCat provisioning — stays parked per Saiful's 2026-08-21 ruling,
  unchanged by this CR.
- A full re-audit of every one of the ~175 unaudited IDs — only the six named risky
  lanes are in scope; trivial UI/copy/content changes are accepted as shipped.
- Ads (CR225/CR226) and store production listings — deferred, not part of the beta
  gate.

## Status

`in_progress` — filed 2026-09-24 by the Architect, back-filling records from session
transcripts covering 2026-09-22 through 2026-09-24. Phase 0 records cleanup executed
in this pass (decision log, daily review log, DEF filing, research preservation).
Phases 1, 1b and 2 not yet started.
