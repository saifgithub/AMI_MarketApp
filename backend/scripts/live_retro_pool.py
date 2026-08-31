"""CR214 Step 4 — pool the live-Room retrospective panel through CR164's estimators.

`weekly_room_retro.py` scores each week's due LIVE Room verdicts and writes
`scored_<ISO-week>.jsonl`. Each file is read in isolation and nothing has ever
run the CR164 controls over the panel as a whole. This does, using the SAME
functions `backtest_report.py` uses — imported, never reimplemented — so a live
number and a backtest number are comparable by construction rather than by
inspection.

Two things this refuses to do quietly, because both would manufacture an answer:

**It never pools across weekly files.** The weekly output is CUMULATIVE, not
incremental: measured 2026-09-01, `scored_2026-W34.jsonl` (141 runs) is a
strict subset of `scored_2026-W35.jsonl` (162 runs), overlap 141 of 141.
Concatenating the directory therefore double-counts every earlier run and
inflates the apparent date count — 303 rows over 46 dates where the truth is
162 over 28. It reads the newest file alone.

**It reports the prompt-partition mix rather than averaging over it.**
`weekly_room_retro.py` recovers `llm_audit.prompt_version` per run precisely so
that generations are never silently pooled; honouring that here means printing
the mix, not hiding it behind a single number.

The live Room is the un-ablated one — news, social and analyst consensus are
present, where the as-of backtest has them UNAVAILABLE — so this panel measures
the Room that actually ships. Its weakness is volume: organic convenes arrive a
couple of names at a time, which is a different limit from the backtest's and
one that waiting does not fix.
"""

from __future__ import annotations

import argparse
import collections
import json
import random
import sys
from datetime import date
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent))

from backtest_report import (  # noqa: E402
    ACTIONS,
    SIGNAL_ACTIONS,
    by_date,
    clustered_ci,
    paired_spread,
    placebo_effect,
)

LIVE_HORIZONS = (("1w", "excess5"), ("4w", "excess20"))


def newest_scored(dir_path: Path) -> Path:
    """The newest weekly file — which contains every earlier one. See module docstring."""
    files = sorted(dir_path.glob("scored_*.jsonl"))
    if not files:
        raise SystemExit(f"no scored_*.jsonl under {dir_path}")
    return files[-1]


def load_rows(path: Path) -> list:
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        r = json.loads(line)
        rows.append(SimpleNamespace(
            action=r["action"],
            as_of=date.fromisoformat(r["as_of"]),
            ticker=r["ticker"],
            excess5=r.get("excess5"),
            excess20=r.get("excess20"),
            # The live scorer stops at 20 trading days; the ~13-week cell the
            # backtest reports has no live counterpart yet. None, not zero.
            excess62=None,
            approve_votes=r.get("approve_votes"),
            samples=r.get("samples"),
            partition=r.get("partition") or "unversioned",
        ))
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--dir", type=Path, required=True,
                    help="Directory holding weekly_room_retro's scored_*.jsonl")
    ap.add_argument("--bootstrap", type=int, default=10000)
    ap.add_argument("--seed", type=int, default=214)
    ap.add_argument("--out", type=Path, default=None)
    args = ap.parse_args()

    src = newest_scored(args.dir)
    rows = load_rows(src)
    rng = random.Random(args.seed)

    L: list[str] = [
        f"# Live Room retrospective — pooled ({src.name})",
        "",
        f"Source: `{src}` — the newest weekly file, which is cumulative and "
        "contains every earlier one. Concatenating the directory would "
        "double-count.",
        "",
        f"- Runs: **{len(rows)}**",
    ]

    for label, attr in LIVE_HORIZONS:
        scored = [r for r in rows if getattr(r, attr) is not None]
        dates = {r.as_of for r in scored}
        L.append(f"- Scored at {label}: **{len(scored)}** over **{len(dates)}** dates")

    acts = collections.Counter(r.action for r in rows)
    L += ["", "## Verdict mix", "",
          "| action | n | share |", "|---|---|---|"]
    for a in ACTIONS:
        if acts.get(a):
            L.append(f"| {a} | {acts[a]} | {acts[a] / len(rows):.1%} |")
    approve = sum(acts.get(a, 0) for a in SIGNAL_ACTIONS)
    L += ["",
          f"Approve rate **{approve / len(rows):.1%}** — against the as-of "
          "backtest Room's ~9-10%. The gap is the ablation: news, social and "
          "analyst consensus are UNAVAILABLE under as-of and present here."]

    parts = collections.Counter(
        "mixed" if r.partition.startswith("mixed:") else r.partition for r in rows
    )
    L += ["", "## Prompt-generation mix", "",
          "`weekly_room_retro.py` recovers the prompt version per run so "
          "generations are never silently pooled. The mix is reported, not "
          "averaged away.", ""]
    for k, v in parts.most_common():
        L.append(f"- `{k}`: {v} runs ({v / len(rows):.0%})")
    if len(parts) > 1:
        L += ["", "> **This panel spans more than one prompt generation.** Every "
              "figure below is an average over versions of the Room, not a "
              "measurement of one of them."]

    L += ["", "## Within-date paired spread (market factor cancelled)", ""]
    L += paired_spread(rows, bootstrap=args.bootstrap, rng=rng, horizons=LIVE_HORIZONS)

    L += ["", "## Placebo-adjusted selection effect", ""]
    L += placebo_effect(rows, bootstrap=args.bootstrap, rng=rng, horizons=LIVE_HORIZONS)

    # The binding constraint on this panel, stated with the number that shows it.
    L += ["", "## Why the paired arm uses so few dates", ""]
    for label, attr in LIVE_HORIZONS:
        a_d = by_date(rows, attr, SIGNAL_ACTIONS)
        p_d = by_date(rows, attr, ("PASS", "REJECT"))
        all_d = sorted(set(a_d) | set(p_d))
        both = sorted(set(a_d) & set(p_d))
        if not all_d:
            continue
        per = sum(len(a_d.get(d, [])) + len(p_d.get(d, [])) for d in all_d) / len(all_d)
        L.append(
            f"- **{label}**: {len(both)} of {len(all_d)} scored dates carry both "
            f"buckets, at **{per:.1f} runs per date**. A within-date spread needs "
            "both legs on the same day, and organic convenes do not supply them: "
            "the user convenes a couple of names at a time, so most dates are "
            "single-bucket. This is a volume limit, not a price-data limit, and "
            "waiting does not fix it — a pinned slate that convenes ~100 names on "
            "ONE date does."
        )

    out = args.out or (args.dir / f"pooled_{src.stem.replace('scored_', '')}.md")
    text = "\n".join(L) + "\n"
    Path(out).write_text(text)
    print(text)
    print(f"[pool] {len(rows)} runs from {src.name} → {out}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
