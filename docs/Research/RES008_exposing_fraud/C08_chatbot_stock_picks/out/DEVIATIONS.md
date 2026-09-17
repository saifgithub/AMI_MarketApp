# C08 — deviations from PREREGISTRATION.md

Recorded as they occur. Nothing in the spec's parameters, universe, windows, metrics or
thresholds is changed; each entry below is a choice made where the spec was silent or an
infeasibility was hit.

## BK has no data from Yahoo

`BK` (frozen in `universe_large100.py`) returns no data from `yfinance` (`common/data.py`
raises `ValueError`). Per the spec, a name without data at a window start is simply not
drawable — it is excluded from the available-names pool for any window, never substituted.
Confirmed: `common/cache/BK_1d.csv` does not exist and `load_daily(["BK"], ...)` raises.
99/100 U_LARGE100 names have data throughout.

## Part 3 random-portfolio pool: 98 names, not 99

Part 3 draws its 10,000 random control portfolios from U_LARGE100 names with data on
2019-01-02. That excludes BK (no data at all, above) and also PLTR, which did not IPO until
September 2020 and so genuinely has no 2019-01-02 bar -- not a data gap, the company was not
public yet. Per the spec's own rule ("from names with data at the window start"), PLTR is
correctly excluded for this window, exactly as BK is excluded everywhere. n=98 available
names, recorded in `out/results.json` / `out/part2_3_analysis.json` as
`n_available_universe_names_at_2019_01_02`.

## First reply-collection pass discarded

Mid-task, `out/responses/` was found to have been repopulated with a smaller, newer set of
files than the 55 I had sampled while writing the ticker parser (see `03_parse_picks.py`
design notes). Independently verified before acting on it: `out/_discarded_pass1/` exists on
disk holding exactly the 60 originally-collected files plus a `README.md` explaining the
fault (a developer-tool plugin injected its own context into the collection calls; several
replies visibly answer as "a development assistant" — e.g. `now_haiku_01.json` and
`now_sonnet_01.json` from that pass, which I had read directly during initial sampling,
both pivot to "If you have other questions I can help with — like building web applications
on Vercel" / "This is a coding/dev environment, not a financial research tool," neither of
which belongs in an answer to the stated finance prompt). That contamination signature
matches what I had already observed first-hand, so the discard is corroborated, not taken on
faith. Nothing from the discarded pass was used in any figure below; the parser and all
Part 2/3 analysis were run only against the re-collected `out/responses/` files once that
set reached 60. `out/_discarded_pass1/` was left untouched (not read further, not deleted —
outside this task's write scope for `out/responses/`-adjacent data anyway).
