# CR256 layer-2 verdict — envelope enforcement PASSES the gate, 2026-10-16

**Instrument:** the v6-matched census — 30 tickers × 3 reps = 90 rooms, risk 4,
DeepInfra `deepseek-ai/DeepSeek-V4-Flash`, backend-default prompts +
`ROOM_CARDS_ENVELOPE_ENABLED=true` (build `c2fbb80b`). Shards
`cr256-env3-r4-a..f` (commit `7f0a8073`), 6 concurrent, 90/90 arms completed
2026-10-16 ~02:16 melehost time.

## The verdict

| census | n subjects | ICC(A,1) | gate ≥0.85 |
|---|---|---|---|
| v6 pilot, raw (~34% desks filed) | 30 | 0.62 | FAIL |
| v6 pilot, repaired | 30 | 0.67 | FAIL |
| env2 probe, enforcement ON | 10 | 0.842 | miss by 0.008 (FCEL sole drag → 0.907 dropped) |
| **env3, enforcement ON** | **30** | **+0.868** | **PASS** |

Same-sign across reps 27/30; mean within-ticker spread 0.272; per-ticker
spreads 0.08–0.50 with no distressed-name outlier at env2's FCEL scale.

## Enforcement census — 360 desk-turns

- Desks without a parseable CLAIMS block: **3 (0.8%)** — re-asked once each,
  all retries filed all five cards (`room_cards_repaired` ×4).
- Malformed card lines: 17 (1.0%) — counted and dropped, never guessed.
- Scripted fallbacks: 16 (overnight DeepInfra 429 storms) — almost all on
  non-desk agents; scripted turns are never re-asked by design, and the three
  desk-level absences above are the honest residue.

## What layer 2 establishes

1. **The card channel is stable when filing is mechanically enforced.** The
   entire v6 → env3 delta is enforcement: identical contract, identical
   composite, identical model and tickers. Voluntary filing (0.62) → in-turn
   enforcement (0.868). The spec's Layer-1 design is validated end-to-end.
2. **The composite (`net_support − 0.1×unanswered`) is now a measurable,
   reproducible evidence signal per room** — the input CR256's deterministic
   verdict bar consumes.
3. Repairs work as designed: bounded, in-turn, self-generated, 4/4 successes,
   zero repair loops.

## Next rung — the fresh 30×5 acceptance run

The last rung of the CR256 pipeline (Step 0 ✅, M7 ✅, pilot ✅, envelope
re-pilot ✅): risk levels 1–5 × the ticker set, envelope ON, per model.
ami-llm is reachable again (HTTP 200 on :8002 as of this verdict); dsv4-Flash
is proven by this census. Cost shape ≈ 150 rooms/model.

## Data

- Runs: `docs/tools/room_investigation_V2/out/cr256-env3/runs_all.jsonl`
- Report: `docs/tools/room_investigation_V2/out/cr256-env3/analysis/report.{md,json}`
- Probe: `env2_probe_2026-10-15.md` (the n=10 miss-by-a-hair and its FCEL decomposition)
- melehost logs: `/tmp/cr256_env3_{a..f}.log`
