# CR076 — Terms of Service: Malaysia as governing law (§16, v4.0)

**Status:** done · **Raised:** 2026-07-23 · **Owner:** Claude (legal-review pass, AT:legal)
**Related:** CR068 (legal-docs hardening — first ToS pass, D-063) · CR064 (Competition Rules,
§15) · D-063, D-065

---

## 1. Why this exists

CR068 (same day) implemented Saiful's direction to drop the Terms' governing-law and
arbitration clauses entirely — *"No arbitration. No courts. Just make the user take all
responsibility..."* (D-063). Peer research done afterward found that among comparable apps,
**every one checked names some governing law even when it drops arbitration** (Anthropic,
Signal, DuckDuckGo pattern) — a total absence of governing law is the outlier, not the norm,
and can itself create forum uncertainty that cuts against AMI as the defendant. That finding
was surfaced to Saiful as an open question.

Saiful's answer: **"use malaysia as governing law."**

## 2. Decision

Add back a governing-law clause naming Malaysia — but read narrowly, since Saiful named only
"governing law," not "courts." His prior direction ("no courts") is preserved by design:

- **§16 is a bare choice-of-law clause.** It states Malaysian law governs the Terms and any
  dispute, and nothing else.
- It explicitly does **not** designate a court or venue, and explicitly does **not** constitute
  an arbitration agreement — both stated in the clause text itself, not left implicit.
- It does not touch §2/§3 (assumption-of-risk framing) or §14 (indemnification), which continue
  to do the primary risk-shifting work exactly as D-063 intended.

This is a **partial** reversal of D-063: the "no governing law at all" sub-decision is amended;
the "no arbitration, no named court" sub-decision stands unchanged. See D-065.

## 3. Scope

- **`legal/policies/terms_of_service.md`** — new §16 "Governing law", marked
  `[LAWYER REVIEW REQUIRED]` (an unpaired choice-of-law clause is workable but unusual; counsel
  should confirm it doesn't get read as implying Malaysian jurisdiction by default, and that it
  holds against consumers resident in more consumer-protective jurisdictions). Version bumped
  **v3.0 → v4.0** (material change — VERSIONING.md's own gate: "changes the governing law").
  Prior version archived to
  [`legal/history/terms_of_service/v3.0_2026-07-23.md`](../../../legal/history/terms_of_service/v3.0_2026-07-23.md).
- **`website/terms/index.html`** — mirrors §16, version bumped to 4.0. Prior version archived to
  `website/terms/v3/index.html` (self-canonical).
- **`website/sitemap.xml`** — added `/terms/v3/` archive entry.
- **`docs/initial_specs/09_compliance/legal_plan_ami_trade.md`** — "must-confirm-with-lawyer"
  item 1 (governing law) updated: no longer "resolved as omitted," now "resolved as Malaysia,
  bare choice-of-law, pending counsel confirmation." Item 2 (arbitration) is untouched — still
  resolved as omitted.
- **`docs/initial_specs/11_decisions/decision_log.md`** — new **D-065**, cross-referencing and
  partially amending D-063.

## 4. Out of scope

- No jurisdiction/venue clause (which court hears a dispute) — not asked for, and adding one
  would reopen the "no courts" position Saiful has not revisited.
- No arbitration clause — same reasoning.
- Competition Rules (`legal/policies/competition_rules.md`) — unchanged. Its own §13 already
  states the Competition inherits whatever the Terms provide; it needs no edit for this CR to
  take effect (§16 now applies to the Competition the same as everything else, automatically,
  through that existing inheritance clause).
- Not deployed (`deploy_ftp.py` not run) — same not-yet-published posture as CR068/CR064.

## 5. Acceptance

- §16 exists in both `terms_of_service.md` and `website/terms/index.html`, matching, version
  4.0, dated 23 July 2026.
- v3.0 is frozen and self-canonical at `legal/history/terms_of_service/v3.0_2026-07-23.md` and
  `website/terms/v3/index.html`.
- §16 is a pure choice-of-law clause — no court, no venue, no arbitration language anywhere in
  its text.
- `legal_plan_ami_trade.md`, `decision_log.md` (D-065), and `cr_list.md` all reflect the change.

## Verification

- Re-read `website/terms/index.html` end-to-end: balanced tags, `/terms/v3/` and `/terms/v2/`
  and `/terms/v1/` all linked from the version-history section, canonical URLs correct on both
  the live page and all three archives.
- Grep for "arbitrat" and "jurisdiction" and "venue" in §16's text — none present, confirming
  the clause stays bare as intended.
