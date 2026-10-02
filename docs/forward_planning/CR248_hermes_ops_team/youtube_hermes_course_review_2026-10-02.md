# Hermes course review — "HERMES AGENT FULL COURSE 3 HOURS: Build & Sell (2026)"

**Source:** Samin Yasar · published 2026-07-10 · 182 min · ~297k views
(https://www.youtube.com/watch?v=8yE6G1Lup1s). Reviewed 2026-10-02 (AT:K6) against the
minihost Hermes deployment (see `test_install_minihost_2026-09-30.md`).

**Credibility note:** course/agency seller — Skool community, affiliate links in the
description (Composio, Multica, Blotato, Coinvest, Higgsfield, QuiverQuant). Two
videos welded together: a genuine Hermes deep-dive (chapters 1–~90 min) and a
build-and-sell-AI-systems pitch (the rest). Self-reported claims ("200+ businesses,
millions saved, Bloomberg") are unverified — ignored. The Hermes mechanics below are
checkable and were checked against our install and the shipped source where it
mattered.

## Bin 1 — transfers as-is (native Hermes features we have not switched on)

1. **Squads with a leader + delegation instructions** — a chief-of-staff profile
   delegating to specialists with written "when to use what" rules. Hermes-native
   (Bot Mode bots message each other; `delegate_task` toolset). We approximated this
   manually with routes + SOUL files; squads formalize it. Angelia = leader.
2. **Native kanban as the shared ops board** — the video uses third-party Multica
   (affiliate); Hermes ships its own SQLite kanban. Shared ops task board, Angelia as
   PM.
3. **Native email channel for customer support** — IMAP/SMTP platform plus a bundled
   agent-email skill with cron polling. Working path to the support inbox that CR088
   content was written for; replaces the never-wired DEF104 script. Biggest concrete
   find in the video for us.
4. **USER.md per persona** — dedicated principal-modeling file, distinct from
   SOUL.md. Angelia first.
5. **Morning ops briefing cron** — same shape as our 12h digest, daily: neteng +
   appsupport + digest-of-digests to the CoS group at 08:00 Riyadh.

## Bin 2 — transfers in shape only

6. **Honcho shared brain** — cross-agent memory with per-person peer cards; answers
   CR248 open question 5 (shared persona memory). Self-hostable but another server;
   today personas share files (KB, notes, changelog). Candidate as persona count
   grows.
7. **Per-persona model routing** (Codex-for-code / Claude-for-design in the video) —
   shape: a model slot per profile. We run one vLLM model; differentiate when beta
   adds endpoints (deep model for Angelia, cheap-fast for acks).
8. **Buddy system** (second agent as repair doctor) — we already operate this way:
   Kimi/Claude sessions doctor the fleet. Could formalize Angelia-as-doctor.
9. **MCP gateway (Composio)** — the shape (one authenticated tool gateway) is right
   *if* we ever connect workspace apps; we keep secrets off SaaS bridges, so shape
   noted, not adopted.

## Bin 3 — needs data/infra we don't have (or shouldn't take)

10. **Content-factory builds** (Instagram carousels, Blotato auto-posting, e-com ad
    factory, property kits) — his agency offer menu; the *shape* (one source asset →
    repurposed formats on a calendar, "repurpose octopus") feeds CR248's
    marketing/social-media personas. Needs real social accounts — greenfield.
11. **Trading/copy-trading builds** (QuiverQuant congress copy-trading) — NOT
    adoptable: real-trading mechanics conflict with AMI's simulation-only,
    advisory-only mandate.
12. iMessage/Photon, Telegram Topics — channel extras; irrelevant to our whatsapp
    setup.

## What we already ship (do not re-propose)

Profiles-as-personas, SOUL.md, cron routines with notepads, skills-from-procedures
(wa-route, hermes-admin), listen-all groups, the 12h CS digest, self-service group
routing, per-persona toolset gating, vLLM as sole model endpoint, multiplexed single
gateway. Ahead of the course's mid-tier material; the gap is Bin 1 items 1–3.

## Adopted / pending

- Pending decision recorded in the spike report: picks 1 (squads), 3 (email), 5
  (morning briefing) were recommended; awaiting Saiful's go.
