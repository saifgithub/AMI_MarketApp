# CR201 step 2 — the shipped Risk Officer, measured against the production assembly

Run: 2026-08-21, `backend/scripts/pm_debate_ablation.py`, LAN-direct to the on-prem
vLLM at `http://192.168.20.74:8000` serving `ami-llm`
(`RedHatAI/Qwen3.6-35B-A3B-NVFP4`). 136 committed convenes over four prompt epochs,
five arms, 680 recorded PM replays + 408 Risk Officer calls, concurrency 16.
Parameters in `run_meta.json`, per-call rows in `ablation_calls.jsonl`, generated
tables in `ABLATION_SUMMARY.md`, assembly comparison in `ASSEMBLY_DIFF.md`.

## The arms

| arm | officer prompt | decode budget | what reaches the CIO | reply read with |
|---|---|---|---|---|
| v1a / v1b | — | — | the recorded prompt, untouched (v1b = second draw) | — |
| v8 | **shipped** `build_risk_officer_messages` | **1800** | one `render_risk_assessment` block ahead of the transcript (CR197's shape) | `extract_json_object`, as production does |
| v9 | **shipped** | **1800** | **three `render_officer_turns` turns appended where the debate was** — the shipped assembly | `extract_json_object`, as production does |
| v9t | **shipped** | **1800** | same as v9 | the object between the first `{` and last `}` — the design apart from today's parser |

## Headline

| arm | APPROVE | rate (95% CI) | vs v1a: APPROVE→PASS / PASS→APPROVE | net | exact McNemar p |
|---|---|---|---|---|---|
| v1a — baseline | 25/135 | 18.5% (12.9–25.9) | — | — | — |
| v1b — same prompt again | 25/131 | 19.1% (13.3–26.7) | 7 / 8 | −1 | 1.000 |
| **v8** — shipped prompt, CR197 rendering | 14/77 | 18.2% (11.2–28.2) | 7 / 7 | **+0** | **1.000** |
| **v9** — shipped assembly | 9/72 | 12.5% (6.7–22.1) | 4 / 0 | +4 | 0.125 |
| **v9t** — shipped assembly, prose-tolerant read | 16/133 | 12.0% (7.5–18.6) | 12 / 4 | **+8** | **0.077** |

CR197's v8, for comparison: 22 approvals, 16.4%, net 0 (9/9), p=1.0, against a 16.3%
baseline and an 8/8 noise floor.

Two separate answers, and they differ:

1. **The shipped officer PROMPT reproduces the debate.** v8 — the shipped builder, the
   shipped 1800-token budget, the CR197 rendering — lands on 7/7, net 0, p=1.0, at
   18.2% against an 18.5% baseline. That is CR197's result reproduced on the
   production prompt: the same symmetric shape the model's own resampling produces
   (7/8 here, 8/8 in CR197).
2. **The shipped ASSEMBLY does not clear the same bar.** v9t — same officer call, same
   payload, rendered the way `_run_risk_officer` renders it — lands 6.5pp below
   baseline (12.0% vs 18.5%) with a one-directional net of +8, p=0.077. Not
   significant at n=132, and the direct v8-vs-v9t contrast on their 75 shared
   convenes is 9/6, net +3, p=0.61 — so the rendering difference is **not
   established**. But it is no longer the "indistinguishable from sampling noise"
   result CR197 reported, the direction is consistent across all four epochs, and
   12.0% sits on top of CR197's measured **ladder-only floor of 11.8%** — the
   reading worth worrying about is that splitting one coherent menu across three
   single-rung voices delivers about what the bare ladder delivered.

## The blocking finding: production discards ~43% of officer replies

| arm | trailing prose after the JSON | otherwise unparseable | discarded |
|---|---|---|---|
| v8 | 56 / 136 (41.2%) | 2 (1.5%) | **42.6%** |
| v9 | 59 / 136 (43.4%) | 1 (0.7%) | **44.1%** |
| v9t | 0 | 1 (0.7%) | 0.7% |

CR197 measured 2/136 = 1.5% unparseable. The shipped assembly measures **42–44%**.
Every one of those is a convene where `_run_risk_officer` sets
`fallback_reason="the reply could not be parsed"` and renders the ladder alone —
marked in the transcript per CR040, so loud rather than silent, but the user gets the
11.8%-floor experience nearly half the time.

The failure is one specific, reproducible shape, and it was isolated by controlled
probe over the same 24 convenes in the same session:

| officer prompt | unparseable |
|---|---|
| CR197 assembly @1200 | 0/24 |
| CR197 assembly @1800 | 1/24 |
| CR197 assembly @1800 + grounding directive | 0/24 |
| **shipped assembly** | 9/24 |
| **shipped assembly, minus the simulated-portfolio block** | **0/24** |
| shipped assembly, ladder moved after the transcript | 16/24 |
| shipped assembly, recorded wire-id transcript labels | 13/24 |

Neither the token budget, nor the grounding directive, nor the ladder's position, nor
the transcript labels account for it. **The holdings block does.** It is present in
`build_risk_officer_messages` and absent from CR197's slice, and with it in the prompt
the model appends a line — *"Worked example — classroom simulation, not financial
advice."* — after an otherwise complete JSON object.

`extract_json_object` then rejects the reply. Its docstring says it tolerates
"leading/trailing prose", and it does — but only when the text does NOT start with
`{`. A reply that opens with the object and closes with a sentence is passed whole to
`json.loads` and fails as extra data. The JSON contract already says *"No prose
outside it"* and the model ignores it, which is `failure_patterns` P2 exactly: the
instruction is not the control, the parser is.

## What weakens this measurement relative to CR197

- **The corpus has no TARGET.** `build_option_ladder` runs with `target=None` in all
  136 convenes, so no ladder carries a reward:risk column. Production supplies one
  whenever the Execution Desk set a target. The officer is measured with *less*
  evidence than it will have — an understatement.
- **The evidence block is today's rendering, not the epoch's.** The reconstruction is
  byte-exact for 39/39 convenes of the newest epoch and differs for the three older
  ones only where the shared renderer moved on after they were recorded (DEF302,
  DEF292, CR179 Leg 4, CR153-156). Every figure is the run's own; only the wording is
  current. See `ASSEMBLY_DIFF.md`.
- **v8 and v9 are computed over biased subsets** — the ~57% of convenes whose officer
  reply parsed. v9t is the only officer arm at full n (133). v9 (12.5%, n=72) and v9t
  (12.0%, n=133) agree closely, which is the evidence that the discard is roughly
  independent of outcome; that is what makes v9t usable as the design's estimate.
- **n cannot resolve this.** The script's own bound is that a difference under
  ~8–10pp is not resolvable at n≈136. The v9t gap is 6.5pp. A null here bounds the
  effect; it does not prove one.
- The corpus is 13 unique tickers across four prompt epochs — clustered, not
  independent — and the baseline itself moved between CR197's session (16.3%) and
  this one (18.5%).

## Calls saved (from the code, not this run)

The Room's RISK phase goes from three LLM calls to one, and from three serial
round-trips to one: 12 agent calls per convene become 10. The decode budget for the
phase falls from 3200 tokens (800 Aggressive + 1300 Conservative + 1100 Neutral) to
1800. Wall-clock saving was not measured here — this script replays the PM, not a
whole room.

## Recommendation

**Do not enable `ROOM_RISK_OFFICER_ENABLED` on Alpha yet.** Not because the design
failed — the shipped prompt reproduced the debate exactly (net 0, p=1.0) — but
because the assembly around it has one defect that is measured, reproducible, and
cheap to fix, and one open question that is not yet answered.

In order:

1. **Fix the read.** `extract_json_object` must trim text after the object's closing
   brace when the reply starts with `{`, the same way it already trims when the reply
   does not. That is the structural control; a prompt line telling the model not to
   append prose is the one P2 says measures ~30%. Guard it with the shape this run
   found: a complete object followed by a sentence.
2. **Re-measure v9 after the fix.** With the discard at ~1% instead of ~43%, v9 and
   v9t converge and the arm reports the assembly at full n on the production read
   path.
3. **Decide the rendering.** v9t at 12.0% vs a v8 at 18.2% on the same payload is the
   live question this run opened. It is not statistically established (p=0.61 head to
   head), but the point estimate says the CIO does better with the menu whole and
   ahead of the transcript than split across three single-rung voices at the end of
   it. Rendering the full assessment into the Balanced voice — or keeping the three
   display turns while ALSO placing the ladder-with-reasons block where
   `render_risk_assessment` puts it — is a one-arm test, not a redesign.

If the flag is enabled before (1), expect roughly two convenes in five to show three
ladder-only voices carrying the `[AMI …]` mark, at the 11.8% approval floor rather
than the 16–18% the debate produces.
