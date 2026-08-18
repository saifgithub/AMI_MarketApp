# LLM predictive edge on stock prices/returns — 2026 literature, and cautionary findings

Every item below was opened and read directly by the research agent (arXiv abstract/HTML, regulator page,
or a corroborating secondary source when the primary was paywalled) — not taken from a search snippet
alone. Confidence is noted per item; items that couldn't be verified are flagged as such rather than
dropped silently. arXiv IDs use YYMM format, so `26XX.NNNNN` = 2026.

**Overall picture: split, leaning toward "no durable price-prediction edge," which is what AMI's own
internal research found independently** ([`../quant_finance/README.md`](../quant_finance/README.md) §4).
Genuine price/return *prediction* from price/technical/news data keeps showing weak-to-fragile edge that
decays under scrutiny or turns out to be memorization; LLM-as-*interpreter* (fundamentals, filings) keeps
being flagged as the more defensible use — see [02_fundamentals_and_industry.md](02_fundamentals_and_industry.md).

---

## 1. Prediction-edge findings

1. **"A Review of Large Language Models for Stock Price Forecasting from a Hedge-Fund Perspective"** —
   Olivia Zhang, Zhilin Zhang. arXiv 2605.05211, submitted 2026-04-10; accepted IEEE Conference on
   Artificial Intelligence (Spain, 2026-05-08/10). Survey covering sentiment extraction, filings/earnings-call
   analysis, price tokenization, multi-agent trading. Flags "fragility in sentiment analysis," data leakage,
   and "limits of stock price predictability." Cites a behavioral-finance result: even with near-omniscient
   advance knowledge of WSJ headlines, human hit rate was only 51.5%, ~45% of participants lost money, 16%
   went bust — used to argue sentiment/news signals give minimal edge. Concludes LLMs' real value is
   **interpretive/factual-extraction**, not standalone price prediction, and recommends specialized
   multi-agent decomposition over monolithic forecasting. **Verified by reading the paper.**
   https://arxiv.org/abs/2605.05211

2. **"Can LLM-based Financial Investing Strategies Outperform the Market in Long Run?"** — Weixian Waylon
   Li, Hyeonjun Kim, Mihai Cucuringu, Tiejun Ma. arXiv 2505.07078 (originally 2025-05, but v5 revised
   2026-02-12, v6 finalized 2026-06-26 — a genuine 2026-updated result). Previously reported LLM investing
   advantages "deteriorate significantly" under broader cross-section and longer evaluation; strategies are
   overly conservative in bull markets (underperform passive benchmarks) and overly aggressive in bear
   markets (heavy losses). **Verified by reading the abstract.** https://arxiv.org/abs/2505.07078

3. **"PolyBench: Benchmarking LLM Forecasting and Trading Capabilities on Live Prediction Market Data"** —
   Pu Cheng, Juncheng Liu, Yunshen Long. arXiv 2604.14199, 2026-04-03. 38,666 binary Polymarket questions,
   7 LLMs, 36,165 predictions. Only 2 of 7 models achieved positive financial returns (MiMo-V2-Flash
   +17.6% CWR, Gemini-3-Flash +6.2% CWR); the other 5 lost money despite high confidence — "a gap between
   surface-level language fluency and genuine probabilistic reasoning under live market uncertainty."
   **Verified.** https://arxiv.org/abs/2604.14199

4. **"Large Language Models and Stock Investing: Is the Human Factor Required?"** — Ricardo Crisostomo,
   Diana Mykhalyuk. arXiv 2603.19944, 2026-03-20 (rev. 2026-04-20). Tested 4 LLMs (ChatGPT, Gemini,
   DeepSeek, Perplexity): "recurring reasoning failures, including financial misconceptions, carryover
   errors, and reliance on outdated or hallucinated information." Can beat the market only "when
   appropriately guided and supervised" — a mild positive result contingent on heavy human scaffolding, not
   autonomous edge. **Verified.** https://arxiv.org/abs/2603.19944

