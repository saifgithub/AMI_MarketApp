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
    # CR219 WP01 R1/R2/R3 — the four fundamentals denials these lines used to
    # cite were the bug, and are gone. Each citation now points at the text that
    # REPLACED it, so the CR doc's file:line refs resolve to the fix rather than
    # to a sentence that no longer exists.
    ("content/agents/fundamentals_analyst.md", (30, 36), "may **not** extend that direction past the second date"),
    ("content/agents/fundamentals_analyst.md", (60, 61), "**M&A history is not available**"),
    ("content/agents/fundamentals_analyst.md", (73, 84), "Six figures on the sheet span more than one"),
    ("content/agents/fundamentals_analyst.md", (89, 89), "the direction stops at the second date"),
    # CR219 WP01 R4 — the blanket "no series" premise was false (window trend,
    # primary trend, 52w RS and the SMA-alignment read are all measured across
    # the history). Both citations now point at the narrowed claim that replaced
    # it: indicator TRAJECTORIES stay denied, measured trends are citable.
    ("content/agents/market_analyst.md",       (18, 32), "never\n  its trajectory"),
    ("content/agents/market_analyst.md",       (64, 64), "you were given its value, not its path"),
    # CR219 WP01 R5 — "you are not supplied consensus estimates" was contradicted
    # by the consensus EPS estimate on the news sheet's own earnings line. The
    # citation now points at the use-mention rule that replaced it.
    ("content/agents/news_analyst.md",         (25, 31), "**consensus EPS estimate**"),
    # CR219 WP01 R6 — narrowed, not deleted: the mention trend baselines VOLUME,
    # not SENTIMENT, and the persona now says which is which.
    ("content/agents/social_media_analyst.md", (28, 39), "Mention volume is baselined; sentiment is not"),
    ("backend/app/agents/overlay_generator.py", (447, 447), "Emphasise momentum in fundamentals"),
    ("backend/app/agents/overlay_generator.py", (93, 93), "Primary goal: {mandate.primary_goal}"),
    ("backend/app/agents/overlay_generator.py", (437, 437), "long_horizon = m.horizon in"),
    ("backend/app/services/room_prompts.py",   (1336, 1336), "_format_profile(profile, agent_id)"),
    # The three denials that are TRUE and must survive any fix.
    ("content/agents/market_analyst.md",       (39, 41), "No MACD, moving-average crossover signal"),
    ("content/agents/social_media_analyst.md", (17, 17), "No Twitter/X, StockTwits, Google Trends, or Discord"),
    ("content/agents/fundamentals_analyst.md", (44, 45), "not a numeric peer-average"),
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
