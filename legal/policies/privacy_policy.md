# Privacy Policy — AMI Trade

> **DRAFT — pending lawyer review.** Not legally binding until reviewed and signed off by counsel. The "Inspired by" footnotes after each clause cite the peer document that informed the starter language; they are not part of the published policy and should be removed before publishing.

**Version:** 2.0 (alpha)
**Effective:** 23 July 2026
**Contact:** privacy@agenticmarketintel.ai
**Published HTML:** `website/privacy/index.html` → `https://www.agenticmarketintel.ai/privacy/`
**Publishing process:** see [`VERSIONING.md`](../VERSIONING.md)

---

## Who we are

AMI Trade is a mobile training and education simulator that lets you direct a team of 12 AI analyst agents and one AI Concierge to research markets and run simulated trades. The app is operated by AMI ("we," "us," "our"). This policy explains what personal information we collect about you, how we use it, who we share it with, and the rights you have over it.

This Privacy Policy applies to the AMI Trade mobile app and to the limited account-related interactions on our marketing website at `agenticmarketintel.ai`. For the rules of using the service itself, see our [Terms of Service](terms_of_service.md).

---

## 1. Anonymous identifier on first launch

When you first open AMI Trade, we create an anonymous, device-bound identifier so you can use the app immediately without registering. This identifier is **not tied to your real-world identity** until you choose to claim the account via Sign in with Apple or Sign in with Google.

While you are anonymous, the only personal information we hold for you is whatever you generate inside the app (chat messages, journal entries, simulated trades), tied to that anonymous identifier.

> _Inspired by: novel — no peer document addresses an anon-first onboarding pattern of this kind._

## 2. What we collect when you claim your account

When you choose to convert your anonymous account into a permanent account, we collect:

- The email address you authorise Apple or Google to share with us
- The name as supplied by Apple or Google (you may choose to share a real name or a private relay alias from Apple)
- An authentication identifier from Apple or Google so we can recognise you on future sign-ins

We do not see, store, or process your Apple or Google password.

