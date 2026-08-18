# LLM fundamentals/filing analysis research, and industry publications — 2026

Companion to [01_prediction_edge_and_caution.md](01_prediction_edge_and_caution.md): where that file covers
*prediction*, this covers *interpretation* — LLMs reading filings/statements/reports for equity research —
which is the closer analogue to AMI's own working Phase 2 pipeline
([`../quant_finance/fundamentals_llm.md`](../quant_finance/fundamentals_llm.md)) and to the Fundamentals
Analyst agent. Every item opened and verified directly unless noted.

---

## 1. Academic: LLM-based fundamentals/filing analysis

1. **IPO Finance Agent: Benchmark of LLM Financial Analysts... on the SpaceX (SPCX) IPO** — Mostapha
   Benhenda. arXiv 2606.23032, 2026-06-22 (v3 2026-06-30). Extends the "Finance Agent v2" benchmark from
   10-K/10-Q analysis to S-1 IPO registration statements; contextual retrieval instead of naive chunking,
   automated rubric-generation/audit pipeline. Top models ~80% accuracy. **Verified.**
   https://arxiv.org/abs/2606.23032

2. **Evaluating LLMs in Financial NLP: A Comparative Study on Financial Report Analysis** — Md Talha
   Mohsin. arXiv 2507.22936 (original submission 2025-07-24, **pre-2026** — only the v2 revision,
   2026-01-19, is new). 5 LLMs on QA over the Business section of US 10-K filings, human + automated
   metrics: no single model dominates, results are conditional not general reliability claims. **Verified.**
   https://arxiv.org/abs/2507.22936

3. **When Summaries Distort Decisions: Information Fidelity in LLM-Compressed Financial Analysis** — Lee,
   Park, Lee, et al. (18 authors). arXiv 2606.29251, 2026-06-28 (v2 2026-07-08). LLM summaries of earnings
   calls/SEC filings can be fluent and "factually plausible" yet still alter investment decisions, via
   decontextualization and model-to-model divergence. Proposes "Agentic Context Compression" as a fix.
   **Verified.** https://arxiv.org/abs/2606.29251

4. **FinReporting: An Agentic Workflow for Localized Reporting of Cross-Jurisdiction Financial
   Disclosures** — Zhang, Song, Elbadry, Chen, et al. (22 authors). arXiv 2604.05966, 2026-04-07 (rev.
   2026-05-15). Maps US/Japan/China filings into a canonical ontology, LLMs as constrained verifiers rather
   than free-form generators. **Verified.** https://arxiv.org/abs/2604.05966

5. **Generative AI for Stock Selection** — Keywan Christian Rasekhschaffe. arXiv 2602.00196, 2026-01-30.
   LLM+RAG generates economically-grounded features from analyst reports/options/price-volume data as
   inputs to ML return-prediction models; Sharpe improvements of 14–91% depending on dataset, generated
   signals weakly correlated to traditional factors. **Verified.** https://arxiv.org/abs/2602.00196

6. **Fin-Analyst at FinMMEval 2026 Task 3: A Live Hybrid Trading Agent with LLM Specialists and Rule-Based
   Signals** — Rashid, Hong, Ding, Hossain. arXiv 2607.12233, 2026-07-14. Eight-specialist LLM pipeline
   (news, SEC filings, fundamentals, analyst forecasts, technicals, sentiment) for TSLA — structurally
   close to AMI's own agent-per-domain design. Ranked **#1 on the official FinMMEval 2026 leaderboard**
   (+13.51% return, Sharpe 4.10, 88% win rate); 8-K disclosures were the most impactful fundamentals
   signal. **Verified.** https://arxiv.org/abs/2607.12233

7. **Signal or Noise in Multi-Agent LLM-based Stock Recommendations?** — Fatouros, Metaxas. arXiv
   2604.17327, 2026-04-19. Live-deployed MarketSenseAI system with News/Fundamentals/Dynamics/Macro
   agents; strong-buy S&P 500 portfolio +25.2% compound excess return (99.7th percentile significance);
   agent-contribution "leadership" rotates by regime — fundamentals lead on S&P 500. **Verified.**
   https://arxiv.org/abs/2604.17327

