# Curriculum map — Levels 1–8, Modules 1–12

The canonical sequence for AMI Trade lessons. Authored from Saiful's outline. Supersedes the looser track-only listing in `lessons.md` (which kept the 7-track classification for downstream agent-unlock routing). Each lesson now has both a **module** (its sequence position) and a **track** (its agent-unlock and search facet).

---

## Why two axes

- **Level / Module** → the user's journey. Determines order, prerequisites, what unlocks "next lesson".
- **Track** → the cross-cutting facet. Determines which agent a lesson contributes to unlocking (the W5 Earn Path), and how the Concierge searches.

The MDX frontmatter carries both:

```yaml
level: 1                        # 1-8: pedagogical stage (Saiful's Level)
module: 3                       # 1-12: cohesive group of lessons within a stage
difficulty: 2                   # 1-5: how hard the content itself is
track: "risk_portfolio"         # one of the 7 enum values (unchanged)
```

The existing `LessonsService` parser reads `level` as an integer — we keep that. `module` + `difficulty` are new fields the loader will accept; legacy lessons (without them) get `module: 0, difficulty: <level>` defaulted.

---

## Level 1 — Beginner Foundation

Audience: brand new to markets. Vocabulary + the basic safety rules.

### Module 1 — What Is the Stock Market?

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 001 | What is a stock? | 1 | foundations | — |
| 002 | Why companies issue shares | 1 | foundations | — |
| 003 | What is a stock exchange? | 1 | foundations | — |
| 004 | US markets vs Bursa Malaysia | 1 | foundations | — |
| 005 | What moves stock prices? | 1 | foundations | news_analyst, market_analyst |
| 006 | What is volatility? | 1 | foundations | market_analyst |

### Module 2 — Investing vs Trading

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 007 | Investing vs trading | 1 | foundations | — |
| 008 | Time horizon and goals | 1 | foundations | — |
| 009 | Risk profile basics | 1 | foundations | — |
| 010 | Compounding vs active trading | 2 | foundations | — |
| 011 | Long-term wealth building | 2 | foundations | — |
| 012 | Why most traders fail | 2 | edge_process | — |

### Module 3 — Risk Management (most important)

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 013 | Why risk matters more than profit | 2 | risk_portfolio | portfolio_manager |
| 014 | Position sizing basics | 2 | risk_portfolio | portfolio_manager, trader |
| 015 | Stop-loss basics | 2 | risk_portfolio | trader |
| 016 | Risk/reward ratio | 2 | risk_portfolio | trader |
| 017 | Portfolio exposure and correlation | 3 | risk_portfolio | portfolio_manager |
| 018 | Drawdown management | 3 | risk_portfolio | portfolio_manager |
| 019 | Survival mindset | 2 | edge_process | portfolio_manager |

---

## Level 2 — Technical Analysis

Audience: comfortable with Level 1. Can now read a chart.

### Module 4 — Reading Charts

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 020 | Candlesticks: anatomy of a bar | 2 | technical_analysis | market_analyst |
| 021 | Timeframes and what they tell you | 2 | technical_analysis | market_analyst |
| 022 | Trend direction | 2 | technical_analysis | market_analyst |
| 023 | Support and resistance | 2 | technical_analysis | market_analyst |
| 024 | Breakouts | 3 | technical_analysis | market_analyst |
| 025 | Pullbacks | 3 | technical_analysis | market_analyst |

### Module 5 — Indicators

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 026 | Moving averages | 2 | technical_analysis | market_analyst |
| 027 | RSI — momentum oscillator | 3 | technical_analysis | market_analyst |
| 028 | MACD — trend + momentum | 3 | technical_analysis | market_analyst |
| 029 | Volume confirmation | 2 | technical_analysis | market_analyst |
| 030 | Trend confirmation across indicators | 3 | technical_analysis | market_analyst |
| 031 | Indicator limitations | 3 | edge_process | market_analyst |

---

## Level 3 — Fundamental Analysis

Audience: cares about the business behind the ticker.

### Module 6 — Understanding Companies

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 032 | Revenue: the top line | 2 | fundamentals_analysis | fundamentals_analyst |
| 033 | Profit and margins | 2 | fundamentals_analysis | fundamentals_analyst |
| 034 | Debt and the balance sheet | 3 | fundamentals_analysis | fundamentals_analyst |
| 035 | Cash flow vs earnings | 3 | fundamentals_analysis | fundamentals_analyst |
| 036 | Competitive advantage (moat) | 3 | fundamentals_analysis | fundamentals_analyst, bull_researcher |
| 037 | Valuation: what is a stock "worth"? | 3 | fundamentals_analysis | fundamentals_analyst |
| 038 | Comparable companies | 3 | fundamentals_analysis | fundamentals_analyst |

