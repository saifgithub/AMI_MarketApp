# Kimi calibration rooms — 2026-07-30

## UPDATE — root cause found, re-run in progress

Saiful asked directly: *"are we using `https://api.kimi.com/coding/v1`?"* —
no, the first pass used `api.moonshot.ai`. That question was the right one:
**his key is a Kimi Coding Plan subscription key** (console: kimi.com/code),
a separate product from the general Moonshot Open Platform, with its own
host and its own model-id namespace. Verified live:

```
curl https://api.moonshot.ai/v1/chat/completions      → 401 Invalid Authentication
curl https://api.kimi.com/coding/v1/chat/completions   → 200 OK
```

`kimi_base_url`/`kimi_model` defaults corrected to `https://api.kimi.com/coding`
/ `kimi-for-coding` (config.py, docker-compose.yml, infra/alpha.env.example).
The section below is the **first-pass run**, left as-written for the
record — everything past "Result" in that section describes the 401 failure,
not Kimi's actual quality. See the bottom of this file for the corrected
re-run's results once complete.

## First-pass run (pre-correction) — blocked on authentication Every one of the 180
agent calls made during this run (3 model variants × 5 tickers × 12 agents)
got **HTTP 401 from `https://api.moonshot.ai`**. The "PASS" verdicts recorded
below are the Portfolio Manager's degrade-loudly safety fallback (`"Portfolio
Manager did not return a machine-readable verdict; defaulting to no trade for
safety"`, `overridden_from_llm: true`) firing on total request failure, not
Kimi's actual judgment on any of these tickers. **None of this data says
anything about Kimi's quality yet** — re-run once the key issue is fixed.

## What was run

5 real, recently-completed Room verdicts pulled from melehost's `room_runs` +
`mandates` tables (user `8f1e288a…`, mandate_version 1 — same mandate for all
5, so this is a clean same-mandate replay, not a synthetic benchmark input):

| Ticker | Baseline (vLLM, live) action |
|---|---|
| BAC | APPROVE |
| NVDA | REJECT |
| NFLX | PASS |
| TDG | PASS |
| DIS | PASS |

Replayed via `backend/scripts/room_benchmark.py` against live Alpha
(`--plan trial_trader`, the mandate above passed via `--mandate-json`), with
melehost's `LLM_FORCE_PROVIDER` flipped to `kimi` for each of three model
variants in turn, restored to normal (vLLM) immediately after the third batch.
Total live-degradation window: ~12 minutes (much shorter than planned — each
Kimi call failed fast on the 401 rather than taking a genuine multi-second
generation, which is itself a clue this wasn't real inference).

## Raw results (all 15 runs: PASS, all via the safety fallback)

| Ticker | kimi-k3 | kimi-k2.7-code | kimi-k2.6 |
|---|---|---|---|
| BAC | PASS (fallback) | PASS (fallback) | PASS (fallback) |
| NVDA | PASS (fallback) | PASS (fallback) | PASS (fallback) |
| NFLX | PASS (fallback) | PASS (fallback) | PASS (fallback) |
| TDG | PASS (fallback) | PASS (fallback) | PASS (fallback) |
| DIS | PASS (fallback) | PASS (fallback) | PASS (fallback) |

Raw JSONL per batch: `runs_kimi-calib-k3-2026-07-30.jsonl`,
`runs_kimi-calib-k27code-2026-07-30.jsonl`, `runs_kimi-calib-k26-2026-07-30.jsonl`.

## What's confirmed vs. not

**Confirmed working correctly:**
- The provider wiring itself (registration, routing, `LLM_FORCE_PROVIDER`
  override) — the gateway correctly attempted every call against
  `https://api.moonshot.ai/v1/chat/completions` with the configured key, for
  all three model ids, and correctly labeled the failure with `self.name` in
  both the transcript (`[AMI error: HTTP 401 from the upstream provider
  (kimi)...]`) and the DB.
- The degrade-loudly safety net (CR040) — a total provider failure did NOT
  get silently treated as a real verdict; it correctly fell back to a
  labeled, safe PASS rather than fabricating a trade decision.

**Isolated — not our code.** A bare `curl` from the Mac straight to
`https://api.moonshot.ai/v1/chat/completions` with the exact same key (no
AMI code in the path at all) returns the same `401` with body
`{"error":{"message":"Invalid Authentication","type":"invalid_authentication_error"}}`.
This rules out a header/auth-format bug in `OpenAICompatibleProvider` — the
key itself is being rejected by Moonshot. Likely causes (unverified,
account-side): the key is invalid/revoked, or the Moonshot account needs
billing/balance set up before a key authenticates (a common pattern for LLM
provider APIs) — needs checking on platform.kimi.ai, which I can't do from
here.

**Not yet known:** anything about Kimi's actual Room-agent quality, on any
of k3 / k2.7-code / k2.6 — this calibration pass didn't reach real inference.

## Next step

Once the key is confirmed live — re-run the direct curl above first, cheap
and fast, no live-traffic impact — re-run the calibration recipe. Tickers
file and mandate JSON are preserved in this folder, so it's a rerun, not a
re-plan.