8. **One Size Fits None: Heuristic Collapse in LLM Investment Advice** — Jillian Ross, **Andrew W. Lo**
   (MIT). arXiv 2604.23837, 2026-04-26. LLM investment-advice recommendations are dominated almost
   entirely by self-reported risk tolerance, with other client-specific factors contributing minimally
   ("heuristic collapse") — a real reliability finding for LLM-generated recommendations, from a
   name-brand author. **Verified.** https://arxiv.org/abs/2604.23837

9. **BigFinanceBench: A Workflow-Grounded Benchmark for Financial-Research Agents** — Wang, Meinhardt,
   Katz, Kim, Chaudhary, Blagden, Xu. arXiv 2606.03829, 2026-06-02. 928 expert-authored financial-research
   tasks scored on 36,241 rubric points (auditability of *how* an answer was derived, not just the final
   number); best of 10 frontier/open-weight agents scored only **58.8%**. **Verified.**
   https://arxiv.org/abs/2606.03829

10. **FinRetrieval: A Benchmark for Financial Data Retrieval by AI Agents** — Kim, Huang. arXiv 2603.04403,
    2026-01-02. 500 retrieval questions, 14 agent configs (Anthropic/OpenAI/Google): tool access dominates
    performance — Claude Opus swings from 19.8% (web search) to 90.8% (structured API). Directly relevant
    to AMI's own yfinance-vs-OpenBB structured-access finding. **Verified.**
    https://arxiv.org/abs/2603.04403

11. **InvestLogicBench: Evaluating Investment Logic in Large Language Models** — Jiang, Zou, Lin, Yu,
    Huang, Jia, Dai. arXiv 2608.06108, 2026-08-06 (most recent item in this whole survey). 201,247
    documented decisions from 151 real investors: LLM reasoning is "logically plausible" (~4/5) but weakly
    grounded in actual events (0.8–2.8/5) — outcome-only metrics miss this gap. **Verified.**
    https://arxiv.org/abs/2608.06108

12. **From Knowing to Doing: A Memory-Controlled Benchmark for LLM Trading Agents (KTD-Fin)** — Zhu, Zhao,
    Sun, Luan, et al. arXiv 2605.28359, 2026-05-27. Barra-style attribution decomposition shows most
    LLM-agent "returns" are market/style beta, not stock-selection alpha, once data leakage is masked —
    directly echoes AMI's own cross-sectional finding (Phase 1, "the signal is beta timing, not stock
    selection"). **Verified.** https://arxiv.org/abs/2605.28359

*Context only, pre-2026, not counted as new findings:* "Generative AI for Analysts" (arXiv 2512.19705,
2025-12-12 — FactSet AI natural experiment, AI raises report breadth/timeliness but **increases** forecast
error 59%); "Finance Agent Benchmark" (arXiv 2508.00828, 2025-05-20 — the original Vals AI paper, best
model only 46.8% accuracy).

---

## 2. Industry research — real research vs. marketing, tagged explicitly

**Real research:**

1. **"Generative AI and Investment Research: Evidence from Analyst Reports"** — Huang, Hugon, Zhang, Zheng.
   SSRN abstract 6682498, posted 2026-01-31. Large-sample study (ML-detected AI-assisted analyst reports):
   GenAI use raises earnings-forecast accuracy — especially for high-workload/lower-skill analysts — with
   causal identification via an overlapping-earnings-calls workload shock; AI-assisted reports also trigger
   stronger market reactions. SSRN page 402'd; **verified via corroborating secondary source**, not the
   primary PDF.

2–4. **Journal of Accounting Research 2026 special issue on Generative AI in Capital Markets** — real,
   peer-reviewed, industry-adjacent (built on real sell-side/Seeking Alpha data). All three Wiley DOI pages
   402/403'd; **verified via search-indexed abstracts, not full text**:
   - Cao, Chen, Ma, Srinivasan — synthesizes 6 conference papers around a 3-layer framework
     (production/dissemination/processing); information-verification cost is the binding constraint.
   - Blankespoor, deHaan, Li — detectable GAI-written text up to **4.5% of new text in 2024** across
     earnings releases, call remarks, risk factors, MD&A, IPO filings.
   - Bradshaw, Ma, Yost, Zou — AI-written Seeking Alpha content peaked at 13.5% post-ChatGPT, fell after a
     2023 AI ban; AI adopters more productive but their articles are **less informative** (smaller
     trading-volume/return reactions than human articles).

