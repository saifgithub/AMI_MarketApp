# CLAUDE.md — Project guide for Claude Code sessions

Loaded into every Claude Code session in this project. High-level orientation, behaviour-critical rules, and pointers. Detail lives under `docs/`.

---

## What this project is

**AMI Trade** is a mobile-first, simulation-only AI trading-education app where the user is the CEO of a 12-agent analyst team. Built on the [TradingAgents](https://github.com/TauricResearch/TradingAgents) multi-agent LLM framework and the AMI "Hex-Reinforced Precision" design language.

Full spec under [`docs/`](docs/). Start with [`docs/initial_specs/00_overview/`](docs/initial_specs/00_overview/) and [`docs/initial_specs/01_product/core_loop_and_features.md`](docs/initial_specs/01_product/core_loop_and_features.md).

---

## Team reality

One founder (Saiful) + Claude. No engineers, no QA, no separate designer.

- **Sequential work.** One thing happens at a time.
- **Managed services over custom infra.** Supabase + RevenueCat + Cloudflare > rolling our own.
- **Quality bar:** "good enough to learn from real users." Stealth alpha first.
- **Saiful is the human-in-the-loop.** He reviews content, makes decisions, tests on devices, opens dev accounts, talks to lawyers. Don't ask him to do code.
- **Translation is not blocking.** Produce structured i18n string files with context comments; Saiful arranges translation externally.

Full split: [`docs/initial_specs/10_delivery/you_do_i_do.md`](docs/initial_specs/10_delivery/you_do_i_do.md).

---

## External dependencies (read-only mounts)

| Mount | Purpose |
|---|---|
| `/Volumes/Extreme Pro/AMI AI Design System/` | AMI hex design system. Tokens, fonts, components. |
| `/Volumes/Extreme Pro/TradingAgent/` | TradingAgents multi-agent framework — **the fork basis. Frozen at `7e9e7b8` (2026-05-01). Never fetch, never pull.** It answers "what did we fork from", and that answer must not move. |
| `/Volumes/Extreme Pro/TradingAgent_upstream/` | The same repo **tracking upstream `main`** (CR167). Refresh with `git -C … pull --ff-only`. Use this one for any "what changed upstream" question — `7e9e7b8` is an ancestor of `main`, so it produces every fork-basis→HEAD diff on its own. |

Read-only — integrate against them, don't modify. We are **not** a code dependency on TradingAgents
(`backend/pyproject.toml:39` has the install commented out); our prompts are ours. Latest drift review:
[`docs/forward_planning/CR167_tradingagents_upstream_drift/`](docs/forward_planning/CR167_tradingagents_upstream_drift/).

---

## `Silent_Scout/` — deprecated and closed (AT:R55, 2026-07-12)

`Silent_Scout/` was an in-repo R&D workspace (LoRA fine-tuning research, on-device
voice research, UI feature-gap planning) kept isolated from production. Saiful closed
it: *"I want to close and deprecate silent scout. It's utility has come to an end."*
— GTM mode means research-before-build in a separate sandbox no longer fits; work goes
straight into the CR pipeline instead.

**The directory no longer exists.** Everything of value was migrated:

- Actionable designs (watchlist badge, sector allocation, price alerts, trailing
  stop, cost-basis lots, earnings/dividend fields, voice STT/TTS benchmark, the
  GB10/LoRA hardware decision, the News/Social analyst live-feed gap) → **CR023–CR032**
  in `docs/forward_planning/`, each with the original research preserved under its own
  `original_silent_scout_research/` subfolder.
- The rejected-features register → `docs/initial_specs/11_decisions/rejected_features_register.md`.
- Historical/stale-but-shipped content with no forward action (old holding-detail
  layout notes, two correctly-deferred Tier-3 features, the closure README) →
  `docs/archive/silent_scout_2026-07-12/`.

If a future session finds a reference to `Silent_Scout/` anywhere (old commit
messages, `history/` narratives, other CR docs), that's a historical mention of a now-
closed workspace — don't try to `cd` into it or treat it as live.

---

## Runtime state (read before assuming anything)

The system is **live** and serving today. Read this before assuming
the backend is on the Mac or that the LLM is mocked.

| Component | Where | Notes |
|---|---|---|
| **Mac** (this workstation) | Pure editor. **NO backend, NO database, NO Docker stack.** | Backend unit tests via `pytest backend/tests/unit/ -q` still work (sqlite tempfile fixture). Anything else goes through `/promote-to-alpha`. Don't start uvicorn or `docker compose up` on the Mac. |
| **Alpha backend** | `melehost` — Ubuntu Linux server, LAN `192.168.20.59`, SSH alias `melehost` | Stack: `ami_postgres` + `ami_redis` + `ami_api_alpha` + `ami_tunnel`, all in `~/ami_trade/` via Docker Compose. Code rsync'd from Mac via the promotion script. |
| **Public hostname** | `https://api-alpha.agenticmarketintel.ai` | Cloudflare Tunnel (token-mode connector running on melehost). TLS terminates at CF edge; backend doesn't open inbound ports. |
| **LLM provider** | **On-prem vLLM** at `http://192.168.20.74:8000` — separate Ubuntu host on the LAN | Serving `ami-llm` (`RedHatAI/Qwen3.6-35B-A3B-NVFP4`, 262k context — rebranded; verified 2026-07-23 from the host's own `/v1/models` `root` path). Gateway prefers `vllm > anthropic > mock`. Per-(plan, agent) tier routing in `app/services/tier_policy.py::pick_tier`. **Not Anthropic, not OpenAI, not mock — real LLM.** |
| **Market data** | Yahoo via `yfinance`, with deterministic mock-walk fallback | `USE_REAL_MARKET_DATA=true` in melehost's `.env`. |
| **Code transport** | rsync via [`/promote-to-alpha`](.claude/commands/promote-to-alpha.md) (slash command) | Deploy path to Alpha is **rsync-only** (melehost has no git remote; it doesn't pull from GitHub). Source *is* version-controlled on GitHub: `origin` → `github.com/saifgithub/AMI_MarketApp` (backup + multi-agent sync); push `main` there. GitHub is not a deploy path. |

Detail in [`docs/initial_specs/08_tech/hosting.md`](docs/initial_specs/08_tech/hosting.md) (melehost spec), [`docs/initial_specs/10_delivery/promotion_protocol.md`](docs/initial_specs/10_delivery/promotion_protocol.md) (how code ships), [`docs/initial_specs/08_tech/backend_modes.md`](docs/initial_specs/08_tech/backend_modes.md) (Flutter Alpha/Beta/Prod modes), and the freshest state in the newest checkpoint memo under [`.deliveryos/checkpoint_history/`](.deliveryos/checkpoint_history/) (the durable cold-start anchor — the `HANDOVER_*` docs were retired in CR097).

If a check fails (curl returns 502 / connect refused), debug from melehost — don't fall back to "let me start a backend on the Mac":

```bash
curl -s https://api-alpha.agenticmarketintel.ai/v1/health
ssh melehost "docker ps --filter 'name=ami_'"
ssh melehost "docker logs ami_api_alpha --tail 50"
```

---

## Decision pointers

| Topic | Locked decision |
|---|---|
| Endpoint of the journey | **Training simulator, simulation-only, forever.** AMI is not licensed to give investment advice; no brokerage integration ever. |
| Markets | **US equities at MVP.** GCC/Tadawul + Bursa later. |
| Languages | **EN at alpha, AR + MS at v1.0.** Pluggable i18n. |
| Platforms | **iOS + Android-GMS at alpha, Huawei AppGallery at v1.1.** |
| Tech stack | **Flutter** frontend, **Python (FastAPI)** backend, **GCP Cloud Run + Supabase**. |
| Design | **AMI "Hex-Reinforced Precision"** — see [`docs/initial_specs/05_design/ami_hex_in_flutter.md`](docs/initial_specs/05_design/ami_hex_in_flutter.md). |
| Brand voice | Confident, analyst-to-analyst, numbers > adjectives, no marketing puffery. |
| Pricing | Floor Pass (free, ads) / Trader $14.99 / Floor Manager $34.99 + credit packs. |
| Onboarding | **Anonymous-first.** Concierge runs a conversational interview; account claim at the end. |
| Brief Your Agent — safety floor | **PM mandate enforcement is uncoachable.** Hard floor in PM prompt + deterministic compliance check. (Feature renamed from "Coach Your Agent" in AT:R27; the conceptual term "uncoachable" stays as the safety-floor's resistance label.) |

Full decision log: [`docs/initial_specs/11_decisions/decision_log.md`](docs/initial_specs/11_decisions/decision_log.md).

---

## Conventions

Full style rules: [`docs/initial_specs/08_tech/coding_conventions.md`](docs/initial_specs/08_tech/coding_conventions.md).

Behaviour-critical rule that affects every session — **degrade loudly** (CR040):

- Any feature gated on config presence must fail **visibly**, never silently fall back. Adding an
  env-driven setting? Forward it in `docker-compose.yml`'s `api-alpha` block — `backend/tests/unit/test_config_compose_parity.py` fails the build otherwise. Twice now a shipped
  feature was dark for months for want of that one line (DEF038, DEF063).
- Before shipping a fallback, ask: *if this fires constantly and silently, what does the user end
  up believing?* DEF059 (LLM down → confident fake APPROVE) is what that question would have caught.
- **Prompt instructions are not controls.** Agents ignore even emphatic "never present this as
  real" ~70% of the time (CR038). If it must hold, make it structural.
- Recurring classes + their enforcing checks: [`docs/initial_specs/08_tech/failure_patterns.md`](docs/initial_specs/08_tech/failure_patterns.md). **This is the guards register — there is no second copy.** Second occurrence of anything ⇒ add an entry **with a guard**. House rule: an entry without an enforcing check is not done.
- **Third time, or a guard that failed twice ⇒ a Dilemma, not another point fix** (CR185): [`docs/dilemmas/DILEMMA_PROTOCOL.md`](docs/dilemmas/DILEMMA_PROTOCOL.md). Several agents solve it independently and blind, in their own subfolders, from a brief that deliberately carries **no** proposed solution. For when the *framing* is suspect, not the effort — a merely large problem is still a CR, a merely risky one is a CR with `GATE: independent`. First instance: [`ISS001_DB_INSERT_RACE`](docs/dilemmas/ISS001_DB_INSERT_RACE/).

Behaviour-critical rule that affects every session — **the AI is named AMI**:

- Code, route names, log keys, tests, internal docs → **LLM** is fine.
- Lesson content, agent prompts, error sentinels, app copy → **AMI** by name. Never say "the AI" anywhere a user might read.

Other essentials:

- File headers: every new file gets a docstring/library comment explaining what it is and why.
- Comments: default to none; write self-documenting code. Add comments only when the *why* is non-obvious.

---

## Change governance (CR / Defect)

Every change to this project is documented as a **CR** or a **Defect** (D-058). Two registers, both in `docs/`:

- **CR** — *planned change* (a feature, refactor, process/infra/content change). Register: [`docs/forward_planning/cr_list.md`](docs/forward_planning/cr_list.md). Each CR gets a folder `docs/forward_planning/CR###_<topic>/` holding its what/why/scope/acceptance doc.
- **Defect** — *fixing something broken vs. spec*. Register: [`docs/defect/def_list.md`](docs/defect/def_list.md). User-reported defects still flow in via `bug_reports` (melehost) → [`/fix-bugs`](.claude/commands/fix-bugs.md); the register is their processed record. Prompt-spotted defects get a `DEF###` too.

**The two registers are GENERATED — never hand-edit them (CR081).** `def_list.md` and `cr_list.md` are **generated artifacts** (like `board.md`), rebuilt from one row-file per item. **Never edit either `.md` table directly** — your edit is lost on the next regenerate, and hand-editing the shared table is exactly the sweep this fixes. To add or change an item:

- **Ask the Architect to mint the ID.** The Architect is the single ID-minter (`DEF###` / `CR###`, sequential, never reused) — one minter = no ID-collision race. Pre-triage items use a topic-slug handle until then; the `orchestration/dispatch/intake/` stub path still exists for that.
- **Write ONE row file — the item's *domain owner* does this, not the Architect.** `docs/defect/_registry/DEF###.row.md` or `docs/forward_planning/_registry/CR###.row.md`, holding that item's single markdown table row. One file per item = a disjoint write-path, so two tracks never collide. A web CR's row is written by `coder.web`, a backend DEF's by `coder.api`, etc. — the register is no longer an Architect chokepoint (it only mints the number, which is domain-agnostic).
- **Regenerate + pathspec-commit:** `python scripts/registers/gen_registers.py gen [def|cr|all]`, then `git commit -m "…" -- <your row file> <the regenerated .md>`.
- *Why:* each register *used to be* a single monolithic markdown table. When two tracks edited it on the shared `main` checkout, whoever committed second **swept the other's uncommitted rows into its own commit** — silently, wrong `(AT:…)` tag. This bit us 2026-07-24: an architect's DEF095/DEF096 laning landed inside an unrelated `AT:R59 DEF098` commit. One-file-per-item makes the collision structurally impossible (same disjoint-write-path guarantee the dispatch/audit handshakes rely on).
- **Corollary — commit with an explicit pathspec, never bare.** On the shared checkout, `git commit -m "…" -- <your files>`. Never bare `git commit`, `git commit -am`, or `git add -A` + commit — those stage-and-sweep whatever another track left dirty. (Message goes *before* `--`; git reads `-m` as a pathspec after it.)

Rules:

- **Auto-file, proceed.** Saiful's prompt IS the approval. When he asks for a change, assign the next `CR###`, create its folder + doc, then implement. No separate approval gate. (A Defect is filed the same way when you spot or are handed one.)
- **IDs** are zero-padded, sequential, never reused: `CR001…`, `DEF001…`.
- **Commit tag:** append `(AT:R<N> CR###)` or `(AT:R<N> DEF###)` to the summary. User-reported bug fixes keep `fix(bug:<short-id>): … (AT:R<N> DEF###)`.
- **Exempt** (plain `(AT:R<N>)`, no ID needed): version/build bumps, docs-only commits (incl. the post-RESTORE sm-checkpoint archive commit and governance-log commits).
- **Enforcement is convention-only** — self-enforce each session; there is no git hook or promotion gate. Full format in [`docs/initial_specs/08_tech/coding_conventions.md`](docs/initial_specs/08_tech/coding_conventions.md).
- **Optional independent-verification layer** for a risky CR/Defect: an architect (track R) + auditor (track U) handshake — see [`orchestration/audit/PROTOCOL.md`](orchestration/audit/PROTOCOL.md) + [`orchestration/audit/AMI_TRADE_BINDINGS.md`](orchestration/audit/AMI_TRADE_BINDINGS.md) (CR005). Not required per item — Saiful invokes it.

---

## What to do when you start a session

1. Read this file (already loaded).
2. **Daily CR/Defect review check (CR085).** If it's on/after 13:00 Asia/Riyadh (Saiful's
   timezone, UTC+3) and `docs/governance/daily_cr_def_review_log.md` has no `## YYYY-MM-DD`
   section for today yet, run [`/daily-cr-def-review`](.claude/commands/daily-cr-def-review.md)
   right in this session before anything else — ask Saiful about every `proposed` CR / `open`
   Defect one by one via `AskUserQuestion`, inline, live. This runs in whichever session
   Saiful opens first that day (not a separate cloud routine — he pushed back on being
   redirected to one, 2026-07-24). Skip silently if today's section already exists.
3. **For the freshest state**, select the newest checkpoint memo in [`.deliveryos/checkpoint_history/`](.deliveryos/checkpoint_history/) **that carries your own role/instance marker** (the CR097 cold-start anchor that replaced `HANDOVER_<track>.md`): `grep -l "ROLE: <your-role>" .deliveryos/checkpoint_history/*.md | sort | tail -1` (filenames are timestamp-prefixed, so lexical sort = chronological; use `INSTANCE: <your-id>` for a fleet instance). **Do NOT read the newest file blindly** — the folder interleaves every track's sessions (15+ session-ids keyed by opaque session-id), so `ls -t | head -1` returns some *other* role's memo. Selection is read-time by design — there is **no shared `LATEST` pointer** (that would be a write race; see "Autonomy + continuity rules"). If nothing carries your marker yet, fall back to `git log --oneline` + the registers (`docs/forward_planning/cr_list.md` / `docs/defect/def_list.md`) — authoritative and unambiguous. Always cross-check against `git log`: a stamped memo can predate later commits.
4. Skim [`docs/initial_specs/10_delivery/project_plan.md`](docs/initial_specs/10_delivery/project_plan.md) — the Alpha → Beta → MVP roadmap. Your task is almost always in there.
5. `git log --oneline` to verify the commit chain.
6. Find the topic-specific doc(s) in `docs/` for your task.
7. Ask Saiful what he wants to work on if it's not obvious. He decides priorities.

---

## What NOT to do

- Don't refactor for hypothetical future requirements.
- Don't add comments explaining what code does.
- Don't introduce new dependencies without flagging — the stack is intentionally lean.
- Don't try to be "helpful" by adding features Saiful didn't ask for.
- Don't write tests that test the framework; test our logic.
- Don't proactively run destructive commands (force push, reset hard, etc.).
- Don't bypass the safety floor design in Brief Your Agent.
- Don't ship a behaviour change without a CR or Defect ID (see Change governance). Exempt: version bumps, docs-only commits (incl. the sm-checkpoint archive commit).

---

## Tone with Saiful

Direct, terse, no fluff. Numbers and tradeoffs, not sales talk. Match his pace — he moves fast and decides quickly. Don't over-explain. Don't ask for confirmation he didn't ask for. Don't summarize what you just did unless he asks.

He calls Claude "buddy" sometimes. That's fine.

---

## Autonomy + continuity rules

- **Inside this project folder, execute autonomously.** Don't ask "ready to commit?" — just do it. (See `memory/feedback_workflow.md`.)
- **Continuity = the sm-checkpoint routine (CR097 retired `/handover` + `/start-fresh`).** To carry context across `/compact` and keep one session alive: `/sm-checkpoint` (SAVE) → tell Saiful to `/compact` → first message after compact is `/sm-checkpoint` (RESTORE). Running to compaction is fine — the memo is what carries context across it. When you SAVE, **open the memo with an identity line `TRACK: <letter> · ROLE: <name> · INSTANCE: <id-or-->`** so cold-start can find it by reading.
- **After a RESTORE, commit ONLY your own timestamped archive — no shared pointer file.** The skill archived the memo to `.deliveryos/checkpoint_history/<ts>_<session-id>.md` (a filename unique to your session — a disjoint write-path). Pathspec-commit exactly that one file: `git commit -m "chore(checkpoint): <role> memo (AT:<track><N>)" -- .deliveryos/checkpoint_history/<ts>_<session-id>.md`. **Do NOT maintain a `LATEST_<track>.md` (or any single shared pointer)** — every same-role session would overwrite it, and two committing concurrently race (the loser's pointer is swept). That is precisely the *shared mutable flag* the CR052 protocol forbids; keep every writer on a disjoint path.
- **Cold start selects at READ time, by your own identity — never "newest file".** The folder interleaves every track's sessions keyed by opaque session-id, so `ls -t | head -1` returns some other role's memo. You are launched as a specific role/instance, so pick the newest archive carrying your marker: `grep -l "ROLE: <your-role>" .deliveryos/checkpoint_history/*.md | sort | tail -1` (filenames are timestamp-prefixed, so lexical sort = chronological; use `INSTANCE: <your-id>` for a fleet instance). No shared file is written, so there is nothing to race. If nothing carries your marker yet, fall back to `git log --oneline` + the registers.
- The global `~/.claude/commands/sm-checkpoint.md` skill is deliberately **not** modified (it's user-global, shared across projects); the archive-commit is an AMI-Trade convention done here in-session, not by the skill. **Keep committing work + CR/DEF governance regardless of the continuity mechanism.** Don't auto-trigger a wrap on a context-budget heuristic — Saiful decides when to wrap.
- **Multi-agent work rides CR052 orchestration**, not session-swaps — see [`orchestration/dispatch/DISPATCH_PROTOCOL.md`](orchestration/dispatch/DISPATCH_PROTOCOL.md). Merged-lane worktrees are reaped there (§9), the job `/handover` used to do.
- **Never delete files outside the project folder.** Saiful's exact words: *"unless it is something you physically cannot do, just go ahead and do it. just dont go crazy and delete files outside of your project folders!"*
