# Every upstream commit between our fork basis and upstream HEAD

`7e9e7b8` (2026-05-01, the frozen mount) → `a33fd4c` (2026-07-18, upstream `main`) — **106 commits**.
Measured, not estimated: `git -C "/Volumes/Extreme Pro/TradingAgent_upstream" rev-list --count 7e9e7b8..HEAD`.

★ marks a commit that touches `tradingagents/agents/` — 21 of the 106. Oldest first.

Release boundaries in range: **v0.2.5** `6553759` · **v0.3.0** `0a19704` · **v0.3.1** `5a3d1b5`.

| | SHA | Date | Subject |
|---|---|---|---|
|   | `2d2c9e6` | 2026-03-31 | add analyst execution planning and timing hooks |
|   | `4300b68` | 2026-03-31 | merge upstream main into analyst-phase1-observability |
|   | `f4519bc` | 2026-03-31 | use execution plan metadata for first analyst |
| ★ | `e7ec980` | 2026-04-18 | feat: add analysis-only crypto asset mode |
| ★ | `99ec63f` | 2026-04-18 | merge upstream main into crypto-analysis-mvp |
| ★ | `5bae826` | 2026-05-08 | Merge remote-tracking branch 'upstream/main' into crypto-analysis-mvp |
|   | `db7e0a6` | 2026-05-10 | fix(cli): load .env from user's CWD when run as console script |
|   | `c405867` | 2026-05-10 | fix: merge streamed chunks into final_state so reports save correctly |
|   | `e2c850e` | 2026-05-10 | fix(cli): preserve exchange suffixes in ticker prompt |
|   | `afdc6d4` | 2026-05-10 | chore: suppress upstream langgraph allowed_objects deprecation noise |
|   | `22bb91b` | 2026-05-11 | fix(llm): structured output for DeepSeek V4 and reasoner |
|   | `704b762` | 2026-05-11 | fix(docker): pre-create .tradingagents dir with appuser ownership |
|   | `19d22b5` | 2026-05-11 | feat(llm): add MiniMax as a built-in provider |
|   | `9482cae` | 2026-05-11 | fix: bundle config/recursion/missing-key fixes |
|   | `e131668` | 2026-05-11 | fix(llm): MiniMax integration polish vs official docs |
|   | `78fe77f` | 2026-05-11 | feat(llm): bump OpenAI catalog to GPT-5.5 frontier |
|   | `9e00c81` | 2026-05-11 | feat(llm): bump Anthropic catalog to Claude Opus 4.7 frontier |
|   | `4f057e2` | 2026-05-11 | feat(llm): swap Gemini 3.1 Flash-Lite to GA stable |
|   | `0011b5e` | 2026-05-11 | feat(llm): align xAI catalog with docs — adopt grok-4.20 frontier |
|   | `faaeeba` | 2026-05-11 | feat(cli): collapse regional duplicates; refresh Qwen catalog |
|   | `d0dd042` | 2026-05-11 | feat(llm): GLM dual-region split + catalog refresh |
| ★ | `0fcf136` | 2026-05-11 | feat(agents): rename to sentiment_analyst; integrate StockTwits + Reddit |
| ★ | `384fe1a` | 2026-05-11 | feat(news): configurable fetch params via DEFAULT_CONFIG |
| ★ | `6b384f7` | 2026-05-11 | feat(i18n): localize researchers, risk debators, research mgr, trader |
|   | `d13e9b7` | 2026-05-11 | feat(config): TRADINGAGENTS_* env-var overlay for DEFAULT_CONFIG |
|   | `9f7abfc` | 2026-05-11 | feat(cli): detect missing provider API keys and persist to .env |
| ★ | `879e2bb` | 2026-05-11 | refactor: align display label and docs with sentiment_analyst rename |
| ★ | `a2f343b` | 2026-05-11 | Merge remote-tracking branch 'upstream/main' into crypto-analysis-mvp |
|   | `249caba` | 2026-05-11 | Merge remote-tracking branch 'upstream/main' into analyst-phase1-observability |
|   | `f10daa2` | 2026-05-11 | feat(ollama): OLLAMA_BASE_URL end-to-end with endpoint confirmation |
|   | `8008624` | 2026-05-11 | feat(ollama): allow Custom model ID in the CLI dropdown |
|   | `819e813` | 2026-05-11 | docs(readme): Ollama line covers endpoint, pull, custom model |
|   | `78d063d` | 2026-05-11 | feat(reflection): configurable alpha benchmark for non-US tickers |
|   | `a5cb7cb` | 2026-05-11 | chore: release v0.2.5 — sentiment analyst, env-var config, more providers |
|   | `b16fe53` | 2026-05-17 | Merge #487 — analyst execution planning and timing hooks |
|   | `a2e7ac1` | 2026-05-17 | Merge #567 — analysis-only crypto asset mode |
|   | `3e5e99b` | 2026-05-17 | fix(graph): integrate #487 + #567 — sentiment label, route, propagate asset_type |
|   | `e848b5e` | 2026-05-17 | fix(llm): gate MiniMax reasoning_split by model capability (#826) |
|   | `61522e1` | 2026-05-17 | fix(llm): skip Anthropic effort kwarg on non-supporting models (#831) |
| ★ | `d7b40a2` | 2026-05-30 | fix(graph): resolve instrument identity to stop wrong-company hallucination |
|   | `3543e53` | 2026-05-31 | fix(dataflows): fall back to Reddit RSS search when JSON 403s |
|   | `a66aa8f` | 2026-05-31 | fix(deps): require yfinance >=1.4.1 and tolerate non-Date index column |
| ★ | `e80636f` | 2026-05-31 | feat(sentiment): structured output for the Sentiment Analyst |
| ★ | `47cbb32` | 2026-05-31 | feat(market): verified market-data snapshot to ground numeric claims |
|   | `8a22594` | 2026-05-31 | feat(config): expose sampling temperature and document reproducibility |
|   | `2c9f1bf` | 2026-05-31 | fix(cli): consolidate duplicate get_ticker and only announce non-stock asset type |
|   | `8694bd0` | 2026-05-31 | fix(llm): send MiniMax reasoning_split via extra_body so the openai SDK accepts it (#826) |
|   | `d6762d6` | 2026-05-31 | chore: gitignore .env.enterprise and reports/ |
|   | `c93b92c` | 2026-05-31 | feat(markets): add China A-share benchmarks and document non-US tickers |
|   | `2f85be6` | 2026-05-31 | chore(llm): add latest models and default to GPT-5.5 |
|   | `1ff3f07` | 2026-05-31 | fix: support commodity/forex/crypto tickers and never invent prices (#781) |
|   | `2e67782` | 2026-05-31 | feat(cli): skip interactive LLM selection when configured via environment (#873) |
|   | `04f434e` | 2026-06-01 | chore: README housekeeping and remove stale TODO |
|   | `2a58c22` | 2026-06-13 | ci: add test/lint/smoke workflow, declare python-dotenv, recommend Python 3.12 |
| ★ | `7c8fe2f` | 2026-06-13 | fix(data): normalize symbols on the identity and reflection paths |
|   | `76add90` | 2026-06-13 | fix(cli): unify ticker handling with the data-path symbol normalizer |
|   | `6560883` | 2026-06-13 | fix(data): respect the configured vendor chain and log vendor failures |
|   | `dab0768` | 2026-06-13 | fix(data): include the requested end date in yfinance fetches |
|   | `a597063` | 2026-06-13 | fix(cli): correct invalid escape sequence in confirm_ollama_endpoint docstring |
|   | `e4be7cc` | 2026-06-13 | fix(data): add Alpha Vantage request timeout and stop mislabeling bad keys |
|   | `0c1231a` | 2026-06-13 | fix(data): keep future/undated news out of historical windows |
|   | `4e7821d` | 2026-06-14 | fix(graph): register get_verified_market_snapshot in the market ToolNode |
|   | `20d3b07` | 2026-06-14 | feat(llm): unify OpenAI-compatible providers behind a registry + generic endpoint |
|   | `295e84c` | 2026-06-14 | feat(llm): add NVIDIA NIM, Kimi, Groq, and Mistral providers |
|   | `895ed13` | 2026-06-14 | feat(llm): add Amazon Bedrock as a first-class provider |
| ★ | `ddfb840` | 2026-06-14 | feat(data): add FRED macro indicators as an optional vendor |
| ★ | `db05903` | 2026-06-14 | feat(data): add Polymarket prediction markets as a keyless vendor |
|   | `7df18fc` | 2026-06-14 | refactor(data): unify vendor errors under a VendorError hierarchy |
|   | `9fd54f8` | 2026-06-14 | fix(data): reject stale yfinance OHLCV instead of reporting wrong prices |
|   | `eeb84aa` | 2026-06-14 | fix(reddit): go RSS-first with 429 backoff and robust transport errors |
|   | `308757c` | 2026-06-14 | fix(data): catch http.client transport errors in StockTwits |
|   | `3cddf1e` | 2026-06-14 | fix(llm): use the OpenAI Responses API only for native endpoints |
|   | `cbc5f67` | 2026-06-14 | test(i18n): guard that every report agent applies the output language |
| ★ | `e3bc872` | 2026-06-14 | chore(lint): make the repository ruff-clean under the strict select |
|   | `6b6177e` | 2026-06-14 | ci: lint the full repository |
|   | `03600f3` | 2026-06-14 | chore(models): refresh the model catalog to current provider lineups |
| ★ | `7aef10a` | 2026-06-14 | fix(sentiment): guide an informative, high-signal narrative |
|   | `c15200d` | 2026-06-14 | fix(cli): label OpenRouter prompts and shortlist mainstream models |
|   | `a420ad0` | 2026-06-21 | fix(cli): honor env precedence for LLM and run config |
|   | `7bb16c5` | 2026-06-21 | chore(models): retire deprecated models, simplify thinking config |
|   | `ee1ece3` | 2026-06-21 | fix(dataflows): degrade gracefully when an optional vendor fails |
|   | `9ad98c5` | 2026-06-21 | fix(data): normalize ticker on the news path |
| ★ | `517eeaf` | 2026-06-21 | fix(structured): harden structured output for local servers and thinking models |
|   | `709fe2b` | 2026-06-21 | fix(graph): dedupe the trailing message in the debug stream |
| ★ | `0405168` | 2026-06-21 | fix(schema): coerce null-ish strings in optional float fields |
|   | `ec3974b` | 2026-06-21 | chore(config): remove the no-op analyst_concurrency_limit knob |
|   | `0b61eff` | 2026-06-21 | chore(deps): remove the unused uv.lock |
|   | `a0120e1` | 2026-06-21 | feat(reporting): share the report-tree writer between the CLI and the API |
| ★ | `2b2d685` | 2026-06-21 | fix(prompts): put the current date at the top of analyst prompts |
|   | `8ab24f3` | 2026-06-21 | test: make the API-key fixture robust to empty-string env vars |
|   | `cbd17ac` | 2026-06-21 | docs: drop retired model IDs from the reproducibility note and smoke script |
|   | `85946c2` | 2026-06-22 | chore: release v0.3.0 |
|   | `3570f2e` | 2026-07-05 | fix(dataflows): apply the Alpha Vantage fundamentals look-ahead filter |
| ★ | `622f99d` | 2026-07-05 | fix(analysts): align the news prompt with the get_news tool signature |
|   | `b47a828` | 2026-07-05 | fix(graph): give the shared debate/risk routers a complete path_map |
|   | `daf1da9` | 2026-07-05 | fix(graph): key checkpoints on graph shape and expose the LLM retry budget |
|   | `a102afa` | 2026-07-05 | fix(dataflows): map crypto to StockTwits/Reddit sentiment symbols |
|   | `43bd32b` | 2026-07-05 | feat(llm): support Bedrock API-key auth via AWS_BEARER_TOKEN_BEDROCK |
|   | `0f70af2` | 2026-07-05 | feat(llm): add Claude Sonnet 5 and Fable 5 to the catalog |
|   | `01477f9` | 2026-07-05 | chore: release v0.3.1 |
|   | `40774ca` | 2026-07-18 | fix(dataflows): make the Yahoo news window UTC and end-exclusive |
|   | `d78c698` | 2026-07-18 | fix(dataflows): refresh the same-day OHLCV cache |
|   | `3f6c082` | 2026-07-18 | fix(cli): report an unusable terminal instead of a prompt_toolkit traceback |
| ★ | `030b434` | 2026-07-18 | fix(agents): stop priming tool calls in schema-only structured agents |
|   | `7bbe33a` | 2026-07-18 | docs: add trending badge |
|   | `a33fd4c` | 2026-07-18 | docs: streamline README header |
