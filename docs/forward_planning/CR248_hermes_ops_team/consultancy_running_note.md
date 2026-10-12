# Running note — AI ops team as a consultancy service

**Living document, append-only.** Started 2026-10-02 (AT:K6) after Saiful: "this may
be the start of a new 'product', where we can package it and deploy as a
consultancy." Nothing here is decided. Add dated entries; promote to a CR when the
shape stabilizes.

## What the product would be

"AI ops team in a box": Hermes Agent (open-source, MIT) + a persona pack
(watcher / admin / support personas + SOUL templates) + skills (self-service
routing, config admin, digests) + deploy/run tooling, installed on the client's own
host, driven from their WhatsApp/Telegram, administered by a Chief-of-Staff persona.
Our own minihost deployment is the dogfood demo.

## Evidence it works (today)

1. Four personas live 2+ days unattended: health-watch, stack-watch, KB-grounded
   support with 12h digests, CoS admin — all on a free on-prem model.
2. Self-service routing: a persona adds its own whatsapp groups conversationally.
3. Admin-from-chat: config changes with audit trail and a safety-tightened
   authorization rule (Saiful-only state changes).
4. Built with config + SOUL files, zero code — the "consultant deploys in an
   afternoon" story is credible.

## Reusable vs AMI-specific

5. Reusable (the product): persona patterns, SOUL structure, skills, digest/notes
   pattern, deferred-restart discipline, allowlist/routing model, ami-wa-route.
6. AMI-specific (stays home): support KB content, api-alpha checks, branding,
   ami-llm vLLM wiring (product needs a model-abstraction layer: client brings
   OpenAI/Anthropic/subscription keys).

## Packaging would need

7. Clean product repo (the "AMI-Team repo" question becomes the product repo).
8. Bootstrap script: install Hermes → deploy persona pack → pair channels → verify
   → hand over the CoS group.
9. Per-client config layer: numbers, groups, secrets — never in git.
10. Update path for upstream Hermes churn (we already hit vendored-file friction).
11. Support model: who doctors client fleets (buddy system — could be a retainer
    service: us, via Angelia-shaped access).

## Business shape (hypotheses, not decisions)

12. Install fee + monthly retainer for fleet administration (the video's second half
    priced exactly this shape: install → executive assistant → retainer).
13. Naming, IP, and liability: our persona pack is ours; Hermes is MIT (attribution);
    client data stays on client host (good story); who is liable when a persona
    misconfigures something (SOUL-level rules are prompt-level — the structural
    guarantee question matters for clients, same CR040 reasoning as home).
14. Conflict check with AMI Trade the company: consultancy revenue vs focus on the
    app (CR036). Is this a second brand, a services arm, or not done at all?

## Open questions for Saiful

15. Does this get its own brand/repo now, or live as a section of CR248 until the
    first external client appears? **Update 2026-10-03:** Saiful frames the product
    as a packaged **"office assistant"** — deployable/developable offshoot. Today's
    email-channel work added a reusable component: persona-owned email support inbox
    (per-profile adapter + allow-all-with-DMARC + firewall pattern) — a standard
    office-assistant feature, now dogfooded.
16. First-client trigger: what event makes us build the bootstrap script — an
    actual prospect, or beta-launch spare capacity?
17. Do we productize the launch-team design doc (launch_ai_team_design.md) as the
    reference architecture for client deployments?

---
*Append new entries below with date + author tag.*

---
## 2026-10-12 (AT:K6) — Paperclip discovered (github.com/paperclipai/paperclip)

Open-source (MIT) Node.js+React **control plane for agent teams** — org charts,
ticket tasks with atomic checkout, heartbeats, budgets w/ hard stops, governance
gates, routines, secrets manager, skills+evals, multi-org, and **portable company
templates** (export/import orgs, secret-scrubbed). Adapters hire external agents
(Claude Code, Codex, CLI, any HTTP/webhook bot).

Impact on this note:
1. The packaging questions in sections 7–11 are largely answered features in
   Paperclip — the "AI office in a box" product can be Paperclip + our persona
   packs + deployment service rather than home-grown orchestration.
2. Complementary to Hermes: Paperclip has NO whatsapp surface and no on-prem
   model story — Hermes stays the customer-facing runtime; Paperclip can even
   orchestrate our personas via the webhook adapter.
3. Commoditized: org/task/approval plumbing. Still ours: whatsapp presence,
   KB/app-knowledge packs, AR/MS, deployment+administration as the service.
4. Next step when Saiful says go: `npx paperclipai test-drive` on minihost
   (Node 24+, outbound 443 already open; NOT on the Mac per standing rule).
   Then decide: adopt as the office orchestration layer vs stay Hermes-native.
