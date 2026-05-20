# Finelo Feature-by-Feature Comparison

Finelo (finelo.com) is the direct competitor. This is our verdict on each of its features.

Verdict legend:
- **Keep** — we ship the same feature
- **Keep + Improve** — same feature, materially upgraded
- **Replace** — we replace with a different but better solution
- **Subsume** — we keep the capability but it's not a standalone feature
- **Cut** — we don't ship this

| # | Finelo feature | Verdict | How we make it better |
|---|---|---|---|
| 1 | 300+ bite-size lessons (≈3 min each) | **Keep + Improve** | AI-tutor wrapper delivers adaptive 1:1 lessons. Quiz fails → auto-generate remedial micro-lesson on the exact gap. Tutor speaks the user's mandate ("since you're targeting halal long-only, here's why P/E matters more for you"). |
| 2 | 10 languages | **Cut to 3** | EN / AR / MS at v1.0. Pluggable architecture for adding more later. Full RTL for Arabic. Voice TTS in all three. |
| 3 | Risk-free market simulator | **Keep + Improve** | Sim is wired to the 12 agents. Every user trade triggers relevant agents' reactions ("Bear Researcher: I warned about earnings — here's what I said"). PM compliance pre-check on every trade. Trade journal is permanent, replayable. |
| 4 | 28-Day Trading Challenge | **Keep + Reframe** | Becomes "Bootcamp" — adaptive length, capstone is "Meet Your First Agent." User can't unlock agents in the Earn Path until Bootcamp completes (or they Skip Path via subscription). |
| 5 | Daily trading challenges | **Keep** | Agent-themed: "Read what the Bear would say about XYZ. Then read what it actually said. Score yourself." Streak-tracked. Always free. |
| 6 | Chart analysis with live data | **Keep** | Standard. Dark-hex-themed charts (ECharts in the AMI palette). 15-min delayed; real-time is Floor Manager only at v1.1. |
| 7 | Investing Challenge (long-term focus) | **Keep + Split** | Two paths: **Active** (short-term, all 12 agents) vs **Long-horizon** (Fundamentals + Portfolio Manager prioritised). User picks at onboarding. |
| 8 | XP system | **Keep + Rebrand** | "Reputation" — earned not just from P&L but from *reasoning quality* (predicting what an agent will say; correctly overriding an agent). Anti-gambling-loop design. |
| 9 | Badges | **Keep + Improve** | Agent-themed: *Bear-Whisperer*, *Mandate Keeper*, *Conservative Streak*, *Convener*. Hex-clipped, role-coloured. |
| 10 | Streaks | **Keep** | Critical retention lever. Tied to *learning days*, not trade days — avoids forcing the user to trade. |
| 11 | Progress tracking | **Keep + Expand** | Four dimensions: (a) curriculum progress, (b) sim P&L, (c) reasoning quality, (d) per-agent agreement-vs-outcome track record. |
| 12 | AI Chart Analyzer | **Replace** | Becomes the **Market Analyst** agent — full conversation, full visible reasoning, not a one-shot output. |
| 13 | Pattern recognition | **Subsume** | One of the Market Analyst's tools, not a standalone feature. |
| 14 | Trade scenarios (instant analysis) | **Keep + Improve** | "What if I sell tomorrow?" runs a scoped multi-agent answer with mandate baked in. Counts as a metered credit. |
| 15 | Quizzes | **Keep + Improve** | AI-generated from each user's gap profile — not fixed item banks. Infinite, personalised. |
| 16 | Performance feedback | **Keep** | Conversational. The user does a weekly "1-on-1" with each agent who graded their trades. |
| 17 | Mobile-first (iOS/Android/Web) | **Keep + Add Huawei** | iOS / Android-GMS / Android-HMS (Huawei AppGallery). Web is companion only. |
| 18 | Account & subscription management | **Keep** | + Credit balance wallet for metered LLM operations. |
| 19 | Live market data | **Keep** | US equities feed. Mandate-aware filtering. |
| 20 | Community (1.5M users claim) | **Keep + Reinvent** | Finelo's is marketing. Ours: shareable Decision Journal entries, public Room replays, leaderboard of *reasoning quality* (not P&L), optional anonymous portfolios. Phase 2 + Phase 3. |
| 21 | Help center / support | **Keep + Replace with Concierge** | The AI Concierge (13th agent) handles product help + routes to lessons when relevant. Free, unlimited. Never gives trading advice. |

## What Finelo doesn't have that we do

These are the differentiators — none of Finelo's features above cover them.

| # | AMI Trade-exclusive feature | Why it matters |
|---|---|---|
| 1 | **Mandate-driven onboarding** (goals + risk + constraints → agent prompts) | Personalisation is at the *agent prompt level*, not the curriculum level. Generic AI becomes "your AI." |
| 2 | **12 specialised AI agents** (TradingAgents framework) | Single chart analyser vs an entire analyst team. 12× the visible reasoning. |
| 3 | **Convene the Room** | Visible multi-agent debate. No one else makes the reasoning legible at this scale. |
| 4 | **1-on-1 with any agent** | Solo conversation with each role — like having a meeting with your fundamentals analyst, then your bear researcher. |
| 5 | **Brief Your Agent** (conversational prompt tuning) | Users actively shape their team. Unique in the category. Switching cost goes up over time. |
| 6 | **AI Concierge as personal assistant** | Lesson routing, journal summary, scheduling, mute/promote agents — all by chat. |
| 7 | **Halal / Sharia compliance as a first-class mandate flag** | Universe filter + debt-ratio check + interest-bearing exclusion. Mass-market apps ignore this. |
| 8 | **Decision Journal with full transcripts** | Every Room, 1-on-1, trade, and mandate edit captured permanently. Replayable. The longer a user is with us, the more valuable their journal. |
| 9 | **PM compliance pre-check on every trade** | Before a sim trade submits, the Portfolio Manager evaluates against the user's mandate. Can veto with explanation. |
| 10 | **Voice morning briefings** in EN/AR/MS | TTS audio "stand-up with your team." Habit-forming. Paid tier. |
| 11 | **Mandate Drift Alerts** | Background check that the user's sim portfolio still matches their stated mandate. Proactive briefing. |
| 12 | **Safety floor on PM mandate enforcement** | Even crazy users get risk-managed. Uncoachable. Visible-but-locked in the Coach UI. |
| 13 | **Reasoning-quality leaderboard** (Phase 2) | Public ranking by quality of reasoning, not P&L. Attracts serious learners; repels gambling-loop seekers. |
| 14 | **AMI hex design language** | Distinctive visual identity. Honeycomb home screen with Concierge at the centre — no other app looks like this. |

## Positioning summary

> *"Finelo teaches you trading concepts. AMI Trade gives you a 12-person analyst team and teaches you to run it."*

Same price. Different category.
