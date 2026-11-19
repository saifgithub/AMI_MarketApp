# CR281 — LLM provider allow-list, and model swaps by configuration only

**What:** (1) A new setting `LLM_PROVIDER_ALLOWLIST` (comma-separated gateway slot names). Empty = today's behaviour. When set, the gateway never registers a slot outside the list, whatever keys or URLs are configured. (2) Swapping the model or provider behind any OpenAI-compatible slot takes an env change only: base URL, model, kind, optional API key.

**Why:** Saiful, 2026-11-19: Alpha must use only on-prem models (`ami-llm` primary, Ling on our own host as backup in the `vllm_fallback` slot, the self-hosted `glm` slot). To enforce "no Anthropic / Kimi / Gemini / DeepInfra on Alpha" the operator commented the keys out of the env file. A commented line is not a control: uncommenting it, or copying an older env over, re-enables a vendor and nothing reports it. Saiful: "isn't it better to check if the configuration exists or not than to be commented out!" Second addition (same day): "the code need to be able to handle only configuration change for model swap ... include the use of API key if it was configured, and skip if not configured."

## Slot names (from `LLMGateway.__init__`)

`vllm`, `vllm_fallback`, `glm`, `anthropic`, `kimi`, `deepseek`, `qwen`, `gemini`, plus `mock` (accepted in the list, never blocked, see below). Source of truth: `KNOWN_SLOTS` in `backend/app/core/llm_allowlist.py`.

## Part 1 — the allow-list

1. `backend/app/core/llm_allowlist.py` (new, pure): slot names, `configured_slots`, `blocked_slots`, `slot_allowed`.
2. `Settings.llm_provider_allowlist` (CSV; lower-cased, de-duplicated). An unknown name fails boot (a typo must not silently allow nothing or everything). Empty = unrestricted.
3. Gateway: each slot registers only if configured AND allowed. `mock` keeps its existing semantics: always present in `_providers`, never counted as "real" (`has_real_provider`), neither required nor blocked by the list; the existing rules about the mock never silently serving real users are untouched.
4. Degrade loudly: boot logs ONE `llm_provider_blocked_by_allowlist` event at error level, listing every provider that is configured but not allowed (names only; the test asserts no key or URL value appears). A second error event `llm_allowlist_no_real_provider` fires if the list is set but none of its slots is configured. `GET /v1/llm/status` reports `allowlist` and `configured_but_blocked`.
5. Beta (`beta_boot.py`): `LLM_PROVIDER_ALLOWLIST` must be set and must not name `anthropic`, `kimi` or `gemini` (the existing key refusals stay). `infra/beta.env.example` carries `LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback` as `[REQUIRED]`.
6. `docker-compose.yml` api-alpha forwards `LLM_PROVIDER_ALLOWLIST` (parity test).
7. Postflight: `check_llm_allowlist`, called from the `config` check. When the deployed env file sets the list, `/v1/llm/status` is read and the promotion FAILS if (a) a non-mock provider is registered outside the list, (b) the container reports no `allowlist` (predates CR281), or (c) the container's list differs from the env file's (compose not forwarding). No allow-list in the env file = no request, so Alpha's current output is unchanged.

### Every place a blocked provider was reachable, and how each closes

All paths resolve through `LLMGateway._providers`; a blocked slot is never put there, so:

1. Preference pick (`_active_provider_name`, `_PREFERENCE`): iterates registered providers only.
2. `LLM_FORCE_PROVIDER`: honoured only if registered, so forcing a blocked name falls through to normal preference.
3. Plan/agent routing (`provider_policy.pick_provider` -> `_pick_provider`): acts on a route only if registered.
4. Tier policy (`tier_policy`): picks a tier, never a provider.
5. Verdict review (`pick_review_provider`): walks `_PREFERENCE`/the backup slot among registered providers; `anthropic` was already excluded by name.
6. Explicit pin (`stream_chat(provider_name=...)`): raises for an unregistered name.
7. CR272 failover / Room restart on the backup: needs `vllm_fallback` registered. A blocked backup is not a failover target, and the `vllm`-kind primary no longer takes the retry-because-a-backup-exists path.
8. Host probes that read `settings.vllm_base_url` directly (prefix-cache startup check via the gateway, `vllm_metrics` sampler, `room_runner.log_prefix_cache_status`, the `main.py` sampler gate): skipped when `vllm` is blocked.
9. Direct clients outside the gateway: none in `backend/app` (grep of `anthropic`, `kimi`, `gemini`, `google_ai`, `deepseek`, `dashscope`, `deepinfra`, `/chat/completions`). `backend/scripts/*_ablation.py` use `VLLMProvider` directly with `settings.vllm_base_url` (operator tools, not imported by the app). `kimi_prompt_review.py` reads `KIMI_API_KEY` from the process environment, by hand, outside the app; it is untouched.
10. `openrouter_api_key` and `openai_api_key` exist as settings but nothing reads them; they are not slots and cannot be reached.

