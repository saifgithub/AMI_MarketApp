# Draft — sales outreach email (managed VPS providers)

**Status: DRAFT ONLY. Not sent. Saiful sends outreach, never Claude — per standing
ownership rule in `docs/initial_specs/10_delivery/you_do_i_do.md`.**

Context: CR245 §11. Targets Cloudways and Elestio (both offer managed
security/backup/update services above raw VPS, per CR245 §11's comparison table).
One generic email, sendable to either vendor's sales team as-is — edit the bracketed
`[Vendor]` placeholder before sending. Leads with technical fit (does our stack even
run on your platform), then security/management specifics, then commercial terms —
per Saiful's direction: fit is moot if the answer to the first question is no.

Known gaps this email exists to close (from CR245 §11's own confidence flags):
- Cloudways: management claims confirmed from their own pages; Docker Compose
  multi-container fit and current pricing were NOT independently verified.
- Elestio: management claims confirmed; "one service = one VM" model may not map
  cleanly to a 3-container stack; real all-in multi-service price not itemized
  anywhere public.

---

**Subject: Hosting a multi-container Docker Compose app (FastAPI + Postgres + Redis) — fit and managed-security questions before we evaluate further**

Hi [Vendor] team,

We're evaluating managed hosting for a production backend and want to check fit before
going further. Some quick context, then our questions.

**What we're running:**
A Docker Compose stack with three services that need to run together on the same
host/network: a FastAPI application server, PostgreSQL, and Redis. Today it's ~2 vCPU /
2–4 GB RAM sized for a small user base, with a credible path to needing meaningfully
more compute if usage grows. We're a small team (no dedicated ops/security engineer),
which is why we're looking at managed options rather than a raw VPS.

**Questions on fit:**

1. Can your platform run an unmodified multi-container Docker Compose stack (app +
   Postgres + Redis, all networked together) as a single deployable unit? Or does your
   model require splitting each service onto its own instance/VM? If the latter, what
   does inter-service networking and latency look like across that split?
2. Do we retain SSH/shell access sufficient to run our own deploy tooling (we currently
   deploy via rsync + `docker compose up`), or is deployment restricted to a
   registry/CI-triggered flow on your platform?
3. What's the realistic minimum and a "comfortable headroom" spec (vCPU/RAM/disk) for
   the stack described above, and what does pricing look like at each?

**Questions on managed security/ops (the main reason we're asking you instead of a raw
VPS provider):**

4. What exactly is patched/updated automatically — OS-level packages, container base
   images, or both? What's the patch cadence, and is there a maintenance window we
   need to plan around?
5. What firewall/network protection is in place by default (e.g., is inbound access to
   Postgres/Redis blocked from the public internet unless we explicitly open it)?
6. Do you offer intrusion/threat detection (e.g., malicious-IP blocking, anomaly
   detection) as standard, or is that an add-on?
7. What's the backup model — frequency, retention period, and what does a restore
   actually involve (self-service vs. support ticket, and typical time-to-restore)?
8. If a security incident is detected on our instance, what's your notification SLA
   and what's expected of us vs. handled by you?

**Commercial:**

9. All-in monthly cost for the spec in Q3, including backups and the managed-security
   features in Q4–Q6 (not itemized separately if they're bundled — just want the real
   total).
10. Contract terms — month-to-month, or a minimum commitment?

Happy to hop on a call if that's faster than email. Appreciate the detail — we're
trying to make a real decision here, not just collect brochures.

Thanks,
[Name]
[Company]
