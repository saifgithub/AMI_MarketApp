# Legal plan — AMI Trade Privacy Policy + ToS

**Status: research output for lawyer review. Not legally binding copy.**

This is the clause-by-clause plan and starter language for AMI Trade's Privacy Policy and Terms of Service, distilled from the peer sample set in [`legal_samples.md`](legal_samples.md). Every draft below is borrowed from / inspired by a cited peer document. Hand this to counsel for review and signoff before publishing.

> **The published drafts now live in [`legal/`](../../../legal/README.md)**, not here (moved
> 2026-07-23, AT:legal CR068). This document stays as the traceability record of what informed
> them.

---

## Privacy Policy — clause map

| # | Clause | Starter language (lawyer to review) | Inspired by |
|---|---|---|---|
| 1 | **What we collect — anon ID** | "When you first open AMI Trade, we create an anonymous device-bound identifier to give you immediate access to the app without requiring an account. This identifier is not tied to your real-world identity until you choose to claim the account via Sign in with Apple or Google." | (Novel — no peer covers this) |
| 2 | **What we collect — claimed account** | "When you claim your account, we collect: email address, name as provided by Apple/Google, and an authentication identifier from your sign-in provider." | [Zoya](https://zoya.finance/privacy) |
| 3 | **What we collect — LLM inputs/outputs** | "We collect the prompts you send to our AMI analyst agents and the responses returned, including chat messages, journal entries, and the structured analyses produced for each ticker." | [Character.AI](https://character.ai/privacy) |
| 4 | **What we collect — bug-report photos** | "If you use the in-app bug reporter, any screenshot or photo you attach is uploaded to our servers and stored for the duration of the support ticket plus a 30-day grace window, after which it is deleted." | (Novel — no peer covers this; pattern borrowed from generic SaaS support tooling) |
| 5 | **What we collect — device + crash data** | "We collect device model, OS version, app version, and crash diagnostics. Crash diagnostics are processed by Sentry, which acts as our data processor." | [Sentry mobile docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/), [Zoya](https://zoya.finance/privacy) |
| 6 | **Why we collect (purpose)** | "To operate the service, audit and improve AMI agent output for safety and quality, prevent fraud and abuse, and provide support." | [Character.AI](https://character.ai/privacy) |
| 7 | **Who we share with** | "Apple and Google (sign-in only), RevenueCat (subscription and purchase management), Sentry (crash diagnostics). The AMI analyst LLM runs on infrastructure we operate; your prompts and responses are not sent to a third-party AI vendor." | [RevenueCat](https://www.revenuecat.com/docs/platform-resources/apple-platform-resources/apple-app-privacy), [Sentry](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/) |
| 8 | **On-prem LLM differentiator** | "Unlike services that route your prompts to a third-party AI provider, the AMI analyst agents are powered by a large language model we host ourselves. Your conversations with AMI agents stay within AMI infrastructure." | (Novel — call this out, it's a real differentiator) |
| 9 | **Retention — LLM audit log** | "Prompts and AMI agent responses are retained in our audit log for 90 days for safety review, then deleted." | (Tighter than [Character.AI's](https://character.ai/privacy) "as necessary" — this is the AMI differentiator) |
| 10 | **Retention — claimed accounts** | "Account-level data is retained while your account is active and for a reasonable period thereafter, or as required by law." | [StockTrak](https://www.stocktrak.com/privacy-policy/) |
| 11 | **Retention — inactive anon accounts** | "Anonymous accounts that are never claimed and have been inactive for 12 months are purged." | [StockTrak](https://www.stocktrak.com/privacy-policy/) (12-month inactivity rule) |
| 12 | **User rights — GDPR / PDPA / CCPA / CPRA** | "You may request access to, correction of, export of, or deletion of your personal data by contacting privacy@agenticmarketintel.ai. EU/UK users have rights under GDPR; California residents under CCPA/CPRA; Malaysian users under PDPA 2010." | [Zoya](https://zoya.finance/privacy), [StockTrak](https://www.stocktrak.com/privacy-policy/) |
| 13 | **Children** | "AMI Trade is intended for users aged 18 and over. We do not knowingly collect personal data from anyone under 18." | [Zoya](https://zoya.finance/privacy) — verbatim pattern |
| 14 | **Halal / compliance switches as sensitive data** | "If you enable Halal/Shariah screening, no-fossil-fuels, or other values-based filters, we treat this as a preference setting; we do not infer or store data about your religion, beliefs, or political views." | (Novel — protects us against GDPR Art. 9 special-category claims) |
| 15 | **Cookies (website only)** | "Our mobile app does not use cookies. Our marketing website at agenticmarketintel.ai uses essential cookies and may use analytics cookies; see the website cookie banner for details." | [Zoya](https://zoya.finance/privacy) |
| 16 | **Changes to this policy** | "We will notify you of material changes via in-app notice or email at least 14 days before they take effect." | [StockTrak](https://www.stocktrak.com/privacy-policy/) |

---

## Terms & Conditions — clause map

| # | Clause | Starter language (lawyer to review) | Inspired by |
|---|---|---|---|
| 1 | **Simulation-only — the big one** | "AMI Trade is a training and education simulator. It does not offer, solicit, or arrange the sale or purchase of any security. All trades, portfolios, and returns shown in the app are simulated and do not reflect real investment results." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) — closest peer phrasing |
| 2 | **Not investment advice** | "Nothing in AMI Trade is intended to provide investment, legal, tax, or any other professional advice. AMI is not a registered investment adviser or broker-dealer in any jurisdiction." | [Public.com](https://public.com/disclosures/terms-of-service) + [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) |
| 3 | **LLM output disclaimer (the AI one)** | "The AMI analyst agents are AI systems. Their output may be inaccurate, incomplete, or out of date, and may not reflect real companies, prices, or events. You should not rely on AMI agent output as a sole source of truth or as a substitute for professional advice." | [OpenAI](https://openai.com/policies/row-terms-of-use/) — "sole source of truth" framing |
| 4 | **Hypothetical returns disclaimer** | "Simulated portfolio performance shown in AMI Trade is hypothetical, does not reflect actual trading, and is not a guarantee of future results." | [Public.com](https://public.com/disclosures/terms-of-service) |
| 5 | **Acceptable use** | "You may not: (a) use the service for any unlawful or fraudulent purpose; (b) scrape, mirror, or programmatically extract content; (c) harass other users via shared content; (d) use AMI agent output for commercial purposes including resale, repackaging, or training other AI systems." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) + (novel: anti-training clause) |
| 6 | **Subscriptions & credits** | "Subscriptions and credit packs are purchased through Apple or Google in-app purchase. Billing, renewals, and most refunds are governed by the platform store's policies. Credits, once consumed, are non-refundable." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) (subscription non-refundable pattern) |
| 7 | **User-generated content license** | "You retain ownership of your journal entries, chat messages with agents, and bug reports. You grant AMI a non-exclusive, worldwide, royalty-free license to host, store, display, and process your content solely to operate, secure, and improve the service." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) — but narrowed (we don't need "irrevocable, perpetual" for our purposes) |
| 8 | **AMI's IP** | "The AMI Trade app, the AMI design system, the 12-agent framework, agent prompts, and all related content are owned by AMI or its licensors." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) |
| 9 | **Account claim flow** | "You may use AMI Trade with an anonymous account or claim a permanent account via Sign in with Apple or Google. On claim, your anonymous-era data (journal, simulated portfolio, agent conversations) is migrated to the claimed account. Once claimed, the prior anonymous identifier cannot be re-used." | (Novel — no peer covers this) |
| 10 | **Termination** | "We may suspend or terminate your account if you violate these Terms or if we are required to do so by law. You may delete your account at any time from the in-app settings." | [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) + [Character.AI](https://character.ai/privacy) |
| 11 | **Limitation of liability** | "TO THE MAXIMUM EXTENT PERMITTED BY LAW, AMI's AGGREGATE LIABILITY FOR ANY CLAIM ARISING FROM YOUR USE OF THE SERVICE WILL NOT EXCEED THE GREATER OF (A) THE AMOUNT YOU PAID TO AMI IN THE 12 MONTHS PRIOR TO THE CLAIM OR (B) USD $100." | [Public.com](https://public.com/disclosures/terms-of-service) — verbatim structure |
| 12 | **Disclaimer of warranties** | "AMI Trade is provided 'as is' and 'as available.' We disclaim all warranties to the maximum extent permitted by law, including warranties of accuracy, merchantability, and fitness for a particular purpose." | [OpenAI](https://openai.com/policies/row-terms-of-use/) + [Wall Street Survivor](https://www.wallstreetsurvivor.com/terms-and-conditions/) |
| 13 | **Governing law & dispute resolution** | **PLACEHOLDER — lawyer to fill.** | — |
| 14 | **Changes to terms** | "We may update these Terms. Material changes will be notified in-app at least 14 days before taking effect." | [StockTrak](https://www.stocktrak.com/privacy-policy/) |

---

## Must-confirm-with-lawyer (do NOT freelance these)

These five clauses are the ones where wrong wording creates real risk. Do **not** draft these from peer samples — they're jurisdiction-sensitive and tied to AMI's specific corporate structure.

1. **Governing law & jurisdiction.** Saiful is in Malaysia. Corporate entity TBD. **Resolved 2026-07-23 (CR068), Saiful's explicit call:** no governing-law clause, no named court. The Terms carry no forum-selection language of any kind — risk-shifting is done entirely by §2/§3's assumption-of-risk framing and §14's indemnification. Counsel should still sanity-check this is a defensible position (see the flagged row in `legal/policies/terms_of_service.md`'s "Lawyer-only checklist") before it's relied on outside alpha.
2. **Arbitration clause** (and whether to have one). **Resolved 2026-07-23 (CR068), Saiful's explicit call: no arbitration clause.** A founder-drafted AIAC-Kuala-Lumpur clause existed briefly the same day and was removed at Saiful's direction in favor of pure assumption-of-risk/indemnification. Not revisited unless Saiful reopens it.
3. **Limitation-of-liability cap.** Drafted at $100 above (matching Public). The cap may be void in some jurisdictions (notably DE, FR consumer law). Lawyer to confirm enforceability and consider a jurisdiction-by-jurisdiction carve-out.
4. **Indemnity** (user indemnifies AMI). Not drafted above on purpose. Standard SaaS clause but the scope (esp. for an 18+ consumer app) needs counsel. **Update 2026-07-23 (CR068):** founder-drafted starter language now exists in `legal/policies/terms_of_service.md` §14 — narrowed to ToS violations, off-simulation reliance on agent output, submitted content, and law/third-party-rights violations, with carve-outs for AMI's own misconduct and non-waivable consumer rights. Still not lawyer-reviewed.
5. **Securities-regulator framing.** "Not a registered investment adviser or broker-dealer in any jurisdiction" is a strong, defensible claim because AMI Trade is genuinely simulation-only. But the *exact* wording that satisfies SEC, FCA, MAS (Singapore), and Securities Commission Malaysia simultaneously is a lawyer question. Especially before we open the GCC + MY markets in v1.0.

---

## Minimum viable for App Store submission (Alpha imminent)

App Review will not approve without a public Privacy Policy URL. For the alpha submission, the floor is:

**Privacy Policy (MVP — required for App Store):**
- Clauses 1, 2, 3, 5, 6, 7, 9, 12, 13, 16 from the Privacy table above
- A working privacy@agenticmarketintel.ai inbox (clause 12)
- Hosted at a stable URL (probably `agenticmarketintel.ai/privacy`)

**ToS (MVP — required even though not as strictly enforced):**
- Clauses 1, 2, 3, 4, 6, 10, 11, 12, 13 from the ToS table above

**Skippable until v1.0 (full version):**
- Privacy clauses 4 (photo uploads — only if bug reporter ships to Alpha), 8 (on-prem LLM differentiator — nice to have, not legally required), 11 (anon expiry — needed only once we have a large anon-only user base), 14 (Halal as sensitive data — needed once we open GCC market in v1.0), 15 (cookies — needed only once the marketing site goes up)
- ToS clauses 5 (acceptable use — recommended but not blocking), 7 (UGC license — needed once journal/UGC features are live), 8 (IP — needed when brand value is real), 9 (anon-to-claim — needed once we explain the flow publicly)

**Rule of thumb:** the App Store check passes on a clean simulation disclaimer (ToS clauses 1-4), an age gate at 18+ (Privacy clause 13), and a working data-rights contact (Privacy clause 12). Everything else is hardening for v1.0.

---

## References

- [Wall Street Survivor ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)
- [StockTrak Privacy](https://www.stocktrak.com/privacy-policy/)
- [Public.com ToS](https://public.com/disclosures/terms-of-service)
- [Character.AI Privacy](https://character.ai/privacy)
- [OpenAI consumer ToS](https://openai.com/policies/row-terms-of-use/)
- [Zoya Privacy](https://zoya.finance/privacy)
- [RevenueCat Apple App Privacy disclosures](https://www.revenuecat.com/docs/platform-resources/apple-platform-resources/apple-app-privacy)
- [Sentry mobile privacy docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/)
