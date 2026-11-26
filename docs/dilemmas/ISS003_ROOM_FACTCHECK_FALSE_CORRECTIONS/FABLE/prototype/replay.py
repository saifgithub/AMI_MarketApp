"""ISS003 / FABLE — replay stored Rooms through (a) today's checker and (b) the
grounding prototype, and print the population numbers SOLUTION.md quotes.

Input is NOT in the repo (it is real Room text; the repo is public). Export it
read-only from Alpha into a scratch folder:

  ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -Atc \\
    \\"select json_build_object('run_id', r.id, 'ticker', r.ticker, 'at', r.triggered_at,
       'transcript', r.transcript, 'sheet', s.sheet)
     from room_runs r join room_fact_sheets s
       on s.sheet_hash = r.bank_inputs->>'fact_sheet'
     where r.status='completed'\\"" > rooms.jsonl

Run from the repo's backend/ folder (needs the app importable, nothing else):

  .venv/bin/python ../docs/dilemmas/ISS003_ROOM_FACTCHECK_FALSE_CORRECTIONS/FABLE/prototype/replay.py \\
      rooms.jsonl out_dir [mandates.jsonl]

Writes out_dir/old_findings.json and out_dir/own_figures.json for hand adjudication.
The ledger here is an approximation of the production one: the rendered sheet is
exact, but coded lines are recovered from the transcript by pattern and the mandate
is only present when mandates.jsonl is given. So the OWN counts are an upper bound.
"""

from __future__ import annotations

import collections
import json
import os
import random
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.getcwd())

from grounding import Ledger, classify, extract  # noqa: E402

from app.services import numeric_quotation as nq  # noqa: E402
from app.services.cio_snapshot_codec import decode_profile  # noqa: E402
from app.services.room_prompts import _format_profile  # noqa: E402
from app.schemas.agents import AgentId  # noqa: E402

NOTE = re.compile(r"\n*\[AMI checked .*?figures of record\.\]", re.S)
TAG = re.compile(r"\s*\[AMI: unverifiable[^\]]*\]")
# Text the code wrote into a turn (Risk Officer option frames, coded notes, the
# mandate-compliant levels line). Production reads these from their source.
CODED = [
    re.compile(r"\(≈[^)]*\)"),
    re.compile(r"option(?:, |: )\*\*[\d.]+%\*\* of portfolio"),
    re.compile(r"\[[^\]]{0,600}\]"),
    re.compile(r"Mandate-compliant levels[^\n]*"),
    re.compile(r"Risk Officer's call:[^\n]*"),
    re.compile(r"Key figure:[^\n]*"),
]


def numeric_leaves(o, acc):
    if isinstance(o, bool) or o is None:
        return
    if isinstance(o, (int, float)):
        acc.append(float(o))
    elif isinstance(o, dict):
        for v in o.values():
            numeric_leaves(v, acc)
    elif isinstance(o, list):
        for v in o:
            numeric_leaves(v, acc)


