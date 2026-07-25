# AMI Trade — Backer Profit-Participation Agreement (template)

> **Status: DRAFT — NOT SENT TO ANYONE, NOT SIGNED.** This is a founder-drafted starting
> point, not legal advice. **Do not send this to a prospective backer, and do not sign
> anything based on it, before a Malaysia-qualified lawyer reviews it** — see the two flags
> below and the checklist at the bottom.
>
> **Two things a lawyer needs to weigh in on before this goes anywhere:**
> 1. **Securities characterisation.** Taking money from multiple people in exchange for a
>    share of profits is the textbook fact pattern for an "investment contract" /
>    collective-investment-scheme test in most jurisdictions, including Malaysia (Capital
>    Markets and Services Act 2007, regulated by the Securities Commission Malaysia). Whether
>    this structure needs a prospectus, falls under an exemption (e.g. limited number of
>    offerees, sophisticated-investor exemption), or needs to be restructured entirely is a
>    question for counsel — **before**, not after, you take a single dollar.
>    `[LAWYER REVIEW REQUIRED]`
> 2. **No corporate entity yet.** Per `legal_plan_ami_trade.md`, AMI Trade has no
>    incorporated entity — "Corporate entity TBD." Until one exists, any agreement you sign is
>    a **personal obligation of Saiful individually**, not a company obligation. §10 below adds
>    a novation mechanism for when an entity is formed, but until it's exercised, backers are
>    contracting with you personally, with your personal assets exposed. Strongly consider
>    incorporating (a Malaysian Sdn Bhd is the natural fit) **before** taking any backer's money.
>    `[LAWYER REVIEW REQUIRED]`
>
> Not part of AMI Trade's consumer-facing legal set (`legal/policies/`) — this is a private
> instrument between the Founder and named Backers, never published to the website, never
> deployed via `deploy_ftp.py`, not in `sitemap.xml`, not versioned via `legal/VERSIONING.md`'s
> public-facing playbook.

| | |
|---|---|
| **Document** | Backer Profit-Participation Agreement |
| **Version** | 0.2 (template, unsent) |
| **Drafted** | 25 July 2026 |
| **Drafted by** | Founder (Claude-assisted), pending counsel review |
| **Parties per signing** | One agreement, multiple Backers via Schedule A (§ below) |

---

## Parties

**The Founder:** Saiful [FULL LEGAL NAME], an individual residing in Malaysia, operating
under the trading name "AMI Trade" (together, the "**Founder**"). *If a corporate entity
(the "**Company**") is incorporated after this Agreement is signed, §10 (Novation) governs
how the Founder's obligations transfer to the Company.*

**The Backer(s):** Each individual or entity listed in **Schedule A**, each a "**Backer**."
Where this Agreement is signed by more than one Backer, each Backer's rights and obligations
are several (not joint) and are calculated **pro rata to that Backer's Contribution** as a
share of Total Contributions — one Backer's default or dispute does not affect another's.

---

## Recitals

- The Founder operates AMI Trade, a simulation-only AI trading-education mobile app.
- The Founder is raising up to **USD 24,000** in total (USD 2,000/month for 12 months) to
  cover operating costs and advertising spend during this period (the "**Raise**").
- Each Backer wishes to contribute part of that amount in exchange for a share of AMI
  Trade's future profits, on the terms below.
- This is **not a loan**: the Founder makes no promise to repay Contributions, has no fixed
  repayment date, and owes no interest. Payment to Backers happens **only if and when** AMI
  Trade generates Monthly Gross Profit, as defined below.
- This is **not equity**: no shares, membership interests, or ownership of any kind are
  issued. Backers get a contractual right to a share of profit, nothing more.

---

## 1. Definitions

- **"Contribution"** — the total amount a Backer pays to the Founder under Schedule A,
  paid in monthly instalments over the **Contribution Period**.
- **"Contribution Period"** — 12 consecutive months from each Backer's first payment.
- **"Total Contributions"** — the sum of all Backers' Contributions actually paid to date.
- **"Monthly Revenue"** — all cash actually collected by AMI Trade in a given calendar
  month from operating the product (subscriptions, credit-pack sales, advertising revenue,
  or any other product revenue). **Excludes** Backer Contributions themselves.
- **"Direct Costs"** — costs directly incurred that same month to generate Monthly Revenue
  and run the product: app-store and payment-processor fees, cloud/hosting and LLM-inference
  costs, third-party data/API costs, advertising and marketing spend, and contractor or
  freelancer fees tied to running the product. **Excludes**: the Founder's own salary, draw,
  or compensation of any kind; non-cash accounting items (depreciation, equity
  compensation); one-off capital purchases unrelated to that month's operation. *(Founder
  compensation is deliberately excluded from Direct Costs so profit isn't reduced by what the
  Founder pays himself — flagged here because it's a real conflict of interest to manage in
  practice, not just on paper.)* `[FOUNDER TO CONFIRM]`
