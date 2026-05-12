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

## Totals

| Level | Module | Lessons |
|---|---|---|
| 1 | 1, 2, 3 | 6 + 6 + 7 = 19 |
| 2 | 4, 5 | 6 + 6 = 12 |
| 3 | 6, 7 | 7 + 6 = 13 |
| 4 | 8 | 7 |
| 5 | 9 | 7 |
| 6 | 10 | 6 |
| 7 | 11 | 7 |
| 8 | 12 | 6 |
| **Total** | **12 modules** | **77 lessons** |

77 lessons is **Alpha-tight** — narrower than the original 150-lesson alpha target but pedagogically complete. The remaining ~70 lessons toward the v1.0 target of 300 are filled in by depth lessons per topic during MVP and beyond.

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

## Animations

Every lesson should include at least one **`<Animation name="..." />`** MDX component reference. Animations are short (2–6 second) Lottie or Flutter-rendered loops that visualize the concept. They live in `content/animations/` keyed by name and ship with the app bundle.

The MDX side just references a name — the Flutter side resolves it to an animation widget. If the name doesn't resolve, the component renders a placeholder so missing animations don't break the lesson.

Catalog (names to be created by Saiful's designer or via Lottie marketplace):

| Module | Animation names |
|---|---|
| 1 (What Is the Stock Market?) | `stock_ownership_pie`, `order_book_fill`, `exchange_floor`, `volatility_waveform` |
| 2 (Investing vs Trading) | `compounding_curve`, `time_horizon_scale`, `win_loss_distribution` |
| 3 (Risk Management) | `position_size_calc`, `stop_loss_trigger`, `drawdown_recovery`, `risk_reward_scale` |
| 4 (Reading Charts) | `candlestick_anatomy`, `trendline_draw`, `support_resistance_test`, `breakout_pattern`, `pullback_pattern` |
| 5 (Indicators) | `moving_average_lag`, `rsi_oscillator`, `macd_crossover`, `volume_bars` |
| 6 (Understanding Companies) | `revenue_waterfall`, `profit_margin_breakdown`, `debt_vs_equity`, `free_cash_flow_waterfall` |
| 7 (Financial Ratios) | `pe_ratio_visual`, `roe_breakdown`, `debt_to_equity_bar`, `dividend_yield_pie` |
| 8 (Emotional Discipline) | `fomo_curve`, `revenge_position_escalation`, `discipline_meter` |
| 9 (Trading Strategies) | `trendfollow_entry_exit`, `breakout_confirm`, `mean_reversion_bounce` |
| 10 (Market Regime) | `bull_bear_states`, `sector_rotation_wheel`, `breadth_heatmap` |
| 11 (Scam Protection) | `red_flag_checklist`, `fake_vs_real_broker`, `pump_dump_curve` |
| 12 (AI + Modern Trading) | `ami_constellation`, `hallucination_demo`, `decision_support_arrow` |

~50 unique animations across the curriculum. Build incrementally — a placeholder is acceptable for Alpha-launch as long as the MDX reference is in place.

---

## See also

- `lessons.md` — the original 7-track classification (kept for the agent-unlock logic).
- `daily_and_streaks.md` — daily challenges + streak rules.
- `agent_academy.md` — the optional deep-dive course per agent (Module 13+ in spirit).
- `../../content/_authoring/lesson_authoring_prompt.md` — the AI-tool prompt that generates lessons matching this map.
