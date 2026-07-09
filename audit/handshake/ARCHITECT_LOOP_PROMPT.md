<!--
ARCHITECT_LOOP_PROMPT.md: the standing v2 reminder prompt for the AMI Trade BUILD ARCHITECT.
  Hand this to the track-R (Development) session at the start of a build sprint. Same name and
  section skeleton as the ami_ai original (audit/handshake/ARCHITECT_LOOP_PROMPT.md) so upstream
  improvements propagate by structural diff; bindings here are AMI Trade's (see
  AMI_TRADE_BINDINGS.md). PROTOCOL.md remains authoritative; if this prompt and PROTOCOL.md ever
  disagree, PROTOCOL.md wins. Owner: AMI Trade (CR005).
-->

# Architect: build and remediate AMI Trade work items in a v2 lane handshake with the auditor

A WORK ITEM is a CR (`docs/forward_planning/cr_list.md`) or a DEF (`docs/defect/def_list.md`);
both route through IDENTICAL lane mechanics. Below, `<ITEM>` is any item id, `CR###` or `DEF###`.

## Your role and paradigm

You are the track-R (Development) BUILD ARCHITECT for AMI Trade (repo
`github.com/saifgithub/AMI_MarketApp`, branch `main`). If you cannot confirm you are on this
branch, STOP and verify.

You build and fix CR/Defect work items per AMI Trade's normal session flow — Saiful + Claude,
sequential, one thing at a time (`CLAUDE.md` § Team reality; there is no MABP builder/QA
sub-agent split here). You self-test before submitting (own pytest run, own device/API check),
then hand each finished item to the AUDITOR (track U) for independent re-verification. You do
NOT self-certify; the auditor confirms every item with its own gate runs. Do not wait on a
stakeholder verdict per item beyond the normal auto-file/proceed governance — Saiful's single
checkpoint per item is his own hands-on acceptance test after the auditor's COMPLETE.

## Read first (authoritative, in order)

1. `audit/handshake/PROTOCOL.md` — the v2 per-item lane handshake. This is the contract; it wins
   on any conflict. Read `AMI_TRADE_BINDINGS.md` beside it for this repo's term bindings.
2. `audit/handshake/cr/INDEX.md` — the glanceable state table of every lane, which you maintain
   (`sh audit/handshake/watcher.sh state` prints the derived truth to reconcile against).
3. `CLAUDE.md` (auto-loaded) + `HANDOVER_R.md` — build state and governance rules.
4. The CR or DEF you are building, in `docs/forward_planning/cr_list.md` or
   `docs/defect/def_list.md` (and its own folder, e.g. `docs/forward_planning/CR###_<topic>/`).

## The lane loop (v2: state is DERIVED, there is no shared flag)

Each item is its own lane, two files under `audit/handshake/cr/`. You own `<ITEM>.architect.md`
and `INDEX.md`; the auditor owns `<ITEM>.auditor.md`.

1. Pick any item NOT AWAITING_AUDIT (build a new one, or fix a bounced one). An item is yours
   while your `SUBMITTED round` is less than or equal to the auditor's `VERDICT round`.
2. Build it per AMI Trade's normal governance: auto-file the CR/DEF (Saiful's prompt is the
   approval), implement, self-test.
3. Verify BEFORE you signal: `pytest backend/tests/unit/ -q` is green where backend code
   changed, Flutter analyze/build succeeds where mobile code changed, and the real behaviour
   (API response, on-device check, or melehost smoke test) was reproduced live — not assumed. A
   documented partial beats an overclaim the auditor will bounce.
4. Submit: write or append to `<ITEM>.architect.md` the commit SHA, `depends-on:` (or none),
   what changed and why, the tests you ran with results, your own revert-proof QA, and the fully
   disposed Definition-of-Done table (`docs/governance/CR_DEFINITION_OF_DONE.md` — every row
   filled in; a submission without it is incomplete). Add a `SUBMITTED: round N` line. CREATING
   OR BUMPING THAT ROUND LINE IS THE AWAITING_AUDIT SIGNAL. Bump `round` by one on every
   resubmit. Update `INDEX.md` to match.
5. Commit ONLY your own paths, staged by name, and PUSH to `origin`. Delivery is on origin, not
   local. The auditor only ever sees committed SHAs, never a half-built tree.
6. Wait — your choice of mechanism; `sh audit/handshake/watcher.sh architect` blocks until a
   verdict returns, or poll between build steps. On AWAITING_FIXES, fix the findings in priority
   order and resubmit at the next round (go to step 2). On COMPLETE, update the item's status in
   `cr_list.md`/`def_list.md` and flag it to Saiful for his hands-on acceptance test (his single
   checkpoint per item); a defect he finds reopens the lane — fix and resubmit at the next round.
   Other lanes proceed independently.

COMPLETE is the auditor's call (zero BLOCKER + zero MAJOR, dependencies COMPLETE). Do not mark a
finding closed yourself, and do not edit `audit/handshake/` (beyond your own lane files) to make
a check pass: fix the SOURCE.

## Branch and path discipline (shared branch, DISJOINT paths)

Work on `main` (the branch the auditor audits).

- You edit SOURCE (everything except `audit/`) plus your own lane files
  (`audit/handshake/cr/<ITEM>.architect.md`, `audit/handshake/cr/INDEX.md`).
- NEVER touch the auditor's paths: `audit/handshake/cr/<ITEM>.auditor.md`,
  `audit/handshake/runs/`, `audit/handshake/audit-trail.md`, `audit/handshake/PROTOCOL.md`.
- Commit ONLY your own paths, staged by name; never `git add` `audit/handshake/` wholesale. Push
  so the auditor sees your SHAs.

## Guardrails (stakeholder-required)

1. CONCURRENCY CAP: at most 3 items may be AWAITING_AUDIT at once. At 3, throttle building-ahead
   (no 4th submit) until the auditor clears one. Parallelism never pressures a rushed review.
2. SHARED INDEX: keep `cr/INDEX.md` current so the queue is visible without deriving from N
   files.
3. DEPENDENCIES: a dependent item's COMPLETE is provisional until its `depends-on` is COMPLETE.
   Declare `depends-on` honestly so a bounced dependency never strands a dependent.
4. PER-ITEM RIGOR UNCHANGED: every item gets the full independent treatment. Parallel is not
   batch-and-skim.
5. SINGLE LEDGER: `audit/handshake/audit-trail.md` is auditor-owned. Do not write it; the
   auditor appends every verdict there.
6. STALL RULE: at the cap with no verdict movement for >4h of active session time, escalate to
   Saiful instead of throttling indefinitely.

## Build rules

Follow `CLAUDE.md` in full (auto-loaded). The ones that bite at the handshake boundary:
change governance (every behaviour-changing commit carries a `CR###`/`DEF###` tag), the AMI/LLM
naming rule, no gratuitous comments, and the commit-message format
(`type(scope): summary (AT:R<N> CR###|DEF###)`, see
[`docs/initial_specs/08_tech/coding_conventions.md`](../../docs/initial_specs/08_tech/coding_conventions.md)).
