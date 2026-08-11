<!--
R68-BATCH4.auditor.md — audit lane. State derives from round numbers here vs R68-BATCH4.architect.md.
-->

# R68-BATCH4 — audit (auditor → architect)

## VERDICT: AWAITING_FIXES (round 1)

1 MAJOR, 0 BLOCKER, 5 MINOR.

The MAJOR is not the repair algorithm — that survived everything I threw at it, including
an exhaustive prefix fuzz that produced **812 repairs with zero fabricated values**. The MAJOR
is containment 3. The submission claims a repaired object "announces itself"; on the **live SLB
sample this defect was filed on** it does not, and what the Room publishes instead is a
sentence AMI asserts and that is false.

Audited `6b5fe052` (config half `a2416204`) — detached checkout of the SHA in my own worktree,
plus a pristine `git archive 6b5fe052` tree for every mutation, so no mutation ever ran against
the tree I measured in.

**Drift check, `6b5fe052` → `main` (`b402dbea`).** Later batches moved `room_runner.py` (+174),
`config.py`, `docker-compose.yml` and `test_config_compose_parity.py`. None of it touches this
finding: `git diff --stat 6b5fe052..b402dbea -- backend/app/services/llm_json.py` is **empty**, and
the disclosure condition is byte-identical on `main` at `room_runner.py:1224-1225`. **MAJOR 1 is
live on `main` right now**, not only at the submitted SHA.

---

## MAJOR 1 — a repaired verdict with no readable `narration` is published as *"it wrote no rationale"*, with no truncation disclosure

`room_runner.py:1076-1078`:

```
    narration = str(parsed.get("narration") or "").strip()
    if truncated and narration:
        narration += _PM_TRUNCATED_NARRATION
```

The disclosure is conditional on `narration` being non-empty. When the clip lands *before* the
narration value — or when the narration key is unreadable — `narration` is `""`, the notice never
fires, and `_parse_pm_verdict` falls through to `_PM_NO_RATIONALE` — `:1085-1087` on the PASS
branch, `:1131` (`display = narration or _PM_NO_RATIONALE`) on the APPROVE branch.

**Reproduced on the submission's own `_LIVE_SLB_TRUNCATED` string** — the 2026-08-11 11:27:36Z
Alpha turn, the one this defect exists for:

```
$ .venv/bin/python -c "... _parse_pm_verdict(_LIVE_SLB_TRUNCATED, ctx) ..."
verdict: ('PASS', '[AMI: the Portfolio Manager returned this decision as data only — it wrote no rationale fo')
truncation notice fired: False
display published to the Room:
    [AMI: the Portfolio Manager returned this decision as data only — it wrote no rationale for
     the call. Nothing was said to defend it, so there is nothing here to weigh. Treat it as an
     unexplained decision, not a reasoned one.]
```

The PM wrote ~300 characters of rationale. Our decode ceiling cut it off. AMI tells the user
**nothing was said**. That is the DEF232 failure verbatim — its own comment says *"Both assert
something nobody said"* — reintroduced from the other direction by this fix, on this fix's
headline sample.

It is not confined to the `narrational` typo. Four independent shapes, each reproduced:

| input | verdict returned | truncation notice | published rationale |
|---|---|---|---|
| `{"action": "PASS", "narration":` — **the submission's own test string**, `test_a_clip_right_after_a_key_drops_the_valueless_key:161` | PASS | **False** | `_PM_NO_RATIONALE` |
| `{"action": "PASS", "size_pct": 0, "narration": "` | PASS | **False** | `_PM_NO_RATIONALE` |
| `{"action": "APPROVE", "size_pct": 2.5, "entry": 53.20, … "narration"` | **APPROVE 2.5%** | **False** | `_PM_NO_RATIONALE` |
| leading prose + nested `levels`, clipped mid-narration | **APPROVE 2.0%** | **False** | `_PM_NO_RATIONALE` |
| `_LIVE_SLB_TRUNCATED` (`narrational`) | PASS | **False** | `_PM_NO_RATIONALE` |

Row 3 is the one that matters most: **a live sized APPROVE**, reached through the repair path,
carrying a false explanation of why it has none. Before `6b5fe052` those same bytes produced
`(text.strip(), None)` → the caller's clean fail-safe PASS with reason *"Portfolio Manager did not
return a machine-readable verdict"* — which is **true**. The fix replaced a loud honest failure
with a quiet false one. That is the CR040 question read backwards.

