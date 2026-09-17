"""C08 Parts 2-3 -- extract tickers from each chatbot reply into out/picks.csv.

Replies are prose/markdown; a reply that gives picks does so in one block near
the top (a markdown table or a numbered/bulleted list), sometimes followed by
unrelated tables further down (an "as of my last data" ETF aside, or -- for
asof2019 replies -- a "how it actually performed" hindsight table). Only the
FIRST block containing >=1 recognisable ticker or mappable company name is
read; nothing after it is scanned, so a later hindsight table never
contaminates the picks. A reply with no such block is a REFUSAL (0 picks).

The known-symbol set is U_LARGE100 (frozen, do not edit) plus a supplementary
list in out/other_symbols_seen.json, built by reading >=12 replies across all
three models by eye first (see out/DEVIATIONS.md / commit history for that
review) -- so a bare bold/parenthetical token only becomes a pick if it is a
real symbol actually seen in this reply set, never any uppercase word.
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CODE_DIR = Path(__file__).resolve().parent
OUT_DIR = CODE_DIR.parent / "out"
RESPONSES_DIR = OUT_DIR / "responses"

sys.path.insert(0, str(CODE_DIR))
from universe_large100 import U_LARGE100  # noqa: E402

N_PICKS_EXPECTED = 10

NAME_TO_TICKER = {
    "alphabet": "GOOGL",
    "google": "GOOGL",
    "berkshire hathaway": "BRK-B",
    "berkshire": "BRK-B",
    "facebook": "META",
    "meta platforms": "META",
    "taiwan semiconductor": "TSM",
    "tsmc": "TSM",
    "ge vernova": "GEV",
    "mercadolibre": "MELI",
    "vertiv": "VRT",
    "constellation energy": "CEG",
    "alibaba": "BABA",
    "crowdstrike": "CRWD",
    "shopify": "SHOP",
    "micron": "MU",
    "uber": "UBER",
    "visa": "V",
    "mastercard": "MA",
    "microsoft": "MSFT",
    "amazon": "AMZN",
    "nvidia": "NVDA",
    "apple": "AAPL",
    "eli lilly": "LLY",
    "jpmorgan chase": "JPM",
    "jpmorgan": "JPM",
    "jp morgan": "JPM",
    "broadcom": "AVGO",
    "unitedhealth": "UNH",
    "costco": "COST",
    "adobe": "ADBE",
    "intuitive surgical": "ISRG",
    "netflix": "NFLX",
    "asml": "ASML",
    "asml holding": "ASML",
}

# Whole-token match only: a capital letter run that is NOT immediately
# preceded or followed by a lowercase letter, so the first letter of a
# normally-capitalised word ("The", "This") never reads as a 1-letter ticker.
TICKER_TOKEN_RE = re.compile(r"(?<![A-Za-z])[A-Z]{1,5}(?:[.\-][A-Z])?(?![a-z])")
TABLE_ROW_RE = re.compile(r"^\s*\|(.+)\|\s*$")
TABLE_SEP_RE = re.compile(r"^\s*\|[\s:\-|]+\|\s*$")
BULLET_ROW_RE = re.compile(r"^\s*[-*]\s+(.+)$")
# A numbered item, optionally under a markdown heading prefix ("## 3. Foo" or
# plain "3. Foo"/"3) Foo"). Group 1 is the item number, group 2 its text.
NUMBERED_ITEM_RE = re.compile(r"^\s*(?:#{1,4}\s*)?(\d{1,2})[.\)]\s+(.+)$")


def load_known_symbols() -> set[str]:
    other = json.loads((OUT_DIR / "other_symbols_seen.json").read_text())
    return set(U_LARGE100) | set(other["symbols"])


def _extract_ticker_from_text(cell: str, known: set[str]) -> str | None:
    for m in re.findall(r"\(([A-Z]{1,5}(?:[.\-][A-Z])?)\)", cell):
        if m in known:
            return m
    for m in re.findall(r"\*\*([A-Z]{1,5}(?:[.\-][A-Z])?)\*\*", cell):
        if m in known:
            return m
    for m in TICKER_TOKEN_RE.findall(cell):
        if m in known:
            return m
    lowered = cell.lower()
    for name, ticker in NAME_TO_TICKER.items():
        if name in lowered:
            return ticker
    return None


def _split_table_row(row: str) -> list[str]:
    return [c.strip() for c in row.strip().strip("|").split("|")]


MIN_TICKER_HITS = 3
MIN_HIT_FRACTION = 0.5


def _looks_like_picks_block(rows: list[str], known: set[str]) -> bool:
    """A real picks list/table names a stock in most of its rows; a stray
    prose bullet list matches a ticker/company name by accident at most once
    or twice. Require both a minimum count and a minimum hit-rate so a
    "Market context" bullet list (one bullet mentions "Apple" in passing)
    is never mistaken for the picks themselves."""
    if not rows:
        return False
    hits = sum(1 for row in rows if _extract_ticker_from_text(row, known) is not None)
    if hits < MIN_TICKER_HITS:
        return False
    return hits / len(rows) >= MIN_HIT_FRACTION


def _collect_numbered_block(lines: list[str], start: int) -> tuple[list[str], int]:
    """Starting at the line matching item "1", collect item texts in strictly
    increasing numeric order, tolerating blank lines and short prose between
    items (a paragraph continuing the previous item's thesis) but stopping at
    a line that starts a new markdown table or a new unrelated heading."""
    n = len(lines)
    items: list[str] = []
    expected = 1
    i = start
    last_item_line = start
    while i < n:
        line = lines[i]
        m = NUMBERED_ITEM_RE.match(line)
        if m and int(m.group(1)) == expected:
            items.append(m.group(2))
            expected += 1
            last_item_line = i
            i += 1
            continue
        if line.strip() == "":
            i += 1
            continue
        if TABLE_ROW_RE.match(line) or (m and int(m.group(1)) != expected):
            break
        if i - last_item_line > 3:
            break
        i += 1
    return items, last_item_line + 1


def _find_picks_block(lines: list[str], known: set[str]) -> list[str] | None:
    """Return the raw text of each row in the FIRST block (table, numbered
    list/headings, or bullet list) that looks like a real picks list (see
    `_looks_like_picks_block`); None if no such block is found in the reply."""
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        if TABLE_ROW_RE.match(line) and not TABLE_SEP_RE.match(line):
            block = []
            j = i
            while j < n and TABLE_ROW_RE.match(lines[j]):
                if not TABLE_SEP_RE.match(lines[j]):
                    block.append(lines[j])
                j += 1
            body = block[1:]  # drop the header row
            if _looks_like_picks_block(body, known):
                return body
            i = j
            continue

        m = NUMBERED_ITEM_RE.match(line)
        if m and int(m.group(1)) == 1:
            items, next_i = _collect_numbered_block(lines, i)
            if _looks_like_picks_block(items, known):
                return items
            i = next_i
            continue

        bm = BULLET_ROW_RE.match(line)
        if bm:
            block = []
            j = i
            while j < n and BULLET_ROW_RE.match(lines[j]):
                block.append(BULLET_ROW_RE.match(lines[j]).group(1))
                j += 1
            if _looks_like_picks_block(block, known):
                return block
            i = j
            continue

        i += 1
    return None


def extract_picks(reply: str, known: set[str], name_to_ticker: dict[str, str] | None = None) -> list[str]:
    """Conservative ticker extraction: only the first picks block counts,
    and only tokens/names in `known`/`name_to_ticker` become a pick."""
    global NAME_TO_TICKER
    prior = NAME_TO_TICKER
    if name_to_ticker is not None:
        NAME_TO_TICKER = name_to_ticker
    try:
        lines = reply.splitlines()
        block = _find_picks_block(lines, known)
        if block is None:
            return []

        picks: list[str] = []
        for row in block:
            if len(picks) >= N_PICKS_EXPECTED:
                break
            cells = _split_table_row(row) if "|" in row else [row]
            ticker = None
            for cell in cells:
                ticker = _extract_ticker_from_text(cell, known)
                if ticker:
                    break
            if ticker and ticker not in picks:
                picks.append(ticker)
        return picks
    finally:
        NAME_TO_TICKER = prior


def main() -> None:
    known = load_known_symbols()
    rows = []
    for path in sorted(RESPONSES_DIR.glob("*.json")):
        record = json.loads(path.read_text())
        name = record.get("name", path.stem)
        parts = name.split("_")
        prompt_key = parts[0]
        model = parts[1]
        run = parts[2]

        reply = record.get("reply")
        if reply is None:
            rows.append({
                "file": path.name, "prompt_key": prompt_key, "model": model, "run": run,
                "n_picks": 0, "tickers": "", "refused": True, "in_universe_count": 0,
            })
            continue

        picks = extract_picks(reply, known)
        refused = len(picks) == 0
        in_universe_count = sum(1 for t in picks if t in U_LARGE100)

        rows.append({
            "file": path.name, "prompt_key": prompt_key, "model": model, "run": run,
            "n_picks": len(picks), "tickers": ";".join(picks), "refused": refused,
            "in_universe_count": in_universe_count,
        })

    out_path = OUT_DIR / "picks.csv"
    with out_path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["file", "prompt_key", "model", "run", "n_picks", "tickers", "refused", "in_universe_count"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"wrote {len(rows)} rows to {out_path}")
    print(f"{'file':<28} {'prompt':<10} {'model':<8} {'run':<4} {'n':<3} {'refused':<8} {'in_univ':<8} tickers")
    for r in rows:
        print(f"{r['file']:<28} {r['prompt_key']:<10} {r['model']:<8} {r['run']:<4} {r['n_picks']:<3} "
              f"{str(r['refused']):<8} {r['in_universe_count']:<8} {r['tickers']}")

    print("\nrefusal / hedge (0-pick) rate per model x prompt:")
    from collections import defaultdict
    counts = defaultdict(lambda: [0, 0])
    for r in rows:
        key = (r["prompt_key"], r["model"])
        counts[key][1] += 1
        if r["refused"]:
            counts[key][0] += 1
    for key in sorted(counts):
        refused_n, total_n = counts[key]
        print(f"  {key[0]:<10} {key[1]:<8} {refused_n}/{total_n} refused ({100.0 * refused_n / total_n:.0f}%)")


if __name__ == "__main__":
    main()
