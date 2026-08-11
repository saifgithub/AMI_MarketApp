<!--
R68-BATCH4.architect.md — architect submission lane. State derives from round numbers here vs
R68-BATCH4.auditor.md.
GATE: none was used while building. Batch 4 of the CR143 prompt + data-feed remediation programme
(one handshake PER BATCH, Saiful 2026-08-11).
-->

# R68-BATCH4 — audit lane (DEF063 · CR024 · CR147 A.1 · CR148 · **DEF258** + the Batch 1–3 acceptance)

**SHA:** `6b5fe052` (`main`, pushed to origin) — config half at `a2416204`, DEF258 at `6b5fe052`.
**SCOPE:** two things that belong together because the second was found by the first's measurement:
(1) the dark feed keys, (2) the truncation regression Batch 1 caused, plus the post-promotion
re-measurement that closes DEF236 and DEF251.
**depends-on:** R68-BATCH1 (`0ef2893f`, COMPLETE r1) · R68-BATCH2 (`0a5b4f1e`, COMPLETE r1) ·
R68-BATCH3 (`de1fd8a7`, COMPLETE r1, 2 MINOR, MINOR 1 closed in-lane).

---

## Part 1 — the dark feed keys (`a2416204`, already on Alpha as `alpha-2026-08-11-4`)

**Alpha Vantage: enabled, not deleted.** Saiful's call on CR147 A.1's fork. `news_analyst.md:17` and
the all-12 shared header at `room_prompts.py:652` had asserted a sentiment tag in **216/216** prompts
that was present in **0/216**. Verified in three places rather than assumed:

- the key answers live — `NEWS_SENTIMENT/NVDA`, 50 articles with per-ticker labels;
- `/v1/admin/config-check` on live Alpha reads `configured: true`;
- an **in-container** `fetch_live_news('NVDA')` returned **2 of 3** headlines tagged, rendering as
  `— sentiment: Neutral` and `— sentiment: Somewhat-Bullish` — the exact vocabulary the prompt
  promises. First time the claim has been true end-to-end.

A leading space on that env line was stripped before promoting. It was the only key of 36 not
starting at column 1, and since this defect class is *"present but unreadable"* it was not worth
reasoning about whether Compose strips it.

**Adanos secondary: wired.** `adanos_api_key_secondary` added to `config.py`, forwarded in
`docker-compose.yml`'s `api-alpha` block. 250 paid calls/month had sat idle and **undetectable**:
`test_config_compose_parity.py` walked `Settings` → compose only, so a key present in the env file
with no `Settings` field was invisible to it **in both directions**. The test now walks env-file →
`Settings` as well, with `_ENV_KEYS_WITHOUT_SETTINGS` (9 entries) as the explicit, reasoned
allowlist — a new test asserts every entry carries a reason, so the allowlist cannot become a
dumping ground. **It was red against the real gap before it was green.** It skips *loudly* when
`infra/alpha.env` is absent (worktrees; the file is gitignored) rather than passing vacuously.

## Part 2 — DEF258, and how it was found

This is the part that matters for review, because **Batch 1's own acceptance measurement found a
regression Batch 1 caused**, which is the whole argument for CR105 Amendment 1.

Evidence doc: `docs/forward_planning/CR143_agent_prompt_audit/POSTFIX_REMEASUREMENT_2026-08-11.md`.
12 tickers on `alpha-2026-08-11-4`, PRE/POST split at `2026-08-11T10:58:50Z` — the promoted
container's `StartedAt`, i.e. the exact instant the new prompt bytes began serving. **PRE n=612
turns / 51 convenes, POST n=156 / 13.**

| what | PRE | POST | verdict |
|---|---|---|---|
| parsed stance yield (debators) | 133/156 — 85.3% | **39/39 — 100%** | DEF251 **PASS** (target ≥95%) |
| turns over their own bullet cap | 127/612 — 20.8% | **11/156 — 7.1%** | DEF236 improved, 9/12 agents at zero |
| code fences | 1 (Trader) | **0/156** | `_NO_FENCE_CLAUSE` holds |
| mean chars/turn | — | **up on 11 of 12 agents** | "must not shorten" **PASS** |
| **turns at exactly `max_tokens`** | **0/612** | **6/156 — 3.8%** | **FAIL → DEF258** |

Truncation had been at 0/198 **by headroom, not by design**. Batch 1 spent it: outputs grew 20–120%.
The plan predicted the return at the tail of a *Trader* turn. It came back at the tail of the **PM's**
— `portfolio_manager` 2/14 (cap 1100), `aggressive_debator` 2/13, `neutral_debator` 1/13,
`bear_researcher` 1/13 — and the PM is the one agent where a clipped tail is not a short answer:

