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

### Correction: GLM **is** a reasoning model, and the first read of this was wrong

The bullet above ("emits no `reasoning_content`") was measured on the wrong field. GLM
returns its chain-of-thought in a field named **`reasoning`**, not `reasoning_content`,
so a probe that checks only the latter sees an empty turn and concludes there is no
thinking to budget for. Re-measured against the Room's *real* per-agent caps:

| call | cap | finish_reason | tokens spent | visible chars |
|---|---|---|---|---|
| Fundamentals analyst | 800 | **`length`** | 800 | **0** |
| Bull researcher | 1600 | `stop` | 723 | 782 |
| Portfolio manager | 900 | `stop` | 778 | 290 |

`_AGENT_MAX_TOKENS` gives all four analysts **800**, which sits below GLM's thinking
preamble outright — so **every analyst turn would have come back empty**. In a backtest an
empty turn becomes a DEF059 fail-safe PASS, which reads as *the model declining to trade*
rather than as a decode-budget defect. That is the single most misleading way this
comparison could have failed, and it would have produced a confident, wrong "GLM is far
more conservative than ami-llm."

This is CR130 (Kimi) and CR211 (the post-swap vLLM model) for the third time, so the fix
is theirs: a per-provider floor. Set to **12000** (Saiful). The 2,985 reasoning chars first
observed are a *lower bound* — that turn was cut off mid-thought, so it says only that GLM
wanted at least that much, never how much. Verified at 12000: three analyst turns, all
`finish_reason='stop'` at 1,366–1,454 tokens with full ~800-char answers. A ceiling, not a
target. The real backstop is `room_agent_timeout_s` (180s), not this number.

## Throughput — measured, and it is the binding constraint

Once the decode floor is right, GLM generates ~1,400 tokens per analyst turn instead of
~300, and the cost profile changes completely:

| concurrency | aggregate | mean per-request | worst per-request |
|---|---|---|---|
| 1 | 25.9 tok/s | 44.3s | 44.3s |
| 4 | 30.9 tok/s (1.19×) | 91.6s | 155.1s |
| 8 | 38.6 tok/s (1.49×) | 146.2s | **250.7s** |

**A single request nearly saturates the box.** Eight-way concurrency buys 1.5× throughput
while making each call 3.3× slower — and the worst call at 8-way (250.7s) **exceeds the
Room's 180s agent guard**, which would manufacture DEF059 fail-safe PASSes. Parallelism is
therefore not available here: it would corrupt the measurement in exactly the direction
that makes a model look falsely conservative.

At concurrency 1 a 12-agent convene costs roughly **9–11 minutes** against the incumbent's
measured 204s (`r70-outcome-2`) and 286s (`r74c`, current model) — i.e. **~3× slower**.
A full 450-pair replay is ~75–80 hours.

## Scope decision (Saiful, 2026-09-01)

Given that, and given the baseline's own 62d spread is +5.09% with a CI of −1.41…+12.88
over 18 dates — so a GLM arm carries a similar ±7pt band and the *difference* of the two
spans roughly ±20pt, which no realistic model gap reaches — the outcome-edge comparison is
**structurally unable to separate the two models at this sample size**, at any runtime.

Scope is therefore **mechanics + decision-diff first**: 54 pairs (3 per date × 18 dates,
seed 217, `pairs_cr217_glm_smoke.jsonl`), ~8h. It answers what is answerable:

- valid/parseable verdict rate vs DEF059 fail-safes,
- GLM's APPROVE rate against the baseline's 9.0% (7.4% on this subset) on **identical pairs**,
- decision agreement, disagreement direction, and per-convene wall clock,
- safety-floor compliance.

It makes **no outcome-edge claim**. Baseline stays the banked `r70-outcome-2` (no new qwen
load — Saiful, 2026-09-01: *"do not touch qwen at the moment. it is busy"*), with the
caveat below stated in every write-up.

## Caveat that must survive into any conclusion

`r70-outcome-2` ran **2026-08-20/21**, before CR211 swapped the on-prem serve on
**2026-08-28**. Its "ami-llm" is the *old, non-reasoning* model, not the
`qwen3.8-flash-next` in production today — and CLAUDE.md is explicit that the `ami-llm`
alias was reused across that swap, so the name does not disambiguate them. **A GLM-vs-baseline
result answers "better than the model we ran in August", not "better than what we run
today."** A true three-way needs a fresh qwen3.8 arm on the same pairs, which is blocked on
the qwen host being free and is not started without an explicit go.


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
