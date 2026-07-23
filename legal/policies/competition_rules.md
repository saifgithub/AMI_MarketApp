# Competition Rules — AMI Trade Reputation, Streaks & Weekly Leagues

> **DRAFT — pending lawyer review.** Not legally binding until reviewed and signed off by counsel. Capitalised terms not defined here have the meaning given in the [Terms of Service](terms_of_service.md) ("Terms").
>
> **Four items below are marked `[LAWYER REVIEW REQUIRED]`**: the credits-as-currency characterisation (§5), the leaderboard/GDPR-erasure interaction (§7), the skill-vs-chance framing of randomised cohort assignment (§8), and the Sharia/legal ruling gate on enabling leagues in Malaysia/GCC (§2). See the "Document status" section at the bottom for the full lawyer-only checklist.

**Version:** 1.0 (alpha)
**Effective:** 23 July 2026
**Contact:** legal@agenticmarketintel.ai
**Published HTML:** `website/competition-rules/index.html` → `https://www.agenticmarketintel.ai/competition-rules/`
**Publishing process:** see [`VERSIONING.md`](../VERSIONING.md)

---

## 0. Scope and incorporation

These Competition Rules govern AMI Trade's **reputation, streak, and weekly league features** (together, the "Competition"). They are incorporated by reference into the [Terms of Service](terms_of_service.md), clause 15. Using any part of the Competition means you agree to these Rules in addition to the Terms.

These Rules do **not** create a separate legal framework for the Competition. Clauses 1–4 (simulation-only, not advice, AI output can be wrong, hypothetical performance), 11 (limitation of liability), 12 (warranty disclaimer), and 14 (indemnification) of the Terms apply to the Competition exactly as they apply to the rest of AMI Trade. Where these Rules are silent, the Terms control.

**No purchase necessary to compete or to earn any Competition reward.** Every plan, including the free Floor Pass, is eligible to participate under the same rules (see §6).

> _Inspired by: standard sweepstakes/contest-rules incorporation pattern; novel in structure (standalone document, not embedded in the main Terms) because scoring is expected to be tuned and re-versioning a standalone document does not force a full Terms re-issue._

## 1. What the Competition is — and is not

The Competition rewards **engagement with the training simulator** — completing lessons, running Room sessions to a verdict, logging disciplined and reviewed trades, maintaining daily activity streaks — with points, a weekly leaderboard, and small amounts of in-app currency at streak milestones.

**The Competition never scores, ranks, or rewards trading profit or loss, real or simulated.** No leaderboard position, streak, or credit award is derived in whole or in part from portfolio performance. This is a design invariant, not a preference — see §8.

Placing well in the Competition means you engaged diligently with the training material. It does not mean, and must not be read to mean, that you are a skilled trader, that any strategy you used would perform well with real money, or that AMI has assessed your investing ability. Clauses 1–4 of the Terms apply in full.

## 2. Eligibility

You must meet the Terms' general eligibility requirements (minimum age, lawful use) to participate in the Competition. The Competition is void where prohibited by local law.

**All plans compete on identical terms**, including the free Floor Pass — the `LEAGUE_ELIGIBLE_PLANS` configuration that determines which subscription tiers may join a weekly league is currently empty, meaning no plan is excluded. **If this configuration is ever changed to exclude the free tier**, participation would require a paid subscription, which changes the Competition's legal character from a free-to-enter engagement feature to a paid-entry competition and requires legal re-review before it ships. This document will be re-versioned before any such change takes effect.

`[LAWYER REVIEW REQUIRED]` — AMI Trade is US-equities-only at alpha. Malaysia and the GCC are on the product roadmap; both carry gambling-adjacent regulatory scrutiny and Sharia considerations distinct from the US/EU/UK markets this document is drafted against. **A Sharia/legal ruling must be obtained before the Competition is enabled for users in those markets.**

## 3. How points are earned

| Action | Points |
|---|---|
| Daily challenge attempted | +2 |
| Daily challenge correct | +3 (5 total for a right answer) |
| Lesson passed | +5 |
| Agent unlocked | +10 |
| Room convened to a verdict | +3 |
| Disciplined trade | +2 (maximum 3 per day) |
| Reviewed trade | +3 (maximum 3 per day) |
| Streak of 7 / 30 / 100 days | +10 / +25 / +50 |

Points are earned by taking the action inside the simulator. No points are earned, and none are deducted, based on whether a simulated trade made or lost simulated money.

## 4. Limits and integrity

