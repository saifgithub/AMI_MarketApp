# Multi-agent LLM trading frameworks, and new 2026 finance-agent benchmarks

Directly relevant to AMI Trade's own architecture — forked from TradingAgents
(`/Volumes/Extreme Pro/TradingAgent/`, frozen `7e9e7b8`; see
[`CR167_tradingagents_upstream_drift`](../../../forward_planning/CR167_tradingagents_upstream_drift/) for
the code/prompt-level upstream diff, which this file doesn't duplicate — this covers the broader
academic/framework field, not the upstream repo's own commits). Every item opened and verified directly
unless noted. arXiv IDs use YYMM format.

---

## 1. TradingAgents itself, and a direct empirical follow-up

**TradingAgents: Multi-Agents LLM Financial Trading Framework** — Yijia Xiao, Edward Sun, Di Luo, Wei Wang.
arXiv 2412.20138, submitted 2024-12-28, latest revision (v7) 2025-06-03. Fundamental/sentiment/technical
analysts + Bull/Bear researchers + risk management + trader/fund-manager roles, debate-driven decisions;
claims gains over baselines on cumulative return, Sharpe, max drawdown. Pre-2026, background only — but the
framework kept shipping through 2026 per its GitHub releases (verified): v0.2.5 (2026-05-11, grounded
sentiment analyst + regional providers), v0.3.0 (2026-06-22, verified data-access contract, new providers
incl. NVIDIA NIM/Kimi/Groq/Mistral, FRED + Polymarket data), v0.3.1 (2026-07-05, correctness/stability
fixes, Claude Sonnet 5 + Fable 5 support). https://github.com/TauricResearch/TradingAgents/releases

**Reproducibility in the TradingAgents Framework** — venue: Proceedings of the 2026 International
Conference on Artificial Intelligence and Fintech (ACM DL, DOI 10.1145/3800973.3801029). Authors not
recoverable — the ACM DL page 403'd; abstract corroborated consistently across multiple independent
search-index snippets quoting the same text, so reported here **with author names flagged unverified**.
Runs TradingAgents with GPT-4o and Qwen3:30B on Google stock (May–Jul 2025), varying temperature/seed/
sampling. **Finding: mean returns 15.8%±4.2% (GPT-4o) and 18.1%±2.8% (Qwen3:30B) vs. 19.1% (GOOGL
buy-and-hold) / 17.4% (QQQ buy-and-hold)** — confidence intervals overlap the passive benchmarks, i.e. the
framework does not reliably beat buy-and-hold once output stochasticity is accounted for; the ~50%-of-
expected-return variance is itself the headline finding. https://dl.acm.org/doi/10.1145/3800973.3801029

**Toward Expert Investment Teams: A Multi-Agent LLM System with Fine-Grained Trading Tasks** — Kunihiro
Miyazaki, Takanobu Kawahara, Stephen Roberts, Stefan Zohren. arXiv 2602.23330, 2026-02-26. Argues
fine-grained task decomposition (vs. TradingAgents-style abstract instructions) improves risk-adjusted
returns on Japanese equities; portfolio optimization across low-correlated agent outputs adds further
gains. **Verified.** https://arxiv.org/abs/2602.23330

## 2. New competing/parallel multi-agent frameworks, 2026

- **AlphaLogics** — Weng, Zhang, Wang, Xia. arXiv 2603.20247, 2026-03-10. Multi-agent system
  (mining/generation/optimization agents) for interpretable alpha-factor generation via "market logic"
  mining + backtesting-guided refinement, tested on CSI 500 and S&P 500. **Verified.**
  https://arxiv.org/abs/2603.20247
- **PolySwarm** — Barot, Borkhatariya. arXiv 2604.03888, 2026-04-04. 50-persona LLM swarm for Polymarket
  prediction-market trading; confidence-weighted Bayesian aggregation + quarter-Kelly sizing +
  latency-arbitrage module; swarm aggregation beats single-model baselines on probability calibration.
  **Verified.** https://arxiv.org/abs/2604.03888
- **FinRL-X: An AI-Native Modular Infrastructure for Quantitative Trading** — Yang, Zhang, She, Liao,
  Zhang. arXiv 2603.21330, 2026-03-22. Not LLM-agent-debate style like TradingAgents — a production-grade
  unified framework spanning backtesting→live deployment, supporting RL and LLM-sentiment components.
  **Verified.** https://arxiv.org/abs/2603.21330

**Explicitly checked and not found**: a genuine 2026 update to FinRobot — a search snippet claimed a
"FinRobot Desktop v0.1.0" 2026 release, but the actual GitHub releases page shows that tag dated 2024-07-07.
**Retracting that snippet explicitly.** No verified 2026 news on FinMem or StockAgent either — only their
original pre-2026 papers turned up.

## 3. New empirical benchmarks/backtests of multi-agent or LLM trading performance, 2026

- **TraderBench** — Yuan, Xu, Xu, Zou, Xiong. arXiv 2603.00285, 2026-02-27. Expert-verified static tasks +
  adversarial trading simulations (crypto + options); 13 models, ~50 tasks: most models use fixed
  non-adaptive strategies, extended reasoning helps knowledge tasks but not actual trading performance.
  **Verified.** https://arxiv.org/abs/2603.00285
- **StockBench** — Chen, Yao, Liu, Xin, Ye, Yu, Hou, Li. arXiv 2510.02209 (originally 2025-10-02, **v2
  revised 2026-03-02**). Daily prices/fundamentals/news; multi-month cumulative return/max drawdown/
  Sortino: most models fail to beat buy-and-hold despite strong financial-QA scores. **Verified**, noting
  original submission predates 2026. https://arxiv.org/abs/2510.02209
- **PredictionMarketBench** — Arora, Malpani. arXiv 2602.00133, 2026-01-28. SWE-bench-style deterministic
  replay benchmark for algorithmic/LLM trading agents on Kalshi prediction markets (crypto/weather/sports);
  naive agents struggle with fees/settlement risk, fee-aware algorithmic strategies stay competitive.
  **Verified.** https://arxiv.org/abs/2602.00133
- **Herculean: An Agentic Benchmark for Financial Intelligence** — 63 authors led by Xueqing Peng, incl.
  Arman Cohan, Sophia Ananiadou, Junichi Tsujii. arXiv 2605.14355, 2026-05-14 (v3 2026-05-29). Four
  professional-workflow domains: Trading, Hedging, Market Insights, Auditing — frontier agents do better on
  Trading/Market Insights than Hedging/Auditing, exposing a reasoning-vs-reliable-execution gap.
  **Verified.** https://arxiv.org/abs/2605.14355
- **LATTICE** — Chan, Li, Xiao, Chen, Du, Ren. arXiv 2604.26235, 2026-04-29. Crypto-copilot
  decision-support benchmark, 6 evaluation dimensions, 16 task types, LLM-judge scoring; 6 real crypto
  copilots on 1,200 queries show similar overall scores but meaningfully different per-dimension
  tradeoffs. **Verified.** https://arxiv.org/abs/2604.26235
- **CoffeeBench** — Sugiura, Hattori, Araragi, Ogawa, Onose, Makino, Usuki, Ishida. arXiv 2606.16613,
  2026-06-15. Tangential — 90-day simulated multi-firm coffee supply-chain economy, one LLM-controlled
  roaster vs. scripted competitors: stronger models communicate more, some get stuck in inaction loops.
  Economic multi-agent, not securities trading, flagged as adjacent not on-topic. **Verified.**
  https://arxiv.org/abs/2606.16613

## 4. Survey/meta papers on the field, 2026

- **Agentic Trading: When LLM Agents Meet Financial Markets** — Xia, You, Wang, Liu, Qi, Wu, Zhang. arXiv
  2605.19337, 2026-05-19. Systematic review, 77 studies, evidence-map methodology. **Core finding: only
  2/19 rigorously-evaluated studies report time-consistent train/test splits, only 1/19 has an explicit
  transaction-cost model** — the field's bottleneck is evaluation rigor/reproducibility, not architecture
  novelty. Does not mention TradingAgents by name in the fetched content. **Verified.**
  https://arxiv.org/html/2605.19337v1
- **Toward Reliable Evaluation of LLM-Based Financial Multi-Agent Systems: Taxonomy, Coordination Primacy,
  and Cost Awareness** — Nguyen, Pham. arXiv 2603.27539, 2026-03-29. Taxonomizes 12 multi-agent systems + 2
  baselines by architecture/coordination/memory/tools; proposes the falsifiable "Coordination Primacy
  Hypothesis" (coordination design matters more than model scale); identifies 5 biases that can flip the
  sign of reported returns — look-ahead, survivorship, backtest overfitting, transaction-cost neglect,
  regime-shift blindness; introduces a "Coordination Breakeven Spread" metric. Does not mention
  TradingAgents by name in the fetched content. **Verified.** https://arxiv.org/html/2603.27539v1

## 5. New financial-domain LLM benchmarks, 2026 (tool-use/agentic-workflow generation)

A real shift is visible here: away from FinBen-style static QA, toward long-horizon, tool-grounded,
execution-verified evaluation.

- **FinTradeBench** — Agrawal, Dutta, Hasan, Karmaker, Dutta. arXiv 2603.19225, 2026-03-19. 1,400 questions
  on NASDAQ-100 fundamentals + trading signals over a decade; 14 LLMs zero-shot/RAG: retrieval helps
  fundamentals reasoning but not time-series trading-signal reasoning. Does not mention TradingAgents or
  FinBen. **Verified.** https://arxiv.org/abs/2603.19225
- **FinMCP-Bench** — Zhu, Tian, Li, Wu, Liang, Li, Zhang, Guo, Chen, Liu, Zhang. arXiv 2603.24943,
  2026-03-26. 613 samples / 10 scenarios / 33 sub-scenarios / 65 real financial MCP tools; single/multi-tool/
  multi-turn tasks; standardized testbed for financial tool-invocation + reasoning accuracy. **Verified.**
  https://arxiv.org/abs/2603.24943
- **FinToolBench** — Lu, Wang, Wang, Tang, Zeng, Chen, Pi, Deng, Chen, Fu, Yang, Sun. arXiv 2603.08262,
  2026-03-09 (v2 2026-08-01). First real-world financial-tool-execution benchmark: 760 executable tools,
  295 tool-required queries, scored beyond success/failure on timeliness, intent-type, regulatory
  compliance; introduces FATR baseline. **Verified.** https://arxiv.org/abs/2603.08262
- **FinTrace** — Cao, Li, Liu, Cao, Xu, Qian, Peng, Tang, Yao, Huang, Subbalakshmi, Zhu, Suchow, Yu. arXiv
  2604.10015, 2026-04-11 (v3 2026-08-10). 800 expert-annotated trajectories, 34 financial task categories,
  9 metrics across action/efficiency/process/output quality: **models pick the right tools but reason
  poorly over what the tools return.** **Verified.** https://arxiv.org/abs/2604.10015
- **CLEF-2026 FinMMEval Lab** — Xie, Elbadry, Zhang, Georgiev, Peng, Qian, Huang, Dimitrov, Jani, Dai,
  Geng, Wang, Koychev, Stoyanov, Nakov. arXiv 2602.10886, 2026-02-11. First multilingual + multimodal
  financial-LLM eval lab; 3 tasks: Financial Exam QA, Multilingual Financial QA (PolyFiQA), Financial
  Decision Making. **Verified.** https://arxiv.org/abs/2602.10886 — Fin-Analyst's #1 leaderboard placement
  (see [02_fundamentals_and_industry.md](02_fundamentals_and_industry.md) item 6) is on this benchmark's
  Task 3.
- **IPO Finance Agent** — see [02_fundamentals_and_industry.md](02_fundamentals_and_industry.md) item 1;
  extends Vals AI's Finance Agent v2 to IPO due-diligence over SEC S-1 filings. Results: Zhipu GLM-5.2
  highest accuracy (79.8%), Xiaomi MiMo-2.5 Pro best cost-efficiency ($0.05/query, 77.2%).
- **FinVault** — Yang et al. (18 authors). arXiv 2601.07853, 2026-01-09. First execution-grounded security
  benchmark for financial agents: 31 regulatory-case sandbox scenarios, 107 real weaknesses, 963 test
  cases across prompt injection/jailbreak/finance-specific attacks; attack success rates up to 50% even on
  the most robust models. **Important: withdrawn by the authors on 2026-07-30 citing legal/IP concerns —
  cite with that caveat if at all.** https://arxiv.org/abs/2601.07853
- **Herculean** (§3 above) doubles as a 2026 agentic-finance benchmark.

**Context, not a benchmark paper itself**: FinNLP 2026, the 11th ACL SIG-FinTech Workshop on Financial
Technology and NLP, co-located with EMNLP 2026 (Budapest, 2026-10-24/29), is soliciting new "FinEval"
shared-task benchmark proposals (task proposals due 2026-06-20, final task list 2026-07-01, system papers
due 2026-08-11) — more FinNLP-track benchmarks are still being minted for later in 2026.
https://sigfintech.github.io/finnlp2026/

---

## Bottom line

The empirical mood around TradingAgents/multi-agent trading systems has turned skeptical in 2026: an
independent ACM reproducibility study, StockBench's 2026 revision, TraderBench, and two 2026 survey papers
all converge on the same message — these systems mostly fail to beat buy-and-hold once stochasticity,
transaction costs, and evaluation-protocol rigor are accounted for, and **the field's bottleneck is
reproducible evaluation, not agent-architecture novelty**. Separately, Feb–Jun 2026 saw a real proliferation
of tool-use/agentic-workflow financial benchmarks (FinMCP-Bench, FinToolBench, FinTrace, Herculean, CLEF
FinMMEval, FinTradeBench) — worth tracking for future model/pipeline evaluation, distinct from the
older FinBen-style static-QA benchmarks AMI has referenced before.
