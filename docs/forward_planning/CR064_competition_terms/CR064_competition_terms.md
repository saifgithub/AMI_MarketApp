# CR064 — Competition terms & conditions (reputation, streaks, weekly leagues)

**Status:** proposed · **Raised:** 2026-07-23 (AT:R65) · **Owner:** Claude drafts → **Saiful's
lawyer reviews and signs off** (per `docs/initial_specs/10_delivery/you_do_i_do.md`)
**Related:** CR063 (in-app delivery) · CR068 (legal-docs hardening — **read first**) ·
CR004 / D-060 · CR049 (data-request flow) · CR065

> **Builds on CR068 — [`CR068_legal_docs_hardening/`](../CR068_legal_docs_hardening/)
> (`AT:legal`, done 2026-07-23).** Its numeric ID churned while both CRs were being filed the
> same day; trust the folder name if the number ever disagrees. That CR moved the canonical legal
> markdown out of `docs/initial_specs/09_compliance/` into a new top-level **`legal/`**
> folder, bumped Terms to **v2.0**, and filled the previously-blank §13.1 arbitration and
> §15 indemnification clauses. This CR targets that new structure and must obey
> [`legal/VERSIONING.md`](../../../legal/VERSIONING.md).

---

## What / Why

AMI Trade operates a **live competition** — weekly reputation leagues with points, streaks,
promotion/relegation, a public leaderboard, and **credits awarded at streak milestones**.

`legal/policies/terms_of_service.md (v2.0)` has **15 sections and mentions none
of it.** No competition terms exist anywhere: not the scoring, not the leaderboard
publication of a user handle, not the anti-cheat/disqualification right, not the fact that a
streak milestone hands the user a *purchasable in-app currency*.

We are running a scored, publicly-ranked, currency-awarding competition with **zero governing
terms**. This CR closes that gap before the alpha widens.

---

## Structure (decided 2026-07-23)

A **standalone Competition Rules document**, incorporated **by reference** from a short new
ToS section — not the full text inside the ToS.

| Artefact | Path |
|---|---|
| Canonical source | `legal/policies/competition_rules.md` (new — joins the three existing policies) |
| Published page | `website/competition-rules/index.html` (new — mirror the `website/terms/` + `website/privacy/` pattern) |
| ToS hook | new **§16** "Reputation, streaks and weekly leagues" in `legal/policies/terms_of_service.md`, incorporating the standalone rules by reference (§16 is the next free number — the doc currently ends at §15) |
| ToS published mirror | `website/terms/index.html` |
| Archived ToS v2.0 | `legal/history/terms_of_service/v2.0_2026-07-23.md` + `website/terms/v2/index.html` |
| In-app route | linked from CR063's rules screen via the existing `LegalScreen` WebView |
| Governance | add `competition_rules.md` to `legal/VERSIONING.md`'s governed set and `legal/README.md` |

**Why standalone:** contest rules are conventionally a separate instrument, they are easier
for a lawyer to review in isolation, and — decisively — **scoring will be tuned**. A
standalone document can be re-versioned when a point value changes without re-issuing the
whole ToS and forcing global re-acceptance.

Use the established `[LAWYER REVIEW REQUIRED]` / `[LAWYER PLACEHOLDER]` markers already used
throughout `terms_of_service.md`, and add every flagged item to that file's lawyer-only
checklist.

### Versioning obligation — this is a material change

Adding §16 introduces **new clauses**, which `legal/VERSIONING.md` classifies as a **Major**
bump. Therefore this CR must:

1. Bump Terms **v2.0 → v3.0** with a new effective date, in **both** the markdown source and
   the published HTML's `<meta name="document-version">` / `document-effective-date`
   (VERSIONING.md requires they match and be bumped in the same commit).
2. Archive the outgoing v2.0 to `legal/history/terms_of_service/v2.0_2026-07-23.md` and
   `website/terms/v2/index.html`.
3. Add a "Version history" row and honour the **14-day user-notice rule** that a major bump
   triggers under ToS §14. **Plan the notice — this is not a silent publish.**
4. Ship `competition_rules.md` at **v1.0** with the same version header, meta tags and
   version-history apparatus as the other three policies.
