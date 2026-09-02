# WP07 — Harness + measurement (R29–R32, R46, R47, R48, R54)

The measurement half of CR219. R54 (ruled): the standing replay harness lives INSIDE
CR219 — AC4 and both experiments below depend on it. Can start in parallel with the
prompt WPs. Model routing: Opus or reviewed Sonnet — design-heavy.

## R29 — what citation rate does and does not prove (convergent)

Citation-rate recovery (AC4) is a **suppression proxy**: it shows agents stopped
refusing data they hold. It says nothing about whether the Room's *answer* got better.
The harness below is the outcome instrument. Write this distinction into the harness
README so nobody later claims AC4 as a quality result.

## R31 — the harness (ruled 2026-09-02: merged design, DECISIONS §3)

Build QWEN's frame at Kimi/GLM's scale:

- **Frame** (`../QWEN/03_improved_plan.md` Phase 5): ticker × mandate golden-set
  matrix, **deterministic scorers** — checks computable from the transcript/verdict
  without a judge model (examples: verdict schema validity; stance-envelope parse
  rate; numbers-quoted-match-sheet rate; mandate-echo correctness; safety-floor
  agreement; citation-of-LIVE-fields rate per WP01's fixes).
- **Scale first**: 4–5 tickers with **cached profiles** (the pickle recipe in
  `../evidence/README.md` §Reproducing — cached because market data moves, R46, and
  a pickle is a local fixture, never committed). 3 mandates each (short/medium/long),
  honoring the production Mandate coherence rules — do NOT recreate the `h_short`
  harness artifact (`convene_gemini.py:77` hardcoded `LONG_HORIZON` while `--horizon`
  varied; incoherent combos produced 4 artifact reports).
- **R32 (convergent)**: PM verdicts inside the harness mirror production —
  `pm_self_consistency_samples=5` vote, never single draws.
- Grow to 8–10 tickers once scorers hold. Runs target the live vLLM
  (LAN-direct, `http://192.168.20.74:8048`); running against a second model is
  CR217's business, not CR219's.
- Home: `../harness/` (new subfolder in the CR folder), scripts runnable from any CWD
  (path-derived like `../evidence/` scripts), venv-invoked.

## R46 — acceptance #5 rewording

The base CR doc's "evidence/ regenerates" implies byte-identical output, which a moving
market makes impossible. Reword (in the base CR doc's acceptance section) to:
**"the evidence scripts run clean against a freshly built profile"** — exit 0, all
turns complete — not byte-equality. One-line doc edit; cite register R46.

## R30 — AC4 trails (treated as decided; DECISIONS §"also settled")

After the prompt WPs promote to Alpha: wait ~1–2 weeks of real traffic, rerun
`../evidence/analysis/citation_rates.py` against the post-fix `llm_audit` corpus, log
the before/after in the CR folder. **Trailing, not gating; no revert on a null result
— a null is a new finding.** Remember the real-user exclusion list
(`feedback_user_report_exclusions`): filter the CR035 synthetics + seed rows if the
corpus query touches user tables.

## R47 — PM self-consistency (re-derived 2026-09-02; the original ask is dead)

Production default is already **5** (`backend/app/core/config.py:751`, since CR214) —
do NOT change config. The remaining work: measure **residual flip rate at n=5** in the
harness (the known ~19.7% was measured at n=1). Method: on 2–3 cached profiles, run
the PM stage k=20 times each and report vote-outcome variance. If residual flip
> ~5%, report the number — raising n further is Saiful's call, not the worker's
(decode cost scales linearly; config comments at `config.py:123/:139` record the
latency ceilings that shaped n=5).

## R48 — thinking-mode experiment (ruled: rides CR219; PM-only, measured)

The live model is a reasoning model running with `reasoning_tokens: 0` (verified
2026-08-31 probe — thinking OFF). Experiment, in order:

1. **Probe whether the serve honors per-request thinking** (e.g.
   `chat_template_kwargs: {"enable_thinking": true}` or the build's equivalent) with
   one `curl` to `192.168.20.74:8048` — LAN-direct. Note: the gateway's
   `enable_thinking: False` at `llm_gateway.py:1021` is the **DashScope** provider
   path, not vLLM; the stale comment at `:627–629` misleads — read the code, not the
   comment.
2. If the serve needs a server-side config change instead → **STOP; remote hosts need
   Saiful's explicit go per step.** Report what's needed, don't do it.
3. If per-request works: harness A/B on the **PM stage only** (GLM R5 concurs),
   thinking on vs off, same cached profiles, deterministic scorers + verdict-variance
   as the metrics. **Re-derive the PM decode budget first** — thinking tokens spend
   from the same completion budget; check `_AGENT_MAX_TOKENS`/tier settings so
   thinking-on runs aren't silently truncated (that would fabricate a losing arm).
4. Ship a default change only on a measured win; otherwise bank the numbers in the
   CR folder.

## Acceptance

- Harness runs end-to-end on one cached profile from a clean checkout (venv only),
  writes a scored JSON + a README explaining every scorer.
- R47 + R48 results banked as dated notes in `../harness/results/`.
- No harness code imports from `../evidence/` by copy-paste — shared logic gets
  extracted, or imported from the evidence scripts directly.
