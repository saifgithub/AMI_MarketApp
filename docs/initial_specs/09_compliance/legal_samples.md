# Legal Samples — Research notes for AMI Trade ToS + Privacy Policy

Raw research. **Not legal copy.** Every quote below is borrowed from a peer app's public legal document and is cited inline. Use this as a clause bank for the AMI Trade drafts in `legal_plan_ami_trade.md`.

Sampling principle: stock simulators are the closest analogue (same "no real money, no advice" framing), AI-chat apps cover LLM-output disclaimers, and Zoya covers the Halal-finance angle.

---

## Sample A — Wall Street Survivor (stock simulator, contest format)

- ToS URL: https://www.wallstreetsurvivor.com/terms-and-conditions/
- Privacy URL: https://www.stocktrak.com/privacy-policy/ (Wall Street Survivor delegates to StockTrak's policy)
- Last fetched: 2026-05-15

### Disclaimer / not-investment-advice
> "Wall Street Survivor is not an investment advisory service, nor is it a registered investment advisor or broker-dealer" — [ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)

> "THIS SITE DOES NOT OFFER, SOLICIT OR ARRANGE FOR THE SALE OR PURCHASE OF SECURITIES… ALL INFORMATION IS PROVIDED FOR ENTERTAINMENT AND RECREATIONAL PURPOSES ONLY." — [ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)

### User-generated content license
> "you automatically grant… to Wall Street Survivor, an irrevocable, perpetual, non-exclusive… license to use, copy, perform, display and distribute such information" — [ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)

### Limitation of liability (the floor)
> "aggregate liability… shall not exceed the amounts actually paid by YOU… or the amount of FIFTY DOLLARS ($50), whichever is greater" — [ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)

