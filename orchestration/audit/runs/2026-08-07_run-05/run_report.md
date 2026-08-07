# Run report — 2026-08-07_run-05

Item: CR141, round 1 (second independent auditor pass — the first, `AT:U66`,
already committed `VERDICT: COMPLETE (round 1)` as `2f01d444` before this
session read the lane). SHA: `afa3ed1e`. Verdict unchanged: **COMPLETE
(round 1)**, zero BLOCKER, zero MAJOR, 1 MINOR (non-gating, same finding
both passes independently reached). Findings appended as an addendum to
`orchestration/audit/cr/CR141.auditor.md` rather than duplicate-committing a
second verdict — same handling CR132's second pass used this session.

## Context — housekeeping gap on the first pass

`2f01d444` committed `CR141.auditor.md` alone: no run report, no
audit-trail row. Same "Done (per item)" gap CR124-round-2 and DEF225 hit
earlier today (see those rows in `audit-trail.md`). Not re-litigating the
verdict — independently reached the same conclusion before reading it —
this report + the trail row below close that housekeeping gap and record
the additional evidence gathered.

## Setup

```text
cd "/Volumes/Extreme Pro/AMI_MarketApp"
git worktree add .claude/worktrees/audit-CR141 afa3ed1e
cd .claude/worktrees/audit-CR141/backend
```

## Regression suite (independent, scratch worktree, absolute interpreter)

```text
"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest tests/unit/ -q
2574 passed, 13 warnings in 307.56s (0:05:07)
```

Exact match to both the architect's submission and the prior auditor pass.
Targeted: `test_cr141_provider_policy.py test_cr141_provider_registration.py
test_cr141_usage_capture.py test_config_compose_parity.py` → `38 passed in
1.59s`. `alembic heads` → `2a08e21c0dac (head)`, single head.

## Acceptance 4 (dormancy) — construction-proof across 64 provider worlds