5. Deploy via `deploy_ftp.py` with a `?v=` cache-bust — **gated on Saiful's wording review**,
   consistent with how CR068 left the Terms/Privacy v2.0 deploy pending.

---

## The rules of the game (code-truth, 2026-07-23 — the operative text)

Verified against `backend/app/services/reputation_service.py`,
`backend/app/services/league_service.py`, `backend/app/core/config.py`, and the live melehost
config. **These terms must describe what the code actually does** — see CR065 for the
spec's unbuilt promises, which must NOT appear here.

### Scoring

| Action | Points |
|---|---|
| Daily challenge attempted | +2 |
| Daily challenge correct | +3 (→ 5 total for a right answer) |
| Lesson passed | +5 |
| Agent unlocked | +10 |
| Room convened to verdict | +3 |
| Disciplined trade | +2 (max **3/day**) |
| Reviewed trade | +3 (max **3/day**) |
| Streak 7 / 30 / 100 days | +10 / +25 / +50 |

### Limits and integrity

Global cap **25 points/day** in the user's own timezone · per-type daily limit of **3** on
the two repeatable trade events · ref-based dedup (re-passing a lesson or re-unlocking an
agent scores 0) · one attempt per daily challenge, re-attempts return the stored result ·
streak milestones fire once ever.

### Streaks

Consecutive days with any qualifying activity (daily challenge, lesson start/completion,
journal entry — journal captures room runs, trades, 1-on-1 chats, briefs) in the user's
timezone. Milestones at 7/30/100 days additionally grant **credits: 5 / 25 / 100**.

### Weekly league

Resets **Monday 00:00 UTC** · cohorts of **≤30** drawn from users active in the prior 7 days,
grouped by tier and randomly shuffled · ranked on points earned **that week only**, ties
broken by earlier join · **top 5 promote, bottom 5 relegate**, relegation only where the
cohort has **≥10** members · ladder **Apprentice → Analyst → Trader → Senior → Floor
Veteran**, cosmetic only with **no functional gating** · never competed → Apprentice.

### Identity

Pseudonymous `Adjective Noun` handle minted on first league contact, regenerable **exactly
once ever**; real name shown only where the user opted in (`users.show_display_name`).

### Eligibility

`LEAGUE_ELIGIBLE_PLANS` is empty ⇒ **all plans compete, including the free Floor Pass.**

### The hard rule

**Zero P&L, anywhere.** No points derive from trading profit or loss, by design.

---

## Special conditions — for lawyer sign-off

Ordered by exposure. Items 1–4 are the ones that decide the legal character of the feature.

### 1. ⚠ Streak milestones award credits — a currency with monetary value

**This is the sharpest exposure.** League *placement* pays nothing, but a streak milestone
grants **5 / 25 / 100 credits**, and credits are **purchasable** (ToS §6, credit packs). We
are therefore giving an item of real monetary value in exchange for sustained engagement.

Required drafting: characterise credits as a **promotional in-app currency** with **no cash
value**, **non-transferable**, **non-redeemable for cash**, **non-refundable**, forfeited on
account termination, earned by **engagement — never by wager, stake, or chance**, and
subject to change. `[LAWYER REVIEW REQUIRED]`

### 2. No purchase necessary — and the condition that keeps it true

All plans compete including the free tier, because `LEAGUE_ELIGIBLE_PLANS` is empty. This is
the principal reason the competition is not a paid-entry contest.

**Standing flag for the business:** the day leagues are restricted to paid plans (populating
`LEAGUE_ELIGIBLE_PLANS`), this becomes **paid entry into a prize-bearing competition** and
**requires legal re-review before shipping.** Record this as a condition, not a footnote —
it is a pricing decision that silently changes the legal character of the product.

### 3. Not gambling — and the declaration it must stay consistent with

No stake, no entry fee, no wagering, and no P&L-linked scoring.
`docs/initial_specs/09_compliance/store_compliance.md` answers the store age-rating
questionnaire **"Gambling content: No"** and **"Simulated gambling: No (we explicitly do not
gamify trading P&L)"**. Those answers become false the moment scoring touches P&L — so the
zero-P&L rule is a **compliance invariant, not a design preference**. State it as binding.

