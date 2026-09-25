# 05 — Kimi cross-check: how it was reached, and what it found

Saiful asked to cross-check the vLLM findings against a second, independent
model. This doc is both the result and the **exact record of how Kimi/Moonshot
was actually called** — worth documenting in detail because getting it right
took several live corrections, and a wrong key/endpoint pairing was used
briefly before being caught.

## Which key, which product — this took two corrections to get right

Kimi is reachable as two **separate products with separate key scopes**, a
distinction already noted in this codebase's own config comments
([backend/app/core/config.py](../../../backend/app/core/config.py), the `kimi_*`
settings block, CR130):

| Product | Base URL | Key prefix | Model-id namespace |
|---|---|---|---|
| **Kimi Coding Plan** (subscription) | `https://api.kimi.com/coding` | `sk-kimi-…` | `kimi-for-coding`, `kimi-for-coding-highspeed` |
| **Moonshot Open Platform** (pay-per-token) | `https://api.moonshot.ai` | different prefix | `kimi-k2.6`, `kimi-k2.7-code`, `kimi-k2.7-code-highspeed`, `kimi-k3` |

**melehost already has a `KIMI_API_KEY` set** — this is the **Coding Plan** key,
wired into `llm_gateway.py`'s `kimi` provider for Saiful's own coding-assistant
use (CR006/CR126/CR130), and it must never be reused for anything else. The
first attempt at this cross-check used melehost's existing key by default,
before Saiful caught it ("melehost keys are for kimi code") — that path was
abandoned without ever sending a request through it for this research.

Saiful separately added a **new key to the Mac's own `.env`**
(`KIMI_API_KEY=sk-ZJutc…`) specifically for this test. Confirmed live
(`GET https://api.moonshot.ai/v1/models`, 200 OK, lists `kimi-k2.6` /
`kimi-k2.7-code` / `kimi-k2.7-code-highspeed` / `kimi-k3`) that this is a
**Moonshot Open Platform** key, a different product from melehost's — Saiful
confirmed directly ("the key is mac is not for kimi code"). Every completion in
this research used this Mac-side Open Platform key, `api.moonshot.ai`, never
melehost's Coding Plan key.

## Which model, and why

Of the four Open Platform models this key can reach, `kimi-k2.7-code*` 400s
outright (Coding Plan namespace, off-limits to this key — confirmed live, not
assumed). Between the remaining two:

- `kimi-k2.6`: thinking-disabled still leaves ~1 residual `reasoning_tokens`
  (confirmed live, repeatable) — a real API quirk, not a sign thinking stayed on
  (`reasoning_content` is an empty string, not populated text).
- `kimi-k3`: thinking-disabled returns `reasoning_tokens: None`,
  `reasoning_content: None` — a genuine, clean zero.

**`kimi-k3` was used as the default model** for exactly this reason. The scripts
tolerate up to 2 residual reasoning tokens (`_REASONING_TOKEN_TOLERANCE`) so a
future run against `kimi-k2.6` would not be wrongly flagged as a thinking-still-on
failure over that documented 1-token quirk.

## Turning thinking off

Moonshot's OpenAI-compatible endpoint does **not** honor the OpenAI/Qwen-style
`enable_thinking` flag this codebase already uses for its Qwen provider
(`llm_gateway.py:1073`, `extra_body={"enable_thinking": False}`). Four candidate
request-body shapes were tested live before finding the one that actually works:

| Request body addition | Result |
|---|---|
| `{"no_thinking": true}` | 200 OK, but `reasoning_tokens: 18` — silently ignored |
| `{"enable_thinking": false}` | 200 OK, but `reasoning_tokens: 27` — silently ignored |
| `{"thinking": false}` | **400 Bad Request** |
| `{"thinking": {"type": "disabled"}}` | **200 OK, `reasoning_tokens: None`, `reasoning_content: None` — genuinely off** |

`{"thinking": {"type": "disabled"}}` is the only one of the four that actually
disables reasoning on this API, and it is what every Kimi call in this research
used. Every script that calls Kimi
(`ibm_kimi_repeat10.py`, `ibm_stance_pivot_probe.py`,
`ibm_growth_threshold_test.py` — all under [`code/`](code/)) asserts this on
every response and raises loudly if `reasoning_tokens`/`reasoning_content` come
back nonzero, rather than silently accepting a thinking-still-on completion as
if it were the clean-comparison one this research needed.

## Temperature is locked to one value

Every model on this key rejects any `temperature` other than exactly `0.6`:

```
{"error":{"message":"invalid temperature: only 0.6 is allowed for this model","type":"invalid_request_error"}}
```

Confirmed on both `kimi-k3` and `kimi-k2.6`, at T=0.2 and T=1.0. This is a
**server-side platform lock on this key/plan**, not a request-shape bug on this
codebase's side — no sweep across temperature is possible with Kimi under this
key. Every Kimi result in this research is therefore at the one value the
platform allows, T=0.6, with the growth-threshold and pivot-probe cascades run
up to 10x at that fixed point (Saiful's explicit instruction: "10 times each
unless Kimi becomes consistent").

## Where this ran from — Mac, not melehost, and why that took a correction too

The first attempt at these calls ran via `docker exec ami_api_alpha` on
melehost, mirroring how the earlier vLLM scripts were run (those genuinely need
the container's Python env and LAN route to reach `192.168.20.74:8000`). Saiful
questioned this directly ("I don't understand why you are using docker for
this") — correctly: the Kimi-calling scripts import nothing from `app.*`, only
`psycopg2` (to read the captured prompt from `llm_audit` via an SSH tunnel to
melehost's Postgres, `ssh -f -N -L 5434:127.0.0.1:5434 melehost`) and `httpx`
(a plain internet call to `api.moonshot.ai`), and the Mac reaches both directly.
Every Kimi call from that point on ran on the Mac itself, no container, no
melehost detour.

## Result: consistency vs. vLLM, fixed T=0.6

`backend/scripts/ibm_kimi_repeat10.py`, 10x repeats per run, `kimi-k3`,
`thinking: disabled`, T=0.6:

| | Kimi (T=0.6) | vLLM (T=0.6) |
|---|---|---|
| **Run A** `fundamentals_analyst` | 6 FOR / 4 NEUTRAL | 2 FOR / 8 NEUTRAL |
| **Run B** `fundamentals_analyst` | 4 FOR / 6 NEUTRAL | 10/10 NEUTRAL (unanimous) |

Full data: [`out/05a_kimi_run_a_repeat10_T0.6.json`](out/05a_kimi_run_a_repeat10_T0.6.json),
[`out/05b_kimi_run_b_repeat10_T0.6.json`](out/05b_kimi_run_b_repeat10_T0.6.json).

Every single Kimi completion across both runs cited the same lead figure
(6.2% FCF yield) — the same fact, correctly quoted, every time (consistent with
[DEF445](../../defect/_registry/DEF445.row.md): the number itself is precomputed
and correct; what varies is how much weight the model gives it).

## Read

- **Kimi is not more stable than vLLM at a comparable temperature** — if
  anything, Run B is where the two providers diverge most sharply (Kimi 4/6,
  vLLM unanimous 10/10 NEUTRAL at the same nominal T=0.6). This rules out "it's
  just this one vLLM deployment being flaky" — two independent model families
  show the same shape of instability on the identical prompt.
- **A given temperature value does not mean the same thing across providers.**
  vLLM's Run B fully converges by T=0.6; Kimi's Run B is still a coin flip at
  the only temperature Kimi allows. "Set temperature to X" is not a portable
  stability knob across model providers.
