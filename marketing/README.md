# `marketing/` — plans and assets

Two marketing plans and their drafted assets: one to raise the USD 24,000 backer round, one to
acquire users. Written 2026-07-30.

**Everything here is a draft for Saiful's review. Nothing has been sent, published, submitted or
deployed.**

Docs-only, so no CR ID — version and docs commits are CR-exempt under `CLAUDE.md`.

---

## Read in this order

| # | File | What it is |
|---|---|---|
| 1 | [`_facts/claim_register.md`](_facts/claim_register.md) | **The gate.** Every number marketing may use, its source, its measurement date, and the list of claims that are forbidden. Read before writing or editing any asset |
| 2 | [`user_poc/so_what.md`](user_poc/so_what.md) | Saiful's positioning document. Canonical for voice and personas |
| 3 | [`users/positioning_and_personas.md`](users/positioning_and_personas.md) | `so_what.md` reconciled against what actually ships, plus the three rules it establishes |
| 4 | [`investors/investor_marketing_plan.md`](investors/investor_marketing_plan.md) | **Strategy: investors.** The $24k backer raise |
| 5 | [`users/user_acquisition_plan.md`](users/user_acquisition_plan.md) | **Strategy: users.** $0 organic now → $1,400/mo post-raise |

Assets sit under `investors/assets/` and `users/assets/`. Each names what blocks it.

---

## The four things worth knowing before reading anything else

**1. We are at zero.** No payment has ever processed. Zero waitlist signups on a site that has been
live for months. No public store listing. No real external users. These are plans for a launch from
nothing, not for optimising a funnel — and the investor plan states the zeros deliberately, because
they are the reason for the raise.

**2. Sharia screening is live, and our own website says it isn't.** AAOIFI-based, 216 compliant of
the 503-name S&P 500 index, as-of dated per verdict, reaching the client since DEF094 was fixed.
It is the most defensible differentiator in the product and it costs nothing to market. Correcting
the website is the highest-value single edit on the list. One guardrail: `unknown` must never read
as approval — that was the defect.

**3. Nothing can be spent until three gates close.** No product analytics, no install attribution,
`SENTRY_DSN` empty, no push, and lifecycle email that only sends login codes. Spending $1,400/month
against that is buying installs we cannot attribute into a funnel we cannot see, with no way to
bring anyone back. Gates A/B/C in `users/user_acquisition_plan.md` §2.

**4. The investor plan's binding constraint is legal, not creative.** The agreement is an unsent
v0.3 draft with five `[LAWYER REVIEW REQUIRED]` flags, two unset terms, and no corporate entity
behind it. Marketing an investment is solicitation, so the plan permits only private, named,
one-at-a-time conversations — no website page, no posts, no cold outreach, no group messages —
until counsel clears it.

---

## What blocks what

| Blocked item | Blocked on | Who |
|---|---|---|
| Any investor conversation | Counsel review of the agreement (P1) | Saiful |
| Investor terms in any document | `Backer Pool %` and `Return Cap` are placeholders (P3, P4) | Saiful |
| Founder-compensation answer | `[FOUNDER TO CONFIRM]` in §1 of the agreement (P5) | Saiful |
| Any price in any asset | Spec, website and free-tier definitions disagree three ways | Saiful |
| Paid acquisition | Gate A — analytics + attribution | build lane |
| Apple Search Ads, Google App Campaigns | Gate B — public store listings | Saiful + capture session |
| Six of eight lifecycle messages | Gate C — push + a lifecycle email sender | Saiful (OneSignal/APNs) + build lane |
| Store screenshots | A capture session on device | Saiful |
| Referral / share card copy | No share mechanic exists | build lane |
| Halal outreach | The website correction shipping first | webmaster |

---

## Rules for editing anything in here

1. **Every number traces to a claim-register row.** A figure without one gets sourced or deleted.
2. **Re-measure before external use** if the register's measurement date is more than ~30 days old,
   or label the figure with its date in the asset.
3. **Run the sweeps** before shipping an edited asset:

```bash
cd "/Volumes/Extreme Pro/AMI_MarketApp"

# forbidden claims — every hit must be a deliberate negation or a guardrail
grep -rniE "guarantee|guaranteed|returns of|beat the market|advice|recommend|signal|picks" marketing/

# unbuilt features claimed as shipped
grep -rniE "briefing|voice|push notification|share card|badge|credit pack|real[- ]time" marketing/users/

# "AMI, never the AI" in user-facing assets
grep -rniE "\bthe AI\b|\bour AI\b" marketing/users/ marketing/investors/assets/one_pager.md
```

4. **Halal copy goes through `claim_register.md` N1 every time.** Scoped universe, dated verdict,
   `unknown` never presented as a pass, no AR/MS without human review.
5. **User-facing copy leads with the outcome, never with agent architecture.** Investor-facing copy
   does the opposite — the architecture is the moat. The two audiences get opposite leads, on
   purpose.
6. **Commit with an explicit pathspec** — `git commit -m "…" -- marketing/`. Never bare, never
   `-am`, never `add -A`: this is a shared checkout and a bare commit sweeps whatever another track
   left dirty.

---

## What this folder does not do

No code. No analytics SDK. No store submission. No website deploy. No edits to
`legal/agreements/profit_sharing_agreement_template.md`, and no edits to `user_poc/so_what.md`.
Where a plan needs one of those, it names it as a build item or a Saiful item and stops.
