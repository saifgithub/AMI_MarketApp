# R48 — PM-only thinking A/B, and the budget that cannot be set

**2026-09-03**, LAN-direct against `http://192.168.20.74:8048`. **No server-side change of
any kind, and no production config touched** — thinking is a per-request flag and the
B-arm budget is a per-request `max_tokens` override inside the harness client. Ran on
Saiful's explicit go. Step 1 (does the serve honour per-request thinking) was answered
2026-09-02: [`2026-09-02_R48_thinking_probe.md`](2026-09-02_R48_thinking_probe.md).

**Model identity**, from `/v1/models` `root`: `/models/qwen38-flash-next-nvfp4`.

---

## Headline

**No default change is recommended, and this lane ships none.**

On CAT, thinking-on and thinking-off return the **identical verdict** — 10/10 PASS both
arms. Thinking bought one real improvement, a **drop in draw parse loss from 14% to 2%**,
and it cost **5.4× the wall-clock** (380 s vs 70 s per 5-draw vote) and **5.7× the output
tokens**. The same defect is fixable for free by the R43 route.

**And the A/B could not be run on two of the three profiles at all.** On MSFT the PM with
thinking on does not stop: 2 of 3 probe draws burned an **8,000-token ceiling entirely on
reasoning and emitted zero characters of answer**. That is not a budget I can set a number
for — it is a runaway, and it is the more important finding of the two.

## Step 1 recap — the flag works, per-request

`chat_template_kwargs: {"enable_thinking": true}`; `reasoning_effort` accepted at
`xhigh` (default) / `medium` / `low`. This build **inlines** thinking into `content` and
emits no `reasoning_content`, so thinking spends from the same `max_tokens` as the answer.
R48 step 2 (stop and ask Saiful for a server change) therefore does not apply.

## The budget re-derivation, done first, from measurement

WP07 R48 step 3 requires the PM decode budget be re-derived before the arm runs, because
`max_tokens_for(PORTFOLIO_MANAGER)` was tuned with thinking OFF and a truncating B arm
would fabricate a losing result. Arithmetic, with every input measured rather than assumed:

| Input | Value | Where it came from |
|---|---|---|
| PM production `max_tokens` | **1700** | `room_prompts.py::_AGENT_MAX_TOKENS[PORTFOLIO_MANAGER]` (DEF236 raised it from 900; DEF289 re-measured) |
| PM answer tokens, thinking OFF | median **419**, p90 **581**, max **1700** | R47's 300 draws (CAT/MSFT/XOM), this repo |
| PM ceiling hits, thinking OFF | **2 / 100** on MSFT at 1700 | R47 |
| PM **reasoning** tokens on the real prompt, CAT | **674 / 816 / 806** | measured here, `pm_thinking_budget_probe.py`, ceiling 8000 |
| PM **reasoning** tokens on the real prompt, MSFT | **5040**, then **8000+**, **8000+** | same probe — see the runaway below |

**The probe's own numbers do not transfer.** The 2026-09-02 probe measured 44–109
reasoning tokens on a 25-token toy prompt. On the real 8,075-token PM prompt the same flag
spends **674–816** — 8× more. Extrapolating from the toy probe would have set a budget
that truncated every draw. This is why the re-derivation was run against the shipped
prompt, not inferred.

**B-arm budget = 1700 + 1500 = 3200.**

- 1700 — the production answer budget, kept whole so the answer half of the arm is
  unchanged from A.
- 1500 — the thinking allowance: CAT's observed maximum (816) × ~1.8. The multiplier is
  CR179's censored-observation factor (1.5) rounded up, because three samples is a thin
  basis for a maximum.

That budget held: **1 truncation in 50 B-arm draws** (2%), against 0 in arm A. The arm is
not a fabricated loss.

**It holds for CAT only, and that is the finding.** No budget makes MSFT safe — see below.

## Arms

Both arms replay the **same fixed CAT transcript** (`results/CAT_long/run.json`), PM stage
only, k=10 full production-mirroring votes each (5 draws, production parser, production
vote). The thinking flag and the `max_tokens` override are the only differences. Strictly
sequential.

| | **Arm A — thinking OFF** | **Arm B — thinking ON** |
|---|---|---|
| Request | today's serve default | `chat_template_kwargs {"enable_thinking": true}`, default effort (`xhigh`) |
| `max_tokens` | 1700 (production) | 3200 (derived above) |
| **Verdict outcomes (10 votes)** | **PASS ×10** | **PASS ×10** |
| **Flip rate** | **0.0%** | **0.0%** |
| Distinct outcomes | 1 | 1 |
| Draws requested | 50 | 50 |
| Draws parsed | 43 | **49** |
| **Draw parse loss** | **14.0%** | **2.0%** |
| **Draws truncated** | **0** | **1** |
| Draws errored | 0 | 0 |
| Draw actions | 42 PASS / 1 APPROVE | **49 PASS / 0 APPROVE** |
| **reasoning_tokens, total** | **0** | **62,679** |
| reasoning_tokens per vote (mean) | 0 | **6,267.9** |
| Output tokens per vote (mean) | 1,330.9 | **7,586.3** |
| **Wall clock per vote (mean)** | **70.4 s** | **379.9 s** |
| Wall clock, arm total | 703.9 s | 3,799.2 s |

`reasoning_tokens` is recorded on **every** draw in both arms, so "arm B really had
thinking on" is checked (62,679 vs 0), not believed.

## Reading it

**Verdict quality: no measurable difference.** Both arms return PASS on all 10 votes with
the same size (none — PASS carries no size). On this profile thinking changed *nothing*
about the decision. That is a null result, and it is reported as one.

