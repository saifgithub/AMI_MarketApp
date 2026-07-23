<!--
CR049 — Website Concierge knowledge base.

This file is the ONLY grounding source for the website chatbot and the contact-form
auto-answer. The model is instructed to answer strictly from what's here and to
ESCALATE anything else. Keep it factual, product-level, and free of anything that
could read as investment advice.

Decisions (Saiful, 2026-07-21):
  - Pricing: intentionally NOT published as numbers yet — stays "announced at launch"
    to match the marketing site. Add $14.99 / $34.99 here only when the site does.
  - Agent count: 12 analyst agents + the Concierge = 13 in all. Site standardised on
    "13"; this file says "12 specialist analysts coordinated by the Concierge (13 in all)".

CR072 (2026-07-23):
  - Curriculum figures below are MEASURED, not estimated. Regenerate before changing:
      ls content/lessons/*.en.mdx | wc -l
      grep -h '^track:' content/lessons/*.en.mdx | sort | uniq -c
      python3 -c "import json;print(len(json.load(open('content/glossary/terms.en.json'))))"
  - Do NOT claim every lesson is verified. DEF078 (19 content fixes) and DEF083 are open.
    The true claim is about the gate, not a clean result.
  - Sharia: DEF084 established the halal flag was an allowlist, not a screen. Resolved
    Option 2 — relabelled a curated demonstration universe. CR069 tracks sourcing a real
    compliance indicator. Never tell a user AMI runs a Sharia screen. Halal/Sharia
    questions escalate to a human via classify_escalation(); the entry below exists so a
    reader of this file cannot conclude otherwise.
-->

# AMI — Website FAQ (grounding knowledge)

## What AMI is
AMI (Agentic Market Intelligence) is an Applied AI company — we build AI systems with real
jobs in expert domains. Our first product is **AMI Trade**.

## What AMI Trade is
AMI Trade is a mobile app where you act as the CEO of an AI analyst team. You pick a stock,
and a team of **12 specialist AI analyst agents — coordinated by a 13th, the Concierge —**
research and debate it (fundamentals, technicals/market, news, social sentiment, a Bull and
a Bear, a research manager, risk debaters, a Trader, and a Portfolio Manager). They hand you
a synthesized view; **you make the final call.**

## Simulation only — always
AMI Trade is a **simulation-only trading-education product.** It is not a brokerage, it never
places real trades, and it never handles real money. It exists to help people learn how to
reason about markets. **It does not and will not give investment advice.**

## How it works
1. Pick a stock (US equities at launch).
2. The analyst agents each do their job and debate the thesis.
3. The Portfolio Manager runs a compliance + judgment review against the mandate you set.
4. You get a clear, synthesized decision — and you decide what to do in the simulation.

## Getting started
Onboarding is **anonymous-first**: a conversational Concierge interview helps you set your
"mandate" (your goals, risk tolerance, horizon). You can create/claim an account at the end.
Free to start.

## Pricing
AMI Trade is **free to start** on the Floor Pass tier (ad-supported). Two paid tiers —
**Trader** and **Floor Manager** — unlock more, and credit packs are available. Exact pricing
is announced at launch.

## The curriculum — the AMI Body of Knowledge
AMI Trade carries a full investment curriculum, not just chart-pattern lessons:
**342 lessons across 13 tracks**, plus **208 glossary terms** and daily challenges.

The 13 tracks and their lesson counts: Edge & Process (98), Fundamentals (66), Technical
Analysis (45), Asset Classes (20), News & Macro (19), Risk & Portfolio (16), Foundations
(16), Quant Methods (12), Economics (12), Sentiment & Behaviour (10), Islamic Finance (10),
Ethics & Integrity (10), Decision Evaluation (8).

Two things are distinctive:
- **It is sourced.** The curriculum is written against the field's recognised bodies of
  knowledge — CFA, CMT, FRM — and the primary sources underneath them. Every sourced lesson
  goes through a dual-pass accuracy gate (fact-check, then an adversarial pass that tries to
  refute the finding) designed to catch our own errors. It is an ongoing process, not a
  finished audit — describe the gate, never claim every lesson has been certified correct.
- **The Decision Evaluation track** teaches how to judge analyst and AI output — spotting a
  fabricated number, telling a confident answer from a correct one. That is the discipline
  the product is built around: you are running a team of AI analysts, so knowing when not to
  believe them is the skill.

## Islamic finance and Sharia screening
AMI Trade includes a 10-lesson **Islamic Finance track** covering Sharia investing
principles. **AMI Trade does not currently run a Sharia compliance screen** — the app ships a
small curated demonstration universe for teaching purposes, which is explicitly not a
screen, and the product does not certify any security as Sharia-compliant. Sourcing a real
compliance indicator is planned work, not a shipped feature. Anyone asking whether a
specific security is halal, or relying on AMI for an observance decision, must be routed to
a human — never answer it.

## Markets, languages, platforms
- **Markets:** US equities at launch; GCC/Tadawul and Bursa Malaysia planned later.
- **Languages:** English at launch; Arabic and Malay planned for v1.
- **Platforms:** iOS and Android. Huawei AppGallery planned later.

## Availability
AMI Trade is in **closed alpha** — invite-only on both platforms: iOS through TestFlight,
Android through Play Store internal testing. It is not yet a public download from either
store. Join the early-access waitlist on this site and we send the invite link directly.

## Privacy & your data
Our Privacy Policy and Terms are linked in the site footer. To request access to your data or
deletion of your account/data, use the **Data Request** form (linked in the footer and the
privacy page) — these are handled by a human within 30 days.

## Contact
General questions: **support.ai@agenticmarketintel.ai**, or use the contact form on the site.
