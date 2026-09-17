"""C02 step 3b — strategy catalogue.

One row per generated strategy: prompt, model, a one-line plain-English read of its stated rules
and parameters (from `reply`, the chatbot's prose -- not from the executable code), whether the
prose promised a win rate or return, and gate status. Descriptions are hand-read from each
`out/generated/pNN_<model>.json`'s `reply` field (30 short prose answers), not regex-extracted --
summarizing prose reliably needs reading it. No channel or video references, per spec.
"""

import json
from pathlib import Path

C02 = Path(__file__).resolve().parents[1]
GENERATED = C02 / "out" / "generated"
GATE_RESULTS = C02 / "out" / "gate_results.json"

# Hand-read from each out/generated/pNN_<model>.json's `reply` field.
DESCRIPTIONS = {
    "p01_haiku": ("9/21 EMA crossover long/short, RSI(14) 40-70 filter, volume confirmation, "
                  "2% stop / 2-3% target.", "none stated (opens with a refusal to promise profitability)"),
    "p01_opus": ("Two strategies offered: RSI(2) mean-reversion pullback in an uptrend (SMA200 filter) "
                 "and a trend/breakout system; picks RSI(2) as primary.", "none stated"),
    "p01_sonnet": ("Two strategies: Donchian(20)+dual MA(50/200)+ATR(14) trend breakout, and a "
                   "mean-reversion counterpart, both with ATR-based stops.", "none stated"),
    "p02_haiku": ("Long-only: buy when close > 50 SMA, sell when close < 50 SMA, optional 1-2% stop.",
                  "none stated"),
    "p02_opus": ("Long-only: buy at next open when close crosses above 50 SMA, sell at next open when "
                 "close crosses below; fully in or fully out, no stops.", "none stated"),
    "p02_sonnet": ("Long-only: hold when close > 50-day SMA, go to cash when close < 50-day SMA.",
                   "none stated"),
    "p03_haiku": ("30-period VWAP crossover: long above VWAP / short below, +3% take-profit, -1% stop "
                  "on both sides.", "none stated (quotes a 1:3 risk/reward ratio, not a win rate)"),
    "p03_opus": ("Same VWAP(30) crossover with 3% TP / 1% stop, delivered as a TradingView Pine Script "
                 "strategy rather than prose rules.", "none stated"),
    "p03_sonnet": ("Same VWAP(30) crossover, 3% TP / 1% stop long side, mirrored -3%/+1% short side, "
                   "opposite crossover flips the position.", "none stated"),
    "p04_haiku": ("RSI+MACD+EMA(20) swing setup: RSI 40-60, MACD histogram turns positive, volume > "
                  "20-day avg; 2:1 reward:risk target, 1.5-2% stop.", "none stated (excluded, see gate)"),
    "p04_opus": ("Offers RSI(2) Connors-style mean-reversion pullback as the 'high win rate' pick, "
                 "SMA200 trend filter.", "“published backtests...often shown win rates of roughly 65–80%”"),
    "p04_sonnet": ("4-indicator stack (EMA 50/200, RSI14, MACD 12/26/9, ATR14) trend-pullback swing "
                   "strategy, volume filter optional.", "none stated (calls win rate alone misleading)"),
    "p05_haiku": ("Z-score bounce: entry at ±2σ from 20-day SMA, exit at zero z-score, stop at "
                  "±3σ, optional RSI(14) and volume confirmation.", "none stated"),
    "p05_opus": ("RSI(2) Connors-style pullback: SMA200 trend filter, RSI(2)<10 entry, SMA5 exit, "
                 "10-day time stop, 2.5xATR(10) disaster stop.", "“published tests have generally shown "
                 "high win rates (often 65–80%)”"),
    "p05_sonnet": ("RSI(2) Connors-style pullback: SMA200 filter, RSI(2)<10, prior-day lower close "
                   "confirmation, ATR14 for risk sizing.", "none stated"),
    "p06_haiku": ("SMA(10/20) crossover trend-following, volume confirmation, ATR/pip-based stop, "
                  "1:2 minimum reward:risk.", "none stated"),
    "p06_opus": ("Donchian(55) breakout with EMA(50/200) trend filter, ATR(20) trailing stop at 3x, "
                 "1% risk per trade, explicitly unoptimized 'textbook' parameters.", "none stated"),
    "p06_sonnet": ("Dual EMA(50/200) + Donchian(20) breakout + ADX filter + ATR(14) trailing stop "
                   "trend-following system.", "none stated"),
    "p07_haiku": ("RSI(14) 30/70 + MACD(12,26,9) histogram-momentum confluence, volume and prior "
                  "support/resistance confirmation, tiered 1.5x/2.5x/4x R:R targets.", "none stated"),
    "p07_opus": ("RSI(14) pullback entries filtered by 200 EMA trend and MACD(12,26,9) momentum "
                 "confirmation, ATR(14) for stops, next-bar-open fills.", "none stated"),
    "p07_sonnet": ("MACD(12,26,9) crossover sets trend direction, RSI(14) 40-60 or oversold-recovery "
                   "times entries within that trend, optional 200 EMA filter.", "none stated"),
    "p08_haiku": ("Opens by rejecting the 70% premise as unrealistic, then gives a generic "
                  "risk/reward + discipline framework rather than a concrete rule set.",
                  "explicitly denies any strategy can guarantee 70%"),
    "p08_opus": ("RSI(2) Connors-style long-only mean reversion on SPY: SMA200 filter, RSI(2)<10 "
                 "entry, SMA5 exit.", "“has shown win rates of roughly 70–80% in many published "
                 "backtests”"),
    "p08_sonnet": ("Same RSI(2) Connors-style pullback (SMA200 filter, RSI(2) entry, quick exit), "
                   "framed around expectancy rather than win rate alone.", "“has historically shown "
                   "high win rates (often 70%+ in backtests)”"),
    "p09_haiku": ("Bitcoin SMA(50/200) golden/death cross, 100% in or 0% (cash), tested "
                  "conceptually over Jan 2015-Feb 2025.", "“approximate return: ~500-800% over the "
                  "period (vs. buy-and-hold's ~10,000%+)”"),
    "p09_opus": ("Bitcoin single SMA(200) trend filter: buy 100% when close > SMA200, sell to cash "
                 "when close < SMA200; explicitly not backtested in-session.", "none stated (says "
                 "“historically it has made money,” no number given)"),
    "p09_sonnet": ("Bitcoin SMA(50/200) golden/death cross, 100% BTC vs. cash, filled at next day's "
                   "open.", "none stated"),
    "p10_haiku": ("SuperTrend(10,3.0) direction + ADX(14)>25 strength filter + RSI(14) 30-70/40-60 "
                  "momentum confirmation, long/short symmetric.", "none stated"),
    "p10_opus": ("SuperTrend(10,3.0) flip within last 3 candles + ADX(14)>=20 + RSI(14) confirmation, "
                 "trend-following on 4H/1H.", "none stated"),
    "p10_sonnet": ("SuperTrend(10,3.0) direction + ADX(14)>25 + RSI(14) 40-60 crossing 50 momentum "
                   "confirmation, symmetric long/short.", "none stated"),
}


def main():
    gate = json.loads(GATE_RESULTS.read_text())
    rows = []
    for f in sorted(GENERATED.glob("p*_*.json")):
        name = f.stem
        record = json.loads(f.read_text())
        prompt_num = name.split("_")[0][1:]
        model = record.get("model_alias", "unknown")
        entry = gate["strategies"].get(name, {})
        status = entry.get("status", "unknown")
        desc, promise = DESCRIPTIONS.get(name, ("(not read)", "(not read)"))
        rows.append((prompt_num, model, desc, promise, status))

    lines = [
        "# C02 strategy catalogue",
        "",
        "One row per generated strategy. Description and promise are read from the chatbot's prose "
        "`reply`, not from the executable code. Gate status per `out/gate_results.json`.",
        "",
        "| Prompt | Model | Rules (plain English) | Win rate / return promised? | Gate status |",
        "|---|---|---|---|---|",
    ]
    for prompt_num, model, desc, promise, status in rows:
        lines.append(f"| p{prompt_num} | {model} | {desc} | {promise} | {status} |")

    (C02 / "out" / "catalogue.md").write_text("\n".join(lines) + "\n")
    print(f"wrote catalogue with {len(rows)} rows")


if __name__ == "__main__":
    main()
