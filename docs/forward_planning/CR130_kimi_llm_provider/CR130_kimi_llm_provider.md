# CR130 — Kimi (Moonshot) LLM provider, direct API

**Status:** done · **Session:** AT:Infrastructure · **Date:** 2026-07-30
**Source:** Saiful — *"I am looking to try KIMI"* (correcting my earlier framing of
Anthropic as the B7 interim default under D-068), then, on routing: *"Direct to
Moonshot"* over OpenRouter.

Executes the provider-layer half of [CR017](../CR017_multiprovider_llm_routing/CR017_multiprovider_llm_routing.md)
§3/§5 — which was research-only and explicitly deferred implementation to a
separate build CR — scoped down to exactly what's needed to make Kimi callable
for manual testing. Does not implement CR017's other open items (usage
capture §2.4, provider routing-by-level §4, Anthropic `cache_control` §5.5).

## What

- Generalized `VLLMProvider` into `OpenAICompatibleProvider(name, base_url,
  model_name, api_key, extra_body=None)` per CR017's own design; kept
  `VLLMProvider` as a real (not aliased) subclass so `check_prefix_cache_at_startup`'s
  `isinstance` check still correctly excludes non-vLLM instances.
- Registered Kimi as an `OpenAICompatibleProvider` instance, direct to
  `https://api.moonshot.ai` (not OpenRouter — Saiful's explicit choice,
  knowingly accepting the ToS/data-training exposure CR006 flagged).
- New `Settings` fields: `kimi_api_key`, `kimi_base_url` (default
  `https://api.moonshot.ai`), `kimi_model` (default `kimi-k3`, Moonshot's
  current flagship as of 2026-07-26 — CR006's "trails Sonnet 5" verdict was
  measured on the older `kimi-k2.7-code`, not K3, which is unevaluated).
- `_PREFERENCE` extended to `vllm > anthropic > kimi > mock` — Kimi ranks
  below the two already-trusted providers, so setting the key alone does not
  redirect live Alpha traffic.
- New `llm_force_provider` / `LLM_FORCE_PROVIDER` override so Kimi (or any
  registered provider) can actually be exercised for a manual test without
  touching `_PREFERENCE` or unregistering vLLM. Falls through to normal
  preference on an unregistered/typo'd name — a test env var must never be
  able to 500 a live flow.
- Forwarded in `docker-compose.yml`'s `api-alpha` block (CR040 compose-parity
  — `test_config_compose_parity.py` catches a forgotten forward). `KIMI_BASE_URL`/`KIMI_MODEL`
  mirror their Settings defaults into the compose substitution
  (`${KIMI_MODEL:-kimi-k3}`), matching the existing `VLLM_MODEL` pattern —
  a bare `:-` would have silently blanked the non-empty defaults.
- Documented in `infra/alpha.env.example` and added to `admin.py`'s
  `_FEATURE_GATES` config-check registry.

## Why

Saiful wants to manually test Kimi as a candidate B7 provider (the Beta cloud
LLM pick, deliberately left open under D-068/CR126) — both against CR006's
existing quality bar (measured on `kimi-k2.7-code`) and fresh against `kimi-k3`
(released 4 days before this session, unevaluated by any prior research).
None of the four keys already in `Settings` (`openrouter`, `openai`,
`google_ai`, `deepseek`) had a registered provider class to test against —
CR017 already identified this gap and scoped the fix; this CR just executes
the smallest slice of it for Kimi specifically, rather than build the full
routing-by-level layer nobody asked for yet.

## Scope

**In scope:** provider class + registration + config + compose forwarding +
tests, as above. **Out of scope:** CR017's usage-capture/telemetry (§2.4),
provider routing-by-user-level (§4), Anthropic `cache_control` wiring (§5.5 —
flagged separately as a real gap the D-068 Anthropic-interim-default framing
exposed), and DeepSeek/Qwen/Gemini registration (same class, but no key/ask
for those yet).

## Acceptance

- [x] `OpenAICompatibleProvider` generalized, `VLLMProvider` behavior
      unchanged (existing vLLM tests pass unmodified except one wording
      assertion, updated to match the now-generic error message)
- [x] Kimi registers when `KIMI_API_KEY` is set; ranks below vllm/anthropic
      in `_PREFERENCE`
- [x] `LLM_FORCE_PROVIDER` overrides preference for testing; falls through
      safely when unregistered
- [x] `backend/tests/unit/ -q` green (1653 passed; 2 pre-existing lesson-corpus
      failures unrelated to this change, flagged separately, not fixed here)
- [x] `docker-compose.yml` forwards all 4 new fields; `test_config_compose_parity.py`
      passes
- [ ] Calibration rooms (recent Room results vs. Kimi, across its model
      variants) — tracked separately, not part of this CR's acceptance
