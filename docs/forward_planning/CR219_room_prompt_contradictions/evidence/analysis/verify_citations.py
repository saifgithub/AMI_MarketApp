"""Check that every file:line the CR doc cites still points at the text it claims.

Line numbers rot. A reviewer who follows a citation to the wrong line stops
trusting the rest of the document, so this pins each one to a distinctive
substring and fails loudly when they drift apart. It is also the tool for
re-checking the CR after someone edits a persona.

exit 0 = every citation resolves. exit 1 = at least one drifted.
"""
import os, sys

ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "..", "..", "..", "..", ".."))

# (path, line-or-range as cited, a substring that must appear within that range)
CITATIONS = [
    ("content/agents/fundamentals_analyst.md", (29, 31), "never describe a margin as rising, falling, expanding"),
    ("content/agents/fundamentals_analyst.md", (48, 49), "M&A history are **not available**"),
    ("content/agents/fundamentals_analyst.md", (56, 60), "no *history* for any of them"),
    ("content/agents/fundamentals_analyst.md", (66, 66), "There is still no margin *trend* on the sheet"),
    ("content/agents/market_analyst.md",       (19, 22), "is not one this data can support"),
    ("content/agents/market_analyst.md",       (54, 54), "you do not have a series"),
    ("content/agents/news_analyst.md",         (25, 25), "not supplied"),
    ("content/agents/social_media_analyst.md", (26, 30), "no\n  historical baseline"),
    ("backend/app/agents/overlay_generator.py", (447, 447), "Emphasise momentum in fundamentals"),
    ("backend/app/agents/overlay_generator.py", (93, 93), "Primary goal: {mandate.primary_goal}"),
    ("backend/app/agents/overlay_generator.py", (437, 437), "long_horizon = m.horizon in"),
    ("backend/app/services/room_prompts.py",   (1336, 1336), "_format_profile(profile, agent_id)"),
    # The three denials that are TRUE and must survive any fix.
    ("content/agents/market_analyst.md",       (27, 29), "No MACD, moving-average crossover signal"),
    ("content/agents/social_media_analyst.md", (17, 17), "No Twitter/X, StockTwits, Google Trends, or Discord"),
    ("content/agents/fundamentals_analyst.md", (39, 40), "not a numeric peer-average"),
    ("backend/app/services/room_prompts.py",   (1, 999), "trader_block_regex"),
]

bad = 0
for rel, (a, b), needle in CITATIONS:
    path = os.path.join(ROOT, rel)
    if not os.path.exists(path):
        print(f"MISSING FILE  {rel}"); bad += 1; continue
    lines = open(path, encoding="utf-8").read().splitlines()
    window = "\n".join(lines[a - 1:b])
    span = f"{a}" if a == b else f"{a}-{b}"
    if needle.replace("\n", "\n") in window:
        print(f"  ok     {rel}:{span}")
    else:
        print(f"  DRIFT  {rel}:{span}  -- expected {needle!r}")
        bad += 1

print(f"\n{len(CITATIONS) - bad}/{len(CITATIONS)} citations resolve")
sys.exit(1 if bad else 0)
