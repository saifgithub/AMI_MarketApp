# External Beta Kit — AMI Trade

**DRAFT — not submitted**

Materials for external TestFlight (iOS) and Play Closed Testing (Android) beta launch. Prepared 2026-09-24 based on shipped features as of `alpha-2026-09-25-1`.

---

## TestFlight Beta App Description (iOS)

**For: App Store Connect > TestFlight > iOS Beta Testers > "What to Test" section (~500–1000 chars)**

---

### Beta App Description

AMI Trade is an AI-first trading education simulator. You manage a team of 12 specialised AI analysts who advise you on paper-money trades tailored to your financial goals, risk tolerance, and personal constraints. Learn to evaluate market opportunities, test strategies without risk, and build decision-making skills in a controlled environment.

**This is a simulation only.** All trades use virtual money. The AI's reasoning is for learning purposes, not investment advice. Past performance—including simulated performance—does not indicate future results.

**Tiers:**
- **Floor Pass (free):** Full simulator access, daily learning challenges, 2 agents at your service.
- **Trader ($14.99/month):** All agents, deeper Room convening, mandate customisation, priority support.

We're gathering feedback from early users to shape the product. Your insights matter.

---

### What to Test

**Use your mandate:** Start by setting your financial goals (returns target, risk tolerance, ESG / Halal screening). The app personalises every agent's response to *your* constraints.

**The Room (marquee feature):** Tap "Convene the Room" on Portfolio or a ticker detail. Watch all 12 agents debate a stock. Their verdicts land in your journal.

**Persistent menu:** Bottom nav stays visible on every page—ticker tape with live quotes, persistent AdMob banner, and smooth page transitions.

**Alpaca paper trading:** If you connect your Alpaca paper account (Settings > Accounts), trade ticket's "destination" picker lets you send orders to Alpaca's simulator or AMI's own. Both respect your mandate.

**Lessons & challenges:** Tap an agent to unlock lessons. "Skip to quiz" lets you jump straight to the assessment. Daily challenges build your rep.

**Portfolio details:** Tap a holding to see its chart (1D, 1W, 1M, 3M, 1Y, 5Y adaptive views), live earnings/dividend dates, and news headlines.

**Watchlist:** Add tickers to watch without holding them. Tap to see quote + quick-action buttons.

**Accessibility:** Text scale, language (EN, AR, MS), Settings tour walkthrough if you get lost.

---

## Google Play Closed Testing Release Notes (Android)

**For: Play Console > Release Management > Closed Testing > Release Notes (max 4000 chars)**

---

### What's New in 0.1.0 (Build 109)

**AI analyst team:** 12 AI agents covering market analysis, research, equity trading, credit research, risk debate, and portfolio management—all personalised to your goals and risk profile.

**Convene the Room:** Watch agents debate investment ideas in real time. Every verdict lands in your journal so you can track your decision-making over time.

**Paper trading:** Simulate trades in AMI's risk-free environment. Connect your Alpaca paper account to route orders there instead. Both paths respect your mandate.

**Persistent chrome:** Ticker tape with live quotes, bottom navigation, and ad banner stay visible as you move between screens for seamless navigation.

**Alpaca order types:** Market orders, limit, stop, stop-limit, and bracket orders (paper account only).

**Lessons & certification:** 270+ lessons unlock agents. Skip the reading and go straight to the quiz if you prefer. Build daily streaks and unlock weekly leagues.

**Watchlist:** Track tickers you're interested in without holding them.

**Charts:** Adaptive candlestick (1D/1W/1M) and line (3M/1Y/5Y) charts with volume and interactive crosshairs.

**Earnings & news:** See upcoming earnings dates, dividend calendars, and the latest headlines for any ticker.

**Multi-language:** Available in English, Arabic, and Malay with RTL support for Arabic.

**Disclaimer:** This is an educational simulation. All trades are paper-money only. Agent reasoning is for learning, not investment advice. We are not a brokerage, registered investment advisor, or licensed financial advisor. Past performance does not indicate future results.

---

## Tester Onboarding Blurb

**For: Invite email or welcome screen (~200 words, friendly but direct)**

---

### Welcome to AMI Trade Beta

Thanks for joining the private beta. You're testing the first release of an AI-first trading simulator built to teach you how to manage an intelligent analyst team.

**To get started:**

1. **Create your mandate** — Your financial goals, risk tolerance, and personal constraints (e.g., no fossil fuels, halal-safe only). This drives every agent's response.
2. **Tap Convene the Room** on any ticker to watch your 12 agents debate. Their verdict lands in your journal.
3. **Trade paper money** — Place orders in AMI's simulator or route them to Alpaca paper if you connect your account. Both respect your mandate.
4. **Explore lessons** — Unlock lessons tied to each agent. Quick quizzes build your rep and unlock weekly leagues.
5. **Check settings** — Language (EN/AR/MS), watchlist tickers, and your performance history all live there.

**What we're tracking:**
- Bugs: tap the report icon (⚠️) in Settings to submit crashes, confusing UX, or missing features with screenshots.
- Feedback: which features feel useful vs. clunky. Your take shapes the roadmap.

**Known limitations:**
- Live order execution not available (paper trading only for now).
- TTS narration deferred to v1.0.
- Coach-mark tours (the blue popups on first visit) are still being refined on iOS.

**Feedback:** Reply to this email or tap Settings > Feedback. We read every submission.

Have fun. Learn something. Enjoy the sandbox.

—AMI Trade Team

---

## Context & Rationale

**Regulatory positioning:** Educational simulation, not investment advice. The disclaimer appears in both Apple and Google compliance forms, and it's load-bearing for store review. Lead with "simulation" and "not advice" everywhere testers might share screenshots or quotes.

**Why this crew ships:** Alpha tag `alpha-2026-09-25-1` + build 0.1.0+109 hold:
- **Shipped 2026-09-24 (CR232):** Persistent shell chrome on every pushed page (nav + ad banner + ticker tape always on-screen, back chevron navigation pattern instead of close buttons).
- **Shipped 2026-09-24 (CR233):** Alpaca limit/stop/stop_limit order types + bracket (DEF419 destination-aware mandate check also included).
- **Shipped 2026-09-21 (CR225/226):** AdMob re-linked at 9.0.0 to fix iOS release build; global adaptive ad banner added.
- **Shipped 2026-08-19 (CR193):** Push console test-send capability validated with real Android delivery.
- **Audited COMPLETE 2026-08-01 (CR027):** Push notification + in-app infrastructure; one-way notification service, OneSignal SDK, no in-app centre yet (deferred to CR135).

**Ads:** Floor Pass sees AdMob inventory (programmatic + house ads). Trader tier unblocked once revenue routing finalises (currently on hold pending decisions on payment partner).

**Device matrix (E5):** Blocked by DEF375 (tour modal prevents iOS gate automation). Runbook exists; manual smoke-test recommended before wide invite.

**External testers:** Expected to be 10–50 early adopters from Saiful's own network, confined to TestFlight (iOS) + Play Closed Testing (Android-GMS). No public app store listing yet.