5. **"Cross-Stock Predictability via LLM-Augmented Semantic Networks"** — Yikuan Huang, Zheqi Fan, Kaiqi
   Hu, Yifan Ye. arXiv 2604.19476, 2026-04-21. LLM used to *filter* spurious edges in a text-derived
   corporate network rather than predict returns directly; long-short Sharpe 0.742→0.820, drawdown
   −10.47%→−7.85% on S&P 500, 2011–2019 backtest. Positive, but LLM-as-filter on network structure, not
   LLM-as-direct-predictor — and the backtest window predates the LLM era, so out-of-sample validity vs.
   training-data leakage isn't addressed in the abstract. **Verified, caveat noted.**
   https://arxiv.org/abs/2604.19476

6. **"Improving Financial Forecasting with a Synergistic LLM-Transformer Architecture"** — Sayed Akif
   Hussain et al. arXiv 2601.02878, 2026-01-06. LLM as sentiment/confidence signal fused with a price
   Transformer; 5.28% RMSE reduction vs. vanilla Transformer (p=0.003). Positive but modest; abstract gives
   no detail on out-of-sample/lookahead-bias controls. **Partially verified** — date/authors/headline
   result confirmed, backtest rigor not confirmable from the abstract alone. https://arxiv.org/abs/2601.02878

7. **"Impact of LLMs news Sentiment Analysis on Stock Price Movement Prediction"** — Walid Siala, Ahmed
   Khanfir, Mike Papadakis. arXiv 2602.00086, 2026-01-22 (rev. through 2026-03-09). DeBERTa/RoBERTa/FinBERT
   sentiment features vs. baseline LSTM/PatchTST: best single model 75% accuracy, ensemble ~80%, but
   sentiment-derived features gave only "slight" improvement over baseline. Weak-positive — sentiment adds
   little marginal edge. **Verified.** https://arxiv.org/abs/2602.00086

8. **QuantaAlpha: An Evolutionary Framework for LLM-Driven Alpha Mining** — Jun Han et al. arXiv 2602.07085,
   2026-02-06 (rev. 2026-05-18). Reports strong backtested numbers (IC 0.0472, 4.68% annualized; factor
   transfer 40.28%/19.1% cumulative excess return on CSI 500/S&P 500 over 4 years) but frames its own core
   contribution as *mitigating* overfitting to "noisy and non-stationary" markets — implying the naive
   version is prone to it. **Verified**, genuine out-of-sample validation beyond cross-market transfer not
   confirmable from the abstract alone. https://arxiv.org/abs/2602.07085

## 2. The memorization/contamination cluster — why apparent "edge" often isn't real

A specific 2026 sub-literature exists to isolate this, and it's the most load-bearing evidence for the
"no durable edge" conclusion:

- **MemGuard-Alpha** — Anisha Roy, Dip Roy. arXiv 2603.26797, 2026-03-26. 7 LLMs, 50 stocks, 42,800
  prompts, 5.5 years. In-sample accuracy rises with contamination (40.8%→52.5%) while out-of-sample
  accuracy *falls* (47%→42%) — apparent predictive skill from memorized training data doesn't transfer.
  Clean signals: 14.48 bps/day avg return vs. 2.13 bps for contaminated signals — a **7x gap**. **Verified.**
  https://arxiv.org/abs/2603.26797
- **"All Leaks Count, Some Count More"** — Zeyu Zhang, Ryan Chen, Bradly C. Stadie. arXiv 2602.17234,
  2026-02-19 (rev. 2026-05-25). Shapley-DCLR metric + TimeSPEC to detect/mitigate post-cutoff knowledge
  leaking into LLM backtests. **Verified.** https://arxiv.org/abs/2602.17234
