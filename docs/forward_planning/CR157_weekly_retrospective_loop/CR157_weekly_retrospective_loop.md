# CR157 — Weekly retrospective loop: score convened Rooms against reality

**Filed:** 2026-08-08 · **Status:** proposed · **Decision:** Saiful, 2026-08-08 —
*"This is the improvement loop CR. We will look back at the rooms that were
convened and the results that were concluded. We need to check 'prediction'
against reality, maybe weekly, on non-trading days, and do a post mortem on the
quality of the ticker evaluation and prediction."*

> **Provenance note (2026-08-09).** This document was reconstructed from
> `_registry/CR157.row.md` by a different session. The row was filed but left
> **unfinished** — no trailing `status | folder | tag` fields and no folder — which
> kept `test_registers_no_drift.py` red in the shared checkout and blocked the CR
> register from being regenerated at all. Saiful asked for the row to be tracked,
> so the three missing fields were completed (`proposed`, this folder, `AT:R66`)
> and this doc written **from the row's own text, adding no scope**. The row
> remains the filing of record. If the owning session has a fuller draft, it
> should overwrite this file; nothing here is meant to pre-empt it.

## Why

CR143's 12-agent audit measured **process** quality — grounding, format, scope
discipline. Nothing measures **outcome** quality: whether a Room's conclusion
about a ticker was actually right. This CR closes that loop.

## What it builds

### 1. Scoreable-conclusion capture

`room_runs` already persists ticker, timestamps, the full transcript and the
verdict as JsonB (`backend/app/db/models.py:530-557`) — the raw material exists.
What is **not** captured as structured fields: the reference price at convene
time, the Trader's entry/stop/target levels, and per-agent `[STANCE]` headers
(they live only inside transcript prose).

Add a `room_run_conclusions` table (or JsonB column) written at run end:
reference price, PM verdict action + size, trader levels, per-agent
stance/conviction/headline.

### 2. Weekly scoring batch, on non-trading days

A job (systemd timer on melehost, precedent in `infra/systemd/`; weekend UTC so
US market closes are final) pulls realized prices through the existing yfinance
history path (`market_data.py`'s `CachingProvider` — **no new provider**) and
scores every conclusion aged ≥7 days:

- direction correctness vs the reference price;
- target-hit / stop-hit where levels exist;
- against a same-window buy-and-hold baseline.

Multiple horizons (1w, 4w), so fast feedback does not force short-termism into a
long-horizon product.

### 3. Post-mortem report

A per-agent scorecard — which agents' stances correlated with outcomes, split by
conviction — plus failure classification using the CR143 taxonomy (E1
hallucination / E2 arithmetic / E3 format / E4 scope / E5 missing-state), so a bad
outcome is traced to a **cause class** rather than merely counted.

Output lands in `docs/forward_planning/CR143_agent_prompt_audit/` (or a successor
home) as the standing evidence base for future prompt CRs, and feeds the
eval-harness golden set.

## Discipline constraints

- **Scores are an internal quality signal, never user-facing.** A lucky PM PASS is
  not "advice that worked".
- **Never pool rates across mandate regimes.** The CR153/CR156 lesson: three
  different single-name caps inside one epoch corpus already burned one audit.
- **Small-n honesty.** Per-agent sample sizes will be single-digit for weeks;
  report confidence, not verdicts.
- **Rooms the user never acted on still score.** The conclusion is the unit of
  quality, not the trade.

## Out of scope

Changing any agent behaviour; auto-tuning prompts from scores (a later CR, gated
on this one producing trustworthy data); any brokerage or live-trading linkage.

## Acceptance

- Conclusions captured on 100% of new runs.
- The weekly batch runs unattended on a non-trading day and scores all due
  conclusions.
- The post-mortem names at least the cause class of every scored miss.
- One full cycle demonstrated on real Alpha data before any prompt change cites it.

## Note added in reconstruction

CR158 (prompt-version stamp, built 2026-08-09) is a hard dependency in practice
rather than in principle: this CR's whole value is comparing outcomes across time,
and without a per-row `prompt_version` a weekly score silently pools runs from
different prompt generations — the exact error that put a wrong 18.4% reformatter
rate into CR143. The scoring batch should partition by `llm_audit.prompt_version`,
not by date.

## As-built (v1, 2026-08-20, AT:R73)

Built as `backend/scripts/weekly_room_retro.py` (commit `8b592e0d`), a read-only in-container
batch mirroring CR164's `backtest_report.py`. Four claims above are stale as specced; recorded
here rather than rewriting the spec:

1. **No `room_run_conclusions` table was added (§1).** By build time, `room_runs.verdict`
   already carried structured action/size/levels and `room_runs.transcript` carried per-agent
   stance/conviction/headline (CR106 B1/B2, live since 2026-07-29). The only missing capture was
   the convene-time reference price — v1 reconstructs it as adjusted close at the last stored
   trading date ≤ convene date, CR164's exact entry convention, so live-retro numbers stay
   directly comparable with backtests. A true captured intraday quote is a v2 schema decision.
2. **No systemd timer (§2).** `infra/systemd/` holds only the pre-Docker A8 unit; the live
   scheduling precedent is the melehost host crontab (CR051 daily report, DEF201 janitor). The
   recommended line (Saturday 09:30 UTC, after Friday's US close is final):
   `30 9 * * 6 docker exec ami_api_alpha python -m scripts.weekly_room_retro --out /backtest_results/weekly_retro >> /home/saiful/ami_trade/reports/weekly_room_retro.log 2>&1`
3. **Prices come via `app/services/price_history.py::get_daily_series` (§2)**, the table-backed
   read-through daily path — not `market_data.py`'s `CachingProvider`, which is the 60s quote
   path. The bar refresh is the script's only product-table write, skippable via `--no-refresh`,
   and `test_never_writes_product_tables` pins that nothing else writes.
4. **Output home is this folder (§3).** Reports land under `--out` (always pass it explicitly —
   the default `./retro_reports` is not gitignored); the E1–E5 post-mortem labels land in
   `results/` here, the CR164 pattern — not in the CR143 folder.

Also as decided at build: outage verdicts excluded via `room_runner.is_llm_outage_verdict`
(DEF336's lesson — a dead-provider PASS is not a scoreable call); synthetic users excluded via
the CR051 `REAL_PRED` filter; runs `<7` days old and `backtest_run_index` rows excluded; rates
partitioned by `llm_audit.prompt_version` per the reconstruction note; E1–E5 labeling stays a
human Claude-session task reading `misses_<ISO-week>.jsonl` — no unattended LLM call ("prompt
instructions are not controls").
