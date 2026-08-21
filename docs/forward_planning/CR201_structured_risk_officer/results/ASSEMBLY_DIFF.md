# CR201 step 2 — what changed between the CR197 measurement and the shipped assembly

CR197 measured arm v8 against a Risk Officer prompt that `pm_debate_ablation.py`
assembled itself, by slicing the recorded Chief Investment Officer prompt. CR201
then shipped `room_prompts.build_risk_officer_messages` + `room_runner._run_risk_officer`.
This is the difference between the two, element by element, established by reading
both builders and by assembling a prompt from each over the same 136 convenes.

| element | CR197 script (`risk_officer_prompt`) | SHIPPED (`build_risk_officer_messages` + `_run_risk_officer`) |
|---|---|---|
| grounding directive (CR056) | absent — the slice starts below it | **present**, prepended by `LLMGateway.stream_chat` on every call |
| persona | `RISK_OFFICER_PERSONA` | same |
| convene header | `─── CONVENE THE ROOM — **VERDICT** PHASE ───` (the CIO's, sliced) | `─── CONVENE THE ROOM — **RISK** PHASE ───` |
| ticker line | present (sliced) | present |
| fact sheet | the CIO's, sliced verbatim | `_format_profile(profile, RISK_OFFICER)` — same lane (`_ALL_DOMAINS`), so the same bytes |
| **simulated-portfolio block (CR055)** | **absent** — it sits in `base`, above the slice | **present**, inside the convene block |
| mandate snapshot / drawdown line | the CIO's, sliced | regenerated; the CIO passes `agent_size_pct=None` too, so the same line |
| live risk state, sector allocation | the CIO's, sliced | regenerated from the same inputs |
| **option ladder position** | **after** the transcript, immediately before the JSON contract | **before** the transcript (deliberate — see the call site comment) |
| ladder reward:risk column | absent (no target in the corpus) | present in production whenever the Execution Desk set a target |
| transcript | the CIO's stripped transcript, wire-id labels | `_format_transcript(run.transcript)` — display-name labels, same turns |
| JSON contract | `build_risk_officer_instruction(rows)` | same |
| user message | `Assess risk on {ticker}.` | same |
| **decode budget** | **1200** (hardcoded) | **1800** — `_AGENT_MAX_TOKENS[RISK_OFFICER]`, derived by CR179's method FROM the censored 1200 |
| what reaches the CIO | ONE `render_risk_assessment` block, injected ahead of the transcript | THREE turns from `render_officer_turns`, appended to the transcript under the three risk `AgentId`s |
| mandate/compliance overlay | absent | absent (deliberate — the officer sizes options, it does not screen instruments) |
| safety floor | absent | absent (deliberate — `enforce_safety_floor` stays on the CIO, DEF059) |

## What the re-run reconstructs, and what it cannot

The arm calls the shipped builder. Its structured inputs are read back off each
recorded prompt: `risk_score`, `max_drawdown_pct`, `locale`, `long_only`, the
reference triple (size/entry/stop), drawdown consumed, open risk, the over-trading
counts, and the holdings block. Two inputs are transplanted verbatim rather than
rebuilt, because no structured source for them survives in the corpus: the **fact
sheet** (`_format_profile` is lossy and the `profile` dict is not stored) and the
**holdings block**.

Fidelity check, run for all 136 convenes before any network call: the regenerated
mandate + live-risk + sector region is compared byte-for-byte against the same
region as recorded.

| epoch | convenes | byte-exact |
|---|---|---|
| 2026-08-07 | 18 | 0 |
| 2026-08-13 | 40 | 0 |
| 2026-08-14 | 39 | 0 |
| 2026-08-14b | 39 | **39** |

The newest epoch reproduces exactly, which is what establishes the reconstruction is
input-faithful. The three older epochs differ only where the shared renderer moved on
*after* they were recorded — DEF302's stop-distance clause, DEF292's one-decimal
share-of-cap, CR179 Leg 4's headroom clause, and the CR153-156 live-risk block. Every
figure is identical; only the wording around it is today's. That is the correct
direction for this measurement: the officer's half is production's rendering of the
run's own numbers, while the CIO's half is held fixed at what was recorded.

**One production input genuinely cannot be reconstructed: the Execution Desk's
TARGET.** It appears nowhere in the recorded prompt, so `build_option_ladder` runs
with `target=None` and the ladder carries no reward:risk column in any of the 136
convenes. Production supplies one whenever the desk set a target. The arm therefore
measures the officer with *less* evidence than it will have in production — an
understatement, not an overstatement, and the same one CR197 recorded for v6/v7.
