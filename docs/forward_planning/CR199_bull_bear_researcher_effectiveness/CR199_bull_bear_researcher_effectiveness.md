# CR199 — Are the Bull and Bear Researchers effective? Do they impact the trade decision?

**Asked:** 2026-08-20, by Saiful — *"evaluate the impact of the bull and bear agent. Are they
really effective? Do they impact the trade decision?"*

This is CR197's question moved one phase upstream. CR197 answered it for the three Risk
Debators; the same machinery, extended, answers it here — with one difference that matters:
the Debators speak at positions 9–11 of 12 and only the Portfolio Manager reads them, while
the Researchers speak at 5–6 and **six** downstream voices read them. A finding of "no
effect" is much harder to earn up here, and a finding of "effect" is much more likely.

---

## Why it needed measuring rather than reasoning about

Three prior measurements all stop short of the causal question:

- **CR143 M5** scores cosine similarity between the PM's `verdict.reason` and each turn.
  That is textual echo. It cannot distinguish "the PM was persuaded by the Bear" from "the
  PM and the Bear both read the same Fundamentals Analyst".
- **CR035** ran ablations, but of the analyst-consensus *input*, never of a *stage*.
- **CR197** built the first stage-ablation harness and left the Researchers untouched.

And the structural read says the Researchers have exactly one channel, the same one CR197
found for the Debators:

| Channel | Status for Bull/Bear |
|---|---|
| Stance / conviction / headline | Parsed into `AgentMessage`, rendered for the UI — but `parse_stance_envelope` strips it **before** the transcript commit, so no downstream agent ever sees it |
| A position size | The prompt tells them **not** to give one ("Sizing is the Trader's proposal…") — and `_SIZE_DECLARING_AGENTS` is the three Debators only, so there is no SIZE field to parse either |
| Any structured field | None. Nothing in `app/` reads `BULL_RESEARCHER` / `BEAR_RESEARCHER` outside the phase list, the templates and the 1-on-1 overlay |
| **Prose in the transcript** | **The only channel.** `_format_transcript` renders `[agent_id] content` into every later agent's prompt |

So the whole question reduces to: *does that prose change what the readers write and what
the Portfolio Manager decides?*

---

## Scope

**A. Deterministic corpus read** (`backend/scripts/researcher_signal_report.py`, no LLM) over
the 136 committed convenes in `CR143_agent_prompt_audit/corpus/`, each agent joined to its own
verbatim recorded prompt. Four channels:

1. stance / conviction entropy + mutual information with the decision;
2. **minted numbers** — quantities cited that are absent from the agent's own prompt (the
   prompt carries the fact sheet *and* the four analyst turns, so "not in the transcript" is
   not the same as "new");
3. **provenance** — of the numbers each downstream reader cites, how many appear in a
   researcher turn and **nowhere else in that reader's own prompt**;
4. attribution and engagement — who names whom.

**B. The causal test** (`backend/scripts/researcher_ablation.py`, live vLLM). A four-arm
two-stage cascade per convene, 7 calls each:

| arm | RM prompt | PM prompt |
|---|---|---|
| A1 control | verbatim | verbatim, RM turn := A1's RM output |
| A2 noise | verbatim, resampled | verbatim, RM turn := A2's RM output |
| B ablated | Bull+Bear removed | Bull+Bear removed, RM turn := B's RM output |
| C direct | (reuses A1) | Bull+Bear removed, RM turn := A1's RM output |

A2 is the point of the design: sampling is server-side and unknown, so the rate at which this
model disagrees with **itself** on a byte-identical prompt is measured, not assumed. B only
means something above that floor. C decomposes the result — it holds the synthesis fixed and
removes the researchers from the PM's window alone, separating the direct channel from the
mediated one.

Decision rule fixed in advance, as CR197's was: exact McNemar plus Wilson intervals, causality
claimed only at p<0.05 **and** ≥5pp over the noise floor. At n≈136 effects below ~8–10pp are
not resolvable, stated up front rather than discovered afterwards.

Fidelity rules inherited from `pm_debate_ablation.py`: `VLLMProvider` used directly (the
gateway would double the CR056 grounding directive and could fall back to Anthropic
mid-measurement), no temperature/top_p (production sends none), `max_tokens` pinned per agent
(RM 1600, PM 1700), a replayed RM turn substituted as prose with its envelope stripped exactly
as production strips it, and actions parsed from the reply rather than the safety-floor-vetoed
`verdict`. Every prompt surgery is verified three ways before any call is made:
**136/136 convenes survive**.

**Declared limitation.** The Trader and the three Risk Debators keep their *recorded* turns in
the PM's window in every arm. They wrote those turns after reading the researchers, so the
ablation cannot remove what they already absorbed. The measured effect is a **lower bound** on
deleting the phase outright.

---

## What this CR does NOT do

No prompt is changed and no phase is cut on the strength of this. CR197's recommendation
pattern applies: measure first, and let Saiful decide the structural question against a
measured effect rather than an assumed one.

---

## Outputs

- `RESEARCHER_SIGNAL.md` — the deterministic read (A).
- `ABLATION.md` — the causal test (B).
- `REPORT.md` — the answer to the question as asked.
- `ablation/researcher_ablation_calls.jsonl` — every live call, resumable.