- **"Monthly Gross Profit"** — Monthly Revenue minus Direct Costs for that calendar month.
  Can be zero or negative; if negative, no Profit Share is owed for that month and the
  shortfall does **not** carry forward against future months.
- **"Backer Pool Percentage"** — **20%** of Monthly Gross Profit, set aside for all Backers
  combined. `[FOUNDER TO SET — placeholder value, adjust before use]`
- **"Backer's Pro Rata Share"** — a given Backer's Contribution divided by Total
  Contributions, applied to the Backer Pool Percentage to work out that Backer's individual
  monthly payment.
- **"Return Cap"** — profit-share payments to a Backer stop once that Backer has received,
  in total, **2.5×** their Contribution. `[FOUNDER TO SET — placeholder value, adjust before use]`

---

## 2. The Contribution

Each Backer pays their Contribution in 12 equal monthly instalments per Schedule A, by bank
transfer to an account nominated by the Founder. A Backer's participation begins on their
first payment; missing two consecutive instalments without agreement suspends that Backer's
Profit Share rights until they catch up, at the Founder's discretion.

## 3. Use of Funds

Contributions are used for AMI Trade's operating costs and advertising/marketing spend
during the Contribution Period, indicatively split **30% infrastructure/tooling and 70%
advertising/user acquisition** — see **Schedule B** for the current breakdown. Schedule B
is provided for transparency and reflects the Founder's plan as of the date on that
schedule; it is **not a binding budget line-item**, and the Founder may reasonably
reallocate between and within these categories as the business's needs change (e.g.
channel performance, timing of opening the app stores to the public). The Founder does not
owe Backers a line-item accounting of actual spend beyond this, but will provide the
summary report described in §5.

## 4. Profit Share

Starting the month after AMI Trade first generates positive Monthly Gross Profit, the
Founder pays each Backer their Pro Rata Share of the Backer Pool Percentage, within 15 days
of month-end. Payments continue until the earlier of: (a) that Backer reaching their Return
Cap, or (b) AMI Trade ceasing operations. There is no guaranteed minimum payment, no
guaranteed timeline to profitability, and no obligation to fund a shortfall from any other
source.

## 5. Reporting

The Founder provides each Backer a brief written summary each quarter: Monthly Revenue,
Direct Costs, Monthly Gross Profit, and amounts paid to the Backer Pool, for each month in
that quarter. Backers may request supporting detail once per year; the Founder isn't
obligated to provide full audited financials (none exist for a solo-founder company at this
stage).

## 6. Term and Cap

This Agreement ends, for a given Backer, on the earlier of: their Return Cap being reached,
both parties agreeing in writing to end it early, or AMI Trade ceasing operations
permanently. Ending the Agreement does not entitle a Backer to any refund of unpaid
Contribution shortfall against profit already earned, and does not revive after termination.

## 7. Nature of the Relationship

