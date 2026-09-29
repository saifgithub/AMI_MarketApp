# AGENTS.md — Project guide for Kimi Code sessions (Track K)

Loaded into every Kimi Code session in this project. This is the slim companion to
[`CLAUDE.md`](CLAUDE.md) — the canonical shared guide. Both carry the same pointers:
high-level orientation and behaviour-critical rules here, canonical detail under `docs/`.

---

## Standing instructions (override defaults)

1. **Be succinct** — always, unless Saiful instructs otherwise. No filler, no restating,
   no summaries he didn't ask for.
2. **Numbered lists, always** — whenever you present a list (steps, options, findings),
   use a numbered list, not bullets, so Saiful can refer to items by number.

---

## Agent identity and track

- **Track:** `K` · **Role:** `Kimi` · **Instance:** `<id-or->` (leave as `-` if not a fleet instance).
- Commit/session tag: `AT:K<N>` — increment the session number per Kimi session; keep the `K`
  prefix so Kimi commits are distinguishable from Claude's `R` commits.
- Checkpoint memos open with: `TRACK: K · ROLE: Kimi · INSTANCE: <id-or->`.

---

## What this project is

**AMI Trade** — a mobile-first, simulation-only AI trading-education app where each user is the
CEO of a 12-agent analyst team. Simulation-only, advisory-only forever. US equities at MVP;
EN at alpha, AR + MS at v1.0; iOS + Android-GMS at alpha. The AI is named **AMI** in anything a
user might read; **LLM** is fine in code, routes, logs, and internal docs.

Full spec: [`docs/initial_specs/00_overview/`](docs/initial_specs/00_overview/) and
[`docs/initial_specs/01_product/core_loop_and_features.md`](docs/initial_specs/01_product/core_loop_and_features.md).
Team split (who does what): [`docs/initial_specs/10_delivery/you_do_i_do.md`](docs/initial_specs/10_delivery/you_do_i_do.md).

---

## External dependencies (read-only mounts)

| Mount | Purpose |
|---|---|
| `/Volumes/Extreme Pro/AMI AI Design System/` | AMI hex design system. Tokens, fonts, components. |
| `/Volumes/Extreme Pro/TradingAgent/` | TradingAgents fork basis — frozen at `7e9e7b8`. Never fetch/pull. |
| `/Volumes/Extreme Pro/TradingAgent_upstream/` | Same repo tracking upstream `main` (CR167) — use for drift questions. |

Integrate against them; never modify them.

---

## Runtime state (read before assuming anything)

The system is **live**. The Mac is a pure editor — no backend, no database, no Docker; backend
unit tests run on the Mac via a SQLite tempfile fixture, everything else ships via promotion.
Alpha runs on `melehost` (Ubuntu, LAN `192.168.20.59`) as `ami_postgres` + `ami_redis` +
`ami_api_alpha` + `ami_tunnel` under Docker Compose, public at
`https://api-alpha.agenticmarketintel.ai` via Cloudflare Tunnel. The LLM is on-prem vLLM at
`http://192.168.20.74:8000` (gateway prefers `vllm > anthropic > mock`). Code transport is
rsync-only via `/promote-to-alpha`; GitHub (`origin`) is backup + multi-agent sync, not a deploy path.

Full detail: [`CLAUDE.md`](CLAUDE.md) "Runtime state" (loaded on demand), [`docs/initial_specs/08_tech/hosting.md`](docs/initial_specs/08_tech/hosting.md),
[`docs/initial_specs/10_delivery/promotion_protocol.md`](docs/initial_specs/10_delivery/promotion_protocol.md),
[`docs/initial_specs/08_tech/backend_modes.md`](docs/initial_specs/08_tech/backend_modes.md),
and the newest own-marker checkpoint memo under [`.deliveryos/checkpoint_history/`](.deliveryos/checkpoint_history/).

If a check fails, debug from melehost — never start a backend on the Mac:

```bash
curl -s https://api-alpha.agenticmarketintel.ai/v1/health
ssh melehost "docker ps --filter 'name=ami_'"
ssh melehost "docker logs ami_api_alpha --tail 50"
```

---

## Commands and skills (Kimi)

Kimi has no separate command-file mechanism — runbooks are Skills, invoked as `/<name>`
(shorthand for `/skill:<name>`).

- **Project skills:** [`.agents/skills/`](.agents/skills/) — runbooks: `/promote-to-alpha`,
  `/rollback-alpha`, `/promote-to-beta`, `/promote-to-prod`, `/rollback-beta`,
  `/rollback-prod`, `/fix-bugs`, `/bug-monitor`, `/daily-cr-def-review`, `/send-test-push`;
  plus `auditor` and `youtube-extract`. These are Kimi copies of `.claude/commands/*.md` —
  **when a runbook changes, update both copies.**
- **User-global skills:** `~/.kimi-code/skills/` — includes the `sm-*` continuity pair
  (`/sm-savepoint` + `/sm-readpoint` around `/compact`; `/sm-handover` + `/sm-takeover`
  across sessions) and the general-purpose skills copied from `~/.claude/skills/`.
- Claude's originals live in `.claude/commands/` and `~/.claude/` — do not edit those from
  a Kimi session unless the change is meant for both tracks.

---

## Conventions

Full style rules: [`docs/initial_specs/08_tech/coding_conventions.md`](docs/initial_specs/08_tech/coding_conventions.md).
Two behaviour-critical rules affect every session:

