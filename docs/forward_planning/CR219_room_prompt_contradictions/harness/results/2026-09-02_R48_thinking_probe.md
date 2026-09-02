# R48 step 1 — does the serve honour per-request thinking?

**2026-09-02**, LAN-direct against `http://192.168.20.74:8048`, read-only. No
server-side change of any kind was made; none is needed.

## Model identity

Read from `/v1/models`, `root` field — never the `id` alias, which was reused
across the 2026-08-28 swap and now names a different model than it did before:

```json
{"id": "ami-llm", "root": "/models/qwen38-flash-next-nvfp4", "max_model_len": 262144}
{"id": "qwen3.8-flash-next", "root": "/models/qwen38-flash-next-nvfp4", "max_model_len": 262144}
```

Two aliases, one build. Both resolve to `/models/qwen38-flash-next-nvfp4`.

## Answer: yes — `chat_template_kwargs: {"enable_thinking": true}`

Same prompt (`"What is 17*23? Think it through."`), `max_tokens: 200`, five request
shapes. The signal is `usage.completion_tokens_details.reasoning_tokens`.

| Request shape | `prompt_tokens` | `reasoning_tokens` | Verdict |
|---|---|---|---|
| baseline, no kwargs | 25 | **0** | thinking OFF — confirms the 2026-08-31 probe |
| `chat_template_kwargs: {"enable_thinking": true}` | **65** | **44** (78 on a second draw) | **works** |
| top-level `enable_thinking: true` | 25 | 0 | ignored |
| `chat_template_kwargs: {"thinking": true}` | 25 | 0 | ignored |
| `reasoning_effort: "high"` | — | — | HTTP 400 |

Raw 400 body, verbatim:

```json
{"error": {"message": "Unexpected reasoning effort high. Supported types are xhigh (default), medium, and low.", "type": "BadRequestError", "param": null, "code": 400}}
```

So `reasoning_effort` **is** a supported parameter on this build, with values
`xhigh` (default), `medium`, `low`. Both `low` and `xhigh` were exercised
alongside `enable_thinking` and both returned non-zero `reasoning_tokens`
(109 and 75 respectively).

## Three things this changes for the A/B

1. **No server-side config change is required**, so R48 step 2 (stop and ask
   Saiful) does not apply. The flag is per-request.
2. **The prompt grows.** `prompt_tokens` went 25 → 65 with thinking on: the chat
   template renders a thinking prefix. Small in absolute terms, but it means the
   two arms are not sending byte-identical prompts, and that belongs in the
   write-up rather than being discovered later.
3. **Thinking spends from the same `max_tokens` as the answer.** This build
   inlines the reasoning into `content` and emits no separate `reasoning_content`
   field, so a PM turn run at today's `max_tokens_for(PORTFOLIO_MANAGER)` budget —
   tuned with thinking OFF — can truncate mid-JSON on the thinking-on arm and
   score as a parse failure. That would fabricate a losing arm. **Re-derive the PM
   decode budget before running R48 step 3**, and check
   `scores.run.turns_truncated_at_budget` in every arm's `run.json`.

`run_convene.py --thinking` is the arm switch; `run.json` records
`reasoning_tokens_total`, so an arm claiming thinking-on can be verified rather
than believed.

## Not done here

Step 3 — the PM-only thinking A/B — is **held for Saiful's go**, as is R47's
k=20 flip measurement. This note is step 1 only.
