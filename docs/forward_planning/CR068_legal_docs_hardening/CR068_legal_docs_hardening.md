# CR068 — Dedicated `legal/` home for the legal documents; T&C hardened against "AI gave bad advice" claims

**Status:** done
**Round:** AT:legal
**Owner:** Claude (legal-review pass)
**Trigger:** Saiful, 2026-07-23 — *"AT: Legal. You are My legal team. Get familiar with the terms and conditions and the privacy policy... The one item we must absolutely secure ourself against is from users who may felt that our LLM gave bad advice... Google makes us offer a screen to have the customer request for data deletion... create a separate folder to keep the legal documents (Call it legal...). Update the T&C."*

---

## 1. Why this exists

A legal review of the live Terms of Service and Privacy Policy, focused on the single risk
Saiful named: users claiming the AMI LLM "gave bad advice." Research (see D-063 in
`decision_log.md`) found the live ToS had **no arbitration clause and no indemnification
clause at all** — both were blank `[LAWYER PLACEHOLDER]` gaps in the underlying draft markdown
that had never been resolved, while other jurisdiction-sensitive clauses (liability cap,
governing law) had already been published without counsel review. It also found the Privacy
Policy stating prompts "are not sent to any third-party AI vendor," an absolute claim
contradicted by the documented Anthropic fallback and sub-processor list in
`disclaimers_and_privacy.md` — filed separately as [DEF085](../../defect/DEF085_privacy_ai_vendor_claim/DEF085_privacy_ai_vendor_claim.md).

Separately, `docs/initial_specs/09_compliance/` already held draft `terms_of_service.md` /
`privacy_policy.md` / `VERSIONING.md` — effectively what Saiful was asking for, just nested
under `docs/initial_specs/` instead of being a dedicated top-level folder.

## 2. Decisions (locked with Saiful, 2026-07-23, via AskUserQuestion)

| # | Question | Decision |
|---|---|---|
| 1 | Relationship between the new `legal/` folder and the existing `docs/initial_specs/09_compliance/` drafts | **Split**: the actual documents (+ versioning + history) move to `legal/`; research/planning material stays in `09_compliance/` with a pointer |
| 2 | Legal entity name for the T&C | Keep placeholder "AMI" / Malaysia-founder framing — no entity is incorporated yet |
| 3 | Privacy Policy's inaccurate third-party-AI-vendor claim | Fix in this pass, but **generically** — "a third-party AI infrastructure provider," never naming a specific vendor |
| 4 | Missing arbitration + indemnification clauses | Add both now, founder-drafted, modeled on peer patterns already in `legal_samples.md`, marked pending formal counsel review |

## 3. Scope

**A. New `legal/` folder** (repo root) — `README.md`, `VERSIONING.md` (moved from
`09_compliance/`, paths updated), `policies/{terms_of_service,privacy_policy,data_deletion_policy}.md`
(first two moved + updated via `git mv`, third new), `history/{terms_of_service,privacy_policy}/v1.0_2026-05-18.md`
(frozen pre-edit snapshots).

**B. Terms of Service v1.0 → v2.0** — strengthened §2 (no-fiduciary/no-recommendation
sentence) and §3 (assumption-of-risk + "mandate-compliance checks are not a guarantee"
sentence, deliberately not over-promising the "uncoachable" safety floor given DEF061's
enforcement gaps); filled the previously-blank §13.1 (arbitration — individual, AIAC Kuala
Lumpur, class-action waiver, 30-day opt-out) and §15 (indemnification — narrowed scope, with
carve-outs for AMI's own misconduct and non-waivable consumer rights); renamed "Coach Your
Agent" → "Brief Your Agent" in the live HTML (markdown source was already current).

**C. Privacy Policy v1.0 → v2.0** — corrected §7/§8's AI-infrastructure disclosure from an
absolute "never third-party" claim to an accurate self-hosted-primary /
contracted-fallback description, generic on vendor identity; added a direct link to the new
Data Deletion Policy in §12; same "Coach Your Agent" → "Brief Your Agent" rename.

**D. Data Deletion Policy v1.0 (new)** — markdown source extracted from the already-live
`website/ami-trade/sad-to-see-you-go/index.html`; the HTML page gained the version-tracking
apparatus (meta tags, visible version line, "Version history" section) it was previously
missing, matching `/terms/` and `/privacy/`. No changes to the live form, Turnstile
integration, or `/data-request` backend call. This page is what satisfies Google Play's
requirement for a public, web-accessible account/data-deletion request page (Android + iOS) —
`store_compliance.md` now documents this explicitly (was an undocumented gap).

**E. Versioning mechanics** — per the pre-existing `VERSIONING.md` playbook: archived the
prior v1.0 HTML to `/terms/v1/` and `/privacy/v1/` (canonical self-referencing), bumped
`sitemap.xml`.

**F. Housekeeping** — `docs/initial_specs/09_compliance/README.md` repointed to `legal/`;
`legal_plan_ami_trade.md`'s "must-confirm-with-lawyer" list updated to note starter language
now exists for arbitration/indemnity; one stale cross-reference fixed in passing
(`decision_log.md` D-060 pointed at a `07_legal/` path that no longer exists).

## 4. Out of scope

- §2's securities-regulator framing (SEC/FCA/MAS/SC Malaysia simultaneous wording) — still
  flagged `[LAWYER REVIEW REQUIRED]`, untouched.
- No age-verification gate added (the 18+ policy has no technical enforcement) — a
  product/eng gap, not a doc-content gap; would need its own CR/Defect if pursued.
- No production deploy (`website/deploy_ftp.py`) run as part of this CR — publishing binding
  legal terms to real users is a separate, explicit step for Saiful once he's reviewed the
  wording.
- No change to the live deletion form's fields, Turnstile widget, or backend contract.

## 5. Acceptance

- `legal/` exists with the structure above; `docs/initial_specs/09_compliance/` no longer
  claims to hold the canonical documents.
- `website/terms/index.html` and `website/privacy/index.html` are v2.0, contain the new
  clauses, and their v1.0 predecessors are frozen and self-canonical at `/terms/v1/` /
  `/privacy/v1/`.
- `website/ami-trade/sad-to-see-you-go/index.html` carries version metadata and a version
  history section; its live form is untouched.
- `sitemap.xml`, `decision_log.md` (D-063 + D-060 fix), `cr_list.md`, and `def_list.md`
  (DEF085) all reflect the change.
