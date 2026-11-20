# Credit applications draft, 2026-11-20 (gate S5)

CR267 WP-40 follow-up. The founder chose two programmes: **Cloudflare for Startups, Tier 3** and **Alibaba Cloud AI Catalyst**. This file holds the eligibility checks, draft answers and the "plan for using the cloud" text for each. Nothing has been submitted. Submitting is the founder's step.

Rules for this file:

1. Eligibility and links were read on each vendor's own page on **2026-11-20**. Where a page did not say, the line says **not stated** or **not verified**.
2. Anything about the company we cannot source from this repo is marked **[founder to fill]**. That covers registration number, founding date, revenue, headcount and emails.
3. The repo is public. No personal data is in this file. "The founder" is used instead of a name.
4. Draft answers use the brand voice: numbers over adjectives, "AMI" by name, no claims of returns or stock picking. AMI Trade is a simulation-only education app.
5. Companion: `beta_host_options_2026-11-20.md` (the host options these credits might pay for) and `credits_and_accelerators_2026-11-19.md` (the wider list).

## 1. What is already in place

1. **Website.** https://agenticmarketintel.ai returned HTTP 200 on 2026-11-20. Page title "AMI Trade — Learn to Make and Defend Trading Decisions". Its structured data names the organisation "AMI — Agentic Market Intelligence" and describes AMI Trade as "a simulation-only trading education app". It has a waitlist ("Join Waitlist", "Get Early Access"). Last-modified header: 2026-08-20.
2. **Domain and DNS on Cloudflare.** Responses carry Cloudflare headers. A Cloudflare Tunnel already fronts the Alpha API at `api-alpha.agenticmarketintel.ai` (`CLAUDE.md`, `infra/cloudflared/`).
3. **Mail records exist.** The domain's MX record points to `mail.agenticmarketintel.ai` (the cPanel host). Whether a mailbox such as `founder@` or `support@` exists on it is **[founder to confirm]**.
4. **Company entity.** The repo's CR258 doc names the company as "Agentic Market Intelligence Sdn Bhd", Malaysia. Registration details are **[founder to fill]**. Company Apple and Google developer accounts are **not enrolled yet** (`CR267_beta_programme.md`); that does not affect these two applications.
5. **Product.** Alpha is live and in stealth. Beta is planned as 20 to 200 testers over 6 to 12 weeks through TestFlight and Play closed testing (`CR267_beta_programme.md`).
6. **Public code presence.** The repo is public on GitHub under the founder's personal account. A company LinkedIn or X page: **[founder to fill]**.

## 2. Blockers and risks

1. **Business email on the domain.** Both programmes want a company-domain email, not Gmail or similar. The mailbox must exist before applying. Cloudflare says it checks this ("no personal email addresses").
2. **Email Routing conflict.** WP-52 plans Cloudflare Email Routing for `support@`. Email Routing needs Cloudflare's MX records. The domain's MX today points to cPanel mail. Switching would move or break any mailbox hosted on cPanel **(inference; check before changing DNS)**. Pick one mail path first. Apply with whichever mailbox already works.
3. **Company age.** Both need the company founded within 10 years. The Sdn Bhd date is **[founder to fill]**; almost certainly fine, but unconfirmed.
4. **Cloudflare: "first-time applicant".** No earlier approval is known from the repo. The account already exists on a free plan. **[founder to confirm no earlier application]**.
5. **Alibaba: fit is not confirmed.** The program page today lists three areas it is "especially interested" in: AI video and image creation, AI model aggregators, content moderation. AMI Trade is none of those. The page states no formal eligibility rules and no country list; award is at Alibaba's discretion. Expect a real chance of decline. (The 2026-11-19 file recorded "AI as the core technology; unlisted company founded within 10 years; accessible website" as criteria; **those lines were not on the page today**, so treat them as unconfirmed.)
6. **Alibaba: account first.** Terms require a valid Alibaba Cloud account. A third-party guide says a payment method must be on file before the form; **not verified on a vendor page**. Account creation and any verification code are the founder's step.
7. **Alibaba: credits exclude prepaid products.** Pay-as-you-go ECS fits. Annual or monthly prepaid plans do not.
8. **Cloudflare: Containers coverage not stated.** If Containers is chosen as Beta host, ask startups@cloudflare.com whether it draws down credits before relying on it.
9. **Cloudflare: Workers AI and AI Gateway are not covered.** Our LLM spend cannot use these credits.
10. **Alibaba licence grant.** The terms let Alibaba use the company name, website and logos in directories and promotion. Decide if that is acceptable before submitting. Source: https://www.alibabacloud.com/startup/terms-and-conditions

## 3. Cloudflare for Startups, Tier 3

