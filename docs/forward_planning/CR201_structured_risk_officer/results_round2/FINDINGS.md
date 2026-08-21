# CR201 step 2, round 2 — the same measurement with the parser fixed

Run: 2026-08-21, `backend/scripts/pm_debate_ablation.py --variants v1a v1b v8 v9
--concurrency 16`, LAN-direct to the on-prem vLLM at `http://192.168.20.74:8000`
serving `ami-llm` (`RedHatAI/Qwen3.6-35B-A3B-NVFP4`). 136 committed convenes over
four prompt epochs, four arms, 544 recorded PM replays + 272 Risk Officer calls.
Per-call rows in `ablation_calls.jsonl`, generated tables in `ABLATION_SUMMARY.md`.

**The only thing that changed between round 1 and round 2 is `extract_json_object`**
(DEF352, `0cf99b69`). Same script, same corpus, same prompts, same model, same
host. That is what makes the two runs comparable and what makes this one an
answer rather than another reading.

## The blocking finding is closed

| arm | trailing prose after the JSON | otherwise unparseable | discarded |
|---|---|---|---|
| v8 round 1 | 56 / 136 (41.2%) | 2 (1.5%) | **42.6%** |
| v9 round 1 | 59 / 136 (43.4%) | 1 (0.7%) | **44.1%** |
| **v8 round 2** | **0 (0.0%)** | 1 (0.7%) | **0.7%** |
| **v9 round 2** | **0 (0.0%)** | 1 (0.7%) | **0.7%** |

Not one reply in 272 was thrown away for closing with a disclaimer. The model
still writes the disclaimer — the corpus shows it — the parser now reads past
it. 0.7% is one reply per arm, and it is the same convene in both: a genuine
non-object, which is what the residual is supposed to be.

## And the gap that worried round 1 went with it

| arm | APPROVE | rate | vs v1a: APPROVE→PASS / PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|---|
| v1a — baseline | 22/136 | 16.2% | — | — | — |
| v1b — same prompt again | 22/136 | 16.2% | 10 / 10 | **+0** | **1.000** |
| v8 — shipped prompt, block rendering | 18/135 | 13.3% | 10 / 6 | +4 | 0.455 |
| **v9 — the SHIPPED assembly** | **21/133** | **15.8%** | **9 / 9** | **+0** | **1.000** |

Round 1 measured the shipped assembly at 12.0% against an 18.5% baseline, net
+8 one-directional, p=0.077, and flagged it as the open question. Round 2
measures it at **15.8% against 16.2%**, net **+0**, **9/9 — the exact symmetric
shape the model's own resampling produces (10/10)**. The 6.5pp gap was the
discard, not the rendering: an arm that loses 44% of its officer payloads is an
arm running on the ladder alone for nearly half its convenes, and CR197 measured
the ladder-only floor at 11.8%, which is almost exactly where round 1 landed.

**Both halves of CR201 now reproduce the debate.** The prompt did in round 1
(v8, net 0, p=1.0) and does again; the assembly does now that the payload
reaches the CIO.

## The rendering question round 1 opened is answered too

Head to head on the 134 convenes where both arms produced a verdict: **v8→v9 is
4 APPROVE→PASS against 9 PASS→APPROVE**. The point estimate now favours the
SHIPPED rendering (three turns under the three risk AgentIds) over the block —
the opposite of round 1's lean, and by a similar margin. Two runs disagreeing in
direction at this n is the honest reading of "not resolvable": the script's own
bound is ~8–10pp at n≈136 and this difference is 2.5pp. What matters for the
rollout is that the shipped rendering is the one that lands on the baseline, and
it does not need to beat v8 to ship — it needs to match v1a, and it does exactly.

No third arm is proposed. Round 1's suggested one-arm test was to decide between
renderings; the deciding number now says the shipped one is fine, and building
an arm to separate 13.3% from 15.8% at this n would answer nothing.

## What still weakens this, unchanged from round 1

- **The corpus has no TARGET** — `build_option_ladder` runs with `target=None`
  on all 136 convenes, so no ladder carries a reward:risk column. Production
  supplies one whenever the Execution Desk set a target, so the officer is
  measured with *less* evidence than it will have. An understatement.
- **n cannot resolve a small effect.** A difference under ~8–10pp is not
  resolvable here. A null bounds the effect; it does not prove one. What it
  rules out is a repeat of round 1's 6.5pp one-directional gap.
- **13 unique tickers across four prompt epochs** — clustered, not independent.
- **The evidence block is today's rendering**, byte-exact for the newest epoch
  (39/39) and current-worded for the three older ones. Every figure is the run's
  own; only the wording is current.
- Baselines move between sessions: 16.3% (CR197), 18.5% (round 1), 16.2% (here).
  Which is why every contrast in this file is paired within its own run.

## Recommendation

**Enable `ROOM_RISK_OFFICER_ENABLED`.** The CR's own rollout gate was: fix the
read, re-measure with the discard at ~1%, then decide. The discard is 0.7%, and
the shipped assembly reproduces the debate at p=1.0 with the symmetric flip
shape of pure resampling, at full n on the production read path.

What it buys, from the code rather than this run: the RISK phase goes from three
LLM calls to one and from three serial round-trips to one (12 agent calls per
convene become 10), and the phase's decode budget falls from 3,200 tokens
(800 + 1,300 + 1,100) to 1,800. Wall-clock was not measured here — this script
replays the PM, not a whole Room.

What to watch after enabling, since it is cheap to watch and the thing this
measurement cannot see: the live rate of `fallback_reason="the reply could not
be parsed"` on `_run_risk_officer`. Round 1 exists because that number was 43%
in a place nobody was looking. It should now sit under 1%.