- **Degrade loudly (CR040).** Config-gated features fail visibly, never silently fall back;
  new env settings must be forwarded in `docker-compose.yml`'s `api-alpha` block
  (`backend/tests/unit/test_config_compose_parity.py` enforces). Prompt instructions are not
  controls — if something must hold, make it structural. Recurring classes + their guards:
  [`docs/initial_specs/08_tech/failure_patterns.md`](docs/initial_specs/08_tech/failure_patterns.md)
  (the guards register — second occurrence gets an entry **with a guard**). Third time, or a
  guard that failed twice ⇒ a Dilemma, not a point fix (CR185):
  [`docs/dilemmas/DILEMMA_PROTOCOL.md`](docs/dilemmas/DILEMMA_PROTOCOL.md).
- **Naming.** New files get a short docstring/header saying what they are and why; comments
  default to none (only non-obvious *why*).

---

## Change governance (CR / Defect)

Every behaviour change is a **CR** (planned) or a **Defect** (fix). Both registers are
**generated** — never hand-edit the `.md` tables:

- Registers: [`docs/forward_planning/cr_list.md`](docs/forward_planning/cr_list.md),
  [`docs/defect/def_list.md`](docs/defect/def_list.md). Row files:
  `docs/forward_planning/_registry/CR###.row.md`, `docs/defect/_registry/DEF###.row.md`.
- The Architect mints IDs; the item's domain owner writes the row file; regenerate with
  `python scripts/registers/gen_registers.py gen [def|cr|all]`.
- **Commit with an explicit pathspec, never bare** — the shared `main` checkout means a bare
  commit sweeps other tracks' dirty files. Format:
  `type(scope): summary (AT:K<N> [CR### | DEF###])`; user-reported bugs:
  `fix(bug:<short-id>): summary (AT:K<N> DEF###)`.
- Exempt (plain `AT:K<N>`): version/build bumps, docs-only commits, checkpoint archive commits.
- Enforcement is convention-only; full rules in [`CLAUDE.md`](CLAUDE.md) "Change governance".
  Optional independent verification for risky items: [`orchestration/audit/PROTOCOL.md`](orchestration/audit/PROTOCOL.md).

---

## Build & test quick reference

```bash
pytest backend/tests/unit/ -q          # backend unit tests (SQLite tempfile fixture)
cd mobile && flutter analyze --no-fatal-infos && flutter test
python scripts/registers/gen_registers.py verify all   # register parity
```

Backend: FastAPI + Pydantic, async-first, Python 3.13, Alembic, structlog. Mobile: Flutter +
Riverpod + go_router, dark-only hex design system. Repo map and stack detail:
[`CLAUDE.md`](CLAUDE.md) and [`docs/initial_specs/`](docs/initial_specs/). Never start
uvicorn/docker/Postgres/Redis on the Mac.

---

## What to do when you start a session

1. Read this file and [`CLAUDE.md`](CLAUDE.md).
2. **Daily CR/Defect review check (CR085).** If it's on/after 13:00 Asia/Riyadh and
   `docs/governance/daily_cr_def_review_log.md` has no `## YYYY-MM-DD` section for today, run
   `/daily-cr-def-review` before other work. Skip silently if today's section exists.
3. **Bug-monitor fallback check (CR185).** If the newest `docs(bug-monitor)` commit is more
   than 6h old (or none exists), run `/bug-monitor` once before other work.
4. **Freshest state:** newest checkpoint memo carrying your own marker —
   `grep -l "ROLE: Kimi" .deliveryos/checkpoint_history/*.md | sort | tail -1`. Do not read
   the newest file blindly (the folder interleaves all tracks). If none, fall back to
   `git log --oneline` + the registers.
5. Skim [`docs/initial_specs/10_delivery/project_plan.md`](docs/initial_specs/10_delivery/project_plan.md).
6. `git log --oneline` to verify the commit chain.
7. Find the topic-specific doc(s) in `docs/` for your task. Ask Saiful what to work on if it's
   not obvious — he decides priorities.

---

## What NOT to do

- Don't refactor for hypothetical future requirements or add features Saiful didn't ask for.
- Don't add comments explaining what code does; don't write tests that test the framework.
- Don't introduce new dependencies without flagging.
- Don't proactively run destructive commands (force push, reset hard, etc.).
- Don't bypass the safety floor design in Brief Your Agent (PM mandate enforcement is
  uncoachable — structural, not prompt-only).
- Don't ship a behaviour change without a CR/Defect ID (exempt: version bumps, docs-only).
- Don't edit `.claude/commands/` or `~/.claude/` from a Kimi session unless meant for both
  tracks — keep the Kimi copies in `.agents/skills/` / `~/.kimi-code/skills/` in sync instead.
- Don't delete files outside the project folder.

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves
fast and decides quickly. Don't over-explain, don't ask for confirmation he didn't ask for,
don't summarize what you just did unless he asks.

---

## Autonomy + continuity

- **Inside this project folder, execute autonomously** — commit with the pathspec rule; don't
  ask "ready to commit?".
- **Continuity = checkpoint memos (CR097).** Stamp the identity line (above), pathspec-commit
  only your own timestamped memo file. No shared `LATEST` pointer — cold start selects at read
  time by identity marker. Don't auto-trigger a wrap on a context heuristic — Saiful decides.
- **Multi-agent work rides CR052 orchestration:**
  [`orchestration/dispatch/DISPATCH_PROTOCOL.md`](orchestration/dispatch/DISPATCH_PROTOCOL.md).
- **Security:** secrets stay out of git (only `*.env.example` shapes are committed);
  `infra/alpha.env` on the Mac is the source of truth for melehost; `/v1/admin/*` uses a static
  bearer; RevenueCat webhooks fail closed. Detail: [`CLAUDE.md`](CLAUDE.md) + [`infra/`](infra/).
