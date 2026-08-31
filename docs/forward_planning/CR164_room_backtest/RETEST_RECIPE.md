# CR164 — the pinned regression re-test recipe

> ## ⚠️ SUSPENDED 2026-08-31 — the baseline below is no longer a comparator (DEF385)
>
> **Do not run this recipe as a regression check.** The recipe's whole promise is *"did we
> change the Room?"* — measured by replaying a pinned plan and diffing against
> `r70-outcome-2`. That promise requires everything except the change under test to hold
> still. **The model did not hold still.**
>
> CR211 (2026-08-28) records the on-prem serve moving: `Qwen3.6-35B-A3B-NVFP4` on `:8000`
> died and **`qwen3.8-flash-next`** came up on `:8048`. `:8000` answers again today serving
> that same Qwen3.8 build, and **the alias `ami-llm` was reused across the swap** — so the
> provenance line in `PHASE_B_OUTCOME_2026-08-20.md:20` ("snapshot `e850c696…` — unchanged
> since the cutoff probe, so the 2025-02-28 window start still holds") now names a model
> that is no longer being served, while reading as though nothing moved.
>
> Two independent things break as a result:
>
> 1. **A replay would change the model AND the code**, so any diff is uninterpretable — the
>    one failure mode the pinned plan exists to prevent.
> 2. **Five of the plan's 18 as-of dates are no longer post-cutoff.** A fresh probe
>    ([`results/cutoff_probe_2026-08-31.md`](results/cutoff_probe_2026-08-31.md)) moves
>    `window_start` **2025-02-28 → 2025-08-01** (price-collapse 2024-08 → 2025-01; last
>    recalled event 2025-01 → 2025-06). `2025-02-28`, `2025-04-11`, `2025-05-09`,
>    `2025-06-13` and `2025-07-11` now sit **inside the model's own knowledge**. Replaying
>    them would produce a batch the prompt scanner still calls clean, because the scanner
>    checks prompts against `as_of` — never `as_of` against the model.
>
> **`r70-outcome-2` is not retracted.** It ran on Qwen3.6, where every one of its dates was
> genuinely post-cutoff, and it remains valid for the model it measured. What is dead is its
> use as a *baseline for future runs*.
>
> **To restore a regression instrument**, a new pinned plan must be cut on `window_start =
> 2025-08-01` (52 usable Fridays at the 20-trading-day horizon, ~43 at ~90 days) and a fresh
> baseline measured on the current serve. That is CR214's sweep; this recipe should be
> rewritten against it rather than patched.
>
> **The durable lesson, which is why DEF385 is filed against code and not just this file:**
> `--window-start` is an *input*. CR164 is rightly proud that the leakage refusal is "code,
> not convention" — but the number that refusal enforces was a convention all along, and it
> went stale silently. Until the sweep refuses to start unless the probe backing its window
> was measured against the model currently answering, this can recur without a symptom.


**Acceptance criterion 5.** *"A pinned regression batch spec is committed and documented as the
post-infra-CR re-test recipe."*

This is that recipe. It exists so that **"we changed the Room — did we break it?"** is a ~4-hour
mechanical operation with a published baseline to diff against, rather than a re-derivation.

The one design decision that makes it possible: as-of mode lives in the **production services**,
not a fork. `backtest_sweep.py` drives the real Room through the real gateway, so replaying the
pinned plan after a prompt, agent or data-layer CR tests the thing that shipped.

---

## The pinned artefact

| | |
|---|---|
| Plan | [`pairs_r70-outcome-1.jsonl`](pairs_r70-outcome-1.jsonl) — 450 pairs, **18 as-of dates × 25 tickers** |
| SHA-256 | `cf4974b4ad647b71985a6ccb0a331630424cf439e339be550b3e520e5d484d10` |
| Universe | [`tickers_142_no_splits.txt`](tickers_142_no_splits.txt) — the split-free set (DEF335 mitigation) |
| Window | `2025-02-28` .. `2026-07-16` |
| Baseline report | [`results/report_r70-outcome-2.md`](results/report_r70-outcome-2.md) |

**Verify the plan before you trust a comparison.** The host copy and the repo copy must be the
same bytes, or the "replay" is a different experiment wearing the same name:

```bash
shasum -a 256 docs/forward_planning/CR164_room_backtest/pairs_r70-outcome-1.jsonl
ssh melehost "sha256sum ~/ami_trade/backtest_results/_outcome_pairs.jsonl"
# both must read cf4974b4ad647b71985a6ccb0a331630424cf439e339be550b3e520e5d484d10
```

**`--pairs-file`, never `--seed` alone.** Seed-plus-window reproduces a plan only if
`--window-end` is also pinned; omit it and the Friday count shifts with the calendar, silently
changing pairs. The file replays the pairs that actually **completed**, which is the set the
baseline was computed on.

---

## Run it

**Always under the supervisor — and `nohup` is not a substitute (DEF387).**

> A bare `nohup docker compose exec -T … &` over ssh **will die when the ssh channel closes**.
> `nohup` blocks SIGHUP; it does not keep `docker compose exec`'s daemon pipes open. On
> 2026-08-31 that killed a sweep at convene 5 of 52 and it sat undetected for **2h49m** — the
> DEF345 signature exactly, no traceback, no non-zero exit, the log simply ending after a
> normal completion line. The reasoning that skipped the supervisor ("nothing is recreating the
> container") was wrong: recreation is *one* cause of exec death, not the class. Use `setsid`
> and the supervisor, always.
>
> **And watch for staleness, not progress.** A monitor filtered on progress lines and error
> strings cannot see death, because death emits neither — it will stay quiet and read as
> healthy. Poll for: log unwritten > 900 s (against a ~250 s convene), supervisor process
> absent, completion sentinel present. The cheap arithmetic tell is the same one that caught
> DEF345: divide elapsed by convenes completed and compare against the convene time.

 The sweep runs as `docker compose exec`, so any lane recreating
`ami_api_alpha` kills it mid-batch with no traceback — that is how `r70-outcome-2` lost 2.5 h after
17 runs. The sweep is resumable; the supervisor relaunches it.

```bash
ssh melehost
cd ~/ami_trade
# Pick a FRESH batch-id. Never reuse one: the server's uq_backtest_run gate
# 409s every pair of an existing batch, and you would score the old run.
sed -i 's/^BATCH=.*/BATCH=r70-retest-<CR###>/' backtest_results/_supervise_outcome2.sh
nohup bash backtest_results/_supervise_outcome2.sh >/dev/null 2>&1 &
tail -f /tmp/cr164_outcome2.log
```

The command it issues, for reference:

```bash
docker compose exec -T api-alpha python scripts/backtest_sweep.py \
  --batch-id "$BATCH" --window-start 2025-02-28 --n-pairs 450 --seed 164 \
  --pairs-file /backtest_results/_outcome_pairs.jsonl \
  --universe-file /backtest_results/_tickers_142.txt \
  --out-dir /backtest_results
```

**Exit codes that mean stop, not retry:**

- **3 — DEF336 outage abort.** Three consecutive LLM-outage fail-safe verdicts. An outage PASS is a
  *completed* run carrying a PASS verdict, so every counter reads it as a decision; `r70-outcome-1`
  recorded 450 of them and reported "450 completed, 0 failed". Fix the provider and re-run under a
  **new** batch-id. The supervisor deliberately does not retry this.
- **No `complete_<batch>.json`** — the sweep never reached its own end (DEF345). `backtest_report`
  refuses the batch with exit 5 before touching the DB. Resume rather than scoring a truncated
  sample as a whole one.

---

## Score it

```bash
docker compose exec -T api-alpha python scripts/backtest_prompt_scan.py \
  --batch-id "$BATCH" --out-dir /backtest_results
docker compose exec -T api-alpha python scripts/backtest_report.py \
  --batch-id "$BATCH" --seed 164 --bootstrap 10000 --stamp $(date -u +%F) \
  --out-dir /backtest_results
```

The report is **byte-reproducible**: same DB state + same `--seed` + same `--stamp` ⇒ identical
bytes. A diff that is not explained by the change under test is itself the finding.

**Reading the run-accounting line (DEF358).** `Sweep completion` is derived from the sentinel's
numbers, not from the file existing. `**COMPLETE**` means every planned pair completed;
`**INCOMPLETE**` means the sweep ended cleanly with pairs short; `**REACHED ITS END**` means a
pre-DEF358 sentinel whose `completed` counts only the final process's work and understates any
resumed batch — read `Index rows` for the real population. `report_r70-outcome-2.md` is one of
those, which is why its line reads `completed 50` against 450 index rows.

---

## The baseline to diff against

`r70-outcome-2`, 446 scored of 450, 18 distinct as-of dates, arm `pit_v1`:

| Measure | Baseline |
|---|---|
| APPROVE 4w excess vs SPY | **+1.40%** (n=40) |
| PASS 4w excess vs SPY | **+0.25%** (n=406) |
| APPROVE − PASS 4w spread | **+1.15%** |
| Block-bootstrap CI over dates | **−2.05% .. +4.43%** (median +1.17%) |
| Pooled random-pick null | **p = 0.3010** |
| Verdict mix | APPROVE 40 · PASS 406 · REJECT 0 · MODIFY 0 |
| Effective n | **18 dates**, not 446 runs |

**What a diff can and cannot say.** The CI spans zero, so the baseline does not establish edge —
it establishes a *measurement*. A re-test is therefore a **regression check**, not a promotion
gate: it answers "did this CR move the Room's behaviour outside the noise we already quantified?"
Against a ~12% verdict-flip noise floor and an effective n of 18, only a large move is readable.
Do not report a re-test as evidence that a change improved the Room.

**Also fixed by construction, and worth re-checking every time:** the prompt scan exits 1 on any
hard fail. `r70-outcome-2`'s seven were one sentence — a Bull Researcher thesis horizon a year past
as-of, i.e. a *stated* future date, not leaked data — and its 592 flags were arithmetic collisions
established by permutation against a far-future control window. `AsOfLeakageError` never fired.
Expect the same shape; investigate any hard fail that is not a stated horizon.

---

## Cost

~450 convenes. Budget a working day of wall-clock with relaunches, and grant the batch user credits
up front (the sweep tops up once on a 402). Nothing here touches live user data: the batch runs
under its own generated user, and scoring reads `backtest_run_index ⋈ room_runs` and
`price_history_daily` only — never a live quote.
