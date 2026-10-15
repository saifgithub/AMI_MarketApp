# CR200-R003 — Conversational admin agent (Dify) over the management console

**Date:** 2026-10-15 · **Status:** proposed · **Track:** AT:K1
**Parent:** CR200 (Management Console) — conversational layer, no new `/admin`
SPA tab. Grouped sub-CR per the CR200-R001/R002 convention.

**What this is:** the spec for putting a natural-language front end on
application administration. Dify (already running on minihost, v1.17.1,
`frontend-dify-*` compose stack) hosts an agent whose model is the AMI LLM
(on-prem vLLM). The agent's capability is a collection of **Dify tools,
each a thin HTTP wrapper over an existing `/v1/admin/*` endpoint**. Chat is
the input surface for *doing*; the existing `/admin` SPA stays the surface
for *seeing*.

**Filed from:** Saiful's ask (2026-10-15): *"use a simple front end like
Dify… create a collection of tools and skills specific for the application.
The problem I can think of is when we want to show something to the user —
what do you suggest?"* The display analysis and the Dify capability checks
(markdown tables, mermaid, images all render in Dify chat; minihost runs
1.17.1, past the CVE-2026-21866 mermaid-XSS fix) precede this doc in the
same session and are summarised in §3–§4.

---

## 1. The plane distinction (binding)

Application **administration** (running the live product: users, messages,
bugs, pushes, data, LLM behaviour) is what this CR covers. Development
**control** (`/promote-to-alpha`, rollback, migrations, git, deploys) is a
different plane and is **out of scope by definition** — no Dify tool may
trigger a promotion, a rollback, a migration, or any deploy-path command.
This is the same separation recorded in the CR200 session: the console
administers the app; the skills move the code.

## 2. What

An agent in Dify — "AMI Ops" — that Saiful talks to in plain language:

- *"How many active users this week?"* → markdown table in chat.
- *"Show me signups for the last 30 days."* → chart image in chat.
- *"Message everyone still on build < 0.1.0+92 to update."* → tool calls
  `/preview`, agent reports `→ N recipients`, asks for confirmation, and
  only then calls send.
- *"What's broken right now?"* → health overview + deep links into
  `/admin#health` for the visual version.

The tool collection is versioned in this repo (see §7), so the agent's
capabilities are code-reviewed and auditable like everything else.

## 3. Display strategy (the problem Saiful named)

Chat is a good input for *do this* and a poor surface for *show me this*.
The strategy, in priority order:

1. **Markdown tables** for small ad-hoc query answers (≤ ~10 rows). Dify
   renders GFM tables natively. Tool output is shaped by the tool, not
   left as raw JSON for the LLM to format.
2. **Chart image endpoint** (`GET /v1/admin/chart.svg?series=…&days=…`) for
   anything time-series or comparative. Rendered **server-side as SVG by a
   small hand-rolled renderer** — no new dependency (matplotlib/plotly
   deliberately rejected; the backend has neither and dependency-minimal is
   house posture). Dify renders image links in chat; the same endpoint is
   reusable anywhere.
3. **Mermaid** for diagrams the *LLM authors* — architecture sketches,
   flow explanations, status maps. Dify renders mermaid code blocks
   (capability verified; also the subject of CVE-2026-21866, fixed in
   Dify 1.11.2, minihost runs 1.17.1). Mermaid is for concepts, **never
   for data** — an LLM-drawn chart of real numbers is the DEF059 class
   (asserting unverified computed content), so data always comes via
   tool-returned tables/images, not model-generated diagram code.
4. **Deep links** for drill-down. Anything interactive (filtering, paging,
   per-row actions) returns a link into the existing `/admin` SPA view —
   no re-implementing rendering inside chat, and the SPA stays the
   single place where things are *shown*.

## 4. Dify capability baseline (verified 2026-10-15)

1. Markdown + GFM tables render in chat (react-markdown + remark-gfm).
2. Mermaid code blocks render as live diagrams.
3. Image links render (enables the chart endpoint).
4. Dify tools support OpenAPI-schema HTTP tools against LAN endpoints —
   the `/v1/admin/*` surface qualifies.
5. minihost instance: Dify 1.17.1 (`langgenius/dify-api:1.17.1`,
   `dify-web:1.17.1`) — past the mermaid-XSS fix.

## 5. Design

### 5.1 Tools are glue, never logic

Every tool is an HTTP call to an existing admin endpoint plus response
shaping. **No new business logic, no new write paths.** The backend's
guards apply unchanged because the tools traverse the same routes:

- `get_admin` gating (`api/admin.py:80`) — ADMIN_SECRET bearer initially;
  Cloudflare Access service token later (CR200 `cf_access_checklist.md`
  phase B pattern).
- Every admin write records an `admin_audit` row
  (`services/admin_audit.py`) — the operator is named because the tool
  sends a fixed `X-Admin-Operator` header set at Dify config time (e.g.
  `dify-agent`), so actions via chat are attributable, not anonymous.