### Module 7 — Financial Ratios

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 039 | The P/E ratio | 2 | fundamentals_analysis | fundamentals_analyst |
| 040 | Price-to-book | 3 | fundamentals_analysis | fundamentals_analyst |
| 041 | Return on equity (ROE) | 3 | fundamentals_analysis | fundamentals_analyst |
| 042 | Debt-to-equity | 3 | fundamentals_analysis | fundamentals_analyst |
| 043 | Dividend yield and payout ratio | 2 | fundamentals_analysis | fundamentals_analyst |
| 044 | Earnings growth | 3 | fundamentals_analysis | fundamentals_analyst |

---

## Level 4 — Trading Psychology

Audience: has lost money emotionally at least once.

### Module 8 — Emotional Discipline

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 045 | Greed | 2 | sentiment_behaviour | social_media_analyst |
| 046 | Fear and capitulation | 2 | sentiment_behaviour | social_media_analyst, bear_researcher |
| 047 | Revenge trading | 3 | edge_process | conservative_debator |
| 048 | FOMO | 2 | sentiment_behaviour | social_media_analyst |
| 049 | Overconfidence | 3 | edge_process | conservative_debator |
| 050 | Boredom trading | 2 | edge_process | conservative_debator |
| 051 | Discipline vs excitement | 3 | edge_process | portfolio_manager |

---

## Level 5 — Strategy Building

Audience: ready to put a process in writing.

### Module 9 — Trading Strategies

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 052 | Trend-following | 3 | edge_process | aggressive_debator, trader |
| 053 | Breakout strategy | 3 | edge_process | market_analyst, trader |
| 054 | Pullback strategy | 3 | edge_process | market_analyst, trader |
| 055 | Mean reversion | 4 | edge_process | conservative_debator, trader |
| 056 | Momentum trading | 3 | edge_process | aggressive_debator |
| 057 | Backtesting a strategy | 4 | edge_process | research_manager |
| 058 | Strategy failure modes | 4 | edge_process | bear_researcher, conservative_debator |

---

## Level 6 — Market Regime

Audience: thinks beyond individual setups.

### Module 10 — Understanding Market Conditions

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 059 | Bull markets | 3 | news_macro | bull_researcher |
| 060 | Bear markets | 3 | news_macro | bear_researcher |
| 061 | Sideways / range markets | 3 | news_macro | neutral_debator |
| 062 | Volatility regimes | 4 | news_macro | market_analyst |
| 063 | Sector rotation | 4 | news_macro | news_analyst |
| 064 | Market breadth | 4 | news_macro | market_analyst, research_manager |

---

## Level 7 — Scam Protection

Audience: anyone on social media. Critical for the GCC + SEA markets we ship to.

### Module 11 — Investment Scam Awareness

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 065 | "Guaranteed return" scams | 1 | edge_process | concierge |
| 066 | Telegram / WhatsApp pump groups | 1 | edge_process | concierge |
| 067 | Fake brokers and clone entities | 1 | edge_process | concierge |
| 068 | Forex / "FX trading" scams | 1 | edge_process | concierge |
| 069 | "AI trading bot" scams | 2 | edge_process | concierge |
| 070 | Pressure tactics: urgency + scarcity | 1 | edge_process | concierge |
| 071 | How to verify before you wire money | 2 | edge_process | concierge |

---

## Level 8 — AI + Modern Trading

Audience: ready to think about AMI itself — what it is and isn't.

### Module 12 — AI-Assisted Trading

| ID | Title | Difficulty | track | Agent callouts |
|---|---|---|---|---|
| 072 | What AMI can do for you | 2 | edge_process | concierge |
| 073 | What AMI cannot do | 3 | edge_process | concierge |
| 074 | AI hallucinations — and how AMI's safety floor mitigates them | 3 | edge_process | portfolio_manager |
| 075 | The risk of overreliance | 3 | edge_process | concierge |
| 076 | Human oversight is the product | 3 | edge_process | concierge |
| 077 | Decision-support vs prediction | 3 | edge_process | research_manager |

---

## Totals (approximate)

| Level | Module | Lessons planned |
|---|---|---|
| 1 | 1, 2, 3 | ~19 |
| 2 | 4, 5 | ~12 |
| 3 | 6, 7 | ~13 |
| 4 | 8 | ~7 |
| 5 | 9 | ~7 |
| 6 | 10 | ~6 |
| 7 | 11 | ~7 |
| 8 | 12 | ~6 |
| **Total** | **12 modules** | **~77 lessons** |