### 4. Skill versus chance

Points accrue deterministically from user actions (skill/effort). However **cohort assignment
is randomised** — `random.shuffle` in `LeagueService._assemble_week`. Lawyer to confirm that
random **matchmaking**, as distinct from random **prize determination**, is acceptable in
each target jurisdiction. `[LAWYER REVIEW REQUIRED]`

### 5. Eligibility, age, territory

17+ store age rating (financial themes) · minimum age and guardian consent · void where
prohibited. US equities at alpha; **Malaysia and GCC are roadmapped and both carry
gambling-adjacent regulatory scrutiny and Sharia considerations — obtain a Sharia/legal
ruling before enabling leagues in those markets.** `[LAWYER REVIEW REQUIRED]`

### 6. Anti-cheat and disqualification

Dedup, the 25/day global cap and the 3/day per-type limits are already enforced in code.
Reserve the right to void points, delist from leaderboards, suspend or terminate for
manipulation, automation, or multi-accounting.

**Flag:** anonymous-first onboarding (D-016) makes alt accounts trivial to create, and
`users.device_user_id` is the only weak correlating signal. The terms should not promise
detection we cannot deliver — reserve the right without warranting enforcement.

### 7. Publicity and privacy

The handle is published to the user's cohort by default; the real name appears only on
opt-in; one regeneration ever. The terms must state what happens to **leaderboard rows and
league history under a GDPR/CCPA erasure request** — this ties directly into CR049's
data-request flow and the 30-day SLA. `[LAWYER REVIEW REQUIRED]`

### 8. Right to modify, suspend, or reset

Reserve the right to change scoring values, caps, cohort size, tiers, or to suspend or cancel
a season — and state the notice given. Scoring **will** be tuned; the terms must anticipate it.

### 9. Simulation-only reaffirmation

The competition must never imply trading skill, profitability, or investment advice.
Standing at the top of a league means the user learned diligently — nothing more. Reaffirm
ToS §1–§4 explicitly inside the competition context.

### 10. Retention

State retention of the reputation ledger (`reputation_events`) and league history
(`league_members`).

### 11. Governing law, disputes, and indemnity

**Do not re-draft — inherit.** CR068 already filled these: §13.1 is founder-drafted individual
arbitration (AIAC Kuala Lumpur, class-action waiver, 30-day opt-out) and §15 is
indemnification, both marked `[LAWYER REVIEW REQUIRED]`. The competition rules must
**explicitly incorporate** them rather than restate or vary them — a competition-specific
dispute clause that diverges from §13.1 would create a conflict between two live documents.

Confirm with counsel that competition disputes (e.g. a voided score or a delisting) fall
inside the §13.1 arbitration scope and the §15 indemnity carve-outs. `[LAWYER REVIEW REQUIRED]`

---

## Out of scope

- Changing any rule. This CR **documents** the competition; CR063 explains it in-app; neither
  alters mechanics.
- The unbuilt spec items (365-day milestone, lifetime tiers, badges, streak freezes) —
  **deliberately excluded**, see CR065. Documenting a 500-credit reward users cannot earn
  would be a misrepresentation.

---

## Acceptance

1. `competition_rules.md` exists, carries the rules of the game exactly as above, and covers
   all 11 special conditions.
2. ToS §16 added, incorporating the standalone rules by reference; published mirrors updated
   at `website/terms/index.html` and `website/competition-rules/index.html`.
3. Every `[LAWYER REVIEW REQUIRED]` / `[LAWYER PLACEHOLDER]` item appears in the ToS
   lawyer-only checklist.
4. The in-app path from CR063's rules screen opens the published page in `LegalScreen`.
5. No statement in the document describes behaviour the code does not implement — verified
   line-by-line against `reputation_service.py` / `league_service.py` / `config.py`.
6. Website deploy carries a `?v=` cache-bust (CF caches 7 days).

## Verification

- Diff every factual claim in the drafted rules against the three source files.
- `curl` the published pages; confirm the in-app WebView loads both.
- Confirm the store-compliance answers in `store_compliance.md` remain consistent with §3.
