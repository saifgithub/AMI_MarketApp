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
| Shared branch | `main` — delivery = pushed to `origin` (`github.com/saifgithub/AMI_MarketApp`) |
| `<AUDIT_ROOT>` | `orchestration/audit` |
| `<AUDIT_LANE_DIR>` | `orchestration/audit/cr` (the builder writes `<ITEM>.architect.md` here on hand-off) |
| `<WORKTREE_DIR>` | `.claude/worktrees` (pattern `agent-*` per session-config; instance worktrees `<instance-id>-<ITEM>`) |
| `<TAG_PREFIX>` | `AT` — commit tag `(AT:<instance-id> CR###\|DEF###)` |
| Change registers | CR: `docs/forward_planning/cr_list.md` · DEF: `docs/defect/def_list.md` (Architect owns status) |
| Backend test command | `pytest backend/tests/unit/ -q` (Mac-safe, sqlite tempfile — no DB) |
| Mobile test command | `flutter analyze lib/` + **contract check**: re-verify `fromJson` against real backend JSON |
| Live-stack verification | curl `https://api-alpha.agenticmarketintel.ai/v1/health`; `ssh melehost "docker logs ami_api_alpha --tail 50"` |
| Deploy path | `/promote-to-alpha` (rsync to melehost; Mac is a pure editor — no local backend) |
| Requester source (errors) | melehost `bug_reports` table (see `.claude/session-config.yml` track R `bug_list`) |

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
# Architect, per lane (run in background; --permission-mode lets it act autonomously):
claude -p --session-id <uuid> --permission-mode acceptEdits --add-dir <repo> \
  "You are coder.api. Read orchestration/dispatch/roster/coder.api.md +
   orchestration/dispatch/loop_prompts/CODER.md. Work your assigned lane end-to-end,
   hand off to the Auditor, then stop."
# Saiful, anytime — interrogate (restores the worker's context):
claude --resume <uuid>
```
`live_handle` in `roster/<id>.md` = the **current run's `<uuid>`**. Fresh uuid per lane ⇒ small,
cheap context (short-lived, token-economy rule). Interrogation is **resume-by-id**, not live mid-run
streaming.

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

- Start with a single **`auditor.core`** = the existing track-U audit loop (`AT:U1`), gating every
  coder instance. Shard into `auditor.backend` / `auditor.mobile` only if the audit queue saturates
  (each coder's roster `auditor:` field is the switch).

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
ACCEPTED. Commit-tag exemptions (handover/version/docs-only) are unchanged.
