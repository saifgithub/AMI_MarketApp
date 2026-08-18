# LLM models & stock trading — 2026 research update

**Compiled 2026-08-18.** Saiful: *"lets update our research in LLM models and stock trading. Find any new
research and lets look for newer training material."* Four parallel research passes (all sources opened
and verified directly — arXiv abstracts, HF model/dataset cards, regulator pages, industry blogs — not
taken from search snippets alone; every item below is tagged with how well it was verified).

This picks up from two things already on record:
- AMI's own internal research: [`../quant_finance/`](../quant_finance/) — Phase 1 (GBM price prediction)
  closed negative, Phase 2 (LLM fundamentals interpretation) working.
- The TradingAgents upstream code/prompt diff:
  [`CR167_tradingagents_upstream_drift`](../../../forward_planning/CR167_tradingagents_upstream_drift/) —
  what changed in the *repo AMI forked from*, commit by commit. This folder covers the broader field
  instead: academic literature, competing frameworks, new benchmarks, and new self-hostable models — not
  duplicated with CR167.

## Documents

| Doc | Contents |
|---|---|
| [01_prediction_edge_and_caution.md](01_prediction_edge_and_caution.md) | Does the 2026 literature find real price/return prediction edge from LLMs? Plus the memorization/contamination cluster, 2026 regulatory guidance (SEC/FINRA/ESMA), and hallucination/red-teaming findings |
| [02_fundamentals_and_industry.md](02_fundamentals_and_industry.md) | LLM-based filing/fundamentals analysis research, and industry publications — explicitly tagged real research vs. marketing content |
| [03_frameworks_and_benchmarks.md](03_frameworks_and_benchmarks.md) | Multi-agent trading frameworks (TradingAgents follow-ups, competitors) and new 2026 tool-use/agentic finance benchmarks |
| [04_new_models_and_training.md](04_new_models_and_training.md) | New open-weight finance-tuned models, training datasets, training-methodology papers, and what's actually deployable on AMI's own GB10 hardware |
| [05_nemotron_finance_pilot_brief.md](05_nemotron_finance_pilot_brief.md) | **Added 2026-08-18.** Scoped pilot brief for the LLM team — includes a correction to item 4 below (the "DSpark" quant is a speculative-decoding draft model, not deployable itself) |

## Headline findings

**1. The field corroborates AMI's own Phase 1/Phase 2 split, independently.** A specific 2026
sub-literature exists just to isolate memorization/lookahead contamination in LLM price-prediction claims
(MemGuard-Alpha: 7x return gap between clean and contaminated signals; "Detecting Lookahead Bias":
accuracy "collapses essentially to zero" post-cutoff). The field's own 2026 hedge-fund-perspective review
recommends LLMs for *interpretation* over *price forecasting* — the same conclusion AMI reached testing
LightGBM exhaustively and finding no usable edge, then pivoting to fundamentals-to-LLM. KTD-Fin's
Barra-style attribution finding — most LLM-agent "returns" are market/style beta, not stock-selection alpha
— directly echoes AMI's own cross-sectional result (AUC collapses to 0.5055 once market-regime drift is
stripped out). See [01](01_prediction_edge_and_caution.md).

**2. The empirical mood around TradingAgents-style multi-agent systems has turned skeptical in 2026.** An
independent ACM reproducibility study running TradingAgents itself found its returns' confidence intervals
overlap buy-and-hold once output stochasticity is accounted for. Two 2026 survey papers (77 studies; 12
systems taxonomized) converge on the same message: the field's bottleneck is reproducible evaluation
methodology (train/test leakage, transaction costs, look-ahead bias), not agent-architecture novelty. See
[03](03_frameworks_and_benchmarks.md) §1, §4.

**3. Real, specific failure modes worth carrying forward**, even where LLMs work: summaries can distort
investment decisions while individually staying "factually plausible" (item in
[02](02_fundamentals_and_industry.md) §1.3); pure LLM-judge verification of financial numbers is
dangerous — FinVerBench found 9/14 model runs producing 95-100% false positives flagging *correct*
financial statements as wrong ([01](01_prediction_edge_and_caution.md) §4); a GRPO training paper found an
untrained base model ranked *last* under LLM-judge scoring but *second* under a rigorous causal audit — a
concrete warning about judge-reward gaming ([04](04_new_models_and_training.md) §5), directly relevant to
why AMI's own safety floor is structural rather than prompt-based (`CLAUDE.md`: *"prompt instructions are
not controls"*).

**4. One genuinely actionable development for AMI's own infra — with a correction.** NVIDIA shipped an
official NVFP4 quantization of the exact Nemotron base model AMI already dual-model-tested against Qwen3.6
(`nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — **not** the `-DSpark`-suffixed repo originally
cited here, which turned out to be a 1.35GB speculative-decoding draft model, not a deployable quant; see
the correction in [04](04_new_models_and_training.md) §4). A third party (Fastino) also shipped a
finance-tuned LoRA on the same base with honest, frontier-model-compared benchmark numbers — but merged
onto the *unquantized* BF16 base, not the NVFP4 one. Nobody has combined the two yet, so this isn't a
solved gap — it's a scoped, real pilot. Brief for the LLM team:
[05_nemotron_finance_pilot_brief.md](05_nemotron_finance_pilot_brief.md).

**5. Structured data access matters more than model choice for retrieval accuracy** — FinRetrieval found
Claude Opus swinging from 19.8% (web search) to 90.8% (structured API) on the same retrieval task; a
vendor benchmark (Daloopa) independently found similar-sized swings. This is the same lesson AMI's own
research already learned the hard way (yfinance `.info` vs. OpenBB's filed statements — see
[`../quant_finance/vs_ami_fundamentals_analyst.md`](../quant_finance/vs_ami_fundamentals_analyst.md)) now
corroborated at a broader scale. See [02](02_fundamentals_and_industry.md) item 10.

## What was explicitly checked and found nothing verifiable

Listed in full in each doc rather than omitted — no 2026 FinGPT/FinMA/PIXIU successor; no verifiable
real-world postmortem of an LLM trading system failing in production; no live current rankings on either
HF finance leaderboard (JS-rendered, couldn't pull); no 2026 FinRobot/FinMem/StockAgent updates (one
search-snippet claim about a "2026 FinRobot release" was checked and retracted — the GitHub tag is
actually from 2024).
