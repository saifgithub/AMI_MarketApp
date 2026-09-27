# 16 — Fully-translated PM prompt, 5x vote test: English-revert is worse than the append-instruction approach

**Status: run complete. This is the more important of the two language
mechanisms tested (docs 14/15 tested "English prompt + reply-in-X
instruction"; this tests "the entire prompt itself in Malay/Arabic") — and
the result is the opposite of what doc 14/15 might have predicted.**

## Why this test, and what it actually checks

Saiful's original framing question (2026-09-26): "Do we send in English and
tell the LLM to reply in Arabic? Or do we need to have the prompts already
in Malay or Arabic?" Docs 14/15 answered the first half. This doc answers
the second half — and does it on the `portfolio_manager` stage
specifically (Saiful: "test it for the voting"), the PM's 5x
self-consistency sample vote that decides the Room's final APPROVE/PASS
action, the single most consequential stage in the whole pipeline.

## Method

1. Pulled JPM's real captured `portfolio_manager` `system_prompt` (37,432
   chars — fact sheet, mandate, full upstream 11-agent transcript, and the
   JSON output-format spec) via `room_llm_audit_trace.py`, from doc 13's
   original English 9-ticker DeepInfra batch (verified identical across all
   5 of that convene's own PM self-consistency samples via checksum before
   using it).
2. Had `ami-llm` (vLLM) itself translate the WHOLE prompt into Malay, then
   separately into Modern Standard Arabic — a one-shot, whole-document
   translation instruction (not the doc 14/15 append-only approach), saved
   as [`out/16b_jpm_pm_prompt_malay_translated.txt`](out/16b_jpm_pm_prompt_malay_translated.txt) /
   [`out/16c_jpm_pm_prompt_arabic_translated.txt`](out/16c_jpm_pm_prompt_arabic_translated.txt).
   Verified both translations were complete, not truncated (checked
   `completion_tokens` against the `max_tokens` ceiling, and confirmed both
   files end on a genuine closing sentence, not a cutoff).
3. Ran `room_agent_replay.py` 5x per combo (vLLM × Malay, DeepInfra ×
   Malay, vLLM × Arabic, DeepInfra × Arabic — English is the untranslated
   original, doc 13's own 5x English draws already exist) directly against
   each translated prompt.
4. **Fixed a real tool bug found live**: `portfolio_manager` answers in
   JSON (`{"action": "APPROVE", ...}`), not the `Side:`/`[STANCE: ...]` tag
   shape every other agent uses — the existing extraction silently returned
   `None` on the very first smoke-test draw despite a perfectly valid
   APPROVE verdict in the raw text. Added `--extract-json-key action` to
   `room_agent_replay.py` (parses the first balanced `{...}` span, since a
   "Worked example — classroom simulation" disclaimer sometimes trails the
   JSON block) — committed before running the real test.

## Result: the vote itself is unanimous everywhere it completes — but the LANGUAGE frequently reverts to English

| Combo | Actions (5 draws) | Native-language draws | English-revert rate |
|---|---|---|---|
| vLLM + Malay | APPROVE ×5 | 3/5 | **2/5 (40%)** |
| DeepInfra + Malay | APPROVE ×5 | 4/5 | **1/5 (20%)** |
| vLLM + Arabic | APPROVE ×3, extraction-failed ×2 | 0/5 | **5/5 (100%)** |
| DeepInfra + Arabic | APPROVE ×5 | 1/5 | **4/5 (80%)** |

**The vote decision itself never wavered** — every draw that returned a
parseable action said APPROVE, matching JPM's original English baseline
(doc 13: APPROVE 5/5). Sizing varied narrowly (1.5%–3.0%, consistent with
doc 13's own English-mode variance), so the underlying financial reasoning
held up regardless of which language it was expressed in.

**But the LANGUAGE the model actually answers in is highly unreliable, even
when the entire prompt — fact sheet, format spec, and instructions — is
translated.** This is the opposite of what doc 14/15's "just append one
instruction sentence" test might predict: those tests (single-agent replay
and full-Room, respectively) found the append-only approach fluent in 9/9
and ~18/20 draws. Here, with the WHOLE prompt translated — arguably a
*stronger* signal to answer in the target language — the revert rate is
dramatically worse, especially for **vLLM + Arabic, which reverted to
English on every single draw (5/5)**.

Sample of an English-revert draw (vLLM, Arabic-translated prompt, draw 2):
> Approve a partial entry at 2.0% of the portfolio, reducing from the
> Execution Desk's 3.0% to balance the strong fundamental case against the
> unresolved technical setup and imminent earnings...

— entirely in English, despite every word of the 34,330-char system prompt
that produced it being in Arabic.

## A second, separate defect found: 2 draws truncated mid-JSON

vLLM/Arabic draws 1 and 3 returned `extracted=None` — not a tool bug this
time (verified: the JSON is genuinely incomplete, 1 open brace / 0 close
braces, cut off mid-narration-string). `room_agent_replay.py`'s
`_call_vllm` uses `max_tokens=2000` by default; these two draws' raw output
length (1339, 1591 chars) was not obviously longer than the other three
successful draws (1411-1658 chars) in the same batch, so length alone does
not explain why these two specifically truncated — **this is an
unexplained anomaly, not a confirmed "non-English runs longer" effect**,
and is flagged as open rather than rationalized.

## What this doesn't answer yet

- **Why does Arabic fail so much worse than Malay, and why does vLLM fail
  worse than DeepInfra on Arabic specifically (100% vs. 80%)?** Not traced
  — could be tokenizer efficiency (Arabic's script may consume more tokens
  per unit of meaning, making the model "run out of room" toward a
  target-language answer and default to a more token-efficient English
  fallback), training-data skew (both base models are far more exposed to
  English/Chinese than Arabic), or something else. Not established here.
- **Only ONE ticker (JPM) and one agent role (`portfolio_manager`) tested.**
  JPM was chosen because it's stable in English (doc 13: unanimous APPROVE
  5/5) — deliberately controlling for the ticker-level instability doc 13
  found elsewhere, so language effects wouldn't be confounded with
  ticker-level noise. Whether this same revert pattern holds on an
  unstable ticker, or on other agent roles, is untested.
- **The 2 vLLM/Arabic truncations are unexplained**, not confirmed as a
  language effect — could be pure sampling variance unrelated to language
  at all.
- **No native speaker review of the Malay/Arabic content that DID come
  through correctly.** Same standing caveat as docs 14/15.
- **Cost**: DeepInfra's two runs here (Malay 5x + Arabic 5x) totaled
  measured ~$0.00539 + ~$0.00623 = ~$0.0116 from `room_agent_replay.py`'s
  own real-usage cost logging (not dashboard-verified against a before/after
  pull this time, since these were small single-agent replay calls, not
  full Room convenes).

## Read

This is the most consequential finding in the CR240 language-support
investigation so far: **translating the entire prompt into the target
language does NOT reliably keep the model answering in that language — if
anything, this small sample suggests it may perform WORSE than simply
appending a one-line instruction to an English prompt** (docs 14/15's
approach). Any real AR/MS localization effort should not assume "translate
the prompts" is sufficient on its own; the actual mechanism that keeps a
model in-language under an otherwise-fully-translated prompt needs its own
investigation (system-level language pinning? a stronger, repeated
instruction? a different base model with stronger non-English retention?)
before this becomes a production plan.