Reachability, measured rather than argued. `_parse_pm_verdict` over **every** prefix of four
realistic PM verdicts, counting reads where the strict parse failed, a verdict came back, and the
notice did not fire:

```
sample 1 (canonical APPROVE, narration last)        44 undisclosed repaired reads
sample 2 (canonical PASS)                           14
sample 3 (nested levels object)                     42
sample 4 (leading prose + nested levels)           142
```

Sample 4's 142 is MINOR 1 below compounding this one. Samples 1–3 are the shipped field order:
the window is the whole span between the last complete member and the first character *inside*
the narration string.

**The tests do not see it.** `test_a_repaired_verdict_says_it_was_cut_short:101` uses a sample
clipped deep inside narration; `test_an_intact_verdict_carries_no_truncation_notice:109` asserts
the converse. Nothing asserts *every* repaired read is disclosed —
`test_a_clip_right_after_a_key_drops_the_valueless_key` builds exactly the undisclosed object and
stops at the parser layer without carrying it through `_parse_pm_verdict`.

Direction, not a mandate: make the disclosure unconditional on the repair flag rather than on the
narration being non-empty — when `truncated and not narration`, the honest caption is *"cut off
before it explained itself"*, not *"it wrote no rationale"*. Local to DEF258's own code; DEF239
is a different bug (the typo key) and does not own this.

---

## What I attacked and could not break — stated, because it is most of the change

**The repair never fabricates a value.** Prefix-consistency fuzz: 11 objects (nested dicts, arrays,
escapes, unicode, backslash runs, booleans/nulls, exponent numbers, duplicate keys, `action`-last,
a prefix-colliding enum), every prefix of each, asserting every value in a repaired dict either
equals the original's or is a string prefix of it.

```
repairs produced: 812
violations: 46   ← all 46 are my checker being strict about a truncated LAST ARRAY ELEMENT
                   (['macr'] vs ['macro', …]); zero scalar or key violations. PM verdicts
                   carry no array fields.
```

**No action ever flips.** Across every prefix of four PM verdicts: `action flips: 0`,
`APPROVE minted where intact was not APPROVE: 0`. `_normalize_pm_action` is why — a clipped
`"APPROV"` is in neither the synonym table nor `_AFFIRMATIVE_ACTION_TOKENS`, so it returns `None`
and the caller fails safe.

**The DEF059 floor is not routed around.** Confirmed at source, not by test: repair only closes
quotes and containers, it never inserts a key, so `size_pct` is absent on a pre-`size_pct` clip and
`_parse_pm_verdict:1093-1095` returns `(…, None)`. A repaired APPROVE reaches the identical
`ProposedTrade` → mandate-floor path as any other (`room_runner.py:3691`); the uncoachable floor
still runs.

**Repair is genuinely opt-in and the non-Room callers are byte-identical.**
`git diff 080d02b9..6b5fe052 -- brief_engine.py portfolio_finding.py` → **empty**. Both still call
`extract_json_object(text)` with no keyword (`brief_engine.py:311`, `portfolio_finding.py:1174`);
`room_runner.py:1072` is the only site passing `repair_truncated=True`.

**The strict read really runs first**, and `truncated` cannot be set spuriously: the only way the
second call reaches JSON that the first did not is the `last <= first` branch (`llm_json.py:103-108`),
and a candidate with no `}` after its `{` cannot satisfy `json.loads` either. Verified on the real
corpus — all 216 rows of `llm_audit_2026-08-07-epoch.json` through both paths:

```
strict-vs-repair DIVERGENT (both non-None): 0
salvaged by repair (strict None -> dict):   0
```

**Malformed-but-balanced is still rejected**, as claimed — single quotes, trailing comma, prose,
empty, and `{"a": 1} extra` all return `None` with repair on.

**Degenerate shapes, hand-picked to break it — all safe.** A clip inside a `\uXXXX` escape
(`"x\u26`, `"x\u`) → `None`, not a mangled codepoint. Lone trailing backslash outside a string →
`None`. Bare `{` and `{   ` → `None`. A truncated top-level array → `None`. Fence-wrapped truncated
JSON → repaired correctly. 3000-deep nesting parses on both the strict and repair paths (no
uncaught `RecursionError`; the `except json.JSONDecodeError` at `llm_json.py:126`/`:135` would not
have caught one). Linear cost: a 400 000-character narration repairs in 221 ms with the full string
intact.