- A global cap of **25 points per day**, measured in your device's local timezone. Once you reach the cap, further qualifying actions that day earn no additional points.
- A **maximum of 3 per day** on each of the two repeatable trade actions (disciplined trade, reviewed trade), counted separately from the global cap.
- **No repeat credit** — re-passing a lesson you already passed, or re-unlocking an agent you already unlocked, earns 0 points.
- **One scored attempt per daily challenge.** A repeat attempt on the same day's challenge does not earn additional points or change your recorded result.
- **Streak milestones (7/30/100 days) pay out once ever per account**, not once per streak.

## 5. Streak milestone credits — `[LAWYER REVIEW REQUIRED]`

Reaching a 7-, 30-, or 100-day activity streak grants **5, 25, or 100 credits** respectively, the same in-app currency sold in credit packs under Terms clause 6.

Credits awarded through the Competition are:

- a **promotional in-app currency with no cash value** — they cannot be exchanged, redeemed, or converted for cash or any cash equivalent, by you or by AMI;
- **non-transferable** between accounts;
- **non-refundable**;
- **forfeited** if your account is terminated or closed, whether by you or by AMI under Terms clause 10;
- earned **solely through sustained engagement** — never through a wager, stake, entry fee, or game of chance; and
- **subject to change** — the milestone thresholds and credit amounts described in §3 may be adjusted; any change is reflected in a re-versioned publication of this document.

## 6. The weekly league

- The league week resets **Monday 00:00 UTC**.
- You are placed into a **cohort of up to 30 users**, assembled from users active in the prior 7 days, grouped by current tier.
- Within a tier, cohort membership is **assigned at random** among eligible active users — see §8 on what this randomisation does and does not mean.
- Ranking within your cohort is based on **points earned that week only.** Points from prior weeks carry no weight — a new entrant can lead their cohort in their first week.
- Ties are broken by whoever joined the cohort earlier.
- At the end of the week, the **top 5** in each cohort are promoted one tier and the **bottom 5** are relegated one tier; relegation only applies to cohorts with **at least 10 members**, so a small cohort will not relegate anyone.
- The tier ladder, from lowest to highest, is: **Apprentice → Analyst → Trader → Senior → Floor Veteran.** Tier is **cosmetic** — it changes your leaderboard placement and displayed rank only, and does not unlock, gate, or restrict any feature of AMI Trade. A user who has never been placed in a cohort starts at Apprentice.

## 7. Your competitive identity — `[LAWYER REVIEW REQUIRED]`

On your first contact with the league, AMI mints a pseudonymous **"Adjective Noun" handle** (for example, "Cobalt Falcon") for you. This handle, not your account email or real name, is what your cohort sees on the leaderboard by default.

- You may regenerate your handle **exactly once, ever.** Once used, this option is not available again.
- Your real display name is shown instead of your handle only if you have separately opted in to displaying it (account setting `show_display_name`).
- Leaderboard rows and league history are personal data about you for the purposes of applicable data-protection law. If you exercise a data deletion, access, correction, or erasure right under the [Privacy Policy](privacy_policy.md) or the [Data Deletion Policy](data_deletion_policy.md), your leaderboard rows and league membership history are deleted or anonymised as part of that request, on the same timeline (currently within 30 days) described in the Data Deletion Policy. Historical cohort rankings for other, unaffected users are not altered by your deletion beyond removing your entry from them.

`[LAWYER REVIEW REQUIRED]` — confirm this treatment satisfies GDPR/CCPA erasure obligations where a leaderboard row references other users' relative standing.

## 8. Not gambling; skill versus chance — `[LAWYER REVIEW REQUIRED]`

**The Competition involves no stake, no entry fee, and no wagering, and no score is ever derived from trading profit or loss.** This is stated in the Terms and reaffirmed here as a binding characteristic of the Competition, not a description that may quietly change: if this were ever to change, it would require a new version of this document and a fresh compliance review, because it is the basis on which AMI Trade's store listings represent the app as containing no gambling or simulated-gambling content.

Points are earned deterministically from actions you take — completing a lesson, convening a Room, logging a trade review — which is a skill-and-effort basis, not chance. The one place randomness enters the Competition is **cohort assignment**: which specific other users you are grouped with in a given week is assigned at random among eligible, tier-matched, active users. This randomisation determines **who you are compared against** (matchmaking); it does not determine **whether you win anything** — your score, and therefore your placement within whatever cohort you are assigned to, is entirely a function of your own recorded actions.

`[LAWYER REVIEW REQUIRED]` — confirm that randomised matchmaking, as distinct from randomised prize determination, does not itself trigger contest/sweepstakes or gambling-adjacent regulation in any jurisdiction where the Competition is offered.

## 9. Anti-cheat and disqualification

AMI reserves the right to void points, remove an entry from a leaderboard, or suspend or terminate an account under Terms clause 10, where we reasonably believe the Competition has been manipulated — including through automation, scripting, or operating multiple accounts to gain an advantage.