- **"Detecting Lookahead Bias in LLM Forecasts"** — Zhenyu Gao, Wenxi Jiang, Yutong Yan. arXiv 2512.23847
  (v1 2025-12-29, **pre-2026** — flagging; v2 revised 2026-06-12). Predictive accuracy is artificially
  inflated pre-training-cutoff and "collapses essentially to zero" post-cutoff, on both news→return and
  earnings-transcript→capex tasks. **Verified.** https://arxiv.org/abs/2512.23847
- **"Can Blindfolded LLMs Still Trade?"** — Joohyoung Jeon, Hongchul Lee. arXiv 2603.17692, 2026-03-18.
  Anonymizes tickers/company names to test whether signal survives without memorized identity: Sharpe 1.40
  on 2025 YTD data survives anonymization, but alpha weakens in trending bull markets. **Verified.**
  https://arxiv.org/abs/2603.17692
- **Foundational source these build on**: "The Memorization Problem: Can We Trust LLMs' Economic
  Forecasts?" — Lopez-Lira, Tang, Zhu. arXiv 2504.14765 (v1 2025-04-20, v2 2025-12-15 — **2025, not 2026**,
  flagged as background/origin only). SSRN mirror 403'd, arXiv version confirmed.
  https://arxiv.org/abs/2504.14765
- **Positive-edge counterexample, for calibration (pre-2026, not a new finding)**: Lopez-Lira & Tang's 2023
  "Can ChatGPT Forecast Stock Price Movements?" (arXiv 2304.07619) found GPT-4 news-reaction signals
  generating ~34bps/day long-short returns pre-transaction-costs, decaying as adoption rises. This is the
  widely-cited positive result the 2026 contamination literature is reacting to/qualifying — background
  only, not independently re-verified this session.

## 3. Regulatory guidance, 2026

No 2026 regulator has issued LLM-specific trading rules. Guidance so far is exam-priority/governance
framing plus explicit hallucination and human-oversight warnings — not prediction-accuracy findings.

1. **SEC** — Brian Daly (Director, Division of Investment Management), speech "Artificial Intelligence and
   the Future of Investment Management," 2026-02-03, ICI Winter Board Meeting. Not a rule. Frames AI/LLMs
   as opportunity but flags: adviser liability exposure from AI-driven losses; AI removes humans from
   real-time decision loops (no "pull the plug" moment) unlike algo models; open questions on whether AI
   agents trigger marketing/registration rules; supervisory frameworks still undeveloped. sec.gov itself
   403'd; **verified via a secondary reproduction (tradersmagazine.com), cross-confirmed by date across
   multiple sources.** https://www.sec.gov/newsroom/speeches-statements/daly-020326-artificial-intelligence-future-investment-management

2. **SEC — 2026 Examination Priorities + AI-washing enforcement.** Flags "Emerging Financial Technology,"
   requires firms to substantiate AI marketing claims; six AI-washing cases (~$44M+ alleged fraud) cited,
   including action against firms claiming AI-enabled investment models when not actually using such
   technology. This is about *misrepresenting* AI use, not a documented case of an LLM trading system
   itself failing. **Unverified against a primary SEC litigation release this session** — corroborated only
   across independent secondary (law-firm) summaries; the underlying regulatory-priorities framing (SEC
   exam priorities + FINRA/NASAA joint AI-hype warnings) is better corroborated than the specific $44M figure.

3. **FINRA** — 2026 Annual Regulatory Oversight Report (published ~2025-12-09, covering 2026 priorities) +
   FINRA's standing AI guidance page (current through 2026-03-06). Names "large language models (LLMs) and
   other generative AI (GenAI) tools" explicitly in scope; instructs member firms to test for and mitigate
   hallucination and bias, maintain governance/WSPs covering AI in trading/fraud-prevention/back-office use,
   and supervise AI the way they supervise employees/systems (documented procedures, pre-deployment testing,
   post-deployment monitoring). **Verified by reading finra.org directly.**
   https://www.finra.org/rules-guidance/key-topics/artificial-intelligence

