# CR061 — Orchestration quick wins (round 2 hardening)

**Status:** in_progress · **Owner:** Architect (track R / dispatch) · **Filed:** 2026-07-22 · **Tag:** `(AT:architect CR061)`

Four small, high-leverage fixes surfaced by dogfooding CR058/059/053 through the CR052 fleet. All
Architect-owned `orchestration/` tooling (no product code). Worktree isolation (the big throughput
fix) is deliberately a SEPARATE later CR per Saiful — this CR is only the cheap wins that reduce
per-lane friction and de-risk the audits happening right now.

## Why (the concrete friction each fixes)

1. **Full-suite death-trap (structural).** The unit suite measured **828s** (not the ~210s assumed) —
   *longer than the 600s max Bash timeout*, so it can NEVER complete in a single foreground call: it
   is always auto-backgrounded and would kill a headless one-shot worker (P7). The CR059 auditor only
   survived by improvising a background+poll loop. This must be a documented, scripted pattern, not
   luck.
2. **Every audit hand-bridged.** I hand-write each auditor's prompt (read AUDITOR.md, verify SHA, run
   suite safely, blind-probe, write verdict, clean up). With 4+ audits imminent, templatize it.
3. **Verification is all manual.** Each lane I hand-run the same ground-truth checks (origin sync,
   commit scope, forbidden files, corpus-test exit). Script the mechanical half.
4. **Roster `live_handle` churn.** `dispatch_launch.sh` `sed`s the shared roster on every launch —
   collides under same-instance concurrency and leaves `roster/<id>.md` modified-uncommitted every
   time (I `git checkout` it each lane). Write a per-lane handle file instead.

## What (the four artifacts)

1. **`orchestration/dispatch/run_full_suite.sh`** — runs the full unit suite to a log and echoes a
   clean `SUITE_EXIT=<code>` sentinel. **Designed to be launched with `run_in_background:true` and
   polled** (828s > 600s max timeout ⇒ background+poll is the only safe way). AUDITOR.md documents it.
2. **`orchestration/dispatch/dispatch_audit.sh <lane> <sha> "<criteria>"`** — templatized auditor
   launch: wraps `dispatch_launch.sh auditor.core <lane> premium solo` with the standard preamble
   (read AUDITOR.md; verify SHA in a clean tree; run the suite via the background+poll pattern; write
   `VERDICT: COMPLETE|AWAITING_FIXES (round N)` to `lanes/<lane>.audit.md`; clean any probe; stage the
   verdict by name; commit+push) + the caller's specific criteria.
3. **`orchestration/dispatch/dispatch_verify.sh [<glob> <count>]`** — mechanical ground-truth on HEAD:
   origin-sync, no forbidden files (uv.lock/settings.local.json/Archive.zip/roster) in the commit,
   optional "exactly N files matching glob", and the corpus-integrity exit code. Non-zero on any fail.
   Does NOT replace the Architect's content read — just the mechanical half.
4. **`dispatch_launch.sh` roster fix** — record the session id to `handles/<lane>.handle` (per-lane,
   disjoint) instead of `sed`-ing the shared roster. Kills the collision + the uncommitted churn.

## Definition of Done

| Row | Disposition |
|---|---|
| Scope | 3 new scripts + 1 helper edit + AUDITOR.md background+poll note. No product code. |
| Tests | POSIX `sh`; smoke-tested (verify passes on a clean HEAD; audit/run_full_suite dry-checked). |
| Docs | This doc; AUDITOR.md note; cr_list row. |
| Commit tag | `(AT:architect CR061)`. |
| Independent check | Self-authored tooling (Architect domain). Same self-cert posture as CR057 — route to auditor.core if Saiful wants; recommended low-priority (tooling, not shipped code). |