We do not warrant that manipulation will be detected. AMI Trade's anonymous-first onboarding makes creating more than one account straightforward, and our ability to correlate accounts is limited. Reserving this right is not a representation that manipulation will be found or prevented.

## 10. AMI's right to modify, suspend, or reset the Competition

Scoring values, daily caps, per-type limits, cohort size, promotion/relegation thresholds, tier names, and streak milestones are expected to be tuned as the product develops, and AMI reserves the right to change them, and to suspend, pause, or reset a league season, at any time. A change to any of the above is reflected in a re-versioned publication of this document; material changes follow the same 14-day notice practice described in Terms clause 13.

## 11. Simulation-only reaffirmation

Nothing about participating in, or performing well in, the Competition changes the fact that AMI Trade is a simulation. Terms clauses 1 through 4 — simulation only, not investment/legal/tax advice, AI output can be wrong, hypothetical-performance disclaimer — apply to every part of the Competition without exception. A high league placement reflects diligent engagement with the training material; it is not, and must not be read as, a signal of trading skill, of the profitability of any strategy, or of investment advice of any kind.

## 12. Data retention

Reputation events (the ledger of point-earning actions behind your score) and league membership history are retained under the general data-retention terms of the [Privacy Policy](privacy_policy.md), and are deleted or anonymised on account deletion per the [Data Deletion Policy](data_deletion_policy.md).

## 13. Disputes, liability, and indemnity — inherited from the Terms

These Rules do not create a separate dispute-resolution process, governing law, liability cap, or indemnity obligation for the Competition. **Disputes about the Competition — including a voided score, a leaderboard delisting, or a suspended account — are governed by the Terms of Service in exactly the same way as any other dispute about AMI Trade:** clause 11 (limitation of liability), clause 12 (warranty disclaimer), and clause 14 (indemnification) apply without modification. The Terms carry no governing-law or arbitration clause, by Saiful's explicit direction (see the Terms' own version history) — that is equally true here; these Rules do not introduce one for the Competition.

`[LAWYER REVIEW REQUIRED]` — confirm that Terms clause 14's indemnity carve-outs (AMI's own breach, gross negligence, wilful misconduct, non-waivable consumer rights) are drafted broadly enough to cover Competition-specific third-party claims such as a disputed score void or a leaderboard delisting, without redrafting clause 14 itself.

---

## § Version history

- **v1.0** — effective 23 July 2026. First publication. Written against the live scoring, streak, league, and eligibility behaviour in `reputation_service.py`, `league_service.py`, and `config.py` as of this date. Deliberately omits milestones, badges, tiers, and mechanics described in `docs/initial_specs/04_education/daily_and_streaks.md` that the code does not implement (365-day milestone, lifetime-total tiers, named badges, streak freezes, reminder notifications, partial credit) — see [CR065](../../docs/forward_planning/CR065_streaks_spec_code_drift/CR065_streaks_spec_code_drift.md). If any of those are built, this document must be re-versioned before the corresponding feature ships. Filed as [CR064](../../docs/forward_planning/CR064_competition_terms/CR064_competition_terms.md).

When a new version is published, the previous version is preserved at `/competition-rules/v<N>/` (website) and `legal/history/competition_rules/` (markdown source) for audit, per [`VERSIONING.md`](../VERSIONING.md).

---

## Contact

For any question about these Rules, contact:

**legal@agenticmarketintel.ai**

For the rules of using AMI Trade generally, see the [Terms of Service](terms_of_service.md). For how we handle personal information, see the [Privacy Policy](privacy_policy.md).

---

## Document status

This is a draft prepared from code-truth review of `backend/app/services/reputation_service.py`, `backend/app/services/league_service.py`, and `backend/app/core/config.py`, cross-checked against the spec/code drift register in [CR065](../../docs/forward_planning/CR065_streaks_spec_code_drift/CR065_streaks_spec_code_drift.md). It must be reviewed and signed off by counsel before being treated as legally binding, same as the Terms of Service, Privacy Policy, and Data Deletion Policy.

### Lawyer-only checklist

Before publishing, counsel must confirm or replace:

| § | Clause | Why it needs counsel |
|---|---|---|
| 2 | Malaysia/GCC eligibility | Sharia/legal ruling required before leagues are enabled in those markets |
| 5 | Streak milestone credits | Confirm the "promotional currency, no cash value" characterisation holds where credits are also directly purchasable |
| 7 | Leaderboard rows under GDPR/CCPA | Confirm erasure-request handling for leaderboard/league-history rows referencing other users |
| 8 | Randomised cohort assignment | Confirm matchmaking-not-prize-determination framing avoids contest/gambling-adjacent regulation |
| 13 | Indemnity scope for Competition claims | Confirm Terms clause 14 already covers a voided score or delisting dispute without redrafting |
