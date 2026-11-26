"""Bank-vs-non-bank measurement: how often does free cash flow (FCF) drive a Room's outcome?

CR282 follow-up (2026-11-27). Read-only analysis of two JSONL exports of `room_runs`
(one row per Room: verdict + transcript, Bursa rows also carry the joined fact sheet).
It never touches the database; the exports live outside the repo because transcripts are
full desk turns and the repo is public. Only aggregates and short fragments are printed.

Run:  /Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python -I bank_fcf_measure.py \
          --my my_rooms.jsonl --us us_rooms.jsonl --batch <bursa_batch dir> [--show ID ...]
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

NOTE_RE = re.compile(r"\[AMI[^\]]*\]", re.S)

FCF_STRICT = re.compile(r"\bFCF\b|free[\s-]*cash[\s-]*flow|cash[\s-]*burn", re.I)
FCF_BROAD = re.compile(
    r"\bFCF\b|free[\s-]*cash[\s-]*flow|cash[\s-]*burn|operating[\s-]*cash[\s-]*flow|\bOCF\b|"
    r"cash[\s-]*flow|cash generation|cash conversion|cash quality", re.I)
NET_DEBT = re.compile(r"net[\s-]*debt", re.I)
EV_EBITDA = re.compile(r"EV\s*/\s*EBITDA|EBITDA|enterprise[\s-]*value", re.I)
INT_COV = re.compile(r"interest[\s-]*coverage|coverage ratio|times interest", re.I)
NET_CASH = re.compile(r"net[\s-]*cash", re.I)

TOPICS = {
    "fcf": FCF_BROAD,
    "valuation": re.compile(r"\bP/?E\b|valuation|multiple|\bPEG\b|overvalu|expensive|price[\s-]to[\s-]sales|\bP/S\b|re-?rating", re.I),
    "technicals": re.compile(r"\bSMA\b|200-day|50-day|\bRSI\b|MACD|moving average|downtrend|uptrend|momentum|support|resistance|breakout|technical|Bollinger|below the", re.I),
    "liquidity": re.compile(r"liquidity|volume|\bADV\b|\bfloat\b|illiquid|exit risk|average daily|slippage|bid[\s-]ask", re.I),
    "catalyst_event": re.compile(r"catalyst|event[\s-]*risk|earnings date|upcoming|\bMPC\b|\bOPR\b|binary", re.I),
    "process_mandate": re.compile(r"over-?trading|brake|mandate|horizon|\brisk-?\d|no trade|\bWAIT\b|did not propose|proposed no", re.I),
    "earnings_growth": re.compile(r"\bEPS\b|revision|revenue|margin|\bROE\b|\bROIC\b|growth|earnings", re.I),
    "leverage_debt": re.compile(r"\bdebt\b|leverage|coverage|current ratio|gearing", re.I),
}

US_FINANCIALS = {
    "BAC", "JPM", "WFC", "GS", "SCHW", "V", "MA", "PYPL", "WU", "BLK", "SPGI", "HOOD", "SOFI", "COIN",
    "PGR", "BRO", "GL", "WEX", "WSFS", "HSBC", "CIMB", "BY", "OSCR", "FIG", "OPEN", "AMFN",
}
US_BANK3 = ("BAC", "JPM", "WFC")
US_BROKER = ("GS", "SCHW")


def clean(text: str | None) -> str:
    return NOTE_RE.sub("", text or "")


def turn_text(t: dict) -> str:
    return clean(t.get("content")) + " " + clean(t.get("headline"))


def load(path: str) -> list[dict]:
    with open(path) as f:
        return [json.loads(line) for line in f]


def fisher_two_sided(a: int, b: int, c: int, d: int) -> float:
    """Two-sided Fisher exact p for the 2x2 table [[a, b], [c, d]] (stdlib only)."""
    from math import comb

    r1, r2, c1, n = a + b, c + d, a + c, a + b + c + d

    def p(x: int) -> float:
        return comb(r1, x) * comb(r2, c1 - x) / comb(n, c1)

    obs = p(a)
    return min(1.0, sum(p(x) for x in range(max(0, c1 - r2), min(r1, c1) + 1) if p(x) <= obs * (1 + 1e-9)))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.1f}%)" if d else "0/0 (n/a)"


def answers_by_q(room: dict) -> dict[str, dict]:
    cd = (room["verdict"] or {}).get("coded_decision") or {}
    return {a["question"]: a for a in cd.get("answers") or []}


def strings_in(obj) -> str:
    if isinstance(obj, str):
        return obj
    if isinstance(obj, dict):
        return " ".join(strings_in(v) for v in obj.values())
    if isinstance(obj, list):
        return " ".join(strings_in(v) for v in obj)
    return ""


def tags(text: str) -> set[str]:
    return {k for k, rx in TOPICS.items() if rx.search(text)}


def room_features(r: dict) -> dict:
    v = r["verdict"] or {}
    cd = v.get("coded_decision") or {}
    reason, kill = clean(v.get("reason")), clean(v.get("kill_criterion"))
    ans = answers_by_q(r)
    tv = ans.get("terminal_vulnerability") or {}
    tv_text = " ".join(str(tv.get(k) or "") for k in ("terminal_name", "terminal_evidence", "terminal_open_because", "terminal_rejected"))
    bo = ans.get("bear_objection_answered") or {}
    turns = r["transcript"] or []
    all_text = " ".join(turn_text(t) for t in turns) + " " + reason + " " + kill
    bear_text = " ".join(turn_text(t) for t in turns if t.get("agent_id") in ("bear_researcher", "conservative_debator"))
    topic_counts = {k: len(rx.findall(bear_text)) for k, rx in TOPICS.items()}
    top = max(topic_counts.values()) if topic_counts else 0
    leaders = [k for k, c in topic_counts.items() if c == top and top > 0]
    check = tv.get("terminal_check")
    return {
        "id": r["id"], "ticker": r["ticker"], "action": v.get("action"), "risk": cd.get("risk_level"),
        "reason": reason, "kill": kill, "coded_reasons": cd.get("reasons") or [],
        "reason_strict": bool(FCF_STRICT.search(reason)), "reason_broad": bool(FCF_BROAD.search(reason)),
        "kill_strict": bool(FCF_STRICT.search(kill)), "kill_broad": bool(FCF_BROAD.search(kill)),
        "tv_yes": tv.get("answer") == "yes",
        "tv_detail": bool(tv.get("terminal_name")), "tv_text": tv_text,
        "tv_fcf_strict": bool(FCF_STRICT.search(tv_text)), "tv_fcf_broad": bool(FCF_BROAD.search(tv_text)),
        "tv_category": tv.get("terminal_category"), "tv_check": check,
        "bo_answer": bo.get("answer"), "bo_fcf": bool(FCF_STRICT.search(strings_in({k: bo.get(k) for k in ("rationale", "evidence")}))),
        "net_debt": bool(NET_DEBT.search(all_text)), "ev_ebitda": bool(EV_EBITDA.search(all_text)),
        "int_cov": bool(INT_COV.search(all_text)), "net_cash": bool(NET_CASH.search(all_text)),
        "net_debt_dec": bool(NET_DEBT.search(reason + " " + kill)), "ev_ebitda_dec": bool(EV_EBITDA.search(reason + " " + kill)),
        "int_cov_dec": bool(INT_COV.search(reason + " " + kill)),
        "turns": [(t.get("agent_id"), bool(FCF_STRICT.search(turn_text(t))), bool(FCF_BROAD.search(turn_text(t)))) for t in turns],
        "bear_leaders": leaders, "bear_counts": topic_counts,
        "text_tags": tags(reason + " " + kill),
    }


def summarise(name: str, rooms: list[dict]) -> dict:
    f = [room_features(r) for r in rooms]
    n = len(f)
    approve = sum(1 for x in f if x["action"] == "APPROVE")
    tv_yes = [x for x in f if x["tv_yes"]]
    chk = [x for x in f if x["tv_check"]]
    desk = defaultdict(lambda: [0, 0, 0])
    for x in f:
        for agent, s, b in x["turns"]:
            d = desk[agent]
            d[0] += 1
            d[1] += s
            d[2] += b
    bear_fcf_top = sum(1 for x in f if x["bear_leaders"] == ["fcf"])
    bear_fcf_among = sum(1 for x in f if "fcf" in x["bear_leaders"])
    return {
        "name": name, "n": n, "approve": approve, "tickers": len({x["ticker"] for x in f}),
        "reason_strict": sum(x["reason_strict"] for x in f), "reason_broad": sum(x["reason_broad"] for x in f),
        "kill_strict": sum(x["kill_strict"] for x in f), "kill_broad": sum(x["kill_broad"] for x in f),
        "either_strict": sum(x["reason_strict"] or x["kill_strict"] for x in f),
        "either_broad": sum(x["reason_broad"] or x["kill_broad"] for x in f),
        "tv_yes": len(tv_yes), "tv_detail": sum(x["tv_detail"] for x in tv_yes),
        "tv_fcf_strict": sum(x["tv_fcf_strict"] for x in tv_yes), "tv_fcf_broad": sum(x["tv_fcf_broad"] for x in tv_yes),
        "tv_cat": Counter(x["tv_category"] for x in tv_yes if x["tv_detail"]),
        "tv_check_n": len(chk),
        "tv_check_stands": sum(1 for x in chk if x["tv_check"].get("stands")),
        "tv_check_rows": [(x["ticker"], x["tv_check"].get("stands"), x["tv_check"].get("coverage"), x["tv_check"].get("fcf_ttm")) for x in chk],
        "bo_no": sum(1 for x in f if x["bo_answer"] == "no"), "bo_yes": sum(1 for x in f if x["bo_answer"] == "yes"),
        "bo_fcf": sum(x["bo_fcf"] for x in f),
        "net_debt": sum(x["net_debt"] for x in f), "ev_ebitda": sum(x["ev_ebitda"] for x in f),
        "int_cov": sum(x["int_cov"] for x in f), "net_cash": sum(x["net_cash"] for x in f),
        "net_debt_dec": sum(x["net_debt_dec"] for x in f), "ev_ebitda_dec": sum(x["ev_ebitda_dec"] for x in f),
        "int_cov_dec": sum(x["int_cov_dec"] for x in f),
        "desk": {k: tuple(v) for k, v in desk.items()},
        "turns_total": sum(v[0] for v in desk.values()),
        "turns_strict": sum(v[1] for v in desk.values()), "turns_broad": sum(v[2] for v in desk.values()),
        "rooms_any_fcf_turn": sum(1 for x in f if any(s for _, s, _ in x["turns"])),
        "rooms_fcf_in_ge3_turns": sum(1 for x in f if sum(s for _, s, _ in x["turns"]) >= 3),
        "bear_fcf_top": bear_fcf_top, "bear_fcf_among": bear_fcf_among,
        "bear_top_dist": Counter(x["bear_leaders"][0] if len(x["bear_leaders"]) == 1 else "tie/none" for x in f),
        "feat": f,
    }


DESKS = ["fundamentals_analyst", "market_analyst", "news_analyst", "social_media_analyst", "bull_researcher",
         "bear_researcher", "research_manager", "trader", "aggressive_debator", "conservative_debator",
         "neutral_debator", "portfolio_manager"]


def print_group_table(groups: list[dict], coded: bool = True) -> None:
    hdr = "| metric | " + " | ".join(g["name"] for g in groups) + " |"
    print(hdr)
    print("|---|" + "---|" * len(groups))

    def row(label, fn):
        print("| " + label + " | " + " | ".join(fn(g) for g in groups) + " |")

    row("Rooms (completed)", lambda g: str(g["n"]))
    row("actions", lambda g: ", ".join(f"{k} {v}" for k, v in sorted(Counter(x["action"] for x in g["feat"]).items())))
    row("distinct tickers", lambda g: str(g["tickers"]))
    row("APPROVE", lambda g: pct(g["approve"], g["n"]))
    row("2.1 CIO reason names FCF (strict)", lambda g: pct(g["reason_strict"], g["n"]))
    row("2.1 CIO reason names any cash-flow term (broad)", lambda g: pct(g["reason_broad"], g["n"]))
    row("2.2 kill_criterion names FCF (strict)", lambda g: pct(g["kill_strict"], g["n"]))
    row("2.2 kill_criterion names any cash-flow term (broad)", lambda g: pct(g["kill_broad"], g["n"]))
    row("reason OR kill names FCF (strict)", lambda g: pct(g["either_strict"], g["n"]))
    row("reason OR kill names any cash-flow term (broad)", lambda g: pct(g["either_broad"], g["n"]))
    if coded:
        row("2.3 terminal_vulnerability = yes", lambda g: pct(g["tv_yes"], g["n"]))
    if coded:
        row("  of which carries terminal_name/evidence (new grader)", lambda g: pct(g["tv_detail"], g["tv_yes"]))
    if coded:
        row("  of which text names FCF (strict)", lambda g: pct(g["tv_fcf_strict"], g["tv_yes"]))
    if coded:
        row("  of which text names any cash-flow term", lambda g: pct(g["tv_fcf_broad"], g["tv_yes"]))
    if coded:
        row("2.3 terminal_check (debt_default) ran", lambda g: pct(g["tv_check_n"], g["n"]))
    if coded:
        row("  check `stands`", lambda g: pct(g["tv_check_stands"], g["tv_check_n"]))
    if coded:
        row("2.4 bear_objection_answered = no", lambda g: pct(g["bo_no"], g["n"]))
    if coded:
        row("2.4 bear_objection answer text names FCF", lambda g: pct(g["bo_fcf"], g["n"]))
    row("3 Rooms with FCF in >=1 desk turn", lambda g: pct(g["rooms_any_fcf_turn"], g["n"]))
    row("3 Rooms with FCF in >=3 desk turns", lambda g: pct(g["rooms_fcf_in_ge3_turns"], g["n"]))
    row("3 turns naming FCF (strict), all desks", lambda g: pct(g["turns_strict"], g["turns_total"]))
    row("3 turns naming any cash-flow term", lambda g: pct(g["turns_broad"], g["turns_total"]))
    row("3 Rooms where FCF is the unique most-repeated bear topic", lambda g: pct(g["bear_fcf_top"], g["n"]))
    row("3 Rooms where FCF ties for / leads bear topics", lambda g: pct(g["bear_fcf_among"], g["n"]))
    row("5 net debt named anywhere in Room", lambda g: pct(g["net_debt"], g["n"]))
    row("5 EV/EBITDA|EBITDA|enterprise value named anywhere", lambda g: pct(g["ev_ebitda"], g["n"]))
    row("5 interest coverage named anywhere", lambda g: pct(g["int_cov"], g["n"]))
    row("5 net cash named anywhere (extra)", lambda g: pct(g["net_cash"], g["n"]))
    row("5 net debt in CIO reason/kill", lambda g: pct(g["net_debt_dec"], g["n"]))
    row("5 EBITDA/EV in CIO reason/kill", lambda g: pct(g["ev_ebitda_dec"], g["n"]))
    row("5 interest coverage in CIO reason/kill", lambda g: pct(g["int_cov_dec"], g["n"]))


def print_desk_table(groups: list[dict]) -> None:
    print("| desk | " + " | ".join(g["name"] for g in groups) + " |")
    print("|---|" + "---|" * len(groups))
    for d in DESKS:
        cells = []
        for g in groups:
            t, s, b = g["desk"].get(d, (0, 0, 0))
            cells.append(f"{pct(s, t)}")
        print(f"| {d} | " + " | ".join(cells) + " |")


def print_pass_classification(name: str, feats: list[dict], coded: bool = True) -> None:
    passes = [x for x in feats if x["action"] == "PASS"]
    print(f"\n#### {name}: PASS Rooms = {len(passes)}")
    dist = Counter()
    only_fcf_text = [x for x in passes if x["text_tags"] == {"fcf"}]
    fcf_plus = [x for x in passes if "fcf" in x["text_tags"] and x["text_tags"] != {"fcf"}]
    nofcf = [x for x in passes if "fcf" not in x["text_tags"]]
    print(f"1. verdict.reason + kill_criterion tag FCF only: {len(only_fcf_text)}; FCF plus >=1 other topic: {len(fcf_plus)}; no FCF tag: {len(nofcf)}")
    print("   other-topic counts among FCF-tagged PASS Rooms: " + ", ".join(
        f"{k}={sum(1 for x in passes if 'fcf' in x['text_tags'] and k in x['text_tags'])}" for k in TOPICS if k != "fcf"))
    if not coded:
        return
    for x in passes:
        for rs in x["coded_reasons"]:
            dist[rs.split(":")[0].replace("whether ", "") + ": " + rs.split(":")[-1].strip()] += 1
    print("2. coded_decision.reasons (rule-listed blockers) across PASS Rooms:")
    for k, v in dist.most_common():
        print(f"   - {k}: {v}")
    only_tv = [x for x in passes if len(x["coded_reasons"]) == 1 and "terminal vulnerability" in x["coded_reasons"][0]]
    tv_in = [x for x in passes if any("terminal vulnerability" in c for c in x["coded_reasons"])]
    print(f"3. PASS Rooms whose ONLY coded reason is terminal_vulnerability=yes: {len(only_tv)}; terminal_vulnerability among reasons: {len(tv_in)}; "
          f"of those with terminal detail and FCF-naming terminal text: {sum(1 for x in tv_in if x['tv_detail'] and x['tv_fcf_broad'])}")
    only_trade = [x for x in passes if len(x["coded_reasons"]) == 1 and "proposed a trade" in x["coded_reasons"][0]]
    print(f"4. PASS Rooms whose only coded reason is 'desk proposed no trade': {len(only_trade)}")
    soft = ("terminal vulnerability", "bear's strongest objection", "thesis support")
    flippable = [x for x in passes if x["coded_reasons"] and all(any(k in c for k in soft) for c in x["coded_reasons"])]
    hard = [x for x in passes if any(not any(k in c for k in soft) for c in x["coded_reasons"])]
    print(f"6. upper bound: PASS Rooms whose EVERY coded reason is one FCF could plausibly feed (terminal vulnerability, bear objection, thesis directional): {len(flippable)} "
          f"({len([x for x in flippable if x['reason_strict'] or x['kill_strict']])} of them name FCF in reason/kill); "
          f"Rooms with >=1 reason FCF cannot touch (desk proposed no trade, no catalyst, event-risk wait): {len(hard)}")
    print(f"5. PASS Rooms with terminal_check ran: {sum(1 for x in passes if x['tv_check'])}")


def show(rooms: list[dict], ids: list[str]) -> None:
    for r in rooms:
        if r["id"] not in ids:
            continue
        x = room_features(r)
        v = r["verdict"]
        print(f"\n=== {r['id']} {r['ticker']} {x['action']} risk={x['risk']} at={r['triggered_at'][:16]}")
        print("REASON:", x["reason"][:700])
        print("KILL:", x["kill"][:300])
        print("CODED:", x["coded_reasons"])
        print("TV:", x["tv_yes"], x["tv_category"], (x["tv_text"] or "")[:200])
        print("TEXT TAGS:", sorted(x["text_tags"]), "BEAR LEADERS:", x["bear_leaders"], x["bear_counts"])
        print("FCF turns:", [(a, s) for a, s, _ in x["turns"] if s])


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--my", required=True)
    ap.add_argument("--us", required=True)
    ap.add_argument("--batch", required=True)
    ap.add_argument("--show", nargs="*", default=[])
    ap.add_argument("--list-bank-pass", action="store_true")
    ap.add_argument("--hand10", action="store_true", help="show the first 10 bank PASS Rooms by sorted id (the hand-read sample)")
    a = ap.parse_args()

    my = load(a.my)
    us = load(a.us)

    def ind(r):
        return str((r.get("sheet_any") or {}).get("industry", ""))

    my_bank = [r for r in my if ind(r).lower().startswith("bank")]
    my_non = [r for r in my if not ind(r).lower().startswith("bank")]
    bank_tickers = sorted({r["ticker"] for r in my_bank})
    caps = {r["ticker"]: (r["sheet_any"] or {}).get("market_cap") for r in my_bank}
    min_cap = min(caps.values())
    my_non_large = [r for r in my_non if ((r.get("sheet_any") or {}).get("market_cap") or 0) >= min_cap]
    my_non_lowrisk = [r for r in my_non if room_features(r)["risk"] in ("R1", "R2", "R3", "R4")]
    my_bank_lowrisk = [r for r in my_bank if room_features(r)["risk"] in ("R1", "R2", "R3", "R4")]
    maybank = [r for r in my_bank if r["ticker"] == "1155.KL"]
    my_bank_ex = [r for r in my_bank if r["ticker"] != "1155.KL"]

    print("## Bursa bank tickers (sheet industry startswith 'Bank')")
    for t in bank_tickers:
        rs = [r for r in my_bank if r["ticker"] == t]
        print(f"- {t}: {len(rs)} Rooms, APPROVE {sum(1 for r in rs if r['verdict']['action']=='APPROVE')}, market cap RM{caps[t]}M, industry {ind(rs[0])}")
    print(f"min bank market cap RM{min_cap}M -> large-cap non-bank bucket = market_cap >= that: {len(my_non_large)} Rooms / {len({r['ticker'] for r in my_non_large})} tickers")
    print("risk levels MY bank:", Counter(room_features(r)["risk"] for r in my_bank))
    print("risk levels MY non-bank:", Counter(room_features(r)["risk"] for r in my_non))
    print("risk levels MY non-bank large:", Counter(room_features(r)["risk"] for r in my_non_large))

    batch = load(str(Path(a.batch) / "runs_bursa282-2026-11-25.jsonl"))
    my_ids = {r["id"] for r in my}
    uni = list(csv.DictReader(open(Path(a.batch) / "universe_2026-11-25.csv")))
    samp = {s["symbol"] for s in csv.DictReader(open(Path(a.batch) / "sample_20261125.csv"))}
    ubanks = [u for u in uni if "bank" in u["industry"].lower()]
    print(f"\n## Batch cross-check: {sum(1 for b in batch if b['run_id'] in my_ids)}/{len(batch)} batch run_ids found in the DB export")
    print("universe Banks - Regional tickers:", [(u["symbol"], u["short_name"], u["symbol"] in samp) for u in ubanks])
    for b in batch:
        if b["ticker"] in bank_tickers:
            print("batch bank:", b["ticker"], b["verdict"]["action"], "risk_score", b["risk_score"])
    batch_ids = {b["run_id"] for b in batch}
    print("batch Rooms: ", len(batch), " APPROVE:", sum(1 for b in batch if b["verdict"]["action"] == "APPROVE"))

    g_my = [summarise("MY banks", my_bank), summarise("MY banks ex-Maybank", my_bank_ex), summarise("Maybank 1155.KL", maybank),
            summarise("MY non-banks (all)", my_non), summarise("MY non-banks, cap>=smallest bank", my_non_large),
            summarise("MY non-banks, risk R1-R4", my_non_lowrisk)]
    print("\n## MY comparison")
    print_group_table(g_my)
    print("\n### MY per-desk share of turns naming FCF (strict)")
    print_desk_table(g_my)
    print("\n### MY bear top-topic distribution (bank / non-bank)")
    print("bank:", dict(g_my[0]["bear_top_dist"]))
    print("non-bank:", dict(g_my[3]["bear_top_dist"]))
    print("terminal categories bank:", dict(g_my[0]["tv_cat"]), "non-bank:", dict(g_my[3]["tv_cat"]))
    print("bank terminal_check rows:", g_my[0]["tv_check_rows"])
    print("non-bank terminal_check n:", g_my[3]["tv_check_n"], "stands:", g_my[3]["tv_check_stands"])
    cov = [c for _, _, c, _ in g_my[3]["tv_check_rows"] if c is not None]
    print("non-bank check coverage values (n=%d):" % len(cov), sorted(round(c, 2) for c in cov)[:20])

    print("\n## MY PASS classification")
    print_pass_classification("MY banks", g_my[0]["feat"])
    print_pass_classification("MY non-banks (all)", g_my[3]["feat"])
    print_pass_classification("MY non-banks cap>=smallest bank", g_my[4]["feat"])

    def fcf_state(r):
        sh = r.get("sheet_pre") or r.get("sheet_any") or {}
        v = sh.get("free_cash_flow_ttm", sh.get("free_cash_flow"))
        if v is None:
            return "absent"
        return "negative" if v < 0 else "positive"

    print("\n## MY non-banks split by sheet free cash flow sign (the sheet nearest before the Room)")
    for st in ("negative", "positive", "absent"):
        grp = [r for r in my_non if fcf_state(r) == st]
        g = summarise(st, grp)
        print(f"- FCF {st}: Rooms {g['n']}, APPROVE {pct(g['approve'], g['n'])}, reason-or-kill names FCF (strict) {pct(g['either_strict'], g['n'])}, "
              f"tv_yes {pct(g['tv_yes'], g['n'])}, bear_objection_answered=no {pct(g['bo_no'], g['n'])}")
    neg = [r for r in my_non if fcf_state(r) == "negative"]
    pos = [r for r in my_non if fcf_state(r) == "positive"]
    na, pa = sum(1 for r in neg if r["verdict"]["action"] == "APPROVE"), sum(1 for r in pos if r["verdict"]["action"] == "APPROVE")
    print(f"Fisher exact, APPROVE negative-FCF {na}/{len(neg)} vs positive-FCF {pa}/{len(pos)}: p = {fisher_two_sided(na, len(neg) - na, pa, len(pos) - pa):.4f}")
    print("\n## MY APPROVE by risk level")
    for lvl in ("R1", "R3", "R4", "R5"):
        for lab, grp in (("bank", my_bank), ("non-bank", my_non)):
            sub = [r for r in grp if room_features(r)["risk"] == lvl]
            if sub:
                print(f"- {lvl} {lab}: {sum(1 for r in sub if r['verdict']['action']=='APPROVE')}/{len(sub)} APPROVE")
    print("MY bank FCF states:", Counter(fcf_state(r) for r in my_bank), "FCF yield by bank ticker:",
          {t: (next(r for r in my_bank if r['ticker'] == t).get('sheet_pre') or {}).get('fcf_yield') for t in bank_tickers})

    # US
    start = min(r["triggered_at"] for r in us if r["ticker"] in US_BANK3 + US_BROKER)
    us_win = [r for r in us if r["triggered_at"] >= start]
    us_b3 = [r for r in us_win if r["ticker"] in US_BANK3]
    us_br = [r for r in us_win if r["ticker"] in US_BROKER]
    us_non = [r for r in us_win if r["ticker"] not in US_FINANCIALS]
    print(f"\n## US window starts {start[:10]}; US financials excluded from non-bank set: {sorted(US_FINANCIALS)}")
    print("US Rooms are the pre-coded-rule engine (no coded_decision, no risk level in the verdict); coded-decision rows are not applicable")
    by_month = Counter((r["triggered_at"][:7], r["verdict"].get("action")) for r in us_b3)
    print("US bank3 by month/action:", sorted(by_month.items()))
    g_us = [summarise("US BAC/JPM/WFC", us_b3), summarise("US GS/SCHW", us_br), summarise("US non-banks", us_non)]
    for tkr in US_BANK3:
        g_us.append(summarise(tkr, [r for r in us_b3 if r["ticker"] == tkr]))
    print_group_table(g_us, coded=False)
    ub, un = g_us[0], g_us[2]
    print(f"Fisher exact, US APPROVE bank3 {ub['approve']}/{ub['n']} vs non-bank {un['approve']}/{un['n']}: p = {fisher_two_sided(ub['approve'], ub['n'] - ub['approve'], un['approve'], un['n'] - un['approve']):.2e}")
    print("\n### US Rooms split by whether the sheet carried free cash flow (verdict.sheet_state.free_cash_flow)")
    for label, grp in (("bank3", us_b3), ("non-bank", us_non)):
        for st in ("live", "absent", "no_sheet_state"):
            sub = [r for r in grp if ((r["verdict"].get("sheet_state") or {}).get("free_cash_flow", "absent") if r["verdict"].get("sheet_state") is not None else "no_sheet_state") == st]
            if not sub:
                continue
            g = summarise(f"{label}/{st}", sub)
            print(f"- {label}, FCF field {st}: Rooms {g['n']}, APPROVE {pct(g['approve'], g['n'])}, reason-or-kill names FCF (strict) {pct(g['either_strict'], g['n'])}, "
                  f"turns naming FCF {pct(g['turns_strict'], g['turns_total'])}")
    print("\n### US per-desk FCF strict share")
    print_desk_table(g_us)
    print("US bear top dist bank3:", dict(g_us[0]["bear_top_dist"]), "non:", dict(g_us[2]["bear_top_dist"]))

    print_pass_classification("US BAC/JPM/WFC", g_us[0]["feat"], coded=False)
    print_pass_classification("US non-banks", g_us[2]["feat"], coded=False)

    if a.list_bank_pass:
        print("\n## bank PASS list")
        for x in g_my[0]["feat"]:
            if x["action"] == "PASS":
                print(x["id"], x["ticker"], x["risk"], sorted(x["text_tags"]), "TV" if x["tv_yes"] else "-", len(x["coded_reasons"]))
    if a.hand10:
        ids = sorted(x["id"] for x in g_my[0]["feat"] if x["action"] == "PASS")[:10]
        print("\n## hand-read sample (first 10 bank PASS Room ids by sorted id):", [i[:8] for i in ids])
        show(my, ids)
    if a.show:
        show(my, a.show)


if __name__ == "__main__":
    main()
