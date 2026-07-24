# Handover — Support (AT:S)

**Last updated:** 2026-07-24 (end of AT:S1 — **CR088**: took ownership of the email-support
knowledge base, moved it from an unversioned melehost directory into `content/support_kb/`,
audited every claim against the live repo/app, fixed several factually-wrong entries, added
entries for real gaps. Filed **DEF104** for a plaintext credential + broken script found along the
way, left unfixed by design.) Narratives in [`history/`](history/) — see "Recent sessions" below.

Read this file **first** in any new Support-track session (`/start-fresh S`). Per-session
narratives live in [`history/`](history/) — one file per `/handover S` wrap. This doc stays
narrative-free; current truth only.

---

## What's on disk + what's running

| | |
|---|---|
| Git state | This session's CR088/DEF104 work is committed on `main` as part of AT:S1 — check `git log --oneline -5` for the exact SHAs (a docs/content-only change set: `.claude/session-config.yml`, `docs/forward_planning/_registry/CR088.row.md` + regenerated `cr_list.md`, `docs/defect/_registry/DEF104.row.md` + regenerated `def_list.md`, `content/support_kb/**`, this file). |
| Scope of this track | Owns the email-support knowledge base (`content/support_kb/`) that grounds replies to `support.ai@agenticmarketintel.ai`. **Currently a manual/content-only operation** — no live email monitoring or auto-reply is wired up. Not a code-shipping track (content + light governance only). |
| KB location | `content/support_kb/` — `kb/` (37 topic files, see `kb/KB_FORMAT.md`), `templates/` (reference), `README.md` (content rules + what's deliberately not here). |
| What's NOT in git | `support_kb/scripts/` stays melehost-only — `ami_support.py` has a hardcoded plaintext IMAP/SMTP password, and `kb_ingest.py`'s learning loop points at a different, disconnected directory (`~/ami_support/*`), so it's never actually written a KB entry. Filed as **DEF104** (open), not fixed this session — scope was content-only per Saiful. |
| Relationship to CR049 | Separate system. The website Concierge/contact-form auto-answer (`website_api/app/services/faq_answer.py`) grounds itself in `website_api/app/knowledge/faq.md`, not this KB. This KB's `faq_*.md` files are mirrors of that file and must stay consistent with it on claims (pricing, availability, curriculum figures, Sharia/halal stance). |
| Audit findings this session | Three claims in the inherited KB described UI that doesn't exist and were corrected: (1) "forgot password" — the app has no password at all, sign-in is Apple/Google or a 6-digit email code (CR050); (2) in-app subscription cancel/receipt buttons — don't exist, and there's nothing to cancel yet since live purchases aren't provisioned (DEF100); (3) mute/promote individual agents — documented in `content/agents/concierge.md`'s scope but never shipped in `mobile/lib` or `backend/app`. All three now have corrected or honest-gap entries. |
| melehost sync | The improved `kb/` + `templates/` were rsynced back to melehost's `support_kb/` (content only — `scripts/`/`learned/` untouched) so the dormant pipeline starts from corrected content if it's ever revived. |

---

## Carry-overs

- **Operating model still undecided.** This was explicitly a one-time content pass (Saiful,
  `AskUserQuestion` 2026-07-24). Whether Support becomes a standing track that actively monitors
  `support.ai@` via the Gmail MCP connector and drafts real replies is a separate future decision
  — don't assume it without asking again.
- **DEF104 unfixed.** The plaintext credential in `ami_support.py` should be rotated and moved to
  an env var; `kb_ingest.py`'s `KB_DIR`/`LEARNED_DIR` should point at the real KB path (or the
  dead `~/ami_support` scaffold should be deleted). Neither script is cron-scheduled currently.
- **`known_issue_mandate_filter_question.md` needs Saiful's sign-off** before its draft wording is
  ever used to answer a real customer — flagged in the file itself.
- **No sanity checks / bug list configured yet** for this track in `.claude/session-config.yml` —
  add via `/session-setup` once there's an operating cadence worth checking (e.g. a live
  email-monitoring loop, if that's ever stood up).

---

## How to start the next session

`/start-fresh S` — session name to use: **AT:S2**

Recent sessions (newest first):
- AT:S1 — this session (CR088, DEF104). No narrative file yet; run `/handover S` to write one to
  `history/` when this session wraps.