Standalone script (not derived from the architect's test file), run inside
the worktree: builds `LLMGateway` across all 2^6 = 64 on/off combinations of
the 6 gateable provider settings (`vllm_base_url`, `anthropic_api_key`,
`kimi_api_key`, `deepseek_api_key`, `dashscope_api_key`,
`google_ai_api_key`), × 4 locales × 3 tiers × {no-args, plan-only,
agent-only} call shapes = 2304 identity assertions
(`gw._pick_provider(...) is gw._providers[gw._active_provider_name()]`).

```text
worlds=64 checks_per_call_shape=768 total_failures=0
ALL DORMANCY CHECKS PASSED
```

Also diffed `afa3ed1e^:backend/app/services/llm_gateway.py` against
`afa3ed1e`: pre-CR141 `_pick_provider` body was exactly
`return self._providers[self._active_provider_name()]` — the post-CR141
fallthrough (when `plan`/`agent_id` are omitted, which is every real call
site) is that same line, byte-identical.

Grepped every real `.stream_chat(` call site across `app/` (10 sites:
`api/llm.py`, `api/brief.py`, `brief_engine.py`×2, `agent_runner.py`×2,
`price_alert_evaluator.py`, `portfolio_finding.py`, `room_runner.py`×3) —
none passes `plan=` or `agent_id=`. (`agent_runner.py:6`'s
`gateway.stream_chat(prompt, history+user_msg, tier, locale)` is a module
docstring example, not executable code — `stream_chat`'s real signature is
keyword-only.)

## Acceptance 2 (NULL not 0) — Anthropic path mutation-proved independently

Architect mutation-proved only the OpenAI-compatible path and reasoned about
Anthropic's. Wrote a throwaway pin
(`tests/unit/test_auditor_mutation_anthropic.py`, not committed — copied in,
run, deleted): green against unmodified `afa3ed1e`. Mutated
`_capture_anthropic_message_start_usage` — `msg_usage.get("cache_read_input_tokens")`
→ `... or 0` (same on `cache_creation_input_tokens`) — mutant killed:
`assert 0 is None` fails as expected on the no-cache-field-at-all case.
Reverted via `git checkout -- app/services/llm_gateway.py`, re-ran targeted
CR141 suite clean (38 passed).

## Wire-format verification — live production probe, not just docs

DEF224 blocks SSH to **melehost**, not the separate GPU host serving vLLM
(192.168.20.74:8000, LAN-reachable directly from the Mac per CLAUDE.md).
Fired a real streaming request:

```text
curl -s -N http://192.168.20.74:8000/v1/chat/completions \
  -d '{"model":"ami-llm","messages":[{"role":"user","content":"Say OK."}],
       "max_tokens":5,"stream":true,"stream_options":{"include_usage":true}}'
```

Real terminal frame:
`{"choices":[],"usage":{"prompt_tokens":15,"total_tokens":17,"completion_tokens":2}}`
— `choices: []` confirmed live (matches the code's assumption). No
`prompt_tokens_details` key at all (absent, not null). Traced why via
WebSearch: vLLM only populates it with `--enable-prompt-tokens-details` at
launch, and a long-standing vLLM V1-engine bug (upstream issues 44961,
16162, 18062) keeps it `null` even then. `_parse_openai_compatible_usage`
degrades correctly — `cache_read_tokens` → `None`, never a guessed 0 — so
CR141's acceptance 2 holds against the real wire. OUT-OF-SCOPE observation
(not a CR141 defect, reported for the architect to mint): `cache_read_tokens`
will be NULL on every vLLM-routed Alpha call today regardless of CR141's
correctness, until/unless the GPU host is relaunched with that flag (and the
upstream bug is confirmed cleared on melehost's vLLM build).

Cross-checked provider docs directly (WebFetch, not summarized-only):
- **DeepSeek** `prompt_cache_hit_tokens` — confirmed against
  `api-docs.deepseek.com`; terminal streaming chunk, empty `choices`.
  CONFIRMED.
- **Anthropic** `message_start`/`message_delta` split — confirmed against
  `platform.claude.com/docs/en/build-with-claude/streaming`'s own SSE
  examples; `message_delta.usage` explicitly documented "cumulative", so the
  code's overwrite-not-accumulate handling is correct. CONFIRMED, with the
  same MINOR the first pass found: 2 of 3 official example payloads omit
  `cache_creation_input_tokens`/`cache_read_input_tokens` from
  `message_start.usage` entirely (only the web-search example carries them
  as explicit `0`) — the docstring's "always reports … never absent" claim
  is not fully backed by Anthropic's own docs, though `.get()` already
  degrades the omitted case to `None` correctly regardless.
- **Gemini** OpenAI-compat endpoint — confirmed (`ai.google.dev/gemini-api/docs/openai`)
  it supports `stream_options.include_usage`; UNVERIFIABLE whether the
  streamed usage carries `prompt_tokens_details.cached_tokens` specifically
  — Google's docs don't specify the shape and no live key exists to probe.

## Migration

`alembic/versions/2a08e21c0dac_cr141_llm_audit_usage_columns.py`: all four
columns `nullable=True`, no `server_default`; `downgrade()` drops all four.
`down_revision = "e4f5a6b70030"` confirmed the sole child (no fork). Read at
source, not relayed.

## Compose parity

`DEEPSEEK_API_KEY` + `DASHSCOPE_API_KEY` newly forwarded in
`docker-compose.yml`; `GOOGLE_AI_API_KEY` was already forwarded pre-CR141.
`deepseek_api_key` correctly dropped from `test_config_compose_parity.py`'s
`_NOT_FORWARDED`. Suite green (part of the 2574).

## Verdict

No new BLOCKER/MAJOR. `CR141.auditor.md`'s `VERDICT: COMPLETE (round 1)`
stands, addendum appended documenting the above.