5. **Bridgewater AIA Labs + Thinking Machines Lab — "Learning to Replicate Expert Judgment in Financial
   Tasks"**. Su, Zhu, Xiao, Alur, Kang. Published 2026-06-30 on thinkingmachines.ai. Rigorous technical
   writeup: frontier models (GPT-5.5, Claude Opus 4.8, Gemini 3.1 Pro) **plateau at ~78%** on six
   financial-document-triage tasks even with expert prompts; fine-tuning Qwen3-235B (interleaved batch
   training + CISPO loss + on-policy distillation, each ablated) reaches **84.7%**, a 29.8% error reduction,
   at **13.8x lower inference cost** than the best frontier model. **Verified by reading the source
   directly.** https://thinkingmachines.ai/news/learning-to-replicate-expert-judgment-in-financial-tasks/
   — the single most methodologically rigorous industry item found this session.

6. **Man Group — "A Trend Following Deep Dive: AlphaTrend and Agentic Research Workflows"**. Luk, Abou
   Zeid, van Hemert. Published 2026-02-11 on man.com. Internal "AlphaTrend" agentic system: parallel
   LLM-driven signal-idea generation, three validation experiments with actual backtested Sharpe-ratio
   distributions and cumulative-return curves vs. a benchmark breakout signal, plus a documented
   Claude-vs-GPT-5 creativity comparison. Trend-following/quant-signal research rather than
   fundamentals-based equity research, but genuine methodology+data from a major buy-side firm.
   **Verified.** https://www.man.com/insights/alphatrend-agentic-research-workflows

**Marketing content (real numbers present, but promotional framing — tagged so, not excluded):**

7. **Anthropic — "Agents for financial services"**. Published 2026-05-05. Ten agent templates, GitHub
   repo, MCP data connectors (Moody's, Dun & Bradstreet, Fiscal AI). One quantified figure (Claude Opus 4.7
   at 64.37% on Vals AI's Finance Agent benchmark); otherwise product announcement + testimonials.
   https://www.anthropic.com/news/finance-agents

8. **Daloopa — vendor-sponsored benchmark report**. Published 2026-02-10 (PR Newswire). OpenAI Agents
   SDK/GPT-5.2, Anthropic Agent SDK/Claude Opus 4.5, Google ADK/Gemini 3 Pro on 500 financial questions:
   structured-database access lifted accuracy up to 71 points to ~90% vs. public web sourcing; flags
   fiscal-calendar/naming-convention failure modes. Real comparative numbers, no confidence intervals or
   independent review, promotes Daloopa's own product.

9. **Two Sigma — "AI in Investment Management: 2026 Outlook"**. Published 2026-01-12. Executive-perspective
   opinion piece, no methodology/data/benchmarks.

**Checked and came up empty for real 2026 technical research:** Goldman Sachs, BlackRock, JPMorgan, Morgan
Stanley — only general market/AI outlook pieces or internal-tool PR (e.g. JPMorgan's LLM Suite rollout), no
disclosed-methodology whitepaper on LLM fundamentals/filing-analysis performance. S&P Global/Kensho's "S&P
AI Benchmarks" (genuine long-document-QA-over-filings methodology) is real but dated 2024–2025 — Kensho
stopped updating it in 2026 rather than publishing new findings. Rogo's technical material is 2024-dated
and third-party-described as "self-reported and promotional, not independently verified" — excluded as
marketing, not counted as a 2026 research item.

---

## Bottom line

The 2026 fundamentals-analysis literature is more consistently positive than the prediction-edge literature
(01), but with real, specific failure modes worth carrying forward: summarization can distort decisions
even when individually accurate (item 3), pure LLM-judge verification of numbers is dangerous (FinVerBench,
see [01](01_prediction_edge_and_caution.md) §4 — 95-100% false-positive rate flagging *correct* statements),
and structured/API data access matters far more than model choice for retrieval accuracy (item 10, and
Daloopa's vendor number). The Bridgewater/Thinking Machines result (item 5) is the strongest evidence found
this session that a smaller, cheaper, domain-tuned model can beat frontier general models on this exact
class of task — directly relevant to the open-weight-model question in
[04_new_models_and_training.md](04_new_models_and_training.md).