These counts are the **shape** of the curriculum, not a hard target. The actual number that ships in Alpha is whatever the AI-tool-generated batches produce at acceptable quality. If a batch comes back tight at 5 lessons for a module that was scoped for 7, ship 5 and add the missing two later when the topic earns the depth.

The ID sequence is reserved (001–077) so even if a lesson is skipped or merged, the IDs stay stable for prerequisites + agent_callouts references.

---

## Existing 13 lessons — re-mapping

The lessons already on disk slot into the new structure. Some need a frontmatter touch-up to add the new `module` field; titles stay the same.

| Existing file | New ID | Level | Module | Notes |
|---|---|---|---|---|
| `001_what_is_a_stock.en.mdx` | 001 | 1 | 1 | unchanged |
| `002_what_is_a_market.en.mdx` | 003 | 1 | 1 | rename slug from `_what_is_a_market` → `_what_is_a_stock_exchange` to match Module 1 sequence |
| `003_what_is_a_brokerage.en.mdx` | merge into 003 | — | — | Brokerage explainer becomes a section inside the new lesson 003 *(or kept as a Foundations bonus)* |
| `004_market_order_vs_limit.en.mdx` | bonus | 1 | 1 | Reposition as a bonus / level-2 deep-dive after Module 1 |
| `005_what_makes_a_price_move.en.mdx` | 005 | 1 | 1 | unchanged |
| `006_reading_a_pe_ratio.en.mdx` | 039 | 3 | 7 | re-id |
| `007_what_is_a_chart.en.mdx` | 020 | 2 | 4 | re-id (candlesticks anatomy) |
| `008_news_that_moves_markets.en.mdx` | bonus | 6 | 10 | tag as a Module 10 deep-dive |
| `009_sentiment_and_the_crowd.en.mdx` | 045–048 (merge or split) | 4 | 8 | content splits across greed/fear/FOMO lessons |
| `010_bull_vs_bear_thinking.en.mdx` | bonus | 5 | 9 | repositioned as a Module 9 conceptual lesson |
| `011_position_sizing_basics.en.mdx` | 014 | 1 | 3 | re-id |
| `012_the_pm_and_your_mandate.en.mdx` | 013 | 1 | 3 | re-id (most important Level-1 lesson) |
| `013_research_manager_synthesis.en.mdx` | 057 | 5 | 9 | re-id |

The re-mapping is **not urgent** — the existing files keep working as-is. Renaming happens lazily when the next batch lands and we want clean numeric ordering.

---

## Animations (optional, selective)

**Most lessons don't need an animation.** Static markdown + a real-ticker numeric example + a clean quiz is plenty for the concept-explainer lessons (probably ~70% of the curriculum). Animations are reserved for concepts that genuinely benefit from motion — things you'd struggle to teach with prose alone.

The MDX component is optional. When present, it just references a name; the Flutter side resolves to a Lottie file or a Flutter-rendered widget. If the name doesn't resolve, a placeholder renders so the lesson still works.

### Where animation pays off

Good candidates (~15–20 across the curriculum). These are the ones we'd actually invest design effort in:

| Module | Lesson ID | Animation name | Why motion helps |
|---|---|---|---|
| 2 | 010 | `compounding_curve` | Time + compounding is hard to grok statically — the curve sweeping over decades is the lesson. |
| 3 | 014 | `position_size_calc` | The risk%-of-account-to-share-count math wants a slider feel. |
| 3 | 015 | `stop_loss_trigger` | A price tagging the stop and exiting feels visceral in motion. |
| 3 | 018 | `drawdown_recovery` | The asymmetric "50% loss needs 100% gain" curve lands much harder when animated. |
| 3 | 016 | `risk_reward_scale` | Two bars sliding into different proportions communicates ratio at a glance. |
| 4 | 020 | `candlestick_anatomy` | Open/high/low/close as a single bar drawing itself — flagship animation. |
| 4 | 023 | `support_resistance_test` | Price approaching a level and bouncing/breaking is the whole concept. |
| 4 | 024 | `breakout_pattern` | A consolidation tightening and resolving up. |
| 5 | 026 | `moving_average_lag` | Price and MA moving together, MA lagging — best shown in motion. |
| 5 | 027 | `rsi_oscillator` | Needle sweeping 0–100, crossing 30/70 thresholds. |
| 8 | 048 | `fomo_curve` | Price accelerating into a peak; the user-entry marker landing late. |
| 8 | 047 | `revenge_position_escalation` | Position size growing trade-by-trade after consecutive losses. |
| 10 | 059 | `bull_bear_states` | Market regime as a state machine flipping between modes. |
| 11 | 066 | `pump_dump_curve` | Telegram-pump price curve — explosion then collapse. |
| 12 | 072 | `ami_constellation` | The 12 agents as nodes lighting up in sequence — branded hero animation. |

