# Risks & Mitigations

What could go wrong, and what we do about each.

## Build risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **App Store rejects on "financial advice" framing** | Medium | High | Lead with "educational simulation" everywhere. Disclaimer in screenshots. Provide reviewer notes. Submit early to leave buffer for re-submission. |
| **Apple Privacy Manifest requires more declarations than expected** | Low | Medium | Build manifest declaratively from data-model knowledge; iterate against App Store feedback |
| **LLM cost spike during dev/testing** | Medium | Medium | Spending limits per env. Cheap models for dev. Premium models behind feature flags. |
| **OpenRouter latency / outages** | Low–Medium | Medium | Direct provider keys as fallbacks. Multi-provider routing handles transparent failover. |
| **Supabase Realtime quirks at scale** | Low | Medium | Test under load before launch. Fall back to long-poll if needed. |
| **TradingAgents framework breaking change** | Low | Medium | Pin to a specific version. Test upgrades in isolation. We don't *modify* their code, just wrap it. |
| **Hex design fidelity on Flutter takes longer than expected** | Low | Low | We have AMI design system spec. Most hex shapes are pure math + ClipPath. |
| **Anonymous → claim edge cases** | Medium | Medium | Automated tests for all 5 paths (success, collision, abandoned, expired, multi-device) |
| **TradingAgents response quality lower than expected on certain mandates** | Medium | Medium | W6 budget for prompt tuning. Multiple models tested per agent. Track quality in Decision Journal — Founders feedback drives improvements. |
| **Drafting 100 lessons by W11 too aggressive** | Medium | Low | If behind by W6, reduce to 80 high-quality lessons. Quality > quantity. Or extend Claude's content production to 12–15 lessons/week. |

## Operational risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Saiful unavailable for 2+ weeks** | Low–Medium | Medium | Claude continues coding within agreed scope. Park decisions in `open_questions.md`. Don't ship without approval. |
| **Domain registrar issue with `agenticmarketintel.ai`** | Very low | High | Domain locked, multi-factor auth on registrar account. Annual renewal alerts. |
| **GCP / Supabase service outage** | Low | High | Both have ≥99.9% SLAs. Cloudflare-fronted CDN provides limited offline-cached responses. |
| **Twilio SMS delivery failure rate in KSA** | Medium | Low | Magic-link is the fallback. We monitor delivery rates. |
| **App Store review takes 2+ weeks unexpectedly** | Low | Medium | Submit W11; W12 has 1-week buffer. If serious delay: TestFlight builds keep moving to Founders. |
| **Founders cohort recruitment slow** | Medium | Low | Saiful's network is the seed. HN/Twitter post is the public push. ~100 users is enough to learn from. |
| **GCP cost spike (runaway test, bug)** | Low | Medium | Budget alerts at $500, $1000 thresholds. Daily LLM cost monitoring in PostHog. |

## Market & strategic risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Finelo launches a directly competing AI feature** | Medium | Medium | Our moat is depth: 12 agents, mandate-driven, Brief Your Agent. A "we have AI now" Finelo update doesn't match. |
| **Big-tech competitor (Google / Apple) ships similar product** | Low | High | Hard to defend against, but the AR/MS + halal + dual-gating positioning is distinctive. Big tech goes mass-market, not niche. |
| **Regulatory shift — sim-only apps required to register** | Low | High | Our advisory-only-simulation-only posture is the regulatory firewall. We monitor; if rules change, we adapt. |
| **AR/MS markets adopt slower than expected** | Medium | Medium | Founders Pricing + Launch-Country Promo accelerate. EN remains a strong path. |
| **Halal-screening positioning controversial somehow** | Low | Low | We frame as user-choice (a mandate flag), not as endorsement. |
| **App Store + Play Store policy change against AI-finance apps** | Low | Medium | Stay updated on guidelines. Our positioning is education, not finance, which is the safer category. |

## Quality & content risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Agent quality embarrassing in early Founders sessions** | Medium | High | Internal testing in W6. Saiful private alpha at W8. Real Founders not until W12. |
| **Lesson content has factual errors** | Low | Medium | Saiful reviews every lesson before publication. Native finance-literate reviewer for AR + MS at v1.0. |
| **Translation quality degrades user trust** | Medium | High | Glossary lock before translation begins. Native QA per language. Saiful insists on quality. |
| **AI-tutor wrapper produces awkward output** | Medium | Low | Wrapper is cheap to iterate. Real Founder feedback informs prompt tuning. |
| **Concierge gives trading advice accidentally** | Low | High | Concierge system prompt forbids advice. Test suite includes "try to get advice" tests. Safety floor logs route to support. |

## Legal & compliance risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Privacy Policy doesn't satisfy Saudi PDPL nuance** | Medium | Medium | Lawyer review specifically for KSA. Update post-launch as PDPL guidance evolves. |
| **Disclaimer wording insufficient for some jurisdiction** | Low | Medium | Standard educational-simulation language is well-tested across markets. Lawyer reviews. |
| **User claims they were "advised" badly by an agent and lost money** | Very low (sim only, no real money) | Low | Disclaimers everywhere. Sim-only is the regulatory firewall. |
| **Ad partner serves a banned-category ad despite filters** | Medium | Medium | Strict programmatic filters. Weekly review reports. User report mechanism. |
| **GDPR DSAR (Data Subject Access Request) handling fails** | Low | Medium | Settings → Export Data + Delete Account flow. 30-day SLA tracked. |

## Saiful-as-bottleneck risks

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| **Saiful gets sick / burnt out during the 12-week sprint** | Medium | Medium | Realistic pacing. Buffer week (W11) built in. Claude can keep coding within scope without Saiful for 1–2 weeks. |
| **Saiful's day-job / family obligations conflict** | Medium | Medium | Same. Communication early; adjust timeline if needed. |
| **Decision fatigue — too many small calls** | Medium | Low | Claude triages — only escalate decisions that need a human. Park ambiguous ones in `open_questions.md`. |

## Risk monitoring

We don't need a fancy risk register. Monthly:
- Review this doc
- Note any new risks
- Note any mitigations that aren't working
- Update probabilities

Saiful's monthly self-check question: *"Of the things on the risks list, which one is closest to biting us?"*

## Cross-references

- Timeline buffer: [`timeline.md`](timeline.md)
- Alpha scope: [`stealth_alpha_scope.md`](stealth_alpha_scope.md)
- Pre-alpha checklist: [`pre_alpha_checklist.md`](pre_alpha_checklist.md)
- Compliance specifics: [`docs/09_compliance/`](../09_compliance/)