Nothing in this Agreement creates a loan, a partnership, a joint venture, an employment
relationship, or an equity/ownership interest of any kind. Backers have **no voting rights,
no board seat, no management authority, and no claim on AMI Trade's assets or IP** beyond
the contractual profit-share right defined above. This distinction is deliberate and
central to the Agreement's structure. `[LAWYER REVIEW REQUIRED — confirm this framing holds
under Malaysian and any relevant Backer-home-jurisdiction securities law]`

## 8. Risk Acknowledgment

Each Backer confirms they understand: AMI Trade is an early-stage, unproven venture; there
is a real possibility of receiving less than their Contribution back, or nothing at all;
past or projected performance is not a guarantee of future profit; and they are contributing
funds they can afford to lose in full.

## 9. Confidentiality

Backers receiving financial summaries under §5 agree to keep them confidential and not
share them outside their own personal or professional advisors, except as required by law.

## 10. Novation Upon Incorporation

If the Founder incorporates a company to operate AMI Trade (the "Company") during the
Contribution Period, the Founder may assign this Agreement — and all obligations under it —
to the Company by written notice to each Backer. Upon assignment, the Company becomes
responsible for all Profit Share obligations in place of the Founder personally, and each
Backer's rights continue unchanged. A Backer may object in writing within 30 days if they
reasonably believe the Company is not a fit substitute (e.g. undercapitalised shell); absent
objection, the assignment takes effect automatically. `[LAWYER REVIEW REQUIRED — confirm
this mechanism is enforceable and correctly protects Backers through the transition]`

## 11. Assignment and Transfer

A Backer may not sell, assign, or transfer their rights under this Agreement to anyone else
without the Founder's written consent. This restriction is deliberate: freely transferable
profit-participation rights look more like a tradeable security than a private contract, and
keeping this non-transferable is part of what keeps this a private arrangement between named
parties. `[LAWYER REVIEW REQUIRED]`

## 12. Governing Law and Disputes

This Agreement is governed by the laws of Malaysia. Both parties submit to the
non-exclusive jurisdiction of the courts of Kuala Lumpur, Malaysia, for any dispute that
cannot be resolved informally within 30 days of one party raising it in writing. There is no
arbitration clause in this Agreement.

## 13. General

This is the entire agreement between the Founder and each Backer regarding the Raise, and
supersedes any prior discussion. Amendments require written agreement from both parties. If
any clause is found unenforceable, the rest of the Agreement stands. Notices are valid by
email to the addresses in Schedule A.

---

## Schedule A — Backer Details

| Backer name | Contribution (total) | Monthly instalment | Start date | Contact email | Signature / date |
|---|---|---|---|---|---|
| [Backer 1] | USD [amount] | USD [amount]/mo | [date] | [email] | |
| [Backer 2] | USD [amount] | USD [amount]/mo | [date] | [email] | |

*Add rows as needed. Sum of "Contribution (total)" should equal USD 24,000 if the full
Raise target is met; can close early or extend to more Backers as needed — adjust
`Total Contributions` and `Return Cap` math accordingly for each Backer's Pro Rata Share.*

---

## Schedule B — Indicative Use of Funds (as of 25 July 2026)

*This schedule is a plan, not a promise — see the reallocation language in §3. Numbers are
the Founder's own estimate, not a measured or audited budget.*

Total raise: USD 24,000 over 12 months (USD 2,000/month).

| Category | Monthly | 12-month total | Share of raise |
|---|---|---|---|
| Infrastructure & tooling | USD 600 | USD 7,200 | 30% |
| Advertising & user acquisition | USD 1,400 | USD 16,800 | 70% |
| **Total** | **USD 2,000** | **USD 24,000** | **100%** |

**Infrastructure & tooling (USD 600/mo)** — app-store developer fees (Apple Developer
Program, Google Play Console), domain renewal, web hosting, running costs (electricity)
for the self-hosted server and on-prem AI-inference hardware already owned by the Founder
(not purchased from this raise), and the Founder's AI-assisted development tooling
(Claude). Includes buffer for infrastructure that only activates later — managed
database/auth, crash reporting, product analytics, push notifications — if the product
grows beyond the current self-hosted alpha setup during the Contribution Period.

**Advertising & user acquisition (USD 1,400/mo)** — indicative channel split once AMI
Trade has a public store listing on at least one platform:

| Sub-channel | Monthly (once public) | Notes |
|---|---|---|
| Apple Search Ads | ~USD 600–700 | Keyword-targeted, App Store only — requires a public App Store release (a TestFlight build is not sufficient) |
| Google App Campaigns | ~USD 600–700 | Automated bidding, Play Store only — requires a public or open-testing Play listing |
| Reddit ads / creator (influencer) placements | remainder, ~USD 100–200 | No store-listing dependency; used before and alongside the two search channels |

Until an app store listing is public, the full advertising allocation goes to the
non-store-dependent row (Reddit ads / creator placements) and organic content
amplification of existing lesson content; Apple Search Ads and Google App Campaigns are
added once the corresponding store listing opens.

---

## Lawyer-only checklist

Before this Agreement is used with a real Backer:

| # | Item | Why it matters |
|---|---|---|
| 1 | Securities characterisation under Malaysian law (CMSA 2007) | Determines whether this needs an exemption, a prospectus, or restructuring entirely — the single biggest legal risk in this document |
| 2 | Founder's personal liability pre-incorporation (§10) | Confirms Backers understand and accept they're contracting with an individual, not a company, until novation |
| 3 | Enforceability of the novation mechanism (§10) | Confirms the assignment-on-incorporation approach actually protects Backers and isn't itself a red flag |
| 4 | Transfer restriction (§11) as an anti-security-classification lever | Confirms this actually helps rather than being cosmetic |
| 5 | Tax treatment of profit-share payments, for both Founder and Backer | Not addressed anywhere in this draft — needs its own advice, likely jurisdiction-dependent per Backer |
| 6 | Multiple-Backer aggregation risk | Whether raising from "some people" (plural) changes the securities analysis versus a single backer |
| 7 | Use-of-funds specificity (Schedule B) | Detailed spend projections read more like a prospectus/PPM than a private contract — confirm the reallocation hedge in §3 is enough to keep this from being read as a binding representation |

---

## Version history

- **v0.1** — 25 July 2026. Initial founder draft, unsent, no signatures. Structure: capped
  return (2.5× placeholder) on % of Monthly Gross Profit (Revenue − Direct Costs),
  non-transferable, Malaysia governing law with courts (no arbitration), novation-on-
  incorporation clause to handle the no-entity-yet gap.
- **v0.2** — 25 July 2026. Added Schedule B (indicative use-of-funds breakdown: 30%
  infra/tooling, 70% advertising; advertising sub-split across Apple Search Ads / Google
  App Campaigns / Reddit-creator channels, gated on public store-listing availability).
  §3 updated to reference it with a non-binding/reallocation hedge. New checklist item #7
  on use-of-funds specificity. Still unsent, no signatures.