4. **ESMA** — "AI adoption and trends in securities markets: EU evidence" (TRV risk-analysis report),
   **2026-02-20**. Survey of 728 EU firms: AI adoption is "partial and uneven," concentrated in
   "low-autonomy, general-purpose back-office tools" — **not** yet materially in live trading/investment-decision
   autonomy. Top flagged risks: data/model vulnerabilities amplified by AI, cybersecurity, third-party/
   infrastructure-provider concentration risk. **Verified via finadium.com summary**, source PDF located
   (esma.europa.eu, 2026-02) but not separately fetched.
   https://finadium.com/esma-finds-partial-and-uneven-ai-adoption-in-securities-markets/
   — *Distinct from* ESMA's earlier, more specific MiFID II guidance (2024-05-30, **pre-2026**, doesn't name
   LLMs/GenAI specifically) — flagging explicitly since search results initially conflated the two.

## 4. Academic critiques: hallucination, overfitting, manipulation risk (2026)

5. **FinVerBench** — Silu Panda. arXiv 2605.29586, 2026-05-28. Tests whether LLMs can verify numerical
   consistency in SEC 10-K-derived financial statements (43 S&P 500 companies). Severe result: 9 of 14
   complete LLM runs produced **95–100% false positives on clean (correct) statements** — flagging correct
   data as wrong. **Verified.** https://arxiv.org/abs/2605.29586

6. **AutoRedTrader: Autonomous Red Teaming of Trading Agents through Synthetic Misinformation Injection** —
   Zhiwei Liu et al. (11 authors incl. Sophia Ananiadou). arXiv 2605.09185, 2026-05-09. Adversarial
   framework achieves 69.00% misinformation exposure rate and **26.67% attack success rate** against
   LLM-based trading agents using subtle, finance-specific (not obviously false) misinformation.
   **Verified.** https://arxiv.org/abs/2605.09185

7. **PHANTOM** (hallucination detection in financial long-context QA) — found via search snippet on
   OpenReview only; WebFetch hit a bot-verification wall, no title/author/date/venue recoverable.
   **Explicitly unverified — do not cite as a confirmed 2026 finding.**

8. **FAITH** (tabular hallucinations in finance) — arXiv 2508.05201. **ID indicates August 2025, pre-2026.**
   Found via snippet only, not opened. Background only.

## 5. Documented real-world failure cases — searched, found nothing verifiable

Searches for a named, verifiable 2026 postmortem of an LLM-based trading system failing in the real world
(as opposed to a research benchmark) turned up nothing meeting the verification bar:

- Retail "AI trading bot" complaints (traders paying $300–$1,200/month for bots that broke during Q1 2026
  EUR/USD volatility) — sourced only from blog-aggregator content, no named company/regulator/outlet.
  **Not reported as a verified finding.**
- "Hedge funds retreat from AI positions" (mid-2026 financial press) — this is about crowded hedge-fund
  *equity positions in AI-theme stocks* unwinding, **not** LLM-driven trading decisions failing. Wrong
  topic, excluded.
- No SEC/FINRA enforcement action, exchange halt, or fund closure explicitly attributed in a verifiable
  primary source to an LLM-based trading system's decision failure was found dated 2026.

## Bottom line vs. AMI's internal finding

Consistent with it. (a) The memorization/contamination cluster (§2) shows apparent LLM predictive skill on
price/return tasks substantially evaporates once contamination is controlled for. (b) The hedge-fund-
perspective review (§1.1) explicitly recommends LLMs for interpretive/factual tasks over standalone price
forecasting — the same split AMI's own Phase 1 (closed negative) / Phase 2 (working) found. (c) The
long-horizon backtest paper (§1.2, 2026-updated) finds LLM investing strategies' edge deteriorates under
broader/longer evaluation, matching AMI's cross-sectional-ranking result (AUC collapses to 0.5055 once
market-regime drift is stripped out). Countervailing positive results exist (§1.3, §1.8) but each carries a
small-model-subset caveat, an unaddressed contamination caveat, or a pre-LLM-era backtest window.