> _Inspired by: [Zoya Privacy Policy](https://zoya.finance/privacy)._

## 3. What we collect when you use the AMI agents

We collect the prompts you send to our AMI analyst agents and the responses returned, including:

- Chat messages with the Concierge or any of the 12 analyst agents
- Journal entries you write inside the app
- The structured analyses produced for each ticker when you convene the Room (the multi-agent debate)
- Brief Your Agent feedback you provide

> _Inspired by: [Character.AI Privacy Policy](https://character.ai/privacy)._

## 4. What we collect when you submit a bug report

If you use the in-app bug reporter, we collect:

- The category, title, and any reproduction steps you write
- The route in the app where the bug was reported and your app version and platform
- Any screenshot or photo you choose to attach

Photo attachments are uploaded to our servers and stored for the duration of the support ticket plus a 30-day grace window, after which they are deleted automatically.

> _Inspired by: novel — pattern borrowed from generic SaaS support tooling._

## 5. What we collect about your device

We collect:

- Device model, operating-system version, and AMI Trade app version
- Crash diagnostics — captured by [Sentry](https://sentry.io), which acts as our data processor under a standard data-processing agreement
- Basic request metadata (timestamps, IP address at the time of request) needed to operate the service

We do **not** collect advertising identifiers, location data, contacts, your photo library other than the bug-report attachment you explicitly choose, or any biometric data.

> _Inspired by: [Sentry mobile-privacy docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/) and [Zoya Privacy Policy](https://zoya.finance/privacy)._

## 6. Why we collect this information

We collect and process the information described above for the following purposes:

- To operate the service and the AMI analyst agents
- To audit and improve agent output for safety, accuracy, and quality
- To prevent fraud, abuse, and violation of our Terms of Service
- To respond to support requests and bug reports

> _Inspired by: [Character.AI Privacy Policy](https://character.ai/privacy)._

## 7. Who we share your information with

We share limited data with the following service providers, each acting as a data processor under contract:

- **Apple and Google** — sign-in only; we receive the identifiers and email described in clause 2 and nothing more
- **RevenueCat** — to manage your subscriptions, credit-pack purchases, and renewal status
- **Sentry** — to capture and analyse crash diagnostics

The AMI analyst agents are powered by a large language model. Our primary AI infrastructure is self-hosted on servers we operate. In some circumstances — for example, to maintain service reliability — a request may be routed to a third-party AI infrastructure provider operating under contract, bound by confidentiality and data-protection obligations equivalent to our own (see clause 8). In every case, your prompts and the agents' responses are used only to generate your session's output — never to train models for other customers, and never sold or shared with advertisers or data brokers.

We do not sell your personal information and we do not share it with advertisers, data brokers, or AI training providers.

> _Inspired by: [RevenueCat Apple App Privacy disclosures](https://www.revenuecat.com/docs/platform-resources/apple-platform-resources/apple-app-privacy) and [Sentry mobile-privacy docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/)._

## 8. Where your AMI agent conversations are processed

AMI Trade is built around a self-hosted AI infrastructure model: the large majority of your conversations with the AMI Concierge and the 12 analyst agents are processed entirely on infrastructure we operate. As described in clause 7, a request may occasionally route through a contracted third-party AI infrastructure provider — for example, if our own infrastructure is unavailable. We do not sell access to your conversations, use them to train third-party foundation models, or share them with advertisers, regardless of which infrastructure processes a given request.

> _Inspired by: novel — this is a real differentiator we want to surface, corrected in v2.0 (AT:legal CR068 / DEF085, 2026-07-23) to stop overstating infrastructure isolation as absolute. v1.0 claimed prompts were "not sent to any third-party AI vendor," which conflicted with `disclaimers_and_privacy.md`'s own sub-processor list and `stack.md`'s documented Anthropic fallback. This version is deliberately generic — it does not name a specific third-party provider, since the identity of any fallback vendor is an infrastructure detail that can change without being a material change to what's disclosed here (self-hosted primary, contracted fallback, no training/resale in either case)._

## 9. How long we keep your agent conversations

Prompts you send to AMI agents, and the responses returned, are retained in our LLM audit log for **90 days** for safety and quality review, and are then deleted. This retention period applies to chat messages, Convene-the-Room sessions, and Brief Your Agent feedback.

> _Inspired by: tighter than the open-ended "as necessary" wording in [Character.AI's policy](https://character.ai/privacy); the explicit 90-day cap is an AMI commitment._

## 10. How long we keep your account data

Account-level data (your sign-in identifier, journal entries, simulated portfolios, lesson progress) is retained while your account is active and for a reasonable period after closure, or as required by law.

> _Inspired by: [StockTrak Privacy Policy](https://www.stocktrak.com/privacy-policy/)._

## 11. Inactive anonymous accounts

Anonymous accounts that are never claimed and have been inactive for 12 months are purged automatically. All associated data (journal, simulated portfolio, agent conversations) is deleted at the same time.

> _Inspired by: [StockTrak Privacy Policy](https://www.stocktrak.com/privacy-policy/) — 12-month inactivity rule._

## 12. Your rights — GDPR, PDPA, CCPA / CPRA

You may request to:

- **Access** the personal data we hold about you
- **Correct** information that is inaccurate
- **Export** your data in a portable, machine-readable format
- **Delete** your account and the personal data tied to it

The fastest way to request account or data deletion is our [account deletion page](https://agenticmarketintel.ai/ami-trade/sad-to-see-you-go) (see [`data_deletion_policy.md`](data_deletion_policy.md) for the canonical source), which also explains exactly what is deleted and what we retain. To exercise any of these rights you may also email **privacy@agenticmarketintel.ai**. We aim to respond within 30 days.

- Residents of the European Union and the United Kingdom have rights under the **GDPR** and the UK GDPR
- Residents of California have rights under **CCPA / CPRA**, including the right not to be discriminated against for exercising those rights
- Residents of Malaysia have rights under the **Personal Data Protection Act 2010 (PDPA)**

> _Inspired by: [Zoya Privacy Policy](https://zoya.finance/privacy) and [StockTrak Privacy Policy](https://www.stocktrak.com/privacy-policy/)._

## 13. Children

AMI Trade is intended for users aged **18 and over**. We do not knowingly collect personal data from anyone under 18. If we learn that we have collected personal data from a person under 18, we will delete it. If you believe a child has provided us with personal information, please email privacy@agenticmarketintel.ai.

> _Inspired by: [Zoya Privacy Policy](https://zoya.finance/privacy) — verbatim pattern._

## 14. Halal and other values-based preferences

If you enable Halal/Shariah screening, no-fossil-fuels screening, or other values-based filters, we treat the choice strictly as a **product preference setting**. We do not use it to infer, store, or share data about your religion, beliefs, or political views. These preferences are stored alongside your other in-app settings and are not used for advertising, profiling, or analytics.

> _Inspired by: novel — explicit GDPR Article 9 ("special categories") risk mitigation._

## 15. Cookies

The AMI Trade mobile app does **not** use cookies.

Our marketing website at `agenticmarketintel.ai` uses essential cookies (required for the site to function) and may use analytics cookies. Where required by law, a cookie banner on the website asks for your consent before analytics cookies are set. See the website's cookie notice for details.

> _Inspired by: [Zoya Privacy Policy](https://zoya.finance/privacy)._

## 16. Changes to this policy

We may update this Privacy Policy from time to time. For **material changes** — changes that meaningfully expand what data we collect, how we share it, or how long we keep it — we will give you at least **14 days' notice** before they take effect. Notice will be given via an in-app banner or by email to the address tied to your claimed account.

> _Inspired by: [StockTrak Privacy Policy](https://www.stocktrak.com/privacy-policy/)._

---

## § Version history

- **v2.0** — effective 23 July 2026. Corrected clauses 7 and 8: v1.0 stated prompts "are not sent to any third-party AI vendor," an absolute claim that conflicted with internal sub-processor records (Anthropic fallback, per `stack.md` and `disclaimers_and_privacy.md`). v2.0 accurately describes self-hosted-primary / contracted-third-party-fallback routing, without naming a specific vendor. Added a direct link to the new [Data Deletion Policy](data_deletion_policy.md) in clause 12. Filed as [DEF085](../../docs/defect/DEF085_privacy_ai_vendor_claim/DEF085_privacy_ai_vendor_claim.md) (the inaccuracy) under [CR068](../../docs/forward_planning/CR068_legal_docs_hardening/CR068_legal_docs_hardening.md) (the broader legal-docs pass).
- **v1.0** — effective 18 May 2026. Initial alpha-stage policy published with AMI Trade closed alpha. Earlier versions: none. Archived at [`../history/privacy_policy/v1.0_2026-05-18.md`](../history/privacy_policy/v1.0_2026-05-18.md).

When a new version is published, the previous version is preserved at `/privacy/v<N>/` (website) and `legal/history/privacy_policy/` (markdown source) for audit. Material changes are notified per clause 16 with at least 14 days' notice.

---

## Contact

For any question about this Privacy Policy, or to exercise any of the rights described above, contact:

**privacy@agenticmarketintel.ai**

---

## Document status

This is a draft prepared from the clause-by-clause plan in [`legal_plan_ami_trade.md`](../docs/initial_specs/09_compliance/legal_plan_ami_trade.md). It must be reviewed and signed off by counsel before being published at `agenticmarketintel.ai/legal/privacy.html` and referenced from the App Store / Play Store listings.