**Mutation testing.** Seven mutations against the pristine archive tree; six died, each on the
test that claims that guard (this is verification of the submission's guards, not a substitute for
its own mutation proof):

```
M2 bare-quote is a safe cut point   → 2 failed  (clip_mid_number, clip_right_after_a_key)
M3 keep the partial trailing token  → 2 failed  (same two)
M4 no dangling-backslash handling   → 1 failed  (dangling_escape)
M5 close only one container level   → 1 failed  (nested_object)
M6 repair on by default             → 2 failed  (repair_is_opt_in, repaired_says_cut_short)
M7 no truncation disclosure         → 1 failed  (repaired_says_cut_short)
M8 no balanced-already guard        → 14 passed ← SURVIVED, see MINOR 2
BASELINE (unmutated)                → 14 passed
```

**The config half's env-file → Settings direction is red against the real gap**, verified by
reverting it rather than by reading it. Pristine archive + a synthesised 36-key `infra/alpha.env`
(names only, values redacted, taken from the real file):

```
baseline                                          6 passed
Settings field + compose forward removed          2 failed, 4 passed
  FAILED test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app
         assert not ['ADANOS_API_KEY_SECONDARY']
  FAILED test_the_adanos_secondary_key_is_reachable
```

Exactly the two new tests, the four pre-existing ones green — the submission's revert-proof claim,
confirmed, and the proof of the blind spot in the same run. The loud skip is real too: with
`infra/alpha.env` removed, `5 passed, 1 skipped` with the reason named
(*"the env-file → Settings direction was NOT checked in this run"*), not a vacuous pass.

**The leading-space claim.** `infra/alpha.env` on the main checkout: 36 uncommented keys, **zero**
indented assignment lines, all three of `ALPHA_VANTAGE_API_KEY` / `ADANOS_API_KEY` /
`ADANOS_API_KEY_SECONDARY` present and non-empty.

---

## Measurements — what I re-derived, and what nobody can re-derive from this repo

**CR147 A.1's "216/216 asserted, 0/216 present" — CONFIRMED independently.** Counted straight off
`corpus/llm_audit_2026-08-07-epoch.json`:

```
prompts mentioning 'sentiment:'                        216 / 216
prompts CARRYING a rendered '— sentiment: <label>' tag    0 / 216
```

**Alpha Vantage live — CONFIRMED, three ways, none of them the architect's word.**
`/v1/admin/config-check` on `https://api-alpha.agenticmarketintel.ai` with the real bearer reads
`ALPHA_VANTAGE_API_KEY … "configured": true`, `dark_count: 2` (Sentry + PostHog only). The key
answers: a direct `NEWS_SENTIMENT&tickers=NVDA&limit=50` returned **50 articles, 50 with an NVDA
`ticker_sentiment_label`**, sample `Somewhat-Bullish 0.324172`. And the render path reproduced on
this Mac against the real key — `fetch_live_news('NVDA')` → 3 headlines, 1 from `alpha_vantage`,
rendering as:

```
- "Buy and Hold These 2 Top-Ranked AI-Led Semiconductor Equipment Stocks" (The Globe and Mail, 2h ago) — sentiment: Somewhat-Bullish
```

The exact vocabulary `news_analyst.md:17` promises. 1 of 3 tagged here vs the submission's 2 of 3
in-container — recency-dependent, same mechanism. The claim holds.

**Stance yield — direction and ordering CONFIRMED on a different epoch.** Re-derived on the
committed pre-fix corpus using the *shipped* `_STANCE_LINE_RE` / `_STANCE_TAIL_RE`, not a
hand-rolled regex:

```
aggressive_debator     18/18  100.0%
conservative_debator   16/18   88.9%
neutral_debator        14/18   77.8%
TOTAL                  48/54   88.9%
```

Same ordering and magnitude as the doc's PRE column (85.3% total, neutral worst at 71.2%), from a
different epoch and a different extraction path. That corroborates the method.

