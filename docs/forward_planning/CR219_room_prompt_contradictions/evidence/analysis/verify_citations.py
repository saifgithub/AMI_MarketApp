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
    # CR219 WP06 2026-09-03, five inserts to this file in sequence: R33 (4
    # lines, "Interest coverage", after "Returns and balance sheet"), R34 (4
    # lines, "Capital expenditure", after "Capital returned"), R35 (4 lines,
    # "Buyback pacing", after "Buybacks" — above R34's point, so R35 also
    # pushes R34's bullet down), R37 (6 lines, "Multiples vs. own history",
    # after the peer-average sentence — above all three prior points, so it
    # pushes every one of them down too), R21-DATA (6 lines, "Earnings
    # revisions" + "Surprise history", after R37's own bullet — above
    # nothing yet inserted, so it only pushes what's below IT). Net shift
    # below all five for anything past every insertion point: +24 from the
    # pre-R33 baseline. Re-verified against actual file content each time
    # (start AND end boundary, after R35 caught a window whose END no
    # longer matched the block it was checking even though the SUBSTRING
    # still fell inside it by accident) — never accumulated by arithmetic
    # alone.
    ("content/agents/fundamentals_analyst.md", (84, 85), "**M&A history is not available**"),
    ("content/agents/fundamentals_analyst.md", (97, 108), "Six figures on the sheet span more than one"),
    ("content/agents/fundamentals_analyst.md", (113, 113), "the direction stops at the second date"),
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
    # CR219 WP05 (R25/R26/R56, 2026-09-03) shifted these three lines down by
    # inserting `_goal_block`'s call site + its ~80-line definition earlier in
    # the file (the "Primary goal:" line itself did not move; the other two
    # shifted because the new block landed above them). Re-pinned to the new
    # line numbers; the cited substrings are unchanged.
    #
    # WP06 R21 ALIGNMENT (2026-09-03) then REWROTE this branch's content —
    # the citation's job was always "locate the R21 branch line", not assert
    # the old (now-fixed) text, so the same leading substring still resolves
    # it, re-pinned to its new line (531 -> 549: the rewrite replaced one
    # `.append(...)` line with a longer commented block + multi-line
    # `.append(...)`, net +18).
    ("backend/app/agents/overlay_generator.py", (549, 549), "Emphasise momentum in fundamentals"),
    ("backend/app/agents/overlay_generator.py", (94, 94), "Primary goal: {mandate.primary_goal}"),
    ("backend/app/agents/overlay_generator.py", (521, 521), "long_horizon = m.horizon in"),
    # CR219 WP06 R33/R34/R35/R37 each added one import line to
    # room_prompts.py's fundamentals import block; R21-DATA added TWO
    # (`eps_revisions_line,` and `surprise_history_line,`) — net +5 lines
    # of import-block shift across all five commits, shifting everything
    # below down by that much.
    ("backend/app/services/room_prompts.py",   (1609, 1609), "_format_profile(profile, agent_id)"),
    # The three denials that are TRUE and must survive any fix.
    ("content/agents/market_analyst.md",       (39, 41), "No MACD, moving-average crossover signal"),
    ("content/agents/social_media_analyst.md", (17, 17), "No Twitter/X, StockTwits, Google Trends, or Discord"),
    ("content/agents/fundamentals_analyst.md", (48, 49), "not a numeric peer-average"),
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
