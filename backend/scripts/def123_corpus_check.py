"""DEF123 acceptance harness — re-runnable measurement of the fabrication rate
CR104 closes: what fraction of Room fundamentals prompts declared as LIVE
carry a numeric value that is actually the old rng-seeded synthetic baseline.

Usage (from a machine with `ssh melehost` configured, per CLAUDE.md — the
Mac never runs the backend, so this queries melehost's Postgres over SSH,
same pattern DEF123's own investigation used):

    ssh melehost "docker exec ami_postgres psql -U postgres -d ami_trade -t -A -F'|' -c \\"
        SELECT id, created_at,
          substring(system_prompt from 'Ticker: ([A-Z]+)') AS ticker,
          substring(system_prompt from 'P/E: ([0-9.]+|not available)') AS pe,
          (system_prompt LIKE '%LIVE from Yahoo Finance as of this call%') AS declared_live
        FROM llm_audit
        WHERE flow='room' AND agent_id='fundamentals_analyst'
          AND created_at > now() - interval '60 days'
    \\"" > /tmp/def123_corpus_raw.tsv

    backend/.venv/bin/python backend/scripts/def123_corpus_check.py /tmp/def123_corpus_raw.tsv

Re-derives the exact synthetic P/E `_profile_for_ticker` used to compute
pre-CR104 (`random.Random(zlib.crc32(ticker))`, draw base_price then pe —
draw ORDER matters, crc32-seeded Random is deterministic per draw sequence)
and counts how many LIVE-declared prompts' rendered P/E matches it exactly.

CR104 acceptance is this count going to 0 — but that can only be TRUE of
prompts generated AFTER the fix ships to Alpha (`/promote-to-alpha`, a
separate Saiful-gated step this lane does not take). Historical rows already
served under the bug stay fabricated forever; re-running this script against
them will keep reporting DEF123's original count until the window rolls past
the promotion date. Re-run with a `created_at > <promotion timestamp>` filter
in the query above once promoted, to see the true post-fix rate.
"""

from __future__ import annotations

import random
import sys
import zlib


def synth_pe(ticker: str) -> str:
    """Reproduces exactly the pre-CR104 `_profile_for_ticker` synthetic P/E
    draw: same rng, same seed, same draw ORDER (base_price drawn first)."""
    rng = random.Random(zlib.crc32(ticker.upper().encode()))
    rng.uniform(0, 400)  # base_price draw — must precede the pe draw
    pe = rng.uniform(12, 55)
    return f"{pe:.1f}"


def main(path: str) -> int:
    total = declared_live = fabricated = 0
    tickers: set[str] = set()
    with open(path) as f:
        for line in f:
            parts = line.rstrip("\n").split("|")
            if len(parts) != 5:
                continue
            _id, _created_at, ticker, pe, live = parts
            total += 1
            if live != "t":
                continue
            declared_live += 1
            if not ticker or pe in ("", "not available"):
                continue
            if pe == synth_pe(ticker):
                fabricated += 1
                tickers.add(ticker)

    print(f"total prompts:        {total}")
    print(f"declared LIVE:        {declared_live}")
    print(f"fabricated P/E:       {fabricated}")
    print(f"distinct tickers:     {len(tickers)}")
    if tickers:
        print(f"  {sorted(tickers)}")
    print()
    print("PASS (0 fabricated)" if fabricated == 0 else "FAIL — DEF123 still reproducing")
    return 0 if fabricated == 0 else 1


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print(f"usage: {sys.argv[0]} <corpus.tsv>", file=sys.stderr)
        raise SystemExit(2)
    raise SystemExit(main(sys.argv[1]))
