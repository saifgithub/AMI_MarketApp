# 04 — vLLM temperature cascade, 10x repeats

## Method

`backend/scripts/ibm_run_a_t1_repeat10.py` takes one captured prompt (the
`fundamentals_analyst` call, one run's user), and sends it 10 times at one
explicit temperature — run as a cascade per Saiful's instruction: start at
T=1.0, then step down (0.8, 0.6, 0.4, 0.2) only if the prior temperature did
not converge (i.e. all 10 draws did not agree). Both `temperature` and `seed`
are otherwise unset everywhere in this codebase, per
[01](01_divergence_sources.md) — this cascade is the first place either is
pinned, and only for the purpose of this test.

## Run A — data gap

Run A's cascade (T=1.0 → 0.8 → 0.6, stopping at T=0.4 once unanimous) was run and
reported live, but its raw JSON outputs were lost to a `docker` container
restart on melehost mid-investigation (`ami_api_alpha` restarted, wiping `/tmp`,
before the files were pulled off the host). **The numbers below are the real,
measured results as reported at the time — not re-derived, not estimated — but
the underlying completions are not preserved in [`out/`](out/) for this run.**
This gap is stated rather than backfilled.

| Temperature | Distribution (10 draws) |
|---|---|
| T=1.0 | 3 FOR / 7 NEUTRAL |
| T=0.8 | 1 FOR / 9 NEUTRAL |
| T=0.6 | 2 FOR / 8 NEUTRAL |
| T=0.4 | **10/10 NEUTRAL — unanimous, cascade stopped here** |

## Run B — raw data preserved

Run B's cascade (T=1.0 → 0.8 → 0.6, stopping at T=0.6 once unanimous) is fully
preserved:
[`out/04a_vllm_run_b_repeat10_T1.0.json`](out/04a_vllm_run_b_repeat10_T1.0.json),
[`out/04b_vllm_run_b_repeat10_T0.8.json`](out/04b_vllm_run_b_repeat10_T0.8.json),
[`out/04c_vllm_run_b_repeat10_T0.6.json`](out/04c_vllm_run_b_repeat10_T0.6.json).

| Temperature | Distribution (10 draws) |
|---|---|
| T=1.0 | 4 FOR / 6 NEUTRAL |
| T=0.8 | 1 FOR / 9 NEUTRAL |
| T=0.6 | **10/10 NEUTRAL — unanimous, cascade stopped here** |

## Read

- **Neither run ever produced SELL/AGAINST** at any temperature tested — the
  model's uncertainty band on this ticker sits entirely within FOR↔NEUTRAL.
- **Lower temperature converges toward NEUTRAL, not toward the original run's
  stance.** Both runs' original completions happened to land on the *minority*
  mode at low temperature (Run A: FOR, converges to NEUTRAL by T=0.4; Run B:
  NEUTRAL, already the mode at T=1.0, converges fully by T=0.6). If either
  original run had been read on its own as "the" answer, it would have been an
  unrepresentative draw.
- **Run B converges at a higher temperature than Run A** (0.6 vs 0.4) — one data
  point, not enough to generalize from, but worth carrying into
  [05](05_kimi_cross_check.md), where the same asymmetry shows up on a second,
  independent provider.
- Production runs at neither temperature — it runs at whatever vLLM's own
  server-side default is, unpinned. Both tested points (0.6, 0.4) are below what
  a real Room convene experiences today, so this is a *floor* on the instability
  a real run sees, not a ceiling.
