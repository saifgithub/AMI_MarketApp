# CR123 — Security-hardening program for beta/launch

> **Grouped (Saiful, 2026-07-31): CR123 + CR124 + CR125 move and get decided together**,
> not as three separate items — CR123 is the umbrella, CR124 (melehost/compose
> hardening) and CR125 (mobile secure session) are its two sub-CRs, already scoped
> "Under CR123" in their own docs.

## What

Umbrella CR for the deepened security review of 2026-07-30
([`docs/governance/security_review_2026-07-29.md`](../../governance/security_review_2026-07-29.md), v2).
Groups and sequences the remediation of every actionable finding into DEFs and two
sub-CRs, and holds the Medium/Low backlog until each item is scheduled.

## Why

Saiful asked for a critical re-review of the 2026-07-29 static assessment — his read was
that it "isn't deep and secure enough." The re-review resolved the original's open
questions against the **live** Alpha host and LAN, ran permitted non-mutating PoCs, and
found a cluster of issues the static pass missed — including a self-inflicted trap where the
original's own "rotate `SECRET_KEY`" remediations would silently brick Alpaca encryption
(N1). The threat model is **beta / public-launch readiness**, so weaknesses that are
tolerable at a 3-tester Alpha (non-expiring tokens, plaintext mobile storage, thin rate
limiting) are treated as blocking.

## Live-proven this session (not asserted)

- **C2** — `/v1/llm/*` reachable unauthenticated from the internet (no Cloudflare Access).
- **C3 (was H3)** — Postgres superuser `postgres`/`postgres` and no-auth Redis reachable
  from any LAN device; connected and read all 30 tables.
- **Q6** — no edge security headers (HSTS/CSP/…) on an auth host.

## Scope — child items

Same-day: **DEF176** (C1 account takeover), **DEF177** (C2 LLM proxy), **DEF178** (H7 leaked
Adanos key).
This week: **DEF179** (H1 mandate bypass), **DEF180** (H5 magic-link oracle + relay),
**DEF181** (H4/N5 audit leakage + attribution), **DEF182** (N1 secret reuse + fail-open
crypto), **DEF183** (N2 blocking-I/O DoS), **DEF184** (N3 body buffering + N4 rate limiter).
Before next promotion: **CR124** (melehost/compose hardening), **DEF185** (H2/M15 boot
hardening), **DEF186** (H6 LLM spend metering), **CR125** (mobile secure session, breaking).

Backlog tracked here, minted as DEFs when worked: M1–M4, M6–M7, M10–M12 + the Low/Info list
(edge headers, `/docs` exposure, admin `localStorage`/`innerHTML`, unsalted SHA-256 magic
codes, PII in audit, `state`-less Alpaca OAuth, etc.).

## Acceptance

- Every child DEF/CR resolved or explicitly scheduled with an owner.
- Re-run the review's Q1–Q3/Q6 probes after the same-day + this-week waves; each must show
  closure (C2 → 401/403; LAN DB/Redis → refused; edge headers present).
- The deepened review doc reflects final state (severities, filed IDs) at program close.

## Out of scope

No application-code changes were made in the review sessions themselves — this CR only
files and sequences. Sharia/legal content and any Supabase-swap work are unrelated tracks.
