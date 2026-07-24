# AMI Trade — Email Support KB

This is the **canonical, version-controlled** source for the email-support knowledge base
(CR088, 2026-07-24 — ownership moved from an ad hoc melehost directory into git). Track **S**
(Support) owns it; see `HANDOVER_S.md` at the repo root.

## Structure

- `kb/` — one file per topic, in the shape documented in `kb/KB_FORMAT.md`. Categories in use:
  `general`, `billing`, `account`, `technical`, `feature`, `concierge`, `agent`, `compliance`,
  `legal`, `known_issue`.
- `templates/` — email-reply structure/branding notes (reference only — no auto-send path exists
  today, see below).

## What's NOT here

`scripts/` (the melehost IMAP-polling processor + KB-ingestion script) is **deliberately not
copied into git** — it has a hardcoded plaintext mailbox credential and a broken learning-loop
path (filed as **DEF104**, open). It stays melehost-only until that's fixed properly. Neither
script is cron-scheduled today, and `ami_support.py` only drafts JSON for human review — nothing
auto-sends yet.

## How this KB is meant to be used today

This is a **one-time content take-over and audit**, not a live automated pipeline (CR088 scope,
decided with Saiful 2026-07-24). In practice: a human (or Claude, reading this KB) drafts replies
to `support.ai@agenticmarketintel.ai` manually, grounded in these files. Standing up live
Gmail-based monitoring/drafting is a separate, not-yet-made decision.

## Content rules

- **FAQ-topic claims** (pricing, availability, curriculum figures, the Sharia/halal stance) must
  stay consistent with `website_api/app/knowledge/faq.md` — that file is still the single source
  of truth for what's said publicly. Support-ops content that doesn't exist on the public site
  (troubleshooting, known-issue call-outs, account/billing mechanics) is additive, not divergent.
- **Verify against the live app/repo before publishing an instruction.** The 2026-07-24 audit
  found several claims in the inherited KB that described UI that doesn't exist (an in-app
  "forgot password" flow — there is no password; in-app subscription cancel/receipt buttons —
  no live purchases yet, DEF100; mute/promote agents — documented in `content/agents/concierge.md`
  but never shipped). Don't repeat that pattern — check the actual screen/endpoint, not just the
  spec doc, before writing an answer that gives steps.
- **Known-issue entries** (`known_issue_*.md`) carry the customer-facing answer plus an
  `**Internal note:**` referencing the tracking Defect. Never put the DEF number in text a
  customer would see — same provenance-is-internal-only pattern used for lesson content
  (`memory/feedback_bok_quality_ownership.md`).
- Sharia/halal, legal/privacy, and account/billing-specific questions are **never** auto-answered
  by any AI system in this product (CR038, structural — see `faq_answer.py`'s escalation
  pre-filter) — this KB grounds a *human* drafting a reply, it does not itself decide to
  auto-send anything.

## Maintenance

Review monthly. Re-verify any claim about a UI path or feature against the current app before
reusing it — screens change. Keep `faq_*.md` in sync with `website_api/app/knowledge/faq.md`.
