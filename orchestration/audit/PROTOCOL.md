<!--
PROTOCOL.md — the builder→Auditor audit handshake, v2. PORTABLE CORE: copy verbatim into any
  project; every project-specific path, host, branch and command resolves through the project's
  BINDINGS file beside it. Defines the PARALLEL per-item lane handshake between the BUILD ARCHITECT
  (builds + fixes) and the AUDITOR (verifies) so the two work concurrently without serializing,
  until each work item is COMPLETE (zero BLOCKER + zero MAJOR).
  Ratified 2026-06-21; DEF routing added 2026-06-27; guardrail 6 (output compression) added
  2026-07-12; genericized 2026-07-23 (see PORTABLE_MANIFEST.md).
-->

# Audit handshake v2: parallel per-item lanes

The architect and the auditor work CONCURRENTLY across many work items; neither role idles waiting for
the other. A WORK ITEM is a CR (a planned change) or a DEF (a defect); both route through IDENTICAL
lane mechanics. Below, `<ITEM>` is any item id in this project's id format (BINDINGS).

## The trust-critical contract (never changes)

- The AUDITOR verifies INDEPENDENTLY and NEVER closes on the architect's word: it re-reads the changed
  source at file:line, re-runs the project's independent regression suite (BINDINGS) on the project's
  deploy-target environment (BINDINGS), reproduces the item's real measurement where it has one, and
  runs a blind adversarial pass on the risky dimension. If the item introduces or touches a stateful
  construct — a cache, singleton, connection pool, background task, or anything that persists across
  more than one call — that pass covers its FULL lifecycle, not just first-construction correctness:
  does it ever refresh/expire/invalidate in the deployed process (not only in a test that resets it),
  and does it respect the project's concurrency model. Correct on the first call is a different claim
  from correct on the thousandth, or under concurrent access (DEF088). Per-item rigor is unchanged
  under parallelism (guardrail 4).
- DISJOINT PATHS, shared branch (BINDINGS): the ARCHITECT writes SOURCE + its own
  `<AUDIT_LANE_DIR>/<ITEM>.architect.md` + `<AUDIT_LANE_DIR>/INDEX.md`; the AUDITOR writes
  `<AUDIT_ROOT>/**` only (`<ITEM>.auditor.md`, `runs/`, `regression/`, `audit-trail.md`, this
  PROTOCOL). Each role commits ONLY its own paths, staged by name, AND PUSHES them to origin
  immediately. DELIVERY IS ON ORIGIN, NOT LOCAL: a committed-but-unpushed lane file is invisible to a
  counterpart that syncs via origin, so a verdict or submission counts as handed over only after
  origin reflects it. Confirm origin advanced (e.g. `git branch -r --contains <sha>`) before treating
  the round as passed to the other role.
- A work item is COMPLETE only when the auditor confirms zero BLOCKER + zero MAJOR (and dependencies are
  COMPLETE). Evidence on every lane file is round-stamped.

## The lanes (directory as queue, no shared mutable flag)

Per item, two files under `<AUDIT_LANE_DIR>/` (one directory holds CR and DEF lanes alike):

- `<ITEM>.architect.md` (architect owns): commit SHA, `depends-on:` (or none), what/why, tests run +
  results, the architect's own revert-proof QA, and a `SUBMITTED: round N` line. Creating or bumping
  that round line is the AWAITING_AUDIT signal.
- `<ITEM>.auditor.md` (auditor owns): per-finding verdict + a
  `VERDICT: COMPLETE | AWAITING_FIXES (round N)` line, plus the run-report path under `<AUDIT_ROOT>/runs/`.

STATE is DERIVED from the two files (no shared flag, no merge conflict on concurrent commits). The
trigger for either role is purely the round numbers on any `*.architect.md` lane (CR or DEF):