## Part 2 — model/provider swap by configuration only

Audit result:

1. **Hard-coded model ids and URLs.** `deepseek`, `qwen`, `gemini` had their base URL and model literals in the gateway. They are now `DEEPSEEK_BASE_URL/MODEL`, `QWEN_BASE_URL/MODEL`, `GEMINI_BASE_URL/MODEL` (defaults = the old literals, forwarded in compose, listed in `beta.env.example`). `status()` also advertised Anthropic tier aliases for these slots and for `vllm_fallback`; they now resolve to the slot's configured model. What remains by design: `TIER_TO_MODEL` (Anthropic's own aliases, the one provider that is not a single-model OpenAI-compatible slot). No quirk, price lookup, tier route or thinking/sampling branch is keyed on a model string: prices come from `LLM_PRICES_JSON`, quirks from `kind`/settings. Model-keyed calibration (`evidence_record`, keyed on `provider:model` identity) reads "uncalibrated" after a swap by design (loud, not silent).
2. **URL shape.** The provider appends `/v1/chat/completions`, so a base with a trailing `/v1` became `/v1/v1/...` (the `qwen` default was exactly that, i.e. never worked). `normalise_base_url` now strips whitespace, trailing slashes and one trailing `/v1` or `/v1/openai` (DeepInfra's documented spelling); every spelling reaches the same `/v1/chat/completions`. Known limit: an endpoint whose chat path is not `<base>/v1/chat/completions` (Gemini's `.../v1beta/openai/chat/completions`) is still not reachable; Gemini is unused and blocked on Alpha and Beta.
3. **Served-model discovery.** `GET /v1/models` is issued per OpenAI-compatible slot with the same client; it works on any host (hosted ones return `id` without `root`, handled). Not host-specific. The vLLM `/metrics` prefix-cache check stays tied to `kind=vllm` on the primary, by design (informational).
4. **API key per slot.** `openai_compatible_headers`: a configured key is sent as `Authorization: Bearer <key>` for both kinds (the `vllm` kind already passed it through; now tested). Empty or whitespace-only sends NO auth header: never `Bearer `, never a placeholder.

5. **Per-slot extra request body (thinking off, and similar).** The `openai` kind sends no thinking field, so a model such as Ling-3.0-flash on DeepInfra runs with thinking ON unless the body carries `chat_template_kwargs.enable_thinking=false` (WP-10 scorecard §1b, §8; WP-10 used an overlay hook, `DEEPINFRA_EXTRA_BODY_JSON`). Each OpenAI-compatible slot now takes `<SLOT>_EXTRA_BODY_JSON` (`VLLM_`, `VLLM_FALLBACK_`, `GLM_`, `KIMI_`, `DEEPSEEK_`, `QWEN_`, `GEMINI_`): a JSON object merged into every request body sent to that slot. Empty merges nothing. Invalid JSON, a non-object, or a protected field fails boot, naming the setting. Precedence (`backend/app/core/llm_extra_body.py`): the gateway-owned fields `model`, `messages`, `stream`, `stream_options`, `max_tokens`, `temperature`, `response_format`, `structured_outputs`, `guided_*` can never come from this setting (refused at boot; also dropped defensively inside the provider); for any other top-level key the operator's value replaces the slot kind's default (e.g. `chat_template_kwargs` on a `vllm`-kind slot); the merge is shallow.

Ling-3.0-flash on DeepInfra as the Beta backup, thinking off: see the Beta lines below (single quotes keep compose from mangling the JSON).

Whether DeepInfra's hosted Ling honours `chat_template_kwargs` is WP-10's finding and was not re-tested here; this setting guarantees the field reaches the request body (tested), not the server's reading of it.

## Exact env lines

Alpha (`infra/alpha.env`, operator edits; not done here). The previously commented-out vendor keys may now be left in place or removed, with no effect: the list keeps them out and the boot log names them.

```
LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback,glm
VLLM_BASE_URL=http://192.168.20.74:8000
VLLM_MODEL=ami-llm
VLLM_KIND=vllm
VLLM_API_KEY=
VLLM_FALLBACK_BASE_URL=http://100.98.142.64:8004
VLLM_FALLBACK_MODEL=ling-3.0-flash-fin-fp4
VLLM_FALLBACK_KIND=vllm
VLLM_FALLBACK_API_KEY=
```

