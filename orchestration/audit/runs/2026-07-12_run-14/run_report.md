<!--
Auditor run report — run-14 (2026-07-12, session AT:U1). Round-1 audit of CR023
(News Analyst live feed — Yahoo + Alpha Vantage NEWS_SENTIMENT), submitted late
by the architect (AT:R58) covering AT:R57 work. Fixed in 4b153a2. Owner: AUDITOR.
-->

# run-14 (round 1) — CR023 (News Analyst live feed)

- **Auditor session:** AT:U1 (track U), 2026-07-12
- **Audited SHA:** `4b153a2` (`feat(agents): make News + Social Media analysts
  truthful`), an ancestor of my `HEAD 22c84c6`. Later commits (`c942120` CR024
  Adanos, `73e984f`/`22c84c6` DEF051/CR033) took the suite past 640, so the count
  can only be reproduced at the exact SHA — done in an **isolated detached
  worktree** (`git worktree add --detach .claude/worktrees/audit-CR023 4b153a2`),
  main venv (py 3.13.13, sqlite tempfile). Worktree removed after.
- **Provenance:** submitted late (work shipped AT:R57, lane opened AT:R58 ahead of
  DEF051's promote). First CR-class item on track U since the DEF wave.

---

## CR023 — News Analyst live feed (`4b153a2`) → COMPLETE

**What shipped (verified in source):**
- **New `news_context.py`** — `LiveHeadline` NamedTuple shared by both sources.
  `_YfinanceSource` wraps the already-cached market-data provider (no second
  yfinance client). `_AlphaVantageSource` hits `NEWS_SENTIMENT`, 30-min TTL cache
  (billed API), parses per-ticker `ticker_sentiment[].ticker_sentiment_label`
  (falling back to article `overall_sentiment_label`). `_merge_headlines` dedupes
  by normalized title (sentiment source passed first → wins collisions), sorts by
  recency, caps to limit. `build_news_context_block` self-gates on
  `use_real_market_data`.
- **`room_runner._profile_for_ticker`** — inside the `use_real_market_data`
  guard: overlays the real top headline onto `catalyst`, stores extra headlines,
  sets `news_source="live"`; overlays real `next_earnings_date`/quarter
  (try/except-wrapped). `forward_catalyst`/`macro_tone`/`fed_tone`/`fed_impact`
  deliberately left synthetic (no real feed) — not fabricated.
- **`agent_runner`** (1-on-1) — News-Analyst-gated real-headline injection,
  reusing the ticker already extracted for the fundamentals block; LLM path only.
- **`room_prompts._format_profile`** — granular disclosure: fundamentals / news /
  forward-macro-sentiment each labeled live-or-synthetic independently.
  `_catalyst_line` surfaces extra headlines; earnings labeled LIVE.
- **`overlay_generator._news_block` + `content/agents/news_analyst.md`** — drop
  the fabricated Reuters/Bloomberg/FT/macro-calendar/regulatory-filings claims;
  disclose the real (Yahoo + AV, no macro-calendar, no regulatory-filings) scope.

**Why it's correct:**
- **Never-raises, end-to-end.** Both sources return `None` on any failure;
  `fetch_live_news` wraps each call in `try/except Exception`; `room_runner`
  guards with `if news_items:` and wraps `earnings()`. Adversarial nit:
  `resp.json().get("feed")` would `AttributeError` on a JSON-array body (AV's
  inner `except` catches only ValueError/KeyError/TypeError) — but the outer
  `fetch_live_news` `except Exception` catches it; contract holds, no behavioral
  difference. Sub-MINOR, no finding minted.
- **Disclosure can't lie.** `news_source="live"` is set only when a real fetch
  succeeded, and the header labels news LIVE iff that flag is set. Same coupling
  for fundamentals (`data_source`) and earnings. Synthetic fields are hard-labeled
  ALWAYS-illustrative.
- **Gating verified.** News/earnings overlays sit inside
  `if settings.use_real_market_data:`; 1-on-1 injection gated to
  `AgentId.NEWS_ANALYST` only (`test_news_block_not_injected_for_other_agents`).
- **No-key regression.** `alpha_vantage_api_key` defaults `""`; AV source built
  only when set. Yahoo-to-prompt is the intended new behavior, disclosed as live.
- **AV shape.** Matches the real NEWS_SENTIMENT schema independently; endpoint
  provenance confirmed against the TradingAgent mount's `alpha_vantage_news.py`.

**Tests (reproduced):** `640 passed` at `4b153a2`. CR023 subset in isolation —
`test_news_context.py` (25) + `test_one_on_one_news_injection.py` (4) +
`test_room_runner.py` news/earnings/label tests → **69 passed**. Coverage is
behavior-focused: degradation (yahoo empty / provider raises / AV network error /
bad status / empty feed / both empty → synthetic fallback), combine/dedupe/
recency/cap, per-ticker vs overall sentiment, cache TTL, unparseable time → 0,
News-Analyst-only gating, and live-vs-synthetic disclosure labeling.

**Register:** `cr_list.md` CR023 = `in_progress` — honest (not `done`:
macro-calendar/regulatory filings unconnected by design; AV key not yet promoted).
CR024 stays `proposed`.

**Scope:** `4b153a2` bundles CR024's social-media truthfulness fix — disclosed,
one coherent "make both analysts truthful" directive; CR024 is its own lane.
CR023's slice is cleanly separable and correct. The folded-in `next_earnings_date`
is scope-appropriate (news/catalyst, cheap — fetch/cache already existed & tested).

**Live:** backend-only; **needs `/promote-to-alpha`** with `ALPHA_VANTAGE_API_KEY`
to activate the paid AV path and to run a live Room end-to-end on Alpha. Not
forceable from the Mac (pure editor). Honestly deferred in the DoD; the unit
fixtures exercise the real fetch/merge/degrade/gate/label paths.

---

## Verdicts

| Item | SHA | Verdict |
|---|---|---|
| CR023 | `4b153a2` | **COMPLETE (round 1)** — zero BLOCKER/MAJOR; real news wired truthfully, never-raises + honest disclosure, 640 reproduced, register accurate. |

No OUT-OF-SCOPE findings this round.