```
{ "action": "PASS", "narrational": "REJECT: Trade violates hard mandate enforcement…
```

That is live Alpha, SLB, `11:27:36Z`, **as the user read it in the Room**. Three failures stacked:
the object never closed → `extract_json_object` returned `None` → `_parse_pm_verdict` returned
`(text.strip(), None)`, so the caller failed safe to PASS (DEF059) **and the raw JSON source became
the transcript turn**.

### The fix is the parser, and the budget was deliberately not touched

`_close_truncated_object` walks the candidate once, tracking quote/escape state and container depth:

- **mid-string** (the common case) — close the quote in place; the clipped sentence is worth keeping.
- **outside a string** — the tail is a partial number, keyword or valueless key (`2.`, `tru`,
  `"narration":`), so fall back to the last **complete member**. Commas and closers only: a bare `"`
  closes keys as well as values, and cutting on a key's quote yields `{"size_pct"}`, which is not
  JSON. That was a real bug in my first cut — two tests caught it before it left the Mac.

**Repair is honest rather than a guess because of field order.** The PM emits `action`, `size_pct`
and the levels *before* `narration`; in all 14 samples the JSON began at character 1 with `action`.
A clip therefore loses the explanation, never the decision.

**Raising the budget was rejected on the numbers, not on taste.** The two clipped samples are
**censored** — their true length is unknown — so they cannot size a cap (P16). The other 12 finished
under 425 tokens against a 1100 ceiling. The tail is not a budget problem, so a bigger budget is not
a fix, only a wider net. `_AGENT_MAX_TOKENS` is unchanged in this batch.

**Three containments, each testable:**

1. **Opt-in.** `extract_json_object(text, *, repair_truncated=False)`. `brief_engine.py:311` and
   `portfolio_finding.py:1174` keep the strict behaviour byte-for-byte; a test asserts truncated
   input is still `None` for them.
2. **Second.** Even on the PM path the strict read runs first; repair only ever sees input that has
   already failed.
3. **Disclosed.** A repaired object is a PARTIAL read, so CR040 applies: `_PM_TRUNCATED_NARRATION`
   says so in the `[AMI …]` voice the client amber-marks (CR106 §3.3). Without it the user reads a
   sentence that stops mid-clause with no way to know why. A test asserts an **intact** verdict never
   carries the notice.

### What the fix must not become

"Accept anything" — a fabricated verdict is worse than a lost one, which is why DEF059 fails safe on
purpose. Asserted directly: single quotes, a trailing comma, prose and empty input are all still
rejected **with repair on**, and a balanced-but-malformed object is not salvaged (it was never
truncated). One further floor: `_parse_pm_verdict` already refuses an APPROVE carrying no `size_pct`,
and a test proves repair does not route around it — recovering a decision is allowed, minting a
position size for it is not.

## Verification

- `backend/tests/unit/test_def258_pm_verdict_truncation.py` — **14 tests**, including the live SLB
  string as a regression anchor.
- Full shared-checkout suite at `6b5fe052`: **3196 passed, 1 skipped**, 400.67s. (The one
  intermediate failure was `test_registers_no_drift` — DEF159's guard firing because the new row file
  was untracked while the table referenced it. Fixed by tracking the row, not by regenerating around
  it; green on re-run with `test_def258_*` and `test_def256_*`, 22 passed.)

## What is NOT claimed

- **`bull_researcher` got worse** on bullet compliance (3/13 → 4/13). At n=13 that is not
  distinguishable from noise, so it is recorded as unresolved, not as a regression, and needs the
  CR164 pinned batch to settle. Recorded in DEF236's row in the same words.
- The **PRE over-budget column is counterfactual** — those turns were written against a guide
  expressed in *sentences*. The comparison measures whether restating the budget in bullets makes it
  followable; it is not a claim that 127 instructions were disobeyed.
- POST is **13 convenes**. Every rate above carries that, and the CR164 pinned batch is still owed.
- **`"narrational"` is NOT fixed here.** The same SLB sample shows the model typo'd the narration
  key, so even after salvage that verdict publishes *"it wrote no rationale"* over real prose. That
  is DEF239, scheduled for Batch 8, now with a live instance rather than a hypothesis.
- **REJECT-inside-PASS at 4/14 (28.6%)** in the same sample — CR156 B, also Batch 8. Filed as
  evidence, not fixed.
- DEF063 closes; **CR024, CR147, CR148 stay non-done** — only their key/config halves are here.

---

**SUBMITTED: round 1**
