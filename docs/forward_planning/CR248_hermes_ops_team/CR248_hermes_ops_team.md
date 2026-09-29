# CR248 — Hermes: one AI agent system, multiple ops personas

**Status:** proposed · **Opened:** 2026-09-30 · **Track:** (unassigned)
**Filed as:** sub-CR of [CR036](../CR036_go_to_market_plan/CR036_go_to_market_plan.md) /
[CR245](../CR245_beta_infra_1000_user_sizing/CR245_beta_infra_1000_user_sizing.md) —
Saiful's own label for this request is **CR036-R001**. Register ID stays a normal
sequential `CR248` per this repo's minting convention (no `CR###-R###` pattern exists
elsewhere); `CR036-R001` is kept here as his reference handle, not a second ID.

**Naming, resolved (Saiful, 2026-09-30):** "Hermes" is **one AI agent system that can
carry multiple personas** — not a naming collision to avoid. The melehost UAT-device
Hermes ([[project_hermes_uat_operator]] memory; harness at `.../AMI_MarketApps/appium/`,
reports at `.../hermes_folder/reports/appium/`) is **specific to melehost and not
involved with the six personas below** (Saiful, 2026-09-30: "the hermes installed on
melehost is specific to melehost, and not involved with the rest of the persona"). It's
kept in this doc purely as **a worked example of how we've used the Hermes concept
before** — one persona, one machine, one fixed job — not as an existing member of this
CR's team. The six roles below are a separate, new set of personas under the same
Hermes system.

---

## Why

Saiful, verbatim: *"I want to have a team of hermes agent to help run the app."* And,
resolving the naming question: *"'Hermes' is an AI agent system. it can have multiple
personas."* Six named personas requested:

1. Network engineer
2. System engineer
3. Application support
4. Customer support
5. Marketing
6. Social media

Team reality per `CLAUDE.md`: "One founder (Saiful) + Claude. No engineers, no QA, no
separate designer." Every one of these six functions is currently either unstaffed,
done ad hoc by Saiful, or partially covered by an existing but narrower CR (support KB
content, CR088; bug-report triage, track R). This CR is the planning ledger for
whether/how to stand up dedicated ongoing coverage for each persona — **not a decision
to build any of it yet.** Per CR245's own standing framing, this whole GTM/ops area is
still planning; nothing here is committed.

## Precedent: how we've used the Hermes concept before

Not one of this CR's six personas — **melehost's UAT-device operator is a separate,
prior Hermes instance, scoped only to that one machine, uninvolved with anything
below** (Saiful, 2026-09-30). Kept here as the one existing worked example of "a Hermes
persona doing a job," for shape/precedent only:

| Existing instance | What it does | Scope |
|---|---|---|
| **UAT/device operator** (melehost Appium harness, per [[project_hermes_uat_operator]]) | Installs new APKs, runs smoke/phase1/alpaca test suites on melehost's UAT device, writes run reports to `hermes_folder/reports/appium/`. Confirmed real and operating today. | **melehost only** — not a member of this CR's six-persona team, not sharing context/memory with it. |

## What exists today, per persona (checked against the repo, not assumed)

| Persona | Current coverage | Gap |
|---|---|---|
| **Network engineer** | Cloudflare Tunnel (token-mode connector) fronts melehost; DNS/TLS at CF edge. No monitoring/alerting beyond manual `curl .../v1/health`. | No on-call, no automated uptime/latency alerting, no incident process. |
| **System engineer** | melehost (Ubuntu, Docker Compose: postgres/redis/api_alpha/tunnel) run entirely by Saiful + Claude via `/promote-to-alpha`. Security review done (CR123/124, C3 fixed). | No patch cadence owner, no backup verification cadence, no capacity/scaling owner — this is exactly the gap CR245 §9–§11 (VPS/managed-hosting research) is trying to fill for Beta, but that's infra *sourcing*, not an ops *role*. |
| **Application support** | Bug reports flow via in-app sheet → `bug_reports` table → track R triage (`/bug-monitor`, scheduled + session-start fallback) → DEF filing. Real, but Claude-operated, not a distinct staffed function. | No triage of non-bug "how do I..." app usage questions; no SLA. |
| **Customer support** | CR088 (done): support KB content pass for a **never fully wired up** IMAP-polling auto-reply script (`support_kb/scripts/`, DEF104 — broken learning-loop path). No live email handling ever stood up. | The actual channel doesn't run today — content exists, automation doesn't. This is the biggest concrete gap of the six. |
| **Marketing** | `M` track exists in `.claude/session-config.yml` (label only, no sanity checks/bug list wired). CR036/CR245 carry messaging pillars, offer-activation calendar, store-compliance checklist as **content**, not an operating function. | No one executing campaigns, no channel ownership, no calendar cadence enforcement. |
| **Social media** | Nothing found in the repo — no track, no CR, no content pipeline. | Fully greenfield. |

## Scope (planning only — nothing below is decided)

For each of the 6 new personas, this CR should eventually answer, in order (per CR245's
own "fit is moot if the first question is no" pattern from the sales-outreach draft):

1. **What does "a Hermes persona doing this job" concretely mean here** — is it a
   Claude session with a defined track + standing brief (like track R/S today), a
   scheduled `/loop` job, a `Workflow` orchestration, or genuinely a human hire, wearing
   the Hermes identity for continuity? Not all six need the same answer, and the
   melehost UAT-device precedent (single-machine, single-job, no shared context with
   anything else) is one worked example of the shape, not a template to copy exactly.
2. **What's the trigger/cadence** — event-driven (a support email arrives), polled
   (health checks every N minutes), or scheduled (weekly social post)?
3. **What decisions require Saiful** — per `you_do_i_do.md`'s Tier 1/2/3 split, which
   of these six personas touch anything in Tier 1 (accounts, legal, sending real
   communications) vs. things Claude can draft-and-execute autonomously.
4. **What's the smallest real first slice** — CR088/DEF104 already show customer
   support has a half-built pipeline (KB content done, automation broken); that's
   probably the cheapest persona to actually stand up first, not the newest one.
5. **How the six new personas relate to each other under one Hermes identity** —
   shared memory/context across personas, or fully separate operating contexts that
   just share a name? Affects whether e.g. the customer-support persona can see what
   application support already knows about a user's bug report. (The melehost
   precedent doesn't inform this either way — it's a single-purpose instance with
   nothing else to share context with.)

## Explicitly NOT in scope for this CR

- Standing up any of the six personas yet — this is the ledger, not the build.
- Renaming "Hermes" — resolved, not a rename candidate (see above).
- Re-deciding CR245's platform/hosting questions (§9–§11) — network/system-engineer
  persona scope here is the **role/ops** question ("who watches this"), not the
  **infra** question ("what do we host on"), which stays CR245's.
- Live customer-support automation fixing DEF104 — that's a defect against existing
  (broken) scope, callable from here but not re-scoped here.

## Open questions for Saiful

1. Priority order across the six — customer support has the most existing
   half-finished groundwork (CR088 + DEF104); is that the one to stand up first, or is
   there a more urgent one (e.g. network/system engineer, given melehost is the single
   point of failure for all of Alpha)?
2. Real hire vs. Claude-operated track vs. scheduled job, per persona — same question
   as scope item 1 above, needs his call per persona rather than one blanket answer.

## Acceptance

Not yet defined — this CR stays `proposed` until Saiful answers the open questions
above and at least one role has a concrete standing-up plan.
