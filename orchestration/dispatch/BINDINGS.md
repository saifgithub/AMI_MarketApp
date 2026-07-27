<!--
BINDINGS.md — AMI Trade local bindings for the dispatch handshake. PER-PROJECT: resolves the
generic terms in DISPATCH_PROTOCOL.md / the loop prompts to this repo's concrete paths, hosts,
commands, and the hot-file registry. The generic files stay byte-identical across projects; only
this file + roster/ change. CR052.
-->

# AMI Trade — dispatch bindings

## Term resolution

| Generic term | AMI Trade binding |
|---|---|
| The stakeholder | **Saiful** — founder, sole human-in-the-loop, single acceptance checkpoint after COMPLETE (`CLAUDE.md` § Team reality). The portable files never name him; this row is the only place the name belongs |
| Shared branch | `main` — delivery = pushed to `origin` (`github.com/saifgithub/AMI_MarketApp`) |
| `<ORCH_ROOT>` | `orchestration` |
| `<DISPATCH_ROOT>` | `orchestration/dispatch` |
| `<AUDIT_ROOT>` | `orchestration/audit` |
| `<AUDIT_LANE_DIR>` | `orchestration/audit/cr` (the builder writes `<ITEM>.architect.md` here on hand-off) |
| `<WORKTREE_DIR>` | `.claude/worktrees` (pattern `agent-*` per session-config; instance worktrees `<instance-id>-<ITEM>`) |
| `<TAG_PREFIX>` | `AT` — commit tag `(AT:<instance-id> CR###\|DEF###)` |
| Change registers | CR: `docs/forward_planning/cr_list.md` · DEF: `docs/defect/def_list.md` (Architect owns status) |
| Backend test command | `cd backend && .venv/bin/python -m pytest tests/unit/ -q` — **measured 2026-07-23: 948 passed in 112 s, exit 0** on an idle Mac (sqlite tempfile, no DB). Fits a foreground Bash call with an explicit `timeout` |
| Mobile test command | `flutter analyze lib/` + `flutter test` |
| Contract check | backend↔mobile is a **hand-mirrored JSON contract, not type-enforced**: re-verify `fromJson` against **real backend JSON**, not just that it compiles (`?? default` hides a rename at runtime) |
| Long-running test command | `sh orchestration/dispatch/run_full_suite.sh` (`uv run pytest tests/unit/`) — launch with `run_in_background:true` and poll for the `SUITE_EXIT=<code>` line. **Runtime unresolved:** CR061's helper scripts assert ~828 s, longer than the 600 s Bash ceiling, while the `.venv` invocation above measured 112 s on 2026-07-23. Whether `uv run` costs the difference or the 828 s figure is stale has not been re-measured — until it is, treat the wrapper as the safe path and don't quote either number as fact |
| Content self-test | `cd backend && uv run pytest tests/unit/test_lesson_corpus_integrity.py -q` (~6 s, exit 0) — a maintainer's whole gate; never the full suite |
| Live-stack verification | curl `https://api-alpha.agenticmarketintel.ai/v1/health`; `ssh melehost "docker logs ami_api_alpha --tail 50"` |
| Deploy path | `/promote-to-alpha` (rsync to melehost; Mac is a pure editor — no local backend) |
| Requester source (errors) | melehost `bug_reports` table (see `.claude/session-config.yml` track R `bug_list`) |

## State & liveness (read artifacts, not processes)

Lane state and auditor liveness are **read from files, never from `ps`**:

- **The board (derived truth):** `sh orchestration/dispatch/dispatch.sh state` +
  `sh orchestration/audit/watcher.sh state`. `board.md` is a lagging cache — reconcile, don't trust.