**Application URL:** https://www.cloudflare.com/lp/startups (the "Apply here" link on https://www.cloudflare.com/startups/). The form page returned HTTP 403 to automated fetches on 2026-11-20, so it could not be read.

### 3.1 What Tier 3 gives (read 2026-11-20 at https://www.cloudflare.com/startups/)

1. **$10k credits.** Valid one year or until used; extensions not currently approved. After that the card on file is billed.
2. **Covered:** Workers, Workers for Platforms, Durable Objects, Workflows, KV, D1, Queues, Vectorize, R2 (up to $10,000), Pages, Images, Stream, Cache Reserve, Argo Smart Routing.
3. **Not covered:** AI Gateway (temporarily), registrar fees, enterprise add-ons, premium network services, and Workers AI for new startups from 1 December.
4. **Free on all tiers:** DDoS and bot protection, WAF with 1,000 custom rules, SSL, CDN, DNS, 1 rate-limiting rule. The page lists a "100% SLA" while its terms say the Startup Plan has no SLA.
5. **Review time:** typically up to 48 hours. If no reply after a week, email startups@cloudflare.com.
6. **Not mentioned on the page:** Containers, and any country restriction.

### 3.2 Eligibility checklist (all must hold; verbatim criteria from the page)

| # | Criterion on the page | Status for AMI | Source of status |
|---|---|---|---|
| 1 | Founded within the last 10 years | Likely yes; date needed | **[founder to fill]** incorporation date |
| 2 | Funded up to Series B | Yes, nothing raised | Founder statement (self-funded) |
| 3 | Bootstrapped or self-funded, under $1M raised (Tier 3) | Yes | Founder statement; **[founder to confirm amount invested is under $1M]** |
| 4 | Building a technology product | Yes | Repo, website |
| 5 | Valid, publicly accessible website | Yes | HTTP 200 on 2026-11-20 |
| 6 | Active on LinkedIn, X or GitHub | Partly: public GitHub repo (personal account) | **[founder to fill]** company LinkedIn or X |
| 7 | Not previously approved into the program | Believed yes | **[founder to confirm]** |
| 8 | For-profit, business email matching the domain | Domain MX exists; mailbox unconfirmed | **[founder to confirm]** mailbox |

Not a fit per the page: educational institutions, personal blogs, consultancies, service agencies, MSPs, resellers. AMI is a product company.

### 3.3 Form fields

**The form could not be read (HTTP 403).** The program page does not list the fields; it says confirmations go to "the address provided in your application form". A search result describes the form as asking for project and team details. Below are the fields most likely to appear, with drafts. **Treat the list as unverified**: the founder will see the real form and should map these drafts onto it. Open the form in a browser, then paste.

| Likely field | Draft answer |
|---|---|
| Company name | Agentic Market Intelligence Sdn Bhd (trading as AMI) |
| Company website | https://agenticmarketintel.ai |
| Country | Malaysia |
| Company registration number | [founder to fill] |
| Date founded / incorporated | [founder to fill] |
| Legal structure | Private limited company (Sdn Bhd) |
| Industry or vertical | Education technology; applied AI; financial education |
| Your name and title | [founder to fill] |
| Business email | [founder to fill; must be on agenticmarketintel.ai] |
| Phone | [founder to fill] |
| LinkedIn / X / GitHub URL | [founder to fill]; public GitHub repo exists under the founder's account |
| Number of employees | [founder to fill] (the team is one founder, per the repo) |
| Funding raised to date | $0 external. Self-funded. [founder to confirm] |
| Funding stage | Bootstrapped, pre-revenue |
| Annual revenue | $0 (pre-revenue, stealth alpha). [founder to confirm] |
| What are you building? | See 3.4 |
| Current Cloudflare use | See 3.5 |
| Estimated monthly Cloudflare spend | [founder to fill]. Today: free plan items only. Planned: Workers Paid $5 plus R2 backups, well under $10 per month for storage |
| Have you applied before? | No. [founder to confirm] |
| How did you hear about the program? | [founder to fill] |
| Do you have an affiliated funding partner? | No (this is why Tier 3 applies) |

### 3.4 Product description (draft, about 100 words)

AMI Trade is a mobile app that teaches people to make and defend trading decisions. It is simulation-only. No real money moves, and the app is not a brokerage or an advisory service. A simulated desk of AMI analysts debates a stock in front of the user. The user then makes the call in a practice portfolio. A compliance check runs before every practice trade, and every decision is saved in a journal the user can replay. It works in English now; Arabic and Malay follow. We are in stealth alpha and plan a closed Beta of 20 to 200 testers over 6 to 12 weeks.

Source: `docs/initial_specs/00_overview/vision_and_positioning.md` and `docs/initial_specs/01_product/core_loop_and_features.md`. Check the wording against any marketing review; it avoids performance claims on purpose.

