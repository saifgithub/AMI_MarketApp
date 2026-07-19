"""Curated earn-path gateways — the lessons that actually unlock each agent (DEF068).

Before this, the gateway set was *incidental*: `_gateway_lessons_for_agent` took the first
three lessons, sorted by lexicographic id, whose `agent_callouts` named the agent. Nobody
chose those lessons. `market_analyst` is named by 71 lessons and three of them counted;
`aggressive_debator`'s third gate was lesson 225 of 292. Measured on the alpha corpus, a user
who had passed 50 lessons was still at 0/3 on three agents and held 1 of 12.

So the set is explicit now, and it is five rather than three.

Two rules shaped the picks:

1. **The first gate is the agent's lesson from the 280-292 sampler.** That block is one L1-L3
   lesson per agent — literally "meet this agent" — and every one of the 12 has one. It gives
   every agent an entry point a beginner can reach in their first session.
2. **The remaining four are the agent's own job, as early as the corpus allows.** Preference
   goes to the agent's natural track and to low `level`, because a gate the user cannot reach
   for weeks is the defect this file exists to fix.

Some agents (news_analyst, neutral_debator) still carry L5-L6 gates. Their subject matter
genuinely lives late in the curriculum; that is a curriculum shape question, not something a
gateway list can fix.

Constraints enforced by `test_lesson_corpus_integrity`:
  - all 12 agents present, exactly GATEWAY_SIZE ids each
  - every id exists in the corpus
  - every gateway lesson names its agent in its own `agent_callouts` — otherwise the lesson
    tile's hex avatars would disagree with the gate about who the lesson belongs to

Changing a list here changes what existing users must do. It never *removes* an agent already
earned: activations are persisted rows and the unlock check only runs on a fresh passing
submit, so a larger gate is a change to the path, not a takeaway.
"""

from __future__ import annotations

GATEWAY_SIZE = 5


AGENT_GATEWAYS: dict[str, list[str]] = {
    # Read a company: what a stock is, then revenue -> profit -> balance sheet.
    "fundamentals_analyst": [
        "280_what_is_a_stock",
        "285_reading_a_pe_ratio",
        "032_revenue_the_top_line",
        "033_profit_and_margins",
        "034_debt_and_the_balance_sheet",
    ],
    # Read a market: what a market and a chart are, what moves price, then the bar itself.
    "market_analyst": [
        "281_what_is_a_market",
        "286_what_is_a_chart",
        "005_what_moves_stock_prices",
        "006_what_is_volatility",
        "020_candlesticks_anatomy_of_a_bar",
    ],
    # Narrative and rotation. The tail is L6 because the news_macro track is L6.
    "news_analyst": [
        "287_news_that_moves_markets",
        "005_what_moves_stock_prices",
        "063_sector_rotation",
        "250_rate_sensitive_sectors_hiking_cutting",
        "251_defensive_cyclical_geographic_rotation",
    ],
    # Crowd emotion — the whole sentiment_behaviour spine.
    "social_media_analyst": [
        "288_sentiment_and_the_crowd",
        "045_greed",
        "046_fear_and_capitulation",
        "048_fomo",
        "206_meme_momentum_fomo",
    ],
    # Build the bull case: moats, operating leverage, brand.
    "bull_researcher": [
        "289_bull_vs_bear_thinking",
        "036_competitive_advantage_moat",
        "059_bull_markets",
        "155_operating_leverage_cyclicals",
        "162_brand_moat_when_a_logo_is_pricing_power",
    ],
    # Build the bear case: fear, failure modes, accounting red flags.
    "bear_researcher": [
        "289_bull_vs_bear_thinking",
        "046_fear_and_capitulation",
        "060_bear_markets",
        "058_strategy_failure_modes",
        "148_revenue_recognition_red_flags",
    ],
    # Judge evidence rather than hold an opinion — synthesis, breadth, validation.
    # `064_market_breadth` is here in place of a second L8 lesson: an all-L5/L8 set left
    # this agent the only one a 50-lesson alpha user had made zero progress on.
    "research_manager": [
        "292_research_manager_synthesis",
        "057_backtesting_a_strategy",
        "064_market_breadth",
        "077_decision_support_vs_prediction",
        "230_in_sample_vs_out_of_sample",
    ],
    # Execution mechanics. All five are L1 — the cheapest agent to earn, deliberately.
    "trader": [
        "283_market_order_vs_limit",
        "014_position_sizing_basics",
        "015_stop_loss_basics",
        "016_risk_reward_ratio",
        "102_atr_based_stops",
    ],
    # Argue for the trade: breakouts, trend, momentum.
    "aggressive_debator": [
        "290_position_sizing_basics",
        "024_breakouts",
        "052_trend_following",
        "056_momentum_trading",
        "053_breakout_strategy",
    ],
    # Argue against it: tails, and the four ways a trader talks themselves into a bad entry.
    "conservative_debator": [
        "290_position_sizing_basics",
        "110_tail_risk_and_fat_tails",
        "047_revenge_trading",
        "049_overconfidence",
        "050_boredom_trading",
    ],
    # Hold the middle: correlation, confirmation, ranges, diversification.
    "neutral_debator": [
        "290_position_sizing_basics",
        "017_portfolio_exposure_and_correlation",
        "030_trend_confirmation_across_indicators",
        "061_sideways_range_markets",
        "236_combining_strategies_for_diversification",
    ],
    # Own the portfolio: mandate, then sizing, exposure and drawdown.
    "portfolio_manager": [
        "291_the_pm_and_your_mandate",
        "013_why_risk_matters_more_than_profit",
        "014_position_sizing_basics",
        "017_portfolio_exposure_and_correlation",
        "018_drawdown_management",
    ],
}