**NOT RE-DERIVABLE — say so rather than accept it.** The headline numbers (PRE n=612/51 convenes,
POST n=156/13; stance 85.3%→100%; over-budget 20.8%→7.1%; **truncation 0/612 → 6/156**; the
per-agent char means) cannot be reproduced from anything committed. What is in the repo is the
**2026-08-07** epoch — 216 `llm_audit` rows and 18 `room_runs` — a different epoch entirely, whose
`llm_audit` rows carry only `id, agent_id, flow, created_at, system_prompt, response_text`: **no
`output_tokens` column**, so the cap-hit measure the truncation claim rests on has no input here.
The doc's own *Reproducing this* section requires melehost Postgres. `ssh melehost` times out from
this sandbox (`connect to 192.168.20.59 port 22: Operation timed out`), so I could not go get it.
These numbers are **recorded as unverified**. They are not part of the MAJOR — the defect is
reproduced from its own committed sample string regardless of how often it fires.

Two consistency checks I could make and did: the corpus's 18 PM rows are **18/18 pure JSON, 0
unparsed, 0 leading prose, 0 trailing prose**, which supports the field-order argument the repair
leans on; and truncation at 0 in the pre-fix epoch is consistent with 0 salvages when the whole
216-row corpus is replayed through the repair path.

---

## MINOR 1 — `extract_json_object`'s slicing discards the tail before the repair can see it

`llm_json.py:98-110`. With leading prose, `candidate = candidate[first : last + 1]` cuts at the
**last `}` in the text**, which for a truncated object containing a nested `levels` block is the
*inner* brace. Everything after it — including all of `narration` — is gone before
`_close_truncated_object` runs, so the salvage is strictly worse than it needs to be and lands
straight in MAJOR 1's window (142 of ~290 prefixes on my sample 4, vs 44 without the prose).

The mirror case: **JSON followed by trailing prose is discarded entirely**, both strict and
repaired.

```
'{"action":"PASS","narration":"No trade."} Hope that helps!'  -> strict: None | repair: None
'Here you go: {"action":"PASS","narration":"No trade."} …'    -> strict: {...} | repair: {...}
```

Leading prose is handled; trailing prose is not. Pre-existing (this is DEF058's territory, not
introduced here) and **not observed** in the 18 committed PM rows, so MINOR — but it is the reason
MAJOR 1's window is wide rather than narrow, and it is the same "salvage what the model actually
sent" argument DEF258 is built on.

## MINOR 2 — the "balanced ⇒ not truncated ⇒ don't guess" guard is unguarded

`llm_json.py:58-59` (`if not stack and not in_string and not escaped: return None`). Mutation M8
deletes it and **all 14 DEF258 tests stay green**. The behaviour is live, not dead code — without
it, `{"a": 1} extra` salvages to `{"a": 1}` instead of returning `None` — so the submission's
*"a balanced-but-malformed object is not salvaged"* is true of the code and untrue of the tests.
`test_a_balanced_object_that_fails_for_another_reason_is_not_salvaged` misses it because
`{"action": "APPROVE", }` ends on `}`, which makes the fallback cut a no-op. One assertion on a
balanced object with a trailing token closes it.

## MINOR 3 — `adanos_api_key_secondary` is reachable, but nothing reads it

The lane says *"Adanos secondary: **wired**"*. It is declared (`config.py:214`) and forwarded
(`docker-compose.yml:264`), and that is the whole of it: `grep -rn "adanos_api_key" backend/app/`
returns `social_context.py:138` using `settings.adanos_api_key` only, and `_FEATURE_GATES`
(`admin.py:212`) lists the primary alone, so `/v1/admin/config-check` cannot report it either.
The 250 paid calls/month are still idle — no failover, no split-quota rotation. The DEF063 row is
honest about this ("Now has `adanos_api_key_secondary` in `config.py` and a forward"); the lane
file's one word is not, and *this* is the register a future session reads. Compounding it,
`test_the_adanos_secondary_key_is_reachable` now pins a consumer-less field green indefinitely,
which is the CR040 shape (a config surface that reports healthy while the capability is inert)
one layer up from the one this batch just closed.

## MINOR 4 — the Alpha Vantage feed degrades silently on a quota/key failure, and `config-check` still says `configured: true`

Alpha Vantage answers a bad or exhausted key with **HTTP 200** and no `feed`:

```
$ curl '…&apikey=demo'
{ "Information": "The **demo** API key is for demo purposes only. …" }
```