(`VLLM_FALLBACK_KIND=vllm` is not the default; the default is `openai`. `glm` stays allowed only so a `GLM_BASE_URL` already in the env keeps working; drop it from the list if unused.) After the change `/v1/llm/status` should show `allowlist: ["vllm","vllm_fallback","glm"]`, and the next postflight proves it. Ling has no price in `LLM_PRICES_JSON` today: add one before enabling a spend ceiling on Alpha, or its calls record cost NULL (observed in the live run).

Beta (`infra/beta.env`; matches `beta.env.example`):

```
LLM_PROVIDER_ALLOWLIST=vllm,vllm_fallback
VLLM_BASE_URL=https://api.deepinfra.com/v1/openai
VLLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
VLLM_KIND=openai
VLLM_API_KEY=<the Beta DeepInfra key>
VLLM_FALLBACK_BASE_URL=https://api.deepinfra.com/v1/openai
VLLM_FALLBACK_MODEL=inclusionAI/Ling-3.0-flash
VLLM_FALLBACK_KIND=openai
VLLM_FALLBACK_API_KEY=<the Beta DeepInfra key>
VLLM_FALLBACK_EXTRA_BODY_JSON='{"chat_template_kwargs":{"enable_thinking":false}}'
LLM_PRICES_JSON='{"deepseek-ai/DeepSeek-V4-Flash":{"in":0.09,"out":0.18},"inclusionAI/Ling-3.0-flash":{"in":0.06,"out":0.18}}'
```

(Saiful's ruling, 2026-11-19: Beta's backup is Ling-3.0-flash on DeepInfra. The boot check refuses an unpriced served model, so the price entry is part of the change. The live swap proof below used GLM-5.3-Flash as the second model, which was Beta's backup when the proof ran.)

## Tests

1. `tests/unit/test_cr281_provider_allowlist.py`: unset = unchanged; set = blocked slots absent from primary pick, force-provider, plan routing, review, explicit pin, failover, host probes, even with keys present; boot log names blocked slots at error level and carries no value; unknown name fails; normalisation; compose forwards; status fields and route; postflight pass/fail cases.
2. `tests/unit/test_cr279_beta_env.py`: Beta refuses an empty list and lists naming anthropic/kimi/gemini.
3. `tests/unit/test_cr281_model_swap.py`: two URL+model pairs per slot (vllm, vllm_fallback, glm, kimi, deepseek, qwen, gemini) set through env only, both route to the right host and model id; keyed vs keyless header (both kinds, blank key); URL with and without `/v1` and trailing slash; AST test that `llm_gateway.py`, `provider_policy.py`, `tier_policy.py` hold no model-id string constant and no OpenAI-compatible endpoint literal, except Anthropic's three tier aliases (justified above).
4. `tests_live/test_cr281_live_swap.py`: outside `testpaths`, skipped unless `DEEPINFRA_API_KEY` is in the environment; never in the unit suite or CI.

## Live swap proof (2026-11-19, run twice; key read from the environment, never printed or stored)

Through the real `LLMGateway` code path, `vllm_fallback` slot, env only, `max_tokens=50`, prompt "Reply with the single word: pong":

1. DeepInfra `https://api.deepinfra.com` + `deepseek-ai/DeepSeek-V4-Flash`, kind `openai`, key set: answered; reported model `deepseek-ai/DeepSeek-V4-Flash`; finish `stop`; 110 input / 3 output tokens.
2. Model changed by env to `zai-org/GLM-5.3-Flash` (listed in DeepInfra's catalogue): answered; reported model `zai-org/GLM-5.3-Flash`; 117 / 3 tokens.
3. Key unset: no `Authorization` header on the client; call failed loudly as HTTP 401 (`stream_error_status=401`, sentinel text "[AMI error: HTTP 401 ...]"), no failover (pinned call).
4. Keyless on-prem Ling (`http://100.98.142.64:8004`, `ling-3.0-flash-fin-fp4`, kind `vllm`): reachable from the Mac; answered; reported model `ling-3.0-flash-fin-fp4`; 130 / 3 tokens; no auth header.

Runs 1 and 2 used the bare host `https://api.deepinfra.com`. After the base was set to Beta's `https://api.deepinfra.com/v1/openai` (normalised to the same endpoint), one more call on DeepSeek-V4-Flash was made through the gateway and answered (104 / 3 tokens). Totals: 9 completion calls plus 2 catalogue GETs; every call 3 output tokens. The gateway logged no cost: neither DeepInfra model nor Ling is in `LLM_PRICES_JSON` here, so it logged `llm_price_missing` (cost NULL). At DeepInfra's list rates the whole run is a fraction of a cent.

## Doubts

1. `/v1/openai` was NOT usable as a base before this CR (it became `/v1/openai/v1/chat/completions`); the normaliser now maps it to the bare host, which serves `/v1/chat/completions` (proved live for both spellings).
2. `ling-3.0-flash-fin-fp4` has no `LLM_PRICES_JSON` entry (see above).