### 3.5 Plan for using Cloudflare (draft)

What we already use:

1. DNS, proxy and WAF on `agenticmarketintel.ai`.
2. Cloudflare Tunnel in front of our Alpha API, so the server opens no inbound ports.
3. Cloudflare Access support for our admin console is built (`CF_ACCESS_TEAM_DOMAIN` in the backend). Whether it is switched on for Alpha was not checked; **[founder to confirm before claiming it]**.

What the credits would pay for, in order of need:

1. **R2 for encrypted off-server database backups.** A nightly encrypted dump goes to an R2 bucket, with a restore drill that downloads the newest object and restores it into a throwaway database. Built and tested against stubs (`infra/backups/`, `wp44_backups_alerts.md`). Size is small: about 20 GB of dumps is about $0.30 per month at R2 list price.
2. **Workers static assets and D1 for the website and waitlist**, with Turnstile on the sign-up form, replacing our current shared-hosting site.
3. **Workers Paid ($5 per month) and Cron Triggers** for an uptime probe that calls our health endpoint and posts failures to a webhook.
4. **Cloudflare Containers, only if we choose it as the Beta API host.** Our options study (`beta_host_options_2026-11-20.md`) compares it with a Singapore VPS. This is not decided. We will ask Cloudflare whether Containers draws down credits before relying on it.
5. **Tunnel, WAF custom rules and the free rate-limiting rule** stay in use for the Beta API at `api-beta.agenticmarketintel.ai`.

Honest expected use: the likely draw on credits is a few hundred dollars over the year (the Containers case reaches about $400 to $700). The credits would not be exhausted.

## 4. Alibaba Cloud AI Catalyst

**Application URL:** https://www.alibabacloud.com/startup/ai ("Submit the online form on this webpage"; no separate form URL is given). Terms: https://www.alibabacloud.com/startup/terms-and-conditions . Contact: contact.us@alibabacloud.com (from the program page).

### 4.1 What it gives (read 2026-11-20 on the program page)

1. Up to **2B free Model Studio tokens**.
2. Up to **$120k cloud credits**, plus POC coupons.
3. 1:1 office hours with Alibaba Cloud AI experts, event invitations, AI Alliance access, 12 months of Alibaba Cloud Academy.
4. **How to apply:** submit the form; you may get a request for more information; successful applicants are emailed within 4 to 5 business days.
5. **Program period:** 2026-08-01 to 2027-03-31 (terms, clause 1.1). The program page itself states no period.
6. **Credit validity:** not stated in the terms. The earlier file says "different validity periods based on the credit amount"; **not on today's pages**.
7. Terms: credits cannot buy domains, CDN, Academy, Marketplace or prepaid products; amounts are decided by Alibaba; some credits need an application that Alibaba may accept or reject. No country restriction is mentioned; Malaysia is not mentioned.

### 4.2 Eligibility checklist

The program page lists **no formal eligibility criteria** today. Terms list only a valid Alibaba Cloud account, the right to reject, and content rules (no offensive material; no infringement of third-party rights). The checks below combine those with the criteria recorded on 2026-11-19; the second set is **unconfirmed today**.