- **A lane's audit outcome:** `orchestration/audit/cr/<ITEM>.auditor.md` (`VERDICT: COMPLETE |
  AWAITING_FIXES`) + the run folder `orchestration/audit/runs/<date>_run-N/`.
- **The auditor watcher runs as** `sh orchestration/audit/watcher.sh auditor -i 30 -t 3600` — a
  30 s-poll, 1 h-timeout, **self-respawning** process (Saiful starts it; it respawns on its own). It
  is **not** a liveness signal: it is legitimately absent from `ps` while an audit is actually
  running and in the gap between respawns. A momentary `ps` zero-read means nothing — read the
  verdict / run artifacts instead.
  - *Precedent (2026-07-25):* the Architect read two transient `ps` zero-reads as "auditor down" and
    surfaced a false stall, while the watcher was in fact mid-audit; the verdict landed `COMPLETE`
    (CR056, run-46) minutes later. Liveness is the artifact, not the process table.

## Verify cwd — run the gate from the repo root

The Architect's pre-audit and pre-integrate re-run uses `pytest backend/tests/unit/ -q` **from the
repo root** — the exact cwd the `/promote-to-alpha` preflight uses — **not** `cd backend && pytest`.
A subdir run masks a **cwd-fragile test** (a source-grep / file-read using a cwd-relative `Path(...)`)
that is red in the deploy path. In a worktree, build the venv with `cd backend && uv sync --frozen
--extra dev`, then run pytest **from the worktree root**.

- *Precedent (2026-07-25):* CR055's coder honestly reported the suite green — run from `backend/`.
  One guard test used `Path("app/services/room_runner.py")` (cwd-relative); from the repo root it was
  a `FileNotFoundError` and would have failed the promote preflight. Bounced to anchor the path to
  the module (`Path(room_runner.__file__)`), not the cwd.

## Escalation precedents (the evidence behind the portable rules)

The portable core states the rules without citing this repo's history. The history is here, so a
rule that looks arbitrary can be traced to what it cost.

| Portable rule | What happened here |
|---|---|
| Route to an independent auditor on **reversibility, not size** | **DEF084-MOBILE** — three ARB files and one widget, shipped a false claim about a Sharia screen to two app stores |
| Record `GATE:` **upfront**, never at hand-off | DEF084-MOBILE's gate was waived at hand-off, when the work looked finished and the session was long |
| Push to a **lane branch**, never the shared branch | DEF084-MOBILE pushed its source directly to `main` (`e344b27`), bypassing both the audit and the integration step |
| **Commit incrementally** | **DEF083** died on `Exceeded USD budget (5)` after editing 31 lessons and before its first commit; all 31 had to be redone |
| **Never economy tier for an auditor** | **DEF059** — LLM down, confident fake `APPROVE`, shipped. A cheap gate manufactures false confidence rather than leaving a visible gap. Economy-tier workers also fabricate the `STATUS` token itself (`memory/feedback_haiku_completion_lies.md`) |
| The **stall rule computes nothing** | **CR050** sat `AWAITING_AUDIT` across whole sessions with its audit never launched, showing as an ordinary in-flight state |
| Never background a command in a one-shot session | **CR057** — a worker emitted a final message while a job ran and was killed mid-lane (`failure_patterns.md` P7) |
| A `DONE` that never read a verdict | **CR070** — of 14 coder lanes marked `DONE`, only 4 carried an auditor `VERDICT: COMPLETE` |
| Verify a **stateful construct across its full lifecycle**, not just first construction | **DEF088** — CR069-BE round 1 verified the sourced-universe resolver's logic exhaustively and passed. Round 2, prompted by the stakeholder questioning the pace, found two MAJORs in the same code's *runtime shape*: a staleness re-check that only ran when the cache was empty (so a long-running process never noticed data going stale) and a synchronous fetch blocking the async event loop. Correct on the first call is a different claim from correct on the thousandth |
| Evidence that lives in one working tree | **DEF087** — a coder exited having written both hand-off files and committed neither, and the board read `AWAITING_AUDIT`; separately an auditor's `COMPLETE` was briefly uncommitted while the board read `AUDIT_PASSED`, the state that authorises a merge. Both scripts now render `UNCOMMITTED` (CR074) |
| A "verified live" claim that verified **one of two** required sources | **DEF089** — CR069's brief curl'd the compliant-set URL in detail and never once fetched the parent-index URL, which turns out to serve an HTML bot-mitigation page with `content-type: text/csv` on it. The gap survived a brief, a lane and a build |

## Caps and windows

- **Per-instance WIP cap:** 2 active lanes (a coder holds ≤2 at once).
- **Global audit cap:** 3 lanes `IN_AUDIT` per auditor instance.
- **Stall window:** 4h of active session time with no verdict movement at a cap → Architect
  escalates to Saiful.
- **Human = single acceptance checkpoint** after `DISPATCH: ACCEPTED`; a defect Saiful finds reopens
  the lane.

## Hosting & launch (interrogable fleet)

An instance is an **independent session**, not an Architect subagent (subagents are invisible /
ephemeral, used only for disposable helper work inside an instance). Coordination is **file-only** —
each instance self-notices via `sh orchestration/dispatch/dispatch.sh inst <id>` and hands off
through the git repo; the Architect never messages an instance in-process.

Three ways to host, with a verified tradeoff (empirically checked on `claude` v2.1.145):

**A. Local headless workers — RECOMMENDED (local + fresh + auto + interrogable).**
The Architect launches a fresh per-lane worker from its own shell (background), and Saiful
interrogates it by resuming its session id. Verified: `claude -p --session-id <uuid>` runs headless
from an agent's shell, persists to `~/.claude/projects/<hash>/<uuid>.jsonl`, and `claude --resume
<uuid>` restores its full context.
```
# Architect, per lane — ALWAYS via the helper (CR057), run through the Bash tool with
# run_in_background:true (task-tracked ⇒ completion callback for the liveness rule). It encodes the
# whole recipe and REQUIRES a cost tier, so no launch is ever hand-assembled or silently premium:
sh orchestration/dispatch/dispatch_launch.sh <instance> <lane> <tier> <fanout> "<task body>"
#   tier   = economy(haiku/low/$2) | standard(sonnet/medium/$5) | premium(opus/high/$10)
#   fanout = solo | ultra   (ultra = grant Workflow+Agent for in-worktree ultracode fan-out, 3× budget)
#   e.g.  … noncoder.edu CR054-W1-ETHIC economy solo "Commit your 10 authored lessons, run the suite…"
#   DISPATCH_DRY_RUN=1 sh …/dispatch_launch.sh …   # prints the resolved launch, spends nothing
# Start cheap; escalate on failure (economy-fail→standard; a died/harness failure = BLOCKER, 0 retries).
# Saiful, anytime — interrogate (restores the worker's context; uuid printed + written to roster):
claude --resume <uuid>
```
`live_handle` in `roster/<id>.md` = the **current run's `<uuid>`**. Fresh uuid per lane ⇒ small,
cheap context (short-lived, token-economy rule). Interrogation is **resume-by-id**, not live mid-run
streaming.

**Completion is machine-verified, never trusted (CR057 · MABP §16).** A worker's "done / pushed /
green" prose AND its `STATUS` token are *claims*, not evidence. On worker exit the Architect confirms
the ground truth — `git ls-files --error-unmatch` (files really committed), `git show --name-only`
(exact scope, no forbidden paths), and the gate green by **test exit code**. **Economy = Haiku
fabricates completion outright** (see `memory/feedback_haiku_completion_lies.md`) — never integrate an
economy lane on its word; prefer **standard** for any lane whose completion is costly to verify.
Code lanes are covered by the Auditor's independent re-run; content lanes have no Auditor, so the
Architect *is* the mechanical verifier.

**B. Interactive background agents (`claude agents`) — local, live-attachable, but human-launched.**
Saiful dispatches from the `claude agents` TUI (peek = Space, reply = Enter, attach = →);
`claude agents --json` lists them for scripting. **Not agent-launchable:** dispatch requires an
interactive TTY, which the Architect's shell lacks (`claude agents` refuses without a TTY). Long-lived
ones also grow context toward the ~1M auto-compaction ceiling — avoid for cheap operation.

**C. Routines (cloud) — auto + fresh, web-interrogable.** The Architect fires a per-instance routine
(`POST …/routines/<id>/fire`, agent-callable) → a fresh cloud session + a `claude.ai/code` URL to
watch/continue. Not in the local picker; runs on Anthropic cloud. Use if you want unattended cloud
workers instead of local ones.

**Worktree isolation** applies to all: an instance builds in `.claude/worktrees/<id>-<ITEM>/`.

## Auditor mapping (sharding)

- **`auditor.core` as a standing instance was dropped (CR070).** A lane's `GATE:` names its gate:
  `independent` = a session Saiful starts on track U (`AT:U1`) following `AUDITOR_LOOP_PROMPT.md`;
  `spawned` = a fresh agent the Architect spawns per audit, same prompt; `none` = no audit, recorded
  upfront at decomposition. Shard into `auditor.backend` / `auditor.mobile` only if the audit queue
  saturates (each coder's roster `auditor:` field is the switch).

## Hot-file registry (measured — serialize via DEPENDS-ON, never parallel)

| File | Crosses | Rule |
|---|---|---|
| `backend/app/db/models.py` | all backend instances (one 727-line file, 24 tables) | **`coder.api` is sole schema/migration owner.** New table/column + Alembic migration routes through `coder.api`; other lanes take `DEPENDS-ON` its schema lane. |
| `backend/app/agents/safety_floor.py` | `coder.api` (owns) ↔ `coder.room`, sim | Frozen interface; signature changes coordinated. |
| `backend/app/services/{llm_gateway,tier_policy,entitlements,credit_service}.py` | `coder.api` (owns) → `coder.room` (consumes) | Frozen library surface; api keeps signatures stable. |
| `backend/app/main.py`, `core/config.py`, `schemas/__init__.py` | any backend instance | Low-frequency (new router / config var / shared type); serialize on touch. |
| `mobile/lib/services/api/api_client.dart` + `state/onboarding_providers.dart` | `coder.mobile`-internal | Single owner serializes internally — no cross-agent collision. |

**Cross-domain CR** (backend + UI) → split into a backend sub-lane + a `coder.mobile` sub-lane joined
by `DEPENDS-ON` (backend lands the JSON schema first; mobile mirrors it, then runs the contract check).

## Governance

Every dispatched work item carries a CR or DEF id (project rule D-058). The Architect files it on
triage (auto-file, proceed); the register status moves proposed→in_progress at assign, →done at
ACCEPTED. Commit-tag exemptions (version bumps / docs-only, incl. the checkpoint-archive commit)
are unchanged — the retired handover-wrap category is gone; see the project guide's Exempt list.

### When the Architect builds directly vs lanes it (2026-07-25)

The generic role says the Architect allocates and does not build. **AMI override:** the Architect
**may implement a change directly** — no coder spawn, no lane, no worktree — when it is **small AND
low-risk**: a bounded diff (order of tens of lines / a few files), **reversible pre-promote**, and
not touching a high-stakes surface. Still self-verify (targeted tests + the gate from the repo root)
before committing; a trivial bounce (e.g. a one-line test-path fix on a lane) is fixed inline, never
round-tripped to an agent. **Lane it to a coder + independent audit** when the work is substantial,
cross-domain, beyond one context, or touches an **irreversible / high-stakes surface** — store-facing,
money / credits / entitlements, the safety floor, schema / migrations, or a user-facing product claim.
Route on **reversibility, not size** (same axis as the escalation rule). The independent-audit layer
is never dropped on genuinely risky work — it caught a real coder false-green on CR055 (2026-07-25).
*Why: the lane machine has a fixed per-lane cost (spawn / hand-off / re-verify / audit / integrate)
that does not shrink with change size, so running it for small work costs more than the work; you
cannot orchestrate away the cost of orchestration. See `memory/feedback_protect_the_room_not_coder.md`.*
