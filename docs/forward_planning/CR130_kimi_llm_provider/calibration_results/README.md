# Kimi calibration rooms — 2026-07-30

## THIRD UPDATE — fixed, full genuine Room verdict obtained

Saiful's direction: *"remove the token limit completely. The token limit was
a local inferencing limitation. I just need to let KIMI give us 1 full
room."* Implemented as a provider-scoped floor rather than deleting the
per-agent budget system — `OpenAICompatibleProvider` now takes an optional
`max_tokens_floor`; Kimi is registered with `KIMI_MAX_TOKENS_FLOOR` (default
`8000`), which raises whatever `room_runner.py` requests up to at least that
value for Kimi calls only. vLLM/Anthropic are untouched. See
`backend/app/services/llm_gateway.py` (`OpenAICompatibleProvider.stream_chat`)
and `backend/app/core/config.py`. Commit: `fix(CR130): provider-scoped
max_tokens floor for Kimi's reasoning overhead`.

Re-ran exactly one calibration ticker (BAC, matching Saiful's ask for one
full room, not a re-run of all five) via
`backend/scripts/room_benchmark.py`, `LLM_FORCE_PROVIDER=kimi`,
batch `kimi-calib-floorfix-2026-07-30`:

| | |
|---|---|
| Action | **APPROVE** (matches the vLLM baseline's APPROVE for BAC) |
| `overridden_from_llm` | `false` — a genuine Room verdict, not the DEF059 fallback |
| Size / entry / target / stop | 1.5% / $61.07 / $69.01 / $57.41 |
| Duration | 611s (~10.2 min) — vs. vLLM's baseline of a few tens of seconds |
| Container logs | zero `room_agent_truncated` / length-stop events across all 12 agents |

Full PM reasoning (verbatim, from `runs_kimi-calib-floorfix-2026-07-30.jsonl`):

> "BAC clears mandate compliance: it is long-only, liquid, and the 1.5%
> starter contributes only ~0.09 percentage points of the 50% portfolio
> drawdown cap with a 6% stop. The fundamentals support a long-term GARP
> thesis at P/E 14.5, PEG 1.07, 21% revenue growth, 30% margins, and
> $280,819M net cash, but the chart offers no breakout confirmation at
> $61.07 with only $1.92 of upside to the $62.99 ceiling and RSI 61 / in-line
> volume. I am approving a half-size starter now to begin accumulating while
> keeping powder dry to scale toward the 3% cap on a confirmed daily close
> above $62.99 with above-average volume; the 6-week horizon lands near the
> FOMC decision in 48 days, with a stop at $57.41 and a target at $69.01."

**Read:** the reasoning-token diagnosis (SECOND UPDATE, below) was correct
and the fix resolves it — Kimi can produce a coherent, well-grounded,
mandate-compliant Room verdict once given enough token budget for its
chain-of-thought. The ~10x latency vs. vLLM (611s vs. vLLM's usual
tens-of-seconds) is the open cost question for any B7 candidacy — not
re-measured across a full 5-ticker set here, since Saiful's ask was
specifically for one full room, not a re-benchmark. `LLM_FORCE_PROVIDER`
restored to empty (vLLM default) on melehost immediately after this run;
verified via `/v1/llm/status` → `active_provider: vllm`.

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

## SECOND UPDATE — real root cause: reasoning-token budget, not endpoint or quality

Re-ran against the corrected `api.kimi.com/coding` endpoint (`kimi-for-coding`,
batch `kimi-calib-forcoding-2026-07-30`). Real calls now happen (200s, no
auth failures) but 4/5 runs still landed on the PM's `DEF059` fail-safe
("lost its model connection... reconvene the room") with realistic
multi-minute durations (186–349s) — a materially different failure from the
first pass's instant 401s.

**Root cause, confirmed via container logs + isolated curl tests:** every
agent call hit `llm_call_length_stop` with `chars: 0` — the model spent its
**entire** `max_tokens` budget (600–900, varies by agent role) on invisible
`reasoning_content` and never emitted a single visible `content` character.
This is not a connection issue and not a Kimi quality issue — it's Kimi's
Coding Plan models being genuine reasoning models whose chain-of-thought
consumes the same token budget as the final answer, and this codebase's
per-agent budgets (tuned for non-reasoning providers) are too small to leave
room for both.

Isolated with direct curl tests (bypassing the app, same prompt complexity as
a real PM call — 374 prompt tokens):

| max_tokens | reasoning_effort | reasoning_tokens | content | finish_reason |
|---|---|---|---|---|
| 600 (trivial prompt) | — | 388 | real, 921 chars | stop |
| 900 (realistic PM prompt) | — | 899 (all of it) | **empty** | length |
| 900 (realistic PM prompt) | `low` | 899 (all of it) | **empty** | length — `reasoning_effort` did not help |
| 4000 (realistic PM prompt) | — | 1,207 | **real, 643 chars, clean JSON verdict** | stop |

`reasoning_effort: "low"` did not measurably reduce reasoning length in this
test — not a usable lever here, at least not with that value. The fix that
actually works is simply a larger `max_tokens` ceiling for this provider —
roughly 1,200+ tokens of reasoning overhead on top of whatever content
budget an agent role needs, so ~2,000–4,000 depending on role, vs. the
current 600–900.

**Not yet fixed in code** — this needs either a per-provider `max_tokens`
override (Kimi/reasoning-style providers get a higher ceiling, vLLM/Anthropic
keep their current tuned values) or some other mechanism; `room_runner.py`
currently hardcodes shared per-agent-role budgets with no provider
awareness. Left as an open item pending Saiful's call on whether to invest
in it now. The other 3 Coding Plan model variants (`kimi-for-coding-highspeed`,
`k3`, `k3-256k`) were not calibration-tested — all four are reasoning models
on the same endpoint, so they'd almost certainly hit the identical
token-budget wall; re-running them now would just reconfirm this finding,
not add new information.

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
