#!/usr/bin/env python3
"""recipe18_concierge.py — RUN2_PLAN S8: the Concierge, the 13th agent.

Production surface S8. Run-1 coverage: **zero** — and it is the surface a new user
meets FIRST, since onboarding is anonymous-first and concierge-led (CLAUDE.md).

The Concierge is not one of the 12 trading agents. Its contract is mostly a list of
things it must never do, which makes it unusually well suited to programmatic labels:
every prohibition is a checkable property of the rendered answer.

## Verifiable without a judge (CR038)

- **Never gives trading advice.** No buy/sell/hold recommendation, no directional
  claim on a ticker. Asserted by regex over the finished target.
- **Routes to a REAL lesson.** Codes are drawn from the live catalogue in
  `content/lessons/*.en.mdx` (365 lessons, group-scoped codes like `CORE 15`,
  `FUND 8`) and every emitted code is asserted to exist. `concierge.md` is explicit
  that the code is what lets a user actually FIND the lesson, so an invented code is
  a navigation dead end, not a cosmetic error.
- **Never invents a capability.** `concierge.md` names two hallucinations it has
  produced before — agent mute/priority controls, and a scheduled morning briefing —
  neither of which exists anywhere in the backend. The refusal cases train saying so
  plainly instead of inventing a screen.
- **Routes trading questions to a REAL agent**, by `agent_id` from
  `content/agents/`, never to an invented desk.

Case mix is deliberate: roughly a third of examples are cases where the correct
behaviour is to decline and redirect. A concierge trained only on answerable
questions learns to answer everything.

Usage: python3 recipe18_concierge.py --out out/recipe18.jsonl
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from common import pick, write_jsonl  # noqa: E402
from role_common import REPO, load_role_prompt  # noqa: E402

LESSONS_DIR = os.path.join(REPO, "content", "lessons")
AGENTS_DIR = os.path.join(REPO, "content", "agents")

P_ADVICE = re.compile(
    r"\b(you should (buy|sell|short)|i (recommend|suggest) (buying|selling)|"
    r"will (rise|fall|go up|go down)|is going to (rise|fall)|"
    r"\b(buy|sell) (it|this|now)\b|price target|undervalued|overvalued)", re.I)
P_INVENTED = re.compile(
    r"(morning brief|daily digest|schedule[ds]? (a )?(briefing|delivery|report)|"
    r"mute (the |an )?agent|agent priority|pin (the |an )?agent)", re.I)


def load_lessons() -> list[dict]:
    out = []
    for fn in sorted(os.listdir(LESSONS_DIR)):
        if not fn.endswith(".en.mdx"):
            continue
        meta, path = {}, os.path.join(LESSONS_DIR, fn)
        with open(path) as f:
            if f.readline().strip() != "---":
                continue
            for line in f:
                line = line.rstrip("\n")
                if line.strip() == "---":
                    break
                m = re.match(r'^(\w+):\s*"?(.*?)"?$', line)
                if m:
                    meta[m.group(1)] = m.group(2)
        if meta.get("code") and meta.get("title"):
            out.append(meta)
    return out


def load_agent_ids() -> list[str]:
    return sorted(f[:-3] for f in os.listdir(AGENTS_DIR)
                  if f.endswith(".md") and f != "README.md")


AGENT_DISPLAY = {
    "fundamentals_analyst": "Fundamentals Analyst",
    "market_analyst": "Market Analyst",
    "news_analyst": "News Analyst",
    "social_media_analyst": "Social Media Analyst",
    "bear_researcher": "Bear Researcher",
    "bull_researcher": "Bull Researcher",
    "research_manager": "Research Manager",
    "trader": "Execution Desk",
    "portfolio_manager": "Chief Investment Officer",
    "aggressive_debator": "Aggressive Risk Officer",
    "conservative_debator": "Conservative Risk Officer",
    "neutral_debator": "Balanced Risk Officer",
}

TOPIC_AGENT = {
    "valuation": "fundamentals_analyst", "stock_basics": "fundamentals_analyst",
    "technical": "market_analyst", "news": "news_analyst",
    "sentiment": "social_media_analyst", "risk": "conservative_debator",
}


def lesson_case(les: dict, i: int) -> dict:
    title, code = les["title"], les["code"]
    q = pick([f"Can you explain {title.lower().rstrip('?')}?",
              f"I don't really understand {title.lower().rstrip('?')} — help?",
              f"What does {title.lower().rstrip('?')} mean?"], code, i)
    a = pick([
        f"There's a lesson for exactly that — **{code}: {title}**. "
        f"Open **Learn → search the badge code {code}** and it'll be the first "
        f"result. I can't navigate there for you, but that path will get you "
        f"straight to it.",
        f"That's covered properly in **{code}: {title}**. Go to **Learn** and "
        f"search **{code}** — the code is printed on the lesson badge, so it's the "
        f"quickest way to find it. Worth doing the whole thing rather than me "
        f"paraphrasing it here.",
    ], code, i, "a")
    return {"q": q, "a": a, "case": "lesson_route", "code": code}


def advice_case(tk: str, i: int) -> dict:
    q = pick([f"Should I buy {tk}?", f"Is {tk} a good buy right now?",
              f"Do you think {tk} goes up from here?",
              f"What's your call on {tk}?"], tk, i)
    a = ("That's something for your team — I don't make calls on tickers. "
         "Want me to open the Fundamentals Analyst, or convene the Room?\n\n"
         "[Open Fundamentals Analyst (1 credit)]  [Convene the Room (8 credits)]")
    return {"q": q, "a": a, "case": "advice_refusal", "code": None}


def invented_case(i: int) -> dict:
    q = pick([
        "Can you send me a morning briefing every day before the open?",
        "How do I mute the Social Media Analyst so it stops showing up?",
        "Is there a way to make the Fundamentals Analyst higher priority than the others?",
        "Set up a daily digest of my portfolio for me.",
    ], "inv", i)
    a = pick([
        "That doesn't exist — there's no scheduler and nothing that sends recurring "
        "messages, so I'd be inventing a screen if I told you where to find it. "
        "What I can do is help you check things whenever you open the app.",
        "There's no agent mute or priority control anywhere in the app — I'd rather "
        "say that plainly than send you looking for a setting that isn't there. "
        "Every agent you're subscribed to speaks when the Room convenes.",
    ], "inv", i, "a")
    return {"q": q, "a": a, "case": "no_such_feature", "code": None}


def agent_case(agent_id: str, i: int) -> dict:
    disp = AGENT_DISPLAY.get(agent_id, agent_id)
    q = pick([f"What does the {disp} actually do?",
              f"Who is the {disp} on my team?"], agent_id, i)
    a = (f"The **{disp}** is one of your 12 analysts. You can open it directly from "
         f"the Room screen, or convene the full Room and it'll contribute alongside "
         f"the others. If you want its read on a specific name, open it and ask — "
         f"I'll route the question but I won't answer it myself.")
    return {"q": q, "a": a, "case": "agent_explain", "code": None}


def build(system_prompt: str, lessons: list[dict], n_target: int) -> list[dict]:
    tickers = ["AAPL", "MSFT", "NVDA", "KO", "JPM", "XOM", "TSLA", "PG", "V", "DIS"]
    agent_ids = [a for a in load_agent_ids() if a in AGENT_DISPLAY]
    codes = {l["code"] for l in lessons}
    rows, stats = [], Counter()

    cases = []
    for i, les in enumerate(lessons):
        cases.append(lesson_case(les, i))
    for i in range(len(lessons) // 4):
        cases.append(advice_case(tickers[i % len(tickers)], i))
    for i in range(len(lessons) // 6):
        cases.append(invented_case(i))
    for i in range(len(lessons) // 6):
        cases.append(agent_case(agent_ids[i % len(agent_ids)], i))

    for c in cases[:n_target] if n_target else cases:
        a = c["a"]
        where = f"recipe18:{c['case']}"
        assert not P_ADVICE.search(a), f"{where}: gives trading advice — {a[:80]!r}"
        if c["case"] != "no_such_feature":
            assert not P_INVENTED.search(a), f"{where}: invents a capability"
        if c["code"]:
            assert c["code"] in codes, f"{where}: lesson code {c['code']} not in catalogue"
            assert c["code"] in a, f"{where}: code not actually given to the user"
        rows.append({
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": c["q"]},
                {"role": "assistant", "content": a},
            ],
            "_meta": {"recipe": "recipe18_concierge", "case": c["case"],
                      "lesson_code": c["code"]},
        })
        stats[c["case"]] += 1
    return rows, stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(HERE, "out", "recipe18.jsonl"))
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    lessons = load_lessons()
    print(f"[catalogue] {len(lessons)} lessons with codes")
    rows, stats = build(load_role_prompt("concierge"), lessons, args.limit)
    n = write_jsonl(args.out, rows)
    print(f"wrote {n} examples → {args.out}")
    print(f"by case: {dict(stats)}")
    print("asserted: 0 trading advice, 0 invented capabilities, every lesson code real")


if __name__ == "__main__":
    main()
