# CR217 — GLM-5.3-Flash as a candidate Room model, scored head-to-head against ami-llm

**Filed:** 2026-09-01 · **Track:** R · **Status:** in progress

## Why

Saiful: *"we have a new llm we are trying out … test `LibertAIDAI/GLM-5.3-Flash-NVFP4`
… and compare the resuls with the backtesting run we did. did it do better than ami-llm ?"*

The incumbent Room model is `qwen3.8-flash-next` (served as `ami-llm` on the LAN box,
`192.168.20.74:8048`). CR164 Phase B scored the Room on 446 as-of convenes over 18 dates
with that model; CR214 re-scored the same banked runs at the Room's own ~13-week horizon.
Those results are the baseline this CR compares against. **No new ami-llm convenes are
needed or wanted** — the baseline is already banked, and the qwen host is in use by
another lane (Saiful, 2026-09-01: *"do not touch qwen at the moment. it is busy"*).

## What this CR ships

A **registered but inert** GLM provider, plus the run that uses it.

| Change | File |
|---|---|
| `glm_base_url` / `glm_model` / `glm_api_key` / `glm_max_tokens_floor` | `backend/app/core/config.py` |
| Provider registration + `_SINGLE_MODEL_SETTING` entry | `backend/app/services/llm_gateway.py` |
| CR040 feature gate (silent-fallthrough is visible in `/v1/admin`) | `backend/app/api/admin.py` |
| Env forwarding (compose-parity is a build gate) | `docker-compose.yml` |
| Wiring + trap tests | `backend/tests/unit/test_cr217_glm_provider.py` |

**Deliberately absent from `LLMGateway._PREFERENCE`.** Registering a candidate must not
change which model serves live Alpha traffic. GLM is reached only via
`LLM_FORCE_PROVIDER=glm`, the mechanism `_active_provider_name` already documents for
exactly this purpose.

## The two traps, and what makes each structural rather than remembered

**1. The published URL is wrong for our config.** The endpoint is quoted as
`http://100.94.223.38:8008/v1/`. `OpenAICompatibleProvider` appends
`/v1/chat/completions` itself and only strips a trailing slash, so pasting the published
form verbatim yields `/v1/v1/chat/completions` → 404 on every call. In a sweep, a 404 per
call is a DEF059 fail-safe PASS — it reads as *the model declining every trade*, not as a
misconfiguration. `GLM_BASE_URL` must therefore be `http://100.94.223.38:8008`.
Pinned by `test_a_v1_suffixed_base_url_doubles_the_path`, which asserts the joined URL.

**2. A missing `GLM_BASE_URL` scores the incumbent against itself.**
`_active_provider_name` falls through to normal preference when a forced provider is not
registered — deliberately and silently, so a typo'd env var can never 500 a live flow.
For a benchmark that kindness is a trap: `LLM_FORCE_PROVIDER=glm` with no URL runs
**ami-llm**, and the head-to-head then reports a null that is indistinguishable from a
real one. That fallthrough is right for live flows and is *not* being changed. Instead:

> **Every GLM result must be verified against `llm_audit.provider`, which is NOT NULL and
> written per call, before it is believed.** Not against the env var that was set, and not
> against `/v1/llm/status` — against what actually answered.

## Measured before any volume (2026-09-01, from the Mac)

Reachability, all three hops: Mac → 200; melehost host → 200 (0.40s); *inside* the
`ami_api_alpha` container → 200 (0.04s). No API key required.

| | PM-shaped call (3,311 input tokens) |
|---|---|
| GLM-5.3-Flash `:8008` | **12.70s** (284 tok out, 22.4 tok/s) · **23.12s** (333 tok, 14.4 tok/s) |
| qwen3.8 `:8048` (single sample, before the hands-off instruction) | 3.41s (44 tok) · 4.03s (55 tok) |

Both are far inside the 180s `room_agent_timeout_s` guard. Two things to carry forward:

- **GLM emits no `reasoning_content`** — so it needs no Kimi-style `max_tokens` floor, and
  `glm_max_tokens_floor` is 0. Raising one arm's token budget would change what is compared.
- **GLM is ~6× more verbose** on the identical prompt (284–333 vs 44–55 visible tokens).
  Expect a longer wall-clock per convene than the incumbent's, independent of tok/s.

The two models also *disagreed* on that probe — GLM APPROVEd, qwen PASSed, calling the
input "corrupted with identical, repetitive analyst notes." That is a correct read of a
synthetic filler prompt and says nothing about judgement on real data. **It is not
evidence either way** and must not be cited as such.

## Acceptance

1. Backend suite green, including `test_config_compose_parity.py`.
2. `/v1/llm/status` on Alpha reports `glm` registered and, under force, active.
3. A smoke batch produces **parseable, non-fail-safe** Room verdicts, with
   `llm_audit.provider = 'glm'` on 100% of its calls.
4. The full run reuses the **same as-of pairs** as the banked ami-llm baseline, scored by
   the **same scorer** (`backtest_report.py`), so the two are directly comparable.
5. The comparison reports the within-date paired spread at 62d — the pre-registered
   primary horizon — with its date-clustered CI and the matched-random placebo arm, and
   states whether the interval separates the two models. Given ~18 dates, the honest prior
   is that **it will not**; a non-separating result is to be reported as a
   non-measurement, not as "the same."

## Out of scope

Making GLM the live Room model. That is a separate decision needing more than one
backtest, and this CR deliberately leaves `_PREFERENCE` untouched.