- CR102's structural preview-before-send applies to messages/push:
  the **tool** enforces nothing new — but the agent's instructions
  (versioned, §7) mandate preview → show count → explicit confirmation →
  send, and the endpoint semantics (0-recipient abort, payload-equality
  where relevant) remain server-side.

**No endpoint may be built that bypasses the audit trail to be
"easier from chat".** A tool that needs a backend capability the API
doesn't have files its own CR instead of reaching around it.

### 5.2 Tool surface — slice 1 (read-only)

1. `user_search` — `GET /v1/admin/users` → top-10 markdown table + deep link.
2. `user_detail` — `GET /v1/admin/users/{id}` → key/value summary + link.
3. `health_overview` — `GET /v1/admin/overview` + `GET /v1/admin/config-check`
   → one-screen text summary + `/admin#health` link.
4. `analytics_summary` — existing analytics endpoints → headline numbers.
5. `chart` — the new SVG endpoint; tool wraps it into an image link.
6. `bug_list` — list/claim/resolve already exist over HTTP from CR200 slice 1;
   read-only in this slice.
7. `broadcasts_list` / `replies_list` — read-only.

### 5.3 Tool surface — slice 2 (actions, each with preview/confirm)

1. `message_preview` / `message_send` — CR102 flow verbatim.
2. `push_preview` / `push_send` — CR200 push console flow verbatim.
3. `bug_claim` / `bug_resolve` — CR200 slice-1 semantics (rowcount-guarded,
   409 on loss).
4. `user_plan_change` / `trial_grant` / `credits_adjust` /
   `suspend` / `reinstate` — single-user verbs; always echo the target
   user back for confirmation.

### 5.4 Backend delta

1. `GET /v1/admin/chart.svg` (`api/admin_chart.py`): series from the
   existing analytics service queries, hand-rolled SVG line/bar render,
   `get_admin`-gated, cacheable. Parameters: `series`, `days`, optional
   `format=svg`. This is the only new backend code in slice 1.
2. No migration, no new env vars, no compose change (LAN-direct HTTP to
   the alpha host, same posture as `scripts/messages.sh`).

### 5.5 Dify-side config (versioned in this repo)

1. `infra/dify/admin-agent/` — tool OpenAPI specs, agent instructions
   (system prompt), and setup notes. The agent instructions carry the
   house rules: AMI naming, confirmation-before-send, "tables and charts
   come from tools, never from your own arithmetic", link-out for
   drill-down.
2. Model endpoint: on-prem vLLM (same `http://192.168.20.74:8000` the
   gateway prefers) via Dify's OpenAI-compatible provider config.

### 5.6 What the agent must never do

1. Never fabricate numbers: any statistic comes from a tool result;
   the instruction text says so explicitly (structural rule, not
   prompt-only: tools are the only data source anyway).
2. Never send anything without a preview count + explicit confirmation
   in the same turn.
3. Never touch the dev-control plane (§1).
4. Never reach the DB directly; HTTP to the admin API only.

## 6. Acceptance

1. Slice 1 tools all execute LAN-direct against Alpha and return rendered
   tables/images in Dify chat (verified by walking the §5.2 list).
2. `chart.svg` renders a real series (e.g. 30-day signups) and is
   `get_admin`-gated (401 without bearer).
3. Every slice-2 send path shows preview count and refuses to proceed on
   0 recipients — behaviour inherited from the API, verified live once.
4. A send performed via the agent appears in `admin_audit` with operator
   `dify-agent`.
5. No new dependency lands in `backend/pyproject.toml`.
6. `pytest backend/tests/unit/ -q` green; chart endpoint has unit tests
   (shape, gating, empty-series → honest empty-state SVG, CR040: never a
   fake flat line).
7. Agent instruction file in-repo; a second person could rebuild the Dify
   app from `infra/dify/admin-agent/` alone.

## 7. Out of scope

1. Dev-control plane (§1) — no promote/rollback/migration/deploy tools,
   ever, in this CR's line.
2. CF Access service-token auth for tools (lands with CR200's existing
   checklist phase B; slice 1 uses ADMIN_SECRET over LAN).
3. User-facing surface — this agent is admin-only by construction
   (tools are all behind `get_admin`).
4. Interactive drill-down in chat (stays in the SPA).
5. Scheduled/autonomous agent runs — conversational, operator-driven only.

## 8. Build sequencing

1. Backend: `chart.svg` endpoint + tests (the only code delta in slice 1).
2. Tool specs for §5.2 read-only set; configure Dify app on minihost;
   wire vLLM provider.
3. Live walkthrough of slice 1 against Alpha.
4. Slice 2 action tools, one at a time, each exercised live with the
   preview/confirm guard demonstrated.
5. Document the runbook (`.agents/skills/` copy when stable) so the
   agent's rebuild path isn't tribal knowledge.