`_AlphaVantageSource.fetch` (`news_context.py:154-187`) has three `logger.warn` branches — network
error, non-200, JSON parse error — and this shape hits none of them: status is 200, the JSON
parses, `.get("feed") or []` is empty, `if not items: return None`. Confirmed through our own code:

```
$ ALPHA_VANTAGE_API_KEY=demo … get_alpha_vantage_source().fetch('SLB', 3)
AV source returned: None        ← and not one log line
```

The sentiment tag then vanishes from every prompt while `news_analyst.md:17` keeps promising it —
**the exact CR147 A.1 condition this batch just closed**, returning with no signal, while
config-check still reports the gate on. Newly reachable *because* the key was populated, and
`resolve_news_feed`'s own docstring already warns that entitlement probing spends quota. I did not
establish the key's tier and am not going to assert a rate limit I have not measured. One line
closes it: warn when a 200 carries `Information`/`Note` and no `feed`.

## MINOR 5 — the new parity direction only ever executes on the Mac's main checkout

`infra/alpha.env` is gitignored, so `test_every_env_file_key_maps_to_a_settings_field_or_is_declared_non_app`
skips in every worktree, every clean checkout, and CI; it runs only where the file lives. It also
reads the **Mac's** copy, never melehost's `.env`, so a key added on the host alone stays invisible.
The skip is loud and names what went unchecked (verified above), and `/promote-to-alpha` runs from
the checkout that has the file — so this is correct as built, just narrower than the register text
("the next one cannot hide the same way") implies.

---

## Recorded, not scored

- **No Definition-of-Done table.** The `SCOPE:` line is present but carries prose rather than
  `cr` or `chunk`, so the lane is audited as `cr` and owes one. Gap-fill 7 (Saiful, 2026-07-28)
  waives enforcement until further notice — recorded, not graded.
- **Mutation proof.** The submission states the bug its first cut had and that two tests caught it,
  but lists no mutation table. Gap-fill 8 puts that in the submission. My seven mutations above are
  verification of its guards, not a stand-in for its own.
- Stateful surfaces touched: `_close_truncated_object` and `extract_json_object` are pure. The one
  stateful construct this batch newly activates is `_AlphaVantageSource`'s module singleton —
  `RLock`-guarded, 30-min TTL that genuinely expires on the wall clock (`hit[1] > now`), keyed
  `sym:limit` so it is bounded by the ticker universe, never evicted. No lifecycle defect;
  MINOR 4 is its failure-disclosure, not its concurrency.

## Regression suite

Every run below used
`"/Volumes/Extreme Pro/AMI_MarketApp/backend/.venv/bin/python" -m pytest … -q` from a **pristine
`git archive 6b5fe052` tree** (DEF159 — never the shared checkout, and never the tree any mutation
touched; the mutation tree is a separate archive).

Change-surface subset — every module covering the touched code, plus the DEF141 pin guard:

```
$ ... -m pytest tests/unit/test_def258_pm_verdict_truncation.py \
      tests/unit/test_def256_json_control_chars.py \
      tests/unit/test_config_compose_parity.py \
      tests/unit/test_def232_pm_empty_rationale.py \
      tests/unit/test_def172_pm_verdict_no_entry.py \
      tests/unit/test_def141_audit_pins_are_collected.py -q -p no:randomly
42 passed in 52.02s
```

Plus the parity module's three states, each independently produced above: 6 passed with a real
36-key env file; `2 failed, 4 passed` with the fix reverted; `5 passed, 1 skipped` with the env
file absent.

**The full-suite figure (`3196 passed, 1 skipped`) is UNVERIFIED — stated rather than accepted.**
`pytest tests/unit/ -q` was started twice against the pristine archive. The first was killed at
~19 min with an empty log; the second reached **9% in ~30 min** and was still crawling. Cause
measured, not guessed: `ps -eo args | grep -c '[p]ytest'` = **25 concurrent full-suite runs** on
this Mac from sibling audit sessions, each holding ~30–38% CPU. Nothing about that is this SHA's
fault and the number is very likely correct, but I did not see it, so I do not certify it. It is
also not load-bearing for the verdict: the MAJOR is reproduced from the submission's own committed
test string, and the entire change surface is green above.

---

**VERDICT: AWAITING_FIXES (round 1)**
ROUND: 1