That's the priority list. Anything else, ship the lesson without an animation and add one later if usage data says the concept is sticking poorly.

### What lives where

- **MDX**: lessons reference animations by name only — `<Animation name="candlestick_anatomy" />`.
- **Flutter**: an `AnimationRegistry` maps names → asset paths. Missing names render an `AmiHexPlaceholder` widget (just a styled hex tile saying "Animation pending").
- **Asset path**: `content/animations/<name>.json` (Lottie) or a Dart-defined widget in `mobile/lib/animations/<name>.dart`.

Production is decoupled from content. Lessons can ship today with animation references; designers fill in the assets at their own pace.

---

## Expansion lessons (deep-dive companions, IDs 100–279)

The 77 IDs above are the **foundation curriculum** — the trunk every user walks through. Each module also has an **expansion set**: deep-dive sub-topic lessons that sit alongside the foundations and drill into specific angles. Expansion lessons live at IDs 100–279 and are NOT on the foundation animation list (no animations).

Lesson-count multiplier per module (relative to foundation count):

| Module | Foundation | Expansion | Multiplier | IDs |
|---|---|---|---|---|
| M3 — Risk Management | 7 | 12 | ~3× | 100–111 |
| M4 — Reading Charts | 6 | 12 | ~3× | 112–123 |
| M5 — Indicators (complicated) | 6 | 24 | ~5× | 124–147 |
| M6 — Understanding Companies (complicated) | 7 | 28 | ~5× | 148–175 |
| M7 — Financial Ratios (complicated) | 6 | 24 | ~5× | 176–199 |
| M8 — Emotional Discipline | 7 | 14 | ~3× | 200–213 |
| M9 — Trading Strategies (complicated) | 7 | 28 | ~5× | 214–241 |
| M10 — Market Regime | 6 | 12 | ~3× | 242–253 |
| M11 — Investment Scam Awareness | 7 | 14 | ~3× | 254–267 |
| M12 — AI-Assisted Trading | 6 | 12 | ~3× | 268–279 |
| **Total expansion** | — | **180** | — | **100–279** |

Expansion lessons live in `content/lessons/<id>_<slug>.en.mdx` alongside the foundations. The directory listing is the canonical catalog; this map is the structural index.

**Notes on expansion design:**
- Each expansion lesson opens by stating which foundation it deepens, then teaches ONE specific sub-topic at the same 7-part-template depth as a foundation lesson.
- "Complicated" modules (M5/M6/M7/M9) get ~5× because the topic genuinely warrants more depth. "Standard" modules get ~3×.
- **M1 and M2 expansion is not yet generated.** M1/M2 foundations (IDs 001–012) are now in place; expansion lessons for these modules can be added at IDs 293+ when prioritised.

---

## Legacy bonus lessons (IDs 280–292)

The 13 pre-curriculum-map lessons originally at IDs 001–013 were parked at IDs 280–292 when the new M1/M2 foundations were written. They remain in the corpus as "legacy bonus" content — Foundations-track material that doesn't fit the new module structure but still has educational value:

- 280: What is a stock? (legacy version)
- 281: What is a market? (now a stock-exchange variant)
- 282: What is a brokerage?
- 283: Market order vs limit order
- 284: What makes a price move? (legacy version)
- 285: Reading a P/E ratio (legacy version; superseded by Module 7)
- 286: What is a chart? (legacy version; superseded by Module 4)
- 287: News that moves markets (legacy version; superseded by Module 10)
- 288: Sentiment and the crowd (legacy version; superseded by Module 8)
- 289: Bull vs bear thinking (legacy version)
- 290: Position sizing basics (legacy version; superseded by 014)
- 291: The PM and your mandate (legacy version; superseded by 013)
- 292: Research Manager synthesis (legacy version; superseded by 057)

These remain available for users who want alternate explanations of the same concepts, or as "bonus" deep-dives surfaced by the Concierge when a foundation lesson's framing doesn't click.

---

## See also

- `lessons.md` — the original 7-track classification (kept for the agent-unlock logic).
- `daily_and_streaks.md` — daily challenges + streak rules.
- `agent_academy.md` — the optional deep-dive course per agent (Module 13+ in spirit).
- `../../content/_authoring/lesson_authoring_prompt.md` — the AI-tool prompt that generates lessons matching this map.