**Parse loss: a real improvement, 14% → 2%.** Arm B also produced **zero** dissenting
draws (49/49 PASS) where arm A had one APPROVE. The plausible reading is that a PM which
reasons before answering is likelier to emit the JSON envelope it was asked for and
likelier to land on the same answer — but with k=10 per arm, 12 points of parse-loss
difference is suggestive, not established, and the same CAT transcript gave **1%** loss in
R47's k=20 run an hour earlier against **14%** in arm A here. **The parse-loss rate is
itself unstable run to run**, which is a caveat on the whole comparison and an
independent finding worth its own line in R43's DEF.

**Cost: 5.4× wall clock, 5.7× output tokens.** A 5-draw PM vote goes from 70 s to 380 s.
Production's PM budget (`vllm_request_timeout_s` 360 s, `config.py:127`; the DEF390
orchestration budget at `:139`) is *below* arm B's mean per-vote time, and those draws run
concurrently in production rather than sequentially as here — but the per-draw time is what
the timeout sees, and arm B's slowest draws sit where the timeout is. Turning this on by
default is not a prompt change; it is a latency-budget change.

### The MSFT runaway — why this A/B is one profile, not three

The budget probe ran 3 draws on each of two profiles at a deliberately generous 8,000-token
ceiling. CAT behaved. MSFT did not:

| Profile | draw | finish | reasoning tokens | answer chars | elapsed |
|---|---|---|---|---|---|
| CAT | 1 | stop | 674 | 829 | 44.2 s |
| CAT | 2 | stop | 816 | 731 | 45.1 s |
| CAT | 3 | stop | 806 | 1007 | 45.2 s |
| MSFT | 1 | **length** | **8000** | **0** | 322.0 s |
| MSFT | 2 | stop | 5040 | 1271 | 228.7 s |
| MSFT | 3 | **length** | **8000** | **0** | 334.5 s |

**Two of three MSFT draws consumed the entire ceiling on reasoning and produced no answer
at all.** Not a clipped JSON envelope — *zero characters*. The third finished only after
5,040 reasoning tokens and 229 s.

MSFT is the profile R47 showed to be genuinely contested (81 APPROVE / 14 PASS at the draw
level). The pattern is consistent with the PM failing to converge on exactly the names where
the evidence is balanced — the cases where a verdict matters most. **There is no
`max_tokens` that fixes this**: raising the ceiling buys more reasoning, not an answer, and
every un-answered draw is a lost vote of the kind R47 showed flips verdicts.

Because of this, the A/B was **not** run on MSFT or XOM. Running it would have produced a
B arm full of empty draws and an apparent "thinking is terrible" result that is really a
statement about the ceiling. Reporting one honest profile beats three dishonest ones.

## Conclusion

1. **Ship no default change.** WP07 step 4 says a default change requires a measured win.
   There is no verdict-quality win on CAT (identical outcomes) and no A/B at all on the
   other two profiles. **`enable_thinking` stays off in production.**
2. **The one benefit thinking bought is available for free.** Parse loss 14% → 2% is worth
   having, but R43's fix — CR210's `pm_verdict_schema()` grammar
   (`room_json_constraints_enabled`, currently OFF) or the `raw_decode` fallback in
   `extract_json_object` — targets the same defect at zero latency cost, instead of paying
   5.4× decode time for a partial mitigation.
3. **The runaway is a finding in its own right and should not be lost with this note.** If
   thinking is ever revisited on this model, the blocker is not the budget — it is that the
   PM does not reliably terminate on contested names. Any future attempt needs a
   convergence guard, not a bigger ceiling.
4. **`reasoning_effort` is untested here.** The probe showed `medium` and `low` are
   accepted. Whether `low` gets the parse-loss benefit without the runaway is an open
   question this note does not answer — it would be the sensible next experiment if the
   question is reopened.

## Caveats

- **One profile, one mandate, k=10 per arm.** CAT × `long` only. Ten votes per arm cannot
  resolve a small difference in verdict outcome; it can only say the arms did not diverge
  on a name where neither arm was in doubt.
- **The arms are not byte-identical prompts.** Thinking-on renders a thinking prefix in the
  chat template (probe: prompt_tokens 25 → 65 on a toy prompt). Small, but the arms differ
  by more than a sampler flag.
- **Not decision quality.** Identical verdicts here do not mean the verdict was right.
- **Parse-loss instability.** Arm A's 14% vs R47's 1% on the *same* transcript ~1 h apart
  means the parse-loss estimate carries run-to-run variance the A/B cannot separate from
  the thinking effect. The 14%→2% delta should be treated as directional.
- **Latency measured sequentially.** Production issues the 5 draws concurrently; the
  per-vote wall clock here is a sum, not a production latency. The **per-draw** times
  (arm B: 45–335 s observed) are the production-relevant figure and they are what
  interacts with `vllm_request_timeout_s`.
- **One serve, one model build.** Not transferable to another model (CR217's business).

## Artifacts

| File | What |
|---|---|
| `2026-09-03_R48_CAT_A_nothinking.json` | Arm A — 10 votes × 5 draws, thinking off, 1700 budget |
| `2026-09-03_R48_CAT_B_thinking.json` | Arm B — 10 votes × 5 draws, thinking on, 3200 budget |
| `2026-09-03_R48_budget_probe.json` | The six budget-probe draws above (CAT ×3, MSFT ×3, ceiling 8000) |
| `../pm_thinking_budget_probe.py` | The probe script, so the derivation can be rerun |
| `2026-09-02_R48_thinking_probe.md` | Step 1 — that per-request thinking works at all |

Every unparsed draw keeps its raw `answer` text in the arm JSONs, so the parse-loss claims
can be checked rather than taken on faith.
