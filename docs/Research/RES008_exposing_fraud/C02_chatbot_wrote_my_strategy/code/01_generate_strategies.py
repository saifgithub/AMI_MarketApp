"""C02 step 1 — ten pre-registered prompts x three chatbots = thirty strategies.

Turn one is the verbatim prompt from PREREGISTRATION.md (commit 3ac320eb). Turn two, in the same
conversation, asks the chatbot to express its own answer as a function with a fixed interface, so
the rules scored are the chatbot's and not our reading of its prose.
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from common.ask_chatbot import MODELS, ask_many  # noqa: E402

PROMPTS = [
    "Give me a profitable trading strategy for stocks using technical indicators. Provide exact entry and exit rules and parameters.",
    "Give me an extremely simple long-only trading strategy that uses the 50 SMA.",
    "Create a strategy to buy when price crosses over VWAP and short when price crosses below VWAP. Use a 30-period VWAP. Sell the long when the position has gained 3%, with a 1% stop loss.",
    "What is the best indicator combination for a high win rate swing trading strategy? Give exact parameters and rules.",
    "Give me a mean reversion trading strategy with exact parameters and rules.",
    "Give me a trend following trading strategy with exact parameters and rules.",
    "Create a trading strategy using RSI and MACD with exact entry and exit rules.",
    "I want a trading strategy with at least a 70% win rate. Give me the exact rules.",
    "Give me a Bitcoin trading strategy with exact rules that would have been profitable.",
    "Give me a trading strategy using SuperTrend, RSI and ADX. Exact parameters please.",
]

TO_CODE = (
    "Now write exactly that strategy as a single Python function and nothing else: "
    "`def signal(bars: pandas.DataFrame) -> pandas.Series`. `bars` has a DatetimeIndex and float "
    "columns open, high, low, close, volume (daily bars). Return a Series aligned to bars.index "
    "holding the target position decided at the close of each bar: 1 = long, -1 = short, 0 = flat. "
    "The value for a bar may use only data up to and including that bar, never later rows. Handle "
    "any stop loss or profit target inside the function by tracking the entry price bar by bar. "
    "Use only numpy and pandas. Reply with one Python code block only."
)

jobs = [
    {"name": f"p{i:02d}_{model}", "model": model, "prompt": prompt, "follow_up": TO_CODE}
    for i, prompt in enumerate(PROMPTS, start=1)
    for model in MODELS
]
ask_many(jobs, Path(__file__).resolve().parents[1] / "out" / "generated", workers=5)