| # | Check | Status for AMI | Source |
|---|---|---|---|
| 1 | Valid Alibaba Cloud account | **Not created** [founder to create; password and verification code are the founder's] | Terms 1.2 |
| 2 | Not under a reseller or distributor | Yes | Terms (2026-11-19 file) |
| 3 | Company unlisted, founded within 10 years | Likely; date needed [founder to fill] | 2026-11-19 file, unconfirmed today |
| 4 | Accessible website | Yes (HTTP 200) | Checked today |
| 5 | AI as core technology of the primary product | Yes: multi-agent LLM system is the product | Repo; criterion unconfirmed today |
| 6 | Solid proposal for using Alibaba Cloud and its AI tools | Draft in 4.4 | 2026-11-19 file |
| 7 | Priority areas (video and image, model aggregators, content moderation) | **No match.** Not exclusive: the page says "especially interested" | Program page |
| 8 | Content: no offensive material, no third-party rights violations | Yes. Review the draft before sending | Terms section 3 |

### 4.3 Form fields

**Not specified on the page, and the form was not visible.** Likely fields: company name, website, country, contact name and email, funding stage, product description, AI use, Alibaba Cloud products wanted, estimated usage, proposal text. Drafts below reuse section 3.3 and the texts in 3.4 and 4.4. **Unverified list.**

| Likely field | Draft answer |
|---|---|
| Company name, website, country | Agentic Market Intelligence Sdn Bhd; https://agenticmarketintel.ai; Malaysia |
| Registration number, founded | [founder to fill] |
| Contact name, title, business email, phone | [founder to fill] |
| Funding to date and stage | Self-funded, pre-revenue, stealth alpha. [founder to confirm] |
| Employees | [founder to fill] |
| Alibaba Cloud account ID | [founder to fill after account creation] |
| Product description | Text in 3.4 |
| How is AI core to the product? | AMI Trade runs a team of LLM agents with fixed roles (analysts, a risk officer, an execution desk, a CIO). Each agent reads market data and the user's mandate and writes a structured opinion. A deterministic compliance check runs after the CIO's decision. The product is the LLM workflow; remove it and nothing remains. |
| Target market | Malaysia and the GCC first (English at alpha; Arabic and Malay at v1.0), then US equities education. Source: `CLAUDE.md` decision pointers. |
| Stage and traction | Alpha live in stealth. Closed Beta planned: 20 to 200 testers over 6 to 12 weeks. [founder to add any waitlist count] |
| Alibaba Cloud products wanted | ECS (Kuala Lumpur or Singapore), Model Studio (Qwen-family models), object storage for backups |
| Expected monthly spend | Host about $28 to $33 for a 2 vCPU, 4 GB instance in Kuala Lumpur (third-party price, **not verified on Alibaba's page**). Model tokens: see 4.4. |

### 4.4 Plan for using Alibaba Cloud (draft)

**Hosting.**

1. Run our Beta API on Alibaba Cloud ECS in Kuala Lumpur, so the server sits in Malaysia, near our first users. The stack is a Docker Compose set: the API, Postgres and a tunnel connector. Same stack as our Alpha environment, so no re-write.
2. Use pay-as-you-go billing, because the credit terms exclude prepaid products.
3. Keep encrypted nightly database backups in object storage, and rehearse a restore.

**Model Studio and Qwen-family models.**

1. Our Alpha already runs a Qwen-family model that we serve on our own hardware. The Model Studio model list read on 2026-11-20 includes `qwen3.8-flash`, `qwen3.7-plus` and `qwen4-max`. Source: https://www.alibabacloud.com/help/en/model-studio/models
2. We would test Qwen models on Model Studio as a second LLM provider for the Beta, behind our own provider-fallback layer, using our standing scorecard (the same Room benchmark we ran for our other candidate models). No switch is promised. Adoption depends on that scorecard.
3. Token planning assumption (founder to confirm): a Room uses about 150K input and 6K output tokens (CR240 scorecard median). If 200 testers run 10 Rooms a month, that is about 312M tokens per month **(arithmetic on assumed use)**. The 2B free tokens would cover several months of that. Pricing and the free quota were **not verified** on the Model Studio pages read today.
4. **Company rule to state if asked:** the app uses no Anthropic models. Alpha runs on our own hardware with a backup provider. Beta's current model is DeepSeek-V4-Flash through DeepInfra (gate S2). Model Studio would be a third provider, and a new LLM vendor needs the founder's approval before any production use.

**What we ask Alibaba for.** Credits for ECS and Model Studio, and an expert session on running Qwen models for structured, schema-bound output, which our Rooms need.

**Offer in return.** Case study and public listing once Beta is live (terms already allow Alibaba to list the company).

## 5. Founder to do, in order

1. Create or confirm a business mailbox on `agenticmarketintel.ai`. Settle the mail path (cPanel versus Cloudflare Email Routing) first.
2. Fill the **[founder to fill]** items: incorporation date, registration number, headcount, company LinkedIn or X, phone, funding and revenue figures.
3. Open https://www.cloudflare.com/lp/startups in a browser, read the real fields, paste the drafts from 3.3 to 3.5, submit. Review is up to 48 hours.
4. Create an Alibaba Cloud account yourself. Then open https://www.alibabacloud.com/startup/ai, read the real fields, paste from section 4, submit. Answer in 4 to 5 business days.
5. After Cloudflare approval, email startups@cloudflare.com and ask whether Containers usage draws down credits, if Containers is still an option at S4.
6. Do not rely on either award for the Beta start date. Neither is guaranteed.

## 6. Could not verify (2026-11-20)

1. **Both application forms.** Cloudflare's form returned HTTP 403; Alibaba's form is embedded and no field list is on the page. Field lists above are expectations, not the real forms.
2. **Alibaba eligibility rules.** The program page states none today; the 2026-11-19 file's criteria are not on the page now.
3. **Alibaba credit validity period**, and whether Malaysia-registered companies are accepted (neither page says).
4. **Whether a mailbox exists on the domain**, and whether Cloudflare Email Routing would break it.
5. **Model Studio token prices and free-quota rules** (pages read did not show them), and **Kuala Lumpur ECS price from Alibaba itself**.
6. **Whether Cloudflare Containers is covered by the credits.**
7. **Company facts** the repo cannot give: incorporation date, registration number, headcount, revenue, funding, LinkedIn and X pages.