- AWAITING_AUDIT (auditor's turn): architect `SUBMITTED round` > auditor `VERDICT round`, or no auditor
  file yet.
- AWAITING_FIXES (architect's turn): the auditor's latest verdict is `AWAITING_FIXES`.
- COMPLETE: the auditor's latest verdict is `COMPLETE`.

The architect works any item NOT AWAITING_AUDIT (building new, fixing bounced), in isolated worktrees or
serialized when source overlaps; the auditor only ever sees COMMITTED SHAs, never a half-built tree. The
auditor works any item that IS AWAITING_AUDIT, FIFO by SUBMITTED time, respecting `depends-on`.

HOW each role notices its turn is the role's own choice; the state is always derivable from the round
numbers, so nothing is lost while a role is busy elsewhere. The auditor runs a watcher over the lane
files. The architect, which may have parallel building underway with its own scheduling concerns,
DECIDES FOR ITSELF how and when to "wait" for a returned VERDICT (a watcher, a poll, or a check between
build steps); the protocol mandates no specific mechanism on the return path.

## Guardrails (stakeholder-required, 2026-06-21)

1. CONCURRENCY CAP: at most N items AWAITING_AUDIT at once (N in BINDINGS). At the cap, the architect
   throttles building-ahead (no further submit) until the auditor clears one, so parallelism never
   pressures a rushed review.
2. SHARED INDEX: the architect keeps `<AUDIT_LANE_DIR>/INDEX.md`, a glanceable read-only table of every
   lane and its derived state, so the queue is visible without deriving from N files.
3. DEPENDENCIES: a dependent item's COMPLETE is PROVISIONAL until its `depends-on` is COMPLETE. The
   auditor may review early but does not set COMPLETE until the dependency is, so a bounced dependency
   never strands a dependent.
4. PER-ITEM RIGOR UNCHANGED: parallel is not batch-and-skim; the cap exists to protect the full
   independent treatment.
5. SINGLE LEDGER: `<AUDIT_ROOT>/audit-trail.md` is the ONE chronological history across all lanes (the
   auditor appends every verdict), so there is one auditable record.
6. OUTPUT COMPRESSION: narrative prose in `<ITEM>.architect.md`, `<ITEM>.auditor.md`, `audit-trail.md`
   headlines, and `runs/<date>_run-NN/run_report.md` is written compressed — fragments over full
   sentences, no filler or hedging, every technical noun and verb kept. Command output cited as
   evidence, file:line citations, machine-parsed state (`SUBMITTED: round N`,
   `VERDICT: COMPLETE | AWAITING_FIXES (round N)`, `depends-on:`), and severity labels (`BLOCKER`,
   `MAJOR`, `MINOR`) are NEVER compressed or paraphrased, so the auditor's re-verification,
   `watcher.sh`'s regex, and the trust-critical contract's COMPLETE test all stay exact.

## Borderline severity: doubt bounces

When a finding's severity is genuinely in doubt (a safe-but-debatable MAJOR vs a strong MINOR), the
auditor does NOT auto-close and does NOT default to the stakeholder: it BOUNCES (writes the finding to
`<ITEM>.auditor.md`, sets `VERDICT: AWAITING_FIXES`). Doubt resolves toward MAJOR, not COMPLETE.
Stakeholder escalation is the EXCEPTION, reserved for a genuine classification dispute or a policy/scope
call the auditor cannot make, not a routine borderline.

## Done (per item)

On EVERY verdict (AWAITING_FIXES and COMPLETE alike), the auditor writes the verdict to
`<AUDIT_LANE_DIR>/<ITEM>.auditor.md`, writes the run report under `<AUDIT_ROOT>/runs/<date>_run-NN/`,
appends the `<AUDIT_ROOT>/audit-trail.md` ledger row, then COMMITS those `<AUDIT_ROOT>/` paths by name
AND PUSHES them to origin, and confirms origin advanced before treating the round as handed back. A
committed-but-unpushed verdict is NOT delivered: an origin-syncing counterpart sees no verdict and reads
the lane as still AWAITING_AUDIT (this once stranded a round-10 AWAITING_FIXES verdict on a local clone
for ~2h). Note also that the auditor CANNOT update `INDEX.md` (architect-owned), so on a bounce the
INDEX lags: detect a returned verdict by reading the auditor lane `VERDICT` keyword, never by the INDEX
row or by comparing round numbers alone (after a bounce SUBMITTED == VERDICT, numerically identical to a
COMPLETE). On COMPLETE the architect then advances or deploys that item while other lanes proceed
independently.