### Termination
> "Wall Street Survivor may, in its sole discretion, for any reason, terminate your account on the site, without any liability" — [ToS](https://www.wallstreetsurvivor.com/terms-and-conditions/)

### Retention (StockTrak)
> "Personal Information and other data of inactive users gets purged from our database after 12 months of inactivity for participants and up to 60 months for instructors / administrators" — [StockTrak Privacy](https://www.stocktrak.com/privacy-policy/)

### Children
> "For persons under the age of 18, the only Personal Information we collect at the time of registration is their first name and the first initial of their last name" — [StockTrak Privacy](https://www.stocktrak.com/privacy-policy/)

---

## Sample B — Public.com (real-money broker, but has AI + simulation features)

- ToS URL: https://public.com/disclosures/terms-of-service
- Last fetched: 2026-05-15

Public is a real broker, so most of its ToS is irrelevant. The bits worth borrowing are the **AI-feature disclaimer** and the **simulation/backtest disclaimer** — both rare to find phrased this cleanly in one document.

### Educational / not-investment-advice
> "THE CONTENT PRESENTED ON THE SERVICES ARE NOT INTENDED TO PROVIDE YOU OR ANYONE ELSE WITH INVESTMENT, LEGAL, TAX, INSURANCE OR ANY OTHER KIND OF PROFESSIONAL ADVICE" — [Public ToS](https://public.com/disclosures/terms-of-service)

### AI-output disclaimer (rare in finance apps, very on-point for us)
> "Alpha is an experimental AI research tool from Public Holdings, Inc. It may produce inaccurate or inappropriate responses and is not investment research or a recommendation." — [Public ToS](https://public.com/disclosures/terms-of-service)

> "Outputs from Agentic Brokerage are provided for informational and illustrative purposes only, and should not be considered investment recommendations or advice." — [Public ToS](https://public.com/disclosures/terms-of-service)

### Simulation / hypothetical returns disclaimer
> "Returns displayed by the backtest are hypothetical in nature, do not reflect actual investment results, and are not guarantees of future results." — [Public ToS](https://public.com/disclosures/terms-of-service)

### Liability cap
> "AGGREGATE LIABILITY… IS LIMITED TO THE GREATER OF: (A) THE AMOUNT YOU HAVE PAID TO PUBLIC.COM… IN THE 12 MONTHS PRIOR… OR (B) $100." — [Public ToS](https://public.com/disclosures/terms-of-service)

---

## Sample C — Character.AI (AI-chat, mass-market, lots of UGC)

- Privacy URL: https://character.ai/privacy (and policies.character.ai/privacy)
- Last fetched: 2026-05-15

Closest analogue for the **LLM I/O, photo upload, and chat-message retention** questions.

### User content collected
> "chat communications, posted images or videos, biography description, and shared Characters" — [Character.AI Privacy](https://character.ai/privacy)

### Why they keep it (model training, ops)
> "train our artificial intelligence/machine learning models" and "Develop new features, algorithms and machine learning models" — [Character.AI Privacy](https://character.ai/privacy)

### Retention (soft — they don't commit to a window)
> "for the time necessary for the purposes for which it is processed" — [Character.AI Privacy](https://character.ai/privacy)

### Children's age
> "The Services are not designed for minors under 13" (under 16 in EEA/UK) — [Character.AI Privacy](https://character.ai/privacy)

### Account deletion
> "You may delete your account through your account profile page" and request "access to and/or a copy of certain information we hold about you" — [Character.AI Privacy](https://character.ai/privacy)

### Notable gap
Anonymous / guest accounts are **not addressed** in the privacy policy — useful gap to flag because AMI Trade *does* create anon accounts on first launch.

---

## Sample D — OpenAI / ChatGPT consumer (LLM output disclaimers, gold standard wording)

- ToS URL: https://openai.com/policies/row-terms-of-use/
- Note: WebFetch blocked by 403; quotes below are from secondary citations on policyforge.co and amstlegal.com summaries of the OpenAI consumer terms.

### Probabilistic / accuracy disclaimer (the cleanest phrasing in the industry)
> "use of our Services may result in Output that does not accurately reflect real people, places, or facts" — [OpenAI Terms (summarised)](https://openai.com/policies/row-terms-of-use/)

> "You should not rely on Output from our Services as a sole source of truth or factual information, or as a substitute for professional advice." — [OpenAI Terms (summarised)](https://openai.com/policies/row-terms-of-use/)

This is the phrasing pattern to copy for AMI's 12-agent output. The "sole source of truth" framing is more useful than a bare "may be inaccurate."

---

## Sample E — Zoya (Halal-finance, mobile-first, US/UK/CA stocks — the closest market analogue)

- Privacy URL: https://zoya.finance/privacy
- Last fetched: 2026-05-15

This is the most directly comparable app in the sample set: mobile, screening-only (not a broker), stocks, religious-compliance flavour. **Borrow heavily from this one.**

### Shariah-compliance disclaimer (perfect tone for AMI's Halal switch)
> "The content on this website is for informational purposes only. Zoya does not recommend any specific securities or investment strategies." — [Zoya Privacy](https://zoya.finance/privacy)

### Data collected
> "Email address, First name and last name, Phone number, Cookies and Usage Data" plus "IP address, browser type, browser version, the pages of our Service that you visit" — [Zoya Privacy](https://zoya.finance/privacy)

### Retention (vague but standard)
> "Investroo Inc. will retain your Personal Data only for as long as is necessary for the purposes set out in this Privacy Policy." — [Zoya Privacy](https://zoya.finance/privacy)

### Third parties (note Sentry mention — same tool we use)
> "Sentry is an application monitoring platform that captures and reports software errors and performance issues." — [Zoya Privacy](https://zoya.finance/privacy)

### Children
> "Our Service does not address anyone under the age of 18. We do not knowingly collect personally identifiable information from anyone under the age of 18." — [Zoya Privacy](https://zoya.finance/privacy)

**Implication for us:** an 18+ age gate is standard for finance-flavoured apps, even education-only ones. This is stricter than Character.AI's 13/16. Apple's App Review tends to be more comfortable with an 18+ gate on "finance" apps.

---

## Required third-party disclosures (vendor docs, not peer policies)

These are non-negotiables flagged by the vendors themselves.

### RevenueCat (IAP backbone)
> "you must disclose that your app collects 'Purchases' information from the App Privacy tab in App Store Connect… All RevenueCat users must select Analytics… and 'App Functionality'" — [RevenueCat — Apple App Privacy](https://www.revenuecat.com/docs/platform-resources/apple-platform-resources/apple-app-privacy)

### Sentry (crash telemetry)
> "Sentry is a third-party partner whose code (SDKs) you integrate in your app that collects data from users of your app. In such cases, we act as a data processor" — [Sentry mobile privacy docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/)

> "You would need to disclose all types of data you are collecting through your app, including data you are sending to Sentry." — [Sentry mobile privacy docs](https://docs.sentry.io/security-legal-pii/security/mobile-privacy/)

---

## What nobody covers well

Gaps across the whole sample set — places AMI Trade has to think for itself instead of copying:

1. **Anonymous-first onboarding.** None of the sampled apps (Character.AI, Zoya, Public, WSS) describe how an anon ID becomes a claimed account, what happens to anon-era data on claim, or what happens if a user never claims and just deletes the app. This is novel for us.
2. **Bug-reporter photo uploads.** Sample apps either don't allow uploads (WSS, Zoya) or treat them as part of chat (Character.AI). None spell out "support attachment" handling — retention, who reviews them, whether they're auto-deleted on ticket close. We should write this from scratch.
3. **Hard retention windows for LLM I/O.** Character.AI and OpenAI both say "as long as necessary" — a non-commitment. AMI's 90-day audit window is **shorter and more specific** than anything in the peer set. That's a feature, not a bug — call it out as a differentiator.
4. **On-prem LLM as a privacy story.** Every peer app sends prompts to a third-party model provider. AMI runs Gemma 4 31B on melehost. None of the samples have language for "the model is ours, your prompts don't leave our infrastructure to a third-party AI vendor." This is a real differentiator worth a clause.
5. **Compliance-switch implications.** When a user opts into Halal screening, their religious affiliation can arguably be inferred — that's a special category of personal data under GDPR Art. 9. None of the peer apps deal with this. Zoya's whole user base is implicitly Muslim, so they sidestep it. For us, where Halal is *one of several* opt-in filters, we may need explicit consent language.
6. **Liability cap floor.** WSS picked $50; Public picked $100 or 12 months of fees. Both are far below typical SaaS caps. **The "greater of $X or fees paid in 12 months" pattern is the consumer-app standard.** Pick a small floor — $50–$100 — to keep the cap meaningful for free-tier users.
