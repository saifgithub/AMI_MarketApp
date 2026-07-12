# Datasets — research notes

> Verified 2026-05-13. Re-check licenses before any commercial deployment.

---

## Round-1 strategy

- **Public HF datasets only.** No Claude Opus distillation in research.
- **License floor:** research/non-commercial is fine for round 1. Commercial deployment needs a re-audit.
- **Format:** every example normalised to chat-style JSONL with the mandate overlay rendered into the **user-side** (not system-side). Use [overlay_generator.py](../../backend/app/agents/overlay_generator.py) as the canonical generator.
- **Replay mix:** every role's training set includes ~5–10% general instruction-following data ([UltraChat-200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k) slice) to prevent catastrophic forgetting.

---

## Core finance datasets

| Dataset | URL | Size | License | Target role(s) |
|---|---|---|---|---|
| TAT-QA | [next-tat/TAT-QA](https://huggingface.co/datasets/next-tat/TAT-QA) | 16.5k Q&A on real SEC filings | Verify | fundamentals_analyst |
| FinQA | [ibm-research/finqa](https://huggingface.co/datasets/ibm-research/finqa) | 8k Q&A over 2.8k reports | Verify | fundamentals_analyst |
| ConvFinQA | [FinGPT/fingpt-convfinqa](https://huggingface.co/datasets/FinGPT/fingpt-convfinqa) | Multi-turn finance QA | Verify | research_manager (debate shape) |
| FinanceBench | [PatronusAI/financebench](https://huggingface.co/datasets/PatronusAI/financebench) | 10k+ Q&A across 40 companies | Verify | EVAL (not training) |
| FiQA | [LLukas22/fiqa](https://huggingface.co/datasets/LLukas22/fiqa) | Pre-processed | Verify | quick fundamentals prototype |
| S&P 500 Earnings Transcripts | [kurry/sp500_earnings_transcripts](https://huggingface.co/datasets/kurry/sp500_earnings_transcripts) | 33k+ transcripts, 2005–2025 | Verify | fundamentals_analyst, news_analyst |
| SEC Financial Statements + Notes | [DenyTranDFW/SEC-Financial-Statements-And-Notes-Dataset](https://huggingface.co/datasets/DenyTranDFW/SEC-Financial-Statements-And-Notes-Dataset) | XBRL extracts | Verify | fundamentals_analyst |
| Earnings Calls Q&A | [lamini/earnings-calls-qa](https://huggingface.co/datasets/lamini/earnings-calls-qa) | Pre-formatted SFT | Verify | fundamentals_analyst |

## Sentiment / news

| Dataset | URL | Size | License | Target role(s) |
|---|---|---|---|---|
| FinancialPhraseBank | [takala/financial_phrasebank](https://huggingface.co/datasets/takala/financial_phrasebank) | 4.8k sentences, 5–8 annotator consensus | CC-BY-NC-SA 3.0 | social_media_analyst, news_analyst |
| Twitter Financial News Sentiment | [zeroshot/twitter-financial-news-sentiment](https://huggingface.co/datasets/zeroshot/twitter-financial-news-sentiment) | 11.9k tweets, bullish/bearish/neutral | MIT | social_media_analyst |
| Financial Tweets Sentiment | [TimKoornstra/financial-tweets-sentiment](https://huggingface.co/datasets/TimKoornstra/financial-tweets-sentiment) | 12.1k tweets | Verify | social_media_analyst (alt corpus) |
| FNSPID | [Zihan1004/FNSPID](https://huggingface.co/datasets/Zihan1004/FNSPID) | 10M+ news entries, S&P 500 | CC-BY-NC 4.0 | news_analyst |
| Financial News Multisource | [Brianferrell787/financial-news-multisource](https://huggingface.co/datasets/Brianferrell787/financial-news-multisource) | 57M rows, 24 sources, 1990–2025 | Verify | news_analyst pre-training |

## Multi-turn / debate / reasoning

| Dataset | URL | Notes |
|---|---|---|
| Tool-Use Multi-Turn Reasoning | [interstellarninja/tool-use-multiturn-reasoning](https://huggingface.co/datasets/interstellarninja/tool-use-multiturn-reasoning) | 14.5k traces. Template for research_manager + trader. |
| Atlas-Reasoning | [AtlasUnified/Atlas-Reasoning](https://huggingface.co/datasets/AtlasUnified/Atlas-Reasoning) | 42 reasoning categories, GPT-4 synthetic. Use cautiously for debate POC. |
| Finance-Instruct-500k | [Josephgflowers/Finance-Instruct-500k](https://huggingface.co/datasets/Josephgflowers/Finance-Instruct-500k) | 500k multi-turn finance Q&A. Apache 2.0. Broad SFT base. |

## Concierge / onboarding (persona)

| Dataset | URL | Notes |
|---|---|---|
| FinePersonas-v0.1 | [argilla/FinePersonas-v0.1](https://huggingface.co/datasets/argilla/FinePersonas-v0.1) | 21M personas, MIT. Not finance-specific; layer onto Finance-Instruct-500k. |
| Synthetic-Persona-Chat | [google/Synthetic-Persona-Chat](https://huggingface.co/datasets/google/Synthetic-Persona-Chat) | 21M personas. Alternate. |
| Roleplay | [hieunguyenminh/roleplay](https://huggingface.co/datasets/hieunguyenminh/roleplay) | 5k character interactions. Shows persona-anchoring shape. |
| UltraChat 200k | [HuggingFaceH4/ultrachat_200k](https://huggingface.co/datasets/HuggingFaceH4/ultrachat_200k) | General conversational. Use for replay-mix anti-forgetting. |

---

## Forex / macro track

MVP is US equities, but the agents need macro/FX reasoning today (dollar moves, carry trade, oil-linked currencies). v1.0 GCC/Malaysia makes FX load-bearing.

**No dedicated forex-SFT dataset exists on HF.** We lean on central-bank text and (later) synthetic Q&A.

| Dataset | URL | Notes |
|---|---|---|
| FOMC Communication | [gtfintechlab/fomc_communication](https://huggingface.co/datasets/gtfintechlab/fomc_communication) | 2.5k labelled sentences (hawkish/dovish/neutral), 1996–2022. CC-BY-NC-4.0. Fundamentals_analyst macro-policy reasoning. |
| ECB-FED Speeches | [istat-ai/ECB-FED-speeches](https://huggingface.co/datasets/istat-ai/ECB-FED-speeches) | 4,987 speeches, 1996–2025. License: verify. news_analyst macro feed. |
| FOMC Statements & Minutes | [vtasca/fomc-statements-minutes](https://huggingface.co/datasets/vtasca/fomc-statements-minutes) | Weekly auto-updated through Apr 2026. CC. Current macro grounding. |
| FinBen-FOMC | [TheFinAI/finben-fomc](https://huggingface.co/datasets/TheFinAI/finben-fomc) | 496 instruction-format Q&A. CC-BY-NC 4.0. Lightweight FX-policy SFT. |
| Forex-Daily-Price | [paperswithbacktest/Forex-Daily-Price](https://huggingface.co/datasets/paperswithbacktest/Forex-Daily-Price) | 150+ pairs OHLCV. Other (subscription). Grounding-only, not text SFT. |

**Known gaps (don't try to close in research phase):**
- Carry-trade reasoning — no dataset. Synthetic Q&A via Opus distillation (deferred).
- GCC / Tadawul / SAR — no HF dataset. Small Tadawul corpus on GitHub (`ralkhawaldeh85/Tadawul-Dataset`, ~2k records). Saudi Press Agency scraping is a v1.0 sub-project.
- Bursa Malaysia / MYR / BNM — no HF dataset. data.gov.my publishes rates; BNM publishes policy statements. Scraping deferred to v1.0.

---

## Per-role round-1 dataset map

| Role | Round-1 datasets |
|---|---|
| concierge | Finance-Instruct-500k (filtered to onboarding/explainer turns) + FinePersonas-v0.1 + UltraChat 200k replay |
| fundamentals_analyst | TAT-QA + FinQA + S&P 500 Earnings + FOMC Communication + UltraChat replay |
| market_analyst | (round 2 — needs synthetic chart-interpretation Q&A) |
| news_analyst | FNSPID + ECB-FED Speeches + FOMC Statements + UltraChat replay |
| social_media_analyst | FinancialPhraseBank + Twitter Financial News Sentiment + UltraChat replay |
| bull_researcher | (round 2 — debate-shape synthetic data needed) |
| bear_researcher | (round 2 — debate-shape synthetic data needed) |
| research_manager | ConvFinQA + Tool-Use Multi-Turn Reasoning + UltraChat replay |
| trader | Tool-Use Multi-Turn Reasoning + (round 2 synthetic trade-proposal JSON) |
| conservative_debator | (round 2) |
| neutral_debator | (round 2) |
| aggressive_debator | (round 2) |
| portfolio_manager | **Do not fine-tune in research phase.** Stays on Claude until everything else is proven. |

---

## License audit checklist (per-dataset gate before download)

1. Confirm license on the HF dataset card.
2. If CC-BY-NC* or `Other` — usable for research, NOT for distributed model weights.
3. Record license in `Silent_Scout/02_data/recipes/<role>.md` next to the dataset reference.
4. Any dataset with no license tag at all → skip. Don't guess.

---

## Opus distillation — cost ladder (deferred)

What it is: feed Claude Opus 4.7 our role prompts + mandate seeds, capture outputs (passed through `safety_floor.check_mandate_compliance`), train Qwen LoRA to imitate.

| Scope | Examples | Output tokens | Estimated cost (Claude Opus 4.7 output rate) |
|---|---|---|---|
| 1–2 role pilot (Concierge + fundamentals_analyst) | ~10k | ~10M | ~$750 |
| 13 roles × 5k examples | ~65k | ~65M | ~$4.9k |
| 13 roles × 10k examples (full) | ~130k | ~130M | ~$9.8k |

Prompt caching on shared system prompts cuts ~30–40% off input-side cost. Output tokens dominate and don't cache.

**Decision rule:** zero spend during research. Re-evaluate only after Phase 1+2 prove the public-data recipe works.
