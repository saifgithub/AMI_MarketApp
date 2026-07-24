# CR088 — Take over + enhance the email support knowledge base

**Status:** done · **Opened:** 2026-07-24 · **Track:** S1
**Owner:** Claude (Support KB Manager). Saiful reviews sensitive draft language (mandate-filter
question) and decides whether/when to sync the improved content back to melehost.

---

## Why

The alpha production team built an ad hoc email-support KB at
`saiful@melehost:/home/saiful/hermes_folder/project/AMI_MarketApps/support_kb/` to ground a
(never fully wired up) IMAP-polling auto-reply script. It was never in git, never audited against
what the app actually does, and diverged from the app in a few places customers would actually
notice. Saiful asked Claude to take ownership: bring it under version control, audit it, and fix
the gaps — as a one-time content pass for now (standing up live email handling is a separate,
future decision).

## Decisions (locked with Saiful, 2026-07-24, via `AskUserQuestion`)

| Question | Decision |
|---|---|
| Ongoing scope | One-time content pass. Not standing up Gmail-monitored live reply drafting yet. |
| `scripts/` (hardcoded plaintext credential + broken learning-loop path — see DEF104) | Content only. `scripts/` stays on melehost untouched; the automation bug is a separate defect. |
| Internal KB vs. public website FAQ (`website_api/app/knowledge/faq.md`) | FAQ-topic claims (pricing, availability, curriculum figures, Sharia/halal stance) stay mirrored — no divergence on what's *said*. Support-ops content that doesn't exist on the public site (troubleshooting, known-issue call-outs, bug-report-vs-email routing) is additive. |
| Governance | Stand up a new **S** (Support) track in `.claude/session-config.yml` first. |

## What was audited

`support_kb/kb/` (17 files) — 11 `faq_*.md` mirrors of the website FAQ + 5 `concierge_*.md`
mirrors of `content/agents/concierge.md`, both re-checked against the live repo (342 EN lessons,
exact 13-track breakdown, 208 glossary terms all measured fresh; Sharia/halal wording checked
against `faq_answer.py`'s escalation policy) — **no drift found**, copied as-is. Two legacy
monolithic docs, `support_faq.txt` and `troubleshooting.txt`, predate the documented
`KB_FORMAT.md` per-entry shape and cover topics (billing, account, technical) the atomized set
didn't have — atomized and merged in. `support_kb/templates/` (2 files) copied as reference.
`support_kb/scripts/` and the empty `learned/` were **not** copied (see DEF104).

## Scope

### A. Content migration + normalization
- New `content/support_kb/` — `README.md`, `kb/` (all entries in `KB_FORMAT.md` shape), `templates/`.
- `support_faq.txt` / `troubleshooting.txt` atomized into individual per-topic files, deduped
  against the existing atomized set.

### B. Content gaps closed
- **Bug report vs. email support** — the app has *no* in-app path to `support.ai@` at all (only
  the bug-report sheet → `bug_reports`, a separate channel); new entry routes correctly.
- **DEF100** (no live purchase yet) — honest, non-committal "not purchasable during alpha" entry.
- **DEF103** (AR lesson fallback) — general "why English in Arabic mode" entry, no ticket numbers
  exposed to the customer.
- **DEF078/101/102** (lesson-accuracy work in flight) — "my quiz answer looks wrong" entry that
  asks for the lesson code rather than dismissing the report.
- **DEF061** (mandate filters not fully enforced) — drafted conservatively, flagged for Saiful's
  review given sensitivity before it's ever used to answer a real customer.
- Stale `info@agenticmarketintel.com` line dropped (unverifiable anywhere else in the repo since
  CR049's footer fix); everything routes through `support.ai@agenticmarketintel.ai`.
- Keyword lists enriched using `website_api/app/services/faq_answer.py`'s existing
  `_ADVICE_RE`/`_ACCOUNT_RE`/`_COMPLIANCE_RE`/`_LEGAL_RE` trigger vocabulary.

### C. Governance
- New track **S** (Support) in `.claude/session-config.yml`, `HANDOVER_S.md` written.
- **DEF104** filed separately for the plaintext credential + broken `kb_ingest.py` path — not
  fixed in this CR (content-only scope).

## Out of scope

- Fixing/wiring `ami_support.py` / `kb_ingest.py` on melehost (DEF104).
- Reviving the IMAP polling cron or the auto-send path.
- Gmail-MCP-based live email handling.
- Any change to `website_api/app/knowledge/faq.md` or CR049 code.

## Acceptance

- `content/support_kb/kb/*.md` all match `KB_FORMAT.md`'s shape.
- Measured facts (lesson count, track breakdown, glossary count) in the copied curriculum entry
  match the live repo at commit time.
- `python scripts/registers/gen_registers.py gen all` + `verify` clean; only CR088 + DEF104 rows
  added.
- `git status` clean tree; commits tagged `(AT:S1 CR088)` / `(AT:S1 DEF104)`.
- melehost's `support_kb/kb/` + `templates/` refreshed via rsync from the git-tracked copy
  (`scripts/`/`learned/` untouched).