def main() -> None:
    rooms_path, out_dir = sys.argv[1], sys.argv[2]
    mandates = {}
    if len(sys.argv) > 3:
        for line in open(sys.argv[3]):
            if line.strip():
                d = json.loads(line)
                mandates[d["run_id"]] = d["mandate"]
    rooms = {}
    for line in open(rooms_path):
        if line.strip():
            d = json.loads(line)
            rooms[d["run_id"]] = d

    st = collections.Counter()
    old, own = [], []
    cross_pool: list[tuple[str, Ledger]] = []
    per_room_own = collections.defaultdict(list)
    ledger_sizes: list[int] = []
    own_ledgers: dict[str, Ledger] = {}

    for rid, d in rooms.items():
        mkt = "MY" if d["ticker"].endswith(".KL") else "US"
        profile = decode_profile(d["sheet"])
        # Each desk is shown its own cut of the sheet (the Execution Desk sees the
        # liquidity lines, the news desk sees the feed). Production builds one
        # ledger per desk from that desk's real prompt; here the union stands in.
        led = Ledger()
        seen_lines: set[str] = set()
        for aid in [None, *AgentId]:
            try:
                rendered = _format_profile(profile, aid)
            except Exception:  # noqa: BLE001
                st[(mkt, "sheet_render_failed")] += 1
                continue
            for ln in rendered.splitlines():
                if ln not in seen_lines:
                    seen_lines.add(ln)
                    led.add_text("sheet", ln)
        raw: list[float] = []
        numeric_leaves(profile, raw)
        if os.environ.get("ISS003_RAW_LEAVES") == "1":
            # Off by default: a raw profile value the desk was never shown is not
            # a figure of record for this purpose, and it raises chance matches.
            for v in raw:
                led.add_value("sheet", v)
                led.add_value("sheet", v * 1e6)
        m_leaves: list[float] = []
        numeric_leaves(mandates.get(rid), m_leaves)
        for v in m_leaves:
            led.add_value("mandate", v)
        sheet_only = Ledger(list(led.entries))
        cross_pool.append((d["ticker"], sheet_only))
        ledger_sizes.append(len({(round(e.value, 6), e.cls) for e in sheet_only.entries}))
        own_ledgers[rid] = sheet_only
        st[(mkt, "rooms")] += 1
        room_old = 0
        room_own = 0
        for t in d["transcript"] or []:
            if t.get("scripted"):
                continue
            stored = t.get("content") or ""
            st[(mkt, "stored_old_notes_users_saw")] += stored.count("AMI checked “")
            # Stored Risk Officer tags: is every figure in the tagged quote a sheet figure?
            for tm in re.finditer(r"([^\n]{0,90})\[AMI: unverifiable\]", stored):
                quote = tm.group(1).split("decided by")[-1].split("Key figure:")[-1]
                qf = [f for f in extract(quote) if f.kind == "figure"]
                st[(mkt, "stored_unverifiable_tags")] += 1
                st[(mkt, "stored_unverifiable_tags_all_figures_on_sheet")] += bool(qf) and all(
                    sheet_only.find(f) for f in qf
                )
            text = TAG.sub("", NOTE.sub("", stored))
            st[(mkt, "turns")] += 1
            # (a) today's checker
            for mm in nq.find_sheet_mismatches(text, profile):
                room_old += 1
                claim_figs = [f for f in extract(mm.claimed_raw)]
                on_sheet = any(sheet_only.find(f) for f in claim_figs)
                st[(mkt, "old_findings")] += 1
                st[(mkt, "old_findings_claim_is_on_sheet")] += on_sheet
                old.append(dict(
                    run_id=rid, ticker=d["ticker"], market=mkt, agent=t.get("agent_id"),
                    field=mm.field_name, claimed=mm.claimed_raw.strip(), sheet=mm.sheet_value,
                    claim_is_on_sheet=on_sheet,
                    ctx=text[max(0, mm.start - 110):mm.end + 90].replace("\n", " "),
                ))
            # (b) grounding
            for pat in CODED:
                for cm in pat.finditer(text):
                    led.add_text("coded", cm.group(0))
            for p in classify(text, led):
                st[(mkt, "numerals")] += 1
                st[(mkt, "status_" + p.status)] += 1
                if p.status == "record":
                    st[(mkt, "record_via_" + "+".join(p.sources))] += 1
                if p.status == "own":
                    room_own += 1
                    own.append(dict(
                        market=mkt, ticker=d["ticker"], agent=t.get("agent_id"), raw=p.fig.raw,
                        ctx=text[max(0, p.fig.start - 100):p.fig.end + 70].replace("\n", " "),
                    ))
            # later turns may restate this turn's figures
            led.add_text("debate", text)
        st[(mkt, "rooms_with_old_finding")] += bool(room_old)
        per_room_own[mkt].append(room_own)

    # Coincidence control: a figure from Room A scored against the sheet of a
    # DIFFERENT ticker. Whatever matches there matches by chance.
    random.seed(3)
    chance = collections.Counter()
    items = list(rooms.items())
    for rid, d in random.sample(items, min(150, len(items))):
        other = random.choice([lg for tk, lg in cross_pool if tk != d["ticker"]])
        for t in (d["transcript"] or [])[:6]:
            text = TAG.sub("", NOTE.sub("", t.get("content") or ""))
            for f in extract(text):
                if f.kind != "figure":
                    continue
                key = f"{f.cls}/{min(f.dec, 2)}dp"
                chance[(key, "n")] += 1
                chance[(key, "hit")] += bool(other.find(f))

    # Alteration control: take a figure the desk quoted correctly from the sheet,
    # change it by 3-60% at the same precision, and score it against ITS OWN Room's
    # sheet. A hit is an altered figure that would be shown as a figure of record.
    altered = collections.Counter()
    for rid, d in random.sample(items, min(200, len(items))):
        lg = own_ledgers[rid]
        for t in (d["transcript"] or [])[:8]:
            text = TAG.sub("", NOTE.sub("", t.get("content") or ""))
            for f in extract(text):
                if f.kind != "figure" or not lg.find(f) or f.value == 0:
                    continue
                factor = random.choice([-1, 1]) * random.uniform(0.03, 0.6) + 1
                v = round(f.value / f.mult * factor, f.dec) * f.mult
                if v == f.value:
                    continue
                g = type(f)(f.raw, v, f.mult, f.dec, f.cls, f.kind, f.start, f.end)
                key = f"{f.cls}/{min(f.dec, 2)}dp"
                altered[(key, "n")] += 1
                altered[(key, "hit")] += bool(lg.find(g))
                altered[("ALL", "n")] += 1
                altered[("ALL", "hit")] += bool(lg.find(g))

    os.makedirs(out_dir, exist_ok=True)
    json.dump(old, open(os.path.join(out_dir, "old_findings.json"), "w"), indent=1)
    json.dump(own, open(os.path.join(out_dir, "own_figures.json"), "w"), indent=1)

    for k in sorted(st):
        print(f"{k[0]:3} {k[1]:40} {st[k]}")
    for mkt, xs in per_room_own.items():
        xs.sort()
        print(f"{mkt:3} own figures per Room: median {xs[len(xs)//2]}, p90 {xs[int(len(xs)*.9)]}, max {xs[-1]}")
    ledger_sizes.sort()
    print(f"distinct sheet figures per Room: median {ledger_sizes[len(ledger_sizes)//2]}, max {ledger_sizes[-1]}")
    print("\naltered sheet figure still matches its own sheet by chance (class/decimals: hits/n):")
    for key in sorted({k[0] for k in altered}):
        n, h = altered[(key, "n")], altered[(key, "hit")]
        if n >= 100:
            print(f"    {key:14} {h}/{n} = {h/n:.0%}")
    print("\nchance match against another ticker's sheet (class/decimals: hits/n):")
    for key in sorted({k[0] for k in chance}):
        n, h = chance[(key, "n")], chance[(key, "hit")]
        if n >= 100:
            print(f"    {key:14} {h}/{n} = {h/n:.0%}")


if __name__ == "__main__":
    main()
